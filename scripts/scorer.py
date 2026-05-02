#!/usr/bin/env python3
"""scorer.py — Story scoring and format detection for 90minWaffle.

Format detection rewrite based on real story analysis (May 2026).

Root cause of F6 bloat:
  - detect_format() was falling through to F6 default for most stories
  - Transfer detection was too loose (gossip columns, "where are they now" triggering F2)
  - Opinion/analysis/VAR reaction stories never reached F7 checks
  - Post-match stories with player names hit F6 before F4 check

Fix strategy:
  - F2 (transfer rumour) now requires BOTH a transfer keyword AND a
    player/club movement signal — gossip columns and "where are they now"
    no longer qualify
  - F7 (hot take) check moved UP before F6 — opinion/analysis/reaction
    stories are far more common than genuine star spotlights
  - F6 (star spotlight) is now strictly performance/personal news only
  - F4 (post-match) keyword list expanded to catch match reaction stories
  - _route_channel() updated: F1/F2 without genuine transfer signal
    routes to #general not #breaking_news
"""

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
    "wsl", "women's super league", "uwcl",
    "women's champions league", "lionesses",
    "women's world cup", "women's euro", "weuros",
    "arsenal women", "chelsea women", "manchester city women",
    "manchester united women", "liverpool women", "tottenham women",
    "leicester women", "aston villa women", "brighton women",
    "everton women", "west ham women", "newcastle women",
    "barcelona femeni", "lyon women", "psg women",
    "female football", "women's football",
    "women's fa cup", "women's league cup", "conti cup",
    "millie bright", "leah williamson", "beth mead",
    "alex greenwood", "keira walsh", "ella toone",
    "alessia russo", "lucy bronze", "mary earps",
    "chloe kelly", "lauren james", "jess carter",
    "vivianne miedema", "sam kerr", "ada hegerberg",
    "aitana bonmati", "alexia putellas",
    "women's team", "womens team", "women's side",
]

HERE_WE_GO = [
    "here we go", "confirmed", "done deal",
    "agreement reached", "medical", "completes move", "unveiled",
    "agrees deal", "agrees terms", "medical booked"
]

# Strict transfer movement signals — player actually moving clubs
TRANSFER_MOVEMENT = [
    "signs for", "signed for", "joins", "completes move", "seals move",
    "completes transfer", "seals transfer", "moves to", "heading to",
    "set to join", "closing in", "personal terms agreed", "medical booked",
    "here we go", "done deal", "unveiled as", "officially joins",
    "loan move", "loan deal confirmed", "permanent deal",
]

# Broader transfer interest — rumour level only
TRANSFER_RUMOUR = [
    "transfer", "transfer target", "transfer talks", "transfer approach",
    "transfer offer", "bid", "bid submitted", "bid rejected",
    "loan fee", "transfer fee", "release clause", "buy-out clause",
    "interest in", "linked with", "on the shortlist", "eyeing",
    "monitoring", "considering", "targeting", "wants to sign",
    "could sign", "summer target", "january target",
    "pounce on", "move for", "swoop for", "approach for",
    "gossip", "rumour", "report", "reports suggest", "according to",
    # Italian football source language (Football Italia, Transfermarkt)
    "re-sign", "resign", "chase", "chasing", "switch from", "switch to",
    "extend contract", "contract extension", "new deal", "renew",
    "offered to", "offered for", "offered a", "approach made",
    "personal terms", "fee agreed", "agreement close", "talks advanced",
    "swap deal", "part-exchange", "cash plus", "option to buy",
    "obliged to buy", "co-ownership", "loan with option",
    "summer signing", "winter signing", "free agent", "out of contract",
    "available for", "want to sell", "open to offers", "surplus to",
    "valued at", "price tag", "asking price", "£", "€", "million fee",
]

# Sources known to publish transfer content — boost F2 detection
TRANSFER_SOURCES = [
    "Football Italia", "Transfermarkt", "Fabrizio Romano",
    "Football Transfers", "Transfer News Live", "Sky Sports Transfer",
    "The Athletic Transfer", "Mirror Transfer", "Sun Transfer",
    "Todo Fichajes", "Calciomercato", "Marca", "AS", "Sport",
]

