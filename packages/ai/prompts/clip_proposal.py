"""El prompt que le pide al modelo un `ClipPlan` — nunca código, nunca un
comando, solo el JSON validado por `packages/ai/schemas/plan.py`. El
formato de salida se describe en el prompt mismo (no hay function
calling/tool use acá: el endpoint configurable puede ser cualquier cosa
compatible con el formato chat de OpenAI, incluido un modelo local chico
que no sepa de herramientas) — `http_llm.py` es quien extrae y valida el
JSON de la respuesta de texto.
"""

from __future__ import annotations

from packages.transcription import Transcript

from ..providers.base import ProposalContext

SYSTEM_PROMPT = """Sos un editor de video que encuentra los mejores momentos de una \
transcripción para convertirlos en clips cortos para redes sociales (shorts/clips).

Reglas:
- Devolvé SOLO un objeto JSON, sin texto antes ni después, sin bloques de código markdown.
- Los tiempos (start_ms/end_ms) tienen que ser milisegundos reales de la transcripción que \
te paso — nunca inventes un tiempo que no esté en los segmentos dados.
- Un clip puede tener varios "segments" no contiguos si hace falta saltar una pausa o una \
repetición en el medio de la misma idea.
- "clips" puede estar vacío si de verdad no hay nada rescatable — no inventes un clip \
forzado solo para devolver algo.
- "reason" tiene que explicar en una frase por qué ese momento vale un clip.
- "needs_review" en true si no estás seguro de que el corte quedó bien (un corte ambiguo, \
una idea que podría seguir un poco más, etc.).

Formato exacto de salida:
{"source_id": "...", "clips": [{"title": "...", "segments": [{"start_ms": 0, "end_ms": 0}], \
"reason": "...", "layout": "vertical|horizontal|square", "subtitle_style": "...", \
"needs_review": false}]}
"""


def build_user_prompt(source_id: str, transcript: Transcript, context: ProposalContext) -> str:
    lines = [
        f"source_id: {source_id}",
        f"tipo de contenido: {context.video_type}",
        f"formatos de salida pedidos: {', '.join(context.formats)}",
        f"estilo de subtítulos: {context.subtitle_style}",
        f"duración de clip preferida: entre {context.min_clip_s:.0f}s y {context.max_clip_s:.0f}s",
    ]
    if context.vocabulary:
        lines.append(f"vocabulario técnico del tema (para no transcribir mal términos propios): {', '.join(context.vocabulary)}")
    lines.append("")
    lines.append("Transcripción (cada línea: [inicio_ms-fin_ms] texto):")
    for seg in transcript.segments:
        lines.append(f"[{seg.start_ms}-{seg.end_ms}] {seg.text}")
    return "\n".join(lines)
