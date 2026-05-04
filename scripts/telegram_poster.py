#!/usr/bin/env python3
"""telegram_poster.py — Telegram posting for 90minWaffle.

Changes vs previous version:
  - Public NEWS channel now has a quality gate — only top-tier stories post
  - Hard rate limit: max 4 posts per hour to public channel
  - Format/score thresholds per format type (F1/F2 always post, F7 needs >=55)
  - F8 TIPS routes to bets channel only — never public
  - Rate limit tracked via data/telegram_rate.json
"""

import asyncio, sqlite3, logging, os, json, time
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv("/root/90minwaffle/.env")

DB_PATH   = "/root/90minwaffle/data/waffle.db"
LOG_PATH  = "/root/90minwaffle/logs/telegram_poster.log"
DATA_DIR  = "/root/90minwaffle/data"
RATE_FILE = os.path.join(DATA_DIR, "telegram_rate.json")

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

# ── Quality gate: minimum score per format for PUBLIC channel ─────────────────
# F1/F2 confirmed/rumour transfers always go through (breaking news)
# F7 hot takes need higher bar — only the best opinion pieces
# Everything else needs score >= 50
PUBLIC_QUALITY_GATE = {
    "F1": 0,    # confirmed transfer — always post
    "F2": 40,   # transfer rumour — decent threshold
    "F3": 55,   # match preview — only strong ones
    "F4": 50,   # post-match — solid results only
    "F5": 45,   # title race — most are good
    "F6": 55,   # star spotlight — genuine spotlights only
    "F7": 55,   # hot take — best opinion only, not every reaction piece
    "F8": 999,  # tips — NEVER to public, bets channel only
    "F9": 45,   # women's football
}

# Hard cap: max posts per hour to public channel
MAX_POSTS_PER_HOUR = 4

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

# ── Rate limiter ──────────────────────────────────────────────────────────────

def _load_rate() -> dict:
    if not os.path.exists(RATE_FILE):
        return {"posts": []}
    try:
        with open(RATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"posts": []}

