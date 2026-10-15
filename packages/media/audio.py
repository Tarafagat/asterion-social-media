"""La etapa 'Transcribir' empieza acá: extraer el audio a mono 16kHz
PCM — exactamente lo que `faster-whisper` espera (ver `packages/
transcription`), para no hacerle a Whisper leer el video entero
(contenedor + pistas de video) cada vez que haya que re-transcribir."""

from __future__ import annotations

from pathlib import Path

from .ffcommon import ensure_parent, run_ffmpeg

WHISPER_SAMPLE_RATE = 16_000


def extract_audio(source: Path, out_wav: Path) -> Path:
    ensure_parent(out_wav)
    run_ffmpeg(
        [
            "-i", str(source),
            "-vn",
            "-ar", str(WHISPER_SAMPLE_RATE),
            "-ac", "1",
            "-acodec", "pcm_s16le",
            str(out_wav),
        ]
    )
    return out_wav
