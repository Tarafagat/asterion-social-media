"""Etapa final: validar. Comprobaciones técnicas (el .mp4 existe, tiene
duración, ffprobe lo puede leer — un render que terminó con código 0 no
es necesariamente un archivo usable) y la señal editorial que ya venía
cargando el clip desde que lo propuso la IA (`needs_review`) — acá no se
inventa criterio editorial nuevo, solo se la deja visible junto al
resultado técnico, para que la UI pueda mostrar ambas cosas juntas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.editorial import PlannedClip
from packages.media import probe


@dataclass(frozen=True)
class ValidationResult:
    clip_id: str
    ok: bool
    needs_review: bool
    issues: list[str]


def run(clip: PlannedClip, export_path: Path) -> ValidationResult:
    issues: list[str] = []

    if not export_path.exists():
        issues.append(f"el archivo exportado {export_path.name} no existe")
        return ValidationResult(clip.id, ok=False, needs_review=clip.needs_review, issues=issues)

    try:
        info = probe(export_path)
    except Exception as exc:
        issues.append(f"ffprobe no pudo leer el archivo exportado: {exc}")
        return ValidationResult(clip.id, ok=False, needs_review=clip.needs_review, issues=issues)

    expected_s = sum(s["end_ms"] - s["start_ms"] for s in clip.segments) / 1000.0
    tolerance_s = 1.0  # el re-encode de concat/subtítulos puede variar unos cuadros
    if abs(info.duration_s - expected_s) > tolerance_s:
        issues.append(
            f"duración exportada ({info.duration_s:.1f}s) difiere de la planificada ({expected_s:.1f}s) más de lo esperable"
        )
    if not info.has_audio:
        issues.append("el .mp4 exportado no tiene pista de audio")

    return ValidationResult(clip.id, ok=not issues, needs_review=clip.needs_review, issues=issues)
