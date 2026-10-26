"""La forma exacta del plan que un proveedor de IA (o el heurístico, sin
IA — ver `packages/ai/providers/heuristic.py`) tiene que devolver. Un
`Clip` puede tener CERO `clips` en total (un video sin nada rescatable,
real y esperado, no un error) y cada `Clip` puede tener VARIOS
`segments` no contiguos (saltar una pausa/una repetición en el medio del
mismo clip).

Esto es lo único que el modelo devuelve — nunca un comando, nunca una
ruta de archivo, nunca código. `validate_edits()` (ver
`apps/worker/app/pipeline/validate.py`) confirma que cada tiempo cae
adentro de la duración real del video antes de que `render.py` toque un
solo fotograma: un modelo no necesita (ni puede) ejecutar nada por su
cuenta.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

VALID_LAYOUTS = {"vertical", "horizontal", "square"}


class ClipSegment(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int

    @field_validator("end_ms")
    @classmethod
    def _end_after_start(cls, v: int, info) -> int:
        start = info.data.get("start_ms", 0)
        if v <= start:
            raise ValueError(f"end_ms ({v}) tiene que ser mayor que start_ms ({start})")
        return v


class Clip(BaseModel):
    title: str
    segments: list[ClipSegment] = Field(min_length=1)
    reason: str = ""
    layout: str = "vertical"
    subtitle_style: str = "shorts"
    needs_review: bool = False

    @field_validator("layout")
    @classmethod
    def _valid_layout(cls, v: str) -> str:
        if v not in VALID_LAYOUTS:
            raise ValueError(f"layout {v!r} desconocido — tiene que ser uno de {sorted(VALID_LAYOUTS)}")
        return v

    def total_duration_ms(self) -> int:
        return sum(s.end_ms - s.start_ms for s in self.segments)


class ClipPlan(BaseModel):
    source_id: str
    clips: list[Clip] = Field(default_factory=list)
