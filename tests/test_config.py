"""M0：Settings 配置解析与路径校验（坑 #11：备份目录不得位于 vault 内）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings


def test_defaults() -> None:
    s = Settings()
    assert s.port == 8080
    assert s.index_backend == "fts5"
    assert s.backup_retention == "7d,4w,3m"
    assert s.watch_debounce_seconds == 2
    assert ".obsidian" in s.ignore_dirs_list
    assert ".trash" in s.disallowed_write_dirs_list


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("INDEX_BACKEND", "meili")
    s = Settings()
    assert s.port == 9090
    assert s.index_backend == "meili"


def test_llm_resolved_model() -> None:
    assert Settings(llm_provider="deepseek").llm_resolved_model == "deepseek-chat"
    assert Settings(llm_provider="ollama").llm_resolved_model == "qwen2.5:7b"
    assert Settings(llm_provider="deepseek", llm_model="custom-x").llm_resolved_model == "custom-x"


def test_resolved_backup_dir_defaults_to_project() -> None:
    """默认备份目录 = 项目根/backups（Docker 部署挂载 /app/backups 方便）。"""
    s = Settings(data_dir=Path("/data"))
    project_root = Path(__file__).resolve().parent.parent
    assert s.resolved_backup_dir == project_root / "backups"


def test_resolved_backup_dir_custom_override() -> None:
    """显式配置 backup_dir 时优先使用。"""
    s = Settings(backup_dir=Path("/custom/backups"))
    assert s.resolved_backup_dir == Path("/custom/backups")


def test_validate_paths_ok_when_outside_vault(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    backup = tmp_path / "data" / "backups"
    s = Settings(vault_path=vault, data_dir=backup.parent)
    s.validate_paths()  # 不应抛异常


def test_validate_paths_rejects_backup_inside_vault(tmp_path: Path) -> None:
    """坑 #11：备份目录位于 vault 内部必须拒绝启动。"""
    vault = tmp_path / "vault"
    backup = vault / "backups"
    s = Settings(vault_path=vault, backup_dir=backup)
    with pytest.raises(ValueError, match="不能位于 vault"):
        s.validate_paths()


def test_redacted_masks_secrets() -> None:
    s = Settings(llm_api_key="sk-abcdef123456", auth_token="tok")
    red = s.redacted()
    assert red["llm_api_key"] == "sk-a****"
    assert red["auth_token"] == "****"
