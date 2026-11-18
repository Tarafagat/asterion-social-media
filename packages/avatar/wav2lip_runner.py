"""Sincroniza los labios de una foto/video con un audio usando Wav2Lip —
la alternativa RÁPIDA EN CPU a SadTalker (ver sadtalker_runner.py). Wav2Lip
solo anima la zona de la boca (red mucho más chica), así que en CPU tarda
minutos en vez de decenas de minutos; a cambio no mueve la cabeza como
SadTalker, solo la boca. Cuál se usa lo decide `AVATAR_ENGINE`
(settings.avatar_engine); el dispatcher está en packages/avatar/__init__.py.

Vive aislado en su propio venv (`vendor/Wav2Lip/venv`, Python 3.9) y se
invoca por subprocess contra su `inference.py` — mismo criterio que
sadtalker_runner.py y packages/media/ffcommon.py: un entorno externo, nunca
importado en el proceso del plugin. Instalación: vendor/setup_wav2lip_linux.sh
(Linux) — ver vendor/WAV2LIP_SETUP.md.

inference.py ya elige el dispositivo solo (`'cuda' if torch.cuda.is_available()
else 'cpu'`), así que en una máquina sin GPU corre por CPU sin configurar nada.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

ENGINE_NAME = "Wav2Lip"
SETUP_DOC = "vendor/WAV2LIP_SETUP.md"

WAV2LIP_DIR = Path(__file__).resolve().parent.parent.parent / "vendor" / "Wav2Lip"
_WAV2LIP_VENV = WAV2LIP_DIR / "venv"
_WAV2LIP_PYTHON_CANDIDATES = (_WAV2LIP_VENV / "bin" / "python", _WAV2LIP_VENV / "python.exe")
WAV2LIP_PYTHON = next(
    (p for p in _WAV2LIP_PYTHON_CANDIDATES if p.exists()), _WAV2LIP_PYTHON_CANDIDATES[0]
)
_CHECKPOINT = WAV2LIP_DIR / "checkpoints" / "wav2lip_gan.pth"
_S3FD = WAV2LIP_DIR / "face_detection" / "detection" / "sfd" / "s3fd.pth"

# tqdm reporta 'NN%|' igual que SadTalker (ver _read_progress_stream).
_PROGRESS_RE = re.compile(r"(\d+)%\|")


class Wav2LipNotInstalledError(RuntimeError):
    pass


class Wav2LipError(RuntimeError):
    pass


class Wav2LipTimeoutError(Wav2LipError):
    pass


def is_installed() -> bool:
    return WAV2LIP_PYTHON.exists() and _CHECKPOINT.exists() and _S3FD.exists()


def _read_progress_stream(proc: subprocess.Popen, on_progress: Callable[[int], None] | None) -> str:
    """Wav2Lip usa barras tqdm (detección de caras + inferencia), que
    separan cada actualización con `\\r`. Igual que en SadTalker, iterar por
    línea nunca dispara; se lee char a char cortando en `\\r`/`\\n` y de cada
    fragmento se toma el ÚLTIMO 'NN%|'."""
    buf: list[str] = []
    output: list[str] = []
    assert proc.stdout is not None
    while True:
        ch = proc.stdout.read(1)
        if ch == "" and proc.poll() is not None:
            break
        if ch in ("\r", "\n"):
            chunk = "".join(buf)
            buf = []
            if chunk:
                output.append(chunk)
                if on_progress:
                    matches = _PROGRESS_RE.findall(chunk)
                    if matches:
                        on_progress(int(matches[-1]))
            continue
        if ch:
            buf.append(ch)
    if buf:
        output.append("".join(buf))
    return "\n".join(output)


def generate_talking_head(
    image_path: Path,
    audio_path: Path,
    out_video: Path,
    *,
    timeout: float = 3600.0,
    on_progress: Callable[[int], None] | None = None,
    on_process_start: Callable[[subprocess.Popen], None] | None = None,
) -> Path:
    """Misma firma pública que sadtalker_runner.generate_talking_head para
    que el dispatcher (packages/avatar/__init__.py) los use indistintamente:
    una foto (o video) + un audio -> un .mp4 con los labios sincronizados."""
    if not is_installed():
        raise Wav2LipNotInstalledError(
            f"{ENGINE_NAME} no está instalado en esta máquina — ver {SETUP_DOC}"
        )

    out_video.parent.mkdir(parents=True, exist_ok=True)

    # Wav2Lip escribe directo en --outfile (a diferencia de SadTalker, que
    # deja el .mp4 en un result_dir y hay que buscarlo). Con una IMAGEN como
    # --face, inference.py activa solo el modo estático (lo detecta por la
    # extensión), así que no hace falta pasar --static.
    args = [
        str(WAV2LIP_PYTHON), "inference.py",
        "--checkpoint_path", str(_CHECKPOINT.resolve()),
        "--face", str(image_path.resolve()),
        "--audio", str(audio_path.resolve()),
        "--outfile", str(out_video.resolve()),
    ]

    start = time.monotonic()
    proc = subprocess.Popen(
        args, cwd=WAV2LIP_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    if on_process_start:
        # Para poder cancelar la corrida desde afuera (apps/worker/app/
        # runner.py::cancel_job), igual que con SadTalker.
        on_process_start(proc)
    try:
        output = _read_progress_stream(proc, on_progress)
        returncode = proc.wait(timeout=max(0.0, timeout - (time.monotonic() - start)))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise Wav2LipTimeoutError(f"{ENGINE_NAME} no terminó en {timeout:.0f}s — se mató el proceso")

    if returncode != 0:
        raise Wav2LipError(f"{ENGINE_NAME} terminó con código {returncode}: {output[-2000:]}")
    if not out_video.exists():
        raise Wav2LipError(f"{ENGINE_NAME} terminó sin errores pero no generó {out_video}")

    return out_video
