"""El proveedor que SIEMPRE funciona, sin configurar nada: agrupa la
transcripción en bloques de duración razonable, cortando en las pausas
naturales del habla — nunca entiende de QUÉ habla el video. Dos razones
para que exista, las dos reales:

  1. Deja probar el pipeline completo (transcribir → seleccionar →
     planificar → renderizar → validar) de punta a punta sin necesitar
     ningún proveedor de IA configurado — justo lo que se usó para
     verificar este plugin en vivo antes de escribir un cliente HTTP que
     nadie podía probar todavía contra un modelo real.
  2. Es honesto consigo mismo: cada clip que propone sale con
     `needs_review=True` y una razón que dice exactamente lo que hizo
     ("cortado por pausa, sin análisis de contenido") — nunca se hace
     pasar por una selección editorial que no hizo.
"""

from __future__ import annotations

from packages.ai.schemas import Clip, ClipPlan, ClipSegment
from packages.transcription import Transcript, TranscriptSegment

from .base import ClipProvider, ProposalContext

# Una pausa de más de esto entre el fin de un segmento y el arranque del
# siguiente cuenta como un corte natural — lo suficientemente largo para
# ser una pausa real de alguien hablando, no solo el espacio entre
# palabras que faster-whisper ya separa en segmentos distintos.
PAUSE_THRESHOLD_MS = 600


class HeuristicProvider(ClipProvider):
    def propose_clips(self, source_id: str, transcript: Transcript, context: ProposalContext) -> ClipPlan:
        clips: list[Clip] = []
        bucket: list[TranscriptSegment] = []

        def flush() -> None:
            if not bucket:
                return
            duration_s = (bucket[-1].end_ms - bucket[0].start_ms) / 1000.0
            if duration_s < context.min_clip_s:
                return  # muy corto para ser un clip útil — se descarta, no se fuerza
            text = " ".join(s.text for s in bucket).strip()
            title = _title_from_text(text)
            clips.append(
                Clip(
                    title=title,
                    segments=[ClipSegment(start_ms=bucket[0].start_ms, end_ms=bucket[-1].end_ms)],
                    reason="Cortado por pausa de habla, sin análisis de contenido (proveedor heurístico, sin IA configurada).",
                    layout=context.formats[0] if context.formats else "vertical",
                    subtitle_style=context.subtitle_style,
                    needs_review=True,
                )
            )

        for i, seg in enumerate(transcript.segments):
            bucket.append(seg)
            duration_s = (seg.end_ms - bucket[0].start_ms) / 1000.0
            is_last = i == len(transcript.segments) - 1
            gap_ms = (
                transcript.segments[i + 1].start_ms - seg.end_ms
                if not is_last
                else PAUSE_THRESHOLD_MS + 1
            )
            at_pause = gap_ms >= PAUSE_THRESHOLD_MS
            if is_last or (at_pause and duration_s >= context.min_clip_s) or duration_s >= context.max_clip_s:
                flush()
                bucket = []

        return ClipPlan(source_id=source_id, clips=clips)


def _title_from_text(text: str, max_words: int = 8) -> str:
    words = text.split()
    title = " ".join(words[:max_words])
    if len(words) > max_words:
        title += "…"
    return title or "Clip sin título"
