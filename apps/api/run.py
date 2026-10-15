"""Lo que declara `Contract.start(...)` en `app.asterion`. Agrega la RAÍZ
del proyecto a `sys.path` (no `apps/api/`) para que `packages.*` y
`apps.worker.app.*` sean importables como paquetes de verdad desde
cualquier módulo — así ni `apps/api/app` ni `apps/worker/app` necesitan
su propio `pyproject.toml`/instalación editable solo para verse entre
sí."""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn  # noqa: E402 (después del sys.path.insert, a propósito)

from apps.api.app.main import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("ASTERION_PLUGIN_PORT", "8899"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
