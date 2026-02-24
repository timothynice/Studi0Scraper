#!/usr/bin/env bash
set -euo pipefail

pkill -f '/Studi0Scraper\.app/Contents/MacOS/Studi0Scraper|python(3(\.[0-9]+)?)? .*scraper_app\.py' || true
