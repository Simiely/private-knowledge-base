"""/api/semantic：语义检索状态与向量重建（可选功能，未启用时返回 enabled=false）。"""

from __future__ import annotations

import threading
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import get_services, require_auth
from app.services import AppServices

router = APIRouter(prefix="/api/semantic", tags=["semantic"], dependencies=[Depends(require_auth)])


@router.get("/status")
def semantic_status(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    if services.semantic is None:
        return {"enabled": False, "ready": False, "model": "", "vectors": 0}
    return services.semantic.status()


@router.post("/rebuild", status_code=202)
def semantic_rebuild(services: AppServices = Depends(get_services)) -> dict[str, Any]:
    """后台重建全部向量（CPU 上大库需要几分钟，立即返回 202）。"""
    semantic = services.semantic
    if semantic is None:
        return {"ok": False, "detail": "语义检索未启用（SEMANTIC_ENABLED=false）"}
    if semantic.status().get("building"):
        return {"ok": True, "alreadyRunning": True}

    def _work() -> None:
        semantic.rebuild(services.index.iter_docs())

    threading.Thread(target=_work, daemon=True, name="semantic-rebuild").start()
    return {"ok": True, "taskId": "semantic-rebuild"}
