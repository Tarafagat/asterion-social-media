"""Etapa 4/7: analizar. Para un video largo, mandar la transcripción
entera en un solo prompt es poco confiable (contexto que se pierde,
modelos con ventana chica) y caro — se parte en bloques con algo de
solapamiento (el final de un bloque se repite al principio del
siguiente) para que una idea que cruza el límite entre dos bloques no
quede cortada a la mitad en los dos. El solapamiento es justamente lo
que genera candidatos duplicados entre bloques — intencional: 'Seleccionar'
(`select_clips.py`) es quien los funde, no acá.

Checkpoint en `analysis/analysis.json`: la llamada a un proveedor de IA
real cuesta tiempo y, según el proveedor, dinero — si ya corrió una vez
para este proyecto, no se vuelve a llamar.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.ai import ClipPlan, ProposalContext, build_provider
from packages.config import Settings
from packages.storage import ProjectLayout
from packages.transcription import Transcript, TranscriptSegment

BLOCK_DURATION_S = 300.0  # 5 minutos — un video corto entero entra en un solo bloque
BLOCK_OVERLAP_S = 20.0


def _block_ranges(duration_s: float) -> list[tuple[float, float]]:
    if duration_s <= 0:
        return [(0.0, 0.0)]
    ranges = []
    start = 0.0
    while start < duration_s:
        block_start = max(0.0, start - BLOCK_OVERLAP_S) if ranges else start
        block_end = min(start + BLOCK_DURATION_S, duration_s)
        ranges.append((block_start, block_end))
        start += BLOCK_DURATION_S
    return ranges


def _slice_transcript(transcript: Transcript, start_s: float, end_s: float) -> Transcript:
    start_ms, end_ms = int(start_s * 1000), int(end_s * 1000)
    segments = [s for s in transcript.segments if s.start_ms >= start_ms and s.end_ms <= end_ms]
    return Transcript(
        language=transcript.language,
        language_probability=transcript.language_probability,
        duration_s=end_s - start_s,
        segments=segments,
    )


def run(layout: ProjectLayout, source_id: str, transcript: Transcript, settings: Settings) -> list[ClipPlan]:
    checkpoint = layout.analysis_json()
    if checkpoint.exists():
        raw = json.loads(checkpoint.read_text(encoding="utf-8"))
        return [ClipPlan.model_validate(p) for p in raw]

    provider = build_provider(settings)
    context = ProposalContext(
        video_type=settings.content_video_type,
        vocabulary=settings.content_vocabulary_list,
        formats=settings.edit_formats_list,
        subtitle_style=settings.edit_subtitle_style,
    )

    plans: list[ClipPlan] = []
    for block_start, block_end in _block_ranges(transcript.duration_s):
        block = _slice_transcript(transcript, block_start, block_end)
        if not block.segments:
            continue
        plans.append(provider.propose_clips(source_id, block, context))

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(
        json.dumps([p.model_dump() for p in plans], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return plans