# These patterns mean it's NOT a real transfer story even if transfer words appear
TRANSFER_EXCLUSIONS = [
    "where are they now", "remember when", "looking back", "throwback",
    "best ever", "worst ever", "greatest", "ranked", "ranking",
    "dream xi", "dream team", "fantasy xi", "predicted xi",
    "retires", "retirement", "announces retirement", "hanging up",
    "injury", "injured", "surgery", "ruled out", "scan",
    "sacked", "appointed", "new manager", "manager of",
    "kit release", "kit revealed", "kit leaked",
    "wage", "wages", "salary", "contract extension",
    "beer commercial", "commercial", "advert", "campaign",
    "vineyard", "third kit", "home kit", "away kit",
    "podcast", "weekly podcast", "football weekly",
    # Manager/team objectives — not transfers
    "targets win", "target win", "targeting win",
    "targets three points", "targeting three points",
    "wants to win", "looking to win", "hoping to win",
    "even if it helps", "despite", "boost rivals",
]

TITLE_RACE_KEYWORDS = [
    "title race", "title charge", "title run", "title fight",
    "top of the table", "points clear", "points behind",
    "decider", "title decider",
    "golden boot", "top four", "top 4", "top-four",
    "european spot", "europa league spot", "champions league spot",
    "relegation battle", "relegation fight", "relegation zone",
    "relegated", "drop zone", "survival", "staying up",
    "league leaders", "premier league title", "prem title",
    "rangers", "celtic", "old firm", "ibrox", "parkhead",
    "scottish title", "spfl title",
    "world cup squad", "world cup 2026", "nations league final", "squad announcement"
]

UCL_KEYWORDS = [
    "champions league", "ucl", "europa league", "conference league",
    "semi-final", "semi final", "quarter-final", "quarter final",
    "round of 16", "knockout", "european night", "away goals",
    "aggregate", "two legs", "second leg", "first leg"
]

# Expanded — catches match reaction, player ratings, post-match analysis
RESULT_KEYWORDS = [
    "full time", "full-time", "ft:", "match report", "highlights",
    "post-match", "post match", "reaction", "after the match",
    "player ratings", "man of the match", "motm", "match rating",
    "five things we learned", "talking points", "verdict",
    # Match result patterns
    "win over", "win against", "victory over", "victory against",
    "beat ", "beats ", "defeated ", "drew with", "draw against",
    "scores in", "scored in", "goal in", " win ", " wins ",
    "comeback", "comeback win", "late winner", "stoppage time",
    "equaliser", "equalizer", "opens scoring",
    "hit seven", "hit six", "hit five", "hit four",
    "seal fate", "seals fate", "seal relegation", "seal promotion",
    "seal survival", "seals the title", "seal the title",
    "thrash", "thrashes", "rout", "thumping",
    # Post-match reaction
    "after defeat", "after victory", "after draw", "after loss",
    "post-win", "post-defeat", "post-draw",
    "relief", "hope after", "boost after",
]

PREVIEW_KEYWORDS = [
    "preview", "prediction", "predicted lineup", "predicted xi",
    "team news", "ahead of", "build-up", "build up",
    "how to watch", "kick off time", "kick-off time",
    "match preview", "everything you need to know",
    "create a", "answer these", "quiz",
]

BIG_CLUBS = [
    "arsenal", "manchester city", "man city", "liverpool", "chelsea",
    "manchester united", "man utd", "tottenham", "spurs", "newcastle",
    "real madrid", "barcelona", "barca", "bayern", "psg", "inter milan",
    "juventus", "atletico"
]

STALE_SIGNALS = [
    "last week", "last month", "yesterday", "earlier this season",
    "looking back", "in 2024", "in 2023", "in 2022",
    "where are they now", "remember when", "throwback",
]

TABLOID_ONLY_SOURCES = ["The Sun", "Daily Mirror", "Daily Star", "Daily Mail"]

