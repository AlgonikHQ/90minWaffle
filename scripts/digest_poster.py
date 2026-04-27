#!/usr/bin/env python3
import os, json, sqlite3, requests, logging, asyncio
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

load_dotenv("/root/90minwaffle/.env")

CACHE_DIR = Path("/root/90minwaffle/data/cache")
DB_PATH = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/digest_poster.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))
DISCORD_PL = os.getenv("DISCORD_WEBHOOK_PREMIER_LEAGUE")
DISCORD_CHAMP = os.getenv("DISCORD_WEBHOOK_CHAMPIONSHIP")
DISCORD_GENERAL = os.getenv("DISCORD_WEBHOOK_GENERAL")

def get_db(): return sqlite3.connect(DB_PATH)

def already_posted_today(key):
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS digest_log (key TEXT PRIMARY KEY, posted_at TEXT)")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        c.execute("SELECT key FROM digest_log WHERE key=?", (key + "_" + today,))
        row = c.fetchone(); conn.close()
        return row is not None
    except: return False

def mark_posted(key):
    try:
        conn = get_db(); c = conn.cursor()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        c.execute("INSERT OR IGNORE INTO digest_log (key, posted_at) VALUES (?, datetime(\'now\'))", (key + "_" + today,))
        conn.commit(); conn.close()
    except: pass

def load_cache(name):
    p = CACHE_DIR / (name + ".json")
    if not p.exists(): return None
    try: return json.loads(p.read_text())
    except: return None

def get_table(comp):
    d = load_cache("standings_" + comp)
    if not d or "standings" not in d: return []
    return d["standings"][0].get("table", [])

def get_scorers(comp, limit=5):
    d = load_cache("scorers_" + comp)
    if not d or "scorers" not in d: return []
    return d["scorers"][:limit]

def form_emoji(form_str):
    if not form_str: return ""
    mapping = {"W": "\u2705", "D": "\u26aa", "L": "\u274c"}
    return " ".join(mapping.get(c, "\u26aa") for c in form_str[-5:])

