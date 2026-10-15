from __future__ import annotations

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str


class ProjectOut(BaseModel):
    id: str
    name: str
    source_filename: str | None = None
    status: str
    duration_s: float | None = None
    width: int | None = None
    height: int | None = None
    has_audio: bool | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict) -> "ProjectOut":
        data = dict(row)
        if data.get("has_audio") is not None:
            data["has_audio"] = bool(data["has_audio"])
        return cls.model_validate(data)
