"""MCP 只读工具测试（用 MockTransport 模拟 Web API）。"""

from __future__ import annotations

import httpx
import pytest

from app.mcp import server


def _mock_client() -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/search":
            return httpx.Response(
                200,
                json={
                    "total": 1,
                    "results": [
                        {
                            "doc_id": "abc123",
                            "path": "部署方案.md",
                            "title": "部署方案",
                            "score": 1.2,
                            "tags": ["docker"],
                            "snippets": [{"text": "本机模型部署步骤"}],
                        }
                    ],
                },
            )
        if path == "/api/search/tags":
            return httpx.Response(200, json=[{"tag": "docker", "count": 1}])
        if path == "/api/search/by-id/abc123":
            return httpx.Response(
                200,
                json={"doc_id": "abc123", "path": "部署方案.md", "title": "部署方案"},
            )
        if path == "/api/vault/file":
            return httpx.Response(
                200,
                json={
                    "path": "部署方案.md",
                    "content": "# 部署\n本机模型部署步骤\n## 步骤\ndocker 实践",
                },
            )
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test")


@pytest.fixture
async def mock_api(monkeypatch: pytest.MonkeyPatch):
    client = _mock_client()
    monkeypatch.setattr(server, "_client", client)
    yield
    await client.aclose()


@pytest.mark.asyncio
async def test_search_notes(mock_api: None) -> None:
    result = await server.search_notes("部署", limit=3)
    assert result["total"] == 1
    assert result["results"][0]["doc_id"] == "abc123"
    assert result["results"][0]["snippet"]


@pytest.mark.asyncio
async def test_read_note_and_by_id(mock_api: None) -> None:
    note = await server.read_note("部署方案.md")
    assert "本机模型部署" in note["content"]
    by_id = await server.read_note_by_id("abc123")
    assert by_id["path"] == "部署方案.md"


@pytest.mark.asyncio
async def test_read_section(mock_api: None) -> None:
    section = await server.read_section("部署方案.md", "步骤")
    assert "docker" in section["content"]
    assert "本机模型" not in section["content"]


@pytest.mark.asyncio
async def test_list_tags(mock_api: None) -> None:
    result = await server.list_tags()
    assert result["tags"][0]["tag"] == "docker"
