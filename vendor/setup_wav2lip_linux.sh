#!/usr/bin/env bash
# Instala Wav2Lip aislado en LINUX (Debian/Ubuntu y otras), bajo
# vendor/Wav2Lip/ con su propio venv Python 3.9 — NO se mezcla con el venv
# del plugin (apps/api/venv). Wav2Lip es la alternativa RÁPIDA EN CPU a
# SadTalker (solo sincroniza labios), por eso es el motor por default
# (config AVATAR_ENGINE=wav2lip).
#
# Más liviano que SadTalker: NO compila nada (sin dlib/basicsr/gfpgan), así
# que instala en minutos. Python 3.9 vía uv (prebuilt). PyTorch CPU.
# Checkpoints desde el mirror camenduru (HuggingFace).
#
# Requiere: Linux con apt y sudo, ~1GB de descarga. Uso:
#   bash vendor/setup_wav2lip_linux.sh
set -euo pipefail
cd "$(dirname "$0")"

CKPT_BASE="https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints"

echo "== 1/6: dependencias del sistema (apt) =="
sudo apt-get update
# libgl1 + libglib2.0-0: lo que pide opencv en runtime. ffmpeg: lo usa
# Wav2Lip para leer/escribir video. No hace falta compilador: todo viene
# en ruedas (wheels) para cp39.
sudo apt-get install -y git wget curl ffmpeg libgl1 libglib2.0-0

echo "== 2/6: Python 3.9 ya compilado (vía uv) =="
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"
uv python install 3.9

echo "== 3/6: clonando Wav2Lip =="
[ -d Wav2Lip ] || git clone --depth 1 https://github.com/Rudrabha/Wav2Lip.git
cd Wav2Lip

echo "== 4/6: venv Python 3.9 + dependencias (CPU) =="
[ -d venv ] || uv venv --seed --python 3.9 venv
# setuptools<80: librosa 0.9.2 todavía usa pkg_resources, que setuptools
# quitó en la 81 (ver el mismo detalle en setup_sadtalker_linux.sh).
venv/bin/pip install "setuptools<80" wheel
# PyTorch CPU. Con GPU NVIDIA, reemplaza por:
#   venv/bin/pip install torch torchvision
venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
# Versiones fijadas que SÍ funcionan en Python 3.9 con el código de
# Wav2Lip: numpy 1.23.5 (la 1.24 quitó np.float, que usa el stack viejo) y
# librosa 0.9.2 (la 0.10 cambió la API de filters.mel que usa audio.py).
# librosa arrastra numba/resampy/scipy/soundfile.
venv/bin/pip install "numpy==1.23.5" "librosa==0.9.2" opencv-python tqdm

echo "== 5/6: checkpoints (mirror camenduru) =="
mkdir -p checkpoints face_detection/detection/sfd
# Modelo principal (~436MB).
[ -f checkpoints/wav2lip_gan.pth ] || \
  wget -nc "$CKPT_BASE/wav2lip_gan.pth" -O checkpoints/wav2lip_gan.pth
# Detector de caras S3FD (~86MB) — Wav2Lip lo espera en esta ruta exacta.
[ -f face_detection/detection/sfd/s3fd.pth ] || \
  wget -nc "$CKPT_BASE/s3fd-619a316812.pth" -O face_detection/detection/sfd/s3fd.pth

echo "== 6/6: verificación =="
venv/bin/python -c "import torch, librosa, cv2, numpy; print('torch', torch.__version__, '. numpy', numpy.__version__, '. librosa', librosa.__version__)"
ls -lh checkpoints/wav2lip_gan.pth face_detection/detection/sfd/s3fd.pth
echo "== listo =="
echo "Reinicia el plugin:  asterion plugin restart social-clips"
echo "(AVATAR_ENGINE ya es 'wav2lip' por default.)"
