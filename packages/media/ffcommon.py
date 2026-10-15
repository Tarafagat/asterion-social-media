"""Lo que `probe.py`/`audio.py`/`render.py` comparten: cómo correr
`ffmpeg`/`ffprobe` de verdad — shell-out, no un wrapper Python
(`ffmpeg-python` u otro) — mismo criterio que `asterion-core/internal/
dbbackup` con `pg_dump`: cero dependencias nuevas más allá del binario
que de todos modos hace falta tener instalado, y el mensaje de error, si
`ffmpeg` no está, lo dice así en vez de fallar con un traceback de un
paquete Python que ni se llegó a usar.
"""

from __future__ import annotations

import functools
import shutil
import subprocess
from pathlib import Path


class FFmpegNotFoundError(RuntimeError):
    def __init__(self, binary: str) -> None:
        super().__init__(
            f"no encontré '{binary}' en el PATH — instalalo (en macOS, "
            f"'brew install ffmpeg') antes de usar este plugin. Ninguna "
            f"etapa de video/audio puede avanzar sin él."
        )


class SubtitleFilterMissingError(RuntimeError):
    """El `ffmpeg` del PATH compiló sin `libass` — pasa en el formula
    default de Homebrew en macOS (no en la mayoría de las distros Linux,
    donde el paquete de ffmpeg ya lo trae). Se detecta ANTES de intentar
    el render, en vez de dejar que ffmpeg falle con un error de parseo de
    filtergraph que no dice nada sobre la causa real — eso fue exactamente
    lo que pasó la primera vez que se probó esto en vivo en esta Mac."""

    def __init__(self) -> None:
        super().__init__(
            "el 'ffmpeg' del PATH no tiene el filtro 'subtitles' (compilado sin libass) — "
            "no puede quemar subtítulos en el video. En macOS con Homebrew: "
            "'brew install ffmpeg-full && brew link --overwrite ffmpeg-full'. "
            "En la mayoría de las distros Linux, el paquete 'ffmpeg' del gestor "
            "de paquetes ya incluye libass."
        )


@functools.lru_cache(maxsize=1)
def has_subtitle_filter() -> bool:
    binary = shutil.which("ffmpeg")
    if binary is None:
        return False
    out = subprocess.run([binary, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=15)
    return " subtitles " in out.stdout


def require_subtitle_filter() -> None:
    if not has_subtitle_filter():
        raise SubtitleFilterMissingError()


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise FFmpegNotFoundError(binary)
    return path


def run_ffmpeg(args: list[str], *, timeout: float = 600.0) -> str:
    """Corre ffmpeg con -y (sobrescribir) y -hide_banner -loglevel error de
    forma consistente — el stdout+stderr combinado se devuelve siempre,
    así quien llama puede mostrarlo en el error del job sin tener que
    volver a correr nada a mano para ver qué pasó."""
    binary = _require("ffmpeg")
    full_args = [binary, "-y", "-hide_banner", "-loglevel", "error", *args]
    proc = subprocess.run(
        full_args, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg terminó con código {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout + proc.stderr


def run_ffprobe(args: list[str], *, timeout: float = 60.0) -> str:
    binary = _require("ffprobe")
    full_args = [binary, "-hide_banner", "-loglevel", "error", *args]
    proc = subprocess.run(
        full_args, capture_output=True, text=True, timeout=timeout
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffprobe terminó con código {proc.returncode}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
