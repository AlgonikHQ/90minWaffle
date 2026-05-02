import os, json, sqlite3, requests, logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/discord_poster.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Season team data (update each August) ─────────────────────────────────
import sys
sys.path.insert(0, "/root/90minwaffle/scripts")
try:
    from season_teams import (
        PREMIER_LEAGUE, CHAMPIONSHIP, SCOTTISH_PREMIERSHIP,
        WOMENS_KEYWORDS, SCOTTISH_COMP_KEYWORDS, SCOTTISH_SOURCES,
        EUROPEAN_CUPS_KEYWORDS, DOMESTIC_TROPHIES_KEYWORDS,
        WORLD_CUP_KEYWORDS, EUROS_KEYWORDS, CHAMPIONSHIP_COMP_KEYWORDS,
    )
except ImportError as e:
    log.error(f"season_teams import failed: {e}")
    PREMIER_LEAGUE = set(); CHAMPIONSHIP = set(); SCOTTISH_PREMIERSHIP = set()
    WOMENS_KEYWORDS = []; SCOTTISH_COMP_KEYWORDS = []; SCOTTISH_SOURCES = []
    EUROPEAN_CUPS_KEYWORDS = []; DOMESTIC_TROPHIES_KEYWORDS = []
    WORLD_CUP_KEYWORDS = []; EUROS_KEYWORDS = []; CHAMPIONSHIP_COMP_KEYWORDS = []

WEBHOOKS = {
    "breaking_news":     os.getenv("DISCORD_WEBHOOK_BREAKING_NEWS"),
    "match_day":         os.getenv("DISCORD_WEBHOOK_MATCH_DAY"),
    "bets":              os.getenv("DISCORD_WEBHOOK_BETS"),
    "hot_takes":         os.getenv("DISCORD_WEBHOOK_HOT_TAKES"),
    "general":           os.getenv("DISCORD_WEBHOOK_GENERAL"),
    "premier_league":    os.getenv("DISCORD_WEBHOOK_PREMIER_LEAGUE"),
    "championship":      os.getenv("DISCORD_WEBHOOK_CHAMPIONSHIP"),
    "womens_football":   os.getenv("DISCORD_WEBHOOK_WOMENS_FOOTBALL"),
    "world_cup":         os.getenv("DISCORD_WEBHOOK_WORLD_CUP"),
    "euros":             os.getenv("DISCORD_WEBHOOK_EUROS"),
    "domestic_trophies": os.getenv("DISCORD_WEBHOOK_DOMESTIC_TROPHIES"),
    "scottish_football": os.getenv("DISCORD_WEBHOOK_SCOTTISH_FOOTBALL"),
    "european_cups":     os.getenv("DISCORD_WEBHOOK_EUROPEAN_CUPS"),
}

# Format → fallback channel (used only if competition router returns None)
FORMAT_CHANNEL = {
    "F1": "breaking_news",
    "F2": "breaking_news",
    "F3": "match_day",
    "F4": "match_day",
    "F5": "premier_league",
    "F6": "general",
    "F7": "hot_takes",
    "F8": "bets",
    "F9": "womens_football",
}

FORMAT_NAMES = {
    "F1": "CONFIRMED TRANSFER",  "F2": "TRANSFER RUMOUR",
    "F3": "MATCH PREVIEW",       "F4": "POST-MATCH",
    "F5": "TITLE RACE",          "F6": "STAR SPOTLIGHT",
    "F7": "HOT TAKE",            "F8": "BETTING TIP",
    "F9": "WOMENS FOOTBALL",
}

COLOUR_MAP = {
    "F1": 0x00C853, "F2": 0xE63946, "F3": 0x4361EE,
    "F4": 0xF77F00, "F5": 0xE9C46A, "F6": 0x9B5DE5,
    "F7": 0xFF4500, "F8": 0x00B4D8, "F9": 0xFF69B4,
}

FORMAT_EMOJI = {
    "F1": "🚨", "F2": "📰", "F3": "⚽", "F4": "📊",
    "F5": "🏆", "F6": "🌟", "F7": "🔥", "F8": "💰", "F9": "👩",
}

FORMAT_LABEL = {
    "F1": "CONFIRMED TRANSFER", "F2": "TRANSFER RUMOUR",
    "F3": "MATCH PREVIEW",      "F4": "POST-MATCH",
    "F5": "TITLE RACE",         "F6": "STAR SPOTLIGHT",
    "F7": "HOT TAKE",           "F8": "BETTING TIP",
    "F9": "WOMENS FOOTBALL",
}


