import asyncio
import sqlite3
import logging
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime, timezone

load_dotenv('/root/90minwaffle/.env')

DB_PATH = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/queue_notifier.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
QUEUE_CHAT   = os.getenv("TELEGRAM_QUEUE_CHAT_ID")
ALERTS_CHAT  = os.getenv("TELEGRAM_ALERTS_CHAT_ID")
REPORTS_CHAT = os.getenv("TELEGRAM_REPORTS_CHAT_ID")

FORMAT_NAMES = {
    "F1": "Confirmed Transfer",
    "F2": "Transfer Rumour",
    "F3": "Match Preview",
    "F4": "Post-Match Reaction",
    "F5": "Title Race / Narrative",
    "F6": "Star Spotlight",
    "F7": "Hot Take",
}

def confidence_emoji(score):
    if score >= 75: return "🟢"
    if score >= 65: return "🟡"
    return "🔴"

def confidence_label(score):
    if score >= 75: return "AUTO-RECOMMENDED"
    if score >= 65: return "YOUR CALL"
    return "QUIET DAY ONLY"

def format_queue_message(story):
    score = story["score"]
    fmt = story["format"]
    emoji = confidence_emoji(score)
    label = confidence_label(score)
    fmt_name = FORMAT_NAMES.get(fmt, fmt)

    msg = (
        f"{emoji} *90minWaffle Queue*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*{story['title']}*\n\n"
        f"📊 Score: `{score}/100` — {label}\n"
        f"🎬 Format: `{fmt}` — {fmt_name}\n"
        f"📰 Source: {story['source']}\n\n"
        f"*Hook:*\n_{story['winning_hook']}_\n\n"
        f"*Caption (copy-ready):*\n```\n{story['caption']}\n```\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Actions: Publish 📤 | Bin ❌ | Delay ⏰ | Regen 🔄\n"
        f"_(Reply with P / B / D / R to action)_"
    )
    return msg

def get_db():
    return sqlite3.connect(DB_PATH)

async def send_queue_item(story):
    bot = Bot(token=BOT_TOKEN)
    msg_text = format_queue_message(story)
    video_path = story.get("video_path")
    chat_id = int(QUEUE_CHAT)

    try:
        # Send video if it exists, otherwise send text card
        if video_path and os.path.exists(video_path):
            with open(video_path, "rb") as vf:
                sent = await bot.send_video(
                    chat_id=chat_id,
                    video=vf,
                    caption=msg_text,
                    parse_mode=None,
                    supports_streaming=True
                )
            log.info(f"  ✅ Video queued — msg_id: {sent.message_id}")
        else:
            sent = await bot.send_message(
                chat_id=chat_id,
                text=msg_text,
                parse_mode=ParseMode.MARKDOWN
            )
            log.info(f"  ✅ Text card queued — msg_id: {sent.message_id}")

        return sent.message_id

    except Exception as e:
        log.error(f"  ❌ Failed to send queue item: {e}")
        return None

async def send_alert(message):
    """Send a message to the private Alerts channel."""
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=int(ALERTS_CHAT),
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )
        log.info("Alert sent")
    except Exception as e:
        log.error(f"Alert failed: {e}")

async def send_report(message):
    """Send a message to the private Reports channel."""
    bot = Bot(token=BOT_TOKEN)
    try:
        await bot.send_message(
            chat_id=int(REPORTS_CHAT),
            text=message,
            parse_mode=ParseMode.MARKDOWN
        )
        log.info("Report sent")
    except Exception as e:
        log.error(f"Report failed: {e}")

async def process_queue():
    conn = get_db()
    c = conn.cursor()

    # Get scripted stories not yet queued
    c.execute("""
        SELECT id, title, source, score, format,
               winning_hook, script, caption, video_path
        FROM stories
        WHERE status IN ('video_ready', 'scripted')
        ORDER BY score DESC
        LIMIT 5
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        log.info("No scripted stories to queue")
        return 0

    log.info(f"=== Sending {len(rows)} items to Queue channel ===")
    sent_count = 0

    for r in rows:
        story = {
            "id": r[0], "title": r[1], "source": r[2],
            "score": r[3], "format": r[4], "winning_hook": r[5],
            "script": r[6], "caption": r[7], "video_path": r[8]
        }

        log.info(f"Queueing: {story['title'][:60]}")
        msg_id = await send_queue_item(story)

        if msg_id:
            conn = get_db()
            c = conn.cursor()
            c.execute("""
                UPDATE stories SET
                    status = 'queued',
                    queued_at = ?,
                    telegram_msg_id = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), str(msg_id), story["id"]))
            conn.commit()
            conn.close()
            sent_count += 1

    log.info(f"=== Queue complete — {sent_count}/{len(rows)} sent ===")
    return sent_count

if __name__ == "__main__":
    # First test — send the scripted video to queue
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, source, score, format,
               winning_hook, script, caption, video_path
        FROM stories WHERE status IN ('video_ready', 'scripted')
        ORDER BY score DESC LIMIT 1
    """)
    r = c.fetchone()
    conn.close()

    if r:
        story = {
            "id": r[0], "title": r[1], "source": r[2],
            "score": r[3], "format": r[4], "winning_hook": r[5],
            "script": r[6], "caption": r[7],
            "video_path": f"/root/90minwaffle/data/test_video_{r[0]}.mp4"
        }
        asyncio.run(process_queue())
    else:
        print("No scripted stories found")
