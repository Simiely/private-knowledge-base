"""检索服务：查询编排 → 原文高亮片段 + 命中偏移（供前端跳转定位）。"""

from __future__ import annotations

from typing import Any

from app.core.indexer.base import IndexRow
from app.core.indexer.service import IndexService
from app.core.semantic import SemanticIndex

# RRF（倒数排名融合）常数：60 是信息检索里的常用经验值，压平头部差距
RRF_K = 60


class SearchService:
    """包装 IndexService，负责结果展示层：分页、高亮片段、原文定位。

    semantic 非空且向量就绪时，关键词结果与向量结果用 RRF 融合；
    融合只影响前若干条排序与召回，分页仍按融合后的顺序切片。
    """

    def __init__(self, index: IndexService, semantic: SemanticIndex | None = None) -> None:
        self.index = index
        self.semantic = semantic

    def search(
        self, q: str, page: int = 1, page_size: int = 20, mode: str = "or"
    ) -> dict[str, Any]:
        if not q or not q.strip():
            return {"total": 0, "page": page, "pageSize": page_size, "results": []}
        offset = max((page - 1) * page_size, 0)
        sem_hits = self.semantic.search(q) if self.semantic else []
        if sem_hits:
            rows, total = self._fused(q, sem_hits, page, page_size, mode)
            rows = rows[offset : offset + page_size]
        else:
            total = self.index.count(q, mode)
            rows = self.index.search_rows(q, page_size, offset, mode)
            # 精确/OR 检索都没命中时，用编辑距离回落，覆盖拼写错误与近似描述。
            if not rows and mode != "and":
                fuzzy_all = self.index.fuzzy_rows(q, limit=max(page_size, 1000), offset=0)
                total = len(fuzzy_all)
                rows = fuzzy_all[offset : offset + page_size]
        results = []
        for row in rows:
            snippet_text, offset_chars, hit_words = _make_snippet(row.body_original, q)
            results.append(
                {
                    "doc_id": row.doc_id,
                    "path": row.path,
                    "title": row.title,
                    "score": row.score,
                    "snippets": (
                        [
                            {
                                "text": snippet_text,
                                "offset": offset_chars,
                                "length": len(snippet_text),
                                "hitWords": hit_words,  # 片段内实际命中的查询词（前端高亮用）
                            }
                        ]
                        if snippet_text
                        else []
                    ),
                    "tags": _split_tags(row.tags),
                }
            )
        return {"total": total, "page": page, "pageSize": page_size, "results": results}

    def _fused(
        self,
        q: str,
        sem_hits: list[tuple[str, float]],
        page: int,
        page_size: int,
        mode: str,
    ) -> tuple[list[IndexRow], int]:
        """关键词 + 向量 RRF 融合；返回 (融合后的行, 结果总数)。"""
        assert self.semantic is not None
        kw_limit = max(page_size * page, 50)
        kw_rows = self.index.search_rows(q, kw_limit, 0, mode)
        kw_rank = {row.doc_id: i for i, row in enumerate(kw_rows)}
        sem_rank = {doc_id: i for i, (doc_id, _) in enumerate(sem_hits)}
        scores: dict[str, float] = {}
        for doc_id, rank in kw_rank.items():
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (RRF_K + rank)
        for doc_id, rank in sem_rank.items():
            scores[doc_id] = scores.get(doc_id, 0.0) + self.semantic.weight / (RRF_K + rank)
        ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        rows: list[IndexRow] = []
        row_by_id = {row.doc_id: row for row in kw_rows}
        for doc_id, score in ordered:
            row = row_by_id.get(doc_id)
            if row is None:
                row = self.index.get_by_doc_id(doc_id)  # 只有向量命中的文档
            if row is None:
                continue  # 向量表里残留已删除文档
            rows.append(
                IndexRow(
                    doc_id=row.doc_id,
                    path=row.path,
                    title=row.title,
                    body_original=row.body_original,
                    tags=row.tags,
                    mtime_ns=row.mtime_ns,
                    score=score,
                )
            )
        # 总数：关键词命中数 + 纯语义新增（关键词结果被截断时略有低估，可接受）
        kw_total = self.index.count(q, mode)
        sem_only = sum(1 for doc_id in sem_rank if doc_id not in kw_rank)
        return rows, kw_total + sem_only

    def list_tags(self) -> list[dict[str, Any]]:
        return self.index.list_tags()

    def get_by_doc_id(self, doc_id: str) -> dict[str, Any] | None:
        row = self.index.get_by_doc_id(doc_id)
        if row is None:
            return None
        return {
            "doc_id": row.doc_id,
            "path": row.path,
            "title": row.title,
            "tags": _split_tags(row.tags),
        }


def _split_tags(tags: str) -> list[str]:
    return [t for t in tags.replace(" ", "").split(",") if t] if tags else []


def _query_words(query: str) -> list[str]:
    """查询词候选：整串优先，再补 jieba 分词词，去重保序。"""
    from app.core.indexer.fts5 import tokenize_query

    words: list[str] = []
    raw = query.strip()
    if raw:
        words.append(raw)
    for w in tokenize_query(query).split(" "):
        w = w.strip().strip('"')
        if w and w not in words:
            words.append(w)
    return words


def _find_ci(haystack: str, needle: str) -> int:
    """大小写不敏感查找，返回在原串中的字节/字符位置（找不到返回 -1）。

    FTS5 unicode61 分词默认对 ASCII 大小写不敏感，检索层必须保持一致：
    否则搜「obsidian」时原文「Obsidian」无法定位、无法高亮（坑：find 区分大小写）。
    """
    return haystack.lower().find(needle.lower())


def _make_snippet(original: str, query: str, context: int = 40) -> tuple[str, int, list[str]]:
    """在原文中定位首个命中词，返回 (高亮片段, 字符偏移, 片段内命中词列表)。

    优先整串查找（用户输入的连续串，英文大小写不敏感），失败则回退到首个分词词；
    hit_words 供前端渲染 <mark> 高亮，只含片段内实际出现的词（英文大小写不敏感匹配）。
    """
    if not original:
        return "", 0, []
    pos = _find_ci(original, query)
    if pos < 0:
        first = next((w for w in _query_words(query)[1:]), None)
        if first:
            pos = _find_ci(original, first)
    if pos < 0:
        pos = 0
    # 命中词长度：整串命中用整串长度，回退分词时用分词长度
    hit_len = len(query) if _find_ci(original, query) >= 0 else len(first or query)
    start = max(pos - context, 0)
    end = min(pos + hit_len + context * 2, len(original))
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(original) else ""
    text = prefix + original[start:end] + suffix
    lowered = text.lower()
    hit_words = [w for w in _query_words(query) if w.lower() in lowered]
    return text, start, hit_words
