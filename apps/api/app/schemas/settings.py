"""Solo lectura, a propósito: Asterion inyecta la configuración de un
plugin como variables de entorno AL ARRANCAR el proceso (ver `packages/
config/settings.py`) — no hay un mecanismo para que el plugin mismo
reescriba su configuración en caliente y que eso tenga efecto sin
reiniciar. La UI muestra el valor efectivo y el comando exacto de
`asterion` para cambiarlo, en vez de fingir un botón 'Guardar' que
tendría que mentir sobre cuándo el cambio entra en efecto."""

from __future__ import annotations

from pydantic import BaseModel

from packages.config import Settings

PLUGIN_NAME = "social-clips"


class SettingsField(BaseModel):
    key: str
    label: str
    value: str
    is_secret: bool = False
    set_command: str


class SettingsOut(BaseModel):
    provider: list[SettingsField]
    content: list[SettingsField]
    editing: list[SettingsField]
    limits: list[SettingsField]

    @staticmethod
    def from_settings(s: Settings) -> "SettingsOut":
        def cmd(key: str) -> str:
            return f"asterion plugin config set {PLUGIN_NAME} {key}=<valor>"

        def field(key: str, label: str, value, secret: bool = False) -> SettingsField:
            return SettingsField(
                key=key, label=label,
                value="••••••••" if secret and value else str(value),
                is_secret=secret, set_command=cmd(key),
            )

        return SettingsOut(
            provider=[
                field("PROVIDER_BASE_URL", "URL del proveedor de IA", s.provider_base_url),
                field("PROVIDER_MODEL", "Modelo", s.provider_model),
                field("PROVIDER_TOKEN", "Token", s.provider_token, secret=True),
            ],
            content=[
                field("CONTENT_LANGUAGE", "Idioma (vacío = detectar solo)", s.content_language),
                field("CONTENT_VOCABULARY", "Vocabulario técnico", s.content_vocabulary),
                field("CONTENT_VIDEO_TYPE", "Tipo de contenido", s.content_video_type),
                field("TRANSCRIPTION_MODEL", "Modelo de transcripción", s.transcription_model),
            ],
            editing=[
                field("EDIT_FORMATS", "Formatos de salida", s.edit_formats),
                field("EDIT_SUBTITLE_STYLE", "Estilo de subtítulos", s.edit_subtitle_style),
                field("EDIT_PAUSE_HANDLING", "Tratamiento de pausas", s.edit_pause_handling),
            ],
            limits=[
                field("LIMIT_BUDGET_USD", "Presupuesto por proyecto (USD)", s.limit_budget_usd),
                field("LIMIT_MAX_RETRIES", "Reintentos máximos", s.limit_max_retries),
                field("LIMIT_MAX_STORAGE_GB", "Espacio máximo (GB)", s.limit_max_storage_gb),
            ],
        )
