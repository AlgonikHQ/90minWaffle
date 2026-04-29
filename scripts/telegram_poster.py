#!/usr/bin/env python3
import asyncio, sqlite3, logging, os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
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

def _relative_time(story):
    """Return '4 mins ago' style string from published_at or fetched_at."""
    from datetime import datetime, timezone
    for field in ("published_at", "fetched_at"):
        val = story.get(field)
        if not val:
            continue
        try:
            if val.endswith("Z"):
                val = val[:-1] + "+00:00"
            dt = datetime.fromisoformat(val).astimezone(timezone.utc)
            delta = int((datetime.now(timezone.utc) - dt).total_seconds())
            if delta < 60:
                return "just now"
            elif delta < 3600:
                return f"{delta // 60}m ago"
            elif delta < 86400:
                return f"{delta // 3600}h ago"
            else:
                return f"{delta // 86400}d ago"
        except Exception:
            continue
    return ""

FORMAT_BADGE = {
    "F1": "🟢 CONFIRMED TRANSFER",
    "F2": "🔴 TRANSFER RUMOUR",
    "F3": "🔵 MATCH DAY",
    "F4": "🟠 FULL TIME",
    "F5": "🏆 TITLE RACE",
    "F6": "⭐ STAR SPOTLIGHT",
    "F7": "🔥 HOT TAKE",
    "F8": "🎯 TIPS & BETS",
    "F9": "👩 WOMENS FOOTBALL",
}

def build_news_message(story):
    fmt     = story.get("format", "F7")
    caption = story.get("caption", "") or ""
    source  = story.get("source", "") or ""
    hook    = story.get("winning_hook", "") or story.get("title", "")
    score   = story.get("score", 0)

    badge   = FORMAT_BADGE.get(fmt, "🔥 HOT TAKE")
    reltime = _relative_time(story)

    # Split caption into body lines and hashtags
    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    hashtags = " ".join(w for l in lines for w in l.split() if w.startswith("#"))
    body_lines = [l for l in lines if not all(w.startswith("#") for w in l.split())]
    body = " ".join(body_lines).replace(hashtags, "").strip()
    # Strip inline hashtags from body
    body = " ".join(w for w in body.split() if not w.startswith("#")).strip()

    # Pull CTA question from caption
    questions = [l for l in lines if "?" in l and not l.startswith("#")]
    cta = questions[0][:80] if questions else ""

    # Trim hashtags to top 5
    tags = hashtags.split()[:5]
    hashtag_line = " ".join(tags)

    # Source + time footer
    source_line = f"_{source}_" if not reltime else f"_{source} · {reltime}_"

    # Build message
    parts = [
        f"*{badge}*",
        "",
        f"*{hook}*",
    ]
    if body and len(body) > 20:
        parts += ["", body]
    if cta:
        parts += ["", f"⚡ {cta}"]
    parts += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        source_line,
    ]
    if hashtag_line:
        parts.append(hashtag_line)
    parts += [
        "",
        "📺 YouTube  •  🐦 @90minWaffle  •  🎵 TikTok",
    ]
    return "\n".join(parts)

# ── News channel (public) ─────────────────────────────────────────────────────
def build_news_buttons(story):
    buttons=[]
    if story.get("url"):
        buttons.append(InlineKeyboardButton("🔗 Read More", url=story["url"]))
    buttons.append(InlineKeyboardButton("🐦 @90minWaffle", url="https://twitter.com/90minwaffle"))
    buttons.append(InlineKeyboardButton("📺 YouTube", url="https://youtube.com/@90minwaffle"))
    buttons.append(InlineKeyboardButton("🎵 TikTok", url="https://tiktok.com/@90minwaffle"))
    keyboard=[]
    if story.get("url"):
        keyboard.append([buttons[0]])
        keyboard.append(buttons[1:])
    else:
        keyboard.append(buttons)
    return InlineKeyboardMarkup(keyboard)

async def post_to_news(story):
    bot = Bot(token=BOT_TOKEN)
    video_path = story.get("video_path")
    msg = build_news_message(story)
    markup = build_news_buttons(story)
    try:
        if video_path and os.path.exists(video_path):
            with open(video_path, "rb") as vf:
                await bot.send_video(chat_id=NEWS_CHANNEL, video=vf,
                    caption=msg, parse_mode=ParseMode.MARKDOWN,
                    reply_markup=markup, supports_streaming=True)
        else:
            await bot.send_message(chat_id=NEWS_CHANNEL, text=msg,
                parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        log.info(f"  Posted to News: {story['title'][:60]}")
        return True
    except Exception as e:
        log.error(f"  News post failed: {e}")
        return False

async def process_news_queue(limit=3):
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT id, title, url, source, score, format, winning_hook, caption, video_path
        FROM stories WHERE status='queued'
        AND format IN ('F1','F2','F3','F4','F5','F6','F7')
        ORDER BY score DESC LIMIT ?""", (limit,))
    rows = c.fetchall(); conn.close()
    if not rows: log.info("No stories for News channel"); return 0
    log.info(f"=== Posting {len(rows)} to News channel ===")
    posted = 0
    for r in rows:
        story = {"id":r[0],"title":r[1],"url":r[2],"source":r[3],"score":r[4],"format":r[5],
                 "winning_hook":r[6],"caption":r[7],"video_path":r[8]}
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

async def send_quota_alert(remaining, limit):
    if not ALERTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        pct = int((remaining / limit) * 100) if limit else 0
        parts = [
            "⚠️ *ElevenLabs Quota Warning*",
            "━" * 20,
            "Remaining: `" + str(remaining) + "` chars (`" + str(pct) + "%` left)",
            "Limit: `" + str(limit) + "` chars/month",
            "Videos will be skipped until quota resets.",
            "_Upgrade at elevenlabs.io if needed_"
        ]
        msg = "\n".join(parts)
        await bot.send_message(chat_id=ALERTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
        log.info("  Quota alert sent")
    except Exception as e:
        log.error(f"  Quota alert failed: {e}")

async def send_rss_alert(feed_name, error):
    if not ALERTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        parts = ["⚠️ *RSS Feed Failure*", "", "Feed: `" + str(feed_name) + "`", "Error: `" + str(error)[:200] + "`"]
        msg = "\n".join(parts)
        await bot.send_message(chat_id=ALERTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"  RSS alert failed: {e}")

async def send_midnight_summary(stats):
    if not REPORTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        from datetime import datetime, timezone
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        parts = [
            "📋 *90minWaffle Daily Summary*",
            "━" * 20,
            "Stories ingested: `" + str(stats.get("stories", 0)) + "`",
            "Shippable: `" + str(stats.get("shippable", 0)) + "`",
            "Videos produced: `" + str(stats.get("videos", 0)) + "`",
            "Posts sent: `" + str(stats.get("posted", 0)) + "`",
            "━" * 20,
            "_90minWaffle — " + date_str + "_"
        ]
        msg = "\n".join(parts)
        await bot.send_message(chat_id=REPORTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
        log.info("  Midnight summary sent")
    except Exception as e:
        log.error(f"  Midnight summary failed: {e}")

if __name__ == "__main__":
    asyncio.run(process_news_queue(limit=3))
