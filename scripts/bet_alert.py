import os, requests, logging, sqlite3, uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

API_FOOTBALL_KEY  = os.getenv("API_FOOTBALL_KEY")
API_FOOTBALL_URL  = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
DISCORD_BETS      = os.getenv("DISCORD_WEBHOOK_BETS")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BETS_CHANNEL = os.getenv("TELEGRAM_BETS_CHANNEL")
DB_PATH           = "/root/90minwaffle/data/waffle.db"
LOG_PATH          = "/root/90minwaffle/logs/bet_alert.log"

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

LEAGUE_IDS = {
    39:  "Premier League",
    40:  "Championship",
    78:  "Bundesliga",
    135: "Serie A",
    61:  "Ligue 1",
    140: "La Liga",
    88:  "Eredivisie",
    94:  "Primeira Liga",
}

EDGE_THRESHOLD = 5.0

def _in_fixture_window():
    now = datetime.now(timezone.utc)
    h, wd = now.hour, now.weekday()
    if wd in (5,6) and 10 <= h <= 18: return True
    if wd in (1,2,3) and 17 <= h <= 23: return True
    if wd == 4 and 18 <= h <= 22: return True
    if wd == 0 and 18 <= h <= 22: return True
    return False

def get_odds(league_id):
    url = API_FOOTBALL_URL + "/odds"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": 2025, "bookmaker": 6}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            results = r.json().get("response", [])
            log.info("Fetched " + str(len(results)) + " matches for league " + str(league_id))
            return results
        log.error("API-Football error " + str(r.status_code))
        return []
    except Exception as e:
        log.error("Odds fetch failed: " + str(e))
        return []

def parse_match(item):
    fixture = item.get("fixture", {})
    teams = item.get("teams", {})
    return {
        "id": str(fixture.get("id", "")),
        "home_team": teams.get("home", {}).get("name", "?"),
        "away_team": teams.get("away", {}).get("name", "?"),
        "commence_time": fixture.get("date", "")
    }

def parse_odds(item):
    outcomes = {}
    for bm in item.get("bookmakers", []):
        for bet in bm.get("bets", []):
            if bet.get("name") != "Match Winner":
                continue
            for val in bet.get("values", []):
                name = val["value"]
                try:
                    price = float(val["odd"])
                except:
                    continue
                if name not in outcomes or price > outcomes[name]["price"]:
                    outcomes[name] = {"price": price, "bookmaker": bm["name"]}
    return outcomes

def implied_prob(decimal_odds):
    return 1 / decimal_odds if decimal_odds > 0 else 0

def calc_margin(outcomes):
    total = sum(implied_prob(o["price"]) for o in outcomes.values())
    return round((total - 1) * 100, 2)

def find_edges(outcomes):
    if len(outcomes) < 2:
        return []
    margin = calc_margin(outcomes)
    edges = []
    for name, data in outcomes.items():
        odds = data["price"]
        prob = implied_prob(odds)
        fair_prob = prob / sum(implied_prob(o["price"]) for o in outcomes.values())
        fair_odds = round(1 / fair_prob, 2) if fair_prob > 0 else 0
        edge_pct = round((odds / fair_odds - 1) * 100, 2) if fair_odds > 0 else 0
        if edge_pct >= EDGE_THRESHOLD:
            edges.append({
                "selection": name, "odds": odds, "bookmaker": data["bookmaker"],
                "fair_odds": fair_odds, "edge_pct": edge_pct, "margin": margin
            })
    return edges

def already_alerted(guid):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM bet_alerts WHERE guid=?", (guid,))
        row = c.fetchone()
        conn.close()
        return row is not None
    except:
        return False

def save_alert(guid, match, edge):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS bet_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT UNIQUE NOT NULL,
            home TEXT, away TEXT, commence_time TEXT,
            selection TEXT, odds REAL, bookmaker TEXT,
            fair_odds REAL, edge_pct REAL, margin REAL,
            alerted_at TEXT DEFAULT (datetime('now')))""")
        c.execute("""INSERT OR IGNORE INTO bet_alerts
            (guid, home, away, commence_time, selection, odds, bookmaker, fair_odds, edge_pct, margin)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (
            guid, match.get("home_team"), match.get("away_team"),
            match.get("commence_time"), edge["selection"], edge["odds"],
            edge["bookmaker"], edge["fair_odds"], edge["edge_pct"], edge["margin"]))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error("Save alert failed: " + str(e))

def _get_team_image(home, away):
    try:
        import sys
        sys.path.insert(0, "/root/90minwaffle/scripts")
        from sportsdb_registry import find_team_in_text, best_team_image
        team = find_team_in_text(home + " " + away)
        if team:
            return best_team_image(team)
    except Exception:
        pass
    return None

