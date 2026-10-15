"""El layout de carpetas de UN proyecto, bajo `<data_dir>/projects/<id>/`.
Cada subcarpeta es, a la vez, dónde vive el resultado de una etapa del
pipeline Y el checkpoint que permite saltearla la próxima vez: si
`transcripts/<id>.json` ya existe, `transcribe.py` no vuelve a correr
faster-whisper sobre el mismo audio — no son dos mecanismos (checkpoint +
almacenamiento), es uno solo. Separado de `packages/config` a propósito:
acá no hay nada que dependa de Asterion ni de variables de entorno, solo
de un `Path` base — así se puede probar con un directorio temporal
cualquiera sin levantar el plugin entero.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectLayout:
    data_dir: Path
    project_id: str

    @property
    def root(self) -> Path:
        return self.data_dir / "projects" / self.project_id

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def audio_dir(self) -> Path:
        return self.root / "audio"

    @property
    def transcripts_dir(self) -> Path:
        return self.root / "transcripts"

    @property
    def analysis_dir(self) -> Path:
        return self.root / "analysis"

    @property
    def edit_plans_dir(self) -> Path:
        return self.root / "edit-plans"

    @property
    def previews_dir(self) -> Path:
        return self.root / "previews"

    @property
    def exports_dir(self) -> Path:
        return self.root / "exports"

    def ensure(self) -> None:
        """Crea las siete subcarpetas si no existen. Llamarlo es barato e
        idempotente — cada etapa del pipeline lo llama antes de escribir
        en vez de asumir que una etapa anterior ya lo hizo, para que
        ninguna etapa dependa en silencio del orden en que corrieron las
        demás."""
        for d in (
            self.source_dir,
            self.audio_dir,
            self.transcripts_dir,
            self.analysis_dir,
            self.edit_plans_dir,
            self.previews_dir,
            self.exports_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def source_video(self, filename: str) -> Path:
        return self.source_dir / filename

    def extracted_audio(self) -> Path:
        # Un solo archivo de audio por proyecto (mono 16kHz, lo que pide
        # faster-whisper) — si el video fuente cambia, es un proyecto
        # nuevo, no un re-extract sobre el mismo id.
        return self.audio_dir / "audio.wav"

    def transcript_json(self) -> Path:
        return self.transcripts_dir / "transcript.json"

    def analysis_json(self) -> Path:
        return self.analysis_dir / "analysis.json"

    def edit_plan_json(self) -> Path:
        return self.edit_plans_dir / "plan.json"

    def clip_export(self, clip_id: str, suffix: str = "mp4") -> Path:
        return self.exports_dir / f"{clip_id}.{suffix}"

    def clip_subtitle(self, clip_id: str, suffix: str = "srt") -> Path:
        return self.exports_dir / f"{clip_id}.{suffix}"
