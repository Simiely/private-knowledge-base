"""运行时配置接口测试：vault / backupdir 查看与热切换、browse / detect / quickaccess、持久化、并发。

覆盖 S5 计划：settings 全接口 + 热切换 + 持久化 + 并发回归。
"""

from __future__ import annotations

import threading
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


@pytest.fixture
def other_vault(tmp_path: Path) -> Path:
    other = tmp_path / "other-vault"
    other.mkdir()
    (other / "笔记.md").write_bytes("# 笔记\n".encode())
    return other


# ---------- 查看 ----------


def test_get_vault(client: TestClient) -> None:
    r = client.get("/api/settings/vault")
    assert r.status_code == 200
    body = r.json()
    assert body["path"].endswith("vault")
    assert "dataDir" in body


def test_get_backupdir(client: TestClient) -> None:
    r = client.get("/api/settings/backupdir")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert "backups" in body["path"]


# ---------- vault 热切换 ----------


def test_set_vault_switch(client: TestClient, other_vault: Path) -> None:
    r = client.post("/api/settings/vault", json={"path": str(other_vault)})
    assert r.status_code == 200
    assert r.json()["status"] in ("switched", "rebuilding")

    h = client.get("/api/health").json()
    assert h["vault"] == str(other_vault.resolve())
    assert h["indexState"] in ("ready", "building")


def test_set_vault_unchanged(client: TestClient) -> None:
    cur = client.get("/api/settings/vault").json()["path"]
    r = client.post("/api/settings/vault", json={"path": cur})
    assert r.status_code == 200
    assert r.json()["status"] == "unchanged"


def test_set_vault_invalid_path(client: TestClient) -> None:
    r = client.post("/api/settings/vault", json={"path": "C:/不存在/目录/xyz"})
    assert r.status_code == 422


def test_set_vault_backup_inside_vault_rejected(client: TestClient) -> None:
    """备份目录位于新 vault 内 → 拒绝（坑 #11）。"""
    backup_root = client.app.state.services.backup.backup_root
    r = client.post("/api/settings/vault", json={"path": str(backup_root)})
    assert r.status_code == 422


# ---------- 备份目录热切换 ----------


def test_set_backupdir_switch(client: TestClient, tmp_path: Path) -> None:
    new_dir = tmp_path / "new-backups"
    new_dir.mkdir()
    r = client.post("/api/settings/backupdir", json={"path": str(new_dir)})
    assert r.status_code == 200
    assert r.json()["status"] == "switched"

    body = client.get("/api/settings/backupdir").json()
    assert body["path"] == str(new_dir.resolve())


def test_set_backupdir_unchanged(client: TestClient) -> None:
    cur = client.get("/api/settings/backupdir").json()["path"]
    r = client.post("/api/settings/backupdir", json={"path": cur})
    assert r.status_code == 200
    assert r.json()["status"] == "unchanged"


def test_set_backupdir_invalid_path(client: TestClient) -> None:
    r = client.post("/api/settings/backupdir", json={"path": "C:/不存在/xyz"})
    assert r.status_code == 422


def test_set_backupdir_inside_vault_rejected(client: TestClient) -> None:
    """备份目录不能位于 vault 内部（坑 #11）。"""
    vault = client.get("/api/settings/vault").json()["path"]
    r = client.post("/api/settings/backupdir", json={"path": vault})
    assert r.status_code == 422


# ---------- 持久化 ----------


def test_persist_settings_file(client: TestClient, other_vault: Path, tmp_path: Path) -> None:
    client.post("/api/settings/vault", json={"path": str(other_vault)})
    rf = tmp_path / "data" / "settings.json"
    assert rf.is_file()
    import json

    data = json.loads(rf.read_text(encoding="utf-8"))
    assert data["vault_path"] == str(other_vault.resolve())


# ---------- 文件系统接口 ----------


def test_browse_roots(client: TestClient) -> None:
    r = client.get("/api/settings/browse")
    assert r.status_code == 200
    body = r.json()
    assert body["path"] == ""
    assert "dirs" in body  # 盘符或 /

def test_browse_existing_dir(client: TestClient, tmp_path: Path) -> None:
    r = client.get("/api/settings/browse", params={"path": str(tmp_path)})
    assert r.status_code == 200
    assert r.json()["path"] == str(tmp_path.resolve())


def test_browse_missing_dir(client: TestClient) -> None:
    r = client.get("/api/settings/browse", params={"path": "C:/不存在/xyz"})
    assert r.status_code == 422


def test_detect(client: TestClient, tmp_path: Path) -> None:
    r = client.get("/api/settings/detect")
    assert r.status_code == 200
    body = r.json()
    assert "vaults" in body and "scanBase" in body


def test_quickaccess(client: TestClient) -> None:
    r = client.get("/api/settings/quickaccess")
    assert r.status_code == 200
    body = r.json()
    assert "disks" in body and "places" in body


# ---------- 并发切换回归（N8：共享状态并发防护） ----------


def test_concurrent_switch_no_race(client: TestClient, other_vault: Path) -> None:
    """并发两个切换请求：switch_lock 串行化，最终 health 必须指向某个一致状态。"""
    errors: list[Exception] = []

    def _switch() -> None:
        try:
            client.post("/api/settings/vault", json={"path": str(other_vault)})
        except Exception as e:  # pragma: no cover
            errors.append(e)

    threads = [threading.Thread(target=_switch) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    h = client.get("/api/health").json()
    # 两个并发切换都指向同一目标，最终状态必须是该目标（不可能是半替换的旧对象）
    assert h["vault"] == str(other_vault.resolve())

# ---------- 自动备份配置（T3 活跃式自动备份） ----------


def test_autobackup_get_default(client) -> None:
    """自动备份配置默认：间隔 30 分钟、启用。"""
    r = client.get("/api/settings/autobackup")
    assert r.status_code == 200
    d = r.json()
    assert d["intervalMinutes"] == 30
    assert d["enabled"] is True


def test_autobackup_put_persists(client) -> None:
    """修改间隔持久化到 settings.json，重启加载生效。"""
    r = client.put("/api/settings/autobackup", json={"intervalMinutes": 15})
    assert r.status_code == 200
    assert r.json()["intervalMinutes"] == 15

    # 持久化到 settings.json
    import json as _json

    rf = client.app.state.services.settings.data_dir / "settings.json"
    data = _json.loads(rf.read_text(encoding="utf-8"))
    assert data["auto_backup_interval_minutes"] == 15


def test_autobackup_put_clamps(client) -> None:
    """间隔钳制到 1 分钟 ~ 24 小时。"""
    r = client.put("/api/settings/autobackup", json={"intervalMinutes": 9999})
    assert r.status_code == 200
    assert r.json()["intervalMinutes"] == 1440
    r2 = client.put("/api/settings/autobackup", json={"intervalMinutes": 0})
    assert r2.json()["intervalMinutes"] == 1


def test_backup_now_reason_auto(client) -> None:
    """/api/backup/now 支持 reason=auto（活跃式自动备份标记）。"""
    r = client.post("/api/backup/now", json={"reason": "auto"})
    assert r.status_code == 202
    assert r.json()["reason"] == "auto"