def _save_rate(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(RATE_FILE, "w") as f:
        json.dump(data, f)

def _can_post_public() -> bool:
    """Return True if we're under the hourly rate limit."""
    data  = _load_rate()
    now   = time.time()
    hour_ago = now - 3600
    # Keep only posts in the last hour
    recent = [ts for ts in data.get("posts", []) if ts > hour_ago]
    if len(recent) >= MAX_POSTS_PER_HOUR:
        log.info(f"  [rate_limit] {len(recent)}/{MAX_POSTS_PER_HOUR} posts this hour — skipping")
        return False
    return True

def _record_post() -> None:
    data  = _load_rate()
    now   = time.time()
    hour_ago = now - 3600
    posts = [ts for ts in data.get("posts", []) if ts > hour_ago]
    posts.append(now)
    _save_rate({"posts": posts})

def _passes_quality_gate(story: dict) -> bool:
    """Return True if story meets the quality bar for the public channel."""
    fmt   = story.get("format", "F7")
    score = story.get("score", 0) or 0
    min_score = PUBLIC_QUALITY_GATE.get(fmt, 50)
    if score < min_score:
        log.info(f"  [quality_gate] Blocked {fmt} score={score} (min={min_score}): {story.get('title','')[:50]}")
        return False
    return True

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_db(): return sqlite3.connect(DB_PATH)

def _relative_time(story):
    for field in ("published_at", "fetched_at"):
        val = story.get(field)
        if not val:
            continue
        try:
            if val.endswith("Z"):
                val = val[:-1] + "+00:00"
            dt = datetime.fromisoformat(val).astimezone(timezone.utc)
            delta = int((datetime.now(timezone.utc) - dt).total_seconds())
            if delta < 60:   return "just now"
            elif delta < 3600:  return f"{delta // 60}m ago"
            elif delta < 86400: return f"{delta // 3600}h ago"
            else:               return f"{delta // 86400}d ago"
        except Exception:
            continue
    return ""

# ── Message builder ───────────────────────────────────────────────────────────

def build_news_message(story):
    fmt     = story.get("format", "F7")
    caption = story.get("caption", "") or ""
    source  = (story.get("source", "") or "").replace(" Football","").replace(" Sport Football","").strip()
    hook    = story.get("winning_hook", "") or story.get("title", "")
    score   = story.get("score", 0)

    badge   = FORMAT_BADGE.get(fmt, "🔥 HOT TAKE")
    reltime = _relative_time(story)

    lines = [l.strip() for l in caption.split("\n") if l.strip()]
    hashtags = " ".join(w for l in lines for w in l.split() if w.startswith("#"))
    body_lines = [l for l in lines if not all(w.startswith("#") for w in l.split())]
    body = " ".join(body_lines).replace(hashtags, "").strip()
    body = " ".join(w for w in body.split() if not w.startswith("#")).strip()

    questions = [l for l in lines if "?" in l and not l.startswith("#")]
    cta = questions[0][:80] if questions else ""

    tags = hashtags.split()[:5]
    hashtag_line = " ".join(tags)

    source_line = f"_{source}_" if not reltime else f"_{source} · {reltime}_"

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

# ── Button builder ────────────────────────────────────────────────────────────

def build_news_buttons(story):
    buttons = []
    if story.get("url"):
        buttons.append(InlineKeyboardButton("🔗 Read More", url=story["url"]))
    buttons.append(InlineKeyboardButton("🐦 @90minWaffle", url="https://twitter.com/90minwaffle"))
    buttons.append(InlineKeyboardButton("📺 YouTube", url="https://youtube.com/@90minwaffle"))
    buttons.append(InlineKeyboardButton("🎵 TikTok", url="https://tiktok.com/@90minwaffle"))
    keyboard = []
    if story.get("url"):
        keyboard.append([buttons[0]])
        keyboard.append(buttons[1:])
    else:
        keyboard.append(buttons)
    return InlineKeyboardMarkup(keyboard)

# ── Post to public news channel ───────────────────────────────────────────────

async def post_to_news(story):
    """Post story to public channel — quality gate + rate limit applied."""
    # Quality gate
    if not _passes_quality_gate(story):
        return False
    # Rate limit
    if not _can_post_public():
        return False

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
            # Try image waterfall
            img_url = None
            try:
                import sys
                sys.path.insert(0, "/root/90minwaffle/scripts")
                from image_resolver import resolve_image
                img_url = resolve_image(story)
            except Exception as e:
                log.debug(f"  Image resolve failed: {e}")

            if img_url and img_url.startswith("http"):
                await bot.send_photo(chat_id=NEWS_CHANNEL, photo=img_url,
                    caption=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
            elif img_url and img_url.startswith("/"):
                with open(img_url, "rb") as f:
                    await bot.send_photo(chat_id=NEWS_CHANNEL, photo=f,
                        caption=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
            else:
                await bot.send_message(chat_id=NEWS_CHANNEL, text=msg,
                    parse_mode=ParseMode.MARKDOWN, reply_markup=markup)

        _record_post()
        log.info(f"  ✅ Posted to News [{story.get('format','?')} score={story.get('score',0)}]: {story['title'][:60]}")
        return True

    except Exception as e:
        log.error(f"  News post failed: {e}")
        return False

# ── Post to Telegram bets channel (F8 only) ──────────────────────────────────

async def post_to_bets_channel(story):
    """Post F8 tips/bets story to Telegram bets channel."""
    if not BETS_CHANNEL:
        log.warning("  BETS_CHANNEL not configured — skipping")
        return False
    bot = Bot(token=BOT_TOKEN)
    hook  = story.get("winning_hook") or story.get("title", "")
    source = story.get("source", "")
    url   = story.get("url", "")

    msg = "\n".join([
        "🎯 *TIPS & BETS*",
        "",
        f"*{hook}*",
        "",
        f"_{source}_",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "📺 YouTube  •  🐦 @90minWaffle  •  🎵 TikTok",
    ])
    buttons = []
    if url:
        buttons.append(InlineKeyboardButton("🔗 Read More", url=url))
    buttons.append(InlineKeyboardButton("🐦 @90minWaffle", url="https://twitter.com/90minwaffle"))
    keyboard = [[buttons[0]], buttons[1:]] if url else [buttons]
    markup = InlineKeyboardMarkup(keyboard)

    try:
        # Try image first
        img_url = None
        try:
            import sys
            sys.path.insert(0, "/root/90minwaffle/scripts")
            from image_resolver import resolve_image
            img_url = resolve_image(story)
        except Exception:
            pass

        if img_url and img_url.startswith("http"):
            await bot.send_photo(chat_id=BETS_CHANNEL, photo=img_url,
                caption=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        elif img_url and img_url.startswith("/"):
            with open(img_url, "rb") as f:
                await bot.send_photo(chat_id=BETS_CHANNEL, photo=f,
                    caption=msg, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        else:
            await bot.send_message(chat_id=BETS_CHANNEL, text=msg,
                parse_mode=ParseMode.MARKDOWN, reply_markup=markup)

        log.info(f"  ✅ Posted to Bets channel: {story.get('title','')[:60]}")
        return True
    except Exception as e:
        log.error(f"  Bets channel post failed: {e}")
        return False


# ── Process queue ─────────────────────────────────────────────────────────────

async def process_news_queue(limit=5):
    # Enforce daily Telegram cap — prevents flooding the single public channel
    from datetime import datetime as _dt
    _today = _dt.utcnow().strftime("%Y-%m-%d")
    conn_cap = get_db()
    _posted_today = conn_cap.execute(
        "SELECT COUNT(*) FROM stories WHERE status='published' AND published_at_tg LIKE ?",
        (_today + "%",)
    ).fetchone()[0]
    conn_cap.close()
    if _posted_today >= TELEGRAM_DAILY_CAP:
        log.info(f"  [telegram] Daily cap reached ({_posted_today}/{TELEGRAM_DAILY_CAP}) — skipping")
        return 0
    """Pull top stories from queue and post — quality gate applied per story.
    F8 (Tips & Bets) routes to bets channel only, never public news channel.
    """
    conn = get_db(); c = conn.cursor()
    fetch_limit = limit * 3
    c.execute("""
        SELECT id, title, url, source, score, format, winning_hook, caption, video_path
        FROM stories WHERE status='queued'
        AND format IN ('F1','F2','F3','F4','F5','F6','F7','F8','F9')
        ORDER BY score DESC LIMIT ?
    """, (fetch_limit,))
    rows = c.fetchall(); conn.close()

    if not rows:
        log.info("No stories in queue")
        return 0

    log.info(f"=== Processing {len(rows)} queued stories (limit={limit}) ===")
    posted = 0

    for r in rows:
        if posted >= limit:
            break
        story = {
            "id": r[0], "title": r[1], "url": r[2], "source": r[3],
            "score": r[4], "format": r[5], "winning_hook": r[6],
            "caption": r[7], "video_path": r[8]
        }

        # F8 — route to bets channel, never public
        if story["format"] == "F8":
            if await post_to_bets_channel(story):
                conn = get_db(); c = conn.cursor()
                c.execute("UPDATE stories SET status='published' WHERE id=?", (story["id"],))
                conn.commit(); conn.close()
                posted += 1
            continue

        # All other formats — public news channel with quality gate
        if await post_to_news(story):
            conn = get_db(); c = conn.cursor()
            c.execute("UPDATE stories SET status='published' WHERE id=?", (story["id"],))
            conn.commit(); conn.close()
            posted += 1

    log.info(f"=== News posting done — {posted} sent ===")
    return posted

# ── Bets channel ──────────────────────────────────────────────────────────────

async def send_bets_card(msg):
    if not BETS_CHANNEL: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=BETS_CHANNEL, text=msg, parse_mode=ParseMode.MARKDOWN)
        log.info("  Bets card sent")
    except Exception as e:
        log.error(f"  Bets send failed: {e}")

# ── Internal channels ─────────────────────────────────────────────────────────

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

async def send_poll(question: str, options: list, channel_id: int = None, is_anonymous: bool = True) -> int | None:
    """
    Send a native Telegram poll to a channel.
    Returns message_id of the poll or None on failure.
    Polls are free, native, show live vote counts, drive strong engagement.
    """
    import os
    from telegram import Bot
    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
    chat = channel_id or NEWS_CHANNEL
    if not chat:
        return None
    try:
        msg = await bot.send_poll(
            chat_id=chat,
            question=question[:300],
            options=[o[:100] for o in options[:10]],
            is_anonymous=is_anonymous,
            allows_multiple_answers=False,
        )
        log.info(f"  Poll sent to {chat}: {question[:60]}")
        return msg.message_id
    except Exception as e:
        log.error(f"  Poll send failed: {e}")
        return None


def _generate_poll_for_story(story: dict) -> tuple[str, list] | None:
    """
    Generate a relevant poll question and options for a story.
    Returns (question, options) or None if no good poll can be made.
    """
    fmt   = story.get("format", "F7")
    title = story.get("title", "")
    hook  = story.get("winning_hook") or title
    t     = title.lower()

    # F7 Hot take polls — opinion split
    if fmt == "F7":
        # Manager sacked/appointed
        if any(k in t for k in ["sacked", "appointed", "new manager", "interim"]):
            return f"React: {hook[:200]}", ["Right decision ✅", "Wrong call ❌", "Too early to say 🤔"]
        # Transfer opinion
        if any(k in t for k in ["transfer", "signs", "joins", "bid"]):
            return f"Is this a good signing?", ["Great deal 🔥", "Overpaid 💸", "Wait and see ⏳"]
        # General hot take
        return f"Do you agree? {hook[:200]}", ["Agree 🟢", "Disagree 🔴", "Partially 🟡"]

    # F4 Post-match polls
    if fmt == "F4":
        if any(k in t for k in ["win", "beat", "victory"]):
            return "Rate the performance:", ["Brilliant 🔥", "Solid 👍", "Average 😐", "Poor 👎"]
        return "What did you think of the match?", ["Great game ⚽", "Boring 😴", "Controversial 😤"]

    # F3 Match preview polls — prediction
    if fmt == "F3":
        # Try to extract teams
        import re
        vs_match = re.search(r"(.+?)\s+v[s]?\s+(.+?)(?:\s*[-–:]|$)", title, re.IGNORECASE)
        if vs_match:
            home = vs_match.group(1).strip()[:30]
            away = vs_match.group(2).strip()[:30]
            return f"Your prediction?", [f"{home} win 🏠", "Draw 🤝", f"{away} win ✈️"]
        return "Who wins today?", ["Home win 🏠", "Draw 🤝", "Away win ✈️"]

    # F2 Transfer rumour polls
    if fmt == "F2":
        return f"Transfer talk: {hook[:150]}", ["Sign them! 🔥", "Not interested ❌", "Depends on price 💰"]

    # F9 Women's football polls
    if fmt == "F9":
        if "wsl" in t or "women's super league" in t:
            return "Who wins the WSL title?", ["Arsenal 🔴", "Chelsea 💙", "Man City 💙", "Other 🏆"]
        return f"Your thoughts on this?", ["Brilliant 🌟", "Good news ✅", "Disappointing 😞"]

    # F5 Title race
    if fmt == "F5":
        return "Who wins the title?", ["Arsenal 🔴", "Man City 💙", "Liverpool 🔴", "Other 🏆"]

    return None


async def post_to_news(story):
    if not INSIDE_CHANNEL: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=INSIDE_CHANNEL, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"  Inside report failed: {e}")

async def send_daily_summary(msg):
    if not REPORTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=REPORTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"  Reports send failed: {e}")

async def send_alert(msg):
    if not ALERTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=ALERTS_CHAT,
            text=f"⚠️ *ALERT*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"  Alert send failed: {e}")

async def send_quota_alert(remaining, limit):
    if not ALERTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        pct = int((remaining / limit) * 100) if limit else 0
        msg = "\n".join([
            "⚠️ *ElevenLabs Quota Warning*", "━" * 20,
            f"Remaining: `{remaining}` chars (`{pct}%` left)",
            f"Limit: `{limit}` chars/month",
            "Videos will be skipped until quota resets.",
            "_Upgrade at elevenlabs.io if needed_"
        ])
        await bot.send_message(chat_id=ALERTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"  Quota alert failed: {e}")

async def send_rss_alert(feed_name, error):
    if not ALERTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        msg = "\n".join(["⚠️ *RSS Feed Failure*", "",
            f"Feed: `{feed_name}`", f"Error: `{str(error)[:200]}`"])
        await bot.send_message(chat_id=ALERTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"  RSS alert failed: {e}")

async def send_midnight_summary(stats):
    if not REPORTS_CHAT: return
    try:
        bot = Bot(token=BOT_TOKEN)
        date_str = datetime.now(timezone.utc).strftime("%d %b %Y")
        msg = "\n".join([
            "📋 *90minWaffle Daily Summary*", "━" * 20,
            f"Stories ingested: `{stats.get('stories', 0)}`",
            f"Shippable: `{stats.get('shippable', 0)}`",
            f"Videos produced: `{stats.get('videos', 0)}`",
            f"Posts sent: `{stats.get('posted', 0)}`",
            "━" * 20, f"_90minWaffle — {date_str}_"
        ])
        await bot.send_message(chat_id=REPORTS_CHAT, text=msg, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log.error(f"  Midnight summary failed: {e}")

if __name__ == "__main__":
    asyncio.run(process_news_queue(limit=3))
