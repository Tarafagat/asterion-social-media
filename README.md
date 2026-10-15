# Asterion Social Clips

Genera clips/shorts a partir de un video largo: transcribe, analiza con IA,
recorta, encuadra y subtitula. Empieza por el caso más simple (un video →
una galería de shorts verticales) con un diseño pensado para sumar otras
redes y formatos después, no solo YouTube.

Se instala y corre como **un plugin de Asterion** — nunca como una app de
Electron aparte. Reusa todo lo que `asterion-core` ya sabe hacer con un
plugin: `install --link`, `build` (`pnpm install && pnpm build` del
frontend, solo), `start`/`stop`/`restart`, `config set` (con el asistente
interactivo), `doctor`, `logs`.

## Decisiones de arquitectura (y por qué)

- **Un solo proceso, no tres.** El pipeline original se pensó como
  `apps/api` + `apps/worker` + `apps/web` corriendo por separado. El
  contrato de plugin de Asterion asume un único `start.command` HTTP, así
  que el worker vive **adentro** del mismo proceso FastAPI, como un hilo
  nativo de Python (no una tarea `asyncio` — `ffmpeg`/`faster-whisper` son
  llamadas bloqueantes, y meterlas en el event loop dejaría la API sin
  responder mientras un job procesa). Ver `apps/worker/app/runner.py`.
- **`frontend/`, no `apps/web/`.** `asterion plugin build` busca
  literalmente `frontend/package.json` en la raíz del plugin para
  compilar el frontend solo — es lo que deja que todo esto sea "simple
  con Asterion" de verdad, en vez de un paso de `pnpm build` manual
  aparte.
- **Sin `keyring` propio.** El token del proveedor de IA (`PROVIDER_
  TOKEN`) está declarado `type="secret"` en `app.asterion` — Asterion
  mismo lo cifra en reposo (AES-256-GCM) y lo entrega descifrado solo en
  el entorno del proceso. Un `keyring` del sistema acá adentro sería
  cifrado redundante, y en macOS dispara el prompt del Llavero.
- **SQLite + hilo nativo, sin Redis ni microservicios** — tal cual pedía
  el diseño original. Una cola de un solo worker no necesita más que una
  tabla con `status='queued'`.
- **El heurístico (`packages/ai/providers/heuristic.py`) no es un
  placeholder — es un proveedor real, sin IA, siempre disponible.** Deja
  probar el pipeline completo (transcribir → analizar → seleccionar →
  planificar → renderizar → validar) sin configurar ningún proveedor de
  IA. Con `PROVIDER_BASE_URL` configurado (el default apunta a un ollama
  local), se usa el proveedor HTTP real en su lugar — nunca cae en
  silencio al heurístico si el HTTP falla, eso sería esconder un error
  real.

## Requisitos

- Python 3.11+ (probado en vivo con 3.14).
- Node 18+ y `pnpm` (para el frontend).
- **`ffmpeg` con `libass` compilado** (el filtro `subtitles`). El
  `ffmpeg` default de Homebrew en macOS **no lo trae** — hace falta
  `brew install ffmpeg-full && brew link --overwrite ffmpeg-full`. En
  la mayoría de las distros Linux, el paquete `ffmpeg` del gestor de
  paquetes ya lo incluye. El plugin lo detecta solo y corta con un error
  claro (`SubtitleFilterMissingError`) antes de intentar un render que
  fallaría igual, en vez de un error críptico de parseo de filtergraph
  de ffmpeg.

## Instalar

```bash
asterion plugin install /ruta/a/asterion-social-media --link --name social-clips
asterion plugin config set social-clips   # asistente interactivo
asterion plugin build social-clips        # venv + pnpm install/build del frontend
asterion plugin start social-clips
```

## Verificado en vivo (no solo compilado)

Pipeline completo, de punta a punta, contra audio/video sintéticos
generados con `say`+`ffmpeg` en esta máquina: inspeccionar → extraer
audio → transcribir (`faster-whisper`, modelo real) → analizar
(heurístico) → seleccionar → planificar → renderizar (recorte +
encuadre vertical 1080×1920 + subtítulos quemados con el preset
`shorts.yaml`) → validar. Confirmado con un frame extraído del .mp4
resultante (el subtítulo se ve quemado, con la tipografía/color/posición
del preset) y con la transcripción forzando `CONTENT_LANGUAGE=en`
contra el texto real dicho por `say` (coincide exacto). UI verificada
con Playwright contra el backend real: crear proyecto → subir video →
"Crear clips" → ver la galería con el clip reproducible.

Instalado, compilado y arrancado por el camino real de Asterion
(`plugin install --link` → `plugin build` → `plugin start`) — no solo
corrido a mano con `python run.py`. `asterion doctor social-clips`
corre limpio.

## Bugs reales encontrados en el camino

- `faster-whisper` 1.2.1 rompe contra la versión más nueva de `av`
  (PyAV) instalada por default — `av==18.1.0` fijado en
  `apps/api/requirements.txt`, ver el comentario ahí.
- `packages/media/render.py` asumía que el filtro `subtitles` siempre
  está disponible — no es cierto en el `ffmpeg` default de Homebrew en
  macOS. Ahora se detecta antes de intentar el render
  (`require_subtitle_filter()`), con un mensaje que dice exactamente
  qué instalar.

## Lo que falta (a propósito, no por descuido)

- **`TranscriptEditor`**: el componente está listado en el árbol
  original pero no se construyó todavía — hoy la transcripción no se
  puede editar a mano desde la UI antes de generar los clips.
- **`HttpLLMProvider` nunca se probó contra un modelo real** (ningún
  proveedor con credenciales configurado en este entorno) — el cliente
  está escrito y probado por tipos/validación, pero la llamada HTTP en
  sí (`packages/ai/providers/http_llm.py`) solo se verificó contra un
  endpoint inexistente (confirma que el error de conexión es claro, no
  que una respuesta real se parsee bien).
- **Un solo tipo de red social de verdad (shorts tipo YouTube/TikTok/
  Reels — el layout `vertical` + subtítulos quemados).** El diseño
  (`layout`/`subtitle_style` por servicio, `packages/ai/schemas`) ya
  deja lugar para otros formatos; agregar una red nueva es, hoy, un
  preset de `presets/` más el layout correspondiente en
  `LAYOUT_DIMENSIONS` — no un cambio de arquitectura.
- **`EDIT_PAUSE_HANDLING`** está declarado en `app.asterion` y se
  muestra en Ajustes, pero ninguna etapa del pipeline todavía lo lee.
