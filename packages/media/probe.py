"""La etapa 'Inspeccionar': duración, resolución, pistas de audio — lo
primero que corre el pipeline sobre cualquier video que se sube, y lo que
decide si las etapas siguientes tienen con qué trabajar (sin pista de
audio, no hay nada que transcribir)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .ffcommon import run_ffprobe


@dataclass(frozen=True)
class MediaInfo:
    duration_s: float
    width: int
    height: int
    has_audio: bool
    audio_channels: int
    video_codec: str
    audio_codec: str

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0


def probe_duration(path: Path) -> float:
    """Duración de cualquier archivo con ffprobe (audio o video) — a
    diferencia de `probe()`, no exige una pista de video, así que sirve
    para un .wav/.mp3 suelto (ver packages/media/dub.py, que necesita la
    duración de un audio generado por TTS, sin pista de video)."""
    out = run_ffprobe(["-print_format", "json", "-show_format", str(path)])
    data = json.loads(out)
    return float(data.get("format", {}).get("duration") or 0.0)


def probe(path: Path) -> MediaInfo:
    out = run_ffprobe(
        [
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    data = json.loads(out)

    video_stream = next((s for s in data["streams"] if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in data["streams"] if s.get("codec_type") == "audio"), None)

    if video_stream is None:
        raise ValueError(f"{path} no tiene ninguna pista de video — ¿es realmente un archivo de video?")

    duration = float(data.get("format", {}).get("duration") or video_stream.get("duration") or 0.0)

    return MediaInfo(
        duration_s=duration,
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        has_audio=audio_stream is not None,
        audio_channels=int(audio_stream.get("channels", 0)) if audio_stream else 0,
        video_codec=video_stream.get("codec_name", ""),
        audio_codec=audio_stream.get("codec_name", "") if audio_stream else "",
    )
