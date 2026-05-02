#!/usr/bin/env python3
"""
performance_tracker.py — Feedback loop for 90minWaffle content scoring.

Pulls Telegram message view counts for published stories and writes them
back into stories.views_1h, views_24h, views_7d, performance_score.

Performance score feeds back into future scoring — formats/sources that
consistently produce high-view content get a positive weight applied
to similar future stories.

Called from orchestrator on heavy cycles.
"""

import sqlite3, logging, asyncio, os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/performance_tracker.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))


def get_db():
    return sqlite3.connect(DB_PATH)


async def get_message_views(message_id: str) -> int | None:
    """Fetch view count for a Telegram message via getMessages."""
    if not BOT_TOKEN or not NEWS_CHANNEL or not message_id:
        return None
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)
        # forward_from_message_id workaround — get message via forwardMessage
        # then delete. Only way to get views without MTProto.
        # For channels, views are on the Message object directly.
        msgs = await bot.get_chat(NEWS_CHANNEL)
        # Use copyMessage to get view count indirectly
        # python-telegram-bot doesn't expose getMessages directly
        # Use raw API call instead
        import requests
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getMessages",
            params={
                "chat_id": NEWS_CHANNEL,
                "message_ids": f"[{message_id}]"
            },
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            messages = data.get("result", {}).get("messages", [])
            if messages:
                return messages[0].get("views", 0)
        return None
    except Exception as e:
        log.debug(f"View fetch failed for msg {message_id}: {e}")
        return None


def calc_performance_score(views_1h: int, views_24h: int, views_7d: int,
                            format_code: str, source_tier: int) -> int:
    """
    Calculate a 0-100 performance score from view counts.
    Benchmarks based on early channel size — will auto-calibrate as audience grows.

    Tier thresholds (views_24h):
      <50    → poor (0-20)
      50-150 → average (20-50)
      150-500 → good (50-75)
      500+   → excellent (75-100)
    """
    if views_24h is None:
        views_24h = 0
    if views_1h is None:
        views_1h = 0

    # Base score from 24h views
    if views_24h >= 500:
        base = 90
    elif views_24h >= 200:
        base = 75
    elif views_24h >= 100:
        base = 55
    elif views_24h >= 50:
        base = 35
    elif views_24h >= 20:
        base = 20
    else:
        base = 5

    # Early velocity bonus — high 1h views suggest viral potential
    if views_1h >= 100:
        base = min(100, base + 15)
    elif views_1h >= 50:
        base = min(100, base + 8)

    return base


def update_views():
    """
    Pull view counts for stories published in the last 7 days
    that have a telegram_msg_id and update their performance metrics.
    """
    conn = get_db()
    c    = conn.cursor()

    # Stories published in last 7 days with Telegram msg IDs
    c.execute("""
        SELECT id, telegram_msg_id, format, source_tier,
               views_1h, views_24h, views_7d,
               published_at_tg, score
        FROM stories
        WHERE telegram_msg_id IS NOT NULL
        AND telegram_msg_id != ''
        AND status = 'published'
        AND datetime(created_at) > datetime('now', '-7 days')
        ORDER BY id DESC
        LIMIT 50
    """)
    rows = c.fetchall()
    conn.close()

    if not rows:
        log.info("No published stories with Telegram IDs to track")
        return 0

    log.info(f"Checking views for {len(rows)} published stories")
    updated = 0

    for row in rows:
        story_id, msg_id, fmt, tier, v1h, v24h, v7d, pub_at, score = row

        views = asyncio.run(_fetch_views_sync(msg_id))
        if views is None:
            continue

        # Determine which bucket to update based on age
        now = datetime.now(timezone.utc)
        try:
            pub_dt = datetime.fromisoformat(pub_at) if pub_at else now
        except Exception:
            pub_dt = now

        age_hours = (now - pub_dt).total_seconds() / 3600

        conn = get_db()
        c    = conn.cursor()

        if age_hours <= 1:
            c.execute("UPDATE stories SET views_1h=? WHERE id=?", (views, story_id))
        elif age_hours <= 24:
            c.execute("UPDATE stories SET views_24h=? WHERE id=?", (views, story_id))
        else:
            c.execute("UPDATE stories SET views_7d=? WHERE id=?", (views, story_id))

        # Recalculate performance score with latest data
        c.execute("SELECT views_1h, views_24h, views_7d FROM stories WHERE id=?", (story_id,))
        latest = c.fetchone()
        if latest:
            perf = calc_performance_score(
                latest[0] or 0, latest[1] or 0, latest[2] or 0,
                fmt or "F7", tier or 2
            )
            c.execute(
                "UPDATE stories SET performance_score=? WHERE id=?",
                (perf, story_id)
            )
            if perf > 60:
                log.info(f"  ⭐ [{perf}] story {story_id} performing well ({views} views)")

        conn.commit()
        conn.close()
        updated += 1

    log.info(f"=== Performance update done — {updated} stories tracked ===")
    return updated


async def _fetch_views_sync(msg_id: str) -> int | None:
    """Sync wrapper for view fetching."""
    return await get_message_views(msg_id)


def get_top_performing_formats() -> dict:
    """
    Return average performance score by format.
    Used by scorer.py to apply a performance weight to future stories.
    """
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT format,
               COUNT(*) as count,
               ROUND(AVG(performance_score), 1) as avg_perf,
               ROUND(AVG(views_24h), 0) as avg_views
        FROM stories
        WHERE performance_score > 0
        AND datetime(created_at) > datetime('now', '-30 days')
        GROUP BY format
        ORDER BY avg_perf DESC
    """)
    rows = c.fetchall()
    conn.close()
    return {r[0]: {"count": r[1], "avg_perf": r[2], "avg_views": r[3]} for r in rows}


def get_top_performing_sources() -> dict:
    """Return average performance score by source."""
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT source,
               COUNT(*) as count,
               ROUND(AVG(performance_score), 1) as avg_perf
        FROM stories
        WHERE performance_score > 0
        AND datetime(created_at) > datetime('now', '-30 days')
        GROUP BY source
        ORDER BY avg_perf DESC
        LIMIT 15
    """)
    rows = c.fetchall()
    conn.close()
    return {r[0]: {"count": r[1], "avg_perf": r[2]} for r in rows}


if __name__ == "__main__":
    update_views()
    print("\n=== FORMAT PERFORMANCE ===")
    for fmt, data in get_top_performing_formats().items():
        print(f"  {fmt}: avg_perf={data['avg_perf']} avg_views={data['avg_views']} ({data['count']} stories)")
    print("\n=== SOURCE PERFORMANCE ===")
    for src, data in get_top_performing_sources().items():
        print(f"  {src}: avg_perf={data['avg_perf']} ({data['count']} stories)")
