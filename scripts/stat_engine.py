#!/usr/bin/env python3
"""90minWaffle Stat Engine - generates verified stat snippets from cache"""
import json, logging
from pathlib import Path
from datetime import datetime, timezone

CACHE_DIR = Path("/root/90minwaffle/data/cache")
LOG_PATH = "/root/90minwaffle/logs/stat_engine.log"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

def _load(name):
    p = CACHE_DIR / f"{name}.json"
    if not p.exists(): return None
    try: return json.loads(p.read_text())
    except Exception as e: log.error(f"Cache read fail {name}: {e}"); return None

def get_table(comp="PL"):
    d = _load(f"standings_{comp}")
    if not d or "standings" not in d: return []
    return d["standings"][0].get("table", []) if d["standings"] else []

def get_team_position(team_name, comp="PL"):
    table = get_table(comp)
    for row in table:
        tn = row["team"]["name"].lower()
        if team_name.lower() in tn or tn in team_name.lower():
            return row
    return None

def get_top_scorers(comp="PL", limit=5):
    d = _load(f"scorers_{comp}")
    if not d or "scorers" not in d: return []
    return d["scorers"][:limit]

def get_upcoming_matches(comp="PL", limit=10):
    d = _load(f"matches_{comp}")
    if not d or "matches" not in d: return []
    upcoming = []
    for m in d["matches"]:
        if m.get("status") in ("SCHEDULED", "TIMED"):
            upcoming.append(m)
    return upcoming[:limit]

def get_recent_results(comp="PL", limit=10):
    d = _load(f"matches_{comp}")
    if not d or "matches" not in d: return []
    finished = [m for m in d["matches"] if m.get("status") == "FINISHED"]
    finished.sort(key=lambda x: x.get("utcDate", ""), reverse=True)
    return finished[:limit]

def get_team_form(team_name, comp="PL", last=5):
    results = get_recent_results(comp, limit=50)
    form = []
    for m in results:
        h = m["homeTeam"]["name"].lower()
        a = m["awayTeam"]["name"].lower()
        tn = team_name.lower()
        if tn not in h and tn not in a and h not in tn and a not in tn: continue
        score = m.get("score", {}).get("fullTime", {})
        hs, as_ = score.get("home"), score.get("away")
        if hs is None or as_ is None: continue
        is_home = tn in h or h in tn
        if hs == as_: form.append("D")
        elif (is_home and hs > as_) or (not is_home and as_ > hs): form.append("W")
        else: form.append("L")
        if len(form) >= last: break
    return form

def get_title_race_snapshot():
    table = get_table("PL")
    if len(table) < 2: return None
    leader = table[0]; second = table[1]
    games_left_leader = 38 - leader["playedGames"]
    games_left_second = 38 - second["playedGames"]
    max_second = second["points"] + (games_left_second * 3)
    min_leader = leader["points"]
    return {
        "leader": leader["team"]["name"],
        "leader_pts": leader["points"],
        "leader_played": leader["playedGames"],
        "leader_gd": leader["goalDifference"],
        "second": second["team"]["name"],
        "second_pts": second["points"],
        "gap": leader["points"] - second["points"],
        "max_second": max_second,
        "min_leader": min_leader,
        "leader_safe": min_leader > max_second,
        "games_left_leader": games_left_leader,
        "games_left_second": games_left_second
    }

def get_relegation_zone():
    table = get_table("PL")
    if len(table) < 20: return []
    return table[17:20]

def get_top_scorer_race(comp="PL"):
    scorers = get_top_scorers(comp, limit=3)
    if not scorers: return None
    leader = scorers[0]
    return {
        "leader": leader["player"]["name"],
        "team": leader["team"]["name"],
        "goals": leader["goals"],
        "assists": leader.get("assists") or 0,
        "chasers": [{"name": s["player"]["name"], "team": s["team"]["name"], "goals": s["goals"]} for s in scorers[1:]]
    }

def build_verified_stats_block(team_name=None, comp="PL"):
    blocks = []
    title = get_title_race_snapshot()
    if title:
        blocks.append("TITLE_RACE: " + title["leader"] + " " + str(title["leader_pts"]) + "pts (P" + str(title["leader_played"]) + ", GD" + ("+" if title["leader_gd"]>=0 else "") + str(title["leader_gd"]) + "), " + title["second"] + " " + str(title["second_pts"]) + "pts. Gap: " + str(title["gap"]) + "pts. Leader_safe: " + str(title["leader_safe"]) + ".")
    ts = get_top_scorer_race(comp)
    if ts:
        blocks.append("TOP_SCORER: " + ts["leader"] + " (" + ts["team"] + ") on " + str(ts["goals"]) + " goals.")
    if team_name:
        pos = get_team_position(team_name, comp)
        if pos:
            blocks.append("TEAM_POSITION: " + pos["team"]["name"] + " " + str(pos["position"]) + ", " + str(pos["points"]) + "pts (P" + str(pos["playedGames"]) + ", W" + str(pos["won"]) + " D" + str(pos["draw"]) + " L" + str(pos["lost"]) + ").")
        form = get_team_form(team_name, comp)
        if form:
            blocks.append("TEAM_FORM_LAST_5: " + "-".join(form))
    rel = get_relegation_zone()
    if rel:
        blocks.append("RELEGATION_ZONE: " + ", ".join(r["team"]["name"] + " (" + str(r["points"]) + "pts)" for r in rel))
    return "\n".join(blocks) if blocks else "NO_VERIFIED_STATS_AVAILABLE"

if __name__ == "__main__":
    print("=== TITLE RACE ===")
    print(json.dumps(get_title_race_snapshot(), indent=2))
    print("=== TOP SCORER PL ===")
    print(json.dumps(get_top_scorer_race("PL"), indent=2))
    print("=== ARSENAL FORM ===")
    print(get_team_form("Arsenal"))
    print("=== VERIFIED STATS BLOCK (Arsenal) ===")
    print(build_verified_stats_block("Arsenal"))
