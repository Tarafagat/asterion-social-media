"""Lo que produce 'Planificar': de un `Clip` ya seleccionado (ver
`candidates.py`) a uno o más `PlannedClip` — uno por cada formato de
salida pedido (`edit_formats`, ej. vertical Y horizontal del mismo
momento), cada uno con su propio id listo para pasarle a `render.py`."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from packages.ai.schemas import Clip, ClipPlan


class PlannedClip(BaseModel):
    id: str
    title: str
    segments: list[dict]  # [{"start_ms":int,"end_ms":int}, ...] — serializable tal cual
    reason: str
    layout: str
    subtitle_style: str
    needs_review: bool


def plan_edits(plan: ClipPlan, formats: list[str]) -> list[PlannedClip]:
    formats = formats or ["vertical"]
    planned: list[PlannedClip] = []
    for clip in plan.clips:
        for fmt in formats:
            planned.append(_expand(clip, fmt))
    return planned


def _expand(clip: Clip, layout: str) -> PlannedClip:
    return PlannedClip(
        id=str(uuid.uuid4()),
        title=clip.title,
        segments=[{"start_ms": s.start_ms, "end_ms": s.end_ms} for s in clip.segments],
        reason=clip.reason,
        layout=layout,
        subtitle_style=clip.subtitle_style,
        needs_review=clip.needs_review,
    )
