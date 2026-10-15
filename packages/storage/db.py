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
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    stage         TEXT NOT NULL DEFAULT 'queued',
    -- Las siete etapas del pipeline, en orden — 'queued' es el estado
    -- antes de que el worker lo tome. Ver apps/worker/app/runner.py.
    status        TEXT NOT NULL DEFAULT 'queued',  -- queued | running | done | failed
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
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
CREATE INDEX IF NOT EXISTS idx_clips_project ON clips(project_id);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
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
