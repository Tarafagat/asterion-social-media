# SadTalker (Avatar IA)

SadTalker anima una foto con un audio para producir un video de cara
hablando — es el motor detrás de "Avatar IA" (distinto del avatar
grabado, que es un video que subís tal cual). Vive completamente aislado
en `vendor/SadTalker/`, con su propio venv Python 3.9: sus dependencias
(torch, numba, dlib, versiones viejas fijadas) nunca se mezclan con las
del plugin (`apps/api/venv`).

No está en git — `vendor/SadTalker/` está en `.gitignore` completo
(repo + checkpoints + venv, ~3GB). Se reproduce con:

```bash
bash vendor/setup_sadtalker.sh
```

## Qué hace el script

1. Instala `python@3.9`, `wget`, `cmake` por Homebrew si faltan.
2. Clona `OpenTalker/SadTalker`.
3. Crea su venv Python 3.9 e instala `torch`/`torchvision`/`torchaudio`
   sin fijar versión (siguiendo las instrucciones oficiales de macOS),
   más `requirements.txt` del repo y `dlib`.
4. Aplica un parche de compatibilidad (ver abajo).
5. Descarga los checkpoints principales (`scripts/download_models.sh`).
6. Descarga `BFM_Fitting` aparte (no está en el script oficial).

## Los dos problemas reales que esto resuelve

Encontrados corriendo esto en vivo en un M1 Pro — ninguno de los dos
está documentado en el repo de SadTalker:

1. **`ModuleNotFoundError: torchvision.transforms.functional_tensor`**
   — `basicsr==1.4.2` (dependencia de `gfpgan`, que SadTalker importa
   siempre al arrancar aunque nunca se pida `--enhancer`) todavía usa
   `torchvision.transforms.functional_tensor.rgb_to_grayscale`. Ese
   módulo lo borró torchvision en la 0.17 (se movió a
   `torchvision.transforms.functional`). Fijar una torchvision vieja
   rompería el resto del stack instalado sin pines — en cambio se
   restituye el módulo como un shim de una línea
   (`venv/.../torchvision/transforms/functional_tensor.py`).

2. **`checkpoints/BFM_Fitting/` falta** — el link de descarga está en
   `scripts/download_models.sh` pero **comentado** (es de una versión
   vieja del repo, antes de que se mudara de `Winfredy` a
   `OpenTalker`). El link con el nuevo org sigue funcionando
   (`v0.0.2/BFM_Fitting.zip`, ~400MB) pero hay que bajarlo aparte.

## Verificado en vivo

`inference.py --driven_audio <wav> --source_image <png> --still
--preprocess full` corrido de punta a punta en esta Mac (M1 Pro, CPU —
sin GPU NVIDIA, más lento que con CUDA pero funciona) con un audio real
generado por Piper TTS, produce un `.mp4` de la cara hablando.

## Uso desde el plugin

`packages/avatar/sadtalker_runner.py::generate_talking_head()` — nunca
se importa SadTalker en el proceso del plugin, siempre por `subprocess`
contra `vendor/SadTalker/venv/bin/python inference.py` (mismo criterio
que `packages/media/ffcommon.py` con `ffmpeg`).
