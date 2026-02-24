#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

echo "Bootstrap complete. Activate with: source .venv/bin/activate"
