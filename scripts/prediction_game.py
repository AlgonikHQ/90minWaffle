#!/usr/bin/env python3
"""
prediction_game.py — Pre-match prediction posts for 90minWaffle Discord.

Posts a prediction embed to the relevant channel before big matches.
Community votes by reacting: 🏠 home win | 🤝 draw | ✈️ away win.
Result is posted back after full time with a winner callout.

Called from orchestrator during F3 preview cycle.
Stores predictions in DB table: prediction_game.
"""

import os, json, requests, sqlite3, logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

LOG_PATH = "/root/90minwaffle/logs/prediction_game.log"
DB_PATH  = "/root/90minwaffle/data/waffle.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BOT_HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type":  "application/json",
}

# Channel IDs where prediction posts go
# Mirrors discord_poster.py CHANNEL_IDS
PREDICTION_CHANNELS = {
    "match_day":         "1497916490798862357",
    "european_cups":     "1500176512219877416",
    "scottish_football": "1500176164583637172",
    "domestic_trophies": "1500175633236627697",
    "world_cup":         "1500175386162761828",
}

PREDICTION_WEBHOOKS = {
    "match_day":         os.getenv("DISCORD_WEBHOOK_MATCH_DAY"),
    "european_cups":     os.getenv("DISCORD_WEBHOOK_EUROPEAN_CUPS"),
    "scottish_football": os.getenv("DISCORD_WEBHOOK_SCOTTISH_FOOTBALL"),
    "domestic_trophies": os.getenv("DISCORD_WEBHOOK_DOMESTIC_TROPHIES"),
    "world_cup":         os.getenv("DISCORD_WEBHOOK_WORLD_CUP"),
}

def get_db():
    return sqlite3.connect(DB_PATH)

def _setup_table():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction_game (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER,
            channel_key TEXT,
            channel_id TEXT,
            message_id TEXT,
            home_team TEXT,
            away_team TEXT,
            match_title TEXT,
            posted_at TEXT,
            result_posted INTEGER DEFAULT 0,
            home_votes INTEGER DEFAULT 0,
            draw_votes INTEGER DEFAULT 0,
            away_votes INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def _already_posted(story_id: int) -> bool:
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM prediction_game WHERE story_id = ?", (story_id,)
    ).fetchone()
    conn.close()
    return row is not None

def _extract_teams_from_title(title: str) -> tuple[str, str]:
    """Best-effort extraction of home vs away from match title."""
    import re, sys
    sys.path.insert(0, "/root/90minwaffle/scripts")
    try:
        from season_teams import PREMIER_LEAGUE, CHAMPIONSHIP, SCOTTISH_PREMIERSHIP
        all_teams = list(PREMIER_LEAGUE | CHAMPIONSHIP | SCOTTISH_PREMIERSHIP)
    except ImportError:
        all_teams = []

    t = title.lower()
    found = []
    for team in all_teams:
        pattern = r'\b' + re.escape(team) + r'\b'
        if re.search(pattern, t):
            found.append(team.title())

    if len(found) >= 2:
        return found[0], found[1]
    # Fallback: split on vs / v
    for sep in [" vs ", " v ", " - "]:
        if sep in title.lower():
            parts = title.lower().split(sep)
            return parts[0].strip().title(), parts[1].strip().title()
    return "Home", "Away"

