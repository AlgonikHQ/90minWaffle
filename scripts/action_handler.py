#!/usr/bin/env python3
"""
90minWaffle Action Handler
Listens for P/B/D/R replies in the Queue Telegram channel and acts on them.
P = Publish (mark as published, post to Discord)
B = Bin (mark as skipped, remove from queue)
D = Delay (push back 2 hours)
R = Regenerate (re-run script generation)
"""
import asyncio
import sqlite3
import logging
import os
import importlib.util
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

load_dotenv('/root/90minwaffle/.env')

DB_PATH   = "/root/90minwaffle/data/waffle.db"
LOG_PATH  = "/root/90minwaffle/logs/action_handler.log"
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
QUEUE_CHAT = int(os.getenv("TELEGRAM_QUEUE_CHAT_ID"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def get_db():
    return sqlite3.connect(DB_PATH)

def import_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def get_story_by_msg_id(msg_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, score, format, script, video_path, status
        FROM stories WHERE telegram_msg_id = ?
    """, (str(msg_id),))
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "title": row[1], "score": row[2],
                "format": row[3], "script": row[4], "video_path": row[5],
                "status": row[6]}
    return None

def get_latest_queued_story():
    """Fallback — get the most recently queued story if no msg_id match."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, score, format, script, video_path, status, source, winning_hook, caption
        FROM stories WHERE status = 'queued'
        ORDER BY queued_at DESC LIMIT 1
    """)
    row = c.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "title": row[1], "score": row[2],
                "format": row[3], "script": row[4], "video_path": row[5],
                "status": row[6], "source": row[7], "winning_hook": row[8],
                "caption": row[9]}
    return None

async def action_publish(story, bot, chat_id):
    """P — Mark as published and post to Discord."""
    try:
        dp = import_module("discord_poster", "/root/90minwaffle/scripts/discord_poster.py")

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT source, winning_hook, caption FROM stories WHERE id=?", (story["id"],))
        row = c.fetchone()
        conn.close()

        full_story = {**story, "source": row[0], "winning_hook": row[1], "caption": row[2]}
        channel_key = dp.FORMAT_CHANNEL.get(story["format"], "breaking_news")
        success = dp.post_to_discord(full_story, channel_key)

        if success:
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE stories SET status='published' WHERE id=?", (story["id"],))
            conn.commit()
            conn.close()
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ *Published to Discord* #{channel_key}\n_{story['title'][:80]}_",
                parse_mode=ParseMode.MARKDOWN
            )
            log.info(f"Published story {story['id']}: {story['title'][:60]}")
        else:
            await bot.send_message(chat_id=chat_id, text="❌ Discord post failed — check logs")

    except Exception as e:
        log.error(f"Publish failed: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Error: {e}")

async def action_bin(story, bot, chat_id):
    """B — Bin the story."""
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE stories SET status='binned' WHERE id=?", (story["id"],))
    conn.commit()
    conn.close()
    await bot.send_message(
        chat_id=chat_id,
        text=f"🗑️ *Binned*\n_{story['title'][:80]}_",
        parse_mode=ParseMode.MARKDOWN
    )
    log.info(f"Binned story {story['id']}: {story['title'][:60]}")

async def action_delay(story, bot, chat_id):
    """D — Delay by 2 hours (keep queued, update queued_at)."""
    delay_until = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE stories SET queued_at=? WHERE id=?", (delay_until, story["id"]))
    conn.commit()
    conn.close()
    await bot.send_message(
        chat_id=chat_id,
        text=f"⏰ *Delayed 2 hours*\n_{story['title'][:80]}_",
        parse_mode=ParseMode.MARKDOWN
    )
    log.info(f"Delayed story {story['id']}: {story['title'][:60]}")

async def action_regen(story, bot, chat_id):
    """R — Regenerate script and video."""
    await bot.send_message(
        chat_id=chat_id,
        text=f"🔄 *Regenerating script...*\n_{story['title'][:80]}_",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        # Reset story to shippable for re-processing
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE stories SET status='shippable', script=NULL, video_path=NULL WHERE id=?",
                  (story["id"],))
        conn.commit()
        conn.close()

        # Re-generate script
        sg = import_module("script_gen", "/root/90minwaffle/scripts/script_gen.py")
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id,title,url,source,source_tier,score,format FROM stories WHERE id=?",
                  (story["id"],))
        row = c.fetchone()
        conn.close()

        if row:
            full_story = {"id":row[0],"title":row[1],"url":row[2],
                         "source":row[3],"source_tier":row[4],"score":row[5],"format":row[6]}
            result = sg.generate_script(full_story)
            if result:
                sg.save_script(story["id"], result)

                # Re-produce video
                va = import_module("video_assembler", "/root/90minwaffle/scripts/video_assembler.py")
                conn = get_db()
                c = conn.cursor()
                c.execute("SELECT script FROM stories WHERE id=?", (story["id"],))
                new_script = c.fetchone()[0]
                conn.close()

                video_story = {**full_story, "script": new_script}
                video_path = va.produce_video(video_story)

                if video_path:
                    # Re-queue
                    qn = import_module("queue_notifier", "/root/90minwaffle/scripts/queue_notifier.py")
                    conn = get_db()
                    c = conn.cursor()
                    c.execute("""SELECT id,title,source,score,format,winning_hook,script,caption,video_path
                                 FROM stories WHERE id=?""", (story["id"],))
                    r = c.fetchone()
                    conn.close()
                    new_story = {"id":r[0],"title":r[1],"source":r[2],"score":r[3],
                                "format":r[4],"winning_hook":r[5],"script":r[6],
                                "caption":r[7],"video_path":r[8]}
                    await qn.send_queue_item(new_story)
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"✅ *Regenerated + re-queued*\n_{story['title'][:80]}_",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    log.info(f"Regenerated story {story['id']}")
                    return

        await bot.send_message(chat_id=chat_id, text="❌ Regeneration failed")

    except Exception as e:
        log.error(f"Regen failed: {e}")
        await bot.send_message(chat_id=chat_id, text=f"❌ Error: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages in the Queue channel."""
    if not update.message:
        return

    chat_id = update.message.chat_id
    if chat_id != QUEUE_CHAT:
        return

    text = update.message.text.strip().upper() if update.message.text else ""
    if text not in ["P", "B", "D", "R"]:
        return

    bot = context.bot

    # Try to find story from replied-to message
    story = None
    if update.message.reply_to_message:
        replied_msg_id = update.message.reply_to_message.message_id
        story = get_story_by_msg_id(replied_msg_id)

    # Fallback to latest queued
    if not story:
        story = get_latest_queued_story()

    if not story:
        await bot.send_message(chat_id=chat_id, text="❌ No queued story found to action")
        return

    log.info(f"Action '{text}' on story {story['id']}: {story['title'][:60]}")

    if text == "P":
        await action_publish(story, bot, chat_id)
    elif text == "B":
        await action_bin(story, bot, chat_id)
    elif text == "D":
        await action_delay(story, bot, chat_id)
    elif text == "R":
        await action_regen(story, bot, chat_id)

async def send_startup_message():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id=QUEUE_CHAT,
        text="🤖 *Action Handler online*\nReply to any queue card with:\nP = Publish | B = Bin | D = Delay | R = Regenerate",
        parse_mode=ParseMode.MARKDOWN
    )

def main():
    log.info("Starting 90minWaffle Action Handler...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Send startup message
    asyncio.get_event_loop().run_until_complete(send_startup_message())

    log.info("Action Handler running — listening for P/B/D/R replies")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
