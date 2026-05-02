#!/usr/bin/env python3
"""
stat_engine.py — Verified stat blocks for 90minWaffle script generation.
Expanded May 2026: UCL, Championship, Scottish Premiership support added.
Stat blocks are fed to Claude in script_gen.py — only verified cached data,
never invented numbers.
"""
import json, logging
from pathlib import Path
from datetime import datetime, timezone

CACHE_DIR = Path("/root/90minwaffle/data/cache")
LOG_PATH  = "/root/90minwaffle/logs/stat_engine.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── Competition code map ───────────────────────────────────────────────────
# Maps internal comp codes to cache file prefixes
COMP_MAP = {
    "PL":  "PL",    # Premier League
    "CL":  "CL",    # UEFA Champions League
    "ELC": "ELC",   # EFL Championship
    "SPL": "SPL",   # Scottish Premiership
    "EL":  "EL",    # UEFA Europa League
    "ECL": "ECL",   # UEFA Conference League
}

def _load(name):
    p = CACHE_DIR / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception as e:
        log.error(f"Cache read fail {name}: {e}")
        return None

# ── Table / standings ──────────────────────────────────────────────────────

def get_table(comp="PL"):
    d = _load(f"standings_{comp}")
    if not d:
        return []
    # football-data.org format
    if "standings" in d:
        return d["standings"][0].get("table", []) if d["standings"] else []
    # Flat list format (SPL fallback)
    if "table" in d:
        return d["table"]
    return []

def get_team_position(team_name, comp="PL"):
    table = get_table(comp)
    tn = team_name.lower()
    for row in table:
        name = row.get("team", {}).get("name", "").lower()
        if tn in name or name in tn:
            return row
    return None

# ── Scorers ────────────────────────────────────────────────────────────────

def get_top_scorers(comp="PL", limit=5):
    d = _load(f"scorers_{comp}")
    if not d:
        return []
    return (d.get("scorers") or d.get("topScorers") or [])[:limit]

# ── Matches ────────────────────────────────────────────────────────────────

def get_upcoming_matches(comp="PL", limit=10):
    d = _load(f"matches_{comp}")
    if not d:
        return []
    matches = d.get("matches") or d.get("fixtures") or []
    return [m for m in matches if m.get("status") in ("SCHEDULED", "TIMED")][:limit]

def get_recent_results(comp="PL", limit=10):
    d = _load(f"matches_{comp}")
    if not d:
        return []
    matches = d.get("matches") or d.get("fixtures") or []
    finished = [m for m in matches if m.get("status") == "FINISHED"]
    finished.sort(key=lambda x: x.get("utcDate", ""), reverse=True)
    return finished[:limit]

def get_team_form(team_name, comp="PL", last=5):
    results = get_recent_results(comp, limit=50)
    form = []
    tn = team_name.lower()
    for m in results:
        h  = m.get("homeTeam", {}).get("name", "").lower()
        a  = m.get("awayTeam", {}).get("name", "").lower()
        if tn not in h and tn not in a and h not in tn and a not in tn:
            continue
        score = m.get("score", {}).get("fullTime", {})
        hs, as_ = score.get("home"), score.get("away")
        if hs is None or as_ is None:
            continue
        is_home = tn in h or h in tn
        if hs == as_:
            form.append("D")
        elif (is_home and hs > as_) or (not is_home and as_ > hs):
            form.append("W")
        else:
            form.append("L")
        if len(form) >= last:
            break
    return form

# ── Snapshot builders ──────────────────────────────────────────────────────

