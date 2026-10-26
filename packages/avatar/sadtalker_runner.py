"""Anima una foto con un audio usando SadTalker — vive en su propio venv
aislado (`vendor/SadTalker/venv`, Python 3.9, dependencias viejas
fijadas: torch, numba, dlib) para no mezclarlas con las de este plugin.
Se invoca por subprocess, igual criterio que `packages/media/ffcommon.py`
con ffmpeg: un binario/entorno externo, nunca importado en proceso.

Dos parches necesarios en esta máquina (macOS/arm64), documentados acá
porque no están en el repo de SadTalker y se perderían en un `git clone`
limpio — ver vendor/SADTALKER_SETUP.md para los pasos completos:
1. `torchvision.transforms.functional_tensor` fue removido en
   torchvision 0.17+ — basicsr (dependencia de gfpgan, que SadTalker
   importa siempre aunque no se pida --enhancer) todavía lo usa. Shim en
   vendor/SadTalker/venv/.../torchvision/transforms/functional_tensor.py.
2. `checkpoints/BFM_Fitting/` no se baja con scripts/download_models.sh
   (el link está comentado, es de una versión vieja) — hace falta bajar
   BFM_Fitting.zip del release v0.0.2 aparte.

Esta máquina no tiene GPU NVIDIA y el propio inference.py de SadTalker
solo sabe detectar CUDA (nunca MPS) — corre 100% por CPU. Verificado en
vivo: un audio de ~8s tardó ~34 minutos reales. El timeout por default
de acá sale generoso (1h) a propósito por eso mismo.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable

SADTALKER_DIR = Path(__file__).resolve().parent.parent.parent / "vendor" / "SadTalker"
_SADTALKER_VENV = SADTALKER_DIR / "venv"
# venv/bin/python en macOS/Linux; en Windows una distribución de
# python-build-standalone deja python.exe en la raíz del venv, sin
# carpeta bin/ — se prueban ambas en vez de asumir la de POSIX.
_SADTALKER_PYTHON_CANDIDATES = (_SADTALKER_VENV / "bin" / "python", _SADTALKER_VENV / "python.exe")
SADTALKER_PYTHON = next(
    (p for p in _SADTALKER_PYTHON_CANDIDATES if p.exists()), _SADTALKER_PYTHON_CANDIDATES[0]
)

_PROGRESS_RE = re.compile(r"(\d+)%\|")


class SadTalkerNotInstalledError(RuntimeError):
    pass


class SadTalkerError(RuntimeError):
    pass


class SadTalkerTimeoutError(SadTalkerError):
    pass


def is_installed() -> bool:
    return SADTALKER_PYTHON.exists() and (SADTALKER_DIR / "checkpoints" / "BFM_Fitting").exists()


def _read_progress_stream(proc: subprocess.Popen, on_progress: Callable[[int], None] | None) -> str:
    """SadTalker reporta avance con barras `tqdm`, que separan cada
    actualización con `\\r` (nunca `\\n`) — iterar por línea con
    `for line in proc.stdout` nunca dispara, todo llega como una sola
    'línea' gigante. Se lee char a char, cortando en `\\r`/`\\n`, y de
    cada fragmento se toma el ÚLTIMO 'NN%|' que aparezca (puede haber
    más de uno en un fragmento si tqdm actualizó rápido). No distingue
    entre las etapas internas de SadTalker (landmark/3DMM/mel/audio2exp/
    Face Renderer/seamlessClone) — no hace falta: Face Renderer domina
    el tiempo real casi por completo, así que el último % visto es, en
    la práctica, el de Face Renderer durante casi toda la corrida."""
    buf = []
    output = []
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
    still: bool = True,
    preprocess: str = "full",
    size: int = 256,
    enhancer: str | None = None,
    timeout: float = 3600.0,
    on_progress: Callable[[int], None] | None = None,
) -> Path:
    if not is_installed():
        raise SadTalkerNotInstalledError(
            "SadTalker no está instalado en esta máquina — ver vendor/SADTALKER_SETUP.md"
        )

    out_video.parent.mkdir(parents=True, exist_ok=True)
    # Carpeta de resultado propia por corrida (nunca compartida) — así se
    # puede identificar el .mp4 que generó ESTA llamada sin parsear el
    # stdout de inference.py para eso ni competir con otra corrida
    # concurrente.
    run_result_dir = SADTALKER_DIR / "_runs" / uuid.uuid4().hex
    run_result_dir.mkdir(parents=True, exist_ok=True)

    args = [
        str(SADTALKER_PYTHON), "inference.py",
        "--driven_audio", str(audio_path.resolve()),
        "--source_image", str(image_path.resolve()),
        "--result_dir", str(run_result_dir.resolve()),
        "--preprocess", preprocess,
        "--size", str(size),
    ]
    if still:
        args.append("--still")
    if enhancer:
        args += ["--enhancer", enhancer]

    start = time.monotonic()
    proc = subprocess.Popen(
        args, cwd=SADTALKER_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
    )
    try:
        output = _read_progress_stream(proc, on_progress)
        returncode = proc.wait(timeout=max(0.0, timeout - (time.monotonic() - start)))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        shutil.rmtree(run_result_dir, ignore_errors=True)
        raise SadTalkerTimeoutError(f"SadTalker no terminó en {timeout:.0f}s — se mató el proceso")

    if returncode != 0:
        shutil.rmtree(run_result_dir, ignore_errors=True)
        raise SadTalkerError(f"SadTalker terminó con código {returncode}: {output[-2000:]}")

    generated = list(run_result_dir.glob("*.mp4"))
    if not generated:
        shutil.rmtree(run_result_dir, ignore_errors=True)
        raise SadTalkerError(f"SadTalker terminó sin errores pero no generó ningún .mp4 en {run_result_dir}")

    shutil.move(str(generated[0]), str(out_video))
    shutil.rmtree(run_result_dir, ignore_errors=True)
    return out_video
