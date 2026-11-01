"""Agent 编辑安全层：写前校验 + 备份 + diff（docs/02 §3.3 安全链路）。

不依赖 Pydantic AI 框架，可独立测试。
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.backup import BackupEngine
from app.core.vault import PathNotAllowed, Vault


class SafetyError(Exception):
    """安全校验失败（Agent 写操作被拒）。"""


def check_write_rules(settings: Settings, rel: str) -> None:
    """共享白名单规则（API 层与 Agent 层唯一实现）：禁写目录 + 隐藏路径。

    - 不检查路径越界/格式（由 vault.resolve_safe_path 统一负责，语义区分）
    - 不要求文件存在（新增文件也走此校验）
    - 违反任一规则抛 SafetyError
    """
    parts = Path(rel).parts
    for d in settings.disallowed_write_dirs_list:
        if d in parts:
            raise SafetyError(f"禁止写入目录: {d}")
    # 隐藏目录/文件：`.` `..` 是相对路径导航符，不算隐藏路径（越界由 vault 统一报 422）
    if any(p.startswith(".") and p not in (".", "..") for p in parts):
        raise SafetyError("禁止写入隐藏目录/文件")


def check_writable(vault: Vault, settings: Settings, rel: str) -> None:
    """路径白名单校验：越界 / 非 md / 禁写目录 / 隐藏目录 / 存在性（坑 #7、#1）。"""
    try:
        vault.resolve_safe_path(rel, md_only=True)  # 先做格式/越界校验（不要求存在）
    except PathNotAllowed as e:
        raise SafetyError(f"路径非法: {e}") from e
    check_write_rules(settings, rel)  # 共享白名单规则（唯一实现）
    if not (vault.root / rel).is_file():
        raise SafetyError(f"文件不存在: {rel}")


def render_diff(old: str, new: str, max_lines: int = 60) -> str:
    """生成统一 diff（截断防止撑爆上下文）。"""
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=2)
    lines = list(diff)
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... (diff 过长，已截断，共 {len(lines)} 行)"]
    return "\n".join(lines) or "(无差异)"


def prepare_write(
    vault: Vault,
    settings: Settings,
    backup: BackupEngine,
    rel: str,
    content: str,
) -> dict[str, Any]:
    """写前检查：校验 → 备份原文件 → 生成 diff。返回操作元数据（不落盘）。"""
    check_writable(vault, settings, rel)
    old = vault.read(rel).text
    backup_path = backup.backup_for_write(rel)
    return {
        "ok": True,
        "path": rel,
        "old_size": len(old),
        "new_size": len(content),
        "backup_path": backup_path,
        "diff": render_diff(old, content),
        "content": content,  # 待确认内容（确认后写入）
    }
