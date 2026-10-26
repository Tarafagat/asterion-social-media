"""La etapa 'Renderizar': de un plan de edición (segmentos + layout +
subtítulos) a un .mp4 final. Un clip puede venir de VARIOS segmentos no
contiguos del video fuente (el modelo saltó una pausa en el medio, por
ejemplo) — se recortan y empalman en una sola pasada de ffmpeg con
`filter_complex`, no con archivos intermedios: menos I/O, y un solo
re-encode en vez de uno por segmento más uno para el concat.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ffcommon import ensure_parent, require_subtitle_filter, run_ffmpeg

# ancho x alto de salida por layout — "ajustar completo + fondo
# difuminado": el cuadro original se escala ENTERO adentro del layout
# (sin recortar nada) y se centra sobre una copia del mismo cuadro,
# escalada para llenar y desenfocada, de fondo. Antes esto recortaba el
# centro para llenar el cuadro — para un 16:9 a 9:16 eso deja ver solo
# ~31% del ancho original, perdiendo todo lo que no esté en el centro
# (texto a los costados de una grabación de pantalla, por ejemplo). Con
# fondo difuminado se ve el cuadro completo siempre, sin barras negras.
LAYOUT_DIMENSIONS: dict[str, tuple[int, int]] = {
    "vertical": (1080, 1920),
    "horizontal": (1920, 1080),
    "square": (1080, 1080),
}


@dataclass(frozen=True)
class RenderSegment:
    start_ms: int
    end_ms: int

    @property
    def duration_s(self) -> float:
        return max(0.0, (self.end_ms - self.start_ms) / 1000.0)

    @property
    def start_s(self) -> float:
        return self.start_ms / 1000.0


def _trim_filter(idx: int, seg: RenderSegment, w: int, h: int) -> tuple[str, str, str]:
    """Un bloque de filtro por segmento: recorta tiempo (trim/atrim) y
    reinicia los timestamps (setpts/asetpts) — sin esto, el segundo
    segmento concatenado empieza con el timestamp absoluto que tenía en
    el video original, no en cero, y el resultado sale con huecos o se
    corta mal.

    El video se divide en dos copias (`split`): una de fondo, escalada
    para LLENAR el cuadro (recortando lo que sobre) y desenfocada fuerte
    con `boxblur`; y una de primer plano, escalada para ENTRAR completa
    sin recortar nada (`force_original_aspect_ratio=decrease`), centrada
    encima con `overlay`. Así el cuadro original siempre se ve entero,
    y el fondo desenfocado rellena el resto del lienzo en vez de dejar
    barras negras."""
    v_label, a_label = f"v{idx}", f"a{idx}"
    bg, fg = f"bg{idx}", f"fg{idx}"
    v = (
        f"[0:v]trim=start={seg.start_s:.3f}:duration={seg.duration_s:.3f},"
        f"setpts=PTS-STARTPTS,split=2[{bg}][{fg}];"
        f"[{bg}]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},boxblur=luma_radius=25:luma_power=2[{bg}b];"
        f"[{fg}]scale={w}:{h}:force_original_aspect_ratio=decrease[{fg}f];"
        f"[{bg}b][{fg}f]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[{v_label}]"
    )
    a = (
        f"[0:a]atrim=start={seg.start_s:.3f}:duration={seg.duration_s:.3f},"
        f"asetpts=PTS-STARTPTS[{a_label}]"
    )
    return v, a, f"[{v_label}][{a_label}]"


def _avatar_filter(mode: str, w: int, h: int, total_duration_s: float) -> tuple[str, str]:
    """El avatar (input índice 1, siempre con `-stream_loop -1` antes de
    su `-i` — así nunca se corta antes de que termine el clip aunque el
    video grabado sea más corto) se prepara y se superpone sobre [vout]
    DESPUÉS del concat, una sola vez — es continuo durante todo el clip,
    no le importan los cortes entre segmentos.

    'pip': el avatar es una burbuja chica en la esquina inferior derecha,
    el contenido original queda a pantalla completa, como hoy sin avatar.

    'background': el avatar pasa a llenar todo el lienzo (es el 'avatar
    de fondo' que habla) y el contenido original queda como un recuadro
    más chico, centrado en la mitad inferior — deja la cara del avatar
    visible arriba."""
    if mode == "background":
        inset_w, inset_h = int(w * 0.82), int(h * 0.46)
        prep = (
            f"[1:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"trim=duration={total_duration_s:.3f},setpts=PTS-STARTPTS[avbg];"
            f"[vout]scale={inset_w}:{inset_h}[voutsmall]"
        )
        overlay = "[avbg][voutsmall]overlay=(main_w-overlay_w)/2:main_h-overlay_h-60[vav]"
        return prep, overlay

    # Basado en el lado más CHICO del lienzo, no siempre en w — para un
    # clip vertical w ya es el lado angosto, pero para un video horizontal
    # completo (ver packages/media/dub.py, que reusa este mismo filtro con
    # la resolución real del video en vez de un layout fijo) w es el lado
    # ANCHO, y calcular la burbuja sobre w la dejaba ocupando casi toda la
    # pantalla en vez de una esquina chica.
    pip_base = min(w, h)
    pip_w, pip_h = int(pip_base * 0.34), int(pip_base * 0.34 * 16 / 9)
    prep = (
        f"[1:v]scale={pip_w}:{pip_h}:force_original_aspect_ratio=increase,crop={pip_w}:{pip_h},"
        f"trim=duration={total_duration_s:.3f},setpts=PTS-STARTPTS[avpip]"
    )
    overlay = "[vout][avpip]overlay=main_w-overlay_w-36:main_h-overlay_h-36[vav]"
    return prep, overlay


def render_clip(
    source: Path,
    segments: list[RenderSegment],
    out_path: Path,
    *,
    layout: str = "vertical",
    subtitle_ass: Path | None = None,
    avatar_path: Path | None = None,
    avatar_mode: str = "pip",
) -> Path:
    if not segments:
        raise ValueError("render_clip necesita al menos un segmento")
    if layout not in LAYOUT_DIMENSIONS:
        raise ValueError(f"layout {layout!r} desconocido — usá uno de {list(LAYOUT_DIMENSIONS)}")

    ensure_parent(out_path)
    w, h = LAYOUT_DIMENSIONS[layout]

    v_filters, a_filters, concat_inputs = [], [], []
    for i, seg in enumerate(segments):
        v, a, inputs = _trim_filter(i, seg, w, h)
        v_filters.append(v)
        a_filters.append(a)
        concat_inputs.append(inputs)

    # 'concat' tiene que quedar ANTES, en la cadena de texto, de cualquier
    # filtro que use [vout] como entrada — el parser de ffmpeg arma el
    # grafo completo, pero mantenerlo en orden de ejecución real evita
    # cualquier ambigüedad con referencias hacia adelante.
    post_filters = [f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=1[vout][aout]"]
    video_out = "[vout]"

    # El avatar se compone DESPUÉS del concat — sobre el clip ya armado,
    # antes de quemar subtítulos (los subtítulos van siempre arriba de
    # todo, incluido el avatar).
    if avatar_path is not None:
        total_s = sum(seg.duration_s for seg in segments)
        prep, overlay = _avatar_filter(avatar_mode, w, h, total_s)
        post_filters.append(prep)
        post_filters.append(overlay)
        video_out = "[vav]"

    # Los subtítulos se queman DESPUÉS del concat (y del avatar, si hay) —
    # sobre el resultado ya unido, no segmento por segmento (los tiempos
    # del .ass ya están en la línea de tiempo del clip final, ver
    # packages/subtitles/ass.py).
    if subtitle_ass is not None:
        require_subtitle_filter()
        escaped = str(subtitle_ass).replace(":", r"\:").replace("'", r"\'")
        post_filters.append(f"{video_out}subtitles='{escaped}'[vsub]")
        video_out = "[vsub]"

    filter_complex = ";".join(v_filters + a_filters + post_filters)

    args = ["-i", str(source)]
    if avatar_path is not None:
        args += ["-stream_loop", "-1", "-i", str(avatar_path)]
    args += [
        "-filter_complex", filter_complex,
        "-map", video_out,
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "160k",
        str(out_path),
    ]
    run_ffmpeg(args, timeout=1800.0)  # un render de varios minutos de fuente puede tardar
    return out_path
