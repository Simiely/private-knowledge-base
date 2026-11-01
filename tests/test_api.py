"""M3：API 层 e2e 测试（vault / search / index / backup / auth）。"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    root = tmp_path / "vault"
    (root / "sub").mkdir(parents=True)
    (root / "检索方案.md").write_bytes("中文分词方案与 Docker 部署实践。".encode())
    (root / "sub" / "笔记.md").write_bytes("第二篇笔记内容。".encode())
    (root / ".obsidian").mkdir()
    (root / ".obsidian" / "conf.json").write_bytes(b"{}")
    settings = Settings(
        vault_path=root,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        watch_enabled=False,
        backup_schedule="",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        _wait_ready(c)
        yield c


def _wait_ready(client: TestClient, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if client.get("/api/index/status").json().get("state") == "ready":
            return
        time.sleep(0.1)
    raise AssertionError("索引未在超时内就绪")


# ---------- vault ----------


def test_tree(client: TestClient) -> None:
    nodes = client.get("/api/vault/tree").json()
    names = {n["name"] for n in nodes}
    assert "检索方案.md" in names
    assert "sub" in names
    assert ".obsidian" not in names  # 忽略规则生效


def test_read_write_create_delete(client: TestClient) -> None:
    # 读
    r = client.get("/api/vault/file", params={"path": "检索方案.md"})
    assert r.status_code == 200
    assert "中文分词" in r.json()["content"]
    # 写
    r = client.put(
        "/api/vault/file", json={"path": "检索方案.md", "content": "改后内容：向量检索。"}
    )
    assert r.status_code == 200
    assert (
        client.get("/api/vault/file", params={"path": "检索方案.md"}).json()["content"]
        == "改后内容：向量检索。"
    )
    # 新建
    r = client.post("/api/vault/file", json={"path": "新笔记.md", "content": "新建内容"})
    assert r.status_code == 201
    # 已存在 → 409
    assert client.post("/api/vault/file", json={"path": "新笔记.md"}).status_code == 409
    # 删除
    assert client.delete("/api/vault/file", params={"path": "新笔记.md"}).status_code == 200
    assert client.get("/api/vault/file", params={"path": "新笔记.md"}).status_code == 404


def test_write_rejects_escape_and_disallowed(client: TestClient) -> None:
    # 路径越界 → 422
    assert (
        client.put("/api/vault/file", json={"path": "../逃逸.md", "content": "x"}).status_code
        == 422
    )
    # 禁写目录（.obsidian）→ 403
    assert (
        client.put(
            "/api/vault/file", json={"path": ".obsidian/conf.json", "content": "x"}
        ).status_code
        == 403
    )
    # 非 md → 422
    assert client.put("/api/vault/file", json={"path": "a.txt", "content": "x"}).status_code == 422
    # 不存在 → 404
    assert (
        client.put("/api/vault/file", json={"path": "不存在.md", "content": "x"}).status_code == 404
    )


def test_meta(client: TestClient) -> None:
    r = client.get("/api/vault/meta", params={"path": "检索方案.md"})
    assert r.status_code == 200
    assert r.json()["encoding"] in ("utf-8", "utf-8-sig")


# ---------- search ----------


def test_search_hit(client: TestClient) -> None:
    r = client.get("/api/search", params={"q": "中文分词"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    hit = body["results"][0]
    assert hit["path"] == "检索方案.md"
    assert "中文分词" in hit["snippets"][0]["text"]


def test_search_no_match(client: TestClient) -> None:
    r = client.get("/api/search", params={"q": "绝对不存在xyz"})
    assert r.json()["total"] == 0


def test_attachment_download(client: TestClient) -> None:
    root = client.app.state.services.vault.root
    (root / "附件.pdf").write_bytes(b"%PDF-1.4 test")
    r = client.get("/api/vault/attachment", params={"path": "附件.pdf"})
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    assert client.get("/api/vault/attachment", params={"path": "../x.pdf"}).status_code == 422
    (root / "坏文件.exe").write_bytes(b"x")
    assert client.get("/api/vault/attachment", params={"path": "坏文件.exe"}).status_code == 422


def test_export_zip(client: TestClient) -> None:
    import io
    import zipfile

    r = client.get("/api/export")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = set(zf.namelist())
    assert "检索方案.md" in names
    assert "sub/笔记.md" in names


# ---------- index ----------


def test_index_status_and_rebuild(client: TestClient) -> None:
    st = client.get("/api/index/status").json()
    assert st["state"] == "ready"
    assert st["totalFiles"] >= 2
    r = client.post("/api/index/rebuild")
    assert r.status_code == 202


# ---------- backup ----------


def test_backup_flow(client: TestClient) -> None:
    # 立即快照（后台任务）
    r = client.post("/api/backup/now")
    assert r.status_code == 202
    _wait_snapshots(client, 1)
    snaps = client.get("/api/backup/list").json()["snapshots"]
    assert len(snaps) == 1
    snap_id = snaps[0]["id"]
    # 改文件后单文件恢复
    client.put("/api/vault/file", json={"path": "检索方案.md", "content": "被改坏了"})
    r = client.post("/api/backup/restore-file", json={"path": "检索方案.md", "snapshotId": snap_id})
    assert r.status_code == 200
    content = client.get("/api/vault/file", params={"path": "检索方案.md"}).json()["content"]
    assert "中文分词" in content  # 已从快照恢复
    # history
    h = client.get("/api/backup/history", params={"path": "检索方案.md"}).json()
    assert any(v["source"] == "snapshot" for v in h["versions"])
    # 删除快照（异步：202 立即返回，后台线程清理，轮询直到消失）
    r = client.delete(f"/api/backup/{snap_id}")
    assert r.status_code == 202
    assert r.json()["async"] is True
    _wait_snapshots_gone(client, snap_id)


def test_backup_restore_requires_confirm(client: TestClient) -> None:
    client.post("/api/backup/now")
    _wait_snapshots(client, 1)
    snap_id = client.get("/api/backup/list").json()["snapshots"][0]["id"]
    r = client.post("/api/backup/restore", json={"snapshotId": snap_id, "confirmCode": "wrong"})
    assert r.status_code == 400


def _wait_snapshots(client: TestClient, expected: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        snaps = client.get("/api/backup/list").json()["snapshots"]
        if len(snaps) >= expected:
            return
        time.sleep(0.1)
    raise AssertionError("快照未在超时内创建")


def _wait_snapshots_gone(client: TestClient, snap_id: str, timeout: float = 30.0) -> None:
    """等待指定快照从列表消失（异步删除完成）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        snaps = client.get("/api/backup/list").json()["snapshots"]
        if all(s["id"] != snap_id for s in snaps):
            return
        time.sleep(0.2)
    raise AssertionError(f"快照 {snap_id} 未在超时内删除")


