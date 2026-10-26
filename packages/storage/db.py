"""`app.db`: proyectos, jobs y clips. `sqlite3` de la librería estándar, sin
ORM — un plugin de un solo usuario en una sola máquina no necesita un
motor de mapeo objeto-relacional, y suma una dependencia que después hay
que mantener sincronizada con el schema a mano igual.

WAL (`PRAGMA journal_mode=WAL`) porque el request HTTP que crea un job y
el loop del worker que lo procesa conviven en el mismo proceso pero no en
el mismo hilo/tarea — sin WAL, una lectura larga del worker podría
bloquear una escritura corta de la API (o viceversa) con el modo rollback
por default de SQLite.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    source_filename TEXT,
    status          TEXT NOT NULL DEFAULT 'new',  -- new | ready | processing | done | failed
    -- Lo que produce 'Inspeccionar' — liviano, re-probarlo no cuesta
    -- nada, así que vive en la fila del proyecto y no en su propia
    -- carpeta de checkpoint (a diferencia de transcribe/analyze, que sí
    -- cuestan tiempo/dinero real y SÍ necesitan poder saltearse).
    duration_s      REAL,
    width           INTEGER,
    height          INTEGER,
    has_audio       INTEGER,
    -- Avatar grabado (sin IA, sin lip-sync) para componer sobre los
    -- clips de este proyecto — uno por proyecto, reusado por todos sus
    -- clips. Ver packages/media/render.py (avatar_path/avatar_mode).
    avatar_path     TEXT,
    avatar_mode     TEXT NOT NULL DEFAULT 'pip',  -- pip | background
    -- Video FUENTE completo (no un clip corto) con el audio original
    -- reemplazado por una narración nueva generada de un guion — ver
    -- packages/media/dub.py y apps/worker/app/runner.py::
    -- _process_dub_video_job. Un solo resultado por proyecto, el más
    -- reciente pisa al anterior (mismo criterio que avatar_path).
    dubbed_video_path TEXT,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    -- 'pipeline' (las siete etapas completas, de un video fuente nuevo) o
    -- 'clip_edit' (re-renderizar UN clip ya existente con segmentos
    -- editados a mano — ver runner.py). Mismo worker, misma cola, misma
    -- UI de progreso para los dos.
    kind          TEXT NOT NULL DEFAULT 'pipeline',
    payload       TEXT,  -- JSON, solo para kind='clip_edit' (clip_id + segments nuevos)
    stage         TEXT NOT NULL DEFAULT 'queued',
    -- Las siete etapas del pipeline, en orden — 'queued' es el estado
    -- antes de que el worker lo tome. Ver apps/worker/app/runner.py.
    status        TEXT NOT NULL DEFAULT 'queued',  -- queued | running | done | failed
    -- Progreso FINO opcional (0-100) dentro de una etapa que no tiene
    -- sub-pasos propios que reportar por separado — hoy solo lo usa
    -- avatar_generate durante 'sadtalker' (parseado del propio stdout de
    -- SadTalker, ver packages/avatar/sadtalker_runner.py). NULL = usar
    -- el % calculado por posición de etapa (jobs.py::_progress_pct), que
    -- sigue siendo el default para el resto de los jobs.
    progress_pct  INTEGER,
    error         TEXT,
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    started_at    TEXT,
    finished_at   TEXT
);

CREATE TABLE IF NOT EXISTS clips (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id          TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    reason          TEXT,
    layout          TEXT NOT NULL DEFAULT 'vertical',
    subtitle_style  TEXT NOT NULL DEFAULT 'shorts',
    needs_review    INTEGER NOT NULL DEFAULT 0,
    segments_json   TEXT NOT NULL,  -- [{"start_ms":...,"end_ms":...}, ...]
    export_path     TEXT,
    subtitle_path   TEXT,
    rating          INTEGER,  -- 1..5, NULL = todavía sin calificar
    -- Si este clip salió de editar otro (packages/media re-render con
    -- segmentos nuevos), acá queda el id del original — el original
    -- nunca se borra ni se pisa, "editar" siempre crea uno nuevo.
    source_clip_id  TEXT REFERENCES clips(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_clips_project ON clips(project_id);
"""

# Columnas agregadas después de la primera versión del schema — 'CREATE
# TABLE IF NOT EXISTS' no las suma a una base ya creada, así que
# `init_db` las agrega a mano, una vez, si todavía no están. Cada tupla:
# (tabla, columna, definición de ALTER TABLE ... ADD COLUMN).
_MIGRATIONS: list[tuple[str, str, str]] = [
    ("projects", "avatar_path", "TEXT"),
    ("projects", "avatar_mode", "TEXT NOT NULL DEFAULT 'pip'"),
    ("jobs", "kind", "TEXT NOT NULL DEFAULT 'pipeline'"),
    ("jobs", "payload", "TEXT"),
    ("jobs", "progress_pct", "INTEGER"),
    ("projects", "dubbed_video_path", "TEXT"),
    ("clips", "rating", "INTEGER"),
    ("clips", "source_clip_id", "TEXT REFERENCES clips(id) ON DELETE SET NULL"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, column, ddl in _MIGRATIONS:
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
