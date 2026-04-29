import sqlite3
import json
import logging
from itertools import combinations

DB_PATH = "/root/90minwaffle/data/waffle.db"
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
    "atletico","dortmund","leeds","coventry","leicester"
]

PLAYERS = [
    "salah","haaland","palmer","saka","rice","trent","isak",
    "eze","rashford","fernandes","maddison","son","wilson",
    "havertz","odegaard","martinelli","mbappe","vinicius",
    "bellingham","yamal","dembele","lewandowski","kane","wirtz",
    "musiala","palhinha","sessegnon","cherki","de zerbi","arteta",
    "guardiola","slot","howe","rosenior"
]

def extract_entities(title):
    t = title.lower()
    return {e for e in CLUBS + PLAYERS if e in t}

def find_corroborated(stories):
    corroborated = set()
    for s1, s2 in combinations(stories, 2):
        if s1["source"] == s2["source"]:
            continue
        shared = extract_entities(s1["title"]) & extract_entities(s2["title"])
        if shared:
            corroborated.add(s1["id"])
            corroborated.add(s2["id"])
    return corroborated

def apply_corroboration_bonus():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT id, title, source, score, score_breakdown
        FROM stories
        WHERE status IN ('holding', 'new', 'skipped')
        AND score > 0
    """)
    rows = c.fetchall()
    stories = [{"id": r[0], "title": r[1], "source": r[2], "score": r[3], "breakdown": r[4]} for r in rows]

    log.info(f"Entity-matching {len(stories)} stories for corroboration...")
    corroborated_ids = find_corroborated(stories)
    log.info(f"Found {len(corroborated_ids)} corroborated stories")

    boosted = 0
    for story in stories:
        if story["id"] not in corroborated_ids:
            continue
        try:
            breakdown = json.loads(story["breakdown"]) if story["breakdown"] else {}
        except Exception:
            breakdown = {}
        if breakdown.get("disqualified") or "multi_source" in breakdown:
            continue

        new_score = min(100, story["score"] + 20)
        breakdown["multi_source"] = 20
        breakdown["total"] = new_score
        status = "shippable" if new_score >= 45 else ("holding" if new_score >= 30 else "skipped")
        if status == "shippable":
            boosted += 1
            log.info(f"  🟢 [{new_score:3d}] {story['title'][:75]}")

        c.execute("UPDATE stories SET score=?, score_breakdown=?, status=? WHERE id=?",
                  (new_score, json.dumps(breakdown), status, story["id"]))

    conn.commit()
    conn.close()
    log.info(f"=== Done — {boosted} promoted to shippable ===")
    return boosted

if __name__ == "__main__":
    apply_corroboration_bonus()
