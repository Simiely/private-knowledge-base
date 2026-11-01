"""/api/settings：运行时配置路由 —— vault / 备份目录 查看与热切换。

薄路由：业务逻辑在 core/runtime（服务构建/持久化/并发锁），本文件只做 HTTP 适配。
热切换流程（行为不变，见 core/runtime.switch_lock 注释）：
1. 校验新路径为存在的目录，且备份目录不在其内部
2. 停止旧 watcher / 备份调度，关闭旧索引库连接
3. 重建服务并替换 request.app.state.services
4. 重新启动 watcher + 备份调度，后台线程全量重建索引
5. 持久化到 {data_dir}/settings.json，下次启动自动生效
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_services, require_auth
from app.core.backup import BackupEngine, BackupRunner, BackupScheduler
from app.core.platform import open_in_file_manager
from app.core.runtime import (
    AgentServiceFactory,
    build_services,
    persist_settings,
    switch_lock,
)
from app.core.vault import VaultError
from app.schemas import AutoBackupBody, AutoBackupOut, BackupDirOut, VaultInfoOut, VaultPathBody
from app.services import AppServices

logger = logging.getLogger("obsidian-agent.settings")

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_auth)])


@router.get("/vault", response_model=VaultInfoOut)
def get_vault(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    return {
        "path": str(services.vault.root),
        "dataDir": str(services.settings.data_dir),
    }


@router.get("/backupdir", response_model=BackupDirOut)
def get_backup_dir(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    return {
        "path": str(services.backup.backup_root),
        "enabled": services.backup.enabled,
        "retention": str(services.backup.retention),
    }


@router.post("/backupdir/open")
def open_backup_dir(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    """用系统文件管理器打开备份目录（前端「打开备份目录」按钮）。"""
    path = str(services.backup.backup_root)
    try:
        open_in_file_manager(path)
    except RuntimeError as e:
        raise HTTPException(422, str(e)) from e
    return {"ok": True, "opened": path}


@router.get("/autobackup", response_model=AutoBackupOut)
def get_auto_backup(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    """活跃式自动备份配置：间隔（分钟）+ 开关（前端滑动开关，持久化）。"""
    return {
        "intervalMinutes": services.settings.auto_backup_interval_minutes,
        "enabled": services.settings.auto_backup_enabled,
    }


@router.put("/autobackup")
def set_auto_backup(
    body: AutoBackupBody,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    """保存自动备份配置（间隔/开关，只更新传入的键），持久化到 settings.json。"""
    updates: dict[str, Any] = {}
    if body.intervalMinutes is not None:
        minutes = max(1, min(body.intervalMinutes, 24 * 60))  # 1 分钟 ~ 24 小时
        services.settings.auto_backup_interval_minutes = minutes
        updates["auto_backup_interval_minutes"] = minutes
    if body.enabled is not None:
        services.settings.auto_backup_enabled = body.enabled
        updates["auto_backup_enabled"] = body.enabled
    if updates:
        try:
            persist_settings(services.settings, **updates)
        except Exception:  # pragma: no cover - 持久化失败不影响本次设置
            logger.warning("持久化自动备份配置失败（忽略）", exc_info=True)
    return {
        "intervalMinutes": services.settings.auto_backup_interval_minutes,
        "enabled": services.settings.auto_backup_enabled,
        "ok": True,
    }


@router.post("/backupdir")
def set_backup_dir(
    body: VaultPathBody,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    """热切换备份目录：重建 backup 服务（engine/runner/scheduler/agent），不动 vault/index。"""
    with switch_lock:  # 并发切换互斥（Sitepoint 2025：共享状态必须并发防护）
        new_path = Path(body.path).expanduser().resolve()
        if not new_path.is_dir():
            raise HTTPException(422, f"目录不存在或不是目录: {new_path}")

        settings = services.settings
        if Path(settings.resolved_backup_dir).resolve() == new_path:
            return {"path": str(new_path), "ok": True, "status": "unchanged"}

        # 坑 #11：备份目录不得位于 vault 内部
        try:
            new_path.relative_to(settings.vault_path.expanduser().resolve())
        except ValueError:
            pass
        else:
            raise HTTPException(
                422, f"备份目录不能位于 vault（{settings.vault_path}）内部，请选库外的目录"
            )

        # 1. 停旧调度器
        services.backup_scheduler.stop()

        # 2. 重建 backup 服务（vault 不变，无需重建索引）
        settings.backup_dir = new_path
        backup = BackupEngine(
            vault=services.vault,
            backup_root=settings.resolved_backup_dir,
            retention=settings.backup_retention,
            max_bytes=settings.backup_max_bytes,
            verify=settings.backup_verify,
            enabled=settings.backup_enabled,
        )
        runner = BackupRunner(backup)
        scheduler = BackupScheduler(backup, settings.backup_schedule)
        # agent 持有 backup 引用，需一并重建
        agent = AgentServiceFactory.build(settings, services.vault, services.index, backup)

        services.backup = backup
        services.backup_runner = runner
        services.backup_scheduler = scheduler
        services.agent = agent

        # 3. 启动新调度器
        scheduler.start()

        # 4. 持久化
        try:
            persist_settings(settings, backup_dir=str(new_path))
        except Exception:  # pragma: no cover - 持久化失败不影响本次切换
            logger.warning("持久化备份目录失败（忽略）", exc_info=True)

        return {"path": str(new_path), "ok": True, "status": "switched"}


@router.post("/vault")
def set_vault(
    body: VaultPathBody,
    request: Request,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    with switch_lock:  # 并发切换互斥
        new_path = Path(body.path).expanduser().resolve()
        if not new_path.is_dir():
            raise HTTPException(422, f"路径不存在或不是目录: {new_path}")

        settings = services.settings
        # 切换前后路径一致：直接返回，避免无谓重建
        if Path(settings.vault_path).resolve() == new_path:
            return {"path": str(new_path), "ok": True, "status": "unchanged"}

        # 校验备份目录不得在新 vault 内部（坑 #11 防备份链断裂）
        try:
            services.settings.resolved_backup_dir.expanduser().resolve().relative_to(new_path)
        except ValueError:
            pass
        else:
            raise HTTPException(
                422,
                f"备份目录（{settings.resolved_backup_dir}）不能位于所选 vault 内部，请换一个路径",
            )

        # 1. 停止旧服务
        services.index.stop_watcher()
        services.backup_scheduler.stop()
        try:
            services.index.backend.close()
        except Exception:  # pragma: no cover - 关闭失败不阻塞切换
            logger.warning("关闭旧索引库连接失败（忽略）", exc_info=True)

        # 2. 重建全套服务
        settings.vault_path = new_path
        try:
            new_services = build_services(settings)
        except VaultError as e:
            raise HTTPException(422, str(e)) from e
        request.app.state.services = new_services

        # 3. 启动新 watcher / 备份调度 / 后台重建索引
        if settings.watch_enabled:
            new_services.index.start_watcher(settings.watch_debounce_seconds)
        new_services.backup_scheduler.start()

        def _rebuild() -> None:
            try:
                new_services.index.full_rebuild()
                logger.info("切换后索引重建完成 total=%s", new_services.index.backend.total_docs())
            except Exception:  # pragma: no cover
                logger.exception("切换后索引重建失败")

        threading.Thread(target=_rebuild, daemon=True, name="vault-switch-rebuild").start()

        # 4. 持久化（下次启动自动加载）
        try:
            persist_settings(settings, vault_path=str(new_path))
        except Exception:  # pragma: no cover - 持久化失败不影响本次切换
            logger.warning("持久化 vault 路径失败（忽略）", exc_info=True)

        return {"path": str(new_path), "ok": True, "status": "rebuilding"}
