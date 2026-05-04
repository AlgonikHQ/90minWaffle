import anthropic
import sqlite3
import json
import logging
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv('/root/90minwaffle/.env')

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/script_gen.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

FORMAT_LENGTHS = {
    "F1": 60, "F2": 45, "F3": 65, "F4": 55,
    "F5": 70, "F6": 50, "F7": 40
}

FORMAT_NAMES = {
    "F1": "Confirmed Transfer",
    "F2": "Transfer Rumour",
    "F3": "Match Preview",
    "F4": "Post-Match Reaction",
    "F5": "Title Race / Narrative",
    "F6": "Star Spotlight",
    "F7": "Hot Take",
}

try:
    from stat_engine import build_verified_stats_block
except ImportError:
    def build_verified_stats_block(team_name=None, comp="PL"):
        return "No verified stats available — do not invent numbers."

SYSTEM_PROMPT = """You are the script writer for 90minWaffle, a UK football short-form video brand.

VOICE: Hot-take merchant. Loud, opinionated, divisive but fair. UK football vocabulary: bottled it, cooked, doing a Spurs, Pep masterclass, the lads, going down. Punchy stat-led sentences. Banter not beef. Wind up, never attack.

STRUCTURE — every script follows this shape:
1. STAT or FACT — open with a verified number, date, or record from the VERIFIED_STATS block below
2. BANTER — punchy take or skull-emoji-worthy observation, UK football voice
3. ENGAGEMENT QUESTION — end with a binary or open question to drive replies

ACCURACY RULES — non-negotiable:
- Every stat in the script must come from the VERIFIED_STATS block in the user prompt. No invented numbers, dates, or records.
- If a fact is not in VERIFIED_STATS, do not state it. Rephrase around what is verified.
- No conflated facts (e.g. wrong cup, wrong year, wrong opponent). When in doubt, leave it out.

STRICT COMPETITION CONTEXT LOCK (HIGHEST PRIORITY):
- Detect competition from title keywords (UCL, Champions League, Premier League, La Liga, etc.).
- UCL / European stories → speak ONLY about Champions League context. NEVER mention domestic league tables, points, or title races.
- Premier League stories → stay ONLY in PL context.
- Example forbidden: Talking about "73 points" or "title race" in a UCL referee decision story.

HARD RULES — never break these:
- Never attack individual players character, mental health, families or personal lives
- Never reference race, religion, nationality in a negative way
- Never attack specific fans or fan groups
- Never attack referees as people (decisions yes, person no)
- No banned phrases: Did you know, Lets dive into, Hey football fans, Hey guys, In this video, Like and subscribe
- No intro. First word is the hook. Hard cut straight into content.
- Sign-off: state the answer to the setup, then pivot to a binary question. NEVER follow for more.

OUTPUT FORMAT: Respond only in valid JSON, no markdown, no preamble.
{
  "hook_1": "...",
  "hook_2": "...",
  "hook_3": "...",
  "hook_scores": {"hook_1": 0-100, "hook_2": 0-100, "hook_3": 0-100},
  "winning_hook": "hook_1|hook_2|hook_3",
  "mainstream_angle": "full script using winning hook, mainstream take",
  "contrarian_angle": "full script using winning hook, contrarian take with steel-man",
  "winning_script": "mainstream|contrarian",
  "caption": "line 1 hook\\nline 2 question\\n#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5",
  "thumbnail_text": "2-4 word ALL CAPS thumbnail headline"
}"""


# ── Competition detection ─────────────────────────────────────────────────────

