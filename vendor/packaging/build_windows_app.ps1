# Arma una carpeta "AsterionSocialClips" autocontenida para Windows —
# el equivalente de build_macos_app.sh, pero escrito y NUNCA corrido en
# una máquina Windows real (este entorno de trabajo es exclusivamente
# macOS). No asumas que esto funciona a la primera: es el mejor intento
# posible sin poder probarlo, no una build verificada como la de Mac.
# Si algo falla, el mensaje de error completo + en qué paso pasó es
# justo lo que hace falta para corregirlo.
#
# A diferencia del script de Mac (que solo empaqueta venvs portables ya
# armados y probados en esta misma sesión), este SÍ arma los venvs de
# cero contra Python nativo de Windows — en esta máquina no existe nada
# previamente armado para Windows a partir de lo cual empaquetar.
#
# Requisitos en la PC Windows antes de correr esto:
#   - Windows 10/11 de 64 bits.
#   - PowerShell 5.1+ (ya viene instalado) corrido como usuario normal
#     (no hace falta Administrador).
#   - Conexión a internet (descarga ~1.5GB entre los dos Python
#     portables + ffmpeg).
#   - Esta carpeta del proyecto ya copiada a la PC Windows, CON
#     `vendor/SadTalker/checkpoints/` y `vendor/SadTalker/BFM_Fitting`
#     ya descargados (son archivos de datos, no binarios de Mac — viajan
#     tal cual) y con `frontend/dist/` ya compilado.
#
# Uso (desde una terminal de PowerShell, parada en la raíz del proyecto):
#   powershell -ExecutionPolicy Bypass -File vendor\packaging\build_windows_app.ps1
#
# IMPORTANTE sobre la carpeta de destino: Windows tiene un límite
# clásico de 260 caracteres por ruta (MAX_PATH) que todavía golpea a
# muchas apps si no se habilitó soporte de rutas largas a nivel sistema.
# El árbol de SadTalker (torch, etc.) tiene miles de archivos con
# nombres largos — si esto se instala muy anidado (ej. dentro de varias
# carpetas de OneDrive/Escritorio) algún archivo puntual puede fallar
# al copiarse o instalarse con "path too long" o similar. Por eso el
# resultado de este script conviene MOVERLO a una ruta corta antes de
# usarlo, ej. `C:\AsterionSocialClips\`, no dejarlo donde se construyó.
# Si aun así aparece ese error, habilitar rutas largas una vez (como
# Administrador, requiere reiniciar):
#   New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
#     -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"  # Invoke-WebRequest es muchísimo más lento con la barra de progreso

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$AppName = "AsterionSocialClips"
$BuildDir = Join-Path $ProjectRoot "vendor\packaging\dist-windows"
$AppDir = Join-Path $BuildDir $AppName
$Project = Join-Path $AppDir "project"
$Staging = Join-Path $env:TEMP "asterion-win-build-staging"

$Py314Url = "https://github.com/astral-sh/python-build-standalone/releases/download/20261021/cpython-3.14.9+20261021-x86_64-pc-windows-msvc-install_only.tar.gz"
$Py39Url  = "https://github.com/astral-sh/python-build-standalone/releases/download/20240415/cpython-3.9.19+20240415-x86_64-pc-windows-msvc-install_only.tar.gz"
$FfmpegUrl = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n9.0-latest-win64-gpl-9.0.zip"
$DlibBinWheelUrl = "https://files.pythonhosted.org/packages/58/b2/2e01cee8e3f607f3ba525aabcbf60e46ede116013fbba255c15d4ea066b4/dlib_bin-19.24.6-cp39-cp39-win_amd64.whl"

function Stop-WithMessage($msg) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    exit 1
}

function Test-Robocopy($exitCode) {
    # Robocopy no sigue la convención normal de códigos de salida: 0-7
    # son todos "éxito" (con distintos matices de qué copió), 8+ es un
    # error real. $ErrorActionPreference="Stop" no lo detecta solo.
    if ($exitCode -ge 8) {
        Stop-WithMessage "robocopy terminó con código $exitCode (8 o más es un error real)."
    }
}

Write-Host "== 1/9: verificando que 'tar' esté disponible (viene con Windows 10 1803+/11) =="
if (-not (Get-Command tar -ErrorAction SilentlyContinue)) {
    Stop-WithMessage "No se encontró 'tar' en el PATH. Hace falta para descomprimir los Python portables. Actualizá Windows o instalá bsdtar/7-Zip y adaptá este script."
}

