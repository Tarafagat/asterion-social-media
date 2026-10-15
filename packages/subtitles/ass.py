"""`.ass` quemado en el video por `packages/media/render.py` (filtro
`subtitles=`) — a diferencia de `.srt`, `.ass` sí sabe de tipografía,
color, borde y posición, que es lo que `presets/*.yaml` configura por
estilo (`shorts`, `programming`, `youtube-horizontal`, el que declare
`edit_subtitle_style`).
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from pathlib import Path

import yaml

from packages.transcription import TranscriptSegment

PRESETS_DIR = Path(__file__).resolve().parent.parent.parent / "presets"


@dataclass(frozen=True)
class SubtitleStyle:
    name: str
    font: str = "Arial"
    font_size: int = 56
    primary_color: str = "&H00FFFFFF"  # ASS: &HAABBGGRR, blanco
    outline_color: str = "&H00000000"  # negro
    outline_width: int = 3
    position: str = "bottom"  # bottom | center | top
    margin_v: int = 100
    max_chars_per_line: int = 26

    # alineación numpad de libass: 2=abajo-centro, 5=centro-centro, 8=arriba-centro
    _ALIGN = {"bottom": 2, "center": 5, "top": 8}

    @property
    def alignment(self) -> int:
        return self._ALIGN.get(self.position, 2)


DEFAULT_STYLE = SubtitleStyle(name="default")


def load_style(style_name: str) -> SubtitleStyle:
    """Un estilo sin archivo propio en `presets/` (o un `presets/` que
    todavía no existe en este checkout) cae al default en vez de romper
    el render — un subtítulo con tipografía genérica es mejor que un job
    fallado por un .yaml que falta."""
    path = PRESETS_DIR / f"{style_name}.yaml"
    if not path.exists():
        return DEFAULT_STYLE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SubtitleStyle(
        name=style_name,
        font=data.get("font", DEFAULT_STYLE.font),
        font_size=int(data.get("font_size", DEFAULT_STYLE.font_size)),
        primary_color=data.get("primary_color", DEFAULT_STYLE.primary_color),
        outline_color=data.get("outline_color", DEFAULT_STYLE.outline_color),
        outline_width=int(data.get("outline_width", DEFAULT_STYLE.outline_width)),
        position=data.get("position", DEFAULT_STYLE.position),
        margin_v=int(data.get("margin_v", DEFAULT_STYLE.margin_v)),
        max_chars_per_line=int(data.get("max_chars_per_line", DEFAULT_STYLE.max_chars_per_line)),
    )


def _ass_timestamp(ms: int) -> str:
    ms = max(0, ms)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, centis = divmod(rem, 1000)
    return f"{h:d}:{m:02d}:{s:02d}.{centis // 10:02d}"


def _wrap(text: str, width: int) -> str:
    return r"\N".join(textwrap.wrap(text, width=width) or [text])


def write_ass(segments: list[TranscriptSegment], style: SubtitleStyle, out_path: Path, *, video_w: int, video_h: int) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.font},{style.font_size},{style.primary_color},{style.outline_color},-1,1,{style.outline_width},0,{style.alignment},40,40,{style.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header]
    for seg in segments:
        text = _wrap(seg.text.strip(), style.max_chars_per_line)
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(seg.start_ms)},{_ass_timestamp(seg.end_ms)},Default,,0,0,0,,{text}"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
