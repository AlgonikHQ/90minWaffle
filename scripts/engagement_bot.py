#!/usr/bin/env python3
"""
90minWaffle Engagement Bot
Pulls from DB content bank with no-repeat rotation.
"""
import os, sqlite3, json, logging, requests
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

LOG_PATH = "/root/90minwaffle/logs/engagement_bot.log"
DB_PATH  = "/root/90minwaffle/data/waffle.db"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

DISCORD_GENERAL   = os.getenv("DISCORD_WEBHOOK_GENERAL")
DISCORD_HOT_TAKES = os.getenv("DISCORD_WEBHOOK_HOT_TAKES")
DISCORD_MATCH_DAY = os.getenv("DISCORD_WEBHOOK_MATCH_DAY")

def get_db():
    return sqlite3.connect(DB_PATH)

def get_next(content_type, weekday_filter=None):
    """Return least-recently-used item of content_type. Never repeats until all exhausted."""
    conn = get_db()
    c = conn.cursor()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if weekday_filter is not None:
        # For polls — pick by weekday first, then fallback to any
        row = c.execute("""
            SELECT id, content_json FROM engagement_content
            WHERE content_type=? AND active=1
            AND json_extract(content_json, '$.weekday')=?
            AND (last_used IS NULL OR last_used NOT LIKE ?)
            ORDER BY used_count ASC, last_used ASC
            LIMIT 1
        """, (content_type, weekday_filter, today + "%")).fetchone()
        if not row:
            row = c.execute("""
                SELECT id, content_json FROM engagement_content
                WHERE content_type=? AND active=1
                AND json_extract(content_json, '$.weekday')=?
                ORDER BY used_count ASC, last_used ASC
                LIMIT 1
            """, (content_type, weekday_filter)).fetchone()
    else:
        row = c.execute("""
            SELECT id, content_json FROM engagement_content
            WHERE content_type=? AND active=1
            AND (last_used IS NULL OR last_used NOT LIKE ?)
            ORDER BY used_count ASC, last_used ASC
            LIMIT 1
        """, (content_type, today + "%")).fetchone()
        if not row:
            # All used today — reset cycle
            row = c.execute("""
                SELECT id, content_json FROM engagement_content
                WHERE content_type=? AND active=1
                ORDER BY used_count ASC, last_used ASC
                LIMIT 1
            """, (content_type,)).fetchone()

    if not row:
        conn.close()
        return None

    item_id, item_json = row
    now = datetime.now(timezone.utc).isoformat()
    c.execute("UPDATE engagement_content SET used_count=used_count+1, last_used=? WHERE id=?", (now, item_id))
    c.execute("INSERT INTO engagement_log (content_type, content_id, posted_at) VALUES (?,?,?)",
              (content_type, item_id, now))
    conn.commit()
    conn.close()
    return json.loads(item_json)

def post(webhook, embed):
    if not webhook:
        log.warning("No webhook configured")
        return False
    try:
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=15)
        log.info("Posted: " + str(r.status_code))
        return r.status_code in (200, 204)
    except Exception as e:
        log.error("Post failed: " + str(e))
        return False

def ts():
    return datetime.now(timezone.utc).isoformat()

# ── Post functions ────────────────────────────────────────────────────────────

def post_did_you_know():
    item = get_next("did_you_know")
    if not item: return
    embed = {
        "author": {"name": item["emoji"] + "  DID YOU KNOW?"},
        "description": "**" + item["fact"] + "**",
        "color": 0x9B59B6,
        "footer": {"text": "90minWaffle | Football facts daily"},
        "timestamp": ts()
    }
    post(DISCORD_GENERAL, embed)
    log.info("did_you_know posted")

