"""Etapa 1/7: Inspeccionar. Lo primero que corre sobre cualquier fuente
subida — si no tiene pista de audio, el job falla acá mismo, antes de
gastar tiempo en nada más."""

from __future__ import annotations

from pathlib import Path

from packages.media import MediaInfo, probe


def run(source_path: Path) -> MediaInfo:
    info = probe(source_path)
    if not info.has_audio:
        raise ValueError(
            f"{source_path.name} no tiene ninguna pista de audio — no hay nada que transcribir."
        )
    return info
