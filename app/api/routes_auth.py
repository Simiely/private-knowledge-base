"""单用户登录：口令换取 HttpOnly Cookie。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.deps import SESSION_COOKIE, get_services, require_auth
from app.services import AppServices

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginBody(BaseModel):
    token: str


@router.post("/login")
def login(
    body: LoginBody,
    response: Response,
    services: AppServices = Depends(get_services),
) -> dict[str, bool]:
    settings = services.settings
    if settings.auth_disabled:
        return {"ok": True}
    if not settings.auth_token:
        raise HTTPException(status_code=503, detail="服务端未配置 AUTH_TOKEN")
    if body.token != settings.auth_token:
        raise HTTPException(status_code=401, detail="口令错误")
    response.set_cookie(
        SESSION_COOKIE,
        settings.auth_token,
        max_age=7 * 24 * 60 * 60,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(
    request: Request,
    services: AppServices = Depends(get_services),
    _: None = Depends(require_auth),
) -> dict[str, object]:
    settings = services.settings
    return {
        "authenticated": True,
        "authDisabled": settings.auth_disabled,
    }