def post_on_this_day():
    now = datetime.now(timezone.utc)
    conn = get_db()
    c = conn.cursor()
    rows = c.execute("""
        SELECT id, content_json FROM engagement_content
        WHERE content_type='on_this_day' AND active=1
    """).fetchall()
    conn.close()
    matches = []
    for row in rows:
        item = json.loads(row[1])
        if item.get("month") == now.month and item.get("day") == now.day:
            matches.append((row[0], item))
    if not matches:
        log.info("on_this_day: no match for today")
        return
    item_id, item = matches[0]
    embed = {
        "author": {"name": "📅  ON THIS DAY IN FOOTBALL"},
        "description": "**" + item["event"] + "**",
        "color": 0xF39C12,
        "footer": {"text": "90minWaffle | Football history"},
        "timestamp": ts()
    }
    post(DISCORD_GENERAL, embed)
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE engagement_content SET used_count=used_count+1, last_used=? WHERE id=?",
              (datetime.now(timezone.utc).isoformat(), item_id))
    c.execute("INSERT INTO engagement_log (content_type, content_id, posted_at) VALUES (?,?,?)",
              ("on_this_day", item_id, datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()
    log.info("on_this_day posted: " + item["event"][:60])

def post_guess_player():
    item = get_next("guess_player")
    if not item: return
    clues = chr(10).join(["• " + c for c in item["clues"]])
    embed = {
        "author": {"name": "🕵️  GUESS THE PLAYER"},
        "title": "Who am I?",
        "description": clues + chr(10) + chr(10) + "💡 Hint: *" + item["hint"] + "*" + chr(10) + chr(10) + "Reply with your answer below 👇",
        "color": 0x1ABC9C,
        "footer": {"text": "Answer revealed in 1 hour | 90minWaffle"},
        "timestamp": ts()
    }
    post(DISCORD_GENERAL, embed)
    log.info("guess_player posted: " + item["answer"])

def post_guess_answer():
    """Post the most recently used guess player answer."""
    conn = get_db()
    c = conn.cursor()
    row = c.execute("""
        SELECT ec.content_json FROM engagement_log el
        JOIN engagement_content ec ON el.content_id = ec.id
        WHERE el.content_type='guess_player'
        ORDER BY el.id DESC LIMIT 1
    """).fetchone()
    conn.close()
    if not row: return
    item = json.loads(row[0])
    embed = {
        "author": {"name": "✅  ANSWER REVEALED"},
        "title": "The answer was: **" + item["answer"] + "**",
        "color": 0x2ECC71,
        "footer": {"text": "90minWaffle | New puzzle on Tuesday/Thursday"},
        "timestamp": ts()
    }
    post(DISCORD_GENERAL, embed)
    log.info("guess_answer posted: " + item["answer"])

def post_trivia():
    item = get_next("trivia")
    if not item: return
    embed = {
        "author": {"name": "🧠  FOOTBALL TRIVIA"},
        "title": item["q"],
        "description": "Think you know the answer?" + chr(10) + chr(10) + "||**" + item["a"] + "**||",
        "color": 0x3498DB,
        "footer": {"text": "90minWaffle | Click the spoiler to reveal the answer"},
        "timestamp": ts()
    }
    post(DISCORD_GENERAL, embed)
    log.info("trivia posted")

def post_daily_poll():
    weekday = datetime.now(timezone.utc).weekday()
    item = get_next("daily_poll", weekday_filter=weekday)
    if not item: return
    embed = {
        "author": {"name": "🗳️  COMMUNITY POLL"},
        "title": item["question"],
        "description": "Drop your answer in the comments 👇" + chr(10) + chr(10) + "🟢 Agree / Yes" + chr(10) + "🔴 Disagree / No" + chr(10) + chr(10) + "*All views welcome — no wrong answers*",
        "color": 0xFF4500,
        "footer": {"text": "90minWaffle | Football. Hot takes. No filter."},
        "timestamp": ts()
    }
    post(DISCORD_HOT_TAKES, embed)
    log.info("daily_poll posted: " + item["question"][:60])

def post_monday_motivation():
    if datetime.now(timezone.utc).weekday() != 0:
        return
    item = get_next("monday_quote")
    if not item: return
    embed = {
        "author": {"name": "💬  MONDAY FOOTBALL QUOTE"},
        "description": '**"' + item["quote"] + '"' + chr(10) + chr(10) + "— *" + item["author"] + "*",
        "color": 0xE9C46A,
        "footer": {"text": "90minWaffle | New week, new football"},
        "timestamp": ts()
    }
    post(DISCORD_GENERAL, embed)
    log.info("monday_motivation posted: " + item["author"])

def post_world_cup_countdown():
    """Post daily World Cup countdown and fact."""
    from datetime import date
    wc_start = date(2026, 6, 11)
    days_left = (wc_start - date.today()).days
    if days_left < 0 or days_left > 90:
        return
    conn = get_db()
    c = conn.cursor()
    row = c.execute("""
        SELECT id, content_json FROM engagement_content
        WHERE content_type='world_cup_fact' AND active=1
        AND (last_used IS NULL OR last_used NOT LIKE ?)
        ORDER BY used_count ASC, last_used ASC LIMIT 1
    """, (datetime.now(timezone.utc).strftime("%Y-%m-%d") + "%",)).fetchone()
    conn.close()
    if not row:
        fact_text = "The 2026 World Cup kicks off June 11 in North America."
    else:
        item_id, item_json = row
        fact = json.loads(item_json)
        fact_text = fact.get("fact", "")
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE engagement_content SET used_count=used_count+1, last_used=? WHERE id=?",
                  (datetime.now(timezone.utc).isoformat(), item_id))
        conn.commit()
        conn.close()
    embed = {
        "author": {"name": "🌍  WORLD CUP 2026 COUNTDOWN"},
        "title": str(days_left) + " days to go",
        "description": "**" + fact_text + "**" + chr(10) + chr(10) + "Are you excited? Who wins it? 👇",
        "color": 0xE63946,
        "footer": {"text": "90minWaffle | USA Canada Mexico 2026"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post(DISCORD_GENERAL, embed)
    log.info("world_cup_countdown posted: " + str(days_left) + " days")

def post_weekend_preview():
    if datetime.now(timezone.utc).weekday() not in (4, 5):
        return
    embed = {
        "author": {"name": "⚽  WEEKEND FOOTBALL IS HERE"},
        "title": "What are you watching this weekend?",
        "description": "Drop your predictions below 👇" + chr(10) + chr(10) + "• Biggest upset?" + chr(10) + "• Top scorer this weekend?" + chr(10) + "• Match of the day?",
        "color": 0x4361EE,
        "footer": {"text": "90minWaffle | Football. Hot takes. No filter."},
        "timestamp": ts()
    }
    post(DISCORD_MATCH_DAY, embed)
    log.info("weekend_preview posted")

# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BlockingScheduler(timezone="UTC")

scheduler.add_job(post_on_this_day,      "cron", hour=8,  minute=0)
scheduler.add_job(post_did_you_know,     "cron", hour=9,  minute=0)
scheduler.add_job(post_daily_poll,       "cron", hour=12, minute=0)
scheduler.add_job(post_trivia,           "cron", day_of_week="mon,wed,fri", hour=15, minute=0)
scheduler.add_job(post_guess_player,     "cron", day_of_week="tue,thu",     hour=18, minute=0)
scheduler.add_job(post_guess_answer,     "cron", day_of_week="tue,thu",     hour=19, minute=0)
scheduler.add_job(post_weekend_preview,  "cron", day_of_week="fri,sat",     hour=10, minute=0)
scheduler.add_job(post_monday_motivation,"cron", day_of_week="mon",         hour=7,  minute=30)
scheduler.add_job(post_world_cup_countdown,"cron", hour=10, minute=30)

if __name__ == "__main__":
    log.info("Engagement bot starting...")
    log.info("333 content items loaded across 6 types")
    log.info("Schedule: On this day 08:00 | Did you know 09:00 | Poll 12:00 | Trivia Mon/Wed/Fri 15:00 | Guess player Tue/Thu 18:00 | Answer reveal 19:00 | Weekend preview Fri/Sat 10:00 | Monday motivation 07:30")
    scheduler.start()
