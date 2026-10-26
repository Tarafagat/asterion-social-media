#!/usr/bin/env bash
# Instala SadTalker aislado (clon + venv Python 3.9 propio + checkpoints)
# bajo vendor/SadTalker/ — nunca se mezcla con el venv del plugin
# (apps/api/venv). Pensado para macOS/arm64; probado en un M1 Pro.
#
# Requiere: Homebrew, ~3GB de descarga, ~10 min según la conexión.
# Uso: bash vendor/setup_sadtalker.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/6: dependencias del sistema (python@3.9, wget, cmake) =="
brew list python@3.9 &>/dev/null || brew install python@3.9
brew list wget &>/dev/null || brew install wget
brew list cmake &>/dev/null || brew install cmake

echo "== 2/6: clonando SadTalker =="
if [ ! -d SadTalker ]; then
  git clone --depth 1 https://github.com/OpenTalker/SadTalker.git
fi
cd SadTalker

echo "== 3/6: venv Python 3.9 propio =="
PY39="$(brew --prefix python@3.9)/bin/python3.9"
[ -d venv ] || "$PY39" -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install torch torchvision torchaudio
venv/bin/pip install -r requirements.txt
venv/bin/pip install dlib

echo "== 4/6: parche de compatibilidad (torchvision >=0.17 borró functional_tensor) =="
# basicsr==1.4.2 (dependencia de gfpgan, que SadTalker importa siempre
# aunque no se pida --enhancer) todavía usa
# torchvision.transforms.functional_tensor.rgb_to_grayscale — ese módulo
# ya no existe en torch/torchvision modernos (los que se instalan acá,
# sin pin, siguiendo las instrucciones oficiales de macOS). Se restituye
# como shim en vez de fijar una torchvision vieja que rompería el resto.
SHIM="venv/lib/python3.9/site-packages/torchvision/transforms/functional_tensor.py"
if [ ! -f "$SHIM" ]; then
  cat > "$SHIM" << 'EOF'
from torchvision.transforms.functional import rgb_to_grayscale  # noqa: F401
EOF
fi

echo "== 5/6: checkpoints principales (script oficial) =="
bash scripts/download_models.sh

echo "== 6/6: BFM_Fitting (no está en el script oficial — link viejo, comentado) =="
if [ ! -d checkpoints/BFM_Fitting ]; then
  wget -nc https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2/BFM_Fitting.zip -O checkpoints/BFM_Fitting.zip
  unzip -n checkpoints/BFM_Fitting.zip -d checkpoints/
fi

echo "== listo =="
venv/bin/python -c "import torch, dlib; print('torch', torch.__version__, '· dlib', dlib.__version__)"
echo "checkpoints: $(du -sh checkpoints | cut -f1) · gfpgan: $(du -sh gfpgan 2>/dev/null | cut -f1 || echo 0)"
