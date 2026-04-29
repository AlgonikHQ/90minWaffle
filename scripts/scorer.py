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

WOMENS_SIGNALS = [
    "women", "woman", "wsl", "women's super league", "uwcl",
    "women's champions league", "lionesses", "england women",
    "women's world cup", "women's euro", "weuros",
    "arsenal women", "chelsea women", "manchester city women",
    "manchester united women", "liverpool women", "tottenham women",
    "leicester women", "aston villa women", "brighton women",
    "everton women", "west ham women", "newcastle women",
    "barcelona femeni", "lyon women", "psg women",
    "she", "her", "girls", "female football",
    "women's fa cup", "women's league cup", "conti cup",
    "millie bright", "leah williamson", "beth mead",
    "alex greenwood", "keira walsh", "ella toone",
    "alessia russo", "lucy bronze", "mary earps",
    "chloe kelly", "lauren james", "jess carter",
    "vivianne miedema", "sam kerr", "ada hegerberg",
    "aitana bonmati", "alexia putellas",
]

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
    "injury", "injured", "surgery", "facial", "ruled out", "scan",
    "sacked", "appointed", "new manager", "manager of",
    "nominated", "award", "podcast", "analysis", "opinion", "ranked",
    "kit release", "kit revealed", "kit details", "kit leaked",
    "strip", "jersey", "shirt", "wage", "wages", "salary",
    "contract extension", "new deal", "renews", "extends contract",
    "beer commercial", "commercial", "advert", "campaign",
    "misses", "miss", "out for", "fitness doubt", "team bus",
    "vineyard", "inspired", "leaked", "third kit", "home kit", "away kit"
]

TITLE_RACE_KEYWORDS = [
    "title race", "title charge", "title run", "title fight",
    "top of the table", "points clear", "points behind",
    "decider", "title decider",
    "golden boot", "top four", "top 4", "top-four",
    "european spot", "europa league spot", "champions league spot",
    "relegation battle", "relegation fight", "relegation zone",
    "relegated", "drop zone", "survival", "staying up",
    "league leaders", "premier league title", "prem title", "rangers", "celtic", "old firm", "ibrox", "parkhead", "scottish title", "spfl title", "world cup squad", "world cup 2026", "nations league final", "squad announcement"
]

# UCL / European competition keywords — never title race
UCL_KEYWORDS = [
    "champions league", "ucl", "europa league", "conference league",
    "semi-final", "semi final", "quarter-final", "quarter final",
    "round of 16", "knockout", "european night", "away goals",
    "aggregate", "two legs", "second leg", "first leg"
]

# Post-match result keywords — strict
RESULT_KEYWORDS = [
    "full time", "full-time", "ft:", "match report", "highlights",
    "post-match", "post match", "reaction", "after the match",
    "player ratings", "man of the match", "motm", "match rating",
    "five things we learned", "talking points", "verdict"
]

# Preview keywords — strict
PREVIEW_KEYWORDS = [
    "preview", "prediction", "predicted lineup", "predicted xi",
    "team news", "ahead of", "build-up", "build up",
    "how to watch", "kick off time", "kick-off time",
    "match preview", "everything you need to know"
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
    "conference league"
]

