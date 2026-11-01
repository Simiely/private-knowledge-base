"""共享 pytest fixture（重构计划 S5：统一 fixture，避免各文件内联重复）。

用法：`def test_xxx(app_client): ...` 直接拿 TestClient；需要独立 vault 结构时用 tmp_path 自建。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

# 测试默认关闭鉴权、开启本地设置路由；安全相关用例显式覆盖。
os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("ENABLE_LOCAL_SETTINGS", "true")


@pytest.fixture
def vault_root(tmp_path: Path) -> Path:
    """标准测试库：根目录 + 首页.md。"""
    root = tmp_path / "vault"
    root.mkdir()
    (root / "首页.md").write_bytes("# 首页\n".encode())
    return root


@pytest.fixture
def app_client(vault_root: Path, tmp_path: Path) -> TestClient:
    """完整应用 TestClient（索引关闭、无定时备份），测试结束自动清理。

    注意：必须显式指定 backup_dir=tmp_path/backups——默认备份目录是项目根/backups，
    不指定会污染真实备份目录。
    """
    settings = Settings(
        vault_path=vault_root,
        data_dir=tmp_path / "data",
        backup_dir=tmp_path / "backups",
        watch_enabled=False,
        backup_schedule="",
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
