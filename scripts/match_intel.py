import os, requests, logging, sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

ODDS_API_KEY  = os.getenv("ODDS_API_KEY")
DISCORD_BETS  = os.getenv("DISCORD_WEBHOOK_BETS")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BETS  = int(os.getenv("TELEGRAM_BETS_CHANNEL", 0))
DB_PATH       = "/root/90minwaffle/data/waffle.db"
LOG_PATH      = "/root/90minwaffle/logs/match_intel.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# Rotate through leagues to conserve Odds API quota (500/month free tier)
# PL always + one European league rotating by day of month
_ALL_SPORTS = [
    ("soccer_epl",                    "Premier League"),
    ("soccer_efl_champ",              "Championship"),
    ("soccer_germany_bundesliga",     "Bundesliga"),
    ("soccer_italy_serie_a",          "Serie A"),
    ("soccer_france_ligue_one",       "Ligue 1"),
    ("soccer_spain_la_liga",          "La Liga"),
    ("soccer_netherlands_eredivisie", "Eredivisie"),
    ("soccer_portugal_primeira_liga", "Primeira Liga"),
]

def _get_todays_sports():
    """PL always + 1 rotating league = 2 requests/day = ~60/month."""
    from datetime import datetime
    day = datetime.now().day
    rotating = _ALL_SPORTS[1:]  # exclude PL
    pick = rotating[day % len(rotating)]
    return [_ALL_SPORTS[0], pick]

SPORTS = _get_todays_sports()

def already_posted_today(key):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS intel_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE,
            posted_at TEXT DEFAULT (datetime('now'))
        )""")
        conn.commit()
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT id FROM intel_log WHERE key=?", (f"{key}_{today}",))
        row = c.fetchone()
        conn.close()
        return row is not None
    except:
        return False

def mark_posted(key):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        c.execute("INSERT OR IGNORE INTO intel_log (key) VALUES (?)", (f"{key}_{today}",))
        conn.commit()
        conn.close()
    except:
        pass

def get_odds(sport_key):
    try:
        import sys
        sys.path.insert(0, "/root/90minwaffle/scripts")
        import odds_quota as oq
        if not oq.can_spend(1):
            s = oq.status()
            log.warning("Odds API quota limit reached - remaining: " + str(s["remaining"]) + " budget: " + str(s["daily_budget"]))
            return []
        r = requests.get(
            "https://api.the-odds-api.com/v4/sports/" + sport_key + "/odds/",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "uk",
                "markets": "h2h",
                "oddsFormat": "decimal",
            }, timeout=15)
        # Always sync actual remaining from headers
        if r.headers.get("x-requests-remaining"):
            oq.sync_from_headers(r.headers.get("x-requests-remaining"))
        else:
            oq.spend(1)
        if r.status_code == 200:
            remaining = r.headers.get("x-requests-remaining", "?")
            log.info("Odds API " + sport_key + ": " + str(len(r.json())) + " matches, " + str(remaining) + " requests remaining")
            return r.json()
        elif r.status_code == 401:
            log.warning("Odds API quota exhausted - skipping until reset")
            return []
        else:
            log.error("Odds API " + str(r.status_code) + ": " + r.text[:150])
            return []
    except Exception as e:
        log.error("Odds fetch failed: " + str(e))
        return []

def build_odds_embed(matches, league_name):
    lines = []
    for m in matches[:10]:
        home = m.get("home_team", "?")
        away = m.get("away_team", "?")
        kick_off = m.get("commence_time", "")[:16].replace("T", " ")
        best = {}
        for bm in m.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                for o in market["outcomes"]:
                    name = o["name"]
                    price = o["price"]
                    if name not in best or price > best[name]:
                        best[name] = price
        if best:
            h = best.get(home, "-")
            d = best.get("Draw", "-")
            a = best.get(away, "-")
            lines.append(f"**{home}** vs **{away}**" + chr(10) + f"> {kick_off} UTC | H: `{h}` D: `{d}` A: `{a}`")

    if not lines:
        return None

    return {
        "title": f"Best Available Odds — {league_name}",
        "description": (chr(10) + chr(10)).join(lines),
        "color": 0x00FF87,
        "footer": {"text": "90minWaffle | Best odds across UK bookmakers | Gamble responsibly 18+"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

def _get_match_image(home, away):
    """Get fanart/stadium image for the match."""
    try:
        import sys
        sys.path.insert(0, "/root/90minwaffle/scripts")
        from sportsdb_registry import find_team_in_text, best_team_image
        team = find_team_in_text(f"{home} vs {away}")
        if team:
            return best_team_image(team)
    except Exception:
        pass
    return None

def post_discord(embed, home="", away=""):
    if not DISCORD_BETS:
        log.error("No DISCORD_WEBHOOK_BETS configured")
        return False
    # Add stadium/fanart image
    img = _get_match_image(home, away)
    if img:
        embed["image"] = {"url": img}
    try:
        r = requests.post(DISCORD_BETS, json={"embeds": [embed]}, timeout=15)
        # Also fire to Telegram bets channel
        try:
            import asyncio
            from telegram import Bot
            from telegram.constants import ParseMode
            tg_bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
            bets_chat = int(os.getenv("TELEGRAM_BETS_CHANNEL", 0))
            if bets_chat:
                tg_msg = f"📊 *Match Intel — {embed.get('title','Odds Update')}*\n\n{embed.get('description','')}"
                asyncio.get_event_loop().run_until_complete(
                    tg_bot.send_message(chat_id=bets_chat, text=tg_msg[:4096], parse_mode=ParseMode.MARKDOWN)
                )
                log.info("  Bets card sent to Telegram")
        except Exception as te:
            log.error(f"  Telegram bets failed: {te}")
        if r.status_code in [200, 204]:
            log.info(f"Posted: {embed.get('title','')[:60]}")
            return True
        else:
            log.error(f"Discord {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        log.error(f"Discord post failed: {e}")
        return False

def run_match_intel(force=False):
    log.info("=== Match Intel starting ===")
    hour = datetime.now().hour
    if not force and hour != 9:
        log.info(f"Not 9am (hour={hour}) — skipping. Use --force to override.")
        return

    for sport_key, league_name in SPORTS:
        db_key = f"odds_{sport_key}"
        if not force and already_posted_today(db_key):
            log.info(f"Odds already posted today for {league_name} — skipping")
            continue
        matches = get_odds(sport_key)
        if not matches:
            log.warning(f"No odds data for {league_name}")
            continue
        embed = build_odds_embed(matches, league_name)
        # Get first match home/away for image lookup
        first_home = matches[0].get("home_team","") if matches else ""
        first_away = matches[0].get("away_team","") if matches else ""
        if embed and post_discord(embed, first_home, first_away):
            mark_posted(db_key)

    log.info("=== Match Intel done ===")

if __name__ == "__main__":
    import sys
    force = "--force" in sys.argv
    run_match_intel(force=force)
