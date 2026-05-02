#!/usr/bin/env python3
"""
90minWaffle Engagement Bot
Pulls from DB content bank with no-repeat rotation.

Changes vs previous version:
  - Telegram engagement posting added — mirrors Discord schedule
  - Telegram uses plain text formatting (no embeds)
  - Same DB content bank used for both platforms
  - Each post function now calls both Discord webhook AND Telegram
  - Telegram posts via BOT_TOKEN to NEWS_CHANNEL (public)
  - Engagement posts are spaced 30 mins after news posts to avoid
    flooding — handled by scheduler timing
"""

import os, sqlite3, json, logging, requests, asyncio
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode

load_dotenv("/root/90minwaffle/.env")

LOG_PATH = "/root/90minwaffle/logs/engagement_bot.log"
DB_PATH  = "/root/90minwaffle/data/waffle.db"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

# Discord webhooks
DISCORD_GENERAL          = os.getenv("DISCORD_WEBHOOK_GENERAL")
DISCORD_HOT_TAKES        = os.getenv("DISCORD_WEBHOOK_HOT_TAKES")
DISCORD_MATCH_DAY        = os.getenv("DISCORD_WEBHOOK_MATCH_DAY")
DISCORD_WORLD_CUP        = os.getenv("DISCORD_WEBHOOK_WORLD_CUP")
DISCORD_EUROS            = os.getenv("DISCORD_WEBHOOK_EUROS")
DISCORD_EUROPEAN_CUPS    = os.getenv("DISCORD_WEBHOOK_EUROPEAN_CUPS")
DISCORD_SCOTTISH         = os.getenv("DISCORD_WEBHOOK_SCOTTISH_FOOTBALL")
DISCORD_DOMESTIC         = os.getenv("DISCORD_WEBHOOK_DOMESTIC_TROPHIES")
DISCORD_WOMENS           = os.getenv("DISCORD_WEBHOOK_WOMENS_FOOTBALL")

# Telegram
BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))

def get_db():
    return sqlite3.connect(DB_PATH)

def get_next(content_type, weekday_filter=None):
    """Return least-recently-used item of content_type. Never repeats until all exhausted."""
    conn = get_db()
    c = conn.cursor()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if weekday_filter is not None:
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

# ── Discord post ──────────────────────────────────────────────────────────────

def post_discord(webhook, embed):
    if not webhook:
        log.warning("No Discord webhook configured")
        return False
    try:
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=15)
        log.info(f"  Discord posted: {r.status_code}")
        return r.status_code in (200, 204)
    except Exception as e:
        log.error(f"  Discord post failed: {e}")
        return False

# ── Telegram post (async wrapped for sync scheduler) ─────────────────────────

def post_telegram(msg: str):
    """Post plain-text engagement message to Telegram public channel."""
    if not NEWS_CHANNEL or not BOT_TOKEN:
        return False
    async def _send():
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(
                chat_id=NEWS_CHANNEL,
                text=msg,
                parse_mode=ParseMode.MARKDOWN
            )
            log.info(f"  Telegram engagement posted: {msg[:60]}")
            return True
        except Exception as e:
            log.error(f"  Telegram engagement failed: {e}")
            return False
    try:
        return asyncio.run(_send())
    except Exception as e:
        log.error(f"  Telegram asyncio failed: {e}")
        return False

def ts():
    return datetime.now(timezone.utc).isoformat()

# ── Engagement post functions ─────────────────────────────────────────────────

def post_did_you_know():
    item = get_next("did_you_know")
    if not item: return

    # Discord
    embed = {
        "author": {"name": item["emoji"] + "  DID YOU KNOW?"},
        "description": "**" + item["fact"] + "**",
        "color": 0x9B59B6,
        "footer": {"text": "90minWaffle | Football facts daily"},
        "timestamp": ts()
    }
    post_discord(DISCORD_GENERAL, embed)

    # Telegram
    msg = "\n".join([
        f"{item['emoji']} *DID YOU KNOW?*",
        "",
        item["fact"],
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📺 YouTube  •  🐦 @90minWaffle  •  🎵 TikTok",
    ])
    post_telegram(msg)
    log.info("did_you_know posted to both platforms")


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

    # Discord
    embed = {
        "author": {"name": "📅  ON THIS DAY IN FOOTBALL"},
        "description": "**" + item["event"] + "**",
        "color": 0xF39C12,
        "footer": {"text": "90minWaffle | Football history"},
        "timestamp": ts()
    }
    post_discord(DISCORD_GENERAL, embed)

    # Telegram
    msg = "\n".join([
        "📅 *ON THIS DAY IN FOOTBALL*",
        "",
        item["event"],
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📺 YouTube  •  🐦 @90minWaffle  •  🎵 TikTok",
    ])
    post_telegram(msg)

    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE engagement_content SET used_count=used_count+1, last_used=? WHERE id=?",
              (datetime.now(timezone.utc).isoformat(), item_id))
    c.execute("INSERT INTO engagement_log (content_type, content_id, posted_at) VALUES (?,?,?)",
              ("on_this_day", item_id, datetime.now(timezone.utc).isoformat()))
    conn.commit(); conn.close()
    log.info("on_this_day posted: " + item["event"][:60])


