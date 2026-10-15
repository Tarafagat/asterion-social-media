from __future__ import annotations

from pydantic import BaseModel


class JobOut(BaseModel):
    id: str
    project_id: str
    stage: str
    status: str
    progress_pct: int
    error: str | None = None
    created_at: str
    updated_at: str
    started_at: str | None = None
    finished_at: str | None = None
