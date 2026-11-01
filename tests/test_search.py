"""M2：检索服务测试（分页 / 高亮片段 / 原文定位 / tags）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.indexer.fts5 import Fts5Index
from app.core.indexer.service import IndexService
from app.core.search import SearchService
from app.core.vault import Vault


@pytest.fixture
def search(tmp_path: Path) -> SearchService:
    root = tmp_path / "vault"
    root.mkdir()
    for i in range(30):
        (root / f"笔记{i}.md").write_bytes(
            f"这是第 {i} 篇关于中文分词方案的笔记，内容包含 docker 实践。".encode()
        )
    vault = Vault(root=root)
    backend = Fts5Index(db_path=tmp_path / "index.db")
    svc = IndexService(vault=vault, backend=backend)
    svc.full_rebuild()
    return SearchService(svc)


def test_pagination(search: SearchService) -> None:
    r1 = search.search("分词", page=1, page_size=10)
    assert r1["total"] == 30
    assert len(r1["results"]) == 10
    r2 = search.search("分词", page=3, page_size=10)
    assert len(r2["results"]) == 10
    assert r2["results"][0]["path"] != r1["results"][0]["path"]


def test_empty_query(search: SearchService) -> None:
    r = search.search("   ")
    assert r["total"] == 0
    assert r["results"] == []


def test_snippet_contains_query_and_offset(search: SearchService) -> None:
    r = search.search("中文分词", page=1, page_size=5)
    assert r["total"] == 30
    hit = r["results"][0]
    assert "中文分词" in hit["snippets"][0]["text"]
    assert hit["snippets"][0]["offset"] >= 0


def test_result_shape(search: SearchService) -> None:
    r = search.search("docker", page=1, page_size=3)
    hit = r["results"][0]
    assert set(hit.keys()) == {"doc_id", "path", "title", "score", "snippets", "tags"}
    assert hit["path"].endswith(".md")
    assert hit["doc_id"]
    assert hit["score"] is not None


def test_tags_splitting(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "带标签.md").write_bytes("---\ntags:\n  - docker\n  - obsidian\n---\n内容".encode())
    vault = Vault(root=root)
    backend = Fts5Index(db_path=tmp_path / "index.db")
    svc = IndexService(vault=vault, backend=backend)
    svc.full_rebuild()
    search_svc = SearchService(svc)
    r = search_svc.search("内容")
    assert r["results"][0]["tags"] == ["docker", "obsidian"]


def test_or_mode_matches_any_term(tmp_path: Path) -> None:
    """自然语言多词查询应“任一命中”，而不是 FTS5 默认全词 AND。"""
    root = tmp_path / "vault"
    root.mkdir()
    (root / "只含中文.md").write_bytes("中文资料".encode())
    (root / "只含docker.md").write_bytes("docker 实践".encode())
    vault = Vault(root=root)
    backend = Fts5Index(db_path=tmp_path / "index.db")
    svc = IndexService(vault=vault, backend=backend)
    svc.full_rebuild()
    r = SearchService(svc).search("中文 docker", page=1, page_size=10)
    assert r["total"] == 2


def test_pinyin_search(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "部署方案.md").write_bytes("本机模型部署步骤".encode())
    vault = Vault(root=root)
    backend = Fts5Index(db_path=tmp_path / "index.db")
    svc = IndexService(vault=vault, backend=backend)
    svc.full_rebuild()
    r = SearchService(svc).search("bushu", page=1, page_size=10)
    assert r["total"] >= 1
    assert "部署" in r["results"][0]["title"]


def test_typo_fuzzy_fallback(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "docker笔记.md").write_bytes("docker 容器实践".encode())
    vault = Vault(root=root)
    backend = Fts5Index(db_path=tmp_path / "index.db")
    svc = IndexService(vault=vault, backend=backend)
    svc.full_rebuild()
    r = SearchService(svc).search("docer", page=1, page_size=10)
    assert r["total"] >= 1
    assert any("docker" in item["path"] for item in r["results"])
