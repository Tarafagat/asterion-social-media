from __future__ import annotations

from pathlib import Path

from packages.storage import get_connection

# El mismo orden que corre packages/worker/app/runner.py — usado por la
# API solo para calcular un % de progreso aproximado para la UI
# (JobProgress), nunca para decidir qué corre el worker.
STAGE_ORDER = [
    "queued", "inspect", "extract_audio", "transcribe",
    "analyze", "select_clips", "plan_edits", "render", "validate",
]


def get_job(db_path: Path, job_id: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    job = dict(row)
    job["progress_pct"] = _progress_pct(job["stage"], job["status"])
    return job


def _progress_pct(stage: str, status: str) -> int:
    if status == "done":
        return 100
    if status == "failed":
        return 0
    try:
        idx = STAGE_ORDER.index(stage)
    except ValueError:
        return 0
    return round(100 * idx / (len(STAGE_ORDER) - 1))


def list_jobs_for_project(db_path: Path, project_id: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC", (project_id,)
        ).fetchall()
    return [dict(r) | {"progress_pct": _progress_pct(r["stage"], r["status"])} for r in rows]