Write-Host "== 2/9: limpiando build anterior =="
if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }
if (Test-Path $Staging) { Remove-Item -Recurse -Force $Staging }
New-Item -ItemType Directory -Force -Path $Project | Out-Null
New-Item -ItemType Directory -Force -Path $Staging | Out-Null

Write-Host "== 3/9: copiando el proyecto (sin dev-only, venvs de Mac, ni datos de usuario) =="
# robocopy /XD con un nombre sin barras excluye ESE NOMBRE en cualquier
# nivel del árbol — bien para carpetas que son siempre basura de build
# (node_modules, __pycache__) pero peligroso para nombres genéricos que
# también existen como código real en otro lado (vendor/SadTalker/src/
# es el código fuente de SadTalker, no se puede confundir con
# frontend/src/) — esos van con ruta completa para que /XD solo mate
# la carpeta exacta, no cualquiera que se llame igual.
$ExcludeDirsByName = @(
    ".git", "tests", "docs", "__pycache__",
    "venv", "venv_homebrew_backup",
    "_runs", "python-runtimes", "ffmpeg-bundle", "packaging",
    "node_modules"
)
$ExcludeDirsByPath = @(
    (Join-Path $ProjectRoot "data"),
    (Join-Path $ProjectRoot "frontend\src")
)
robocopy $ProjectRoot $Project /E /XD ($ExcludeDirsByName + $ExcludeDirsByPath) /XF "*.pyc" ".DS_Store" "tsconfig.tsbuildinfo" /NFL /NDL /NJH /NJS
Test-Robocopy $LASTEXITCODE
# robocopy con /XD "venv" también se salta `apps/api/venv` y
# `vendor/SadTalker/venv` del árbol de Mac a propósito — se arman de
# cero más abajo, nativos de Windows.

Write-Host "== 4/9: verificando que los checkpoints de SadTalker ya estén (no se pueden resolver acá) =="
$CheckpointsOk = (Test-Path (Join-Path $Project "vendor\SadTalker\checkpoints\BFM_Fitting")) -and
                 (Test-Path (Join-Path $Project "frontend\dist\index.html"))
if (-not $CheckpointsOk) {
    Stop-WithMessage "Falta vendor\SadTalker\checkpoints\BFM_Fitting o frontend\dist\index.html en el proyecto de origen. Copiá la carpeta del proyecto completa (con esos datos ya generados) antes de correr este script — ver vendor\SADTALKER_SETUP.md."
}

Write-Host "== 5/9: Python portable para la API (3.14.9) =="
$Py314Tar = Join-Path $Staging "py314.tar.gz"
Invoke-WebRequest -Uri $Py314Url -OutFile $Py314Tar
tar -xzf $Py314Tar -C $Staging
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "tar falló al descomprimir el Python 3.14 portable." }
$ApiVenv = Join-Path $Project "apps\api\venv"
Move-Item (Join-Path $Staging "python") $ApiVenv
$ApiPython = Join-Path $ApiVenv "python.exe"
& $ApiPython -m pip install --upgrade pip
& $ApiPython -m pip install -r (Join-Path $Project "apps\api\requirements.txt")
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "pip install de apps\api\requirements.txt falló." }

Write-Host "== 6/9: Python portable para SadTalker (3.9.19) + torch + dlib-bin =="
$Py39Tar = Join-Path $Staging "py39.tar.gz"
Invoke-WebRequest -Uri $Py39Url -OutFile $Py39Tar
# El de 3.14 ya se movió fuera de $Staging en el paso anterior, así que
# acá "python/" (el nombre que usa python-build-standalone siempre)
# está libre sin necesidad de renombrar nada al extraer.
tar -xzf $Py39Tar -C $Staging
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "tar falló al descomprimir el Python 3.9 portable." }
$SadTalkerVenv = Join-Path $Project "vendor\SadTalker\venv"
Move-Item (Join-Path $Staging "python") $SadTalkerVenv
$SadTalkerPython = Join-Path $SadTalkerVenv "python.exe"
& $SadTalkerPython -m pip install --upgrade pip
# Sin pin de versión, igual que en Mac (instrucciones oficiales) — pip
# resuelve el build CPU para Windows por default (no hace falta un
# --index-url especial salvo que se quiera CUDA).
& $SadTalkerPython -m pip install torch torchvision torchaudio
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "pip install de torch/torchvision/torchaudio falló." }
& $SadTalkerPython -m pip install -r (Join-Path $Project "vendor\SadTalker\requirements.txt")
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "pip install de vendor\SadTalker\requirements.txt falló." }
# dlib real necesita compilar con Visual Studio Build Tools + CMake —
# casi seguro ausente en la máquina de alguien que no programa. dlib-bin
# es el mismo dlib (mismo binding pybind11), empaquetado como wheel
# precompilada — instala el paquete "dlib" real, solo que ya compilado.
$DlibWheel = Join-Path $Staging "dlib_bin.whl"
Invoke-WebRequest -Uri $DlibBinWheelUrl -OutFile $DlibWheel
& $SadTalkerPython -m pip install $DlibWheel
if ($LASTEXITCODE -ne 0) { Stop-WithMessage "pip install de dlib-bin falló — si esto rompe, la alternativa es instalar Visual Studio Build Tools (C++) + CMake y usar 'pip install dlib' a secas, mucho más lento y con más superficie de error." }

