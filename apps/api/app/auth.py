"""Login simple de un solo usuario para entrar al editor.

El usuario y la clave se configuran desde Asterion (`ADMIN_USERNAME` /
`ADMIN_PASSWORD`, ver `packages/config/settings.py` y `app.asterion`) —
Asterion cifra la clave en reposo (type=secret). No hay tabla de usuarios
ni hash guardado: es UNA credencial de admin, así que se compara directo
contra la config (en tiempo constante). La sesión es un token FIRMADO con
HMAC-SHA256 (stdlib, sin dependencias nuevas), guardado en una cookie
httpOnly; la clave de firma se deriva de la propia contraseña, así cambiar
la clave invalida todas las sesiones viejas sin guardar estado en ningún
lado.

Si `ADMIN_PASSWORD` queda vacío, el login está DESHABILITADO y todo queda
abierto a quien llegue al puerto — el mismo comportamiento de antes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time

from packages.config import Settings

COOKIE_NAME = "sc_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 días


def auth_enabled(settings: Settings) -> bool:
    return bool(settings.admin_password)


def _secret(settings: Settings) -> bytes:
    # Clave de firma derivada de usuario+clave: estable entre reinicios
    # mientras la clave no cambie, y cambiar la clave invalida los tokens
    # viejos (su firma deja de validar). El sufijo versiona el esquema.
    base = f"{settings.admin_username}:{settings.admin_password}:social-clips-auth-v1"
    return hashlib.sha256(base.encode("utf-8")).digest()


def check_credentials(username: str, password: str, settings: Settings) -> bool:
    if not auth_enabled(settings):
        return False
    user_ok = hmac.compare_digest((username or ""), settings.admin_username)
    pass_ok = hmac.compare_digest((password or ""), settings.admin_password)
    return user_ok and pass_ok


def make_token(username: str, settings: Settings, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{username}:{exp}".encode("utf-8")
    sig = hmac.new(_secret(settings), payload, hashlib.sha256).digest()
    return (
        base64.urlsafe_b64encode(payload).decode("ascii")
        + "."
        + base64.urlsafe_b64encode(sig).decode("ascii")
    )


def verify_token(token: str | None, settings: Settings) -> str | None:
    """Devuelve el usuario si el token es válido y no expiró, si no None."""
    if not token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = base64.urlsafe_b64decode(payload_b64)
        sig = base64.urlsafe_b64decode(sig_b64)
    except Exception:
        return None
    expected = hmac.new(_secret(settings), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        username, exp = payload.decode("utf-8").rsplit(":", 1)
    except Exception:
        return None
    if int(exp) < int(time.time()):
        return None
    return username
