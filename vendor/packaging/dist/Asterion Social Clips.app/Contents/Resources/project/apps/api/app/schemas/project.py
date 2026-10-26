from __future__ import annotations

from pydantic import BaseModel, Field


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
    has_avatar: bool = False
    avatar_mode: str = "pip"
    has_dubbed_video: bool = False
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: dict) -> "ProjectOut":
        data = dict(row)
        if data.get("has_audio") is not None:
            data["has_audio"] = bool(data["has_audio"])
        data["has_avatar"] = bool(data.get("avatar_path"))
        data.pop("avatar_path", None)
        data["has_dubbed_video"] = bool(data.get("dubbed_video_path"))
        data.pop("dubbed_video_path", None)
        return cls.model_validate(data)


class AvatarModeIn(BaseModel):
    avatar_mode: str = Field(pattern="^(pip|background)$")
