"""MCP 只读服务：把知识库的搜索/读取能力暴露给本地模型。

设计：
- 不直接打开索引库，统一调用 Web API（`/api/search`、`/api/vault/file`），
  避免 Web 与 MCP 双进程争用 SQLite。
- 默认 Streamable HTTP + Bearer Token；只监听本机，远程用 Tailscale。
- 只读工具：搜索、读取全文、按标题读章节、标签、相关笔记。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from mcp.server.mcpserver import MCPServer

MCP_PATH = "/mcp"
DEFAULT_MAX_CHARS = 20000
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


API_BASE = _env("MCP_API_BASE", "http://127.0.0.1:8080").rstrip("/")
API_TOKEN = _env("AUTH_TOKEN")
MCP_TOKEN = _env("MCP_TOKEN")
HOST = _env("MCP_HOST", "127.0.0.1")
PORT = int(_env("MCP_PORT", "8090") or "8090")

_client: httpx.AsyncClient | None = None


def _api() -> httpx.AsyncClient:
    global _client
    if _client is None:
        headers = {"X-Auth-Token": API_TOKEN} if API_TOKEN else {}
        _client = httpx.AsyncClient(base_url=API_BASE, headers=headers, timeout=30.0)
    return _client


def _error(message: str, status: int | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"error": message}
    if status is not None:
        result["status"] = status
    return result


mcp = MCPServer(
    name="obsidian-knowledge",
    instructions=(
        "这是用户的私人知识库。需要回答问题时：先调用 search_notes 做模糊定位，"
        "拿到 path 或 doc_id 后必须调用 read_note/read_note_by_id 读取全文；"
        "不要只凭搜索片段作答。引用时返回 path 与 title。"
    ),
    version="0.2.0",
)


@mcp.tool()
async def search_notes(query: str, limit: int = 5, mode: str = "or") -> dict[str, Any]:
    """模糊/关键词检索笔记，返回 doc_id、path、title、片段、标签与分数。

    参数：
    - query：自然语言或关键词（支持拼音、错字回退）。
    - limit：返回条数，1~20。
    - mode：or=模糊（默认），and=精确全词。
    """
    limit = max(1, min(limit, 20))
    mode = "and" if mode == "and" else "or"
    r = await _api().get("/api/search", params={"q": query, "pageSize": limit, "mode": mode})
    if r.status_code != 200:
        return _error(f"搜索失败：{r.text}", r.status_code)
    body = r.json()
    results = [
        {
            "doc_id": item.get("doc_id", ""),
            "path": item.get("path", ""),
            "title": item.get("title", ""),
            "score": item.get("score"),
            "tags": item.get("tags", []),
            "snippet": (item.get("snippets") or [{}])[0].get("text", ""),
        }
        for item in body.get("results", [])
    ]
    return {"total": body.get("total", len(results)), "results": results}


@mcp.tool()
async def read_note(
    path: str, offset: int = 0, max_chars: int = DEFAULT_MAX_CHARS
) -> dict[str, Any]:
    """按相对路径读取完整 Markdown；超长时按 offset/max_chars 分块返回。

    回答前必须调用此工具读取原文；不要只依赖 search 的片段。
    """
    r = await _api().get("/api/vault/file", params={"path": path})
    if r.status_code != 200:
        return _error(f"读取失败：{r.text}", r.status_code)
    body = r.json()
    content = str(body.get("content", ""))
    total = len(content)
    offset = max(0, min(offset, total))
    max_chars = max(500, min(max_chars, 100000))
    chunk = content[offset : offset + max_chars]
    return {
        "path": body.get("path", path),
        "title": Path(path).stem,
        "total_chars": total,
        "offset": offset,
        "max_chars": max_chars,
        "truncated": offset + max_chars < total,
        "content": chunk,
    }


@mcp.tool()
async def read_note_by_id(
    doc_id: str, offset: int = 0, max_chars: int = DEFAULT_MAX_CHARS
) -> dict[str, Any]:
    """按 search_notes 返回的 doc_id 读取全文。"""
    meta = await _api().get(f"/api/search/by-id/{doc_id}")
    if meta.status_code != 200:
        return _error(f"未找到 doc_id：{doc_id}", meta.status_code)
    path = str(meta.json().get("path", ""))
    if not path:
        return _error(f"doc_id 无对应路径：{doc_id}")
    return await read_note(path=path, offset=offset, max_chars=max_chars)


@mcp.tool()
async def read_section(
    path: str, heading: str, max_chars: int = DEFAULT_MAX_CHARS
) -> dict[str, Any]:
    """按标题读取某一节（从匹配标题到下一个同级/更高级标题）。"""
    note = await read_note(path=path, max_chars=100000)
    if "error" in note:
        return note
    lines = str(note.get("content", "")).splitlines()
    target = heading.strip().lstrip("#").strip()
    start = -1
    level = 0
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m and m.group(2).strip() == target:
            start, level = i, len(m.group(1))
            break
    if start < 0:
        return _error(f"未找到标题：{heading}")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = HEADING_RE.match(lines[j])
        if m and len(m.group(1)) <= level:
            end = j
            break
    section = "\n".join(lines[start:end])
    return {
        "path": path,
        "heading": target,
        "content": section[: max(500, min(max_chars, 100000))],
        "truncated": len(section) > max_chars,
    }


@mcp.tool()
async def list_tags() -> dict[str, Any]:
    """列出知识库全部标签及文档数。"""
    r = await _api().get("/api/search/tags")
    if r.status_code != 200:
        return _error(f"读取标签失败：{r.text}", r.status_code)
    return {"tags": r.json()}


@mcp.tool()
async def related_notes(path: str, limit: int = 5) -> dict[str, Any]:
    """按当前笔记标题做模糊检索，返回相关笔记（排除自身）。"""
    title = Path(path).stem
    found = await search_notes(query=title, limit=max(limit + 1, 5))
    if "error" in found:
        return found
    results = [item for item in found.get("results", []) if item.get("path") != path]
    return {"query": title, "results": results[: max(1, min(limit, 10))]}


@mcp.tool()
async def get_note_by_path(path: str) -> dict[str, Any]:
    """按路径读取全文（read_note 的别名，便于模型直接使用路径）。"""
    return await read_note(path=path)


class BearerAuthMiddleware:
    """给 MCP HTTP 入口加一个简单 Bearer Token 校验。"""

    def __init__(self, app: Any, token: str) -> None:
        self.app = app
        self.token = token

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        headers = {
            key.decode("latin-1"): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        auth = headers.get("authorization", "")
        token = headers.get("x-mcp-token", "")
        if auth != f"Bearer {self.token}" and token != self.token:
            await send(
                {
                    "type": "http.response.start",
                    "status": 401,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b'{"error":"unauthorized"}',
                }
            )
            return
        await self.app(scope, receive, send)


def main() -> None:
    if not MCP_TOKEN:
        raise RuntimeError("必须设置 MCP_TOKEN，MCP 服务不提供无鉴权模式")
    app = mcp.streamable_http_app(
        streamable_http_path=MCP_PATH,
        host=HOST,
        stateless_http=True,
        json_response=True,
    )
    app.add_middleware(BearerAuthMiddleware, token=MCP_TOKEN)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
