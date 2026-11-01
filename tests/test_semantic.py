"""P6：语义检索测试（用假 embeddings 避免下载模型）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.indexer.fts5 import Fts5Index
from app.core.indexer.service import IndexService
from app.core.search import SearchService
from app.core.semantic import SemanticIndex
from app.core.vault import Vault


def _fake_embed(self, texts: list[str]) -> list[list[float]]:
    """假向量：按维度词的字符出现次数，最后加一维常量避免零向量。

    travel 与「旅游」共享同一维，用来模拟“字面不同但语义相同”的召回。
    """
    travel = [t.count("旅游") + t.count("travel") for t in texts]
    return [[v, t.count("容器"), 0.2] for t, v in zip(texts, travel, strict=True)]


@pytest.fixture
def semantic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(SemanticIndex, "_embed", _fake_embed)
    # 查询走同一个假向量（真实实现会调 fastembed.query_embed）
    monkeypatch.setattr(SemanticIndex, "_embed_query", lambda self, t: _fake_embed(self, [t])[0])
    return SemanticIndex(
        db_path=tmp_path / "vectors.db",
        model_name="fake-model",
        cache_dir=tmp_path / "models",
    )


def test_rebuild_and_search(semantic: SemanticIndex) -> None:
    docs = [
        {"doc_id": "d1", "title": "部署方案", "tags": "", "body": "本机模型部署步骤"},
        {"doc_id": "d2", "title": "旅游规划", "tags": "", "body": "成都旅游安排"},
        {"doc_id": "d3", "title": "宝宝食谱", "tags": "", "body": "辅食做法"},
    ]
    result = semantic.rebuild(docs)
    assert result["vectors"] == 3
    assert semantic.status()["ready"] is True

    hits = semantic.search("模型部署")
    assert hits[0][0] == "d1"
    assert hits[0][1] > 0.9


def test_search_before_rebuild_is_empty(semantic: SemanticIndex) -> None:
    assert semantic.search("模型") == []


def test_upsert_and_remove(semantic: SemanticIndex) -> None:
    semantic.rebuild([{"doc_id": "d1", "title": "部署", "tags": "", "body": "模型"}])
    semantic.upsert_docs([{"doc_id": "d2", "title": "旅游", "tags": "", "body": "成都旅游"}])
    assert semantic.count() == 2
    semantic.remove(["d1"])
    assert semantic.count() == 1


def _build_index(tmp_path: Path) -> IndexService:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "docker.md").write_bytes("docker 容器实践".encode())
    (root / "旅游.md").write_bytes("成都 近郊 旅游 规划".encode())
    vault = Vault(root=root)
    svc = IndexService(vault=vault, backend=Fts5Index(db_path=tmp_path / "index.db"))
    svc.full_rebuild()
    return svc


def test_semantic_recalls_doc_without_keyword_hit(
    tmp_path: Path, semantic: SemanticIndex
) -> None:
    """关键词零命中（英文 travel）时，语义通道仍能召回中文「旅游」笔记。"""
    index = _build_index(tmp_path)
    semantic.rebuild(index.iter_docs())
    baseline = SearchService(index).search("travel", page=1, page_size=10)
    assert baseline["total"] == 0  # 纯关键词确实搜不到

    fused = SearchService(index, semantic).search("travel", page=1, page_size=10)
    assert fused["total"] >= 1
    assert any("旅游" in item["path"] for item in fused["results"])


def test_keyword_search_unchanged_without_semantic(tmp_path: Path) -> None:
    index = _build_index(tmp_path)
    r = SearchService(index).search("容器", page=1, page_size=10)
    assert r["total"] == 1
    assert r["results"][0]["path"] == "docker.md"
