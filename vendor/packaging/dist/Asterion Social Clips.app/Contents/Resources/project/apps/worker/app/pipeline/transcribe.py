"""Etapa 3/7: transcribir. La más cara en tiempo de CPU de todo el
pipeline — el checkpoint acá es el que de verdad importa: si
`transcripts/transcript.json` ya existe, se lee directo, nunca se vuelve
a correr faster-whisper sobre el mismo audio."""

from __future__ import annotations

import json
from pathlib import Path

from packages.storage import ProjectLayout
from packages.transcription import Transcript, transcribe


def run(layout: ProjectLayout, audio_path: Path, *, model_size: str, language: str = "") -> Transcript:
    checkpoint = layout.transcript_json()
    if checkpoint.exists():
        return Transcript.from_dict(json.loads(checkpoint.read_text(encoding="utf-8")))

    result = transcribe(audio_path, model_size=model_size, language=language or None)
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return result
