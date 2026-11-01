"""索引服务编排：全量重建（进度上报）/ 增量更新 / watcher 联动 / 状态查询。

对应 docs/02 §3.1 索引构建数据流：
启动 → 扫描（忽略规则过滤）→ 解析（markdown.py）→ 分批写入（断点续传/进度）
文件变更 → debounce → update_paths 增量
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from app.core.indexer.base import IndexBackend, IndexDoc, IndexRow
from app.core.markdown import parse as parse_markdown
from app.core.markdown import strip_comment
from app.core.search_text import doc_id_for_path, pinyin_index_text
from app.core.semantic import SemanticIndex
from app.core.textcodec import safe_decode
from app.core.vault import Vault, VaultWatcher

logger = logging.getLogger("obsidian-agent.indexer.service")

ProgressCallback = Callable[[int, int], None]  # (done, total)


class IndexService:
    def __init__(self, vault: Vault, backend: IndexBackend) -> None:
        self.vault = vault
        self.backend = backend
        self.watcher: VaultWatcher | None = None
        self.semantic: SemanticIndex | None = None  # runtime 注入；None = 未启用语义检索
        self._building = False

    @property
    def building(self) -> bool:
        """索引是否正在构建（供 API 层只读检查，避免直接访问私有字段）。"""
        return self._building

    # ---------- 文档转换 ----------

    def _to_index_doc(self, rel: str, abs_path: Path) -> IndexDoc | None:
        try:
            raw = abs_path.read_bytes()
        except OSError:
            return None
        text = _safe_decode(raw)
        if text is None:
            return None
        doc = parse_markdown(text, path=rel)
        body = strip_comment(doc.body)
        return IndexDoc(
            path=rel,
            title=doc.title,
            body=_tokenize_fields(doc.title, *doc.aliases, body),
            tags=",".join(doc.tags),  # 原文逗号连接：unicode61 可切分检索，且可还原展示
            body_original=body,
            mtime_ns=abs_path.stat().st_mtime_ns,
            doc_id=doc_id_for_path(rel),
            pinyin=pinyin_index_text(doc.title, *doc.aliases, ",".join(doc.tags)),
        )

    # ---------- 全量 / 增量 ----------

    def full_rebuild(self, progress: ProgressCallback | None = None) -> dict[str, Any]:
        """全量重建（幂等）。progress 回调 (done, total)，total 先扫描统计。"""
        if self._building:
            raise RuntimeError("索引正在构建中")
        self._building = True
        try:
            files = self.vault.walk_md()
            total = len(files)
            done = 0

            def gen() -> Iterator[IndexDoc]:
                nonlocal done
                for rel, abs_path in files:
                    doc = self._to_index_doc(rel, abs_path)
                    done += 1
                    if progress:
                        progress(done, total)
                    if doc:
                        yield doc

            count = self.backend.build(gen(), batch_size=200)
            return {"state": "ready", "total": count, "indexed": done}
        finally:
            self._building = False

    def update_paths(self, paths: set[str]) -> dict[str, Any]:
        """增量更新（watchdog 回调）：存在则 upsert，不存在则 remove。"""
        upserted = 0
        removed = 0
        changed_docs: list[IndexDoc] = []
        removed_ids: list[str] = []
        for rel in sorted(paths):
            abs_path = self.vault.root / rel
            if abs_path.is_file() and abs_path.suffix.lower() == ".md":
                doc = self._to_index_doc(rel, abs_path)
                if doc:
                    self.backend.upsert(doc)
                    changed_docs.append(doc)
                    upserted += 1
            else:
                self.backend.remove(rel)
                removed_ids.append(doc_id_for_path(rel))
                removed += 1
        if upserted or removed:
            logger.info("增量索引 upsert=%s remove=%s", upserted, removed)
        if self.semantic is not None:
            # 编辑/新建后同步更新向量（单篇几十毫秒）；未就绪时静默跳过
            self.semantic.upsert_docs(
                [
                    {
                        "doc_id": d.doc_id,
                        "title": d.title,
                        "tags": d.tags.replace(",", " "),
                        "body": d.body_original,
                    }
                    for d in changed_docs
                ]
            )
            self.semantic.remove(removed_ids)
        return {"upserted": upserted, "removed": removed}

    # ---------- watcher / 状态 ----------

    def start_watcher(self, debounce_seconds: float, polling: bool = False) -> None:
        if self.watcher is not None:
            return
        self.watcher = VaultWatcher(
            vault=self.vault,
            debounce_seconds=debounce_seconds,
            on_change=self.update_paths,
            polling=polling,
        )
        self.watcher.start()
        logger.info("vault 监听已启动（debounce=%ss）", debounce_seconds)

    def stop_watcher(self) -> None:
        if self.watcher:
            self.watcher.stop()
            self.watcher = None

    def status(self) -> dict[str, Any]:
        return {
            "state": "building" if self._building else "ready",
            "totalFiles": self.backend.total_docs(),
            "vaultFiles": len(self.vault.walk_all()),
            "lastFullAt": self.backend.last_full_at(),
            "backend": self.backend.name,
        }

    def search_rows(
        self, query: str, limit: int, offset: int, mode: str = "and"
    ) -> list[IndexRow]:
        return self.backend.search_rows(query, limit, offset, mode)

    def count(self, query: str, mode: str = "and") -> int:
        return self.backend.count(query, mode)

    def fuzzy_rows(self, query: str, limit: int, offset: int) -> list[IndexRow]:
        backend = self.backend
        fuzzy = getattr(backend, "fuzzy_rows", None)
        if fuzzy is None:
            return []
        return fuzzy(query, limit, offset)

    def list_tags(self) -> list[dict[str, Any]]:
        backend = self.backend
        list_tags = getattr(backend, "list_tags", None)
        if list_tags is None:
            return []
        return list_tags()

    def get_by_doc_id(self, doc_id: str) -> IndexRow | None:
        backend = self.backend
        getter = getattr(backend, "get_by_doc_id", None)
        if getter is None:
            return None
        return getter(doc_id)

    def iter_docs(self) -> list[dict[str, str]]:
        """全部文档快照（语义向量重建用；后端不支持时返回空）。"""
        backend = self.backend
        lister = getattr(backend, "iter_docs", None)
        if lister is None:
            return []
        return lister()


def _safe_decode(data: bytes) -> str | None:
    """S5：解码降级统一到 textcodec.safe_decode（与 vault 共用）。"""
    r = safe_decode(data)
    return r[0] if r else None


def _tokenize_fields(*fields: str) -> str:
    from app.core.indexer.fts5 import tokenize

    return " ".join(tokenize(f) for f in fields if f)