# Exclude non-football noise — football/soccer ONLY allowed through
NOISE_KEYWORDS = [
    # ── Horse racing ──────────────────────────────────────────────────────────
    "horse racing", "horse race", "horseracing", "racehorse", "thoroughbred",
    "jockey", "trainer", "stallion", "filly", "gelding", "furlong",
    "cheltenham", "ascot", "goodwood", "epsom", "newmarket", "kempton",
    "sandown", "haydock", "leopardstown", "punchestown", "curragh",
    "grand national", "royal ascot", "cheltenham festival", "gold cup",
    "champion hurdle", "stayers hurdle", "arkle", "novices",
    "prix de", "prix ganay", "breeders cup", "kentucky derby",
    "odds on", "each way", "nap of the day", "racing tips",
    "il etait temps", "daryz", "lady blanche", "dowman",

    # ── Formula 1 / Motorsport ───────────────────────────────────────────────
    "formula 1", "formula one", "f1 race", "f1 driver", "f1 team",
    "grand prix", "gp race", "qualifying session", "sprint race",
    "pole position", "fastest lap", "pit stop", "safety car",
    "verstappen", "hamilton", "leclerc", "norris", "russell",
    "alonso", "sainz", "perez", "piastri", "stroll", "tsunoda",
    "red bull racing", "ferrari f1", "mercedes f1", "mclaren f1",
    "aston martin f1", "williams f1", "alpine f1", "haas f1",
    "fia", "motogp", "nascar", "indycar", "tour de france",
    "miami gp", "monaco gp", "silverstone gp", "monza gp",
    "wolff", "horner", "binotto", "cadillac f1",

    # ── Cricket ───────────────────────────────────────────────────────────────
    "cricket", "wicket", "wickets", "batting", "bowling figures",
    "test match", "ashes", "the ashes", "ipl", "t20", "odi",
    "test cricket", "county cricket", "one day international",
    "spinner", "pacer", "century", "duck", "over", "innings",

    # ── Rugby ─────────────────────────────────────────────────────────────────
    "rugby union", "rugby league", "six nations", "rugby world cup",
    "premiership rugby", "pro14", "pro12", "super rugby",
    "try scored", "line out", "scrum", "ruck", "maul",
    "fly half", "hooker", "prop forward", "lock forward",

    # ── Tennis ───────────────────────────────────────────────────────────────
    "tennis", "wimbledon", "us open tennis", "french open", "australian open",
    "roland garros", "atp", "wta", "grand slam tennis",
    "set point", "match point", "ace serve", "double fault",
    "djokovic", "alcaraz", "sinner", "medvedev", "swiatek",

    # ── Golf ─────────────────────────────────────────────────────────────────
    "golf", "pga tour", "ryder cup", "masters golf", "the open golf",
    "us open golf", "birdie", "eagle", "bogey", "par", "handicap",
    "fairway", "bunker", "green", "caddie",
    "mcilroy", "rory", "tiger woods", "scheffler", "hovland",

    # ── Boxing / MMA / Combat ────────────────────────────────────────────────
    "boxing", "boxer", "boxing match", "world title fight",
    "heavyweight", "knockout blow", "ufc", "mma", "wrestling",
    "fury", "joshua", "aj vs", "usyk", "canelo", "wilder",
    "tyson", "ngannou", "conor mcgregor",

    # ── American sports ──────────────────────────────────────────────────────
    "nfl", "nba", "nhl", "mlb", "super bowl", "world series",
    "playoffs nba", "playoffs nfl", "slam dunk", "three pointer",
    "touchdown", "quarterback", "running back", "wide receiver",
    "lebron", "steph curry", "lakers", "celtics", "warriors",
    "patriots", "chiefs", "cowboys", "yankees", "dodgers",
    "nuggets", "halfcourt", "mascot",

    # ── Snooker / Darts ──────────────────────────────────────────────────────
    "snooker", "o'sullivan", "ronnie o", "crucible", "world snooker",
    "maximum break", "century break", "frame", "cue ball",
    "darts", "treble 20", "bullseye", "oche", "van gerwen",
    "gerwyn price", "michael smith darts", "luke littler",

    # ── Athletics / Olympics / Cycling ───────────────────────────────────────
    "athletics", "marathon", "sprinter", "100m", "long jump",
    "javelin", "discus", "shot put", "decathlon", "heptathlon",
    "olympics", "olympic games", "paralympics",
    "cycling", "tour de france", "giro", "vuelta", "velodrome",
    "triathlon", "swimming race", "gymnastics",

    # ── Other sports ─────────────────────────────────────────────────────────
    "basketball", "netball", "volleyball", "handball",
    "ice hockey", "field hockey", "lacrosse", "squash",
    "badminton", "table tennis", "polo", "equestrian",
    "ski", "skiing", "snowboard", "biathlon",
    "sailing", "rowing", "kayak", "canoe",

    # ── Celebrity / Entertainment / Non-sports ───────────────────────────────
    "celebrity", "dua lipa", "taylor swift", "beyonce", "kanye",
    "oktoberfest", "ikea", "instagram filter", "tiktok trend",
    "birthday party", "red carpet", "movie", "film review",
    "tv show", "reality tv", "love island", "big brother",

    # ── Sky Sports non-football filler ───────────────────────────────────────
    "live on sky sports racing", "live on sky sports cricket",
    "live on sky sports golf", "live on sky sports f1",
    "more than the score", "sky sports news live",
    "scottish football podcast", "fpl podcast", "racing podcast",
    "today on sky sports racing", "today on sky sports golf",
]

# Football-positive signals — story must contain at least one to pass noise gate
FOOTBALL_SIGNALS = [
    "football", "soccer", "premier league", "championship", "league one",
    "league two", "fa cup", "efl cup", "carabao cup", "champions league",
    "europa league", "conference league", "world cup", "euros", "euro 2024",
    "bundesliga", "la liga", "serie a", "ligue 1", "eredivisie",
    "mls", "afcon", "copa america",
    "goalkeeper", "striker", "midfielder", "winger", "defender",
    "manager", "head coach", "transfer", "signing", "match", "goal",
    "penalty", "free kick", "corner", "offside", "var", "red card",
    "yellow card", "hat trick", "clean sheet", "assist",
    "relegation", "promotion", "play-off", "fixture", "squad",
    "pitch", "stadium", "fans", "supporter", "derby",
]

FORMAT_MAP = {
    "confirmed_transfer": "F1",
    "transfer_rumour":    "F2",
    "match_preview":      "F3",
    "post_match":         "F4",
    "title_race":         "F5",
    "star_spotlight":     "F6",
    "hot_take":           "F7",
    "womens_football":    "F9",
}

EXPIRY_HOURS = {
    "F1": 2, "F2": 6, "F3": 24, "F4": 4,
    "F5": 24, "F6": 48, "F7": 12, "F9": 24
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
    # Must contain at least one football signal to proceed
    if not contains_any(t, FOOTBALL_SIGNALS):
        return 0, {"disqualified": "no football signal"}

    # ── Women's football boost ────────────────────────────────────────────────
    if contains_any(t, WOMENS_SIGNALS):
        score += 5
        breakdown["womens_football"] = 5
        story["is_womens"] = True

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
    # Only fire if genuine title/relegation narrative — not just "run-in" or generic league mention
    title_race_strong = [
        "title race", "title charge", "title fight", "top of the table",
        "points clear", "points behind", "title decider", "golden boot",
        "relegation battle", "relegation fight", "drop zone", "staying up",
        "league leaders", "premier league title", "prem title",
        "rangers", "celtic", "old firm", "scottish title", "spfl title",
        "world cup squad", "world cup 2026", "nations league final", "squad announcement"
    ]
    if contains_any(t, title_race_strong):
        score += 10
        breakdown["title_race"] = 10

    # ── UCL / European competition boost ─────────────────────────────────────
    if contains_any(t, UCL_KEYWORDS):
        score += 10
        breakdown["ucl_boost"] = 10

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

    # F9 — Women's Football (always check first after tips)
    if contains_any(t, WOMENS_SIGNALS):
        return "F9"

    # F8 — Tips & Bets (always first)
    if contains_any(t, TIPS_KEYWORDS):
        return "F8"

    # Hard exclusion check — these NEVER become F1 or F2 regardless of other signals
    is_excluded = contains_any(t, TRANSFER_EXCLUSIONS)

    # F1 — Confirmed transfer (Here We Go signal + strict transfer keywords, no exclusions)
    if not is_excluded and contains_any(t, HERE_WE_GO) and contains_any(t, TRANSFER_KEYWORDS):
        return "F1"

    # F2 — Transfer rumour — only if not excluded AND no injury/kit/personal signals
    injury_signals = ["injur", "surgery", "ruled out", "miss", "scan", "facial", "hospital"]
    kit_signals = ["kit", "strip", "jersey", "shirt", "badge", "crest", "vineyard", "leaked"]
    personal_signals = ["commercial", "advert", "beer", "campaign", "bus", "video"]
    is_injury = any(s in t for s in injury_signals)
    is_kit = any(s in t for s in kit_signals)
    is_personal = any(s in t for s in personal_signals)

    if not is_excluded and not is_injury and not is_kit and not is_personal and contains_any(t, TRANSFER_KEYWORDS):
        return "F2"

    # F4 — Post-match result (check before preview — result pages often mention upcoming too)
    if contains_any(t, RESULT_KEYWORDS):
        return "F4"

    # UCL / European competition content — route as F4 post-match or F3 preview
    if contains_any(t, UCL_KEYWORDS):
        if contains_any(t, PREVIEW_KEYWORDS + ["ahead of", "vs", "v ", "how to watch", "kick"]):
            return "F3"
        return "F4"  # Default UCL content to match report / reaction

    # F3 — Match preview (domestic)
    if contains_any(t, PREVIEW_KEYWORDS + ["vs", "v ", "facing", "takes on"]):
        return "F3"

    # F5 — Title race (strict domestic league only — UCL excluded above)
    if contains_any(t, TITLE_RACE_KEYWORDS) and not contains_any(t, UCL_KEYWORDS):
        return "F5"

    # F6 — Star Spotlight: retirement, injury, personal, kit, award, records
    if contains_any(t, [
        "retires", "retirement", "announces retirement", "hanging up", "calling time",
        "injured", "injury", "ruled out", "out for", "scan", "surgery", "fitness doubt",
        "kit", "strip", "jersey", "shirt release",
        "award", "nominated", "ballon", "record", "broke a", "history", "milestone",
        "profile", "legend", "spotlight", "man of the match", "motm",
        "player of", "young player"
    ]):
        return "F6"

    # F7 — Hot Take: manager news, opinion, analysis, podcast
    if contains_any(t, [
        "sacked", "appointed manager", "new manager", "head coach", "interim",
        "takes charge", "named manager", "manager of the year", "nominated for",
        "podcast", "analysis", "opinion", "column", "verdict", "ranked", "ranking",
        "why", "should", "must", "case for", "argument", "controversial",
        "sacked in the morning", "deep dive", "five things", "talking points",
        "what went wrong", "what next", "the problem with", "hot take"
    ]):
        return "F7"

    # F6 — Star Spotlight (secondary check via keyword list)
    if contains_any(t, STAR_SPOTLIGHT_KEYWORDS):
        return "F6"

    # F7 — Hot Take (secondary check via keyword list)
    if contains_any(t, HOT_TAKE_KEYWORDS):
        return "F7"

    # Default — F7 for scored content, F6 for everything else
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
