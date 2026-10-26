#!/usr/bin/env bash
# Arma "Asterion Social Clips.app" — una app de escritorio macOS/arm64
# autocontenida: Python portable (apps/api/venv, vendor/SadTalker/venv,
# ya reconstruidos con python-build-standalone, sin depender de
# Homebrew), ffmpeg/ffprobe estáticos, el frontend ya compilado, los
# checkpoints de SadTalker y las voces de Piper. Alguien que nunca
# programó la abre haciendo doble click — no instala Python, Node,
# ffmpeg ni nada aparte.
#
# Uso: bash vendor/packaging/build_macos_app.sh

set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP_NAME="Asterion Social Clips"
BUILD_DIR="$PROJECT_ROOT/vendor/packaging/dist"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
RES_PROJECT="$APP_DIR/Contents/Resources/project"

echo "== 1/6: limpiando build anterior =="
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

echo "== 2/6: copiando el proyecto (sin dev-only ni datos de usuario) =="
mkdir -p "$RES_PROJECT"
rsync -a "$PROJECT_ROOT/" "$RES_PROJECT/" \
  --exclude ".git/" \
  --exclude "data/" \
  --exclude "tests/" \
  --exclude "docs/" \
  --exclude "__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".DS_Store" \
  --exclude "apps/api/venv_homebrew_backup/" \
  --exclude "vendor/SadTalker/.git/" \
  --exclude "vendor/SadTalker/venv_homebrew_backup/" \
  --exclude "vendor/SadTalker/_runs/" \
  --exclude "vendor/python-runtimes/" \
  --exclude "vendor/ffmpeg-bundle/" \
  --exclude "vendor/packaging/" \
  --exclude "frontend/node_modules/" \
  --exclude "frontend/src/" \
  --exclude "frontend/tsconfig.tsbuildinfo"

echo "== 3/6: ffmpeg/ffprobe estáticos (sin dependencias de Homebrew) =="
mkdir -p "$RES_PROJECT/vendor/bin"
cp "$PROJECT_ROOT/vendor/ffmpeg-bundle/ffmpeg" "$RES_PROJECT/vendor/bin/ffmpeg"
cp "$PROJECT_ROOT/vendor/ffmpeg-bundle/ffprobe" "$RES_PROJECT/vendor/bin/ffprobe"
chmod +x "$RES_PROJECT/vendor/bin/ffmpeg" "$RES_PROJECT/vendor/bin/ffprobe"

echo "== 4/6: Info.plist =="
cat > "$APP_DIR/Contents/Info.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Asterion Social Clips</string>
  <key>CFBundleDisplayName</key><string>Asterion Social Clips</string>
  <key>CFBundleIdentifier</key><string>dev.asterion.socialclips</string>
  <key>CFBundleVersion</key><string>0.1.0</string>
  <key>CFBundleShortVersionString</key><string>0.1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.video</string>
</dict>
</plist>
EOF

echo "== 5/6: lanzador =="
cat > "$APP_DIR/Contents/MacOS/launch" << 'EOF'
#!/bin/bash
# Arranca el backend (venv portable, sin Asterion CLI de por medio) y
# abre el navegador apenas responde /health. stdout/stderr van a un log
# en ~/Library/Logs para poder diagnosticar sin terminal.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../Resources/project" && pwd)"
LOG_DIR="$HOME/Library/Logs/AsterionSocialClips"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/server.log"

export PATH="$DIR/vendor/bin:$PATH"
PORT="${ASTERION_PLUGIN_PORT:-8899}"

cd "$DIR"
"$DIR/apps/api/venv/bin/python" "$DIR/apps/api/run.py" >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 120); do
  if curl -s "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    open "http://127.0.0.1:$PORT"
    break
  fi
  sleep 1
done

wait "$SERVER_PID"
EOF
chmod +x "$APP_DIR/Contents/MacOS/launch"

echo "== 6/6: firma ad-hoc (Apple Silicon no corre binarios sin firmar) =="
codesign --force --deep --sign - "$APP_DIR" 2>&1 | tail -5

du -sh "$APP_DIR"
echo "Listo: $APP_DIR"