def post_discord(match, edge):
    if not DISCORD_BETS:
        log.error("No DISCORD_WEBHOOK_BETS configured")
        return False
    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    league = match.get("league", "Football")
    kick_off = match.get("commence_time", "")[:16].replace("T", " ")
    stars = "+" * min(5, max(1, int(edge["edge_pct"] / 2)))
    desc = (
        "**" + edge["selection"] + "** @ `" + str(edge["odds"]) + "` (" + edge["bookmaker"] + ")\n"
        + stars + " Edge: **+" + str(edge["edge_pct"]) + "%** above fair value\n"
        + "Fair odds: `" + str(edge["fair_odds"]) + "` | Margin: `" + str(edge["margin"]) + "%`"
    )
    embed = {
        "author": {"name": "VALUE EDGE ALERT - " + league},
        "title": home + " vs " + away,
        "description": desc,
        "color": 0x00C853,
        "fields": [
            {"name": "Kick-off", "value": kick_off + " UTC", "inline": True},
            {"name": "League", "value": league, "inline": True},
            {"name": "Edge", "value": "+" + str(edge["edge_pct"]) + "%", "inline": True},
        ],
        "footer": {"text": "90minWaffle x StatiqFC | Value edges only | Gamble responsibly 18+"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    img = _get_team_image(home, away)
    if img:
        embed["image"] = {"url": img}
    try:
        r = requests.post(DISCORD_BETS, json={"embeds": [embed]}, timeout=15)
        if r.status_code in [200, 204]:
            log.info("Discord bet alert: " + home + " vs " + away + " - " + edge["selection"])
            return True
        log.error("Discord error " + str(r.status_code))
        return False
    except Exception as e:
        log.error("Discord post failed: " + str(e))
        return False

def post_telegram(match, edge):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_BETS_CHANNEL:
        log.warning("Telegram bets not configured - skipping")
        return
    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    league = match.get("league", "Football")
    kick_off = match.get("commence_time", "")[:16].replace("T", " ")
    stars = "+" * min(5, max(1, int(edge["edge_pct"] / 2)))
    msg = (
        "*VALUE EDGE - " + league + "*\n"
        "--------------------\n"
        "*" + home + " vs " + away + "*\n"
        "Kick-off: `" + kick_off + " UTC`\n\n"
        "Selection: *" + edge["selection"] + "*\n"
        "Odds: *" + str(edge["odds"]) + "* (" + edge["bookmaker"] + ")\n"
        "Fair Odds: `" + str(edge["fair_odds"]) + "`\n"
        "Edge: *+" + str(edge["edge_pct"]) + "%* " + stars + "\n"
        "Margin: `" + str(edge["margin"]) + "%`\n"
        "--------------------\n"
        "_Gamble responsibly 18+ | StatiqFC x 90minWaffle_"
    )
    img_url = _get_team_image(home, away)
    try:
        if img_url:
            url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendPhoto"
            r = requests.post(url, json={"chat_id": TELEGRAM_BETS_CHANNEL, "photo": img_url, "caption": msg, "parse_mode": "Markdown"}, timeout=15)
        else:
            url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
            r = requests.post(url, json={"chat_id": TELEGRAM_BETS_CHANNEL, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        if r.status_code == 200:
            log.info("Telegram bet alert: " + home + " vs " + away)
        else:
            log.error("Telegram error " + str(r.status_code))
    except Exception as e:
        log.error("Telegram post failed: " + str(e))

def run_bet_alerts():
    log.info("=== Bet Alert Scanner starting ===")
    if not _in_fixture_window():
        log.info("  Outside fixture window - skipping")
        return 0
    total_alerts = 0
    for league_id, league_name in LEAGUE_IDS.items():
        items = get_odds(league_id)
        for item in items:
            match = parse_match(item)
            match["league"] = league_name
            outcomes = parse_odds(item)
            edges = find_edges(outcomes)
            for edge in edges:
                guid = match["id"] + "_" + edge["selection"]
                if already_alerted(guid):
                    continue
                log.info("Edge: " + match["home_team"] + " vs " + match["away_team"] + " - " + edge["selection"] + " @ " + str(edge["odds"]))
                if post_discord(match, edge):
                    save_alert(guid, match, edge)
                    post_telegram(match, edge)
                    total_alerts += 1
    log.info("=== Bet Alert Scanner done - " + str(total_alerts) + " alerts sent ===")
    return total_alerts

if __name__ == "__main__":
    run_bet_alerts()