def build_pl_discord():
    table = get_table("PL")
    scorers = get_scorers("PL")
    if not table: return None
    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    rows = []
    for r in table[:6]:
        pos = r["position"]
        name = r["team"]["name"].replace(" FC", "").replace(" AFC", "")
        pts = r["points"]
        gd = r["goalDifference"]
        played = r["playedGames"]
        form = form_emoji(r.get("form", ""))
        rows.append(f"`{pos:2}` **{name}** — `{pts}pts` GD:{gd:+d} P:{played}  {form}")
    table_str = "\n".join(rows)
    scorer_rows = []
    for i, s in enumerate(scorers, 1):
        pname = s["player"]["name"]
        tname = s["team"]["shortName"] if "shortName" in s["team"] else s["team"]["name"].replace(" FC","")
        goals = s["goals"]
        scorer_rows.append(f"`{i}.` {pname} ({tname}) — `{goals} goals`")
    scorer_str = "\n".join(scorer_rows)
    embed = {
        "author": {"name": "\U0001f3c6  PREMIER LEAGUE STANDINGS"},
        "title": "Top 6 — " + now,
        "description": table_str,
        "color": 0x3D0059,
        "fields": [
            {"name": "\U0001f45f Top Scorers", "value": scorer_str, "inline": False}
        ],
        "footer": {"text": "90minWaffle • Football. Hot takes. No filter. | twitter.com/90minwaffle"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return embed

def build_champ_discord():
    table = get_table("ELC")
    if not table: return None
    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    rows = []
    for r in table[:6]:
        pos = r["position"]
        name = r["team"]["name"].replace(" FC", "").replace(" AFC", "")
        pts = r["points"]
        gd = r["goalDifference"]
        played = r["playedGames"]
        form = form_emoji(r.get("form", ""))
        rows.append(f"`{pos:2}` **{name}** — `{pts}pts` GD:{gd:+d} P:{played}  {form}")
    table_str = "\n".join(rows)
    embed = {
        "author": {"name": "\U0001f3df  CHAMPIONSHIP STANDINGS"},
        "title": "Top 6 + Form — " + now,
        "description": table_str,
        "color": 0xF77F00,
        "footer": {"text": "90minWaffle • Football. Hot takes. No filter. | twitter.com/90minwaffle"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return embed

def build_telegram_table(comp, label, emoji):
    table = get_table(comp)
    if not table: return None
    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines = [emoji + " *" + label + " — Top 6*", "_" + now + "_", ""]
    for r in table[:6]:
        pos = r["position"]
        name = r["team"]["name"].replace(" FC","").replace(" AFC","")
        pts = r["points"]
        gd = r["goalDifference"]
        lines.append(str(pos) + ". *" + name + "* — " + str(pts) + "pts (GD " + ("{:+d}".format(gd)) + ")")
    if comp == "PL":
        scorers = get_scorers("PL")
        if scorers:
            lines += ["", "\U0001f45f *Top Scorers*"]
            for i, s in enumerate(scorers[:5], 1):
                pname = s["player"]["name"]
                goals = s["goals"]
                lines.append(str(i) + ". " + pname + " — " + str(goals) + " goals")
    lines += ["", "\u2501"*20, "\U0001f426 @90minWaffle on X | \U0001f4fa YouTube | \U0001f3b5 TikTok"]
    return "\n".join(lines)

def post_discord_embed(webhook, embed):
    if not webhook: return False
    try:
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=15)
        return r.status_code in (200, 204)
    except Exception as e:
        log.error("Discord post failed: " + str(e)); return False

async def post_telegram_digest(text, buttons=None):
    if not NEWS_CHANNEL or not BOT_TOKEN: return False
    try:
        bot = Bot(token=BOT_TOKEN)
        markup = None
        if buttons:
            keyboard = [buttons]
            markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(chat_id=NEWS_CHANNEL, text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return True
    except Exception as e:
        log.error("Telegram digest failed: " + str(e)); return False

async def run_digest():
    log.info("=== Digest Poster starting ===")
    sent = 0

    if not already_posted_today("pl_standings"):
        embed = build_pl_discord()
        if embed and post_discord_embed(DISCORD_PL, embed):
            log.info("  PL standings posted to Discord")
            mark_posted("pl_standings")
            sent += 1
        tg_text = build_telegram_table("PL", "Premier League", "\U0001f3c6")
        if tg_text:
            buttons = [
                InlineKeyboardButton("\U0001f426 @90minWaffle", url="https://twitter.com/90minwaffle"),
                InlineKeyboardButton("\U0001f4fa YouTube", url="https://youtube.com/@90minwaffle"),
                InlineKeyboardButton("\U0001f3b5 TikTok", url="https://tiktok.com/@90minwaffle")
            ]
            await post_telegram_digest(tg_text, buttons)

    if not already_posted_today("champ_standings"):
        embed = build_champ_discord()
        if embed and post_discord_embed(DISCORD_CHAMP, embed):
            log.info("  Championship standings posted to Discord")
            mark_posted("champ_standings")
            sent += 1
        tg_text = build_telegram_table("ELC", "Championship", "\U0001f3df")
        if tg_text:
            buttons = [
                InlineKeyboardButton("\U0001f426 @90minWaffle", url="https://twitter.com/90minwaffle"),
                InlineKeyboardButton("\U0001f4fa YouTube", url="https://youtube.com/@90minwaffle"),
                InlineKeyboardButton("\U0001f3b5 TikTok", url="https://tiktok.com/@90minwaffle")
            ]
            await post_telegram_digest(tg_text, buttons)

    log.info("=== Digest done — " + str(sent) + " posted ===")
    return sent

if __name__ == "__main__":
    asyncio.run(run_digest())
