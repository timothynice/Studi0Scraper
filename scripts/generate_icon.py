#!/usr/bin/env python3
"""Prepare the canonical 1024x1024 app icon from user-provided artwork."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image

TARGET_SIZE = 1024
OUTPUT_NAME = "studi0scraper-icon-1024.png"
SOURCE_GLOB = "icon-source.*"


def fit_to_square(source: Image.Image, size: int) -> Image.Image:
    source = source.convert("RGBA")
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    scale = min(size / source.width, size / source.height)
    width = max(1, int(round(source.width * scale)))
    height = max(1, int(round(source.height * scale)))
    resized = source.resize((width, height), Image.Resampling.LANCZOS)

    left = (size - width) // 2
    top = (size - height) // 2
    canvas.paste(resized, (left, top), resized)
    return canvas


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    assets_dir = root / "assets"
    source_env = os.environ.get("ICON_SOURCE", "").strip()
    if source_env:
        source_path = Path(source_env).expanduser().resolve()
    else:
        matches = sorted(
            p
            for p in assets_dir.glob(SOURCE_GLOB)
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
        )
        source_path = matches[0] if matches else assets_dir / "icon-source.png"
    out_path = assets_dir / OUTPUT_NAME

    if not source_path.exists():
        raise SystemExit(
            f"Missing source icon: {source_path}\n"
            "Place your artwork at assets/icon-source.(png|jpg|webp|tiff|bmp) and rerun,\n"
            "or set ICON_SOURCE=/absolute/path/to/your/icon.file."
        )

    with Image.open(source_path) as source:
        icon = fit_to_square(source, TARGET_SIZE)
        icon.save(out_path)

    print(f"Source: {source_path}")
    print(f"Wrote:  {out_path}")


if __name__ == "__main__":
    main()
