"""El único proceso HTTP que Asterion arranca (`Contract.start`). Levanta
la API, inicializa la base, arranca el worker en un hilo de fondo (ver
`apps/worker/app/runner.py`) y sirve `frontend/dist` ya compilado — el
mismo patrón que cualquier otro plugin de este ecosistema con frontend
propio (`asterion plugin build` ya sabe correr `pnpm install && pnpm
build` ahí, sin que este archivo necesite saber nada de pnpm)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from packages.config import get_settings
from packages.storage import init_db

from .routes import clips, jobs, projects, settings_routes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("api")

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FRONTEND_DIST = PLUGIN_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db_path = settings.data_dir_path() / "app.db"
    init_db(db_path)

    app.state.settings = settings
    app.state.db_path = db_path

    # Import diferido — ver la misma nota en routes/jobs.py: carga
    # faster_whisper en cascada, no hace falta pagar ese costo si la API
    # arranca y nunca se crea ningún job.
    from apps.worker.app.runner import reconcile_orphaned_jobs, start_worker_thread

    reconciled = reconcile_orphaned_jobs(db_path)
    if reconciled:
        logger.warning("worker: %d job(s) huérfano(s) de un reinicio anterior marcados como fallidos", reconciled)

    thread, stop_event = start_worker_thread(db_path, settings)
    logger.info("API arrancada — datos en %s", settings.data_dir_path())

    yield

    stop_event.set()
    thread.join(timeout=5.0)


app = FastAPI(title="Asterion Social Clips", lifespan=lifespan)


@app.get("/health")
def health():
    return JSONResponse({"status": "healthy"})


api_v1 = "/api/v1"
app.include_router(projects.router, prefix=api_v1)
app.include_router(jobs.router, prefix=api_v1)
app.include_router(clips.router, prefix=api_v1)
app.include_router(settings_routes.router, prefix=api_v1)


if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # Cualquier ruta que no matcheó ya contra /api/v1/* ni /assets/*
        # es una ruta de React Router del lado del cliente (/projects/abc,
        # /settings, etc.) — se le devuelve siempre el mismo index.html y
        # el router del navegador decide qué pantalla mostrar.
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/")
    def no_frontend_yet():
        return JSONResponse(
            {
                "detail": (
                    "frontend/dist todavía no existe — 'asterion plugin build social-clips' "
                    "compila el frontend (pnpm install && pnpm build) antes de arrancarlo."
                )
            },
            status_code=503,
        )
