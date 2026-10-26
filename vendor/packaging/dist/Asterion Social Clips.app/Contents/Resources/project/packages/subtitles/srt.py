"""`.srt` plano — para quien prefiera subirlo como pista separada en vez
de quemado en el video (YouTube, entre otros, acepta subtítulos como
archivo aparte). Los tiempos que recibe ya tienen que estar relativos al
arranque del CLIP, no del video fuente — ver `_shift_to_clip_relative`
en `apps/worker/app/pipeline/render.py`, que es quien hace esa resta
antes de llamar acá."""

from __future__ import annotations

from pathlib import Path

from packages.transcription import TranscriptSegment


def _timestamp(ms: int) -> str:
    ms = max(0, ms)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, millis = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def write_srt(segments: list[TranscriptSegment], out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_timestamp(seg.start_ms)} --> {_timestamp(seg.end_ms)}")
        lines.append(seg.text.strip())
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
