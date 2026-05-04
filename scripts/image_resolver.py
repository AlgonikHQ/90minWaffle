"""image_resolver.py — 4-layer image waterfall for 90minWaffle cards.

Layer 1: OG scrape      — pull og:image from the article URL (editorial photo)
Layer 2: RSS media      — <media:content> / <enclosure> embedded in feed item
Layer 2.5: Wikipedia    — free editorial player photos
Layer 3: TheSportsDB    — render > cutout > thumb (ONLY if team context matches)
Layer 4: Branded card   — 90minWaffle logo placeholder (NO team badge JPEGs)

Changes vs previous version:
  - SportsDB layer now validates player team matches story context
    (prevents wrong kit / wrong club photos like QPR for an Arsenal story)
  - Team badge JPEG fallback REMOVED — aesthetically poor, replaced with
    branded placeholder card
  - Branded placeholder generated via Pillow: dark bg + 90minWaffle logo
    stored at assets/brand_placeholder.png
  - _looks_like_real_photo() now also blocks beluga/wildlife/non-sport CDN paths

Dedup policy unchanged — 48hr TTL, best-effort not hard block.
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
ASSETS_DIR        = "/root/90minwaffle/assets"
USED_IMAGES_FILE  = os.path.join(DATA_DIR, "used_images.json")
BRAND_PLACEHOLDER = os.path.join(ASSETS_DIR, "brand_placeholder.png")
LOGO_PATH         = os.path.join(ASSETS_DIR, "90minwafflePFP.jpg")   # your PFP logo

HTTP_TIMEOUT = 6
USER_AGENT   = (
    "Mozilla/5.0 (compatible; 90minWaffle-bot/1.0; +https://twitter.com/90minwaffle)"
)

MIN_CONTENT_LENGTH = 5_000

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
    log.info(f"  [image_resolver] ✓ {source}: {url[:80]}")
    _mark_used(url)
    return url


# ---------------------------------------------------------------------------
# Branded placeholder — generated once, cached to disk
# ---------------------------------------------------------------------------

def _get_brand_placeholder() -> Optional[str]:
    """Return path to branded placeholder PNG, generating it if needed.

    Design: dark #0d0d0d background, 90minWaffle logo centred,
    red waveform strip at bottom matching the header aesthetic.
    Returns a file:// path — Telegram send_photo accepts local paths.
    For Discord embeds we'd need to host it, so returns None for remote use
    and lets card_generator handle local vs remote.
    """
    if os.path.exists(BRAND_PLACEHOLDER):
        return BRAND_PLACEHOLDER

    try:
        from PIL import Image, ImageDraw, ImageFont
        import math

        os.makedirs(ASSETS_DIR, exist_ok=True)

        W, H = 1280, 720
        img = Image.new("RGB", (W, H), color=(13, 13, 13))
        draw = ImageDraw.Draw(img)

        # Red waveform strip at bottom (decorative bars matching brand header)
        bar_color = (180, 30, 30)
        num_bars  = 60
        bar_w     = W // num_bars
        strip_h   = 80
        for i in range(num_bars):
            height = int(strip_h * (0.3 + 0.7 * abs(math.sin(i * 0.4))))
            x0 = i * bar_w + 2
            x1 = x0 + bar_w - 4
            y0 = H - height
            y1 = H
            draw.rectangle([x0, y0, x1, y1], fill=bar_color)

        # Paste logo if it exists
        if os.path.exists(LOGO_PATH):
            logo = Image.open(LOGO_PATH).convert("RGBA")
            logo_size = 300
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            # Centre the logo
            lx = (W - logo_size) // 2
            ly = (H - logo_size) // 2 - 30
            img.paste(logo, (lx, ly), logo)
        else:
            # Text fallback if logo file missing
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            except Exception:
                font = ImageFont.load_default()
            label = "90minWaffle"
            bbox  = draw.textbbox((0, 0), label, font=font)
            tw    = bbox[2] - bbox[0]
            th    = bbox[3] - bbox[1]
            draw.text(((W - tw) // 2, (H - th) // 2 - 20), label, fill=(255, 255, 255), font=font)

            # Tagline
            try:
                small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            except Exception:
                small = ImageFont.load_default()
            tag   = "Football. Hot Takes. No Filter."
            tbbox = draw.textbbox((0, 0), tag, font=small)
            tw2   = tbbox[2] - tbbox[0]
            draw.text(((W - tw2) // 2, H // 2 + 50), tag, fill=(180, 180, 180), font=small)

        img.save(BRAND_PLACEHOLDER, "PNG", optimize=True)
        log.info(f"  [image_resolver] Brand placeholder generated: {BRAND_PLACEHOLDER}")
        return BRAND_PLACEHOLDER

    except Exception as e:
        log.warning(f"  [image_resolver] Could not generate brand placeholder: {e}")
        return None


# ---------------------------------------------------------------------------
# Layer 1 — OG scrape
# ---------------------------------------------------------------------------

def _og_scrape(article_url: str) -> Optional[str]:
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

        for prop in ("og:image", "twitter:image", "twitter:image:src"):
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag:
                img = tag.get("content", "").strip()
                if img and img.startswith("http") and _looks_like_real_photo(img):
                    return img

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
    """Reject known placeholder/logo/non-football patterns."""
    low = url.lower()

    # Hard-block non-football imagery patterns
    skip_patterns = [
        "logo", "icon", "favicon", "sprite", "placeholder",
        "avatar", "default", "blank", "badge", "crest",
        "pixel", "1x1", "tracking", "ads", "banner_ad",
        # Wildlife / nature CDN paths that have appeared as false positives
        "beluga", "whale", "dolphin", "shark", "animal", "wildlife",
        "nature", "ocean", "sea_life", "aquarium",
        # SportsDB badge URLs — small JPEG club crests, not editorial photos
        "thesportsdb.com/images/media/team/badge",
        "thesportsdb.com/images/media/team/logo",
        "thesportsdb.com/images/media/team/fanart",
        # SportsDB badge/logo URLs — small club crests, not editorial photos
        "thesportsdb.com/images/media/team/badge",
        "thesportsdb.com/images/media/team/logo",
        "thesportsdb.com/images/media/team/fanart",
        # Non-football sport assets
        "horse", "racing_horse", "jockey", "golf_ball", "tennis_ball",
        "cricket_bat", "rugby_ball",
        # Heraldic / medieval / historical art — NOT football imagery
        "coat_of_arms", "coat-of-arms", "heraldic", "heraldry", "medieval",
        "illuminated", "manuscript", "parchment", "escutcheon", "blazon",
        "armorial", "crest_art", "shield_art", "genealogy",
        # Religious / prayer imagery
        "prayer", "praying", "worship", "mosque", "islamic_art",
        "religious", "devotion", "pilgrimage",
        # Wikipedia article images that are NOT player photos
        "signature", "autograph", "map_of", "location_map", "flag_of",
        "logo_of", "seal_of", "emblem",
    ]
    for p in skip_patterns:
        if p in low:
            return False

    # Block Wikipedia non-photo pages by URL pattern
    if "wikipedia.org" in low or "wikimedia.org" in low:
        bad_wiki = ["coat_of_arms", "arms_of_", "heraldry", "coa_", "_coa.", "blazon",
                    "shield", "_escutcheon", "manuscript", "illuminat", "genealogy",
                    "signature_of", "flag_of_", "map_of_", "location_of_"]
        for bw in bad_wiki:
            if bw in low:
                return False

    if not any(ext in low for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        if "?" not in low and "/" not in low[8:]:
            return False

    return True


# ---------------------------------------------------------------------------
# Layer 1.5 — Wikipedia
# ---------------------------------------------------------------------------

def _wikipedia_player(name: str) -> Optional[str]:
    if not name or len(name) < 4:
        return None
    try:
        slug = name.strip().replace(" ", "_")
        r = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}",
            headers={"User-Agent": USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data  = r.json()
        thumb = data.get("thumbnail", {}).get("source", "")
        if thumb and "320px" in thumb:
            thumb = thumb.replace("320px", "800px")
        if thumb and _looks_like_real_photo(thumb):
            log.debug(f"  [image_resolver] Wikipedia hit: {name}")
            return thumb
        return None
    except Exception as e:
        log.debug(f"  [image_resolver] Wikipedia failed ({name}): {e}")
        return None


# ---------------------------------------------------------------------------
# Layer 2 — RSS media
# ---------------------------------------------------------------------------

def _rss_media(story: dict) -> Optional[str]:
    for key in ("media_url", "enclosure_url", "image_url", "thumbnail"):
        val = story.get(key, "")
        if val and val.startswith("http") and _looks_like_real_photo(val):
            return val
    return None


# ---------------------------------------------------------------------------
# Layer 3 — TheSportsDB (with team-context validation)
# ---------------------------------------------------------------------------

def _extract_story_teams(title: str, hook: str) -> list[str]:
    """Extract team names mentioned in the story for context validation."""
    text_lower = f"{title} {hook}".lower()
    known_clubs = [
        "arsenal", "chelsea", "liverpool", "manchester city", "man city",
        "manchester united", "man utd", "tottenham", "spurs", "newcastle",
        "aston villa", "west ham", "fulham", "everton", "brighton",
        "crystal palace", "brentford", "wolves", "nottingham forest",
        "bournemouth", "leicester", "ipswich", "southampton",
        "real madrid", "barcelona", "barca", "atletico", "atletico madrid",
        "bayern", "psg", "inter milan", "juventus", "ac milan",
        "dortmund", "porto", "benfica", "celtic", "rangers",
        "qpr", "queens park rangers", "stoke", "cardiff", "swansea",
    ]
    return [club for club in known_clubs if club in text_lower]


def _sportsdb_player_team_matches(player_data: dict, story_teams: list[str]) -> bool:
    """Validate that a SportsDB player record belongs to a club in the story.

    Prevents showing a QPR photo for an Arsenal story, or a Chelsea 2019
    kit photo for a current Man Utd story.
    """
    if not story_teams:
        # No teams extracted — can't validate, allow through (better than nothing)
        return True

    player_team = (
        player_data.get("strTeam") or
        player_data.get("strCurrentTeam") or
        player_data.get("strClub") or ""
    ).lower()

    if not player_team:
        return True  # No team info on record, can't reject

    for story_team in story_teams:
        if story_team in player_team or player_team in story_team:
            return True

    log.debug(
        f"  [image_resolver] SportsDB team mismatch — "
        f"player team '{player_team}' not in story teams {story_teams}"
    )
    return False


def _sportsdb(title: str, hook: str) -> Optional[str]:
    """TheSportsDB lookup with team-context validation.

    Only returns a player image if the player's registered team
    matches a team mentioned in the story. This prevents wrong-kit
    and wrong-club images.

    Team images (badges) are intentionally NOT returned here —
    those are handled by the branded placeholder fallback instead.
    """
    story_teams = _extract_story_teams(title, hook)

    try:
        import importlib.util, sys
        sys.path.insert(0, "/root/90minwaffle/scripts")
        spec = importlib.util.spec_from_file_location(
            "sportsdb_registry", "/root/90minwaffle/scripts/sportsdb_registry.py"
        )
        reg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reg)

        text_combined = f"{title} {hook}"
        names = reg.extract_player_names(text_combined)

        for name in names[:3]:
            # Try registry first
            team    = reg.find_team_in_text(text_combined)
            team_id = team.get("id") if team else None
            url = reg.find_player_image(name, team_id)
            if url:
                log.debug(f"  [image_resolver] SportsDB registry hit: {name}")
                return url

            # Legacy API search — validate team context before accepting
            import requests as _req
            r = _req.get(
                f"{reg.BASE}/searchplayers.php",
                params={"p": name},
                timeout=8,
            )
            players = (r.json() or {}).get("player") or []
            for p in players:
                sport = (p.get("strSport") or "").lower()
                if sport not in ("soccer", "football"):
                    continue
                # ── TEAM CONTEXT VALIDATION ──────────────────────────────
                if not _sportsdb_player_team_matches(p, story_teams):
                    continue   # skip — wrong club kit
                # ────────────────────────────────────────────────────────
                img = p.get("strRender") or p.get("strCutout") or p.get("strThumb")
                if img:
                    log.debug(f"  [image_resolver] SportsDB API hit: {name} ({p.get('strTeam','')})")
                    return img

        # NOTE: Team badge fallback intentionally removed.
        # We no longer return badge JPEGs — branded placeholder handles this.
        return None

    except Exception as e:
        log.debug(f"  [image_resolver] SportsDB failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_image(story: dict) -> Optional[str]:
    """Return the best image URL/path for a story, or None.

    Waterfall:
        Layer 1   — OG scrape (editorial photo from article)
        Layer 2   — RSS media field
        Layer 2.5 — Wikipedia player photo
        Layer 3   — TheSportsDB (player only, team-validated, no badges)
        Layer 4   — Branded 90minWaffle placeholder (local file path)

    Returns a URL string for remote images, or a local file path for
    the branded placeholder. card_generator must handle both cases.
    """
    title = story.get("title", "")
    hook  = story.get("winning_hook", "") or title
    url   = story.get("url", "")

    script_ctx = story.get("script", "") or ""
    hook = f"{hook} {script_ctx[:120]}".strip()

    candidates: list[tuple[str, str]] = []

    # ── Layer 1: OG scrape ──────────────────────────────────────────────────
    og = _og_scrape(url)
    if og:
        candidates.append((og, "OG"))

    # ── Layer 2: RSS media ──────────────────────────────────────────────────
    rss = _rss_media(story)
    if rss and rss != og:
        candidates.append((rss, "RSS"))

    # ── Layer 2.5: Wikipedia ────────────────────────────────────────────────
    try:
        from sportsdb_registry import extract_player_names
        wiki_names = extract_player_names(f"{title} {hook}", limit=3)
        for wname in wiki_names:
            wiki_img = _wikipedia_player(wname)
            if wiki_img and wiki_img not in [c[0] for c in candidates]:
                candidates.append((wiki_img, f"Wikipedia:{wname}"))
                break
    except Exception as e:
        log.debug(f"  [image_resolver] Wikipedia layer failed: {e}")

    # ── Layer 3: TheSportsDB (validated) ────────────────────────────────────
    sdb = _sportsdb(title, hook)
    if sdb and sdb not in [c[0] for c in candidates]:
        candidates.append((sdb, "SportsDB"))

    # Pick first non-deduped candidate
    for img_url, source in candidates:
        if not _is_used(img_url):
            return _accept(img_url, source)

    # All remote candidates deduped — try branded placeholder
    # (local file, always fresh, never deduped)
    if candidates:
        img_url, source = candidates[0]
        log.info(f"  [image_resolver] All deduped — reusing {source}: {img_url[:80]}")
        _mark_used(img_url)
        return img_url

    # ── Layer 4: Branded placeholder (absolute last resort) ─────────────────
    log.info(f"  [image_resolver] No remote image — using brand placeholder")
    return _get_brand_placeholder()
