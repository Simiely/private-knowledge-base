"""SQLite FTS5 + jieba 预分词实现（默认索引后端，零外部依赖）。

中文策略（docs/09 §2.3）：
- 入库前用 jieba 分词，token 以空格连接，供 FTS5 unicode61 切词
- 检索 query 走同一分词管线；含 FTS5 特殊字符（- + 等）的词加引号防注入
- body_original 列存原文（UNINDEXED），供 search 层做原文高亮/定位
- 断点续传：meta 表记录 last_full_at / total
"""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import jieba
from rapidfuzz import fuzz

from app.core.indexer.base import IndexDoc, IndexRow
from app.core.search_text import expand_synonyms, pinyin_variants

logger = logging.getLogger("obsidian-agent.indexer.fts5")

_TABLE = "docs_fts"
_META = "meta"

# 该字符集外的 token 视为含特殊字符，查询时加引号
_SAFE_TOKEN_RE = re.compile(r"^[\w\u4e00-\u9fff]+$", re.UNICODE)


def _meaningful(word: str) -> bool:
    """是否含有效字符（字母/数字/中文）——过滤纯标点 token（如 '-'）。"""
    return any(c.isalnum() or "\u4e00" <= c <= "\u9fff" for c in word)


def tokenize(text: str) -> str:
    """jieba 分词 → 空格连接的预分词串（过滤纯标点）。"""
    return " ".join(w for w in jieba.lcut(text, cut_all=False) if _meaningful(w))


def tokenize_query(text: str) -> str:
    """查询分词：安全词不加引号（保持 AND 语义），特殊字符词加引号防语法注入。"""
    parts: list[str] = []
    for word in jieba.lcut(text, cut_all=False):
        word = word.strip()
        if not word or not _meaningful(word):
            continue
        if _SAFE_TOKEN_RE.match(word):
            parts.append(word)
        else:
            parts.append('"' + word.replace('"', '""') + '"')
    return " ".join(parts)


def build_match_query(text: str, mode: str = "and", expand: bool = True) -> str:
    """构建 FTS5 MATCH 查询。

    - mode=and：保持原有精确语义；
    - mode=or：原词任一命中即可；
    - expand=True 时追加同义词与拼音变体（仅在原词无结果时启用，
      避免 `you*` 这类拼音前缀把“旅游”排到“邮箱”笔记前面）。
    """
    base = tokenize_query(text)
    if not base:
        return ""
    if mode == "and":
        return base

    tokens = base.split(" ")
    if not expand:
        return " OR ".join(token for token in tokens if token.strip())

    expanded: list[str] = list(tokens)
    for token in tokens:
        raw = token.strip('"')
        for syn in expand_synonyms(raw):
            expanded.append(syn)
    for variant in pinyin_variants(text):
        parts = [part for part in variant.split(" ") if part.strip()]
        expanded.extend(parts)
        # 连写拼音需要前缀匹配（bushu 命中 bushu...），单音节也可前缀匹配。
        expanded.extend(f"{part}*" for part in parts if not part.endswith("*"))

    seen: set[str] = set()
    unique: list[str] = []
    for token in expanded:
        token = token.strip()
        if not token or token in seen:
            continue
        seen.add(token)
        unique.append(token)
    return " OR ".join(unique)


