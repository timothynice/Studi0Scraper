# Site Content + Image Scraper

Crawls a website from a base URL, visits internal pages, and saves content/images in organized per-page folders.

## What it does

- Crawls internal links one page at a time (BFS crawl).
- Creates one folder per page based on URL path.
- Saves:
  - `content.md` (formatted markdown of visible page content)
  - `images/` (downloaded image files)
- Tries to pick high-res image variants from `srcset` and Squarespace image URLs.
- Writes a `crawl-summary.json` at the output root.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python site_scraper.py "https://your-site.com" --output "./site-export"
```

## Basic mac app UI

You can run a simple desktop app wrapper to choose URL + destination folder and start/stop a crawl:

```bash
source .venv/bin/activate
python scraper_app.py
```

The app uses your current Python environment and runs the crawler directly in the app process.

## Build standalone `.app` (macOS)

Build a distributable app bundle with icon assets:

```bash
cd /Users/TimNice/Development/WebScraper
./build_macos_app.sh
```

Output app:

- `/Users/TimNice/Development/WebScraper/release/WebScraper.app`

## Useful options

```bash
python site_scraper.py "https://your-site.com" \
  --output "./site-export" \
  --max-pages 5000 \
  --delay 0.2 \
  --timeout 30 \
  --include-subdomains
```

Capture controls:

```bash
# Capture only content markdown
python site_scraper.py "https://your-site.com" --no-images

# Capture only images
python site_scraper.py "https://your-site.com" --no-content
```

Ignore robots.txt only if you own the site and explicitly want that behavior:

```bash
python site_scraper.py "https://your-site.com" --ignore-robots
```

If your local environment has TLS certificate chain issues, you can bypass verification:

```bash
python site_scraper.py "https://your-site.com" --insecure
```

## Troubleshooting

If you see this pattern:

- `[skip robots] https://...`
- `"pages_processed": 0`

it means robots rules prevented crawling your starting URL. If this is your own site and you explicitly want to export it anyway, run with:

```bash
python site_scraper.py "https://your-site.com" --ignore-robots
```

## Output layout

```text
site-export/
  crawl-summary.json
  your-site-com/
    home/
      content.md
      images/
        hero-image.jpg
    about/
      content.md
      images/
        team-photo.jpg
```

## Notes for Squarespace

- Squarespace often serves responsive image URLs (`?format=750w`, `?format=1500w`, etc.).
- This scraper attempts to request larger variants (`2500w`) when available.
- Not every asset can be recovered at original upload resolution; this depends on how Squarespace stores/serves the asset.

## Next improvements (optional)

- Add resume mode (skip already-saved pages).
- Add hash-based dedupe across the entire site.
- Add Playwright fallback for JS-rendered galleries.
