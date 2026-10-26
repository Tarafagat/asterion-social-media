"""Etapa 6/7: planificar. De la selección global a la lista final de
`PlannedClip` — uno por combinación (clip, formato de salida) — y se
persiste en `edit-plans/plan.json`: es el último documento 100% de
texto/JSON antes de `render.py`, el que de verdad define qué se va a
cortar. Igual que `select_clips`, es barata y determinística: el
checkpoint existe para poder INSPECCIONAR el plan final antes de
renderizar (y para que la API tenga qué mostrar en la UI), no porque
recalcularla sea costoso."""

from __future__ import annotations

import json

from packages.ai import ClipPlan
from packages.editorial import PlannedClip, plan_edits
from packages.storage import ProjectLayout


def _clamp_to_duration(planned: list[PlannedClip], duration_s: float) -> list[PlannedClip]:
    """Un proveedor de IA (sobre todo uno chico/local) a veces redondea
    mal o alucina un tiempo apenas fuera de rango — nunca se le confía
    ciegamente: todo segmento se recorta a la duración real del video
    fuente antes de que `render.py` vea el plan, y un clip que queda sin
    ningún segmento válido se descarta en vez de intentar renderizar un
    archivo de cero segundos."""
    duration_ms = int(duration_s * 1000)
    clamped: list[PlannedClip] = []
    for clip in planned:
        valid_segments = []
        for seg in clip.segments:
            start_ms = max(0, min(seg["start_ms"], duration_ms))
            end_ms = max(0, min(seg["end_ms"], duration_ms))
            if end_ms > start_ms:
                valid_segments.append({"start_ms": start_ms, "end_ms": end_ms})
        if valid_segments:
            clip.segments = valid_segments
            clamped.append(clip)
    return clamped


def run(layout: ProjectLayout, plan: ClipPlan, formats: list[str], *, duration_s: float) -> list[PlannedClip]:
    planned = plan_edits(plan, formats)
    planned = _clamp_to_duration(planned, duration_s)
    checkpoint = layout.edit_plan_json()
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        json.dumps([p.model_dump() for p in planned], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return planned