def post_prediction(story: dict, channel_key: str) -> str | None:
    """
    Post a prediction embed to Discord via webhook.
    Returns the Discord message_id or None.
    """
    webhook = PREDICTION_WEBHOOKS.get(channel_key)
    if not webhook:
        return None

    home, away = _extract_teams_from_title(story.get("title", ""))
    hook = story.get("winning_hook") or story.get("title", "")

    embed = {
        "title": f"🔮 PREDICT THE RESULT",
        "description": (
            f"**{hook}**\n\n"
            f"React with your prediction:\n\n"
            f"🏠 **{home} win**\n"
            f"🤝 **Draw**\n"
            f"✈️ **{away} win**\n\n"
            f"_Result drops here after full time_ 📊"
        ),
        "color": 0x4361EE,
        "footer": {
            "text": "90minWaffle Prediction Game • Football. Hot takes. No filter."
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        r = requests.post(
            webhook + "?wait=true",
            json={"embeds": [embed]},
            timeout=15
        )
        if r.status_code in (200, 201):
            msg_id = r.json().get("id")
            log.info(f"  Prediction posted: {hook[:50]} → msg {msg_id}")

            # Add reactions via bot
            if msg_id:
                channel_id = PREDICTION_CHANNELS.get(channel_key)
                _add_reactions(channel_id, msg_id, ["🏠", "🤝", "✈️"])

            return msg_id
        else:
            log.error(f"  Prediction post failed {r.status_code}: {r.text[:100]}")
            return None
    except Exception as e:
        log.error(f"  Prediction post exception: {e}")
        return None

def _add_reactions(channel_id: str, message_id: str, emojis: list):
    """Add seed reactions to a message via bot token."""
    if not BOT_TOKEN or not channel_id:
        return
    for emoji in emojis:
        try:
            url = (
                f"https://discord.com/api/v10/channels/{channel_id}"
                f"/messages/{message_id}/reactions/{requests.utils.quote(emoji)}/@me"
            )
            r = requests.put(url, headers=BOT_HEADERS, timeout=5)
            if r.status_code == 204:
                log.info(f"  Reaction {emoji} added")
            else:
                log.warning(f"  Reaction {emoji} failed: {r.status_code}")
        except Exception as e:
            log.warning(f"  Reaction exception: {e}")

def post_result(prediction_id: int, result_text: str, channel_key: str):
    """
    Post the match result as a follow-up message in the same channel.
    Updates the DB record as result_posted.
    """
    webhook = PREDICTION_WEBHOOKS.get(channel_key)
    if not webhook:
        return

    embed = {
        "title": "📊 FULL TIME — How did you do?",
        "description": f"**{result_text}**\n\n_Check the main feed for the full breakdown_ 🔥",
        "color": 0xF77F00,
        "footer": {"text": "90minWaffle Prediction Game"},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=15)
        if r.status_code in (200, 201, 204):
            conn = get_db()
            conn.execute(
                "UPDATE prediction_game SET result_posted=1 WHERE id=?",
                (prediction_id,)
            )
            conn.commit()
            conn.close()
            log.info(f"  Result posted for prediction {prediction_id}")
    except Exception as e:
        log.error(f"  Result post failed: {e}")

def run_predictions(limit=3):
    """
    Main entry point — called from orchestrator during F3 cycle.
    Finds F3 stories posted in last 2 hours without a prediction post,
    creates prediction embeds for them.
    """
    _setup_table()

    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT id, title, url, source, score, format, winning_hook, caption
        FROM stories
        WHERE format = 'F3'
        AND status = 'published'
        AND datetime(updated_at) > datetime('now', '-2 hours')
        ORDER BY score DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        log.info("No recent F3 stories for predictions")
        return 0

    posted = 0
    for r in rows:
        story = {
            "id": r[0], "title": r[1], "url": r[2], "source": r[3],
            "score": r[4], "format": r[5], "winning_hook": r[6], "caption": r[7],
        }

        if _already_posted(story["id"]):
            continue

        # Determine channel — reuse discord_poster routing
        import sys
        sys.path.insert(0, "/root/90minwaffle/scripts")
        from discord_poster import route_story
        channel_key = route_story(story)

        # Only post predictions to match-relevant channels
        if channel_key not in PREDICTION_CHANNELS:
            continue

        msg_id = post_prediction(story, channel_key)
        if msg_id:
            home, away = _extract_teams_from_title(story["title"])
            conn = get_db()
            conn.execute("""
                INSERT INTO prediction_game
                (story_id, channel_key, channel_id, message_id,
                 home_team, away_team, match_title, posted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                story["id"], channel_key,
                PREDICTION_CHANNELS.get(channel_key, ""),
                msg_id, home, away, story["title"],
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            conn.close()
            posted += 1

    log.info(f"=== Predictions done — {posted} posted ===")
    return posted

def resolve_pending_results():
    """
    Check for F4 stories that match pending predictions and post results.
    Called from orchestrator after F4 posting cycle.
    """
    _setup_table()
    conn = get_db()
    c    = conn.cursor()

    # Get unresolved predictions
    c.execute("""
        SELECT id, story_id, channel_key, home_team, away_team, match_title
        FROM prediction_game
        WHERE result_posted = 0
        AND datetime(posted_at) > datetime('now', '-24 hours')
    """)
    pending = c.fetchall()

    # Get recent F4 stories
    c.execute("""
        SELECT id, title, winning_hook, score
        FROM stories
        WHERE format = 'F4'
        AND status = 'published'
        AND datetime(updated_at) > datetime('now', '-3 hours')
        ORDER BY score DESC
        LIMIT 10
    """)
    f4_stories = c.fetchall()
    conn.close()

    if not pending or not f4_stories:
        return 0

    import re, sys
    sys.path.insert(0, "/root/90minwaffle/scripts")

    resolved = 0
    for pred in pending:
        pred_id, story_id, channel_key, home, away, match_title = pred
        home_l = home.lower()
        away_l = away.lower()

        for f4 in f4_stories:
            f4_title = f4[1].lower()
            f4_hook  = (f4[2] or "").lower()
            # Match if both teams appear in the F4 title
            if (home_l in f4_title or home_l in f4_hook) and \
               (away_l in f4_title or away_l in f4_hook):
                result_text = f4[2] or f4[1]
                post_result(pred_id, result_text, channel_key)
                resolved += 1
                break

    log.info(f"=== Resolved {resolved} prediction results ===")
    return resolved

if __name__ == "__main__":
    import sys
    if "--resolve" in sys.argv:
        resolve_pending_results()
    else:
        run_predictions(limit=5)
