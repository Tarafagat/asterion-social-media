"""Etapa 2/7: extraer el audio. Checkpoint: si `audio/audio.wav` ya
existe, no se vuelve a correr ffmpeg sobre el mismo video — ver
`ProjectLayout.extracted_audio()`."""

from __future__ import annotations

from pathlib import Path

from packages.media import extract_audio
from packages.storage import ProjectLayout


def run(layout: ProjectLayout, source_path: Path) -> Path:
    out = layout.extracted_audio()
    if out.exists():
        return out
    return extract_audio(source_path, out)
