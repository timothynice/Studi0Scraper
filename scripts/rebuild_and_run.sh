#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Stopping any running Studi0Scraper instances..."
"$ROOT_DIR/scripts/stop_app.sh"

echo "Cleaning previous build artifacts..."
"$ROOT_DIR/scripts/clean.sh"

echo "Building app..."
"$ROOT_DIR/build_macos_app.sh"

echo "Installing to ~/Applications and launching..."
"$ROOT_DIR/scripts/install_app.sh" --launch

echo "Done."