def _title_contains_team(title_lower: str, team_set: set) -> bool:
    """Word-boundary safe team name check — avoids partial matches."""
    import re
    for team in team_set:
        pattern = r'\b' + re.escape(team) + r'\b'
        if re.search(pattern, title_lower):
            return True
    return False


def _is_scottish_team_story(title_lower: str) -> bool:
    """True only if title contains a Scottish Premiership team AND no PL/Champ team."""
    has_scottish = _title_contains_team(title_lower, SCOTTISH_PREMIERSHIP)
    if not has_scottish:
        return False
    # Celtic/Rangers appear in UCL/UEL stories — don't grab those for scottish_football
    # if a European competition keyword is also present
    if any(kw in title_lower for kw in EUROPEAN_CUPS_KEYWORDS):
        return False
    return True


def classify_competition(title: str, source: str) -> str | None:
    """
    Returns specialist channel key or None (fall through to FORMAT_CHANNEL).
    Priority order is intentional — do not reorder without testing.
    """
    t = (title or "").lower()
    s = (source or "").lower()

    # 1. Women's football — must be first, catches women's UCL before european_cups
    if any(kw in t for kw in WOMENS_KEYWORDS) or any(kw in s for kw in WOMENS_KEYWORDS):
        return "womens_football"

    # 2. World Cup — before euros/european_cups to avoid "cup" keyword bleed
    if any(kw in t for kw in WORLD_CUP_KEYWORDS):
        return "world_cup"

    # 3. Euros / Nations League (international, not clubs)
    if any(kw in t for kw in EUROS_KEYWORDS):
        return "euros"

    # 4. European club cups — after international tourneys are handled above
    if any(kw in t for kw in EUROPEAN_CUPS_KEYWORDS):
        return "european_cups"

    # 5. Domestic trophies (FA Cup, Carabao, Copa del Rey etc)
    if any(kw in t for kw in DOMESTIC_TROPHIES_KEYWORDS):
        return "domestic_trophies"

    # 6. Scottish football
    #    Competition keyword in title takes priority over team name
    if any(kw in t for kw in SCOTTISH_COMP_KEYWORDS):
        return "scottish_football"
    if any(kw in s for kw in SCOTTISH_SOURCES):
        return "scottish_football"
    if _is_scottish_team_story(t):
        return "scottish_football"

    # 7. Championship
    #    Competition keyword first — team names only as secondary signal
    if any(kw in t for kw in CHAMPIONSHIP_COMP_KEYWORDS):
        return "championship"
    if _title_contains_team(t, CHAMPIONSHIP) and not _title_contains_team(t, PREMIER_LEAGUE):
        return "championship"

    return None


def route_story(story: dict) -> str:
    """Full routing decision. Priority: F9/F8 hardcoded → competition → format → general."""
    fmt    = story.get("format", "F7")
    title  = story.get("title", "")
    source = story.get("source", "")

    # F9 always womens_football regardless of title
    if fmt == "F9":
        return "womens_football"

    # F8 always bets
    if fmt == "F8":
        return "bets"

    competition_channel = classify_competition(title, source)
    if competition_channel:
        log.info(f"  Competition route → #{competition_channel}: {title[:50]}")
        return competition_channel

    channel = FORMAT_CHANNEL.get(fmt, "general")
    log.info(f"  Format route → #{channel} [{fmt}]: {title[:50]}")
    return channel


def get_db():
    return sqlite3.connect(DB_PATH)


def _discord_relative_time(story):
    for field in ("published_at", "fetched_at"):
        val = story.get(field)
        if not val:
            continue
        try:
            if val.endswith("Z"):
                val = val[:-1] + "+00:00"
            dt = datetime.fromisoformat(val).astimezone(timezone.utc)
            delta = int((datetime.now(timezone.utc) - dt).total_seconds())
            if delta < 60:    return "just now"
            elif delta < 3600:  return f"{delta // 60}m ago"
            elif delta < 86400: return f"{delta // 3600}h ago"
            else:               return f"{delta // 86400}d ago"
        except Exception:
            continue
    return ""