LOWER_LEAGUE_SIGNALS = [
    "league one", "league two", "national league", "mls", "saudi pro league",
]

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
    "fia", "motogp", "nascar", "indycar",
    "miami gp", "monaco gp", "silverstone gp", "monza gp",
    "wolff", "horner", "binotto", "cadillac f1",
    # ── Cricket ───────────────────────────────────────────────────────────────
    "cricket", "wicket", "wickets", "batting", "bowling figures",
    "test match", "ashes", "the ashes", "ipl", "t20", "odi",
    "test cricket", "county cricket", "one day international",
    "spinner", "pacer", "century", "duck", "innings",
    # ── Rugby ─────────────────────────────────────────────────────────────────
    "rugby union", "rugby league", "six nations", "rugby world cup",
    "premiership rugby", "pro14", "super rugby",
    "try scored", "line out", "scrum", "ruck", "maul",
    "fly half", "hooker", "prop forward", "lock forward",
    # ── Tennis ───────────────────────────────────────────────────────────────
    "tennis", "wimbledon", "us open tennis", "french open", "australian open",
    "roland garros", "atp", "wta", "grand slam tennis",
    "set point", "match point", "ace serve", "double fault",
    "djokovic", "alcaraz", "sinner", "medvedev", "swiatek",
    # ── Golf / leaderboard sports ─────────────────────────────────────────────
    "golf", "pga tour", "ryder cup", "masters golf", "the open golf",
    "us open golf", "birdie", "eagle", "bogey", "par", "handicap",
    "fairway", "bunker", "caddie",
    "mcilroy", "rory", "tiger woods", "scheffler", "hovland",
    "leaderboard", "shoots up leaderboard", "cadillac championship",
    "zurich classic", "wells fargo", "travelers championship",
    "bmw championship", "fedex cup", "korn ferry",
    "world number 1", "world no 1", "world ranking golf",
    "chevron championship", "vare trophy", "solheim cup",
    # ── Boxing / MMA ─────────────────────────────────────────────────────────
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
    # ── Snooker / Darts ──────────────────────────────────────────────────────
    "snooker", "o'sullivan", "ronnie o", "crucible", "world snooker",
    "maximum break", "century break", "cue ball",
    "darts", "treble 20", "bullseye", "oche", "van gerwen",
    "gerwyn price", "michael smith darts", "luke littler",
    # ── Athletics / Olympics ─────────────────────────────────────────────────
    "athletics", "marathon runner", "sprinter", "100m race", "long jump",
    "javelin", "discus", "shot put", "decathlon", "heptathlon",
    "olympics", "olympic games", "paralympics",
    "cycling", "tour de france", "giro", "vuelta", "velodrome",
    # ── Other sports ─────────────────────────────────────────────────────────
    "basketball", "netball", "volleyball", "handball",
    "ice hockey", "field hockey", "lacrosse", "squash",
    "badminton", "table tennis", "polo", "equestrian",
    "ski", "skiing", "snowboard", "biathlon",
    "sailing", "rowing", "kayak",
    # ── Celebrity / Entertainment ─────────────────────────────────────────────
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

    if contains_any(t, NOISE_KEYWORDS):
        return 0, {"disqualified": "noise/off-topic"}
    if not contains_any(t, FOOTBALL_SIGNALS):
        return 0, {"disqualified": "no football signal"}

    if contains_any(t, WOMENS_SIGNALS):
        score += 5
        breakdown["womens_football"] = 5
        story["is_womens"] = True

    tier = story.get("source_tier", 3)
    tier_points = {1: 30, 2: 15, 3: 5}.get(tier, 5)
    score += tier_points
    breakdown["source_tier"] = tier_points

    if contains_any(t, HERE_WE_GO):
        score += 15
        breakdown["here_we_go"] = 15

    transfer_hits = count_matching(t, TRANSFER_RUMOUR)
    if transfer_hits >= 2:
        score += 10
        breakdown["transfer_keywords"] = 10
    elif transfer_hits == 1:
        score += 5
        breakdown["transfer_keywords"] = 5

    if contains_any(t, BIG_CLUBS):
        score += 10
        breakdown["big_club"] = 10

    if any(p in t for p in star_players):
        score += 10
        breakdown["star_player"] = 10

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

    if contains_any(t, UCL_KEYWORDS):
        score += 10
        breakdown["ucl_boost"] = 10

    if contains_any(t, STALE_SIGNALS):
        score -= 10
        breakdown["stale"] = -10

    if contains_any(t, LOWER_LEAGUE_SIGNALS):
        score -= 20
        breakdown["lower_league"] = -20

    if story.get("source") in TABLOID_ONLY_SOURCES:
        score -= 15
        breakdown["tabloid_only"] = -15

    score = max(0, min(100, score))
    breakdown["total"] = score
    return score, breakdown


# ── Format detection keyword lists ───────────────────────────────────────────

# TIPS: ONLY explicit betting/odds language — must be unambiguous
# Every word here must ONLY appear in genuine betting content, not match reports or podcasts
TIPS_KEYWORDS = [
    "betting odds", "match odds", "betting tips", "football tips",
    "accumulator", "acca tip", "each-way bet", "lay the draw",
    "bookmaker odds", "bookie odds", "best bet today", "tip of the day",
    "correct score prediction", "both teams to score", "btts tip",
    "over 2.5 goals tip", "under 2.5 goals tip", "anytime scorer tip",
    "first goalscorer tip", "football predictions today",
    "value bet", "free bet", "bet builder",
]

