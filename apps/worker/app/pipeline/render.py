"""Etapa 7/7 (antes de Validar): renderizar. Por cada `PlannedClip`:
recortar+encuadrar+subtitular con `packages/media.render_clip`. La parte
no trivial es el REBASADO de tiempos: el plan guarda los segmentos en
tiempo ABSOLUTO del video fuente (así los valida `validate.py` contra la
duración real), pero el .mp4 resultante arranca en 0 — si el clip junta
dos segmentos no contiguos, los subtítulos del segundo tienen que
empezar donde terminó el primero en el CLIP, no donde estaban en el
video original.
"""

from __future__ import annotations

from packages.editorial import PlannedClip
from packages.media import LAYOUT_DIMENSIONS, RenderSegment, render_clip
from packages.storage import ProjectLayout
from packages.subtitles import load_style, write_ass
from packages.transcription import Transcript, TranscriptSegment


def _clip_relative_segments(transcript: Transcript, abs_segments: list[dict]) -> list[TranscriptSegment]:
    out: list[TranscriptSegment] = []
    clip_cursor_ms = 0
    for abs_seg in abs_segments:
        start_ms, end_ms = abs_seg["start_ms"], abs_seg["end_ms"]
        shift = clip_cursor_ms - start_ms
        for seg in transcript.segments:
            if seg.start_ms >= start_ms and seg.end_ms <= end_ms:
                out.append(
                    TranscriptSegment(
                        start_ms=seg.start_ms + shift,
                        end_ms=seg.end_ms + shift,
                        text=seg.text,
                        words=[
                            type(w)(w.start_ms + shift, w.end_ms + shift, w.word)
                            for w in seg.words
                        ],
                    )
                )
        clip_cursor_ms += end_ms - start_ms
    return out


def run(
    layout: ProjectLayout,
    source_path,
    clip: PlannedClip,
    transcript: Transcript,
    *,
    avatar_path=None,
    avatar_mode: str = "pip",
):
    render_segments = [RenderSegment(s["start_ms"], s["end_ms"]) for s in clip.segments]

    subtitle_path = None
    clip_segments = _clip_relative_segments(transcript, clip.segments)
    if clip_segments:
        style = load_style(clip.subtitle_style)
        video_w, video_h = LAYOUT_DIMENSIONS.get(clip.layout, LAYOUT_DIMENSIONS["vertical"])
        subtitle_path = write_ass(
            clip_segments, style, layout.exports_dir / f"{clip.id}.ass",
            video_w=video_w, video_h=video_h,
        )

    out_path = layout.clip_export(clip.id)
    render_clip(
        source_path,
        render_segments,
        out_path,
        layout=clip.layout,
        subtitle_ass=subtitle_path,
        avatar_path=avatar_path,
        avatar_mode=avatar_mode,
    )
    return out_path, subtitle_path
