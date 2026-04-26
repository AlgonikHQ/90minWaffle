import os, requests, logging, sqlite3, uuid
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

API_FOOTBALL_KEY  = os.getenv("API_FOOTBALL_KEY")
API_FOOTBALL_URL  = os.getenv("API_FOOTBALL_URL", "https://v3.football.api-sports.io")
DISCORD_BETS      = os.getenv("DISCORD_WEBHOOK_BETS")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_BETS_CHAT = os.getenv("TELEGRAM_BETS_CHAT_ID")
DB_PATH           = "/root/90minwaffle/data/waffle.db"
LOG_PATH          = "/root/90minwaffle/logs/bet_alert.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

LEAGUE_IDS = [39, 40]  # 39=Premier League, 40=Championship
EDGE_THRESHOLD = 5.0  # minimum edge % to alert

def get_odds(league_id):
    url = f"{API_FOOTBALL_URL}/odds"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"league": league_id, "season": 2024, "bookmaker": 6}  # bookmaker 6 = Bet365
    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        if r.status_code == 200:
            data = r.json()
            results = data.get("response", [])
            log.info(f"Fetched {len(results)} matches for league {league_id}")
            return results
        else:
            log.error(f"API-Football error {r.status_code}: {r.text[:200]}")
            return []
    except Exception as e:
        log.error(f"Odds fetch failed: {e}")
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

def find_best_odds(match):
    outcomes = {}
    for bm in match.get("bookmakers", []):
        for market in bm.get("markets", []):
            if market["key"] != "h2h":
                continue
            for outcome in market["outcomes"]:
                name = outcome["name"]
                price = outcome["price"]
                if name not in outcomes or price > outcomes[name]["price"]:
                    outcomes[name] = {"price": price, "bookmaker": bm["title"]}
    return outcomes

def implied_prob(decimal_odds):
    return 1 / decimal_odds if decimal_odds > 0 else 0

def calc_margin(outcomes):
    total = sum(implied_prob(o["price"]) for o in outcomes.values())
    return round((total - 1) * 100, 2)

def find_edges(outcomes):
    best = outcomes
    if len(best) < 2:
        return []

    margin = calc_margin(best)
    edges = []

    for name, data in best.items():
        odds = data["price"]
        prob = implied_prob(odds)
        fair_prob = prob / sum(implied_prob(o["price"]) for o in best.values())
        fair_odds = round(1 / fair_prob, 2) if fair_prob > 0 else 0
        edge_pct = round((odds / fair_odds - 1) * 100, 2) if fair_odds > 0 else 0

        if edge_pct >= EDGE_THRESHOLD:
            edges.append({
                "selection": name,
                "odds": odds,
                "bookmaker": data["bookmaker"],
                "fair_odds": fair_odds,
                "edge_pct": edge_pct,
                "margin": margin
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
            alerted_at TEXT DEFAULT (datetime('now'))
        )""")
        c.execute("""INSERT OR IGNORE INTO bet_alerts
            (guid, home, away, commence_time, selection, odds, bookmaker, fair_odds, edge_pct, margin)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (
            guid,
            match.get("home_team"),
            match.get("away_team"),
            match.get("commence_time"),
            edge["selection"],
            edge["odds"],
            edge["bookmaker"],
            edge["fair_odds"],
            edge["edge_pct"],
            edge["margin"]
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Save alert failed: {e}")

def post_discord(match, edge):
    if not DISCORD_BETS:
        log.error("No DISCORD_WEBHOOK_BETS configured")
        return False

    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    kick_off = match.get("commence_time", "")[:16].replace("T", " ")

    embed = {
        "title": f"VALUE BET ALERT",
        "description": f"**{home} vs {away}**\nKick-off: {kick_off} UTC",
        "color": 0x00FF87,
        "fields": [
            {"name": "Selection", "value": edge["selection"], "inline": True},
            {"name": "Odds", "value": str(edge["odds"]), "inline": True},
            {"name": "Bookmaker", "value": edge["bookmaker"], "inline": True},
            {"name": "Fair Odds", "value": str(edge["fair_odds"]), "inline": True},
            {"name": "Edge", "value": f"+{edge['edge_pct']}%", "inline": True},
            {"name": "Market Margin", "value": f"{edge['margin']}%", "inline": True},
        ],
        "footer": {"text": "90minWaffle Bet Alerts | Gamble responsibly"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        r = requests.post(DISCORD_BETS, json={"embeds": [embed]}, timeout=15)
        if r.status_code in [200, 204]:
            log.info(f"Discord bet alert sent: {home} vs {away} — {edge['selection']} @ {edge['odds']}")
            return True
        else:
            log.error(f"Discord error {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        log.error(f"Discord post failed: {e}")
        return False

def post_telegram(match, edge):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_BETS_CHAT:
        log.warning("Telegram bets not configured — skipping")
        return

    home = match.get("home_team", "?")
    away = match.get("away_team", "?")
    kick_off = match.get("commence_time", "")[:16].replace("T", " ")

    msg = "VALUE BET ALERT\n\n" + home + " vs " + away + "\nKick-off: " + kick_off + " UTC\n\nSelection: *" + edge["selection"] + "*\nOdds: *" + str(edge["odds"]) + "* (" + edge["bookmaker"] + ")\nFair Odds: " + str(edge["fair_odds"]) + "\nEdge: +" + str(edge["edge_pct"]) + "%\n\n_Gamble responsibly_"
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": TELEGRAM_BETS_CHAT,
            "text": msg,
            "parse_mode": "Markdown"
        }, timeout=15)
        if r.status_code == 200:
            log.info(f"Telegram bet alert sent")
        else:
            log.error(f"Telegram error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log.error(f"Telegram post failed: {e}")

def run_bet_alerts():
    log.info("=== Bet Alert Scanner starting ===")
    total_alerts = 0

    for league_id in LEAGUE_IDS:
        items = get_odds(league_id)
        for item in items:
            match = parse_match(item)
            outcomes = parse_odds(item)
            edges = find_edges(outcomes)
            for edge in edges:
                guid = match["id"] + "_" + edge["selection"]
                if already_alerted(guid):
                    continue
                log.info(f"Edge found: {match['home_team']} vs {match['away_team']} — {edge['selection']} @ {edge['odds']} (+{edge['edge_pct']}%)")
                if post_discord(match, edge):
                    save_alert(guid, match, edge)
                    post_telegram(match, edge)
                    total_alerts += 1

    log.info(f"=== Bet Alert Scanner done — {total_alerts} alerts sent ===")
    return total_alerts

if __name__ == "__main__":
    run_bet_alerts()
