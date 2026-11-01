"""运行时配置领域层：服务构建工厂 / 运行时配置持久化 / 热切换并发锁。

职责（从 api/routes_settings.py 拆分而来，纯领域逻辑，不依赖 Web 框架）：
- build_services：以 Settings 构建全套服务（create_app 与热切换共用，行为一致）
- load_runtime_settings / persist_settings：{data_dir}/settings.json 读写
- switch_lock：热切换互斥锁——防止两个切换请求并发重建服务（Sitepoint 2025 并发警告）
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

from app.config import Settings
from app.core.backup import BackupEngine, BackupRunner, BackupScheduler
from app.core.indexer.fts5 import Fts5Index
from app.core.indexer.service import IndexService
from app.core.search import SearchService
from app.core.semantic import SemanticIndex
from app.core.vault import Vault
from app.services import AppServices

logger = logging.getLogger("obsidian-agent.runtime")

RUNTIME_FILE = "settings.json"

# 热切换互斥锁：set_vault / set_backupdir 重建服务期间串行化，
# 防止并发切换导致 app.state.services 读到半替换状态（竞态）。
switch_lock = threading.RLock()


def load_runtime_settings(settings: Settings) -> None:
    """读取 {data_dir}/settings.json 覆盖 .env（vault_path / backup_dir / auto_backup 持久化）。"""
    rf = settings.data_dir / RUNTIME_FILE
    if not rf.is_file():
        return
    try:
        data = json.loads(rf.read_text(encoding="utf-8"))
        if data.get("vault_path"):
            settings.vault_path = Path(str(data["vault_path"]))
            logger.info("已应用运行时配置 vault_path=%s", settings.vault_path)
        if data.get("backup_dir"):
            settings.backup_dir = Path(str(data["backup_dir"]))
            logger.info("已应用运行时配置 backup_dir=%s", settings.backup_dir)
        if data.get("auto_backup_interval_minutes") is not None:
            settings.auto_backup_interval_minutes = int(data["auto_backup_interval_minutes"])
            logger.info(
                "已应用运行时配置 auto_backup_interval_minutes=%s",
                settings.auto_backup_interval_minutes,
            )
        if data.get("auto_backup_enabled") is not None:
            settings.auto_backup_enabled = bool(data["auto_backup_enabled"])
            logger.info(
                "已应用运行时配置 auto_backup_enabled=%s",
                settings.auto_backup_enabled,
            )
    except Exception:  # pragma: no cover - 配置文件损坏不应阻塞启动
        logger.warning("读取运行时配置失败（忽略）: %s", rf)


def persist_settings(settings: Settings, **updates: Any) -> None:
    """合并写入 {data_dir}/settings.json（保留已有字段，仅更新传入的键）。"""
    rf = settings.data_dir / RUNTIME_FILE
    rf.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if rf.is_file():
        try:
            data = {**json.loads(rf.read_text(encoding="utf-8"))}
        except Exception:  # pragma: no cover
            data = {}
    data.update(updates)
    rf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_services(settings: Settings) -> AppServices:
    """以 settings.vault_path 构建全套服务（create_app 与热切换共用，保持行为一致）。"""
    vault = Vault(
        root=settings.vault_path,
        ignore_dirs=settings.ignore_dirs_list,
        ignore_files=settings.ignore_files_list,
        max_file_bytes=settings.max_file_bytes,
    )
    backend = Fts5Index(
        db_path=settings.data_dir / "index.db",
        userdict=settings.jieba_userdict or None,
    )
    index = IndexService(vault=vault, backend=backend)
    semantic: SemanticIndex | None = None
    if settings.semantic_enabled:
        semantic = SemanticIndex(
            db_path=settings.data_dir / "vectors.db",
            model_name=settings.semantic_model,
            cache_dir=settings.resolved_semantic_cache_dir,
            max_chars=settings.semantic_max_chars,
            weight=settings.semantic_weight,
            top_k=settings.semantic_top_k,
        )
        index.semantic = semantic
    search = SearchService(index, semantic)
    backup = BackupEngine(
        vault=vault,
        backup_root=settings.resolved_backup_dir,
        retention=settings.backup_retention,
        max_bytes=settings.backup_max_bytes,
        verify=settings.backup_verify,
        enabled=settings.backup_enabled,
    )
    return AppServices(
        settings=settings,
        vault=vault,
        index=index,
        search=search,
        backup=backup,
        backup_runner=BackupRunner(backup),
        backup_scheduler=BackupScheduler(backup, settings.backup_schedule),
        agent=AgentServiceFactory.build(settings, vault, index, backup),
        semantic=semantic,
    )


class AgentServiceFactory:
    """延迟导入 AgentService，避免 runtime 模块在 LLM 未配置时引入重依赖。"""

    @staticmethod
    def build(settings: Settings, vault: Vault, index: IndexService, backup: BackupEngine) -> Any:
        from app.agent.service import AgentService

        return AgentService(vault=vault, index=index, backup=backup, settings=settings)
