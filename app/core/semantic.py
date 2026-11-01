"""语义检索：本地 embedding（fastembed）+ SQLite 向量表 + 余弦相似度。

设计取舍：
- **可选依赖**：fastembed 未安装 / 模型下载失败 → `ready=False`，搜索自动退回关键词，
  进程不崩（生产镜像可以不带这个依赖）。
- **不引入 numpy**：向量用 `array('f')` 打包成 BLOB，余弦用纯 Python。634 篇 × 512 维
  一次查询约 0.1s，换来零额外二进制依赖。
- **建库时归一化**：存单位向量，查询只需点积；避免每次算模长。
- **与 FTS 同源对齐**：doc_id = 路径 sha1 前 16 位，向量表和 FTS 表用同一个 doc_id 关联。
"""

from __future__ import annotations

import logging
import math
import sqlite3
import threading
import time
from array import array
from collections.abc import Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger("obsidian-agent.semantic")

_VECTORS = "doc_vectors"
_META = "semantic_meta"
BATCH = 32


class SemanticIndex:
    """向量索引：负责向量化、持久化与相似度检索（不依赖 FastAPI）。"""

    def __init__(
        self,
        db_path: Path,
        model_name: str,
        cache_dir: Path,
        max_chars: int = 800,
        weight: float = 1.5,
        top_k: int = 20,
    ) -> None:
        self.db_path = db_path
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.max_chars = max_chars
        self.weight = weight
        self.top_k = top_k
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._emb: Any = None
        self._error: str | None = None
        self._ready = False
        self._building = False
        self._cache: list[tuple[str, array]] | None = None
        self._init_schema()

    # ---------- schema ----------

    def _init_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS {_META} (k TEXT PRIMARY KEY, v TEXT)")
            self._conn.execute(
                f"CREATE TABLE IF NOT EXISTS {_VECTORS} ("
                f"doc_id TEXT PRIMARY KEY, vec BLOB NOT NULL, updated REAL NOT NULL)"
            )
        if self._get_meta("model") != self.model_name:
            # 模型换了 → 旧向量维度/语义空间不一致，整表作废
            with self._lock, self._conn:
                self._conn.execute(f"DELETE FROM {_VECTORS}")
        self._ready = self.count() > 0

    # ---------- 模型 ----------

    def _embedder(self) -> Any:
        if self._emb is None:
            from fastembed import TextEmbedding

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._emb = TextEmbedding(model_name=self.model_name, cache_dir=str(self.cache_dir))
        return self._emb

    def _embed(self, texts: list[str]) -> list[list[float]]:
        """文档向量（bge 系列用 passage 表示）。"""
        model = self._embedder()
        return [list(map(float, v)) for v in model.embed(texts)]

    def _embed_query(self, text: str) -> list[float]:
        """查询向量：优先 query_embed（bge 会加“为这个句子生成表示…”检索指令前缀）。"""
        model = self._embedder()
        fn = getattr(model, "query_embed", None)
        if fn is not None:
            return [float(x) for x in next(iter(fn([text])))]
        return self._embed([text])[0]

    # ---------- 构建 ----------

    def rebuild(self, docs: Iterable[dict[str, str]]) -> dict[str, Any]:
        """全量重建向量表。docs 每项需含 doc_id/title/tags/body。"""
        self._building = True
        started = time.time()
        try:
            items = list(docs)
            texts = [_doc_text(d, self.max_chars) for d in items]
            with self._lock, self._conn:
                self._conn.execute(f"DELETE FROM {_VECTORS}")
            written = 0
            for i in range(0, len(items), BATCH):
                chunk = texts[i : i + BATCH]
                vecs = self._embed(chunk)
                rows = [
                    (items[i + j]["doc_id"], _pack(_normalize(vec)))
                    for j, vec in enumerate(vecs)
                ]
                with self._lock, self._conn:
                    self._conn.executemany(
                        f"INSERT OR REPLACE INTO {_VECTORS} (doc_id, vec, updated) "
                        f"VALUES (?, ?, ?)",
                        [(doc_id, blob, time.time()) for doc_id, blob in rows],
                    )
                written += len(rows)
            self._set_meta("model", self.model_name)
            self._set_meta("built_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
            self._cache = None
            self._ready = True
            self._error = None
            logger.info("语义索引完成 vectors=%s 用时=%.1fs", written, time.time() - started)
            return {"vectors": written, "seconds": round(time.time() - started, 1)}
        except Exception as exc:  # noqa: BLE001 - 依赖/网络失败必须降级而不是崩服务
            self._error = f"{type(exc).__name__}: {exc}"
            logger.warning("语义索引不可用（已降级为关键词检索）: %s", self._error)
            return {"vectors": 0, "error": self._error}
        finally:
            self._building = False

    def upsert_docs(self, docs: Iterable[dict[str, str]]) -> int:
        """增量更新少量文档向量（编辑/新建后调用，单篇约几十毫秒）。"""
        if not self._ready:
            return 0
        items = list(docs)
        if not items:
            return 0
        try:
            vecs = self._embed([_doc_text(d, self.max_chars) for d in items])
        except Exception as exc:  # noqa: BLE001
            logger.warning("增量向量化失败（跳过，等下次全量重建）: %s", exc)
            return 0
        with self._lock, self._conn:
            self._conn.executemany(
                f"INSERT OR REPLACE INTO {_VECTORS} (doc_id, vec, updated) VALUES (?, ?, ?)",
                [
                    (d["doc_id"], _pack(_normalize(v)), time.time())
                    for d, v in zip(items, vecs, strict=True)
                ],
            )
        self._cache = None
        return len(items)

    def remove(self, doc_ids: Iterable[str]) -> None:
        ids = list(doc_ids)
        if not ids:
            return
        with self._lock, self._conn:
            self._conn.executemany(f"DELETE FROM {_VECTORS} WHERE doc_id = ?", [(i,) for i in ids])
        self._cache = None

    # ---------- 检索 ----------

    def search(self, query: str, top_k: int | None = None) -> list[tuple[str, float]]:
        """返回 [(doc_id, cosine)]，降序；未就绪返回空列表。"""
        if not self._ready or self._building or not query.strip():
            return []
        try:
            qvec = _normalize(self._embed_query(query))
        except Exception as exc:  # noqa: BLE001
            logger.warning("查询向量化失败（本次降级）: %s", exc)
            return []
        scored = [(doc_id, _dot(qvec, vec)) for doc_id, vec in self._load_cache()]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: (top_k or self.top_k)]

    def _load_cache(self) -> list[tuple[str, array]]:
        if self._cache is not None:
            return self._cache
        with self._lock:
            rows = self._conn.execute(f"SELECT doc_id, vec FROM {_VECTORS}").fetchall()
        self._cache = [(str(r["doc_id"]), _unpack(r["vec"])) for r in rows]
        return self._cache

    # ---------- 状态 ----------

    def needs_rebuild(self, doc_count: int) -> bool:
        """向量数与索引文档数不一致（或模型换过）才需要全量重建，避免每次启动重跑 20s+。"""
        if self._get_meta("model") != self.model_name:
            return True
        return self.count() != doc_count

    def count(self) -> int:
        with self._lock:
            row = self._conn.execute(f"SELECT count(*) AS n FROM {_VECTORS}").fetchone()
        return int(row["n"] or 0) if row else 0

    def status(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "model": self.model_name,
            "vectors": self.count(),
            "ready": self._ready,
            "building": self._building,
            "lastBuiltAt": self._get_meta("built_at"),
            "error": self._error,
        }

    def _set_meta(self, k: str, v: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT INTO {_META} (k, v) VALUES (?, ?) "
                f"ON CONFLICT(k) DO UPDATE SET v = excluded.v",
                (k, v),
            )

    def _get_meta(self, k: str) -> str | None:
        with self._lock:
            row = self._conn.execute(f"SELECT v FROM {_META} WHERE k = ?", (k,)).fetchone()
        return str(row["v"]) if row else None


def _doc_text(doc: dict[str, str], max_chars: int) -> str:
    """参与向量化的文本：标题 + 标签 + 正文前 N 字（正文过长只取开头，控制耗时）。"""
    head = f"{doc.get('title', '')} {doc.get('tags', '')}".strip()
    body = (doc.get("body") or "")[:max_chars]
    return f"{head}\n{body}".strip() or "(空文档)"


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _dot(a: list[float], b: array) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _pack(vec: list[float]) -> bytes:
    return array("f", vec).tobytes()


def _unpack(blob: bytes) -> array:
    arr = array("f")
    arr.frombytes(blob)
    return arr