Write-Host "== 7/9: parche de compatibilidad torchvision (basicsr/gfpgan todavía usan functional_tensor) =="
$FunctionalTensorPath = Join-Path $SadTalkerVenv "Lib\site-packages\torchvision\transforms\functional_tensor.py"
if (-not (Test-Path $FunctionalTensorPath)) {
    Set-Content -Path $FunctionalTensorPath -Value "from torchvision.transforms.functional import rgb_to_grayscale  # noqa: F401`n" -Encoding utf8
}

Write-Host "== 8/9: ffmpeg/ffprobe estáticos para Windows (BtbN, build GPL con libass/libfreetype) =="
$FfmpegZip = Join-Path $Staging "ffmpeg.zip"
Invoke-WebRequest -Uri $FfmpegUrl -OutFile $FfmpegZip
$FfmpegExtract = Join-Path $Staging "ffmpeg-extract"
Expand-Archive -Path $FfmpegZip -DestinationPath $FfmpegExtract
$FfmpegBinSrc = Get-ChildItem -Path $FfmpegExtract -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if (-not $FfmpegBinSrc) { Stop-WithMessage "No se encontró ffmpeg.exe dentro del zip descargado — puede que BtbN haya cambiado la estructura del release." }
$VendorBin = Join-Path $Project "vendor\bin"
New-Item -ItemType Directory -Force -Path $VendorBin | Out-Null
Copy-Item (Join-Path $FfmpegBinSrc.DirectoryName "ffmpeg.exe") (Join-Path $VendorBin "ffmpeg.exe")
Copy-Item (Join-Path $FfmpegBinSrc.DirectoryName "ffprobe.exe") (Join-Path $VendorBin "ffprobe.exe")

Write-Host "== 9/9: lanzador =="
$LauncherPath = Join-Path $AppDir "Iniciar Asterion Social Clips.bat"
$LauncherContent = @'
@echo off
setlocal
set "DIR=%~dp0project"
set "PATH=%DIR%\vendor\bin;%PATH%"
if not defined ASTERION_PLUGIN_PORT set ASTERION_PLUGIN_PORT=8899
set "LOGDIR=%LOCALAPPDATA%\AsterionSocialClips"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOGFILE=%LOGDIR%\server.log"

cd /d "%DIR%"
start /min "" cmd /c ""%DIR%\apps\api\venv\python.exe" "%DIR%\apps\api\run.py" >> "%LOGFILE%" 2>&1"

echo Iniciando Asterion Social Clips, un momento...
echo (si algo falla, el detalle queda en %LOGFILE%)
set TRIES=0
:waitloop
set /a TRIES+=1
if %TRIES% gtr 120 goto timeout
curl -s -o nul "http://127.0.0.1:%ASTERION_PLUGIN_PORT%/health"
if %ERRORLEVEL% equ 0 goto ready
timeout /t 1 /nobreak >nul
goto waitloop

:ready
start "" "http://127.0.0.1:%ASTERION_PLUGIN_PORT%"
exit /b 0

:timeout
echo No arrancó en 2 minutos. Revisá el detalle en %LOGFILE%.
pause
exit /b 1
'@
Set-Content -Path $LauncherPath -Value $LauncherContent -Encoding ascii

Remove-Item -Recurse -Force $Staging

$SizeGb = [math]::Round(((Get-ChildItem $AppDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1GB), 1)
Write-Host ""
Write-Host "Listo (con reservas, nunca se corrió en una PC Windows real): $AppDir ($SizeGb GB)"
Write-Host "Para usarlo: mover TODA la carpeta '$AppName' a una ruta corta (ej. C:\AsterionSocialClips\) y abrir 'Iniciar Asterion Social Clips.bat'."
