"""应用服务容器（跨层共享的数据类）。

从 api/deps.py 拆出（重构 S1）：core/runtime.py 需要 AppServices 类型来构建服务，
但 core 不应依赖 api 层——AppServices 放这里后，core 与 api 都从本模块引用，
解除 core→api 的反向依赖（概念循环）。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agent.service import AgentService
from app.config import Settings
from app.core.backup import BackupEngine, BackupRunner, BackupScheduler
from app.core.indexer.service import IndexService
from app.core.search import SearchService
from app.core.semantic import SemanticIndex
from app.core.vault import Vault


@dataclass
class AppServices:
    """全套应用服务实例（create_app 与热切换共用，行为一致）。"""

    settings: Settings
    vault: Vault
    index: IndexService
    search: SearchService
    backup: BackupEngine
    backup_runner: BackupRunner
    backup_scheduler: BackupScheduler
    agent: AgentService
    semantic: SemanticIndex | None = None  # 未启用语义检索时为 None
