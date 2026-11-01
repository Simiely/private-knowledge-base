"""/api/settings 文件系统路由：目录浏览 / 库自动检测 / 快捷位置。

薄路由：实际逻辑在 core/platform（S11：文件系统操作已收敛到 core），本文件只做 HTTP 适配。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_auth
from app.core import platform

router = APIRouter(
    prefix="/api/settings", tags=["filesystem"], dependencies=[Depends(require_auth)]
)


@router.get("/browse")
def browse_dirs(
    path: str = Query(default="", description="要浏览的目录路径，空 = 根/盘符列表"),
) -> dict[str, Any]:
    """返回指定路径下的子目录列表，供前端逐级导航选择 vault。"""
    try:
        return platform.browse_dirs(path)
    except FileNotFoundError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:  # pragma: no cover - 防御未知异常
        raise HTTPException(500, f"浏览目录失败: {e}") from e


@router.get("/detect")
def detect_vaults() -> dict[str, Any]:
    """自动检测本机 Obsidian 库：常见位置（用户目录/桌面/文档/下载）+ 全盘根目录浅扫。"""
    return platform.detect_local_vaults()


@router.get("/quickaccess")
def quick_access() -> dict[str, Any]:
    """快捷位置：disks = 磁盘/挂载点，places = 常用文件夹（前端侧边栏分组显示）。"""
    return platform.quick_access()
