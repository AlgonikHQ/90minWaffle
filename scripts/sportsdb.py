#!/usr/bin/env python3
import os, requests, sqlite3, logging, random
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

API_KEY = os.getenv("SPORTSDB_API_KEY", "440176")
BASE = "https://www.thesportsdb.com/api/v1/json/" + API_KEY
DB_PATH = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/sportsdb.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

# Premier League team name normalisation
TEAM_ALIASES = {
    "man utd": "Manchester United", "man united": "Manchester United",
    "man city": "Manchester City", "spurs": "Tottenham Hotspur",
    "tottenham": "Tottenham Hotspur", "wolves": "Wolverhampton Wanderers",
    "brighton": "Brighton", "newcastle": "Newcastle United",
    "west ham": "West Ham United", "nottm forest": "Nottingham Forest",
    "forest": "Nottingham Forest", "leicester": "Leicester City",
    "leeds": "Leeds United", "ipswich": "Ipswich Town",
    "brentford": "Brentford", "fulham": "Fulham",
    "southampton": "Southampton", "everton": "Everton",
    "villa": "Aston Villa", "aston villa": "Aston Villa",
    "chelsea": "Chelsea", "arsenal": "Arsenal",
    "liverpool": "Liverpool", "bournemouth": "Bournemouth",
    "crystal palace": "Crystal Palace", "luton": "Luton Town",
    "sheffield utd": "Sheffield United", "sheffield united": "Sheffield United",
    "burnley": "Burnley", "watford": "Watford",
}

LEAGUE_IDS = {
    "premier league": "4328", "epl": "4328",
    "championship": "4329", "efl": "4329",
    "champions league": "4480", "ucl": "4480",
    "la liga": "4335", "bundesliga": "4331",
    "serie a": "4332", "ligue 1": "4334",
}

def _ensure_cache_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS sportsdb_cache (
        key TEXT PRIMARY KEY,
        image_url TEXT,
        cached_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.commit(); conn.close()

def _cache_get(key):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("SELECT image_url FROM sportsdb_cache WHERE key=?", (key,))
        row = c.fetchone(); conn.close()
        return row[0] if row else None
    except: return None

def _cache_set(key, url):
    try:
        conn = sqlite3.connect(DB_PATH); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO sportsdb_cache (key, image_url) VALUES (?,?)", (key, url or ""))
        conn.commit(); conn.close()
    except: pass

def _get(endpoint):
    try:
        r = requests.get(BASE + endpoint, timeout=10)
        if r.status_code == 200: return r.json()
        return None
    except Exception as e:
        log.warning("SportsDB request failed: " + str(e)); return None

def get_team_image(team_name, image_type="banner"):
    _ensure_cache_table()
    key = "team_" + image_type + "_" + team_name.lower().strip()
    cached = _cache_get(key)
    if cached is not None: return cached or None

    # Normalise name
    normalised = TEAM_ALIASES.get(team_name.lower().strip(), team_name)
    data = _get("/searchteams.php?t=" + requests.utils.quote(normalised))
    if not data or not data.get("teams"):
        _cache_set(key, ""); return None

    t = data["teams"][0]
    if image_type == "banner": url = t.get("strBanner") or t.get("strFanart1") or t.get("strBadge")
    elif image_type == "badge": url = t.get("strBadge")
    elif image_type == "logo": url = t.get("strLogo") or t.get("strBadge")
    elif image_type == "fanart": url = t.get("strFanart" + str(random.randint(1,4))) or t.get("strFanart1") or t.get("strBanner")
    else: url = t.get("strBanner") or t.get("strFanart1")

    _cache_set(key, url or "")
    log.info("SportsDB team image: " + team_name + " -> " + str(url)[:60])
    return url

def get_player_image(player_name, image_type="thumb"):
    _ensure_cache_table()
    key = "player_" + image_type + "_" + player_name.lower().strip()
    cached = _cache_get(key)
    if cached is not None: return cached or None

    data = _get("/searchplayers.php?p=" + requests.utils.quote(player_name))
    if not data or not data.get("player"):
        _cache_set(key, ""); return None

    p = data["player"][0]
    if image_type == "cutout": url = p.get("strCutout") or p.get("strThumb")
    else: url = p.get("strThumb") or p.get("strCutout")

    _cache_set(key, url or "")
    log.info("SportsDB player image: " + player_name + " -> " + str(url)[:60])
    return url

def get_league_image(league_name, image_type="banner"):
    _ensure_cache_table()
    key = "league_" + image_type + "_" + league_name.lower().strip()
    cached = _cache_get(key)
    if cached is not None: return cached or None

    league_id = LEAGUE_IDS.get(league_name.lower(), "4328")
    data = _get("/lookupleague.php?id=" + league_id)
    if not data or not data.get("leagues"):
        _cache_set(key, ""); return None

    l = data["leagues"][0]
    if image_type == "badge": url = l.get("strBadge") or l.get("strLogo")
    elif image_type == "trophy": url = l.get("strTrophy") or l.get("strBadge")
    elif image_type == "fanart": url = l.get("strFanart" + str(random.randint(1,4))) or l.get("strFanart1")
    else: url = l.get("strBanner") or l.get("strFanart1")

    _cache_set(key, url or "")
    log.info("SportsDB league image: " + league_name + " -> " + str(url)[:60])
    return url

def extract_teams_from_title(title):
    title_lower = title.lower()
    found = []
    for alias, canonical in TEAM_ALIASES.items():
        if alias in title_lower and canonical not in found:
            found.append(canonical)
    # Also check canonical names directly
    canonical_names = list(set(TEAM_ALIASES.values()))
    for name in canonical_names:
        if name.lower() in title_lower and name not in found:
            found.append(name)
    return found[:2]

def extract_players_from_title(title, star_players=None):
    if not star_players: return []
    found = []
    title_lower = title.lower()
    for player in star_players:
        last_name = player.split()[-1].lower()
        if last_name in title_lower and player not in found:
            found.append(player)
    return found[:1]

def get_best_image_for_story(title, source="", star_players=None):
    """Returns best image URL for a story based on title analysis."""
    # Try player first (most specific)
    players = extract_players_from_title(title, star_players or [])
    if players:
        url = get_player_image(players[0], "thumb")
        if url: return url, "player"

    # Try team
    teams = extract_teams_from_title(title)
    if teams:
        url = get_team_image(teams[0], "banner")
        if url: return url, "team"

    # Fall back to league image
    if "champions league" in title.lower() or "ucl" in title.lower():
        url = get_league_image("champions league", "fanart")
    elif "championship" in title.lower():
        url = get_league_image("championship", "banner")
    else:
        url = get_league_image("premier league", "fanart")
    return url, "league"

if __name__ == "__main__":
    print("Testing SportsDB...")
    print(get_team_image("Arsenal", "banner"))
    print(get_team_image("Chelsea", "fanart"))
    print(get_player_image("Erling Haaland", "thumb"))
    print(get_league_image("premier league", "fanart"))
    t, kind = get_best_image_for_story("Kane needs Ballon dOr moment with Bayern")
    print("Story image:", kind, t)
