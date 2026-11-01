"""/api/vault：目录树 / 文件读写 / 元信息。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.deps import ensure_writable, get_services, require_auth
from app.core.vault import ASSET_EXTS, ATTACHMENT_EXTS, FileTooLarge, PathNotAllowed
from app.schemas import (
    FileCreate,
    FileMetaOutFlat,
    FileReadOut,
    FileWrite,
    PathResult,
    TreeNode,
)
from app.services import AppServices

router = APIRouter(prefix="/api/vault", tags=["vault"], dependencies=[Depends(require_auth)])


@router.get("/resolve-md")
def resolve_md(
    name: str = Query(..., description="文档名（Obsidian wikilink 目标，如 '目标' 或 '目标.md'）"),
    services: AppServices = Depends(get_services),
) -> dict[str, str]:
    """按文件名全库解析 md 文档路径（`[[目标]]` wikilink 语义：文件可在任意目录）。"""
    found = services.vault.find_md_by_name(name)
    if found is None:
        raise HTTPException(404, f"未找到文档: {name!r}")
    return {"path": found}


@router.get("/asset")
def get_asset(
    path: str = Query(..., description="vault 内图片路径（相对路径，或 Obsidian wikilink 文件名）"),
    services: AppServices = Depends(get_services),
) -> FileResponse:
    """读取 vault 内图片资源（md 里 `![](相对路径)` / `![[文件名.png]]` 引用的图片）。

    解析顺序：
    1. 相对路径（基于 vault 根，如 attachments/x.png，`![](...)` 由前端解析后传入）
    2. 按文件名全库搜索（Obsidian wikilink `![[x.png]]` 语义：文件可在任意目录）

    安全：resolve_safe_path 防路径遍历/越界/绝对路径；仅允许图片扩展名。
    """
    try:
        try:
            full = services.vault.resolve_safe_path(path, must_exist=True)
        except FileNotFoundError:
            # 相对路径不存在 → 尝试 wikilink 文件名全库匹配
            found = services.vault.find_asset_by_name(path)
            if found is None:
                raise HTTPException(404, f"图片资源不存在: {path!r}") from None
            full = found
    except PathNotAllowed as e:
        raise HTTPException(422, str(e)) from e
    if full.suffix.lower() not in ASSET_EXTS:
        raise HTTPException(422, f"仅允许图片资源（{', '.join(sorted(ASSET_EXTS))}）: {path!r}")
    return FileResponse(full)


@router.get("/attachment")
def get_attachment(
    path: str = Query(..., description="vault 内附件相对路径"),
    services: AppServices = Depends(get_services),
) -> FileResponse:
    """下载 PDF/PPTX/MP4/ZIP 等附件；白名单 + 路径越界防护。"""
    try:
        full = services.vault.resolve_safe_path(path, must_exist=True)
    except (PathNotAllowed, FileNotFoundError) as e:
        raise HTTPException(404 if isinstance(e, FileNotFoundError) else 422, str(e)) from e
    if full.suffix.lower() not in ATTACHMENT_EXTS:
        raise HTTPException(422, f"不允许的附件类型: {path!r}")
    # filename 会让浏览器以附件方式下载，避免 HTML 在同源内联执行。
    return FileResponse(full, filename=full.name)


@router.get("/tree", response_model=list[TreeNode])
def tree(
    path: str = "",
    services: AppServices = Depends(get_services),
) -> Any:
    try:
        return services.vault.tree(path)
    except (FileNotFoundError, PathNotAllowed) as e:
        raise HTTPException(
            status_code=404 if isinstance(e, FileNotFoundError) else 422, detail=str(e)
        ) from e


@router.get("/file", response_model=FileReadOut)
def read_file(
    path: str = Query(...),
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    try:
        content = services.vault.read(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PathNotAllowed as e:
        raise HTTPException(422, str(e)) from e
    meta = content.meta
    return {
        "path": path,
        "content": content.text,
        "meta": {
            "size": meta.size,
            "mtime": meta.mtime,
            "encoding": meta.encoding,
            "newline": meta.newline,
        },
    }


@router.put("/file", response_model=PathResult)
def write_file(
    body: FileWrite,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    ensure_writable(services, body.path)
    try:
        services.vault.write(body.path, body.content)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except (PathNotAllowed, FileTooLarge) as e:
        raise HTTPException(422 if isinstance(e, PathNotAllowed) else 403, str(e)) from e
    services.index.update_paths({body.path})
    return {"path": body.path, "ok": True}


@router.post("/file", status_code=201, response_model=PathResult)
def create_file(
    body: FileCreate,
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    ensure_writable(services, body.path)
    try:
        services.vault.create(body.path, body.content)
    except FileExistsError as e:
        raise HTTPException(409, str(e)) from e
    except PathNotAllowed as e:
        raise HTTPException(422, str(e)) from e
    services.index.update_paths({body.path})
    return {"path": body.path, "ok": True}


@router.delete("/file", response_model=PathResult)
def delete_file(
    path: str = Query(...),
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    ensure_writable(services, path)
    try:
        services.vault.delete(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PathNotAllowed as e:
        raise HTTPException(422, str(e)) from e
    services.index.update_paths({path})
    return {"path": path, "ok": True}


@router.get("/meta", response_model=FileMetaOutFlat)
def meta(
    path: str = Query(...),
    services: AppServices = Depends(get_services),
) -> dict[str, Any]:
    try:
        m = services.vault.meta(path)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e)) from e
    except PathNotAllowed as e:
        raise HTTPException(422, str(e)) from e
    return {
        "path": path,
        "size": m.size,
        "mtime": m.mtime,
        "encoding": m.encoding,
        "newline": m.newline,
    }
