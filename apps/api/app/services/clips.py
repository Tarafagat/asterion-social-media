from __future__ import annotations

import json
from pathlib import Path

from packages.storage import get_connection


def list_clips_for_project(db_path: Path, project_id: str) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM clips WHERE project_id = ? ORDER BY created_at ASC", (project_id,)
        ).fetchall()
    out = []
    for r in rows:
        clip = dict(r)
        clip["segments"] = json.loads(clip["segments_json"])
        del clip["segments_json"]
        out.append(clip)
    return out


def get_clip(db_path: Path, clip_id: str) -> dict | None:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM clips WHERE id = ?", (clip_id,)).fetchone()
    if not row:
        return None
    clip = dict(row)
    clip["segments"] = json.loads(clip["segments_json"])
    del clip["segments_json"]
    return clip
