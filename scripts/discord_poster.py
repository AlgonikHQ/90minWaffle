import os
import requests
import sqlite3
import logging
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/root/90minwaffle/.env')

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/discord_poster.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

WEBHOOKS = {
    "breaking_news": os.getenv("DISCORD_WEBHOOK_BREAKING_NEWS"),
    "match_day":     os.getenv("DISCORD_WEBHOOK_MATCH_DAY"),
    "bets":          os.getenv("DISCORD_WEBHOOK_BETS"),
}

# Format → Discord channel routing
FORMAT_CHANNEL = {
    "F1": "breaking_news",
    "F2": "breaking_news",
    "F3": "match_day",
    "F4": "match_day",
    "F5": "breaking_news",
    "F6": "match_day",
    "F7": "breaking_news",
}

FORMAT_NAMES = {
    "F1": "✅ CONFIRMED TRANSFER",
    "F2": "🔁 TRANSFER RUMOUR",
    "F3": "🏟️ MATCH PREVIEW",
    "F4": "📊 POST-MATCH",
    "F5": "🏆 TITLE RACE",
    "F6": "⭐ STAR SPOTLIGHT",
    "F7": "🔥 HOT TAKE",
}

COLOUR_MAP = {
    "F1": 0x00FF87,  # Green — confirmed
    "F2": 0xE63946,  # Red — rumour
    "F3": 0x4361EE,  # Blue — preview
    "F4": 0xF77F00,  # Orange — post match
    "F5": 0xFFD60A,  # Yellow — title race
    "F6": 0x7B2D8B,  # Purple — star
    "F7": 0xE63946,  # Red — hot take
}

def get_db():
    return sqlite3.connect(DB_PATH)

def build_embed(story):
    fmt   = story.get("format", "F7")
    score = story.get("score", 0)
    confidence = "🟢 AUTO-RECOMMENDED" if score >= 75 else "🟡 YOUR CALL"

    embed = {
        "title": story["title"][:256],
        "description": f"_{story.get('winning_hook', '')}_{chr(10)}{chr(10)}{story.get('caption', '').split(chr(10))[0]}",
        "color": COLOUR_MAP.get(fmt, 0xE63946),
        "fields": [
            {
                "name": "Format",
                "value": FORMAT_NAMES.get(fmt, fmt),
                "inline": True
            },
            {
                "name": "Score",
                "value": f"`{score}/100` — {confidence}",
                "inline": True
            },
            {
                "name": "Source",
                "value": story.get("source", "Unknown"),
                "inline": True
            },
            {
                "name": "Caption (copy-ready)",
                "value": f"```{story.get('caption', '')[:500]}```",
                "inline": False
            },
        ],
        "footer": {
            "text": "90minWaffle • React with 🔥 if you agree"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    # Add URL if available
    if story.get("url"):
        embed["url"] = story["url"]

    return embed

def post_to_discord(story, channel_key):
    webhook_url = WEBHOOKS.get(channel_key)
    if not webhook_url:
        log.error(f"  No webhook for channel: {channel_key}")
        return False

    embed = build_embed(story)
    video_path = story.get("video_path")

    try:
        if video_path and os.path.exists(video_path):
            # Post video file + embed
            with open(video_path, "rb") as vf:
                files = {"file": (os.path.basename(video_path), vf, "video/mp4")}
                payload = {"payload_json": json.dumps({"embeds": [embed]})}
                r = requests.post(webhook_url, data=payload, files=files, timeout=60)
        else:
            # Post embed only
            r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)

        if r.status_code in [200, 204]:
            log.info(f"  ✅ Posted to #{channel_key}: {story['title'][:60]}")
            return True
        else:
            log.error(f"  ❌ Discord error {r.status_code}: {r.text[:200]}")
            return False

    except Exception as e:
        log.error(f"  ❌ Post failed: {e}")
        return False

def process_discord_queue(limit=5):
    conn = get_db()
    c = conn.cursor()

    # Get queued stories not yet posted to Discord
    c.execute("""
        SELECT id, title, url, source, score, format,
               winning_hook, caption, video_path
        FROM stories
        WHERE status = 'queued'
        AND video_path IS NOT NULL
        ORDER BY score DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        log.info("No queued stories to post to Discord")
        return 0

    log.info(f"=== Discord posting — {len(rows)} stories ===")
    posted = 0

    for r in rows:
        story = {
            "id": r[0], "title": r[1], "url": r[2],
            "source": r[3], "score": r[4], "format": r[5],
            "winning_hook": r[6], "caption": r[7], "video_path": r[8]
        }

        channel_key = FORMAT_CHANNEL.get(story["format"], "breaking_news")
        log.info(f"Posting to #{channel_key}: {story['title'][:60]}")

        success = post_to_discord(story, channel_key)
        if success:
            # Mark as published
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE stories SET status='published' WHERE id=?", (story["id"],))
            conn.commit()
            conn.close()
            posted += 1

    log.info(f"=== Discord posting complete — {posted}/{len(rows)} posted ===")
    return posted

if __name__ == "__main__":
    process_discord_queue(limit=5)
            c.execute("UPDATE stories SET status='published' WHERE id=?",(story["id"],))
            conn.commit(); conn.close()
            posted+=1
    log.info(f"=== Done — {posted}/{len(rows)} posted ===")
    return posted
if __name__=="__main__":
    process_discord_queue(limit=5)
            c.execute("UPDATE stories SET status='published' WHERE id=?",(story["id"],))
            conn.commit(); conn.close()
            posted+=1
    log.info(f"=== Done — {posted}/{len(rows)} posted ===")
    return posted
if __name__=="__main__":
    process_discord_queue(limit=5)
