#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Studi0Scraper.app"
SOURCE_APP="$ROOT_DIR/release/$APP_NAME"
TARGET_DIR="$HOME/Applications"
TARGET_APP="$TARGET_DIR/$APP_NAME"
LAUNCH=false
BUILD_IF_MISSING=false

for arg in "$@"; do
  case "$arg" in
    --launch)
      LAUNCH=true
      ;;
    --build)
      BUILD_IF_MISSING=true
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Usage: $0 [--build] [--launch]"
      exit 2
      ;;
  esac
done

if [[ ! -d "$SOURCE_APP" ]]; then
  if [[ "$BUILD_IF_MISSING" == "true" ]]; then
    "$ROOT_DIR/build_macos_app.sh"
  else
    echo "Missing build output: $SOURCE_APP"
    echo "Run ./build_macos_app.sh first or use --build."
    exit 1
  fi
fi

mkdir -p "$TARGET_DIR"
rm -rf "$TARGET_APP"
cp -R "$SOURCE_APP" "$TARGET_APP"

echo "Installed: $TARGET_APP"

if [[ "$LAUNCH" == "true" ]]; then
  open "$TARGET_APP"
fi
