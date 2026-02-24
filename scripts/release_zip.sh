#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_PATH="$ROOT_DIR/release/Studi0Scraper.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Missing build output at $APP_PATH"
  echo "Run ./build_macos_app.sh first."
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
ZIP_PATH="$ROOT_DIR/release/Studi0Scraper-macOS-$STAMP.zip"

ditto -c -k --sequesterRsrc --keepParent "$APP_PATH" "$ZIP_PATH"
echo "Created: $ZIP_PATH"
