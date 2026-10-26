"""Ajustes del plugin, leídos de las variables de entorno que Asterion ya
inyecta al arrancar el proceso (`ASTERION_PLUGIN_CONFIG_<CLAVE>`, una por
cada `Contract.config(...)` de `app.asterion`) — nunca un archivo propio,
nunca un segundo almacén de secretos: `PROVIDER_TOKEN` está declarado
`type="secret"` en el contrato, así que Asterion mismo lo cifra en reposo
(AES-256-GCM) y lo entrega descifrado solo en el entorno de este proceso.
Un `keyring` del sistema acá adentro sería cifrado redundante, y en macOS
dispara el prompt del Llavero — una fricción que ningún otro plugin de
este ecosistema tiene.

Los nombres y los defaults de cada campo tienen que coincidir con los que
declara `app.asterion` — son la misma configuración vista desde dos
lugares, y una se genera a partir de la otra en la mente de quien la
edita, no en el código: si cambiás un default acá, cambialo ahí también.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASTERION_PLUGIN_CONFIG_", extra="ignore")

    # --- Proveedor de IA ---
    provider_base_url: str = "http://127.0.0.1:11434/v1"
    provider_model: str = "llama3.1"
    provider_token: str = ""

    # --- Transcripción / contenido ---
    transcription_model: str = "small"
    content_language: str = ""  # vacío = dejar que faster-whisper lo detecte solo
    content_vocabulary: str = ""  # lista separada por comas, ver content_vocabulary_list
    content_video_type: str = "generic"

    # --- Edición ---
    edit_formats: str = "vertical"  # lista separada por comas, ver edit_formats_list
    edit_subtitle_style: str = "shorts"
    edit_pause_handling: str = "trim"

    # --- Límites ---
    limit_budget_usd: float = 0.0
    limit_max_retries: int = 2
    limit_max_storage_gb: float = 20.0

    # --- Dónde viven los datos de cada proyecto ---
    data_dir: str = ""  # vacío = resuelto por data_dir_path() a <ASTERION_PLUGIN_DIR>/data

    @property
    def content_vocabulary_list(self) -> list[str]:
        return [v.strip() for v in self.content_vocabulary.split(",") if v.strip()]

    @property
    def edit_formats_list(self) -> list[str]:
        return [v.strip() for v in self.edit_formats.split(",") if v.strip()] or ["vertical"]

    def data_dir_path(self) -> Path:
        """La carpeta de datos NUNCA vive adentro del árbol de código que
        `plugin build`/`plugin update` tocan — ver el layout de proyecto
        en `packages/storage/layout.py`. Sin `data_dir` configurado,
        cae en `<carpeta del plugin>/data`, afuera de `apps/`/`packages/`
        pero todavía autocontenida (un plugin --link no depende de que
        exista una carpeta fuera de sí mismo para arrancar la primera
        vez)."""
        if self.data_dir:
            return Path(self.data_dir).expanduser().resolve()
        plugin_dir = os.environ.get("ASTERION_PLUGIN_DIR", ".")
        return (Path(plugin_dir) / "data").resolve()


@lru_cache
def get_settings() -> Settings:
    # cacheado: Settings() relee el entorno una sola vez por proceso.
    # Asterion no soporta reconfigurar un plugin en caliente todavía
    # (`plugin config set` + `plugin restart` es el camino), así que no
    # hay necesidad real de invalidar este caché en runtime.
    return Settings()
