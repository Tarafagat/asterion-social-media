"""Forma de onda para el editor de clips: una sola imagen PNG ancha del
audio COMPLETO del proyecto (no uno por clip) — los segmentos de un clip
son rangos de tiempo absolutos de ese mismo audio (ver `segments_json`),
así que el frontend recorta/hace zoom sobre esta única imagen con
`background-position` en vez de pedir una imagen nueva por cada corte.

`showwavespic` (filtro nativo de ffmpeg) hace el trabajo — nada de leer
samples PCM a mano ni sumar numpy como dependencia nueva, mismo criterio
que el resto de `packages/media`: shell-out a ffmpeg, no un wrapper.
"""

from __future__ import annotations

from pathlib import Path

from .ffcommon import ensure_parent, run_ffmpeg

PIXELS_PER_SECOND = 20
MAX_WIDTH = 20_000  # una fuente de varias horas no debería generar un PNG gigante
HEIGHT = 120


def generate_waveform_png(audio_path: Path, out_png: Path, *, duration_s: float) -> Path:
    ensure_parent(out_png)
    width = max(400, min(MAX_WIDTH, round(duration_s * PIXELS_PER_SECOND)))
    run_ffmpeg(
        [
            "-i", str(audio_path),
            "-filter_complex",
            f"showwavespic=s={width}x{HEIGHT}:colors=0xf0c04a:split_channels=0",
            "-frames:v", "1",
            "-update", "1",
            str(out_png),
        ],
        timeout=120.0,
    )
    return out_png
