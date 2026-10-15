"""La capa entre las rutas HTTP y SQLite — nada de lógica de negocio
pesada acá (eso vive en `packages/`/`apps/worker`), solo las consultas."""

from __future__ import annotations

import uuid
from pathlib import Path

from packages.storage import get_connection


def create_project(db_path: Path, name: str) -> dict:
    project_id = str(uuid.uuid4())
    with get_connection(db_path) as conn:
        conn.execute("INSERT INTO projects (id, name) VALUES (?, ?)", (project_id, name))
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row)


def list_projects(db_path: Path) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_project(db_path: Path, project_id: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None


def set_source_filename(db_path: Path, project_id: str, filename: str) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE projects SET source_filename = ?, status = 'ready' WHERE id = ?",
            (filename, project_id),
        )


def delete_project(db_path: Path, project_id: str) -> None:
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def latest_job(db_path: Path, project_id: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    return dict(row) if row else None
