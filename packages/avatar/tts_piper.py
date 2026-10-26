"""Texto -> voz local con Piper (sin nube, sin API key) — la mitad
'barata' del pipeline de Avatar IA / doblaje de video. La otra mitad
(animar la cara con el audio) es SadTalker, que corre aislado en su
propio venv (ver sadtalker_runner.py); Piper en cambio instala limpio en
este mismo venv (onnxruntime + numpy, nada que choque con faster-
whisper/av), así que acá sí se usa directo, sin subprocess.

Masculina/femenina son el mismo modelo multi-hablante
(es_ES-sharvard-medium, 2 locutores embebidos, M=0/F=1) — un solo
archivo cubre las dos, en vez de manejar dos modelos de acentos
distintos. Confirmado con un análisis de F0 real sobre una muestra de
cada una (no por el nombre del modelo, que no dice nada confiable del
género): masculina ≈110Hz, femenina ≈192Hz — ambos dentro del rango
típico esperado para cada caso."""

from __future__ import annotations

import shutil
import tempfile
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from piper import PiperVoice
from piper.config import SynthesisConfig
from piper.phonemize_espeak import ESPEAK_DATA_DIR

VOICES_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "voices"


def _short_espeak_data_dir() -> Path:
    """El binding compilado de espeak-ng (espeakbridge.so/.pyd) copia la
    ruta a un buffer fijo de ~160 caracteres: toda ruta más larga se
    trunca y cae en silencio al path de la máquina de CI que compiló el
    wheel ('/Users/runner/work/piper1-gpl/...' o su equivalente en
    Windows), con un error que no delata la causa real. Cualquier
    instalación empaquetada como app de escritorio queda por encima de
    ese límite solo por lo anidada que es la ruta — no es un caso borde,
    pasa siempre. El workaround: una copia corta y estable en la carpeta
    temporal del sistema, bien por debajo del límite — una copia y no un
    symlink porque en Windows crear symlinks pide privilegios de admin
    (Modo desarrollador), algo que no se le puede pedir a quien solo
    quiere abrir la app."""
    cache_dir = Path(tempfile.gettempdir()) / "asterion-espeak-ng-data"
    marker = cache_dir / ".source"
    source = str(ESPEAK_DATA_DIR.resolve())
    if marker.is_file() and marker.read_text(encoding="utf-8") == source:
        return cache_dir
    if cache_dir.is_symlink() or cache_dir.is_file():
        cache_dir.unlink()
    elif cache_dir.exists():
        shutil.rmtree(cache_dir)
    shutil.copytree(ESPEAK_DATA_DIR, cache_dir)
    marker.write_text(source, encoding="utf-8")
    return cache_dir


@dataclass(frozen=True)
class VoiceOption:
    model_id: str
    speaker_id: int | None
    label: str


# Un modelo multi-hablante (es_ES-sharvard-medium, descargado con
# `python -m piper.download_voices es_ES-sharvard-medium --data-dir
# models/voices`) alcanza para las dos opciones — agregar una entrada
# acá después de confirmar (con F0, no a ojo) que corresponde al género
# que dice.
AVAILABLE_VOICES: dict[str, VoiceOption] = {
    "es-masculina": VoiceOption("es_ES-sharvard-medium", 0, "Español — masculina"),
    "es-femenina": VoiceOption("es_ES-sharvard-medium", 1, "Español — femenina"),
}
DEFAULT_VOICE = "es-femenina"


class VoiceNotFoundError(RuntimeError):
    pass


@lru_cache(maxsize=4)
def _load_model(model_id: str) -> PiperVoice:
    model_path = VOICES_DIR / f"{model_id}.onnx"
    if not model_path.exists():
        raise VoiceNotFoundError(
            f"el modelo de voz {model_id!r} no está descargado — "
            f"'python -m piper.download_voices {model_id} --data-dir {VOICES_DIR}'"
        )
    return PiperVoice.load(str(model_path), espeak_data_dir=str(_short_espeak_data_dir()))


def synthesize(text: str, out_wav: Path, *, voice_id: str = DEFAULT_VOICE) -> Path:
    option = AVAILABLE_VOICES.get(voice_id)
    if option is None:
        raise VoiceNotFoundError(f"voz {voice_id!r} desconocida — opciones: {list(AVAILABLE_VOICES)}")

    out_wav.parent.mkdir(parents=True, exist_ok=True)
    voice = _load_model(option.model_id)
    syn_config = SynthesisConfig(speaker_id=option.speaker_id) if option.speaker_id is not None else None
    with wave.open(str(out_wav), "wb") as wav_file:
        voice.synthesize_wav(text, wav_file, syn_config=syn_config)
    return out_wav
