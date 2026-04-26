#!/usr/bin/env python3
"""
90minWaffle Weekly Report Generator
Sends a Sunday digest to the Reports Telegram channel.
"""
import asyncio
import sqlite3
import logging
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv('/root/90minwaffle/.env')

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/reports.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def get_db():
    return sqlite3.connect(DB_PATH)

def get_week_stats():
    conn = get_db()
    c = conn.cursor()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Total stories ingested
    c.execute("SELECT COUNT(*) FROM stories WHERE fetched_at >= ?", (week_ago,))
    total_ingested = c.fetchone()[0]

    # Stories by status
    c.execute("""
        SELECT status, COUNT(*) FROM stories
        WHERE fetched_at >= ?
        GROUP BY status
    """, (week_ago,))
    status_counts = dict(c.fetchall())

    # Videos produced
    c.execute("""
        SELECT COUNT(*) FROM stories
        WHERE video_path IS NOT NULL AND fetched_at >= ?
    """, (week_ago,))
    videos_produced = c.fetchone()[0]

    # Published to Discord
    c.execute("""
        SELECT COUNT(*) FROM stories
        WHERE status = 'published' AND fetched_at >= ?
    """, (week_ago,))
    published = c.fetchone()[0]

    # Top stories by score
    c.execute("""
        SELECT title, score, format, source
        FROM stories
        WHERE fetched_at >= ?
        ORDER BY score DESC
        LIMIT 5
    """, (week_ago,))
    top_stories = c.fetchall()

    # Format breakdown
    c.execute("""
        SELECT format, COUNT(*) FROM stories
        WHERE status IN ('scripted','queued','published')
        AND fetched_at >= ?
        GROUP BY format
        ORDER BY COUNT(*) DESC
    """, (week_ago,))
    format_breakdown = c.fetchall()

    # Source breakdown
    c.execute("""
        SELECT source, COUNT(*) FROM stories
        WHERE fetched_at >= ?
        GROUP BY source
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """, (week_ago,))
    top_sources = c.fetchall()

    conn.close()

    return {
        "total_ingested": total_ingested,
        "status_counts": status_counts,
        "videos_produced": videos_produced,
        "published": published,
        "top_stories": top_stories,
        "format_breakdown": format_breakdown,
        "top_sources": top_sources,
    }

def format_report(stats):
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%d %b")
    week_end = now.strftime("%d %b %Y")

    FORMAT_NAMES = {
        "F1": "Confirmed Transfer",
        "F2": "Transfer Rumour",
        "F3": "Match Preview",
        "F4": "Post-Match",
        "F5": "Title Race",
        "F6": "Star Spotlight",
        "F7": "Hot Take",
    }

    # Top stories section
    top_stories_text = ""
    for i, (title, score, fmt, source) in enumerate(stats["top_stories"], 1):
        top_stories_text += f"  {i}. [{score}] {title[:55]}\n"

    # Format breakdown
    fmt_text = ""
    for fmt, count in stats["format_breakdown"]:
        fmt_text += f"  • {FORMAT_NAMES.get(fmt, fmt)}: {count}\n"

    # Source breakdown
    src_text = ""
    for source, count in stats["top_sources"]:
        src_text += f"  • {source}: {count}\n"

    shippable = stats["status_counts"].get("shippable", 0)
    scripted  = stats["status_counts"].get("scripted", 0)
    queued    = stats["status_counts"].get("queued", 0)
    skipped   = stats["status_counts"].get("skipped", 0)

    report = f"""📊 *90minWaffle Weekly Report*
_{week_start} → {week_end}_
━━━━━━━━━━━━━━━━━━━━

📥 *Ingestion*
Stories scanned: `{stats['total_ingested']}`
Shippable: `{shippable}`
Skipped/noise: `{skipped}`

🎬 *Production*
Videos produced: `{stats['videos_produced']}`
Sent to queue: `{queued}`
Published to Discord: `{stats['published']}`

🏆 *Top Stories This Week*
{top_stories_text}
📋 *Format Breakdown*
{fmt_text}
📰 *Top Sources*
{src_text}
━━━━━━━━━━━━━━━━━━━━
_Next report: Sunday_"""

    return report

async def send_weekly_report():
    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    chat_id = int(os.getenv("TELEGRAM_REPORTS_CHAT_ID"))

    log.info("Generating weekly report...")
    stats = get_week_stats()
    report = format_report(stats)

    await bot.send_message(
        chat_id=chat_id,
        text=report,
        parse_mode=ParseMode.MARKDOWN
    )
    log.info("✅ Weekly report sent to Reports channel")

async def send_daily_summary():
    """Shorter daily summary for the Reports channel."""
    from telegram import Bot
    from telegram.constants import ParseMode

    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    chat_id = int(os.getenv("TELEGRAM_REPORTS_CHAT_ID"))

    conn = get_db()
    c = conn.cursor()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    c.execute("SELECT COUNT(*) FROM stories WHERE fetched_at LIKE ?", (f"{today}%",))
    ingested = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM stories WHERE video_path IS NOT NULL AND fetched_at LIKE ?", (f"{today}%",))
    videos = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM stories WHERE status='published' AND fetched_at LIKE ?", (f"{today}%",))
    published = c.fetchone()[0]

    c.execute("""SELECT title, score FROM stories
        WHERE fetched_at LIKE ? ORDER BY score DESC LIMIT 3""", (f"{today}%",))
    top3 = c.fetchall()
    conn.close()

    top3_text = "\n".join([f"  {i+1}. ⭐{s}/100 — {t[:65]}" for i, (t, s) in enumerate(top3)])

    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    msg = f"""📋 *90minWaffle Daily Summary — {now}*
━━━━━━━━━━━━━━━━━━━━
📥 Ingested: `{ingested}` stories
🎬 Videos: `{videos}` produced
📤 Published: `{published}` to Discord

🏆 Top stories today:
{top3_text}
━━━━━━━━━━━━━━━━━━━━"""

    await bot.send_message(chat_id=chat_id, text=msg, parse_mode=ParseMode.MARKDOWN)
    log.info("✅ Daily summary sent")

if __name__ == "__main__":
    import sys
    if "--daily" in sys.argv:
        asyncio.run(send_daily_summary())
    else:
        asyncio.run(send_weekly_report())
