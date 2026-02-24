#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf "$ROOT_DIR/build" "$ROOT_DIR/dist" "$ROOT_DIR/release"
