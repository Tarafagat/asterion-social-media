#!/usr/bin/env bash
# Instala SadTalker aislado en LINUX (Debian/Ubuntu) — equivalente a
# setup_sadtalker.sh, que es para macOS/Homebrew. Clon + venv Python 3.9
# propio + checkpoints bajo vendor/SadTalker/, sin mezclarse NUNCA con el
# venv del plugin (apps/api/venv).
#
# Requiere: Debian/Ubuntu con sudo, ~3GB de descarga y bastante tiempo
# (dlib se compila; en CPU el primer render tarda varios minutos). Instala
# PyTorch para CPU por defecto — si la instancia tiene GPU NVIDIA, ver la
# nota del paso 3.
#
# Uso:  bash vendor/setup_sadtalker_linux.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/6: dependencias del sistema (apt) =="
sudo apt-get update
sudo apt-get install -y git wget unzip cmake build-essential \
    libgl1 libglib2.0-0 ffmpeg software-properties-common

# Python 3.9: SadTalker fija dependencias viejas que piden 3.9. En Ubuntu
# sale del PPA deadsnakes; en Debian u otra distro, instala Python 3.9 con
# pyenv (https://github.com/pyenv/pyenv) y vuelve a ejecutar este script.
if ! command -v python3.9 >/dev/null 2>&1; then
  echo "   python3.9 no está — probando con el PPA deadsnakes (Ubuntu)..."
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update
  sudo apt-get install -y python3.9 python3.9-venv python3.9-dev
fi
command -v python3.9 >/dev/null 2>&1 || {
  echo "ERROR: no se pudo instalar python3.9. En Debian, instálalo con pyenv y vuelve a ejecutar este script."
  exit 1
}

echo "== 2/6: clonando SadTalker =="
[ -d SadTalker ] || git clone --depth 1 https://github.com/OpenTalker/SadTalker.git
cd SadTalker

echo "== 3/6: venv Python 3.9 + PyTorch (CPU por defecto) =="
[ -d venv ] || python3.9 -m venv venv
venv/bin/pip install --upgrade pip
# CPU por defecto. Con GPU NVIDIA, reemplaza la línea siguiente por:
#   venv/bin/pip install torch torchvision torchaudio
# (baja las ruedas CUDA que correspondan al driver instalado).
venv/bin/pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
venv/bin/pip install -r requirements.txt
venv/bin/pip install dlib

echo "== 4/6: parche de compatibilidad (torchvision >=0.17 borró functional_tensor) =="
# basicsr==1.4.2 (dependencia de gfpgan, que SadTalker importa siempre al
# arrancar aunque no se pida --enhancer) todavía usa
# torchvision.transforms.functional_tensor.rgb_to_grayscale, borrado en
# torchvision 0.17. Se restituye como shim en vez de fijar una torchvision
# vieja que rompería el resto del stack.
SHIM="venv/lib/python3.9/site-packages/torchvision/transforms/functional_tensor.py"
[ -f "$SHIM" ] || echo "from torchvision.transforms.functional import rgb_to_grayscale  # noqa: F401" > "$SHIM"

echo "== 5/6: checkpoints principales (script oficial) =="
bash scripts/download_models.sh

echo "== 6/6: BFM_Fitting (no está en el script oficial — link del release v0.0.2) =="
if [ ! -d checkpoints/BFM_Fitting ]; then
  wget -nc https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/BFM_Fitting.zip -O checkpoints/BFM_Fitting.zip
  unzip -n checkpoints/BFM_Fitting.zip -d checkpoints/
fi

echo "== listo =="
venv/bin/python -c "import torch, dlib; print('torch', torch.__version__, '. dlib', dlib.__version__)"
echo "Ahora reinicia el plugin:  asterion plugin restart social-clips"