class Fts5Index:
    name = "fts5"

    def __init__(self, db_path: Path, userdict: str | None = None) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)  # data_dir 可能未创建
        if userdict and Path(userdict).is_file():
            jieba.load_userdict(str(Path(userdict).expanduser()))
            logger.info("已加载 jieba 自定义词典: %s", userdict)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # 单连接跨线程共享（check_same_thread=False 仅关闭检查，不代表线程安全）：
        # 后台索引线程 / API 请求线程 / 状态轮询并发访问同一连接会导致
        # SQLite 内部状态错乱 → Linux 上 segfault（GitHub Actions 实测崩溃）。
        # 用 RLock 串行化全部连接操作。
        self._lock = threading.RLock()
        self._init_schema()

    # ---------- schema ----------

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS {_META} (k TEXT PRIMARY KEY, v TEXT)")
            exists = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (_TABLE,)
            ).fetchone()
            if exists:
                cols = {
                    str(row[1])
                    for row in self._conn.execute(f"PRAGMA table_info({_TABLE})").fetchall()
                }
                # 旧库没有 doc_id/pinyin 列：直接重建索引表，启动时全量重索引。
                if {"doc_id", "pinyin"} - cols:
                    self._conn.execute(f"DROP TABLE {_TABLE}")
                    exists = None
            if not exists:
                self._conn.execute(
                    f"""CREATE VIRTUAL TABLE {_TABLE} USING fts5(
                        doc_id UNINDEXED,
                        path UNINDEXED,
                        title,
                        body,
                        pinyin,
                        tags,
                        body_original UNINDEXED,
                        mtime_ns UNINDEXED,
                        tokenize='unicode61'
                    )"""
                )

    # ---------- 写入 ----------

    def build(self, docs: Iterable[IndexDoc], batch_size: int = 200) -> int:
        """全量重建（先清空再分批写入）。返回索引文档数。"""
        with self._lock:
            with self._conn:
                self._conn.execute(f"DELETE FROM {_TABLE}")
            count = 0
            batch: list[tuple[Any, ...]] = []
            for doc in docs:
                batch.append(self._row_tuple(doc))
                count += 1
                if len(batch) >= batch_size:
                    self._insert_batch(batch)
                    batch.clear()
            if batch:
                self._insert_batch(batch)
            self._set_meta("total", str(count))
            self._set_meta("last_full_at", datetime.now().isoformat(timespec="seconds"))
            logger.info("索引重建完成 total=%s", count)
            return count

    def upsert(self, doc: IndexDoc) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(f"DELETE FROM {_TABLE} WHERE path = ?", (doc.path,))
                self._conn.execute(
                    f"INSERT INTO {_TABLE} "
                    f"(doc_id, path, title, body, pinyin, tags, body_original, mtime_ns) "
                    f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    self._row_tuple(doc),
                )

    def remove(self, path: str) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(f"DELETE FROM {_TABLE} WHERE path = ?", (path,))

    def _insert_batch(self, rows: list[tuple[Any, ...]]) -> None:
        with self._conn:
            self._conn.executemany(
                f"INSERT INTO {_TABLE} "
                f"(doc_id, path, title, body, pinyin, tags, body_original, mtime_ns) "
                f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )

    def _row_tuple(self, doc: IndexDoc) -> tuple[Any, ...]:
        return (
            doc.doc_id,
            doc.path,
            doc.title,
            doc.body,
            doc.pinyin,
            doc.tags,
            doc.body_original,
            doc.mtime_ns,
        )

    # ---------- 查询 ----------

    def _count_raw(self, q: str) -> int:
        with self._lock:
            row = self._conn.execute(
                f"SELECT count(*) AS n FROM {_TABLE} WHERE {_TABLE} MATCH ?", (q,)
            ).fetchone()
        return int(row["n"]) if row else 0

    def _effective_query(self, query: str, mode: str) -> str:
        """原词优先；原词无结果时才启用同义词/拼音扩展。"""
        base = build_match_query(query, mode, expand=False)
        if not base or mode == "and":
            return base
        if self._count_raw(base) > 0:
            return base
        return build_match_query(query, mode, expand=True)

    def search_rows(
        self, query: str, limit: int, offset: int, mode: str = "and"
    ) -> list[IndexRow]:
        q = self._effective_query(query, mode)
        if not q:
            return []
        sql = (
            f"SELECT doc_id, path, title, body_original, tags, mtime_ns, rank FROM {_TABLE} "
            f"WHERE {_TABLE} MATCH ? ORDER BY rank LIMIT ? OFFSET ?"
        )
        with self._lock:
            rows = self._conn.execute(sql, (q, limit, offset)).fetchall()
        return [
            IndexRow(
                doc_id=str(r["doc_id"]),
                path=str(r["path"]),
                title=str(r["title"]),
                body_original=str(r["body_original"]),
                tags=str(r["tags"]),
                mtime_ns=int(r["mtime_ns"]),
                score=-float(r["rank"]),
            )
            for r in rows
        ]

    def count(self, query: str, mode: str = "and") -> int:
        q = self._effective_query(query, mode)
        if not q:
            return 0
        return self._count_raw(q)

    def fuzzy_rows(self, query: str, limit: int, offset: int) -> list[IndexRow]:
        """FTS5 无结果时的容错回退：对标题/标签/正文做相似度匹配。

        只用于小库（本项目单库数百篇），避免引入独立模糊搜索引擎。
        """
        q = query.strip()
        if not q:
            return []
        with self._lock:
            rows = self._conn.execute(
                f"SELECT doc_id, path, title, body_original, tags, mtime_ns FROM {_TABLE}"
            ).fetchall()
        scored: list[IndexRow] = []
        for r in rows:
            hay_title = str(r["title"] or "")
            hay_tags = str(r["tags"] or "")
            hay_body = str(r["body_original"] or "")[:5000]
            score = max(
                fuzz.partial_ratio(q, hay_title),
                fuzz.partial_ratio(q, hay_tags),
                fuzz.partial_ratio(q, hay_body),
            )
            if score < 60:
                continue
            scored.append(
                IndexRow(
                    doc_id=str(r["doc_id"]),
                    path=str(r["path"]),
                    title=hay_title,
                    body_original=str(r["body_original"]),
                    tags=hay_tags,
                    mtime_ns=int(r["mtime_ns"]),
                    score=float(score),
                )
            )
        scored.sort(key=lambda row: row.score or 0, reverse=True)
        return scored[offset : offset + limit]

    def list_tags(self) -> list[dict[str, Any]]:
        """统计索引中的标签（按出现文档数降序）。"""
        with self._lock:
            rows = self._conn.execute(f"SELECT tags FROM {_TABLE}").fetchall()
        counts: dict[str, int] = {}
        for row in rows:
            raw = str(row["tags"] or "")
            for tag in {t for t in raw.replace(" ", "").split(",") if t}:
                counts[tag] = counts.get(tag, 0) + 1
        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def get_by_doc_id(self, doc_id: str) -> IndexRow | None:
        with self._lock:
            r = self._conn.execute(
                f"SELECT doc_id, path, title, body_original, tags, mtime_ns "
                f"FROM {_TABLE} WHERE doc_id = ? LIMIT 1",
                (doc_id,),
            ).fetchone()
        if r is None:
            return None
        return IndexRow(
            doc_id=str(r["doc_id"]),
            path=str(r["path"]),
            title=str(r["title"]),
            body_original=str(r["body_original"]),
            tags=str(r["tags"]),
            mtime_ns=int(r["mtime_ns"]),
            score=None,
        )

    def total_docs(self) -> int:
        # FTS5 空表时 count(*) 返回 NULL（已知怪癖），必须容错
        with self._lock:
            row = self._conn.execute(f"SELECT count(*) AS n FROM {_TABLE}").fetchone()
        return int(row["n"] or 0) if row else 0

    def iter_docs(self) -> list[dict[str, str]]:
        """导出全部文档的检索所需字段（语义向量构建用）。"""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT doc_id, path, title, tags, body_original FROM {_TABLE}"
            ).fetchall()
        return [
            {
                "doc_id": str(r["doc_id"]),
                "path": str(r["path"]),
                "title": str(r["title"]),
                "tags": str(r["tags"]),
                "body": str(r["body_original"]),
            }
            for r in rows
        ]

    def last_full_at(self) -> str | None:
        return self._get_meta("last_full_at")

    def _set_meta(self, k: str, v: str) -> None:
        with self._lock:
            with self._conn:
                self._conn.execute(
                    f"INSERT INTO {_META} (k, v) VALUES (?, ?) "
                    f"ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                    (k, v),
                )

    def _get_meta(self, k: str) -> str | None:
        with self._lock:
            row = self._conn.execute(f"SELECT v FROM {_META} WHERE k = ?", (k,)).fetchone()
        return str(row["v"]) if row else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()

