from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from packages.config import Settings

from ..auth import (
    COOKIE_NAME,
    SESSION_TTL_SECONDS,
    auth_enabled,
    check_credentials,
    make_token,
    verify_token,
)
from ..deps import get_settings_dep

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.get("/me")
def me(request: Request, settings: Settings = Depends(get_settings_dep)) -> dict:
    """Estado del login para el frontend. `enabled=false` = no hay clave
    configurada, así que no se pide login (todo abierto)."""
    if not auth_enabled(settings):
        return {"enabled": False, "authenticated": True, "username": None}
    user = verify_token(request.cookies.get(COOKIE_NAME), settings)
    return {"enabled": True, "authenticated": user is not None, "username": user}


@router.post("/login")
def login(body: LoginIn, response: Response, settings: Settings = Depends(get_settings_dep)) -> dict:
    if not auth_enabled(settings):
        # Sin clave configurada no hay nada que validar — ya está "dentro".
        return {"enabled": False, "authenticated": True, "username": None}
    if not check_credentials(body.username, body.password, settings):
        raise HTTPException(401, "Usuario o clave incorrectos.")
    token = make_token(body.username, settings)
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=SESSION_TTL_SECONDS, httponly=True, samesite="lax", path="/",
    )
    return {"enabled": True, "authenticated": True, "username": body.username}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