def get_title_race_snapshot(comp="PL"):
    table = get_table(comp)
    if len(table) < 2:
        return None
    leader = table[0]
    second = table[1]
    total_games = 38 if comp in ("PL", "SPL") else 46 if comp == "ELC" else 36
    played = leader.get("playedGames", leader.get("played", 0))
    games_left_leader = total_games - played
    played2 = second.get("playedGames", second.get("played", 0))
    games_left_second = total_games - played2
    max_second = second["points"] + (games_left_second * 3)
    return {
        "leader":           leader["team"]["name"],
        "leader_pts":       leader["points"],
        "leader_played":    played,
        "leader_gd":        leader.get("goalDifference", 0),
        "second":           second["team"]["name"],
        "second_pts":       second["points"],
        "gap":              leader["points"] - second["points"],
        "max_second":       max_second,
        "leader_safe":      leader["points"] > max_second,
        "games_left_leader": games_left_leader,
        "games_left_second": games_left_second,
    }

def get_relegation_zone(comp="PL"):
    table = get_table(comp)
    cutoff = 18 if comp == "PL" else 22 if comp == "ELC" else 10
    if len(table) < cutoff:
        return []
    return table[cutoff - 3:cutoff]

def get_top_scorer_race(comp="PL"):
    scorers = get_top_scorers(comp, limit=3)
    if not scorers:
        return None
    leader = scorers[0]
    player = leader.get("player", {})
    team   = leader.get("team", {})
    return {
        "leader":  player.get("name", "Unknown"),
        "team":    team.get("name", "Unknown"),
        "goals":   leader.get("goals", 0),
        "assists": leader.get("assists", 0),
        "chasers": [
            {
                "name":  s.get("player", {}).get("name", ""),
                "team":  s.get("team", {}).get("name", ""),
                "goals": s.get("goals", 0),
            }
            for s in scorers[1:]
        ],
    }

# ── UCL-specific stats ─────────────────────────────────────────────────────

def get_ucl_snapshot():
    """Return top 4 CL standings + recent results."""
    table = get_table("CL")
    blocks = []
    if table:
        top4 = table[:4]
        rows = [f"{r['team']['name']} {r['points']}pts (P{r.get('playedGames', r.get('played',0))})" for r in top4]
        blocks.append("UCL_TOP4: " + " | ".join(rows))
    results = get_recent_results("CL", limit=5)
    if results:
        lines = []
        for m in results:
            h  = m.get("homeTeam", {}).get("name", "?")
            a  = m.get("awayTeam", {}).get("name", "?")
            sc = m.get("score", {}).get("fullTime", {})
            hs = sc.get("home", "?")
            as_ = sc.get("away", "?")
            lines.append(f"{h} {hs}-{as_} {a}")
        blocks.append("UCL_RECENT: " + " | ".join(lines))
    return blocks

# ── Scottish Premiership stats ─────────────────────────────────────────────

def get_scottish_snapshot():
    blocks = []
    title = get_title_race_snapshot("SPL")
    if title:
        blocks.append(
            f"SPL_TITLE: {title['leader']} {title['leader_pts']}pts "
            f"(P{title['leader_played']}, GD{'+' if title['leader_gd']>=0 else ''}{title['leader_gd']}), "
            f"{title['second']} {title['second_pts']}pts. Gap: {title['gap']}pts."
        )
    rel = get_relegation_zone("SPL")
    if rel:
        blocks.append("SPL_BOTTOM: " + ", ".join(
            f"{r['team']['name']} ({r['points']}pts)" for r in rel
        ))
    return blocks

# ── Championship stats ─────────────────────────────────────────────────────

def get_championship_snapshot():
    blocks = []
    title = get_title_race_snapshot("ELC")
    if title:
        blocks.append(
            f"CHAMP_TITLE: {title['leader']} {title['leader_pts']}pts "
            f"(P{title['leader_played']}), "
            f"{title['second']} {title['second_pts']}pts. Gap: {title['gap']}pts."
        )
    ts = get_top_scorer_race("ELC")
    if ts:
        blocks.append(f"CHAMP_TOP_SCORER: {ts['leader']} ({ts['team']}) — {ts['goals']} goals.")
    return blocks

# ── Master block builder ───────────────────────────────────────────────────

