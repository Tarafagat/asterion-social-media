"""Reemplaza el audio del video FUENTE completo por una narración nueva
(generada de un guion con Piper TTS, ver packages/avatar/tts_piper.py) —
a diferencia de un clip, acá no se recorta nada del contenido, el video
original se mantiene entero. La única pregunta real es qué hacer cuando
la narración nueva no dura lo mismo que el video original:

- Narración más CORTA: se recorta el video a esa duración (el resto del
  video original, sin audio nuevo que lo cubra, no tendría sentido
  dejarlo).
- Narración más LARGA: se repite el video en loop hasta cubrirla, con
  '-stream_loop -1' (opción de ENTRADA — el demuxer relee el archivo
  desde el principio indefinidamente, sin el límite de frames que tiene
  el filtro `loop` dentro de filter_complex).

Opcionalmente monta un avatar hablando encima (la misma animación que
genera SadTalker para el guion, ver sadtalker_runner.py) — reusa
`_avatar_filter` de render.py tal cual (ya está parametrizado en ancho/
alto, no hace falta duplicarlo), con el ancho/alto REALES del video
completo en vez de un layout fijo de 1080x1920: acá no se reformatea a
ningún tamaño de red social, se mantiene la resolución original.
"""

from __future__ import annotations

from pathlib import Path

from .ffcommon import ensure_parent, run_ffmpeg
from .probe import probe, probe_duration
from .render import _avatar_filter


def replace_audio(
    video_path: Path,
    audio_path: Path,
    out_path: Path,
    *,
    avatar_path: Path | None = None,
    avatar_mode: str = "pip",
) -> Path:
    ensure_parent(out_path)
    video_info = probe(video_path)
    audio_duration = probe_duration(audio_path)

    if audio_duration <= video_info.duration_s:
        args = ["-i", str(video_path)]
    else:
        args = ["-stream_loop", "-1", "-i", str(video_path)]

    # Mismo label [vout] que usa _avatar_filter (copiado de render.py) —
    # así se reusa tal cual, sin tener que generalizarlo para aceptar un
    # label de entrada distinto.
    filters = [f"[0:v]trim=duration={audio_duration:.3f},setpts=PTS-STARTPTS[vout]"]
    video_out = "[vout]"

    if avatar_path is not None:
        args += ["-stream_loop", "-1", "-i", str(avatar_path)]
        prep, overlay = _avatar_filter(avatar_mode, video_info.width, video_info.height, audio_duration)
        filters += [prep, overlay]
        video_out = "[vav]"

    audio_input_index = 2 if avatar_path is not None else 1
    args += ["-i", str(audio_path)]

    args += [
        "-filter_complex", ";".join(filters),
        "-map", video_out,
        "-map", f"{audio_input_index}:a",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        str(out_path),
    ]
    run_ffmpeg(args, timeout=1800.0)
    return out_path
