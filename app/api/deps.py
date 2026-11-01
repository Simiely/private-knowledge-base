"""API 层公共依赖：应用服务单例 / 认证 / 禁写校验。

AppServices 数据类已移至 app/services.py（S1：解除 core→api 反向依赖），
本模块只保留 API 专属依赖（get_services / require_auth / ensure_writable）。
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from app.agent.safety import SafetyError, check_write_rules
from app.services import AppServices


def get_services(request: Request) -> AppServices:
    services: AppServices = request.app.state.services
    return services


SESSION_COOKIE = "oa_session"


async def require_auth(request: Request, x_auth_token: str | None = Header(default=None)) -> None:
    """单用户口令认证。

    支持两种凭证：
    - 浏览器：登录后 HttpOnly Cookie（图片等资源请求也能自动携带）；
    - 程序/MCP：`X-Auth-Token` 请求头。
    未配置 AUTH_TOKEN 时直接拒绝（503），避免空 token 全站裸奔。
    """
    settings = request.app.state.services.settings
    if settings.auth_disabled:
        return
    if not settings.auth_token:
        raise HTTPException(
            status_code=503,
            detail="服务端未配置 AUTH_TOKEN；请设置后重启，或仅本地开发时显式 AUTH_DISABLED=true",
        )
    presented = x_auth_token or request.cookies.get(SESSION_COOKIE)
    if presented != settings.auth_token:
        raise HTTPException(status_code=401, detail="未授权：请先登录或提供 X-Auth-Token")


def ensure_writable(services: AppServices, rel: str) -> None:
    """写操作前检查：路径不在禁写目录、不以点开头（03 API 参考 §4.3 白名单语义）。

    复用 agent.safety.check_write_rules（共享白名单唯一实现），SafetyError 转 403。
    注意：`..` 越界路径不在此拦截——由 vault.resolve_safe_path 报 422（语义区分）。
    """
    try:
        check_write_rules(services.settings, rel)
    except SafetyError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