def _detect_competition(title: str) -> str:
    """
    Detect competition context from story title.
    Returns both a human-readable label AND a stat_engine comp code.
    Used for: (1) prompt locking in Claude, (2) stat block selection.
    """
    t = title.lower()
    if any(k in t for k in ["champions league", "ucl", "semi-final", "quarter-final",
                              "second leg", "first leg", "aggregate"]):
        return "UEFA Champions League"
    if any(k in t for k in ["europa league", "uel"]):
        return "UEFA Europa League"
    if any(k in t for k in ["conference league", "uecl"]):
        return "UEFA Conference League"
    if any(k in t for k in ["fa cup", "carabao", "efl cup", "league cup",
                              "community shield", "fa trophy", "fa vase"]):
        return "Domestic Cup"
    if any(k in t for k in ["scottish premiership", "spfl", "scottish cup",
                              "scottish league cup", "old firm", "celtic", "rangers",
                              "hearts", "hibernian", "aberdeen"]):
        return "Scottish Premiership"
    if any(k in t for k in ["championship", "efl championship", "league one", "league two"]):
        return "EFL Championship"
    if any(k in t for k in ["bundesliga"]):
        return "Bundesliga"
    if any(k in t for k in ["la liga", "laliga"]):
        return "La Liga"
    if any(k in t for k in ["serie a"]):
        return "Serie A"
    if any(k in t for k in ["ligue 1"]):
        return "Ligue 1"
    if any(k in t for k in ["world cup", "world cup 2026", "nations league"]):
        return "International"
    return "Premier League"

def _comp_to_stat_code(competition_label: str) -> str:
    """Map competition label to stat_engine comp code."""
    mapping = {
        "UEFA Champions League":  "CL",
        "UEFA Europa League":     "CL",   # use CL cache as fallback
        "UEFA Conference League": "CL",
        "EFL Championship":       "ELC",
        "Scottish Premiership":   "SPL",
        "Domestic Cup":           "PL",   # FA Cup/Carabao — PL stats most relevant
        "International":          "PL",   # World Cup/Nations League — PL as context
        "Bundesliga":             "PL",
        "La Liga":                "PL",
        "Serie A":                "PL",
        "Ligue 1":                "PL",
    }
    return mapping.get(competition_label, "PL")


# ── Team detection ────────────────────────────────────────────────────────────

PL_TEAMS = [
    "arsenal", "manchester city", "manchester united", "liverpool", "chelsea",
    "tottenham", "newcastle", "aston villa", "brighton", "west ham",
    "crystal palace", "fulham", "brentford", "everton", "wolves",
    "nottingham forest", "bournemouth", "leeds", "burnley", "leicester",
    "southampton", "ipswich", "sunderland",
]

def _detect_team(title: str):
    """Return first PL team found in title, or None."""
    t = title.lower()
    for team in PL_TEAMS:
        if team in t:
            return team
    return None


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(story: dict, fmt: str) -> str:
    length      = FORMAT_LENGTHS.get(fmt, 55)
    format_name = FORMAT_NAMES.get(fmt, "Football News")
    contrarian  = fmt in ["F5", "F7"]
    sometimes   = fmt in ["F2", "F3", "F4"]

    if contrarian:
        contrarian_instruction = "Contrarian angle is REQUIRED for this format. Steel-man rule: acknowledge the mainstream view fairly before disagreeing."
    elif sometimes:
        contrarian_instruction = "Generate both angles. Pick the stronger one as winning_script."
    else:
        contrarian_instruction = "Contrarian angle not required. Set winning_script to mainstream."

    detected_comp = _detect_competition(story["title"])
    stat_comp     = _comp_to_stat_code(detected_comp)
    detected_team = _detect_team(story["title"])
    verified_stats = build_verified_stats_block(team_name=detected_team, comp=stat_comp)

    # StatiqFC bridge — enrich F3 previews with edge context if available
    edge_context = ""
    if fmt == "F3":
        try:
            import sys as _sys
            _sys.path.insert(0, "/root/90minwaffle/scripts")
            from statiq_bridge import find_edge_for_fixture, build_edge_context_block
            # Extract teams from title
            import re as _re
            vs_match = _re.search(r"(.+?)\s+v[s]?\s+(.+?)(?:\s*[-–:]|$)", story["title"], _re.IGNORECASE)
            if vs_match:
                _home = vs_match.group(1).strip()
                _away = vs_match.group(2).strip()
                _edge = find_edge_for_fixture(_home, _away)
                if _edge:
                    edge_context = build_edge_context_block(_edge)
                    log.info(f"  Edge context injected for {_home} vs {_away}")
        except Exception as _be:
            log.debug(f"  Bridge lookup failed (non-critical): {_be}")

    edge_section = f"\nEDGE_CONTEXT (for F3 only — use to frame statistical angle):\n{edge_context}" if edge_context else ""

    return f"""Generate a 90minWaffle video script for this story:

COMPETITION LOCK: {detected_comp} — speak ONLY in this competition's context. Never mix competitions.

VERIFIED_STATS (use only these for any numbers/dates/records):
{verified_stats}{edge_section}

HEADLINE: {story["title"]}
SOURCE: {story.get("source", "Unknown")} (Tier {story.get("source_tier", 2)})
FORMAT: {fmt} — {format_name}
TARGET LENGTH: ~{length} seconds spoken (~{length * 2} words)
SCORE: {story.get("score", 50)}/100

{contrarian_instruction}

Generate 3 hook variants. Pick the highest scoring one as winning_hook.
Each hook must lead with a verified stat from VERIFIED_STATS above.
Scripts end with: state the answer, then a binary question CTA.
IMPORTANT: Your entire response must be a single valid JSON object. No markdown, no explanation, no preamble. Start with {{ and end with }}."""


