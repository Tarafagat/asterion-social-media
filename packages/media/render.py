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

# ancho x alto de salida por layout — "recortar para llenar": se escala
# hasta que el lado más chico ya mide lo que pide el layout, y se recorta
# el centro del otro lado. Para un fuente 16:9 a vertical 9:16 esto
# produce lo mismo que ya hace cualquier editor de shorts: el centro del
# cuadro, sin barras negras a los costados.
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
    corta mal."""
    v_label, a_label = f"v{idx}", f"a{idx}"
    v = (
        f"[0:v]trim=start={seg.start_s:.3f}:duration={seg.duration_s:.3f},"
        f"setpts=PTS-STARTPTS,"
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h}[{v_label}]"
    )
    a = (
        f"[0:a]atrim=start={seg.start_s:.3f}:duration={seg.duration_s:.3f},"
        f"asetpts=PTS-STARTPTS[{a_label}]"
    )
    return v, a, f"[{v_label}][{a_label}]"


def render_clip(
    source: Path,
    segments: list[RenderSegment],
    out_path: Path,
    *,
    layout: str = "vertical",
    subtitle_ass: Path | None = None,
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

    concat = f"{''.join(concat_inputs)}concat=n={len(segments)}:v=1:a=1[vout][aout]"
    video_out = "[vout]"

    # Los subtítulos se queman DESPUÉS del concat — sobre el resultado ya
    # unido, no segmento por segmento (los tiempos del .ass ya están en
    # la línea de tiempo del clip final, ver packages/subtitles/ass.py).
    if subtitle_ass is not None:
        require_subtitle_filter()
        escaped = str(subtitle_ass).replace(":", r"\:").replace("'", r"\'")
        v_filters.append(f"[vout]subtitles='{escaped}'[vsub]")
        video_out = "[vsub]"

    filter_complex = ";".join(v_filters + a_filters + [concat])

    run_ffmpeg(
        [
            "-i", str(source),
            "-filter_complex", filter_complex,
            "-map", video_out,
            "-map", "[aout]",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "160k",
            str(out_path),
        ],
        timeout=1800.0,  # un render de varios minutos de fuente puede tardar
    )
    return out_path
