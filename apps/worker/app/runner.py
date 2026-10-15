"""El 'worker' no es un proceso aparte — ver el comentario de paquete en
`app.asterion`. Es un hilo de Python nativo (no una tarea `asyncio`)
corriendo adentro del mismo proceso que FastAPI, porque las etapas
pesadas (`ffmpeg`, `faster-whisper`) son llamadas BLOQUEANTES — meterlas
en una tarea async bloquearía el event loop entero, y la API dejaría de
responder mientras un job procesa. Un hilo aparte deja que la API siga
atendiendo requests (incluido '¿cómo va este job?') mientras el trabajo
pesado corre en paralelo.

Cola: la tabla `jobs` de SQLite, con `status='queued'` — no hace falta
Redis ni una librería de colas para un worker que procesa de a uno.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path

from packages.config import Settings
from packages.storage import ProjectLayout, get_connection

from .pipeline import analyze, extract_audio, inspect, plan_edits, render, select_clips, transcribe, validate

logger = logging.getLogger("worker")

POLL_INTERVAL_S = 2.0


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _set_job(db_path: Path, job_id: str, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE jobs SET {sets}, updated_at = ? WHERE id = ?",
            (*fields.values(), _now_iso(), job_id),
        )


def _set_project(db_path: Path, project_id: str, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    with get_connection(db_path) as conn:
        conn.execute(
            f"UPDATE projects SET {sets}, updated_at = ? WHERE id = ?",
            (*fields.values(), _now_iso(), project_id),
        )


def _next_queued_job(db_path: Path) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def process_job(db_path: Path, settings: Settings, job: dict) -> None:
    job_id, project_id = job["id"], job["project_id"]

    with get_connection(db_path) as conn:
        project = dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())

    layout = ProjectLayout(settings.data_dir_path(), project_id)
    layout.ensure()
    source_path = layout.source_video(project["source_filename"])

    try:
        _set_job(db_path, job_id, stage="inspect", status="running", started_at=_now_iso())
        info = inspect.run(source_path)
        _set_project(
            db_path, project_id,
            duration_s=info.duration_s, width=info.width, height=info.height,
            has_audio=1 if info.has_audio else 0,
        )

        _set_job(db_path, job_id, stage="extract_audio")
        audio_path = extract_audio.run(layout, source_path)

        _set_job(db_path, job_id, stage="transcribe")
        transcript = transcribe.run(
            layout, audio_path,
            model_size=settings.transcription_model,
            language=settings.content_language,
        )

        _set_job(db_path, job_id, stage="analyze")
        block_plans = analyze.run(layout, project_id, transcript, settings)

        _set_job(db_path, job_id, stage="select_clips")
        merged = select_clips.run(project_id, block_plans)

        _set_job(db_path, job_id, stage="plan_edits")
        planned = plan_edits.run(layout, merged, settings.edit_formats_list, duration_s=info.duration_s)

        _set_job(db_path, job_id, stage="render")
        for clip in planned:
            export_path, subtitle_path = render.run(layout, source_path, clip, transcript)
            result = validate.run(clip, export_path)
            with get_connection(db_path) as conn:
                conn.execute(
                    """INSERT INTO clips
                       (id, project_id, job_id, title, reason, layout, subtitle_style,
                        needs_review, segments_json, export_path, subtitle_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        clip.id, project_id, job_id, clip.title, clip.reason, clip.layout,
                        clip.subtitle_style, 1 if (clip.needs_review or not result.ok) else 0,
                        json.dumps(clip.segments),
                        str(export_path), str(subtitle_path) if subtitle_path else None,
                    ),
                )
            if not result.ok:
                logger.warning("clip %s con problemas de validación: %s", clip.id, result.issues)

        _set_job(db_path, job_id, stage="validate", status="done", finished_at=_now_iso())
        _set_project(db_path, project_id, status="done")

    except Exception as exc:  # cualquier etapa puede fallar — se registra, nunca se silencia
        logger.exception("job %s falló", job_id)
        _set_job(db_path, job_id, status="failed", error=str(exc), finished_at=_now_iso())
        _set_project(db_path, project_id, status="failed")


def create_job(db_path: Path, project_id: str) -> str:
    job_id = str(uuid.uuid4())
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO jobs (id, project_id, stage, status) VALUES (?, ?, 'queued', 'queued')",
            (job_id, project_id),
        )
    _set_project(db_path, project_id, status="processing")
    return job_id


def worker_loop(db_path: Path, settings: Settings, stop_event: threading.Event) -> None:
    logger.info("worker: loop arrancado, sondeando cada %.0fs", POLL_INTERVAL_S)
    while not stop_event.is_set():
        job = _next_queued_job(db_path)
        if job is None:
            stop_event.wait(POLL_INTERVAL_S)
            continue
        process_job(db_path, settings, job)


def start_worker_thread(db_path: Path, settings: Settings) -> tuple[threading.Thread, threading.Event]:
    stop_event = threading.Event()
    thread = threading.Thread(
        target=worker_loop, args=(db_path, settings, stop_event), daemon=True, name="asm-worker"
    )
    thread.start()
    return thread, stop_event
