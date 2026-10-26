from __future__ import annotations

from pydantic import BaseModel, Field


class ClipOut(BaseModel):
    id: str
    project_id: str
    job_id: str
    title: str
    reason: str | None = None
    layout: str
    subtitle_style: str
    needs_review: bool
    segments: list[dict]
    export_path: str | None = None
    subtitle_path: str | None = None
    rating: int | None = None
    source_clip_id: str | None = None
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> "ClipOut":
        data = dict(row)
        data["needs_review"] = bool(data["needs_review"])
        return cls.model_validate(data)


class RatingIn(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)


class EditSegmentIn(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)


class EditClipIn(BaseModel):
    segments: list[EditSegmentIn]
    avatar_enabled: bool = False
