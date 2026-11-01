"""/api/backup：快照列表 / 创建 / 状态 / 单文件历史与恢复 / 整库恢复 / 删除。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_services, require_auth
from app.core.backup import BackupError
from app.schemas import (
    BackupListOut,
    BackupNowBody,
    BackupNowOut,
    DeleteOut,
    RestoreAllBody,
    RestoreFileBody,
    RunnerStatusOut,
    SnapshotFilesOut,
    VerifyOut,
)
from app.services import AppServices

logger = logging.getLogger("obsidian-agent.backup")

router = APIRouter(prefix="/api/backup", tags=["backup"], dependencies=[Depends(require_auth)])

RESTORE_CONFIRM_CODE = "RESTORE"


@router.get("/list", response_model=BackupListOut)
def list_backups(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    return {
        "snapshots": services.backup.list_snapshots(),
        "retention": services.backup.retention,
        "runner": services.backup_runner.status(),
    }


@router.get("/files", response_model=SnapshotFilesOut)
def snapshot_files(
    snapshotId: str, services: AppServices = Depends(get_services)
) -> dict[str, Any]:
    """快照内文件列表（相对路径，供前端展开查看）。"""
    try:
        files = services.backup.snapshot_files(snapshotId)
    except BackupError as e:
        raise HTTPException(404, str(e)) from e
    return {"snapshotId": snapshotId, "files": files}


@router.post("/verify/{snap_id}", response_model=VerifyOut)
def verify_snapshot(snap_id: str, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    """校验指定快照：文件数 + 抽样 checksum。"""
    try:
        ok, detail = services.backup.verify_snapshot(snap_id)
    except BackupError as e:
        raise HTTPException(404, str(e)) from e
    return {"snapshotId": snap_id, "ok": ok, "detail": detail}


@router.post("/now", status_code=202, response_model=BackupNowOut)
def backup_now(
    body: BackupNowBody | None = None,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    """立即备份。reason: manual（手动，默认）/ auto（前端活跃式自动备份）。"""
    reason = (body.reason if body else None) or "manual"
    try:
        services.backup_runner.run_backup(reason)
    except BackupError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True, "taskId": "backup-manual", "reason": reason}


@router.get("/status", response_model=RunnerStatusOut)
def backup_status(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    return services.backup_runner.status()


@router.get("/history")
def history(path: str, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    """单文件版本历史：来自快照 + 写前备份（pre-write）。"""
    versions: list[dict[str, Any]] = []
    for s in services.backup.list_snapshots():
        if path in services.backup.snapshot_files(s["id"]):
            versions.append({"snapshotId": s["id"], "at": s["createdAt"], "source": "snapshot"})
    pre_write = services.backup.pre_write_file(path)
    if pre_write.is_file():
        versions.append(
            {
                "snapshotId": "pre-write",
                "at": pre_write.stat().st_mtime,
                "source": "pre-write",
            }
        )
    return {"path": path, "versions": versions}


@router.post("/restore-file")
def restore_file(
    body: RestoreFileBody, services: AppServices = Depends(get_services)
) -> dict[str, Any]:
    try:
        target = services.backup.restore_file(body.path, body.snapshotId)
    except BackupError as e:
        raise HTTPException(404, str(e)) from e
    services.index.update_paths({body.path})
    return {"path": body.path, "restoredFrom": body.snapshotId, "target": target}


@router.post("/restore", status_code=202)
def restore_all(
    body: RestoreAllBody, services: AppServices = Depends(get_services)
) -> dict[str, Any]:
    if body.confirmCode != RESTORE_CONFIRM_CODE:
        raise HTTPException(400, "确认码错误：需输入 RESTORE")
    try:
        services.backup_runner.run_restore(
            body.snapshotId, after=lambda: services.index.full_rebuild()
        )
    except BackupError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True, "taskId": "restore", "snapshotId": body.snapshotId}


@router.delete("/{snap_id}", status_code=202, response_model=DeleteOut)
def delete_snapshot(snap_id: str, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    """删除快照：后台线程执行（Windows 上硬链接删除较慢，同步会卡住前端）。

    立即返回 202，前端通过轮询列表看到快照消失即删除完成。
    删除失败（如被占用）记录在引擎日志；若快照目录不存在立即 404。
    """
    if not (services.backup.snapshot_root / snap_id).is_dir():
        raise HTTPException(404, f"快照不存在: {snap_id}")
    import threading as _threading

    def _do_delete() -> None:
        try:
            services.backup.delete_snapshot(snap_id)
        except BackupError as e:
            logger.warning("删除快照失败 %s: %s", snap_id, e)

    _threading.Thread(target=_do_delete, daemon=True, name=f"del-{snap_id}").start()
    return {"ok": True, "deleting": snap_id, "async": True}
