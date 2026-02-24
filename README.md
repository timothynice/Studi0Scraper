# Studi0Scraper

Studi0Scraper is a desktop + CLI website crawler that exports:
- page content as clean Markdown (`content.md`)
- page images into per-page `images/` folders

It supports dark/light theming, appearance presets, and controlled crawl settings.

## Requirements

- macOS (for `.app` build/install scripts)
- Python 3.10+

## Fastest Way To Rebuild + Run

Use this one command:

```bash
./scripts/rebuild_and_run.sh
```

It will:
1. Stop running app instances.
2. Clean old build artifacts.
3. Build a fresh `Studi0Scraper.app`.
4. Install it into `~/Applications`.
5. Launch it.

## Command Reference

```bash
# Create/refresh .venv and install all dependencies
./scripts/bootstrap.sh

# Stop running app instances
./scripts/stop_app.sh

# Remove build artifacts
./scripts/clean.sh

# Build standalone app bundle
./build_macos_app.sh

# Install built app to ~/Applications (build first if missing)
./scripts/install_app.sh --build

# Install and launch
./scripts/install_app.sh --build --launch

# Create distributable zip in release/
./scripts/release_zip.sh
```

Installed app path:

```text
~/Applications/Studi0Scraper.app
```

## Run From Source (No App Bundle)

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
python scraper_app.py
```

## CLI Usage

```bash
python site_scraper.py "https://example.com" --output "./site-export"
```

Useful options:

```bash
python site_scraper.py "https://example.com" \
  --output "./site-export" \
  --max-pages 2000 \
  --delay 0.3 \
  --timeout 20 \
  --include-subdomains

# Content only
python site_scraper.py "https://example.com" --no-images

# Images only
python site_scraper.py "https://example.com" --no-content
```

## Output Layout

```text
site-export/
  crawl-summary.json
  example-com/
    home/
      content.md
      images/
    about/
      content.md
      images/
```

## Notes

- At least one capture mode (images/content) must be enabled.
- `robots.txt` is respected by default; use `--ignore-robots` only when appropriate.
- Build artifacts (`build/`, `dist/`, `release/`) are intentionally not source-controlled.
