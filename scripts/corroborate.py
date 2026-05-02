import sqlite3
import json
import logging
from itertools import combinations
from collections import defaultdict

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/scorer.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

CLUBS = [
    "arsenal","man city","manchester city","liverpool","chelsea",
    "man utd","manchester united","tottenham","spurs","newcastle",
    "aston villa","west ham","fulham","everton","brighton",
    "crystal palace","brentford","wolves","forest","bournemouth",
    "real madrid","barcelona","bayern","psg","juventus","inter",
    "atletico","dortmund","leeds","coventry","leicester","sunderland",
    "celtic","rangers","hearts","hibernian","aberdeen",
]

PLAYERS = [
    "salah","haaland","palmer","saka","rice","trent","isak",
    "eze","rashford","fernandes","maddison","son","wilson",
    "havertz","odegaard","martinelli","mbappe","vinicius",
    "bellingham","yamal","dembele","lewandowski","kane","wirtz",
    "musiala","palhinha","cherki","arteta","guardiola","slot",
    "howe","gyokeres","mainoo","gallagher","nkunku","mudryk",
]

def extract_entities(title):
    t = title.lower()
    return {e for e in CLUBS + PLAYERS if e in t}

def find_corroborated(stories):
    """
    Returns dict of story_id -> source_count (how many distinct sources cover it).
    Stories covered by 2+ sources get boosted.
    Stories covered by 3+ sources get double boost.
    """
    import sqlite3 as _sq
    conn = _sq.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, source FROM stories WHERE status IN ('shippable','published') AND score > 0")
    anchor_rows = c.fetchall()
    conn.close()
    anchors = [{"id": r[0], "title": r[1], "source": r[2]} for r in anchor_rows]

    # Count distinct sources covering each story's entities
    story_sources = defaultdict(set)

    for s1 in stories:
        e1 = extract_entities(s1["title"])
        if not e1:
            continue
        # Check against anchors (already published/shippable)
        for s2 in anchors:
            if s1["source"] == s2["source"]:
                continue
            if e1 & extract_entities(s2["title"]):
                story_sources[s1["id"]].add(s2["source"])

    # Also check within current batch
    for s1, s2 in combinations(stories, 2):
        if s1["source"] == s2["source"]:
            continue
        if extract_entities(s1["title"]) & extract_entities(s2["title"]):
            story_sources[s1["id"]].add(s2["source"])
            story_sources[s2["id"]].add(s1["source"])

    return {sid: len(sources) for sid, sources in story_sources.items()}

def apply_corroboration_bonus():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT id, title, source, score, score_breakdown, format
        FROM stories
        WHERE status IN ('holding', 'new', 'skipped')
        AND score > 0
    """)
    rows = c.fetchall()
    stories = [
        {"id": r[0], "title": r[1], "source": r[2],
         "score": r[3], "breakdown": r[4], "format": r[5]}
        for r in rows
    ]

    log.info(f"Entity-matching {len(stories)} stories for corroboration...")
    corroboration_map = find_corroborated(stories)
    log.info(f"Found {len(corroboration_map)} corroborated stories")

    boosted = 0
    for story in stories:
        source_count = corroboration_map.get(story["id"], 0)
        if source_count == 0:
            continue

        try:
            breakdown = json.loads(story["breakdown"]) if story["breakdown"] else {}
        except Exception:
            breakdown = {}

        if breakdown.get("disqualified") or "multi_source" in breakdown:
            continue

        # Tiered boost: 2 sources = +20, 3+ sources = +35
        bonus = 35 if source_count >= 3 else 20
        new_score = min(100, story["score"] + bonus)
        breakdown["multi_source"] = bonus
        breakdown["multi_source_count"] = source_count
        breakdown["total"] = new_score

        # Format-aware thresholds (same as scorer.py)
        fmt_thresholds = {
            "F1": 40, "F2": 35, "F3": 30, "F4": 30,
            "F5": 30, "F6": 35, "F7": 28, "F8": 40, "F9": 28,
        }
        fmt = story.get("format", "F7")
        ship_threshold = fmt_thresholds.get(fmt, 30)
        hold_threshold = max(ship_threshold - 10, 15)

        if new_score >= ship_threshold:
            status = "shippable"
            boosted += 1
            log.info(f"  🟢 [{new_score:3d}] x{source_count}src {story['title'][:70]}")
        elif new_score >= hold_threshold:
            status = "holding"
        else:
            status = "skipped"

        c.execute(
            "UPDATE stories SET score=?, score_breakdown=?, status=? WHERE id=?",
            (new_score, json.dumps(breakdown), status, story["id"])
        )

    conn.commit()
    conn.close()
    log.info(f"=== Done — {boosted} promoted to shippable ===")
    return boosted

if __name__ == "__main__":
    apply_corroboration_bonus()
