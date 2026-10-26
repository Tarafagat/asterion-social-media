# Empaquetado como app de escritorio

Dos scripts, uno por plataforma, para armar una carpeta/`.app`
autocontenida que alguien sin Python/Node/ffmpeg instalado puede abrir
con un doble click. Ninguno de los dos sube nada a ningún lado — todo
queda en `vendor/packaging/dist*/` en esta misma máquina.

## macOS (`build_macos_app.sh`) — verificado en vivo

```bash
bash vendor/packaging/build_macos_app.sh
```

Produce `vendor/packaging/dist/Asterion Social Clips.app`. Probado de
punta a punta en esta Mac (M1 Pro/arm64): arranca desde una carpeta
relocada, sirve el frontend y la API, genera voz real con Piper, y
anima un avatar real con SadTalker — con el venv portable, sin Homebrew
de por medio.

**Primera apertura — Gatekeeper.** La app tiene firma ad-hoc (obligatoria
en Apple Silicon para que el binario corra), pero no está notarizada
por Apple (eso requiere una cuenta de desarrollador paga). La primera
vez que alguien la abra después de bajarla/copiarla de otro lado, macOS
va a decir "no se puede abrir porque no se pudo verificar al
desarrollador". Eso se resuelve una sola vez:

1. Click derecho sobre `Asterion Social Clips.app` → **Abrir**.
2. En el diálogo, click en **Abrir** de nuevo (esta vez sí deja).

Las aperturas siguientes son un doble click normal, sin volver a pedirlo.

## Windows (`build_windows_app.ps1`) — sin verificar, alto riesgo

**Esto nunca se corrió en una PC Windows real** — este entorno de
trabajo es exclusivamente macOS, sin acceso a una máquina ni VM
Windows, así que no hay forma de probarlo desde acá. Es el mejor
intento posible por analogía con la build de Mac (mismas piezas:
Python portable de `python-build-standalone`, ffmpeg estático, el mismo
código de la app sin cambios salvo dos fixes reales — ver abajo), pero
hay que asumir que la primera corrida va a necesitar ajustes.

```powershell
powershell -ExecutionPolicy Bypass -File vendor\packaging\build_windows_app.ps1
```

Correrlo desde una copia del proyecto YA con
`vendor\SadTalker\checkpoints\` (con `BFM_Fitting` adentro) y
`frontend\dist\` ya presentes — son datos, viajan tal cual desde esta
Mac, no hace falta regenerarlos en Windows.

### Qué puede salir mal (en orden de probabilidad)

1. **dlib**: en vez de compilar dlib desde cero (necesita Visual Studio
   Build Tools + CMake, que alguien sin conocimientos de programación
   casi seguro no tiene instalado), el script instala `dlib-bin`, una
   wheel precompilada del mismo dlib. Si esa wheel específica
   (`19.24.6`, cp39/win_amd64) dejó de existir o da error, revisar
   https://pypi.org/project/dlib-bin/#files por una versión más nueva
   para cp39 y actualizar la URL en el script.
2. **Alguna dependencia pinneada sin wheel para Windows**: la mayoría
   de `vendor/SadTalker/requirements.txt` son paquetes viejos (2022-23)
   — se asume que tienen wheels de Windows porque SadTalker se usa en
   Windows en su comunidad, pero no se verificó paquete por paquete.
3. **Rutas largas de Windows (MAX_PATH)**: ver el aviso dentro del
   propio script — mover el resultado a una carpeta corta como
   `C:\AsterionSocialClips\` antes de usarlo, y si aun así aparece un
   error de "ruta demasiado larga", habilitar rutas largas a nivel
   sistema (instrucciones en el script).
4. **BtbN cambia la estructura de su release de ffmpeg**: el script
   busca `ffmpeg.exe` recursivamente dentro del .zip bajado, así que
   zips con otra estructura interna deberían seguir andando, pero si el
   *nombre del archivo* del release cambió (`ffmpeg-n9.0-latest-win64-gpl-9.0.zip`)
   hay que actualizar `$FfmpegUrl`.

Si algo de esto (o cualquier otra cosa) falla, lo más útil es el texto
completo del error + en qué paso (`== N/9: ... ==`) pasó.

### Dos fixes reales que SÍ viajan sin cambios, porque viven en el código de la app

Encontrados armando y verificando la build de Mac — no son hacks del
script de empaquetado, están en `packages/avatar/`:

- **`tts_piper.py`** — el binding compilado de espeak-ng (que usa Piper
  para la voz) trunca cualquier ruta de más de ~160 caracteres y cae en
  silencio a una ruta de la máquina de CI que compiló el paquete,
  rompiendo la síntesis de voz en CUALQUIER instalación empaquetada (la
  ruta siempre es larga por lo anidada). El fix copia los datos de
  espeak a una carpeta corta y estable en la carpeta temporal del
  sistema — funciona igual en macOS, Linux y Windows.
- **`sadtalker_runner.py`** — antes asumía `venv/bin/python` (POSIX).
  En Windows, python-build-standalone deja `python.exe` en la raíz del
  venv, sin carpeta `bin/`. Ahora prueba ambas rutas.

### Primera apertura — SmartScreen

Mismo tipo de fricción que Gatekeeper en Mac: Windows va a avisar
"Windows protegió su PC" por ser un ejecutable sin firma de un
publicador reconocido (firmar para Windows también requiere un
certificado pago). Se resuelve con **Más información** → **Ejecutar de
todas formas**, una sola vez.

## Qué queda afuera, a propósito

- **Linux**: no se armó ningún build — este entorno es macOS y no puede
  correr contenedores Linux reales para probar algo equivalente (sí
  podría, en principio, usarse Docker Desktop para un build *Linux* real
  y verificable desde acá si hace falta más adelante; es un pedido
  aparte).
- **Firma/notarización paga** (Apple Developer ID, certificado de
  Authenticode de Windows): eliminaría el aviso de Gatekeeper/SmartScreen
  por completo, pero son trámites y costos fuera del alcance de este
  empaquetado.
- **.dmg para Mac / instalador .msi para Windows**: por ahora es una
  carpeta/`.app` que se copia y listo — un instalador de verdad es un
  paso más que no se hizo todavía.