def post_guess_player():
    item = get_next("guess_player")
    if not item: return
    clues = "\n".join(["• " + c for c in item["clues"]])

    # Discord
    embed = {
        "author": {"name": "🕵️  GUESS THE PLAYER"},
        "title": "Who am I?",
        "description": clues + "\n\n💡 Hint: *" + item["hint"] + "*\n\nReply with your answer below 👇",
        "color": 0x1ABC9C,
        "footer": {"text": "Answer revealed in 1 hour | 90minWaffle"},
        "timestamp": ts()
    }
    post_discord(DISCORD_GENERAL, embed)

    # Telegram
    msg = "\n".join([
        "🕵️ *GUESS THE PLAYER — Who am I?*",
        "",
        clues,
        "",
        f"💡 Hint: _{item['hint']}_",
        "",
        "Reply with your answer 👇",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🐦 @90minWaffle  •  📺 YouTube",
    ])
    post_telegram(msg)
    log.info("guess_player posted: " + item["answer"])


def post_guess_answer():
    conn = get_db(); c = conn.cursor()
    row = c.execute("""
        SELECT ec.content_json FROM engagement_log el
        JOIN engagement_content ec ON el.content_id = ec.id
        WHERE el.content_type='guess_player'
        ORDER BY el.id DESC LIMIT 1
    """).fetchone()
    conn.close()
    if not row: return
    item = json.loads(row[0])

    # Discord
    embed = {
        "author": {"name": "✅  ANSWER REVEALED"},
        "title": "The answer was: **" + item["answer"] + "**",
        "color": 0x2ECC71,
        "footer": {"text": "90minWaffle | New puzzle on Tuesday/Thursday"},
        "timestamp": ts()
    }
    post_discord(DISCORD_GENERAL, embed)

    # Telegram
    msg = "\n".join([
        "✅ *ANSWER REVEALED*",
        "",
        f"The answer was: *{item['answer']}*",
        "",
        "How did you do? 👇",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🐦 @90minWaffle  •  📺 YouTube",
    ])
    post_telegram(msg)
    log.info("guess_answer posted: " + item["answer"])


def post_trivia():
    item = get_next("trivia")
    if not item: return

    # Discord
    embed = {
        "author": {"name": "🧠  FOOTBALL TRIVIA"},
        "title": item["q"],
        "description": "Think you know the answer?\n\n||**" + item["a"] + "**||",
        "color": 0x3498DB,
        "footer": {"text": "90minWaffle | Click the spoiler to reveal the answer"},
        "timestamp": ts()
    }
    post_discord(DISCORD_GENERAL, embed)

    # Telegram — no spoiler tags, use separator trick
    msg = "\n".join([
        "🧠 *FOOTBALL TRIVIA*",
        "",
        f"*{item['q']}*",
        "",
        "Reply with your answer 👇",
        "",
        "⬇️ Answer below ⬇️",
        "||",
        f"✅ _{item['a']}_",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🐦 @90minWaffle  •  📺 YouTube",
    ])
    post_telegram(msg)
    log.info("trivia posted")


def post_daily_poll():
    weekday = datetime.now(timezone.utc).weekday()
    item = get_next("daily_poll", weekday_filter=weekday)
    if not item: return

    # Discord
    embed = {
        "author": {"name": "🗳️  COMMUNITY POLL"},
        "title": item["question"],
        "description": "Drop your answer in the comments 👇\n\n🟢 Agree / Yes\n🔴 Disagree / No\n\n*All views welcome — no wrong answers*",
        "color": 0xFF4500,
        "footer": {"text": "90minWaffle | Football. Hot takes. No filter."},
        "timestamp": ts()
    }
    # Route poll to hot_takes by default — specialist topic polls
    # go to their channel if keyword detected
    poll_question = item.get("question", "").lower()
    poll_channel = DISCORD_HOT_TAKES
    if any(k in poll_question for k in ["world cup", "2026", "nations league"]):
        poll_channel = DISCORD_WORLD_CUP or DISCORD_HOT_TAKES
    elif any(k in poll_question for k in ["champions league", "ucl", "europa", "european"]):
        poll_channel = DISCORD_EUROPEAN_CUPS or DISCORD_HOT_TAKES
    elif any(k in poll_question for k in ["scottish", "celtic", "rangers", "old firm"]):
        poll_channel = DISCORD_SCOTTISH or DISCORD_HOT_TAKES
    elif any(k in poll_question for k in ["fa cup", "carabao", "league cup", "wembley"]):
        poll_channel = DISCORD_DOMESTIC or DISCORD_HOT_TAKES
    elif any(k in poll_question for k in ["women", "wsl", "lionesses"]):
        poll_channel = DISCORD_WOMENS or DISCORD_HOT_TAKES
    post_discord(poll_channel, embed)

    # Telegram
    msg = "\n".join([
        "🗳️ *COMMUNITY POLL*",
        "",
        f"*{item['question']}*",
        "",
        "🟢 Yes / Agree",
        "🔴 No / Disagree",
        "",
        "Drop your answer below 👇",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "_All views welcome — no wrong answers_",
        "🐦 @90minWaffle  •  📺 YouTube",
    ])
    post_telegram(msg)
    log.info("daily_poll posted: " + item["question"][:60])


