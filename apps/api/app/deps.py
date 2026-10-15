"""Dependencias compartidas de FastAPI — el path de la base y los
settings se calculan una vez al arrancar (`main.py`) y se cuelgan de
`app.state`; las rutas los piden así en vez de releer el entorno en cada
request."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request

from packages.config import Settings


def get_db_path(request: Request) -> Path:
    return request.app.state.db_path


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings
