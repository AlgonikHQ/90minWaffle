import sqlite3
import json
import logging
import re
from datetime import datetime, timezone, timedelta

DB_PATH = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/scorer.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# ── Keyword signal lists ──────────────────────────────────────────────────────

HERE_WE_GO = [
    "here we go", "confirmed", "official", "signs", "signed", "done deal",
    "agreement reached", "medical", "completes move", "joins", "unveiled"
]

TRANSFER_KEYWORDS = [
    "transfer", "signing", "bid", "loan fee", "transfer fee", "release clause",
    "buy-out clause", "transfer talks", "transfer negotiations", "transfer target",
    "transfer approach", "transfer offer", "signed for", "joins", "completes move",
    "agrees deal", "agrees terms", "medical booked", "here we go"
]

# Non-transfer contexts that must NOT trigger F1/F2 even if transfer words appear
TRANSFER_EXCLUSIONS = [
    "retires", "retirement", "announces retirement", "hanging up",
    "injury", "injured", "sacked", "appointed", "new manager", "manager of",
    "nominated", "award", "podcast", "analysis", "opinion", "ranked",
    "kit release", "kit revealed", "strip", "wage", "wages", "salary",
    "contract extension", "new deal", "renews", "extends contract"
]

TITLE_RACE_KEYWORDS = [
    "title race", "title charge", "champions", "championship", "top of the table",
    "points clear", "points behind", "runin", "run-in", "decider", "deciding",
    "golden boot", "top four", "top 4", "european spot", "relegation battle",
    "relegated", "drop zone", "survival"
]

BIG_CLUBS = [
    "arsenal", "manchester city", "man city", "liverpool", "chelsea",
    "manchester united", "man utd", "tottenham", "spurs", "newcastle",
    "real madrid", "barcelona", "barca", "bayern", "psg", "inter milan",
    "juventus", "atletico"
]

STALE_SIGNALS = [
    "last week", "last month", "yesterday", "earlier this season",
    "looking back", "in 2024", "in 2023", "in 2022"
]

TABLOID_ONLY_SOURCES = ["The Sun", "Daily Mirror", "Daily Star", "Daily Mail"]

LOWER_LEAGUE_SIGNALS = [
    "league one", "league two", "national league", "mls", "saudi pro league",
    "conference league", "scottish premiership"
]

# Exclude non-football noise from 90min / Sky general RSS
NOISE_KEYWORDS = [
    "marathon", "snooker", "cricket", "golf", "tennis", "rugby", "nfl",
    "nba", "boxing", "formula 1", "formula one", "cycling", "olympics",
    "kit leak", "boots", "adidas", "nike", "puma", "kappa", "shirt", "jersey",
    "oktoberfest", "ikea", "instagram", "tiktok", "birthday", "celebrity",
    "wicket", "wickets", "batting", "bowling figures", "test match", "ashes",
    "o'sullivan", "ronnie", "crucible", "snooker world", "world snooker",
    "fury", "joshua", "aj vs", "boxing match", "ufc", "mma", "darts",
    "nascar", "motogp", "tour de france", "wimbledon", "six nations",
    "super bowl", "world series", "dua lipa", "taylor swift", "celebrity",
    "live on sky: ", "more than the score", "the most bizzare",
    "capitals struggle", "ipl", "t20", "odi", "test cricket"
]

FORMAT_MAP = {
    "confirmed_transfer": "F1",
    "transfer_rumour":    "F2",
    "match_preview":      "F3",
    "post_match":         "F4",
    "title_race":         "F5",
    "star_spotlight":     "F6",
    "hot_take":           "F7",
}

EXPIRY_HOURS = {
    "F1": 2, "F2": 6, "F3": 24, "F4": 4,
    "F5": 24, "F6": 48, "F7": 12
}

def get_db():
    return sqlite3.connect(DB_PATH)

def get_star_players(c):
    c.execute("SELECT player_name FROM star_index ORDER BY total_score DESC LIMIT 30")
    return [row[0].lower() for row in c.fetchall()]

def text(story):
    return f"{story['title']} {story.get('url','')}"

def contains_any(text_lower, keywords):
    return any(kw in text_lower for kw in keywords)

def count_matching(text_lower, keywords):
    return sum(1 for kw in keywords if kw in text_lower)

def score_story(story, star_players):
    t = text(story).lower()
    breakdown = {}
    score = 0

    # ── Noise filter — hard disqualify ───────────────────────────────────────
    if contains_any(t, NOISE_KEYWORDS):
        return 0, {"disqualified": "noise/off-topic"}

    # ── Source tier ───────────────────────────────────────────────────────────
    tier = story.get("source_tier", 3)
    tier_points = {1: 30, 2: 15, 3: 5}.get(tier, 5)
    score += tier_points
    breakdown["source_tier"] = tier_points

    # ── Here We Go / confirmed transfer ──────────────────────────────────────
    if contains_any(t, HERE_WE_GO):
        score += 15
        breakdown["here_we_go"] = 15

    # ── Transfer keywords ─────────────────────────────────────────────────────
    transfer_hits = count_matching(t, TRANSFER_KEYWORDS)
    if transfer_hits >= 2:
        score += 10
        breakdown["transfer_keywords"] = 10
    elif transfer_hits == 1:
        score += 5
        breakdown["transfer_keywords"] = 5

    # ── Big club involvement ──────────────────────────────────────────────────
    if contains_any(t, BIG_CLUBS):
        score += 10
        breakdown["big_club"] = 10

    # ── Star player involvement ───────────────────────────────────────────────
    if any(p in t for p in star_players):
        score += 10
        breakdown["star_player"] = 10

    # ── Title race / narrative ────────────────────────────────────────────────
    if contains_any(t, TITLE_RACE_KEYWORDS):
        score += 10
        breakdown["title_race"] = 10

    # ── Negative: stale signals ───────────────────────────────────────────────
    if contains_any(t, STALE_SIGNALS):
        score -= 10
        breakdown["stale"] = -10

    # ── Negative: lower league ────────────────────────────────────────────────
    if contains_any(t, LOWER_LEAGUE_SIGNALS):
        score -= 20
        breakdown["lower_league"] = -20

    # ── Negative: tabloid-only source ────────────────────────────────────────
    if story.get("source") in TABLOID_ONLY_SOURCES:
        score -= 15
        breakdown["tabloid_only"] = -15

    score = max(0, min(100, score))
    breakdown["total"] = score
    return score, breakdown

STAR_SPOTLIGHT_KEYWORDS = [
    "best player", "star man", "in form", "on fire", "hat-trick", "brace",
    "masterclass", "outstanding", "brilliant", "incredible", "world class",
    "player of", "man of the match", "motm", "spotlight", "profile", "legend"
]

HOT_TAKE_KEYWORDS = [
    "opinion", "why", "should", "must", "need to", "time to", "case for",
    "case against", "overrated", "underrated", "debate", "unpopular",
    "hot take", "controversial", "argument", "verdict", "ranked", "ranking",
    "best", "worst", "top 5", "top 10", "greatest", "talking points"
]

TIPS_KEYWORDS = [
    "odds", "bet", "betting", "accumulator", "acca",
    "value bet", "each way", "lay", "bookmaker", "bookie",
    "best bet", "tip of the day", "betting tips", "correct score",
    "both teams to score", "btts", "over 2.5", "under 2.5", "anytime scorer"
]

def detect_format(story, score):
    t = text(story).lower()

    # F8 — Tips & Bets (highest priority)
    if contains_any(t, TIPS_KEYWORDS):
        return "F8"

    # Retirement / personal news — never a transfer story
    if contains_any(t, ["retires", "retirement", "announces retirement", "hanging up", "calling time"]):
        return "F6"  # Star Spotlight

    # Manager / coaching news
    if contains_any(t, ["sacked", "appointed manager", "new manager", "head coach", "interim manager",
                         "managerial", "takes charge", "named manager", "manager of the year",
                         "manager of year", "nominated for"]):
        return "F7"  # Hot Take

    # Injury news
    if contains_any(t, ["injured", "injury", "ruled out", "out for", "scan", "surgery",
                         "fitness doubt", "doubt for", "limped off", "stretcher"]):
        return "F6"  # Star Spotlight

    # Kit / merchandise — not transfer
    if contains_any(t, ["kit", "strip", "jersey", "shirt release", "unveiled", "badge", "crest"]):
        return "F6"

    # Award / stats / records
    if contains_any(t, ["award", "nominated", "trophy", "golden boot", "ballon", "record", "broke a", "history"]):
        return "F6"

    # Podcast / analysis / opinion pieces
    if contains_any(t, ["podcast", "analysis", "opinion", "column", "sacked in the morning",
                         "the debate", "special report", "deep dive"]):
        return "F7"

    # F1 — Confirmed transfer (Here We Go + strong transfer signal, no exclusions)
    is_excluded = contains_any(t, TRANSFER_EXCLUSIONS)
    if not is_excluded and contains_any(t, HERE_WE_GO) and contains_any(t, TRANSFER_KEYWORDS):
        return "F1"

    # F2 — Transfer rumour (strong transfer signal only, no exclusions)
    if not is_excluded and contains_any(t, TRANSFER_KEYWORDS):
        return "F2"

    # F3 — Match preview
    if contains_any(t, ["preview", "prediction", "ahead of", "facing", "vs", "v ", "line-up", "lineup",
                         "team news", "kick off", "kicks off", "build-up"]):
        return "F3"

    # F4 — Post match
    if contains_any(t, ["reaction", "post-match", "post match", "full time", "full-time",
                         "after the match", "beaten", "wins", "win over", "defeat",
                         "result", "final score", "highlights", "player ratings"]):
        return "F4"

    # F5 — Title race / league table
    if contains_any(t, TITLE_RACE_KEYWORDS):
        return "F5"

    # F6 — Star Spotlight
    if contains_any(t, STAR_SPOTLIGHT_KEYWORDS):
        return "F6"

    # F7 — Hot Take / opinion
    if contains_any(t, HOT_TAKE_KEYWORDS):
        return "F7"

    # Default — opinion/analysis for anything that doesn't fit neatly
    if score >= 45:
        return "F7"
    return "F6"

def confidence_colour(score):
    if score >= 65: return "green"
    if score >= 45: return "yellow"
    return "red"

def calc_expiry(fmt):
    hours = EXPIRY_HOURS.get(fmt, 12)
    expires = datetime.now(timezone.utc) + timedelta(hours=hours)
    return expires.isoformat()

def score_unscored_stories():
    conn = get_db()
    c = conn.cursor()

    star_players = get_star_players(c)
    log.info(f"Star index: {len(star_players)} players loaded")

    c.execute("SELECT id, title, url, source, source_tier FROM stories WHERE status = 'new'")
    stories = [
        {"id": r[0], "title": r[1], "url": r[2], "source": r[3], "source_tier": r[4]}
        for r in c.fetchall()
    ]
    log.info(f"Scoring {len(stories)} new stories")

    ship_count = hold_count = skip_count = noise_count = 0

    for story in stories:
        score, breakdown = score_story(story, star_players)
        fmt = detect_format(story, score)
        expires = calc_expiry(fmt)
        confidence = confidence_colour(score)

        if breakdown.get("disqualified"):
            status = "skipped"
            noise_count += 1
        elif score >= 45:
            status = "shippable"
            ship_count += 1
        elif score >= 30:
            status = "holding"
            hold_count += 1
        else:
            status = "skipped"
            skip_count += 1

        c.execute('''
            UPDATE stories SET
                score = ?,
                score_breakdown = ?,
                status = ?,
                format = ?,
                expires_at = ?
            WHERE id = ?
        ''', (score, json.dumps(breakdown), status, fmt, expires, story["id"]))

        if status == "shippable":
            log.info(f"  🟢 [{score:3d}] {fmt} — {story['title'][:70]}")
        elif status == "holding":
            log.info(f"  🟡 [{score:3d}] {fmt} — {story['title'][:70]}")

    conn.commit()
    conn.close()

    log.info(f"=== Scoring complete ===")
    log.info(f"  🟢 Shippable : {ship_count}")
    log.info(f"  🟡 Holding   : {hold_count}")
    log.info(f"  ⚪ Skipped   : {skip_count + noise_count} (incl {noise_count} noise)")

    return ship_count, hold_count, skip_count

if __name__ == "__main__":
    score_unscored_stories()
