"""/api/search：全文检索。"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_services, require_auth
from app.schemas import SearchOut
from app.services import AppServices

router = APIRouter(prefix="/api/search", tags=["search"], dependencies=[Depends(require_auth)])


@router.get("", response_model=SearchOut)
def search(
    q: str = Query(...),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    mode: Literal["or", "and"] = Query("or", description="or=自然语言模糊；and=精确全词"),
    services: AppServices = Depends(get_services),
) -> Any:
    return services.search.search(q, page=page, page_size=pageSize, mode=mode)


@router.get("/tags")
def tags(services: AppServices = Depends(get_services)) -> list[dict[str, Any]]:
    """全部标签及文档数，供前端筛选与 MCP list_tags 使用。"""
    return services.search.list_tags()


@router.get("/by-id/{doc_id}")
def by_id(doc_id: str, services: AppServices = Depends(get_services)) -> dict[str, Any]:
    """按稳定 doc_id 反查路径/标题/标签。"""
    hit = services.search.get_by_doc_id(doc_id)
    if hit is None:
        raise HTTPException(404, f"文档不存在: {doc_id}")
    return hit
