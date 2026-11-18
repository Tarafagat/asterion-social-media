# Wav2Lip (Avatar — rápido en CPU)

Wav2Lip sincroniza los labios de una foto (o video) con un audio. Es la
alternativa **rápida en CPU** a SadTalker: solo anima la zona de la boca
(red mucho más chica), así que en CPU tarda **minutos** en vez de decenas
de minutos. A cambio no mueve la cabeza como SadTalker, solo la boca.

Es el **motor por default** del avatar (config `AVATAR_ENGINE=wav2lip`).
El otro motor es SadTalker (`AVATAR_ENGINE=sadtalker`, ver
[SADTALKER_SETUP.md](SADTALKER_SETUP.md)). El código que elige entre los
dos está en `packages/avatar/__init__.py`; cada uno corre aislado en su
propio venv y se invoca por subprocess (ver
`packages/avatar/wav2lip_runner.py`).

No está en git — `vendor/Wav2Lip/` está en `.gitignore` (repo + venv +
checkpoints, ~0.5GB). Se reproduce con:

```bash
bash vendor/setup_wav2lip_linux.sh
```

## Qué hace el script

1. Instala deps del sistema con `apt` (ffmpeg, libgl para opencv). **No
   compila nada** (a diferencia de SadTalker, que compila dlib): todo
   viene en wheels, así que instala en minutos.
2. Python 3.9 con **uv** (prebuilt, sin compilar ni tocar el Python del
   sistema) — igual que en SadTalker.
3. Clona `Rudrabha/Wav2Lip`.
4. Crea su venv e instala PyTorch **CPU** + versiones fijadas que funcionan
   en Python 3.9: `numpy==1.23.5` (la 1.24 quitó `np.float`) y
   `librosa==0.9.2` (la 0.10 cambió la API de `filters.mel`).
5. Descarga los checkpoints desde el mirror **camenduru** (HuggingFace):
   `wav2lip_gan.pth` (~436MB) y el detector de caras `s3fd` (~86MB), este
   último a `face_detection/detection/sfd/s3fd.pth`, que es donde Wav2Lip
   lo busca.

## CPU

El `inference.py` de Wav2Lip elige el dispositivo solo
(`'cuda' if torch.cuda.is_available() else 'cpu'`), así que en una máquina
sin GPU corre por CPU sin configurar nada. Con GPU NVIDIA, cambiar la línea
de `torch` del script por la versión CUDA (ver el comentario ahí).

## Uso desde el plugin

`packages/avatar/wav2lip_runner.py::generate_talking_head()` lo invoca por
subprocess contra `vendor/Wav2Lip/venv/bin/python inference.py` con
`--checkpoint_path`/`--face`/`--audio`/`--outfile`. Con una imagen como
`--face`, Wav2Lip activa solo el modo estático (lo detecta por la
extensión). El resultado se monta sobre el clip/video igual que el de
SadTalker (pip/fondo, ver `packages/media/render.py`).
