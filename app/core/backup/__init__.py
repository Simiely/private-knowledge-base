"""备份子系统（包门面，S2 拆分）。

对外保持 `from app.core.backup import BackupEngine, ...` 兼容——
实现拆到 specs / engine / runner / scheduler / fsutil 各模块。

设计（docs/09 §10）：
- 快照 = 普通目录树（可人工直接读取），未变文件硬链接复用上一快照（零空间占用）
- os.link 失败自动降级为复制（坑 #13）
- 备份根目录必须位于 vault 之外（坑 #11，由 config.validate_paths 保证）
- 恢复前强制先建"恢复前快照"（坑 #14）
"""

from __future__ import annotations

from app.core.backup.engine import (
    PRE_RESTORE_DIR,
    PRE_WRITE_DIR,
    SNAPSHOT_DIR,
    SNAPSHOT_MANIFEST,
    BackupEngine,
)
from app.core.backup.fsutil import _md5, rmtree_manual
from app.core.backup.runner import BackupRunner
from app.core.backup.scheduler import BackupScheduler
from app.core.backup.specs import BackupError, CronSpec, RetentionSpec

__all__ = [
    "BackupEngine",
    "BackupRunner",
    "BackupScheduler",
    "BackupError",
    "CronSpec",
    "RetentionSpec",
    "rmtree_manual",
    "_md5",
    "SNAPSHOT_MANIFEST",
    "PRE_WRITE_DIR",
    "PRE_RESTORE_DIR",
    "SNAPSHOT_DIR",
]
