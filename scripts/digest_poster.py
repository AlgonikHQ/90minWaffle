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

BOT_TOKEN     = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL  = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))
DISCORD_PL    = os.getenv("DISCORD_WEBHOOK_PREMIER_LEAGUE")
DISCORD_CHAMP = os.getenv("DISCORD_WEBHOOK_CHAMPIONSHIP")
DISCORD_GEN   = os.getenv("DISCORD_WEBHOOK_GENERAL")

LEAGUES = [
    {"comp": "PL",  "label": "Premier League",  "emoji": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "colour": 0x3D0059, "webhook": "PL",    "tg": True},
    {"comp": "ELC", "label": "Championship",     "emoji": "🏟",        "colour": 0xF77F00, "webhook": "CHAMP", "tg": True},
    {"comp": "BL1", "label": "Bundesliga",       "emoji": "🇩🇪",        "colour": 0xE8000D, "webhook": "GEN",   "tg": False},
    {"comp": "SA",  "label": "Serie A",          "emoji": "🇮🇹",        "colour": 0x009246, "webhook": "GEN",   "tg": False},
    {"comp": "FL1", "label": "Ligue 1",          "emoji": "🇫🇷",        "colour": 0x003189, "webhook": "GEN",   "tg": False},
    {"comp": "PD",  "label": "La Liga",          "emoji": "🇪🇸",        "colour": 0xC60B1E, "webhook": "GEN",   "tg": False},
]

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
        c.execute("INSERT OR IGNORE INTO digest_log (key, posted_at) VALUES (?, datetime('now'))", (key + "_" + today,))
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

def form_bar(form_str):
    if not form_str: return ""
    mapping = {"W": "✅", "D": "🟡", "L": "❌"}
    return " ".join(mapping.get(c, "⚪") for c in form_str[-5:])

def build_discord_embed(league):
    comp   = league["comp"]
    label  = league["label"]
    emoji  = league["emoji"]
    colour = league["colour"]
    table  = get_table(comp)
    if not table: return None

    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    rows = []
    for r in table[:6]:
        pos   = r["position"]
        name  = r["team"]["name"].replace(" FC","").replace(" AFC","")[:18]
        pts   = r["points"]
        gd    = r["goalDifference"]
        played = r["playedGames"]
        form  = form_bar(r.get("form",""))
        rows.append("`" + str(pos).rjust(2) + "` **" + name + "** — `" + str(pts) + "pts` GD:" + ("{:+d}".format(gd)) + " P:" + str(played) + "  " + form)

    fields = [{"name": "Top 6", "value": chr(10).join(rows), "inline": False}]

    # Add top scorers for PL and ELC
    if comp in ("PL","ELC"):
        scorers = get_scorers(comp)
        if scorers:
            sc_lines = []
            for i, s in enumerate(scorers, 1):
                pname = s["player"]["name"]
                goals = s["goals"]
                sc_lines.append("`" + str(i) + ".` " + pname + " — `" + str(goals) + " goals`")
            fields.append({"name": "⚽ Top Scorers", "value": chr(10).join(sc_lines), "inline": False})

    # Title race callout for PL
    if comp == "PL" and len(table) >= 2:
        leader = table[0]; second = table[1]
        gap = leader["points"] - second["points"]
        gl  = 38 - leader["playedGames"]
        callout = (
            "**" + leader["team"]["name"].replace(" FC","") + "** lead by **" + str(gap) + " pts** "
            "with " + str(gl) + " games left."
        )
        fields.append({"name": "🏆 Title Race", "value": callout, "inline": False})

    return {
        "author": {"name": emoji + "  " + label.upper() + " STANDINGS — " + now},
        "color": colour,
        "fields": fields,
        "footer": {"text": "90minWaffle • Football. Hot takes. No filter. | @90minWaffle"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def build_telegram_digest(league):
    comp  = league["comp"]
    label = league["label"]
    emoji = league["emoji"]
    table = get_table(comp)
    if not table: return None

    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    lines = [emoji + " *" + label + " Standings*", "_" + now + "_", ""]

    for r in table[:6]:
        pos  = r["position"]
        name = r["team"]["name"].replace(" FC","").replace(" AFC","")
        pts  = r["points"]
        gd   = r["goalDifference"]
        form = form_bar(r.get("form",""))
        lines.append(str(pos) + ". *" + name + "* — " + str(pts) + "pts (GD " + ("{:+d}".format(gd)) + ") " + form)

    if comp == "PL":
        scorers = get_scorers("PL")
        if scorers:
            lines += ["", "⚽ *Top Scorers*"]
            for i, s in enumerate(scorers[:5], 1):
                lines.append(str(i) + ". " + s["player"]["name"] + " — " + str(s["goals"]) + " goals")
        if len(table) >= 2:
            gap = table[0]["points"] - table[1]["points"]
            gl  = 38 - table[0]["playedGames"]
            lines += ["", "🏆 *" + table[0]["team"]["name"].replace(" FC","") + "* lead by *" + str(gap) + "pts* with " + str(gl) + " games left"]

    lines += ["", "━━━━━━━━━━━━━━━━━━━━", "📺 @90minWaffle | YouTube | TikTok"]
    return chr(10).join(lines)

def post_discord(webhook_url, embed):
    if not webhook_url: return False
    try:
        r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
        return r.status_code in (200, 204)
    except Exception as e:
        log.error("Discord digest failed: " + str(e)); return False

async def post_telegram(text):
    if not NEWS_CHANNEL or not BOT_TOKEN: return False
    try:
        bot = Bot(token=BOT_TOKEN)
        buttons = [
            InlineKeyboardButton("🐦 @90minWaffle", url="https://twitter.com/90minwaffle"),
            InlineKeyboardButton("📺 YouTube", url="https://youtube.com/@90minwaffle"),
        ]
        markup = InlineKeyboardMarkup([buttons])
        await bot.send_message(chat_id=NEWS_CHANNEL, text=text,
            parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
        return True
    except Exception as e:
        log.error("Telegram digest failed: " + str(e)); return False

async def run_digest():
    log.info("=== Digest Poster starting ===")
    sent = 0

    webhook_map = {
        "PL":    DISCORD_PL,
        "CHAMP": DISCORD_CHAMP,
        "GEN":   DISCORD_GEN,
    }

    for league in LEAGUES:
        key = "standings_" + league["comp"]
        if already_posted_today(key):
            log.info("  Already posted today: " + league["label"])
            continue

        embed = build_discord_embed(league)
        webhook = webhook_map.get(league["webhook"])
        if embed and post_discord(webhook, embed):
            log.info("  Posted: " + league["label"] + " to Discord")
            mark_posted(key)
            sent += 1

        if league["tg"]:
            tg_text = build_telegram_digest(league)
            if tg_text:
                await post_telegram(tg_text)

        await asyncio.sleep(2)

    log.info("=== Digest done — " + str(sent) + " posted ===")
    return sent

if __name__ == "__main__":
    asyncio.run(run_digest())