def build_embed(story):
    fmt     = story.get("format", "F7")
    score   = story.get("score", 0)
    hook    = story.get("winning_hook") or story["title"]
    caption = story.get("caption", "") or ""
    script  = story.get("script", "") or ""
    source  = story.get("source", "Unknown")
    emoji   = FORMAT_EMOJI.get(fmt, "🔥")
    label   = FORMAT_LABEL.get(fmt, "HOT TAKE")
    reltime = _discord_relative_time(story)

    body_lines = []
    if script and len(script) > 30:
        body_lines.append(script[:280] + ("..." if len(script) > 280 else ""))
    elif hook != story["title"]:
        body_lines.append(hook)

    tags = [w for w in caption.split() if w.startswith("#")][:5]
    hashtag_str = " ".join(tags)

    description = f"**{hook}**"
    if body_lines:
        description += f"\n\n{body_lines[0]}"
    if hashtag_str:
        description += f"\n\n{hashtag_str}"

    time_part = f" · {reltime}" if reltime else ""
    author_name = f"{emoji}  {label}  ·  {score}/100  ·  {source}{time_part}"

    embed = {
        "author": {"name": author_name[:256]},
        "title": story["title"][:256],
        "description": description[:2048],
        "color": COLOUR_MAP.get(fmt, 0xE63946),
        "fields": [
            {"name": "Format",  "value": label,          "inline": True},
            {"name": "Score",   "value": f"{score}/100", "inline": True},
            {"name": "Source",  "value": source,         "inline": True},
        ],
        "footer": {"text": "90minWaffle • Football. Hot takes. No filter. | @90minWaffle"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if story.get("url"):
        embed["url"] = story["url"]

    try:
        from image_resolver import resolve_image
        img = resolve_image(story)
        if img:
            embed["image"] = {"url": img}
    except Exception:
        pass

    return embed


def post_to_discord(story, channel_key):
    webhook_url = WEBHOOKS.get(channel_key)
    if not webhook_url:
        log.error(f"No webhook configured for channel: {channel_key}")
        return False
    embed = build_embed(story)
    video_path = story.get("video_path")
    try:
        if video_path and os.path.exists(video_path):
            with open(video_path, "rb") as vf:
                files = {"file": (os.path.basename(video_path), vf, "video/mp4")}
                payload = {"payload_json": json.dumps({"embeds": [embed]})}
                r = requests.post(webhook_url, data=payload, files=files, timeout=60)
        else:
            r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
        if r.status_code in [200, 204]:
            log.info(f"Posted to #{channel_key}: {story['title'][:60]}")
            return True
        else:
            log.error(f"Discord {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        log.error(f"Post failed: {e}")
        return False


def post_poll(story, channel_key):
    webhook_url = WEBHOOKS.get(channel_key)
    if not webhook_url:
        return False
    hook = story.get("winning_hook", story.get("title", ""))[:100]
    embed = {
        "author": {"name": "🗳️  COMMUNITY POLL"},
        "title": "What do you think?",
        "description": "**" + hook + "**\n\n🟢 React ✅ to AGREE\n🔴 React ❌ to DISAGREE",
        "color": 0xFF4500,
        "footer": {"text": "90minWaffle • Football. Hot takes. No filter. | twitter.com/90minwaffle"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    try:
        r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
        if r.status_code in (200, 204):
            log.info(f"  Poll posted to #{channel_key}")
            return True
        return False
    except Exception as e:
        log.error(f"  Poll post failed: {e}")
        return False


def process_discord_queue(limit=5):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, url, source, score, format,
               winning_hook, caption, video_path
        FROM stories
        WHERE status = 'queued'
        ORDER BY score DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        log.info("No queued stories for Discord")
        return 0
    log.info(f"=== Discord posting - {len(rows)} stories ===")
    posted = 0
    for r in rows:
        story = {
            "id": r[0], "title": r[1], "url": r[2],
            "source": r[3], "score": r[4], "format": r[5],
            "winning_hook": r[6], "caption": r[7], "video_path": r[8]
        }
        channel_key = route_story(story)
        log.info(f"Routing to #{channel_key}: {story['title'][:60]}")
        if post_to_discord(story, channel_key):
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE stories SET status='published' WHERE id=?", (story["id"],))
            conn.commit()
            conn.close()
            posted += 1
    log.info(f"=== Discord done - {posted}/{len(rows)} posted ===")
    return posted


if __name__ == "__main__":
    process_discord_queue(limit=5)
