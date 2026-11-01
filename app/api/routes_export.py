"""/api/export：整库 ZIP 导出（明文，可直接用 Obsidian 打开）。"""

from __future__ import annotations

import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.api.deps import get_services, require_auth
from app.services import AppServices

router = APIRouter(prefix="/api/export", tags=["export"], dependencies=[Depends(require_auth)])


@router.get("")
def export_vault(services: AppServices = Depends(get_services)) -> FileResponse:
    """把 vault 内所有非忽略文件打包为 ZIP；导出文件留在 data/exports。"""
    export_dir = Path(services.settings.data_dir) / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = export_dir / f"vault-export-{stamp}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for rel, abs_path in services.vault.walk_all():
            zf.write(abs_path, arcname=rel)
    return FileResponse(target, filename=target.name, media_type="application/zip")