def post_monday_motivation():
    if datetime.now(timezone.utc).weekday() != 0:
        return
    item = get_next("monday_quote")
    if not item: return

    # Discord
    embed = {
        "author": {"name": "💬  MONDAY FOOTBALL QUOTE"},
        "description": '**"' + item["quote"] + '"\n\n— *' + item["author"] + "*",
        "color": 0xE9C46A,
        "footer": {"text": "90minWaffle | New week, new football"},
        "timestamp": ts()
    }
    post_discord(DISCORD_GENERAL, embed)

    # Telegram
    msg = "\n".join([
        "💬 *MONDAY FOOTBALL QUOTE*",
        "",
        f'_"{item["quote"]}"_',
        "",
        f"— *{item['author']}*",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "New week. New football. 🔥",
        "🐦 @90minWaffle  •  📺 YouTube",
    ])
    post_telegram(msg)
    log.info("monday_motivation posted: " + item["author"])


def post_world_cup_countdown():
    from datetime import date
    wc_start = date(2026, 6, 11)
    days_left = (wc_start - date.today()).days
    if days_left < 0 or days_left > 90:
        return

    conn = get_db(); c = conn.cursor()
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
        conn = get_db(); c = conn.cursor()
        c.execute("UPDATE engagement_content SET used_count=used_count+1, last_used=? WHERE id=?",
                  (datetime.now(timezone.utc).isoformat(), item_id))
        conn.commit(); conn.close()

    # Discord — route to #world-cup channel
    embed = {
        "author": {"name": "🌍  WORLD CUP 2026 COUNTDOWN"},
        "title": str(days_left) + " days to go",
        "description": "**" + fact_text + "**\n\nAre you excited? Who wins it? 👇",
        "color": 0xE63946,
        "footer": {"text": "90minWaffle | USA Canada Mexico 2026"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_discord(DISCORD_WORLD_CUP or DISCORD_GENERAL, embed)

    # Telegram
    msg = "\n".join([
        f"🌍 *WORLD CUP 2026 — {days_left} DAYS TO GO*",
        "",
        fact_text,
        "",
        "Who wins it? Drop your prediction 👇",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🐦 @90minWaffle  •  📺 YouTube",
    ])
    post_telegram(msg)
    log.info("world_cup_countdown posted: " + str(days_left) + " days")


def post_weekend_preview():
    if datetime.now(timezone.utc).weekday() not in (4, 5):
        return

    # Discord
    embed = {
        "author": {"name": "⚽  WEEKEND FOOTBALL IS HERE"},
        "title": "What are you watching this weekend?",
        "description": "Drop your predictions below 👇\n\n• Biggest upset?\n• Top scorer this weekend?\n• Match of the day?",
        "color": 0x4361EE,
        "footer": {"text": "90minWaffle | Football. Hot takes. No filter."},
        "timestamp": ts()
    }
    post_discord(DISCORD_MATCH_DAY, embed)

    # Telegram
    msg = "\n".join([
        "⚽ *WEEKEND FOOTBALL IS HERE*",
        "",
        "What are you watching this weekend?",
        "",
        "Drop your predictions 👇",
        "• Biggest upset?",
        "• Top scorer this weekend?",
        "• Match of the day?",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🐦 @90minWaffle  •  📺 YouTube  •  🎵 TikTok",
    ])
    post_telegram(msg)
    log.info("weekend_preview posted")


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BlockingScheduler(timezone="UTC")

# Both Discord + Telegram on the same schedule
scheduler.add_job(post_on_this_day,         "cron", hour=8,  minute=0)
scheduler.add_job(post_did_you_know,        "cron", hour=9,  minute=0)
scheduler.add_job(post_daily_poll,          "cron", hour=12, minute=0)
scheduler.add_job(post_trivia,              "cron", day_of_week="mon,wed,fri", hour=15, minute=0)
scheduler.add_job(post_guess_player,        "cron", day_of_week="tue,thu",     hour=18, minute=0)
scheduler.add_job(post_guess_answer,        "cron", day_of_week="tue,thu",     hour=19, minute=0)
scheduler.add_job(post_weekend_preview,     "cron", day_of_week="fri,sat",     hour=10, minute=0)
scheduler.add_job(post_monday_motivation,   "cron", day_of_week="mon",         hour=7,  minute=30)
scheduler.add_job(post_world_cup_countdown, "cron", hour=10, minute=30)

if __name__ == "__main__":
    log.info("Engagement bot starting — Discord + Telegram")
    log.info("Schedule: On this day 08:00 | Did you know 09:00 | Poll 12:00 | Trivia Mon/Wed/Fri 15:00 | Guess player Tue/Thu 18:00 | Answer 19:00 | Weekend preview Fri/Sat 10:00 | Monday motivation 07:30 | WC countdown 10:30")
    scheduler.start()
