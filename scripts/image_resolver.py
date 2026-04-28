"""image_resolver.py — 4-layer image waterfall for 90minWaffle cards.

Layer 1: OG scrape      — pull og:image from the article URL (editorial photo)
Layer 2: RSS media      — <media:content> / <enclosure> embedded in feed item
Layer 3: TheSportsDB    — render > cutout > thumb via sportsdb_registry
Layer 4: Team badge     — absolute last resort

Dedup policy:
  - Used images tracked in data/used_images.json with UTC timestamp
  - Same URL skipped within DEDUP_TTL_HOURS (default 48)
  - Cache auto-purges entries older than DEDUP_TTL_HOURS on every write
  - After 48hrs an image is fair game again — nothing stales permanently

Usage in card_generator.py:
    from image_resolver import resolve_image
    img_url = resolve_image(story)   # story dict with title, url, winning_hook
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEDUP_TTL_HOURS   = 48
DEDUP_TTL_SECONDS = DEDUP_TTL_HOURS * 3600
DATA_DIR          = "/root/90minwaffle/data"
USED_IMAGES_FILE  = os.path.join(DATA_DIR, "used_images.json")

HTTP_TIMEOUT = 6          # keep scrape snappy — cards fire on a cycle
USER_AGENT   = (
    "Mozilla/5.0 (compatible; 90minWaffle-bot/1.0; +https://twitter.com/90minwaffle)"
)

# Minimum image dimensions to reject tiny logos/icons accidentally in OG tags
MIN_CONTENT_LENGTH = 5_000   # bytes — anything smaller is almost certainly an icon

# ---------------------------------------------------------------------------
# Dedup tracker
# ---------------------------------------------------------------------------

def _load_used() -> dict:
    if not os.path.exists(USED_IMAGES_FILE):
        return {}
    try:
        with open(USED_IMAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_used(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    # Purge expired entries before saving — keeps the file lean
    now = time.time()
    cleaned = {
        url: ts for url, ts in data.items()
        if (now - ts) < DEDUP_TTL_SECONDS
    }
    tmp = USED_IMAGES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2)
    os.replace(tmp, USED_IMAGES_FILE)


def _is_used(url: str) -> bool:
    """Return True if this URL was used within the dedup window."""
    used = _load_used()
    ts = used.get(url)
    if ts is None:
        return False
    return (time.time() - ts) < DEDUP_TTL_SECONDS


def _mark_used(url: str) -> None:
    used = _load_used()
    used[url] = time.time()
    _save_used(used)


def _accept(url: str, source: str) -> str:
    """Mark URL as used and log the winning layer."""
    log.info(f"  [image_resolver] ✓ {source}: {url[:80]}")
    _mark_used(url)
    return url


# ---------------------------------------------------------------------------
# Layer 1 — OG scrape
# ---------------------------------------------------------------------------

def _og_scrape(article_url: str) -> Optional[str]:
    """Fetch the article page and pull og:image.

    This is the editorial photo the journalist/editor chose — always current,
    always relevant. BBC Sport, Sky Sports, The Guardian all embed high-quality
    action photos here.
    """
    if not article_url or not article_url.startswith("http"):
        return None
    try:
        r = requests.get(
            article_url,
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
        )
        if r.status_code != 200:
            return None

        soup = BeautifulSoup(r.text, "html.parser")

        # og:image is the primary target
        for prop in ("og:image", "twitter:image", "twitter:image:src"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag:
                img = tag.get("content", "").strip()
                if img and img.startswith("http") and _looks_like_real_photo(img):
                    return img

        # Some sites use <link rel="image_src">
        link = soup.find("link", rel="image_src")
        if link:
            img = link.get("href", "").strip()
            if img and img.startswith("http") and _looks_like_real_photo(img):
                return img

        return None
    except Exception as e:
        log.debug(f"  [image_resolver] OG scrape failed ({article_url[:60]}): {e}")
        return None


def _looks_like_real_photo(url: str) -> bool:
    """Cheap heuristic — reject known placeholder/logo patterns."""
    low = url.lower()
    # Reject obvious non-photos
    skip_patterns = [
        "logo", "icon", "favicon", "sprite", "placeholder",
        "avatar", "default", "blank", "badge", "crest",
        "pixel", "1x1", "tracking", "ads", "banner_ad",
    ]
    for p in skip_patterns:
        if p in low:
            return False
    # Must be a real image format
    if not any(ext in low for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        # Allow URLs without extensions (CDN paths) — don't reject them
        if "?" not in low and "/" not in low[8:]:
            return False
    return True


# ---------------------------------------------------------------------------
# Layer 2 — RSS media fields (passed through from rss_poller if available)
# ---------------------------------------------------------------------------

def _rss_media(story: dict) -> Optional[str]:
    """Check if the story dict carries a media URL directly from the RSS item.

    rss_poller stores extra feed fields in story["media_url"] if present.
    Also checks common feedparser field names.
    """
    for key in ("media_url", "enclosure_url", "image_url", "thumbnail"):
        val = story.get(key, "")
        if val and val.startswith("http") and _looks_like_real_photo(val):
            return val
    return None


# ---------------------------------------------------------------------------
# Layer 3 — TheSportsDB via existing registry
# ---------------------------------------------------------------------------

def _sportsdb(title: str, hook: str) -> Optional[str]:
    """Delegate to the existing sportsdb facade."""
    try:
        import importlib.util, sys
        spec = importlib.util.spec_from_file_location(
            "sportsdb", "/root/90minwaffle/scripts/sportsdb.py"
        )
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.get_image_for_story(title, hook)
    except Exception as e:
        log.debug(f"  [image_resolver] SportsDB failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_image(story: dict) -> Optional[str]:
    """Return the best image URL for a story, or None.

    story dict must contain at minimum:
        title        (str)
        url          (str)  — article URL from RSS
        winning_hook (str)  — AI-generated hook for extra name context

    Waterfall:
        Layer 1 — OG scrape from article URL
        Layer 2 — RSS media field
        Layer 3 — TheSportsDB render/cutout/thumb
        Layer 4 — TheSportsDB team badge (best_team_image fallback inside sportsdb)

    Each candidate is checked against the 48hr dedup window before acceptance.
    If ALL candidates are deduped (e.g. only one team badge exists), the most
    recent one is returned anyway — dedup is best-effort, not a hard block.
    """
    title = story.get("title", "")
    hook  = story.get("winning_hook", "") or title
    url   = story.get("url", "")

    candidates: list[tuple[str, str]] = []  # (url, source_label)

    # ── Layer 1: OG scrape ──────────────────────────────────────────────────
    og = _og_scrape(url)
    if og:
        candidates.append((og, "OG"))

    # ── Layer 2: RSS media ──────────────────────────────────────────────────
    rss = _rss_media(story)
    if rss and rss != og:
        candidates.append((rss, "RSS"))

    # ── Layer 3+4: TheSportsDB ──────────────────────────────────────────────
    sdb = _sportsdb(title, hook)
    if sdb and sdb not in (og, rss):
        candidates.append((sdb, "SportsDB"))

    if not candidates:
        log.info(f"  [image_resolver] No image found for: {title[:60]}")
        return None

    # Pick first non-deduped candidate
    for img_url, source in candidates:
        if not _is_used(img_url):
            return _accept(img_url, source)

    # All candidates deduped — fall back to first candidate anyway
    # (better a repeated image than no image at all)
    img_url, source = candidates[0]
    log.info(f"  [image_resolver] All deduped — reusing {source}: {img_url[:80]}")
    _mark_used(img_url)
    return img_url
