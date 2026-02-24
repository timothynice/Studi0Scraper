#!/usr/bin/env python3
"""Crawl a site and download page images into per-page folders.

Designed for static/content-heavy sites such as Squarespace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import re
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import parse_qs, quote, unquote, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, Tag
from requests.packages.urllib3.exceptions import InsecureRequestWarning

try:
    from markdownify import markdownify as to_markdown
except ImportError:  # pragma: no cover - fallback path when dependency is absent
    to_markdown = None

USER_AGENT = "site-scraper/1.0 (+https://example.local)"
PAGE_EXTENSIONS = {".html", ".htm", ""}
IMAGE_MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/avif": ".avif",
    "image/heic": ".heic",
    "image/heif": ".heif",
}
CONTENT_EXCLUDE_TAGS = (
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    "canvas",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "iframe",
)


@dataclass(frozen=True)
class ImageCandidate:
    url: str
    width_hint: int
    hint_name: str


def slugify(text: str, fallback: str = "item") -> str:
    text = unquote(text).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or fallback


def normalize_netloc(netloc: str) -> str:
    return netloc.lower().split(":")[0]


def build_allowed_hosts(base_url: str, include_subdomains: bool) -> Set[str]:
    host = normalize_netloc(urlparse(base_url).netloc)
    hosts = {host}
    if host.startswith("www."):
        hosts.add(host[4:])
    else:
        hosts.add(f"www.{host}")
    return hosts


def is_internal_url(url: str, allowed_hosts: Set[str], include_subdomains: bool) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False

    host = normalize_netloc(parsed.netloc)
    if host in allowed_hosts:
        return True

    if include_subdomains:
        return any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts)
    return False


def strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ""))


def normalize_page_url(url: str, drop_query: bool = True) -> str:
    parsed = urlparse(strip_fragment(url))
    path = parsed.path or "/"

    if path != "/" and path.endswith("/"):
        path = path[:-1]

    if drop_query:
        query = ""
    else:
        query = parsed.query

    return urlunparse((parsed.scheme.lower(), normalize_netloc(parsed.netloc), path, "", query, ""))


def should_crawl_url(url: str) -> bool:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext and ext not in PAGE_EXTENSIONS:
        return False
    return True


def page_folder_for_url(output_root: Path, host: str, page_url: str) -> Path:
    parsed = urlparse(page_url)
    raw_segments = [seg for seg in parsed.path.split("/") if seg]

    if not raw_segments:
        segments = ["home"]
    else:
        segments = []
        for raw in raw_segments:
            stem = Path(raw).stem
            segments.append(slugify(stem, fallback="page"))

    page_dir = output_root / slugify(host, fallback="site") / Path(*segments)
    page_dir.mkdir(parents=True, exist_ok=True)
    return page_dir


def select_visible_content_root(soup: BeautifulSoup) -> Tag:
    for selector in ("main", "article", "[role='main']", "body"):
        candidate = soup.select_one(selector)
        if isinstance(candidate, Tag) and candidate.get_text(" ", strip=True):
            return candidate

    body = soup.body
    if isinstance(body, Tag):
        return body

    html = soup.find("html")
    if isinstance(html, Tag):
        return html

    fallback = soup.find(True)
    if isinstance(fallback, Tag):
        return fallback

    raise ValueError("No page content found")


def cleanup_content_tree(root: Tag) -> None:
    for tag in root.find_all(CONTENT_EXCLUDE_TAGS):
        tag.decompose()

    for tag in root.find_all(True):
        if tag.get("aria-hidden") == "true" or tag.get("hidden") is not None:
            tag.decompose()
            continue

        style = (tag.get("style") or "").replace(" ", "").lower()
        if "display:none" in style or "visibility:hidden" in style:
            tag.decompose()


def normalize_markdown(markdown: str) -> str:
    lines = [line.rstrip() for line in markdown.replace("\r\n", "\n").split("\n")]
    cleaned: List[str] = []
    blank_count = 0
    for line in lines:
        if line.strip():
            blank_count = 0
            cleaned.append(line)
            continue
        blank_count += 1
        if blank_count <= 2:
            cleaned.append("")
    return "\n".join(cleaned).strip() + "\n"


def build_page_markdown(html: str, page_url: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    title_text = ""
    if soup.title and soup.title.get_text(strip=True):
        title_text = soup.title.get_text(" ", strip=True)
    if not title_text:
        title_text = Path(urlparse(page_url).path).name or normalize_netloc(urlparse(page_url).netloc)

    content_root = select_visible_content_root(soup)
    content_soup = BeautifulSoup(str(content_root), "html.parser")
    render_root = select_visible_content_root(content_soup)
    cleanup_content_tree(render_root)

    if to_markdown is None:
        markdown_body = normalize_markdown(render_root.get_text("\n", strip=True))
    else:
        markdown_body = to_markdown(
            str(render_root),
            heading_style="ATX",
            bullets="-",
            autolinks=True,
        )
        markdown_body = normalize_markdown(markdown_body)

    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    header = f"# {title_text}\n\nSource: {page_url}\nCaptured: {captured_at}\n\n"
    return header + markdown_body


def parse_srcset(srcset: str, base_url: str, hint_name: str) -> List[ImageCandidate]:
    candidates: List[ImageCandidate] = []
    for part in srcset.split(","):
        piece = part.strip()
        if not piece:
            continue

        fields = piece.split()
        image_url = fields[0]
        width_hint = 0
        if len(fields) > 1 and fields[1].endswith("w") and fields[1][:-1].isdigit():
            width_hint = int(fields[1][:-1])

        absolute_url = urljoin(base_url, image_url)
        candidates.append(ImageCandidate(url=absolute_url, width_hint=width_hint, hint_name=hint_name))
    return candidates


def parse_inline_style_urls(style_text: str, base_url: str, hint_name: str) -> List[ImageCandidate]:
    urls: List[ImageCandidate] = []
    for match in re.findall(r"url\(([^)]+)\)", style_text or ""):
        cleaned = match.strip().strip('"').strip("'")
        if cleaned:
            urls.append(ImageCandidate(url=urljoin(base_url, cleaned), width_hint=0, hint_name=hint_name))
    return urls


def image_identity_key(url: str) -> str:
    """Normalize image URL so resized/query variants map to one identity."""
    parsed = urlparse(strip_fragment(url))
    normalized_query = parse_qs(parsed.query, keep_blank_values=True)

    # Common responsive/transformation params that produce the same underlying asset.
    for key in (
        "format",
        "w",
        "h",
        "width",
        "height",
        "dpr",
        "quality",
        "q",
        "fit",
        "crop",
        "auto",
        "ixlib",
        "rect",
    ):
        normalized_query.pop(key, None)

    pairs: List[Tuple[str, str]] = []
    for key in sorted(normalized_query.keys()):
        values = normalized_query[key]
        for value in sorted(values):
            pairs.append((key, value))

    query = urlencode(pairs, doseq=True, quote_via=quote) if pairs else ""
    return urlunparse((parsed.scheme.lower(), normalize_netloc(parsed.netloc), parsed.path, "", query, ""))


def squarespace_upgrade(url: str) -> Tuple[str, int]:
    """Try to push Squarespace resized URLs to larger variants.

    Squarespace image URLs often include query param `format=NNNNw`.
    """

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return url, 0

    host = normalize_netloc(parsed.netloc)
    if "squarespace" not in host and "sqspcdn" not in host:
        return url, 0

    query = parse_qs(parsed.query, keep_blank_values=True)
    width_hint = 0

    if "format" in query and query["format"]:
        current = query["format"][0]
        match = re.match(r"^(\d+)w$", current)
        if match:
            width_hint = int(match.group(1))
            if width_hint < 2500:
                query["format"] = ["2500w"]
                rebuilt_query = urlencode(query, doseq=True, quote_via=quote)
                upgraded = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, rebuilt_query, ""))
                return upgraded, 2500

    return url, width_hint


def build_candidates_from_tag(tag: Tag, base_url: str, hint_name: str) -> List[ImageCandidate]:
    candidates: List[ImageCandidate] = []

    for attr in ("srcset", "data-srcset"):
        raw_srcset = tag.get(attr)
        if raw_srcset:
            candidates.extend(parse_srcset(raw_srcset, base_url, hint_name))

    for attr in ("src", "data-src", "data-image", "data-original", "data-image-url"):
        raw = tag.get(attr)
        if raw:
            candidates.append(ImageCandidate(url=urljoin(base_url, raw), width_hint=0, hint_name=hint_name))

    style_value = tag.get("style")
    if style_value:
        candidates.extend(parse_inline_style_urls(style_value, base_url, hint_name))

    upgraded: List[ImageCandidate] = []
    for candidate in candidates:
        upgraded_url, upgraded_width = squarespace_upgrade(candidate.url)
        upgraded.append(
            ImageCandidate(
                url=upgraded_url,
                width_hint=max(candidate.width_hint, upgraded_width),
                hint_name=candidate.hint_name,
            )
        )
    return upgraded


def pick_best_candidate(candidates: Iterable[ImageCandidate]) -> Optional[ImageCandidate]:
    best: Optional[ImageCandidate] = None
    for cand in candidates:
        if cand.url.startswith("data:"):
            continue
        if best is None or cand.width_hint > best.width_hint:
            best = cand
    return best


def extract_page_images(soup: BeautifulSoup, page_url: str) -> List[ImageCandidate]:
    selected: List[ImageCandidate] = []
    seen_keys: Set[str] = set()

    processed_imgs: Set[int] = set()

    for picture in soup.find_all("picture"):
        hint = "image"
        img = picture.find("img")
        if isinstance(img, Tag):
            processed_imgs.add(id(img))
            hint = img.get("alt") or Path(urlparse(page_url).path).name or "image"

        candidates: List[ImageCandidate] = []
        for child in picture.find_all(["source", "img"]):
            if not isinstance(child, Tag):
                continue
            candidates.extend(build_candidates_from_tag(child, page_url, hint))

        best = pick_best_candidate(candidates)
        if best:
            key = image_identity_key(best.url)
            if key in seen_keys:
                continue
            selected.append(best)
            seen_keys.add(key)

    for img in soup.find_all("img"):
        if id(img) in processed_imgs:
            continue
        if not isinstance(img, Tag):
            continue

        hint = img.get("alt") or Path(urlparse(page_url).path).name or "image"
        best = pick_best_candidate(build_candidates_from_tag(img, page_url, hint))
        if best:
            key = image_identity_key(best.url)
            if key in seen_keys:
                continue
            selected.append(best)
            seen_keys.add(key)

    for meta in soup.find_all("meta"):
        if not isinstance(meta, Tag):
            continue
        prop = (meta.get("property") or "").lower()
        name = (meta.get("name") or "").lower()
        if prop in {"og:image", "og:image:url"} or name in {"twitter:image", "twitter:image:src"}:
            content = meta.get("content")
            if content:
                absolute = urljoin(page_url, content)
                upgraded_url, upgraded_width = squarespace_upgrade(absolute)
                key = image_identity_key(upgraded_url)
                if key not in seen_keys:
                    selected.append(ImageCandidate(url=upgraded_url, width_hint=upgraded_width, hint_name="social-image"))
                    seen_keys.add(key)

    for style_tag in soup.find_all("style"):
        if not isinstance(style_tag, Tag):
            continue
        text = style_tag.string or style_tag.get_text(strip=False)
        for candidate in parse_inline_style_urls(text or "", page_url, "style-image"):
            if candidate.url.startswith("data:"):
                continue
            key = image_identity_key(candidate.url)
            if key in seen_keys:
                continue
            upgraded_url, upgraded_width = squarespace_upgrade(candidate.url)
            selected.append(ImageCandidate(url=upgraded_url, width_hint=upgraded_width, hint_name="style-image"))
            seen_keys.add(key)

    return selected


def extract_page_links(soup: BeautifulSoup, page_url: str, allowed_hosts: Set[str], include_subdomains: bool) -> List[str]:
    links: List[str] = []
    seen: Set[str] = set()

    for anchor in soup.find_all("a"):
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if not href:
            continue
        href = href.strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        absolute = urljoin(page_url, href)
        normalized = normalize_page_url(absolute)
        if normalized in seen:
            continue
        if not is_internal_url(normalized, allowed_hosts, include_subdomains):
            continue
        if not should_crawl_url(normalized):
            continue

        seen.add(normalized)
        links.append(normalized)

    return links


def infer_extension(url: str, content_type: str) -> str:
    path_ext = Path(urlparse(url).path).suffix.lower()
    if path_ext and len(path_ext) <= 5:
        return path_ext

    if content_type:
        ctype = content_type.split(";")[0].strip().lower()
        if ctype in IMAGE_MIME_TO_EXT:
            return IMAGE_MIME_TO_EXT[ctype]
        guessed = mimetypes.guess_extension(ctype)
        if guessed:
            return guessed

    return ".bin"


def build_image_filename(candidate: ImageCandidate, existing: Set[str], content_type: str) -> str:
    parsed = urlparse(candidate.url)
    original_name = Path(parsed.path).stem
    base_name = slugify(candidate.hint_name or original_name or "image", fallback="image")

    if base_name in {"image", "social-image", "style-image"} and original_name:
        fallback = slugify(original_name, fallback="image")
        if fallback and fallback != "image":
            base_name = fallback

    # Clean common duplicated-extension suffixes from source names.
    base_name = re.sub(r"-(?:jpe?g|png|webp|gif|svg|avif|heic|heif)$", "", base_name)
    if not base_name:
        base_name = "image"

    ext = infer_extension(candidate.url, content_type)
    candidate_name = f"{base_name}{ext}"

    if candidate_name not in existing:
        existing.add(candidate_name)
        return candidate_name

    for index in range(2, 10000):
        numbered = f"{base_name}-{index}{ext}"
        if numbered not in existing:
            existing.add(numbered)
            return numbered

    digest = hashlib.sha1(candidate.url.encode("utf-8")).hexdigest()[:10]
    hashed = f"{base_name}-{digest}{ext}"
    existing.add(hashed)
    return hashed


def download_image(
    session: requests.Session,
    candidate: ImageCandidate,
    output_dir: Path,
    used_names: Set[str],
    seen_hashes: Set[str],
    timeout: int,
    retries: int,
) -> Optional[Dict[str, str]]:
    for attempt in range(1, retries + 2):
        try:
            with session.get(candidate.url, timeout=timeout, stream=True) as response:
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if content_type and not content_type.lower().startswith("image/"):
                    return None

                file_name = build_image_filename(candidate, used_names, content_type)
                output_path = output_dir / file_name
                hasher = hashlib.sha256()

                with output_path.open("wb") as fh:
                    for chunk in response.iter_content(chunk_size=65536):
                        if chunk:
                            hasher.update(chunk)
                            fh.write(chunk)

                digest = hasher.hexdigest()
                if digest in seen_hashes:
                    output_path.unlink(missing_ok=True)
                    return None
                seen_hashes.add(digest)

                return {
                    "source_url": candidate.url,
                    "file": str(output_path.name),
                    "content_type": content_type,
                    "sha256": digest,
                }
        except Exception:
            if attempt > retries:
                return None
            time.sleep(0.5 * attempt)

    return None


def fetch_html(session: requests.Session, url: str, timeout: int) -> Optional[Tuple[str, str]]:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return None

    response.encoding = response.encoding or "utf-8"
    return response.text, response.url


def make_robots_parser(
    session: requests.Session,
    base_url: str,
    timeout: int,
    log: Callable[[str], None],
) -> Optional[RobotFileParser]:
    robots_url = urljoin(base_url, "/robots.txt")
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        response = session.get(robots_url, timeout=timeout)
        if response.status_code >= 400:
            log(f"[warn robots unavailable] {robots_url} returned {response.status_code}; continuing without robots rules")
            return None

        parser.parse(response.text.splitlines())
        return parser
    except Exception as exc:
        log(f"[warn robots unavailable] {robots_url}: {exc}; continuing without robots rules")
        return None


def crawl_site(
    base_url: str,
    output_root: Path,
    include_subdomains: bool,
    delay_seconds: float,
    timeout: int,
    max_pages: int,
    respect_robots: bool,
    verify_ssl: bool,
    capture_images: bool = True,
    capture_content: bool = True,
    log: Optional[Callable[[str], None]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict[str, object]:
    log_fn = log or print
    output_root.mkdir(parents=True, exist_ok=True)

    normalized_base = normalize_page_url(base_url)
    allowed_hosts = build_allowed_hosts(normalized_base, include_subdomains)
    base_host = normalize_netloc(urlparse(normalized_base).netloc)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.verify = verify_ssl
    if not verify_ssl:
        requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    robots = make_robots_parser(session, normalized_base, timeout=timeout, log=log_fn) if respect_robots else None

    queue: deque[str] = deque([normalized_base])
    visited: Set[str] = set()
    failures: List[str] = []

    pages_processed = 0
    images_downloaded = 0
    pages_with_content = 0

    while queue and pages_processed < max_pages:
        if should_stop and should_stop():
            log_fn("[stopped] Crawl cancelled by user.")
            break

        page_url = queue.popleft()
        if page_url in visited:
            continue
        visited.add(page_url)

        if robots and not robots.can_fetch(USER_AGENT, page_url):
            log_fn(f"[skip robots] {page_url}")
            continue

        try:
            fetched = fetch_html(session, page_url, timeout)
            if fetched is None:
                log_fn(f"[skip non-html] {page_url}")
                continue

            html, resolved_url = fetched
            normalized_resolved = normalize_page_url(resolved_url)
            if normalized_resolved != page_url:
                page_url = normalized_resolved
                visited.add(page_url)

            log_fn(f"[page] {page_url}")
            soup = BeautifulSoup(html, "html.parser")

            page_dir = page_folder_for_url(output_root, base_host, page_url)

            links = extract_page_links(soup, page_url, allowed_hosts, include_subdomains)
            for link in links:
                if link not in visited:
                    queue.append(link)

            content_saved = False
            if capture_content:
                markdown = build_page_markdown(html, page_url)
                (page_dir / "content.md").write_text(markdown, encoding="utf-8")
                pages_with_content += 1
                content_saved = True

            image_results: List[Dict[str, str]] = []
            if capture_images:
                image_dir = page_dir / "images"
                image_dir.mkdir(parents=True, exist_ok=True)
                image_candidates = extract_page_images(soup, page_url)
                used_names: Set[str] = set()
                seen_hashes: Set[str] = set()

                for candidate in image_candidates:
                    if should_stop and should_stop():
                        log_fn("[stopped] Crawl cancelled by user.")
                        break
                    result = download_image(
                        session=session,
                        candidate=candidate,
                        output_dir=image_dir,
                        used_names=used_names,
                        seen_hashes=seen_hashes,
                        timeout=timeout,
                        retries=2,
                    )
                    if result:
                        image_results.append(result)
                        images_downloaded += 1

            pages_processed += 1

            log_fn(f"  content: {'yes' if content_saved else 'no'} | images: {len(image_results)} | links queued: {len(queue)}")

            if delay_seconds > 0:
                time.sleep(delay_seconds)

        except Exception as exc:
            failures.append(f"{page_url} :: {exc}")
            log_fn(f"[error] {page_url}: {exc}")

    summary: Dict[str, object] = {
        "base_url": normalized_base,
        "pages_processed": pages_processed,
        "pages_seen": len(visited),
        "pages_with_content": pages_with_content,
        "images_downloaded": images_downloaded,
        "capture_images": capture_images,
        "capture_content": capture_content,
        "failures": failures,
    }
    (output_root / "crawl-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    log_fn("\nDone")
    log_fn(json.dumps(summary, indent=2))
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl a website and save page content/images into per-page folders")
    parser.add_argument("base_url", help="Starting URL, e.g. https://example.com")
    parser.add_argument(
        "--output",
        default="site-export",
        help="Output directory (default: ./site-export)",
    )
    parser.add_argument("--max-pages", type=int, default=2000, help="Maximum pages to crawl (default: 2000)")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between page fetches in seconds")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    parser.add_argument(
        "--include-subdomains",
        action="store_true",
        help="Crawl subdomains of the base host as well",
    )
    parser.add_argument(
        "--ignore-robots",
        action="store_true",
        help="Ignore robots.txt restrictions",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification (use only when necessary)",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip image downloading",
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="Skip markdown content export",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    capture_images = not args.no_images
    capture_content = not args.no_content
    if not capture_images and not capture_content:
        raise SystemExit("At least one output type must be enabled (images and/or content).")

    crawl_site(
        base_url=args.base_url,
        output_root=Path(args.output).resolve(),
        include_subdomains=args.include_subdomains,
        delay_seconds=args.delay,
        timeout=args.timeout,
        max_pages=args.max_pages,
        respect_robots=not args.ignore_robots,
        verify_ssl=not args.insecure,
        capture_images=capture_images,
        capture_content=capture_content,
    )


if __name__ == "__main__":
    main()