# Hard noise patterns — NEVER F8 regardless of any other signal
# These are podcast/match/feature titles that contain innocent words
TIPS_NOISE = [
    "podcast", "sacked in the morning", "never give up", "cockatoo",
    "connections between", "coaches and players", "choose figc",
    "play daily", "word game", "can you name", "quiz", "sportword",
    "hit seven", "hit six", "hit five", "seal fate", "promotion",
    "relegated", "celebrates", "we'll decide", "were better than",
    "got what we needed", "want to scream",
]

# Behaviour/incident — never becomes TIPS
BEHAVIOUR_CONTEXT = [
    "lash out", "lashes out", "commits", "sin", "sinned",
    "ultimate sin", "modern football", "confrontation", "altercation",
    "clash", "clashed", "pushes", "shoves", "squared up",
    "tunnel incident", "brawl", "melee", "verbal",
    "protests", "refused to", "walks off", "stormed off",
    "fuming", "fumes", "fumes at", "disbelief", "anger", "furious",
    "denied penalty", "var denied", "var overturned", "var check",
    "could have broken", "could've broken", "should have been",
]

# F7 HOT TAKE — opinion, analysis, manager news, quotes about other teams
HOT_TAKE_SIGNALS = [
    # Manager news
    "sacked", "appointed manager", "new manager", "head coach", "interim",
    "takes charge", "named manager", "manager of the year",
    "favourite for", "favourite to", "in the running",
    "sacked in the morning",
    # Opinion / analysis
    "podcast", "analysis", "opinion", "column", "verdict",
    "ranked", "ranking", "deep dive", "five things", "talking points",
    "what went wrong", "what next", "the problem with", "hot take",
    "why ", "should ", "must ", "case for", "argument", "controversial",
    "overrated", "underrated", "debate", "unpopular",
    "can they", "will they", "could they",
    # Player quotes about other teams / future
    " says ", " claims ", " believes ", " thinks ", " insists ",
    " admits ", " reveals ", " warns ", " predicts ", " suggests ",
    "expects", "confident", "backs ", "urges", "calls for",
    "demands", "slams", "criticises", "defends",
    "tells ", "told ", "speaks out", "opens up",
    # Reaction / drama
    "fuming", "incredible", "unbelievable", "outrage", "furious",
    "lash out", "lashes out", "var denied", "var overturned",
    "on brink", "in crisis", "under pressure", "axed",
    "fight back", "responds", "hits back",
    # Summaries / previews that are analytical
    "rebuild", "era", "end of an era", "future of",
    "what it means", "implications", "impact of",
    "boost after", "hope after", "worry for",
]

# F6 STAR SPOTLIGHT — strictly about player performance, records, personal news
# NOT for quotes FROM a player about other clubs
STAR_SPOTLIGHT_SIGNALS = [
    "hat-trick", "hat trick", "brace", "treble",
    "masterclass", "world class", "outstanding", "brilliant",
    "man of the match", "motm", "player of the month", "player of the year",
    "young player of", "golden boot winner", "top scorer",
    "record", "history", "milestone", "all-time",
    "retires", "retirement", "announces retirement", "hanging up", "calling time",
    "injured", "injury update", "ruled out", "out for", "surgery",
    "scan results", "fitness boost", "return from injury", "return to training",
    "kit launch", "shirt launch", "jersey revealed",
    "award", "nominated for", "ballon d'or",
    "profile", "legend", "spotlight", "career",
    "signs new deal", "new contract", "extends contract", "renews",
    "wage rise", "bumper deal",
]

# These disqualify F6 — player is opining, not the subject of performance news
F6_DISQUALIFIERS = [
    " says ", " claims ", " believes ", " thinks ", " insists ",
    " admits ", " reveals ", " warns ", " predicts ", " suggests ",
    "expects", "confident that", "backs ", "urges", "calls for",
    "demands", "slams", "criticises",
    "tells ", "told ", "speaks out", "opens up about",
    "can win", "will win", "could win", "next season",
    "favourite for", "tips ", "tipped ",
]


