"""sportsdb_registry — team & roster cache for TheSportsDB.

Responsibilities:
  - Pull every team from configured leagues into a local cache (teams.json).
  - On demand, pull a team's full roster into a roster cache (rosters.json).
  - Resolve any text query ("Spurs", "West Ham", "Atletico") to a canonical
    team_id via exact / alias / substring / token matching.
  - Return the best player image (render > cutout > thumb) verified against
    the team currently mentioned in the story.

Refresh discipline:
  - Team cache: refreshed weekly via refresh_teams.py (cron / systemd timer).
  - Roster cache: refreshed lazily — first request for a team triggers a
    fetch; subsequent requests within ROSTER_TTL_DAYS use the cache.

Used by sportsdb.py (90minWaffle) and intended to be reused by StatiqFC.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Optional, Dict, List, Tuple

import requests
from dotenv import load_dotenv

from leagues_config import LEAGUES

load_dotenv("/root/90minwaffle/.env")
API_KEY = os.getenv("SPORTSDB_API_KEY")
BASE = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

# Cache locations
DATA_DIR = "/root/90minwaffle/data"
TEAMS_CACHE = os.path.join(DATA_DIR, "teams.json")
ROSTERS_CACHE = os.path.join(DATA_DIR, "rosters.json")

# Roster TTL — refresh a team's roster if older than this
ROSTER_TTL_DAYS = 7

# Polite request defaults — TheSportsDB free tier is 30 req/min
HTTP_TIMEOUT = 8

# ---------------------------------------------------------------------------
# Cache I/O
# ---------------------------------------------------------------------------

def _ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_json(path: str, data: dict) -> None:
    _ensure_data_dir()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Team cache — populated by refresh_teams()
# ---------------------------------------------------------------------------

def refresh_teams(verbose: bool = False) -> int:
    """Pull every team from every configured league into the local cache.

    Run weekly. Returns the number of teams cached.
    """
    teams: Dict[str, dict] = {}

    for league in LEAGUES:
        url = f"{BASE}/search_all_teams.php"
        try:
            r = requests.get(url, params={"id": league["id"]}, timeout=HTTP_TIMEOUT)
            d = r.json() or {}
        except Exception as e:
            if verbose:
                print(f"[refresh_teams] {league['name']}: ERROR {e}")
            continue

        league_teams = d.get("teams") or []
        if verbose:
            print(f"[refresh_teams] {league['name']}: {len(league_teams)} teams")

        for t in league_teams:
            tid = t.get("idTeam")
            if not tid:
                continue
            # Build alias list from canonical name + alternates + short forms
            canonical = t.get("strTeam", "")
            alternates = (t.get("strTeamAlternate") or "").split(",")
            aliases = [canonical] + [a.strip() for a in alternates if a.strip()]
            # search_all_teams.php uses strBadge / strLogo / strBanner /
            # strFanart1 — NOT the strTeamBadge etc. that searchteams.php uses.
            teams[tid] = {
                "id": tid,
                "canonical": canonical,
                "aliases": aliases,
                "league_id": league["id"],
                "league_name": league["name"],
                "tier": league["tier"],
                "badge": t.get("strBadge") or t.get("strTeamBadge"),
                "logo": t.get("strLogo") or t.get("strTeamLogo"),
                "banner": t.get("strBanner"),
                "fanart": t.get("strFanart1"),
                "equipment": t.get("strEquipment"),
                "stadium": t.get("strStadium"),
                "stadium_thumb": t.get("strStadiumThumb"),
                "country": t.get("strCountry"),
            }

        time.sleep(2)  # be polite, stay under rate limit

    cache = {
        "refreshed_at": int(time.time()),
        "teams": teams,
    }
    _save_json(TEAMS_CACHE, cache)
    return len(teams)


def _teams() -> Dict[str, dict]:
    cache = _load_json(TEAMS_CACHE)
    return cache.get("teams", {}) if isinstance(cache, dict) else {}


# ---------------------------------------------------------------------------
# Team resolution — fuzzy name -> team_id
# ---------------------------------------------------------------------------

_NORMALIZE_RE = re.compile(r"[^a-z0-9 ]+")


def _normalize(s: str) -> str:
    s = (s or "").lower().strip()
    s = _NORMALIZE_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def resolve_team(query: str) -> Optional[dict]:
    """Resolve a text query to a cached team record.

    Strategy: exact alias match first, then substring match, then token
    overlap. Returns None if nothing reasonable found.
    """
    q = _normalize(query)
    if not q:
        return None

    teams = _teams()
    if not teams:
        return None

    # 1. Exact alias match
    for t in teams.values():
        for a in t.get("aliases", []):
            if _normalize(a) == q:
                return t

    # 2. Substring — query is contained in an alias, or an alias is contained
    #    in the query. Prefer longer aliases (more specific match).
    candidates: List[Tuple[int, dict]] = []
    for t in teams.values():
        for a in t.get("aliases", []):
            an = _normalize(a)
            if not an:
                continue
            if q == an:
                return t  # belt + braces
            if an in q or q in an:
                # score = length of the matching alias
                candidates.append((len(an), t))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    # 3. Token overlap — for queries like "Manchester United beat Spurs"
    #    a query that contains every word of an alias counts as a match.
    q_tokens = set(q.split())
    for t in teams.values():
        for a in t.get("aliases", []):
            a_tokens = set(_normalize(a).split())
            if a_tokens and a_tokens.issubset(q_tokens):
                candidates.append((len(a_tokens), t))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    return None


def find_team_in_text(text: str) -> Optional[dict]:
    """Scan text for any cached team alias and return the best match.

    Ranking:
      1. Prefer the team mentioned EARLIEST in the text (subject of the
         story, not the opponent).
      2. Tiebreaker: longest alias wins (more specific match).

    Matching modes:
      a. Word-boundary match of an alias inside the text (e.g. alias
         'Bayern' found in 'Bayern thrash Dortmund').
      b. Multi-word phrase match: a 2+ word PREFIX of an alias appears
         in the text (e.g. 'West Ham' in text matches alias
         'West Ham United'). This handles short forms not present in
         the alias list.
    """
    n = _normalize(text)
    if not n:
        return None
    teams = _teams()
    if not teams:
        return None

    # candidates: (position_in_text, -alias_length, team_dict)
    # negative length so sort ascending gives earliest-then-longest
    candidates: List[Tuple[int, int, dict]] = []

    for t in teams.values():
        for a in t.get("aliases", []):
            an = _normalize(a)
            if len(an) < 3:
                continue

            # Mode a: alias appears as a whole phrase in the text
            m = re.search(rf"\b{re.escape(an)}\b", n)
            if m:
                candidates.append((m.start(), -len(an), t))
                continue

            # Mode b: a 2+ word prefix of the alias appears in the text.
            # This handles "West Ham" matching "West Ham United".
            tokens = an.split()
            if len(tokens) >= 3:
                # try the first 2 tokens as a phrase
                prefix = " ".join(tokens[:2])
                if len(prefix) >= 5:  # avoid junk like "fc al"
                    m = re.search(rf"\b{re.escape(prefix)}\b", n)
                    if m:
                        candidates.append((m.start(), -len(prefix), t))

    if not candidates:
        return None
    candidates.sort()  # earliest position first, then longest alias
    return candidates[0][2]


# ---------------------------------------------------------------------------
# Roster cache — lazy, per-team
# ---------------------------------------------------------------------------

def _rosters() -> dict:
    return _load_json(ROSTERS_CACHE)


def _save_rosters(rosters: dict) -> None:
    _save_json(ROSTERS_CACHE, rosters)


def _is_fresh(entry: dict) -> bool:
    age = time.time() - entry.get("fetched_at", 0)
    return age < ROSTER_TTL_DAYS * 86400


def get_roster(team_id: str, force_refresh: bool = False) -> List[dict]:
    """Return the cached roster for team_id, fetching if missing or stale."""
    if not team_id:
        return []
    rosters = _rosters()
    entry = rosters.get(team_id)
    if entry and _is_fresh(entry) and not force_refresh:
        return entry.get("players", [])

    # Fetch from API
    try:
        r = requests.get(
            f"{BASE}/lookup_all_players.php",
            params={"id": team_id},
            timeout=HTTP_TIMEOUT,
        )
        d = r.json() or {}
    except Exception:
        # Use stale cache if available rather than returning nothing
        return entry.get("players", []) if entry else []

    players = d.get("player") or []
    # Slim each player down to only the fields we need
    slim = []
    for p in players:
        slim.append({
            "id": p.get("idPlayer"),
            "name": p.get("strPlayer"),
            "team": p.get("strTeam"),
            "position": p.get("strPosition"),
            "thumb": p.get("strThumb"),
            "cutout": p.get("strCutout"),
            "render": p.get("strRender"),
        })

    rosters[team_id] = {
        "fetched_at": int(time.time()),
        "players": slim,
    }
    _save_rosters(rosters)
    return slim


# ---------------------------------------------------------------------------
# Image selection
# ---------------------------------------------------------------------------

def best_player_image(player: dict) -> Optional[str]:
    """Render > cutout > thumb. Returns None if all three are missing."""
    return player.get("render") or player.get("cutout") or player.get("thumb")


def best_team_image(team: dict) -> Optional[str]:
    """Fanart > banner > stadium > logo > badge (badge is absolute last resort).
    
    Fanart and stadium images are actual photos — vastly better than badge JPEGs.
    Badge is kept only as a final fallback when nothing else exists.
    """
    return (
        team.get("fanart")
        or team.get("banner")
        or team.get("stadium_thumb")
        or team.get("logo")
        or team.get("badge")
    )


def find_player_image(player_name: str, team_id: str) -> Optional[str]:
    """Find a player's best image by checking the team's cached roster.

    Strict — only returns an image if the player is actually in this team's
    current roster. No cross-team fallback (that's how we got the stale
    West Ham photo for Declan Rice).
    """
    if not player_name or not team_id:
        return None
    pn = _normalize(player_name)
    if not pn:
        return None

    roster = get_roster(team_id)
    if not roster:
        return None

    # Exact name match first
    for p in roster:
        if _normalize(p.get("name", "")) == pn:
            img = best_player_image(p)
            if img: return img
    # Substring match (handles "Salah" vs "Mohamed Salah")
    for p in roster:
        pname = _normalize(p.get("name", ""))
        if pn in pname or pname in pn:
            img = best_player_image(p)
            if img: return img
    # Last word match — "Haaland" matches "Erling Haaland"
    pn_last = pn.split()[-1] if pn.split() else pn
    if len(pn_last) > 4:
        for p in roster:
            pname_parts = _normalize(p.get("name", "")).split()
            if pname_parts and pname_parts[-1] == pn_last:
                img = best_player_image(p)
                if img: return img
    return None


# ---------------------------------------------------------------------------
# Public top-level API used by sportsdb.py
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[A-Z][a-zA-Z'\-]+")


def _team_word_set() -> set:
    """All single words that appear in any team alias — used to filter
    name-pair false positives like 'Newcastle Declan' or 'Manchester United'."""
    words = set()
    for t in _teams().values():
        for a in t.get("aliases", []):
            for w in _normalize(a).split():
                if len(w) > 2:
                    words.add(w)
    return words


# Known single-name players and managers — matched without needing a surname pair
KNOWN_SINGLES = [
    # PL players
    "haaland","salah","saka","rice","trent","isak","eze","palmer","rashford",
    "fernandes","maddison","son","havertz","odegaard","martinelli","wilson",
    "palhinha","sessegnon","watkins","ollie","gallagher","zaha","madueke",
    "nketiah","trossard","white","timber","calafiori","raya","flekken",
    "fabianski","areola","henderson","pope","pickford","flaherty",
    "mudryk","maatsen","sterling","cucurella","colwill","gusto","james",
    "reece","caicedo","jackson","nkunku","sancho","silva","thiago",
    # European stars
    "mbappe","vinicius","bellingham","yamal","dembele","lewandowski",
    "kane","wirtz","musiala","pedri","gavi","ter stegen","courtois",
    "alisson","ederson","oblak","sommer","neuer","szczesny",
    "rodri","modric","kroos","camavinga","tchouameni","valverde",
    "benzema","griezmann","giroud","benzema","diaby","cherki",
    # Managers
    "arteta","guardiola","slot","howe","maresca","iraola","glass",
    "nuno","moyes","wilder","edwards","freedman","lampard","gerrard",
    "ancelotti","flick","kompany","tuchel","nagelsmann","xabi",
    "mourinho","ten hag","amorim","klopp","pochettino","conte",
    "fabregas","de zerbi","emery","villa","unai","rosenior",
    # Scotland
    "rodgers","clement","mcginn","tierney","dykes","adams",
]

def extract_player_names(text: str, limit: int = 8) -> List[str]:
    """Pull plausible player/manager name candidates from free text.

    Strategy:
    1. Check against KNOWN_SINGLES first — single surname match
    2. Find capitalised First Last pairs, reject team-name tokens
    3. Combine, deduplicate, return up to limit
    """
    if not text:
        return []
    t_lower = text.lower()
    names: List[str] = []

    # Pass 1 — known singles (highest confidence)
    for name in KNOWN_SINGLES:
        if name in t_lower and name.title() not in names:
            names.append(name.title())
        if len(names) >= limit:
            return names

    # Pass 2 — First Last capitalised pairs
    words = _WORD_RE.findall(text)
    if len(words) >= 2:
        team_tokens = _team_word_set()
        for i in range(len(words) - 1):
            w1, w2 = words[i], words[i + 1]
            if len(w1) <= 2 or len(w2) <= 2:
                continue
            if _normalize(w1) in team_tokens or _normalize(w2) in team_tokens:
                continue
            full = f"{w1} {w2}"
            if full not in names:
                names.append(full)
            if len(names) >= limit:
                break

    return names[:limit]


def get_image_for_story(title: str, hook: str = "") -> Optional[str]:
    """Resolve the best image for a piece of content.

    Strict policy: image must match the story.
      1. If a team is detected in the text:
         a. Try every name candidate against THAT team's roster.
         b. If no player match, return the team's badge.
         c. If even the badge is missing, return None — never a wrong image.
      2. If no team is detected, fall back to a generic player search
         (the only place loose matching is allowed).
    """
    text = f"{title or ''} {hook or ''}".strip()
    if not text:
        return None

    team = find_team_in_text(text)

    if team:
        names = extract_player_names(text)
        # Try player image ONLY in the team mentioned in story
        for name in names:
            img = find_player_image(name, team["id"])
            if img:
                return img
        # No player found — return fanart/stadium not badge
        return best_team_image(team)

    # No team detected — try player search across all teams
    # but verify the player's current team matches the story context
    names = extract_player_names(text)
    for name in names:
        # Search all teams for this player
        for tid, team_data in _teams().items():
            img = find_player_image(name, tid)
            if img:
                # Verify team name appears in story text
                team_name = _normalize(team_data.get("canonical", ""))
                if any(a and _normalize(a) in _normalize(text)
                       for a in team_data.get("aliases", [])):
                    return img
        # No verified match — try legacy search as last resort
        img = _legacy_player_search(name)
        if img:
            return img

    # No team detected — last-ditch player search via TheSportsDB's own
    # search endpoint. Used for non-club content (e.g. "Cristiano Ronaldo").
    names = extract_player_names(text)
    for name in names:
        img = _legacy_player_search(name)
        if img:
            return img
    return None


def _legacy_player_search(name: str) -> Optional[str]:
    """Generic player search via /searchplayers.php. Only used when no team
    context is available. Render > cutout > thumb."""
    try:
        r = requests.get(
            f"{BASE}/searchplayers.php",
            params={"p": name},
            timeout=HTTP_TIMEOUT,
        )
        d = r.json() or {}
        players = d.get("player") or []
        if not players:
            return None
        p = players[0]
        return (
            p.get("strRender")
            or p.get("strCutout")
            or p.get("strThumb")
        )
    except Exception:
        return None
