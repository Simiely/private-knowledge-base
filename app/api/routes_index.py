"""/api/index：索引状态与重建。"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_services, require_auth
from app.schemas import IndexStatusOut
from app.services import AppServices

router = APIRouter(prefix="/api/index", tags=["index"], dependencies=[Depends(require_auth)])


@router.get("/status", response_model=IndexStatusOut)
def status(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    return services.index.status()


@router.post("/rebuild", status_code=202)
def rebuild(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    if services.index.building:
        raise HTTPException(409, "索引正在构建中")
    threading.Thread(target=services.index.full_rebuild, daemon=True, name="api-rebuild").start()
    return {"ok": True, "message": "全量重建已启动"}