def build_verified_stats_block(team_name=None, comp="PL"):
    """
    Build a verified stats block for script_gen.py.
    Comp is auto-detected by script_gen from story title.
    Covers: PL, CL, ELC (Championship), SPL (Scottish).
    """
    blocks = []

    if comp == "CL":
        blocks.extend(get_ucl_snapshot())
        # Also pull team position if we know the team
        if team_name:
            pos = get_team_position(team_name, "CL")
            if pos:
                p = pos.get("playedGames", pos.get("played", 0))
                blocks.append(
                    f"TEAM_CL_POSITION: {pos['team']['name']} "
                    f"{pos['points']}pts (P{p}, "
                    f"W{pos.get('won',0)} D{pos.get('draw',0)} L{pos.get('lost',0)})."
                )

    elif comp in ("ELC", "Championship"):
        blocks.extend(get_championship_snapshot())
        if team_name:
            pos = get_team_position(team_name, "ELC")
            if pos:
                p = pos.get("playedGames", pos.get("played", 0))
                blocks.append(
                    f"CHAMP_TEAM: {pos['team']['name']} "
                    f"P{pos['position']}, {pos['points']}pts (P{p})."
                )
            form = get_team_form(team_name, "ELC")
            if form:
                blocks.append("CHAMP_FORM_LAST5: " + "-".join(form))

    elif comp == "SPL":
        blocks.extend(get_scottish_snapshot())
        if team_name:
            pos = get_team_position(team_name, "SPL")
            if pos:
                p = pos.get("playedGames", pos.get("played", 0))
                blocks.append(
                    f"SPL_TEAM: {pos['team']['name']} "
                    f"P{pos['position']}, {pos['points']}pts (P{p})."
                )
            form = get_team_form(team_name, "SPL")
            if form:
                blocks.append("SPL_FORM_LAST5: " + "-".join(form))

    else:
        # Default: Premier League
        title = get_title_race_snapshot("PL")
        if title:
            blocks.append(
                f"TITLE_RACE: {title['leader']} {title['leader_pts']}pts "
                f"(P{title['leader_played']}, GD{'+' if title['leader_gd']>=0 else ''}{title['leader_gd']}), "
                f"{title['second']} {title['second_pts']}pts. "
                f"Gap: {title['gap']}pts. Leader_safe: {title['leader_safe']}."
            )
        ts = get_top_scorer_race("PL")
        if ts:
            blocks.append(f"TOP_SCORER: {ts['leader']} ({ts['team']}) on {ts['goals']} goals.")
        if team_name:
            pos = get_team_position(team_name, "PL")
            if pos:
                p = pos.get("playedGames", pos.get("played", 0))
                blocks.append(
                    f"TEAM_POSITION: {pos['team']['name']} "
                    f"P{pos['position']}, {pos['points']}pts "
                    f"(P{p}, W{pos.get('won',0)} D{pos.get('draw',0)} L{pos.get('lost',0)})."
                )
            form = get_team_form(team_name, "PL")
            if form:
                blocks.append("TEAM_FORM_LAST_5: " + "-".join(form))
        rel = get_relegation_zone("PL")
        if rel:
            blocks.append("RELEGATION_ZONE: " + ", ".join(
                f"{r['team']['name']} ({r['points']}pts)" for r in rel
            ))

    return "\n".join(blocks) if blocks else "NO_VERIFIED_STATS_AVAILABLE"

if __name__ == "__main__":
    print("=== PL TITLE RACE ===")
    print(json.dumps(get_title_race_snapshot("PL"), indent=2))
    print("=== UCL SNAPSHOT ===")
    print("\n".join(get_ucl_snapshot()))
    print("=== CHAMPIONSHIP SNAPSHOT ===")
    print("\n".join(get_championship_snapshot()))
    print("=== SCOTTISH SNAPSHOT ===")
    print("\n".join(get_scottish_snapshot()))
    print("=== VERIFIED BLOCK (Arsenal, PL) ===")
    print(build_verified_stats_block("Arsenal", "PL"))
    print("=== VERIFIED BLOCK (Celtic, SPL) ===")
    print(build_verified_stats_block("Celtic", "SPL"))
