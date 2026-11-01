"""索引后端抽象接口（可插拔：fts5 默认 / meili 可选，见 docs/02 §6 扩展点）。"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


@dataclass
class IndexDoc:
    """一条索引文档。body/tags 为**预分词**后的文本（token 间空格），body_original 保留原文。"""

    path: str
    title: str
    body: str
    tags: str = ""
    body_original: str = ""
    mtime_ns: int = 0
    doc_id: str = ""
    pinyin: str = ""


@dataclass
class IndexRow:
    path: str
    title: str
    body_original: str
    tags: str
    mtime_ns: int
    doc_id: str = ""
    score: float | None = None


class IndexBackend(Protocol):
    """索引后端协议。实现：app.core.indexer.fts5.Fts5Index / meili.MeiliIndex"""

    name: str

    def build(self, docs: Iterable[IndexDoc], batch_size: int = 200) -> int: ...

    def upsert(self, doc: IndexDoc) -> None: ...

    def remove(self, path: str) -> None: ...

    def search_rows(
        self, query: str, limit: int, offset: int, mode: str = "and"
    ) -> list[IndexRow]: ...

    def count(self, query: str, mode: str = "and") -> int: ...

    def total_docs(self) -> int: ...

    def last_full_at(self) -> str | None: ...

    def close(self) -> None: ...
