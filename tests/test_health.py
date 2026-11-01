"""应用入口冒烟（M0 用例，M3 改为 create_app 工厂注入临时配置）。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path: Path):
    root = tmp_path / "vault"
    root.mkdir()
    (root / "首页.md").write_bytes("# 首页\n".encode())
    settings = Settings(
        vault_path=root,
        data_dir=tmp_path / "data",
        watch_enabled=False,
        backup_schedule="",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert body["indexBackend"] == "fts5"


def test_version(client: TestClient) -> None:
    r = client.get("/api/version")
    assert r.status_code == 200
    assert "version" in r.json()


def test_static_index_served(client: TestClient) -> None:
    # frontend/dist 被 .gitignore 排除，本地未执行 `cd frontend && npm run build` 时不存在。
    # 该测试仅在 dist 存在时有意义（CI 已强制构建，不会真跳过）；本地开发不构建前端也可跑 pytest。
    dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if not dist.is_dir():
        pytest.skip("frontend/dist 未构建，请先执行 cd frontend && npm run build")
    r = client.get("/")
    assert r.status_code == 200
    assert "Obsidian Agent" in r.text


def test_bad_config_placeholder(tmp_path: Path) -> None:
    """vault 不存在时 create_app 应抛错（占位/拒绝启动），不依赖全局 .env 环境。

    fix(N6)：原实现读模块级 app（依赖运行环境无 .env 的假设），改为显式构造无效 Settings。
    """
    from app.core.vault import VaultError
    from app.main import create_app

    settings = Settings(
        vault_path=tmp_path / "不存在-vault",
        data_dir=tmp_path / "data",
        watch_enabled=False,
        backup_schedule="",
    )
    with pytest.raises(VaultError):
        create_app(settings)
