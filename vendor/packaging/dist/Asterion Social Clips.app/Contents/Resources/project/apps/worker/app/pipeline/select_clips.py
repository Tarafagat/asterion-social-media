"""Etapa 5/7: seleccionar. Funde los candidatos de todos los bloques de
`analyze.py` en una sola lista global, sin duplicados — ver
`packages/editorial.merge_plans`. Sin checkpoint propio: es una operación
local, determinística y barata (no vuelve a tocar ffmpeg, whisper ni
ningún proveedor de IA), así que no hace falta poder saltearla — correrla
de nuevo nunca cuesta nada."""

from __future__ import annotations

from packages.ai import ClipPlan
from packages.editorial import merge_plans


def run(source_id: str, block_plans: list[ClipPlan]) -> ClipPlan:
    return merge_plans(source_id, block_plans)