# ---------- auth ----------


def test_auth_required_when_token_set(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    root.mkdir()
    (root / "x.md").write_bytes(b"x")
    settings = Settings(
        vault_path=root,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        watch_enabled=False,
        backup_schedule="",
        auth_token="secret123",
        auth_disabled=False,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.get("/api/vault/tree").status_code == 401
        r = c.get("/api/vault/tree", headers={"X-Auth-Token": "secret123"})
        assert r.status_code == 200


def test_auth_rejects_when_token_not_configured(tmp_path: Path) -> None:
    """安全默认：未配置 AUTH_TOKEN 时接口不可访问，避免空 token 裸奔。"""
    root = tmp_path / "vault"
    root.mkdir()
    (root / "x.md").write_bytes(b"x")
    settings = Settings(
        vault_path=root,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        watch_enabled=False,
        backup_schedule="",
        auth_disabled=False,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.get("/api/vault/tree").status_code == 503


def test_login_cookie_flow(tmp_path: Path) -> None:
    """浏览器登录后，Cookie 可访问 API（图片等资源也能自动带凭证）。"""
    root = tmp_path / "vault"
    root.mkdir()
    (root / "x.md").write_bytes(b"x")
    settings = Settings(
        vault_path=root,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        watch_enabled=False,
        backup_schedule="",
        auth_token="secret123",
        auth_disabled=False,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        assert c.post("/api/auth/login", json={"token": "wrong"}).status_code == 401
        assert c.post("/api/auth/login", json={"token": "secret123"}).status_code == 200
        assert c.get("/api/vault/tree").status_code == 200
        assert c.post("/api/auth/logout").status_code == 200
        assert c.get("/api/vault/tree").status_code == 401


# ---------- agent ----------


def test_agent_chat_requires_llm(client: TestClient) -> None:
    """未配置 LLM 时 chat 返回 400 而非 500。"""
    r = client.post("/api/agent/chat", json={"message": "你好"})
    assert r.status_code == 400
    assert "LLM" in r.json()["detail"]


def test_agent_chat_empty_message(client: TestClient) -> None:
    r = client.post("/api/agent/chat", json={"message": "   "})
    assert r.status_code == 422


def test_agent_confirm_unknown_op(client: TestClient) -> None:
    r = client.post("/api/agent/confirm", json={"sessionId": "s1", "opId": "op-999"})
    assert r.status_code == 404


def test_agent_session(client: TestClient) -> None:
    r = client.get("/api/agent/session", params={"sessionId": "new"})
    assert r.status_code == 200
    assert r.json()["messages"] == 0