# ── DB helper ─────────────────────────────────────────────────────────────────

def get_db():
    return sqlite3.connect(DB_PATH)


# ── Script generation ─────────────────────────────────────────────────────────

def generate_script(story: dict):
    fmt    = story.get("format", "F7")
    prompt = build_prompt(story, fmt)

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    log.info(f"Generating script for: {story['title'][:70]}")

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        log.info(f"  ✅ Script generated — winning_hook: {result.get('winning_hook')}, script: {result.get('winning_script')}")
        return result

    except json.JSONDecodeError as e:
        log.error(f"  ❌ JSON parse error: {e}")
        return None
    except Exception as e:
        log.error(f"  ❌ API error: {e}")
        return None


# ── Save script to DB ─────────────────────────────────────────────────────────

def save_script(story_id: int, result: dict):
    conn = get_db()
    c    = conn.cursor()

    # Resolve winning_hook — may be "hook_1"/"hook_2"/"hook_3" key or actual text
    winning_hook_raw = result.get("winning_hook", "")
    if winning_hook_raw in ("hook_1", "hook_2", "hook_3"):
        winning_hook_text = result.get(winning_hook_raw, winning_hook_raw)
    else:
        winning_hook_text = winning_hook_raw

    # Resolve winning script
    if result.get("script"):
        winning_script = result.get("script", "")
    else:
        winning_script_key = result.get("winning_script", "mainstream")
        winning_script = result.get(f"{winning_script_key}_angle", "")

    if not winning_script or not winning_script.strip():
        log.warning(f"  Empty script for story {story_id} — resetting to shippable")
        c.execute("UPDATE stories SET status='shippable' WHERE id=?", (story_id,))
        conn.commit(); conn.close()
        return

    c.execute('''
        UPDATE stories SET
            hook_1       = ?,
            hook_2       = ?,
            hook_3       = ?,
            winning_hook = ?,
            script       = ?,
            caption      = ?,
            status       = 'scripted'
        WHERE id = ?
    ''', (
        result.get("hook_1"),
        result.get("hook_2"),
        result.get("hook_3"),
        winning_hook_text,
        winning_script,
        result.get("caption"),
        story_id
    ))
    conn.commit()
    conn.close()
    log.info(f"  💾 Saved — hook: {winning_hook_text[:60]}")


# ── Main loop ─────────────────────────────────────────────────────────────────

def process_shippable_stories(limit=10):
    conn = get_db()
    c    = conn.cursor()
    c.execute('''
        SELECT id, title, url, source, source_tier, score, format
        FROM stories
        WHERE status = 'shippable'
        ORDER BY score DESC
        LIMIT ?
    ''', (limit,))
    rows  = c.fetchall()
    conn.close()

    stories = [
        {"id": r[0], "title": r[1], "url": r[2], "source": r[3],
         "source_tier": r[4], "score": r[5], "format": r[6]}
        for r in rows
    ]

    log.info(f"=== Script generation — {len(stories)} stories to process ===")
    success = 0
    for story in stories:
        result = generate_script(story)
        if result:
            save_script(story["id"], result)
            success += 1

    log.info(f"=== Done — {success}/{len(stories)} scripts generated ===")
    return success


if __name__ == "__main__":
    process_shippable_stories(limit=10)
