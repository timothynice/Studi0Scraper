#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Stopping any running WebScraper instances..."
pkill -f '/WebScraper.app/Contents/MacOS/WebScraper|python3? .*scraper_app.py' || true

echo "Cleaning previous build artifacts..."
rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist" "$ROOT_DIR/release/WebScraper.app"

echo "Building app..."
"$ROOT_DIR/build_macos_app.sh"

echo "Launching app..."
open "$ROOT_DIR/release/WebScraper.app"

echo "Done."
