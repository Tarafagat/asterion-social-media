"""Quién decide qué proveedor usar — una sola vez, acá, para que
`apps/worker/app/pipeline/plan_edits.py` no tenga que saber nada de
proveedores concretos. La regla es explícita a propósito: `provider_base_
url` vacío es la única forma de pedir el heurístico sin IA; con una URL
configurada (el default de `app.asterion` ya trae una), siempre se
intenta de verdad, y si falla, falla — nunca cae solo al heurístico
porque el HTTP no respondió. Eso sería silenciar un fallo real detrás de
un resultado que parece haber funcionado."""

from __future__ import annotations

from packages.config import Settings

from .providers import ClipProvider, HeuristicProvider, HttpLLMProvider, ProposalContext


def build_provider(settings: Settings) -> ClipProvider:
    if not settings.provider_base_url.strip():
        return HeuristicProvider()
    return HttpLLMProvider(
        base_url=settings.provider_base_url,
        model=settings.provider_model,
        token=settings.provider_token,
    )


def build_context(settings: Settings) -> ProposalContext:
    return ProposalContext(
        video_type=settings.content_video_type,
        vocabulary=settings.content_vocabulary_list,
        formats=settings.edit_formats_list,
        subtitle_style=settings.edit_subtitle_style,
    )