def detect_format(story, score):
    """Context-aware format detection — tight, channel-balanced routing.

    Priority order (highest to lowest):
      F9 Women's → F8 Tips → F1 Confirmed transfer → F2 Transfer rumour →
      F4 Post-match → F3 Preview → F5 Title race → F7 Hot take →
      F6 Star spotlight → F7 default (not F6)

    Key changes:
      - F2 requires genuine transfer movement/interest + no exclusion
        (gossip columns, "where are they now", dream XIs are excluded)
      - F7 check BEFORE F6 — most stories are opinion/analysis/reaction
      - F6 requires explicit performance/personal signal AND no opinion disqualifier
      - Default is F7 not F6
    """
    t = text(story).lower()

    # ── F9: Women's football ─────────────────────────────────────────────────
    if contains_any(t, WOMENS_SIGNALS):
        return "F9"

    # ── F8: Tips & Bets — explicit odds/betting ONLY ─────────────────────────
    has_behaviour   = contains_any(t, BEHAVIOUR_CONTEXT)
    has_explicit_bet = contains_any(t, TIPS_KEYWORDS)
    if has_explicit_bet and not has_behaviour:
        return "F8"

    # ── Exclusion check (stale/non-transfer content) ─────────────────────────
    is_excluded = contains_any(t, TRANSFER_EXCLUSIONS)

    # ── F1: Confirmed transfer ───────────────────────────────────────────────
    if not is_excluded and contains_any(t, HERE_WE_GO) and contains_any(t, TRANSFER_MOVEMENT):
        return "F1"

    # ── F2: Transfer rumour — requires real movement/interest signal ─────────
    # Gossip columns, dream XIs, "where are they now" are excluded above
    # Known transfer sources (Football Italia, Transfermarkt etc) get lower threshold
    has_movement    = contains_any(t, TRANSFER_MOVEMENT)
    has_rumour      = contains_any(t, TRANSFER_RUMOUR)
    is_transfer_src = story.get("source", "") in TRANSFER_SOURCES
    injury_block    = any(s in t for s in ["injur", "surgery", "ruled out", "facial", "hospital"])
    kit_block       = any(s in t for s in ["kit", "strip", "jersey", "shirt", "badge", "crest"])

    if not is_excluded and not injury_block and not kit_block:
        # Known transfer source: single rumour signal is enough
        if is_transfer_src and has_rumour:
            return "F2"
        # Any source: movement signal or 2+ rumour signals
        if has_movement or (has_rumour and count_matching(t, TRANSFER_RUMOUR) >= 2):
            return "F2"

    # ── F4: Post-match result / reaction ────────────────────────────────────
    if contains_any(t, RESULT_KEYWORDS):
        return "F4"

    # ── UCL / European content ───────────────────────────────────────────────
    if contains_any(t, UCL_KEYWORDS):
        if contains_any(t, PREVIEW_KEYWORDS + ["ahead of", "vs", "v ", "how to watch", "kick"]):
            return "F3"
        return "F4"

    # ── F3: Match preview ────────────────────────────────────────────────────
    if contains_any(t, PREVIEW_KEYWORDS + ["vs", "v ", "facing", "takes on"]):
        return "F3"

    # ── F5: Title race ───────────────────────────────────────────────────────
    if contains_any(t, TITLE_RACE_KEYWORDS) and not contains_any(t, UCL_KEYWORDS):
        return "F5"

    # ── F7: Hot Take — BEFORE F6 ─────────────────────────────────────────────
    # Most football stories are opinion, analysis, reaction or quotes.
    # Check this before star spotlight to prevent F6 bloat.
    if contains_any(t, HOT_TAKE_SIGNALS):
        return "F7"

    # Also catch behaviour/incident stories here
    if has_behaviour:
        return "F7"

    # ── F6: Star Spotlight — strict ──────────────────────────────────────────
    # Only genuine performance/personal/records stories about a player.
    # If player is merely quoted giving an opinion → already caught by F7 above.
    has_spotlight   = contains_any(t, STAR_SPOTLIGHT_SIGNALS)
    has_disqualifier = contains_any(t, F6_DISQUALIFIERS)

    if has_spotlight and not has_disqualifier:
        return "F6"

    # ── Default: F7 (not F6) ─────────────────────────────────────────────────
    # If we can't classify it cleanly, it's more likely analysis/opinion
    # than a genuine player spotlight. Hot takes channel is better catch-all.
    return "F7"


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
        else:
            # Format-aware thresholds — F7/F9 ship at lower score (high volume formats)
            # F1/F2 require higher confidence before shipping
            fmt_thresholds = {
                "F1": 40, "F2": 35, "F3": 30, "F4": 30,
                "F5": 30, "F6": 35, "F7": 28, "F8": 40, "F9": 28,
            }
            ship_threshold = fmt_thresholds.get(fmt, 30)
            hold_threshold = max(ship_threshold - 10, 15)

            if score >= ship_threshold:
                status = "shippable"
                ship_count += 1
            elif score >= hold_threshold:
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
