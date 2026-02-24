#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

SYS_PY="$(command -v python3 || command -v python)"
if [[ -z "$SYS_PY" ]]; then
  echo "python3/python not found on PATH"
  exit 1
fi

if [[ ! -d ".venv" ]]; then
  "$SYS_PY" -m venv .venv
fi

if [[ -x ".venv/bin/python3" ]]; then
  PY_BIN=".venv/bin/python3"
elif [[ -x ".venv/bin/python" ]]; then
  PY_BIN=".venv/bin/python"
else
  echo "No Python interpreter found in .venv/bin"
  exit 1
fi

"$PY_BIN" -m pip install --upgrade pip
"$PY_BIN" -m pip install -r requirements.txt -r requirements-build.txt
"$PY_BIN" scripts/generate_icon.py

ICONSET_DIR="assets/WebScraper.iconset"
ICON_ICNS="assets/WebScraper.icns"

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" assets/webscraper-icon-1024.png --out "$ICONSET_DIR/icon_${size}x${size}.png" >/dev/null
  scale2=$((size * 2))
  sips -z "$scale2" "$scale2" assets/webscraper-icon-1024.png --out "$ICONSET_DIR/icon_${size}x${size}@2x.png" >/dev/null
done

iconutil -c icns "$ICONSET_DIR" -o "$ICON_ICNS"

"$PY_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "WebScraper" \
  --icon "$ICON_ICNS" \
  --add-data "assets/gear-outline-dark.png:assets" \
  --add-data "assets/gear-outline-light.png:assets" \
  scraper_app.py

mkdir -p release
rm -rf release/WebScraper.app
cp -R dist/WebScraper.app release/WebScraper.app

printf "\nBuild complete:\n%s\n" "$ROOT_DIR/release/WebScraper.app"
