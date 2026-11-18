#!/usr/bin/env bash
# Instala SadTalker aislado en LINUX (Debian, Ubuntu y otras) — equivalente
# a setup_sadtalker.sh, que es para macOS/Homebrew. Clon + venv Python 3.9
# propio + checkpoints bajo vendor/SadTalker/, sin mezclarse NUNCA con el
# venv del plugin (apps/api/venv).
#
# Python 3.9 se obtiene con uv (https://astral.sh/uv): baja un Python 3.9
# YA COMPILADO, sin compilar nada ni tocar el Python del sistema. Así
# funciona igual en Debian (que ya trae 3.13) que en Ubuntu, sin depender
# del PPA deadsnakes (que solo existe en Ubuntu).
#
# Requiere: Linux con apt y sudo, ~3GB de descarga y bastante tiempo (dlib
# se compila; en CPU el primer render tarda varios minutos). Instala
# PyTorch para CPU por defecto — con GPU NVIDIA, ver la nota del paso 4.
#
# Uso:  bash vendor/setup_sadtalker_linux.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/7: dependencias del sistema (apt) =="
sudo apt-get update
# build-essential + cmake -> compilar dlib ; libgl1 + libglib2.0-0 -> lo
# que pide opencv en tiempo de ejecución ; ffmpeg lo usa SadTalker.
sudo apt-get install -y git wget curl unzip cmake build-essential ffmpeg \
    libgl1 libglib2.0-0

echo "== 2/7: Python 3.9 ya compilado (vía uv) =="
# SadTalker fija dependencias viejas que piden Python 3.9; las distros
# actuales traen 3.12/3.13. uv baja un 3.9 standalone, sin compilar.
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.9

echo "== 3/7: clonando SadTalker =="
[ -d SadTalker ] || git clone --depth 1 https://github.com/OpenTalker/SadTalker.git
cd SadTalker

echo "== 4/7: venv Python 3.9 + PyTorch (CPU por defecto) =="
[ -d venv ] || uv venv --seed --python 3.9 venv
# setuptools FIJADO a <80: desde la 81 se quitó `pkg_resources`, que
# librosa 0.9.2 (la que fija SadTalker) todavía importa. Con el setuptools
# más nuevo, inference.py muere con "No module named 'pkg_resources'".
venv/bin/pip install --upgrade pip wheel cython
venv/bin/pip install "setuptools<80"
# CPU por defecto. Con GPU NVIDIA, reemplaza la línea siguiente por:
#   venv/bin/pip install torch torchvision torchaudio
# (baja las ruedas CUDA que correspondan al driver instalado).
venv/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# IMPORTANTE (Linux): basicsr, facexlib y gfpgan se compilan de sdist e
# importan torch en su setup.py. Con aislamiento de build (lo normal) pip
# arma un entorno nuevo y baja el torch de CUDA (~888MB + VARIOS GB de libs
# nvidia-*) SOLO para compilarlos, LLENANDO EL DISCO ("No space left on
# device"). Con --no-build-isolation reutilizan el torch CPU ya instalado
# en el venv y no se baja nada de CUDA. (En macOS no pasa: el torch de PyPI
# para macOS ya es CPU, por eso el script de macOS no necesita esto.)
venv/bin/pip install -r requirements.txt --no-build-isolation
venv/bin/pip install dlib

echo "== 5/7: parche de compatibilidad (torchvision >=0.17 borró functional_tensor) =="
# basicsr==1.4.2 (dependencia de gfpgan, que SadTalker importa siempre al
# arrancar aunque no se pida --enhancer) todavía usa
# torchvision.transforms.functional_tensor.rgb_to_grayscale, borrado en
# torchvision 0.17. Se restituye como shim en vez de fijar una torchvision
# vieja que rompería el resto del stack.
SHIM="venv/lib/python3.9/site-packages/torchvision/transforms/functional_tensor.py"
[ -f "$SHIM" ] || echo "from torchvision.transforms.functional import rgb_to_grayscale  # noqa: F401" > "$SHIM"

echo "== 6/7: checkpoints principales (script oficial) =="
bash scripts/download_models.sh

echo "== 7/7: BFM_Fitting (no está en el script oficial — link del release v0.0.2) =="
if [ ! -d checkpoints/BFM_Fitting ]; then
  wget -nc https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/BFM_Fitting.zip -O checkpoints/BFM_Fitting.zip
  unzip -n checkpoints/BFM_Fitting.zip -d checkpoints/
fi

echo "== listo =="
venv/bin/python -c "import torch, dlib; print('torch', torch.__version__, '. dlib', dlib.__version__)"
echo "Ahora reinicia el plugin:  asterion plugin restart social-clips"
