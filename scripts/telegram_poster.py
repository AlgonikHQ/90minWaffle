#!/usr/bin/env python3
import asyncio, sqlite3, logging, os
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv("/root/90minwaffle/.env")

DB_PATH   = "/root/90minwaffle/data/waffle.db"
LOG_PATH  = "/root/90minwaffle/logs/telegram_poster.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL   = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))
INSIDE_CHANNEL = int(os.getenv("TELEGRAM_INSIDE_CHANNEL", 0))
BETS_CHANNEL   = int(os.getenv("TELEGRAM_BETS_CHANNEL", 0))
QUEUE_CHAT     = int(os.getenv("TELEGRAM_QUEUE_CHAT_ID", 0))
REPORTS_CHAT   = int(os.getenv("TELEGRAM_REPORTS_CHAT_ID", 0))
ALERTS_CHAT    = int(os.getenv("TELEGRAM_ALERTS_CHAT_ID", 0))

FORMAT_EMOJI = {
    "F1": "✅", "F2": "🔁", "F3": "🏟", "F4": "📊",
    "F5": "🏆", "F6": "⭐", "F7": "🔥"
}

def get_db(): return sqlite3.connect(DB_PATH)

def build_news_message(story):
    fmt     = story.get("format", "F7")
    emoji   = FORMAT_EMOJI.get(fmt, "📰")
    caption = story.get("caption", "")
    source  = story.get("source", "")
    hook    = story.get("winning_hook", "")
    return f"{emoji} *{hook}*\n\n{caption}\n\n— {source}"

# ── News channel (public) ─────────────────────────────────────────────────────
async def post_to_news(story):
    bot = Bot(token=BOT_TOKEN)
    video_path = story.get("video_path")
    msg = build_news_message(story)
    try:
        if video_path and os.path.exists(video_path):
            with open(video_path, "rb") as vf:
                await bot.send_video(chat_id=NEWS_CHANNEL, video=vf,
                    caption=msg, parse_mode=ParseMode.MARKDOWN, supports_streaming=True)
        else:
            await bot.send_message(chat_id=NEWS_CHANNEL, text=msg, parse_mode=ParseMode.MARKDOWN)
        log.info(f"  Posted to News: {story['title'][:60]}")
        return True
    except Exception as e:
        log.error(f"  News post failed: {e}")
        return False

async def process_news_queue(limit=3):
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT id, title, source, score, format, winning_hook, caption, video_path
        FROM stories WHERE status='queued' AND video_path IS NOT NULL
        AND format IN ('F1','F2','F5','F7')
        ORDER BY score DESC LIMIT ?""", (limit,))
    rows = c.fetchall(); conn.close()
    if not rows: log.info("No stories for News channel"); return 0
    log.info(f"=== Posting {len(rows)} to News channel ===")
    posted = 0
    for r in rows:
        story = {"id":r[0],"title":r[1],"source":r[2],"score":r[3],"format":r[4],
                 "winning_hook":r[5],"caption":r[6],"video_path":r[7]}
        if await post_to_news(story):
            conn = get_db(); c = conn.cursor()
            c.execute("UPDATE stories SET status='published' WHERE id=?", (story["id"],))
            conn.commit(); conn.close()
            posted += 1
    log.info(f"=== News posting done — {posted}/{len(rows)} ===")
    return posted

# ── Queue channel (videos for manual Reels/TikTok download) ──────────────────
async def post_to_queue(story):
    if not QUEUE_CHAT: return
    bot = Bot(token=BOT_TOKEN)
    video_path = story.get("video_path")
    caption = story.get("caption", "")
    hook = story.get("winning_hook", story["title"])
    msg = f"📥 *QUEUE — Ready for Reels/TikTok*\n\n*{hook}*\n\n{caption}"
    try:
        if video_path and os.path.exists(video_path):
            with open(video_path, "rb") as vf:
                await bot.send_video(chat_id=QUEUE_CHAT, video=vf,
                    caption=msg, parse_mode=ParseMode.MARKDOWN, supports_streaming=True)
        log.info(f"  Queued for manual post: {story['title'][:60]}")
    except Exception as e:
        log.error(f"  Queue post failed: {e}")

# ── Inside channel (cycle reports — private) ──────────────────────────────────
async def send_report(msg):
    if not INSIDE_CHANNEL: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=INSIDE_CHANNEL, text=msg, parse_mode=ParseMode.MARKDOWN)
        log.info("  Cycle report sent to Inside channel")
    except Exception as e:
        log.error(f"  Inside report failed: {e}")

# ── Reports channel (daily summary) ──────────────────────────────────────────
async def send_daily_summary(msg):
    if not REPORTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=REPORTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
        log.info("  Daily summary sent to Reports channel")
    except Exception as e:
        log.error(f"  Reports send failed: {e}")

# ── Alerts channel (errors/warnings) ─────────────────────────────────────────
async def send_alert(msg):
    if not ALERTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=ALERTS_CHAT, text=f"⚠️ *ALERT*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
        log.info("  Alert sent")
    except Exception as e:
        log.error(f"  Alert send failed: {e}")

# ── Bets channel (odds cards) ─────────────────────────────────────────────────
async def send_bets_card(msg):
    if not BETS_CHANNEL: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=BETS_CHANNEL, text=msg, parse_mode=ParseMode.MARKDOWN)
        log.info("  Bets card sent")
    except Exception as e:
        log.error(f"  Bets send failed: {e}")

if __name__ == "__main__":
    asyncio.run(process_news_queue(limit=3))
