"""M2：FTS5 + jieba 索引测试（中文命中 / 增量 / 删除 / 特殊字符）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.indexer.fts5 import Fts5Index, tokenize_query
from app.core.indexer.service import IndexService
from app.core.vault import Vault


@pytest.fixture
def index(tmp_path: Path) -> Fts5Index:
    return Fts5Index(db_path=tmp_path / "index.db")


@pytest.fixture
def svc(tmp_path: Path) -> tuple[Vault, IndexService]:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "检索方案.md").write_bytes("这篇文章介绍中文分词方案对比，Docker 部署实践。".encode())
    (root / "其它.md").write_bytes("与检索无关的日常记录。".encode())
    vault = Vault(root=root)
    backend = Fts5Index(db_path=tmp_path / "index.db")
    return vault, IndexService(vault=vault, backend=backend)


# ---------- 全量构建与中文命中 ----------


def test_build_and_chinese_hit(svc: tuple[Vault, IndexService]) -> None:
    _, svc = svc
    info = svc.full_rebuild()
    assert info["total"] == 2
    assert svc.count("分词") == 1
    assert svc.count("中文") == 1
    rows = svc.search_rows("分词", 10, 0)
    assert rows[0].path == "检索方案.md"


def test_chinese_multiword_and(svc: tuple[Vault, IndexService]) -> None:
    """搜「中文分词」要求文档同时含「中文」和「分词」两个词。"""
    _, svc = svc
    svc.full_rebuild()
    assert svc.count("中文分词") == 1
    assert svc.count("检索方案") == 1


def test_english_case_insensitive(svc: tuple[Vault, IndexService]) -> None:
    _, svc = svc
    svc.full_rebuild()
    assert svc.count("docker") == 1  # 原文 Docker（大写）也应命中
    assert svc.count("DOCKER") == 1


def test_title_searchable(svc: tuple[Vault, IndexService]) -> None:
    _, svc = svc
    svc.full_rebuild()
    assert svc.count("检索方案") == 1


def test_no_match(svc: tuple[Vault, IndexService]) -> None:
    _, svc = svc
    svc.full_rebuild()
    assert svc.count("不存在的词xyz") == 0
    assert svc.search_rows("不存在的词xyz", 10, 0) == []


# ---------- 增量更新 ----------


def test_incremental_upsert(svc: tuple[Vault, IndexService]) -> None:
    vault, svc = svc
    svc.full_rebuild()
    (vault.root / "检索方案.md").write_bytes("新增了向量检索技术讨论。".encode())
    svc.update_paths({"检索方案.md"})
    assert svc.count("向量检索") == 1
    assert svc.count("分词") == 0  # 旧内容已被替换


def test_incremental_remove(svc: tuple[Vault, IndexService]) -> None:
    vault, svc = svc
    svc.full_rebuild()
    (vault.root / "其它.md").unlink()
    svc.update_paths({"其它.md"})
    assert svc.count("日常记录") == 0
    assert svc.backend.total_docs() == 1


def test_rebuild_is_idempotent(svc: tuple[Vault, IndexService]) -> None:
    _, svc = svc
    svc.full_rebuild()
    svc.full_rebuild()
    assert svc.backend.total_docs() == 2


# ---------- 特殊字符与分词语义 ----------


def test_query_with_special_chars_no_error(index: Fts5Index, tmp_path: Path) -> None:
    """含 - 的查询不应被 FTS5 当作 NOT 运算符。"""
    root = tmp_path / "vault"
    root.mkdir()
    (root / "a.md").write_bytes("docker-compose 配置详解".encode())
    vault = Vault(root=root)
    svc = IndexService(vault=vault, backend=index)
    svc.full_rebuild()
    assert svc.count("docker-compose") == 1
    assert svc.count("docker -compose") >= 0  # 不抛异常


def test_tokenize_query_special_chars() -> None:
    q = tokenize_query("docker-compose")
    assert q == "docker compose"  # 纯标点 '-' 被过滤，保留 AND 语义


def test_status(svc: tuple[Vault, IndexService]) -> None:
    _, svc = svc
    svc.full_rebuild()
    status = svc.status()
    assert status["state"] == "ready"
    assert status["totalFiles"] == 2
    assert status["backend"] == "fts5"
    assert status["lastFullAt"]


# ---------- 并发安全（坑：单连接跨线程 segfault，GitHub Actions 实测）----------


def test_concurrent_build_and_query(index: Fts5Index) -> None:
    """三线程并发：全量重建 + 查询 + 增量写。锁缺失时 Linux 上会 segfault。"""
    import threading

    docs_seed = [
        ("a.md", "中文分词方案"),
        ("b.md", "Docker 部署实践"),
        ("c.md", "检索性能对比"),
    ]

    def make_docs() -> list:
        # 模拟 IndexService 行为：body 入库前需 jieba 预分词（Fts5Index 假定已分词）
        from app.core.indexer.base import IndexDoc
        from app.core.indexer.fts5 import tokenize

        return [
            IndexDoc(path=p, title=t, body=tokenize(t), tags="", body_original=t, mtime_ns=0)
            for p, t in docs_seed
        ]

    errors: list[BaseException] = []
    stop = threading.Event()

    def worker_build() -> None:
        try:
            while not stop.is_set():
                index.build(make_docs(), batch_size=1)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    def worker_query() -> None:
        try:
            while not stop.is_set():
                index.total_docs()
                index.search_rows("中文", 10, 0)
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    def worker_upsert() -> None:
        from app.core.indexer.base import IndexDoc

        try:
            i = 0
            while not stop.is_set():
                i += 1
                index.upsert(
                    IndexDoc(
                        path="live.md",
                        title=f"更新{i}",
                        body=f"内容{i}",
                        tags="",
                        body_original=f"内容{i}",
                        mtime_ns=i,
                    )
                )
        except BaseException as e:  # noqa: BLE001
            errors.append(e)

    ts = [
        threading.Thread(target=worker_build),
        threading.Thread(target=worker_query),
        threading.Thread(target=worker_upsert),
    ]
    for t in ts:
        t.start()
    import time

    time.sleep(1.5)  # 并发窗口
    stop.set()
    for t in ts:
        t.join(timeout=10)

    assert not errors, f"并发操作异常: {errors}"
    # 锁未死锁、操作全部正常；结束后重建确认可用
    index.build(make_docs(), batch_size=1)
    assert index.count("中文") >= 1
