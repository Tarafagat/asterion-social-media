"""La etapa 'Transcribir', de verdad: `faster-whisper` corriendo local,
con tiempos por palabra. Probado en vivo en esta máquina (macOS/arm64) —
ver el pin de `av==18.1.0` en `apps/api/requirements.txt`, sin el cual
`faster_whisper.audio.decode_audio` revienta con un `TypeError` (la
versión más nueva de PyAV le sacó el parámetro `metadata_errors` que
`faster-whisper` 1.2.1 todavía le pasa a `av.open()`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

# Un modelo por tamaño, cacheado en el proceso — cargarlo tarda (de
# fracciones de segundo para 'tiny' a varios segundos para 'medium'+), y
# el worker procesa jobs de a uno, en el mismo proceso: no tiene sentido
# recargarlo en cada job si el tamaño configurado no cambió.
_model_cache: dict[str, WhisperModel] = {}


def _get_model(model_size: str) -> WhisperModel:
    if model_size not in _model_cache:
        _model_cache[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _model_cache[model_size]


@dataclass(frozen=True)
class TranscriptWord:
    start_ms: int
    end_ms: int
    word: str

    def to_dict(self) -> dict[str, Any]:
        return {"start_ms": self.start_ms, "end_ms": self.end_ms, "word": self.word}

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TranscriptWord":
        return TranscriptWord(d["start_ms"], d["end_ms"], d["word"])


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    words: list[TranscriptWord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "words": [w.to_dict() for w in self.words],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "TranscriptSegment":
        return TranscriptSegment(
            d["start_ms"], d["end_ms"], d["text"],
            [TranscriptWord.from_dict(w) for w in d.get("words", [])],
        )


@dataclass(frozen=True)
class Transcript:
    language: str
    language_probability: float
    duration_s: float
    segments: list[TranscriptSegment]

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "language_probability": self.language_probability,
            "duration_s": self.duration_s,
            "segments": [s.to_dict() for s in self.segments],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Transcript":
        return Transcript(
            d["language"], d["language_probability"], d["duration_s"],
            [TranscriptSegment.from_dict(s) for s in d.get("segments", [])],
        )

    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments)


def transcribe(audio_path: Path, *, model_size: str = "small", language: str | None = None) -> Transcript:
    """`language=None` deja que Whisper detecte el idioma del primer
    bloque de audio solo — `language="en"`/`"es"`/etc. lo fuerza, lo que
    tanto acelera (se salta la detección) como mejora la precisión
    cuando ya se sabe de antemano (ver `content_language` en
    `packages/config`, pensado justo para esto)."""
    model = _get_model(model_size)
    raw_segments, info = model.transcribe(
        str(audio_path),
        word_timestamps=True,
        language=language or None,
    )

    segments: list[TranscriptSegment] = []
    for seg in raw_segments:
        words = [
            TranscriptWord(start_ms=round(w.start * 1000), end_ms=round(w.end * 1000), word=w.word)
            for w in (seg.words or [])
        ]
        segments.append(
            TranscriptSegment(
                start_ms=round(seg.start * 1000),
                end_ms=round(seg.end * 1000),
                text=seg.text.strip(),
                words=words,
            )
        )

    return Transcript(
        language=info.language,
        language_probability=info.language_probability,
        duration_s=info.duration,
        segments=segments,
    )
