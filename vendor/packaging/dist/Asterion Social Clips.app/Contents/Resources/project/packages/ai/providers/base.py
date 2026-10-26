"""El contrato que cualquier proveedor de 'proponer clips' cumple — uno
local sin IA (`heuristic.py`, siempre disponible, cero red, cero costo) y
uno que de verdad habla con un modelo (`http_llm.py`, necesita
`provider_base_url`/`provider_model` configurados). `apps/worker/app/
pipeline/plan_edits.py` elige cuál usar; el resto del pipeline no sabe ni
le importa cuál fue.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from packages.ai.schemas import ClipPlan
from packages.transcription import Transcript


@dataclass(frozen=True)
class ProposalContext:
    video_type: str = "generic"
    vocabulary: list[str] = field(default_factory=list)
    formats: list[str] = field(default_factory=lambda: ["vertical"])
    subtitle_style: str = "shorts"
    # Rango de duración que un clip "útil" para shorts/clips suele tener
    # — el heurístico lo usa para agrupar; el prompt al LLM lo incluye
    # como instrucción, no como validación dura (el modelo puede, con
    # justificación, proponer algo más largo).
    min_clip_s: float = 15.0
    max_clip_s: float = 90.0


class ClipProvider(ABC):
    @abstractmethod
    def propose_clips(self, source_id: str, transcript: Transcript, context: ProposalContext) -> ClipPlan:
        """Nunca debe devolver un ClipPlan con tiempos fuera de
        transcript.duration_s — eso lo exige el tipo, no la validación:
        quien implemente un proveedor nuevo es responsable de no inventar
        tiempos que `validate.py` tenga que descartar después."""
        raise NotImplementedError
