"""El proveedor que de verdad llama a un modelo — local (ollama, LM
Studio, vLLM, lo que sea que hable el dialecto chat de OpenAI en
`provider_base_url`) o remoto. Sin credenciales/endpoint configurados
(los defaults de `app.asterion` apuntan a un ollama local típico, pero
eso no significa que haya uno corriendo), esto falla con un error de
conexión claro — nunca cae en silencio al heurístico ni inventa una
respuesta. Quien decide ese fallback es `apps/worker/app/pipeline/
plan_edits.py`, con el usuario al tanto, no este cliente.
"""

from __future__ import annotations

import json
import re

import httpx

from packages.ai.schemas import ClipPlan
from packages.transcription import Transcript

from .base import ClipProvider, ProposalContext
from ..prompts import SYSTEM_PROMPT, build_user_prompt

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


class ProviderCallError(RuntimeError):
    """El proveedor respondió, pero no con algo usable — nunca se traga
    en silencio, siempre sube hasta el job como un fallo real de esa
    etapa (ver apps/worker/app/pipeline/plan_edits.py)."""


class HttpLLMProvider(ClipProvider):
    def __init__(self, base_url: str, model: str, token: str = "", *, timeout: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.token = token
        self.timeout = timeout

    def propose_clips(self, source_id: str, transcript: Transcript, context: ProposalContext) -> ClipPlan:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(source_id, transcript, context)},
            ],
            "temperature": 0.2,
        }

        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise ProviderCallError(
                f"no pude conectarme a {self.base_url} — ¿está corriendo el servidor del modelo? ({exc})"
            ) from exc

        if resp.status_code != 200:
            raise ProviderCallError(
                f"{self.base_url} respondió {resp.status_code}: {resp.text[:500]}"
            )

        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderCallError(
                f"la respuesta de {self.base_url} no tiene la forma esperada (choices[0].message.content): {resp.text[:500]}"
            ) from exc

        raw_json = _extract_json(content)
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ProviderCallError(
                f"el modelo no devolvió JSON válido: {exc}\n--- respuesta cruda ---\n{content[:1000]}"
            ) from exc

        try:
            return ClipPlan.model_validate(data)
        except Exception as exc:  # pydantic.ValidationError, pero no importamos solo para el tipo
            raise ProviderCallError(
                f"el JSON del modelo no cumple el esquema de ClipPlan: {exc}"
            ) from exc


def _extract_json(content: str) -> str:
    """Un modelo chico, aunque el prompt le pida 'solo JSON', a veces
    igual lo envuelve en un bloque ```json ... ``` — se lo saca antes de
    intentar parsear en vez de fallar por una cerca de markdown que ni
    es parte del contenido real."""
    content = content.strip()
    m = _JSON_FENCE_RE.search(content)
    if m:
        return m.group(1)
    return content
