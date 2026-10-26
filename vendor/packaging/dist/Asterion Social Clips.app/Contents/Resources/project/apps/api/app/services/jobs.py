from __future__ import annotations

from pathlib import Path

from packages.storage import get_connection

# El mismo orden que corre packages/worker/app/runner.py — usado por la
# API solo para calcular un % de progreso aproximado para la UI
# (JobProgress), nunca para decidir qué corre el worker. Una lista por
# `kind` de job (ver jobs.kind) — todas comparten el mismo campo `stage`
# en la tabla, pero cada kind tiene sus propias etapas/longitud, así que
# no pueden compartir una sola lista sin pisarse el denominador del %.
STAGE_ORDER_BY_KIND: dict[str, list[str]] = {
    "pipeline": ["queued", "inspect", "extract_audio", "transcribe", "analyze", "select_clips", "plan_edits", "render", "validate"],
    "clip_edit": ["queued", "render", "validate"],
    "avatar_generate": ["queued", "tts", "sadtalker", "done"],
    "dub_video": ["queued", "tts", "mux", "done"],
    "dub_video_avatar": ["queued", "tts", "sadtalker", "mux", "done"],
    "transcribe_only": ["queued", "inspect", "extract_audio", "transcribe", "done"],
}


def get_job(db_path: Path, job_id: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    job = dict(row)
    job["progress_pct"] = _progress_pct(job)
    return job


def _progress_pct(job: dict) -> int:
    if job["status"] == "done":
        return 100
    if job["status"] == "failed":
        return 0
    # jobs.progress_pct (la columna cruda) es un override FINO opcional
    # dentro de una etapa — hoy solo lo escribe avatar_generate durante
    # 'sadtalker', parseado en vivo del propio progreso de SadTalker (ver
    # packages/avatar/sadtalker_runner.py). Si está, manda; si no, se
    # cae al % calculado por posición de etapa de siempre.
    if job.get("progress_pct") is not None:
        return job["progress_pct"]
    stage_order = STAGE_ORDER_BY_KIND.get(job["kind"], STAGE_ORDER_BY_KIND["pipeline"])
    try:
        idx = stage_order.index(job["stage"])
    except ValueError:
        return 0
    return round(100 * idx / (len(stage_order) - 1))


def list_jobs_for_project(db_path: Path, project_id: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
        ).fetchall()
    out = []
    for r in rows:
        job = dict(r)
        job["progress_pct"] = _progress_pct(job)
        out.append(job)
    return out
