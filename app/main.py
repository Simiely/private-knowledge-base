"""Obsidian Agent —— 应用入口（M3：API 层完整路由 + 启动生命周期）。

create_app(settings) 工厂模式：测试可注入自定义配置；uvicorn 入口使用模块级 app。
"""

from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_agent,
    routes_auth,
    routes_backup,
    routes_export,
    routes_filesystem,
    routes_index,
    routes_search,
    routes_semantic,
    routes_settings,
    routes_vault,
)
from app.config import Settings, get_settings
from app.core.backup import BackupError
from app.core.runtime import build_services, load_runtime_settings
from app.core.vault import FileTooLarge, PathNotAllowed, VaultError
from app.services import AppServices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("obsidian-agent")

APP_VERSION = "0.1.0"


def create_app(settings: Settings | None = None) -> FastAPI:
    """应用工厂：构建领域服务 → 挂载路由 → 生命周期（索引/watcher/定时备份）。"""
    settings = settings or get_settings()
    load_runtime_settings(settings)  # 热切换持久化：读取 data/settings.json 覆盖 vault_path
    settings.validate_paths()  # 坑 #11：备份目录不得位于 vault 内，失败即拒绝启动
    services = build_services(settings)  # 服务构建统一走 core/runtime（与热切换共用）

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # 启动/关闭/后台线程统一从 app.state 取服务：vault 热切换后仍是新对象（防闭包串库）
        initial: AppServices = app.state.services
        if settings.watch_enabled:
            initial.index.start_watcher(settings.watch_debounce_seconds, settings.watch_polling)
        initial.backup_scheduler.start()

        def _build_vectors(services_ref: AppServices) -> None:
            try:
                semantic = services_ref.semantic
                if semantic is None:
                    return
                docs = services_ref.index.iter_docs()
                result = semantic.rebuild(docs)
                logger.info("初始语义索引完成 %s", result)
            except Exception:  # pragma: no cover - 语义失败不影响关键词检索
                logger.exception("初始语义索引失败")

        def _bootstrap() -> None:
            try:
                cur: AppServices = app.state.services
                cur.index.full_rebuild()
                logger.info("初始索引完成 total=%s", cur.index.backend.total_docs())
                if cur.semantic is not None and cur.semantic.needs_rebuild(
                    cur.index.backend.total_docs()
                ):
                    # 向量构建很慢（CPU embedding），放到独立线程，不阻塞关键词检索
                    threading.Thread(
                        target=_build_vectors, args=(cur,), daemon=True, name="semantic-index"
                    ).start()
            except Exception:  # pragma: no cover
                logger.exception("初始索引失败")

        boot_thread = threading.Thread(target=_bootstrap, daemon=True, name="initial-index")
        boot_thread.start()
        yield
        # 关闭阶段动态取最新服务：vault 热切换后 app.state 已是新服务对象
        current: AppServices = app.state.services
        current.index.stop_watcher()
        current.backup_scheduler.stop()
        # 优雅关闭：等待初始索引线程结束再关连接，避免并发 close sqlite（access violation）
        boot_thread.join(timeout=30)
        if boot_thread.is_alive():  # pragma: no cover - 大库超时场景
            logger.warning("初始索引仍在运行，跳过索引库连接关闭（进程退出时回收）")
        else:
            # 等后台重建（API 触发 / 切换库触发）结束再关连接，防跨线程 close SQLite
            current.index.shutdown()

    app = FastAPI(
        title="Obsidian Agent",
        description=(
            "Dockerized Obsidian AI workspace: browse, edit, "
            "full-text search and AI agent over your vault"
        ),
        version=APP_VERSION,
        lifespan=lifespan,
    )
    # 安全默认：不启用通配 CORS；需要跨源时显式配置 CORS_ORIGINS。
    if settings.cors_origins_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["X-Auth-Token", "Content-Type"],
        )
    if settings.auth_disabled:
        logger.warning("AUTH_DISABLED=true：API 无鉴权，仅限本地开发/测试")
    elif not settings.auth_token:
        logger.warning("AUTH_TOKEN 为空：API 将返回 503，直到配置 token 或显式关闭鉴权")

    app.state.services = services

    app.include_router(routes_auth.router)
    app.include_router(routes_vault.router)
    app.include_router(routes_search.router)
    app.include_router(routes_index.router)
    app.include_router(routes_backup.router)
    app.include_router(routes_export.router)
    app.include_router(routes_semantic.router)
    app.include_router(routes_agent.router)
    # 目录浏览/切换 vault/切换备份目录只在本地开发显式开启；生产不暴露。
    if settings.enable_local_settings:
        app.include_router(routes_settings.router)
        app.include_router(routes_filesystem.router)

    @app.get("/api/health", tags=["system"])
    def health(request: Request) -> dict[str, Any]:
        # 从 app.state 动态取服务：vault 热切换后仍指向最新服务（闭包引用会指向已关闭的旧索引）
        services: AppServices = request.app.state.services
        st = services.index.status()
        return {
            "status": "ok",
            "version": APP_VERSION,
            "vault": str(services.settings.vault_path),
            "indexBackend": st["backend"],
            "indexState": st["state"],
        }

    @app.get("/api/version", tags=["system"])
    def version() -> dict[str, Any]:
        return {"version": APP_VERSION}

    _register_exception_handlers(app)

    # 静态前端：挂载 Vue3 构建产物 dist；缺失时明确报错，不静默回退旧版占位页
    # （坑：回退 frontend/static 曾导致用户拿到 M0 旧版页面、层级目录无法访问）
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    static_dir = frontend_dir / "dist"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
    else:
        logger.error(
            "未找到 frontend/dist（Vue 构建产物）。请先执行 `cd frontend && npm run build`，"
            "否则前端页面不可用（API 正常）。"
        )
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """核心领域异常 → HTTP 状态码映射（docs/05 §1 错误约定）。"""

    @app.exception_handler(PathNotAllowed)
    async def _path_not_allowed(_: Request, exc: PathNotAllowed) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(FileTooLarge)
    async def _file_too_large(_: Request, exc: FileTooLarge) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(FileNotFoundError)
    async def _not_found(_: Request, exc: FileNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(FileExistsError)
    async def _conflict(_: Request, exc: FileExistsError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(BackupError)
    async def _backup_error(_: Request, exc: BackupError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(VaultError)
    async def _vault_error(_: Request, exc: VaultError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})


# uvicorn 入口：配置错误（如 vault 路径不存在）时不阻塞 import，由占位 app 暴露错误
def _placeholder_app(error: str) -> FastAPI:
    """配置错误的占位应用：/api/health 返回 500，其余接口不可用。"""

    app = FastAPI(title="Obsidian Agent (配置错误)", version=APP_VERSION)

    @app.get("/api/health")
    def health() -> JSONResponse:
        return JSONResponse(status_code=500, content={"status": "error", "detail": error})

    return app


try:
    app = create_app()
except Exception as exc:  # pragma: no cover - 仅配置错误路径
    logger.error("应用初始化失败（检查 VAULT_PATH 等配置）: %s", exc)
    app = _placeholder_app(str(exc))
