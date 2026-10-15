"""La etapa 'Seleccionar': un video largo se analiza en bloques (ver
`apps/worker/app/pipeline/analyze.py`) para no perder contexto cuando el
transcript entero no entra en una sola llamada al modelo — eso deja
candidatos que se solapan o se repiten en el borde de dos bloques
consecutivos. Acá se funden en una sola lista global, sin duplicados.

Deliberadamente simple: comparar el solapamiento de los TIEMPOS de los
segmentos, no el contenido semántico — dos clips que cubren básicamente
el mismo rango del video fuente son, por definición, el mismo momento
visto desde dos bloques distintos, sin necesidad de comparar texto.
"""

from __future__ import annotations

from packages.ai.schemas import Clip, ClipPlan


def _span(clip: Clip) -> tuple[int, int]:
    starts = [s.start_ms for s in clip.segments]
    ends = [s.end_ms for s in clip.segments]
    return min(starts), max(ends)


def _overlap_ratio(a: tuple[int, int], b: tuple[int, int]) -> float:
    overlap = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    shorter = min(a[1] - a[0], b[1] - b[0])
    if shorter <= 0:
        return 0.0
    return overlap / shorter


def dedup_by_overlap(clips: list[Clip], *, overlap_threshold: float = 0.6) -> list[Clip]:
    # Los clips más largos primero: si dos se solapan, se prefiere quedarse
    # con la versión más completa en vez de la que un bloque recortó más
    # corta por quedar cerca de su propio borde.
    ordered = sorted(clips, key=lambda c: c.total_duration_ms(), reverse=True)
    kept: list[Clip] = []
    kept_spans: list[tuple[int, int]] = []

    for clip in ordered:
        span = _span(clip)
        if any(_overlap_ratio(span, k) >= overlap_threshold for k in kept_spans):
            continue
        kept.append(clip)
        kept_spans.append(span)

    # De vuelta en orden cronológico — el orden de "más largo primero" fue
    # solo para decidir qué descartar, no el orden en que se muestran.
    return sorted(kept, key=lambda c: _span(c)[0])


def merge_plans(source_id: str, plans: list[ClipPlan], *, overlap_threshold: float = 0.6) -> ClipPlan:
    all_clips = [clip for plan in plans for clip in plan.clips]
    return ClipPlan(source_id=source_id, clips=dedup_by_overlap(all_clips, overlap_threshold=overlap_threshold))
