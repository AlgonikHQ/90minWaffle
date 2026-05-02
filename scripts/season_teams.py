"""
season_teams.py — Single source of truth for division membership and competition keywords.
Update PREMIER_LEAGUE / CHAMPIONSHIP / SCOTTISH_PREMIERSHIP each August at season start.
Competition keyword lists below do NOT need seasonal updates.
Last updated: May 2026 — reflects 2025-26 season.
"""

# ── Premier League 2025-26 ─────────────────────────────────────────────────
PREMIER_LEAGUE = {
    "arsenal", "manchester city", "man city", "manchester united", "man utd",
    "man united", "liverpool", "aston villa", "brentford", "brighton",
    "bournemouth", "chelsea", "fulham", "everton", "sunderland", "newcastle",
    "crystal palace", "leeds", "leeds united", "nottingham forest", "forest",
    "west ham", "tottenham", "spurs", "burnley", "wolverhampton", "wolves",
}

# ── Championship 2025-26 ───────────────────────────────────────────────────
CHAMPIONSHIP = {
    "birmingham", "birmingham city", "blackburn", "blackburn rovers",
    "bristol city", "charlton", "charlton athletic", "coventry", "coventry city",
    "derby", "derby county", "hull", "hull city", "ipswich", "ipswich town",
    "leicester", "leicester city", "middlesbrough", "boro", "millwall",
    "norwich", "norwich city", "oxford", "oxford united", "portsmouth",
    "preston", "preston north end", "qpr", "queens park rangers",
    "sheffield united", "sheffield wednesday", "sheff wed", "sheff utd",
    "southampton", "stoke", "stoke city", "swansea", "swansea city",
    "watford", "west brom", "west bromwich", "west bromwich albion",
    "wrexham",
}

# ── Scottish Premiership 2025-26 ───────────────────────────────────────────
SCOTTISH_PREMIERSHIP = {
    "aberdeen", "celtic", "dundee", "dundee united", "falkirk",
    "hearts", "heart of midlothian", "hibernian", "hibs",
    "kilmarnock", "livingston", "motherwell", "rangers", "st mirren",
}

# ══════════════════════════════════════════════════════════════════════════
# COMPETITION KEYWORDS — do not need seasonal updates
# ══════════════════════════════════════════════════════════════════════════

# ── Women's football ───────────────────────────────────────────────────────
# Checked FIRST in classifier — keeps women's UCL out of #european-cups
WOMENS_KEYWORDS = [
    "wsl", "women's super league", "womens super league",
    "nwsl", "women's world cup", "womens world cup",
    "women's champions league", "womens champions league",
    "women's euro", "womens euro", "lionesses",
    "women's football", "womens football",
    "fa women", "barclays women",
    "women's fa cup", "womens fa cup",
    "women's league cup", "womens league cup",
]

# ── English domestic trophies — HARDLINED, English only ───────────────────
# Every keyword here MUST be English-specific.
# No foreign cup names. No generic "cup" alone. No "league cup" without context.
# Adding a keyword here means ANY story containing it goes to #domestic-trophies.
DOMESTIC_TROPHIES_KEYWORDS = [
    # FA Cup — all common references
    "fa cup",
    "emirates fa cup",
    "fa cup third round", "fa cup fourth round", "fa cup fifth round",
    "fa cup quarter-final", "fa cup semi-final", "fa cup final",
    "fa cup draw", "fa cup replay",

    # Carabao Cup / EFL Cup / League Cup — all historical sponsor names
    "carabao cup",
    "efl cup",
    "league cup",          # generic but almost always English in context
    "football league cup",
    "carabao cup draw", "carabao cup final", "carabao cup semi",
    "efl cup draw", "efl cup final",
    "league cup draw", "league cup final", "league cup semi",
    "milk cup",            # historical name (80s)
    "rumbelows cup",       # historical name (90s)
    "worthington cup",     # historical name (late 90s/2000s)
    "carling cup",         # historical name (2000s)

    # Community Shield / Charity Shield
    "community shield",
    "fa community shield",
    "charity shield",
    "fa charity shield",

    # FA Trophy — semi-pro non-league (tiers 5-8)
    "fa trophy",
    "isuzu fa trophy",
    "fa challenge trophy",

    # FA Vase — amateur non-league (tiers 9-10)
    "fa vase",
    "isuzu fa vase",
    "fa challenge vase",
]

# ── Scottish football ──────────────────────────────────────────────────────
SCOTTISH_COMP_KEYWORDS = [
    "scottish premiership", "spfl", "scottish premier",
    "william hill premiership",
    "scottish cup", "scottish fa cup",
    "scottish league cup", "league cup scotland",
    "viaplay cup",          # current Scottish League Cup sponsor name
    "hampden",
    "scotland national", "scotland vs", "vs scotland",
    "scotland international",
]

SCOTTISH_SOURCES = [
    "bbc scotland", "the scotsman", "daily record", "scottish sun",
]

# ── European club cups ─────────────────────────────────────────────────────
# Clubs only — women's UCL caught before this by WOMENS_KEYWORDS
EUROPEAN_CUPS_KEYWORDS = [
    "champions league", "uefa champions", "ucl",
    "europa league", "uefa europa", "uel",
    "conference league", "uecl", "europa conference",
    "club world cup", "fifa club world cup",
    "intercontinental cup",
]

# ── World Cup ─────────────────────────────────────────────────────────────
WORLD_CUP_KEYWORDS = [
    "world cup",
    "fifa world cup",
    "world cup qualifier", "world cup qualifying",
    "world cup 2026", "world cup 2030", "world cup 2034",
]

# ── Euros / Nations League ────────────────────────────────────────────────
EUROS_KEYWORDS = [
    "euro 2024", "euro 2028", "euro 2032",
    "euros qualifier", "euros qualifying",
    "european championship",
    "uefa european championship",
    "nations league",
    "uefa nations league",
]

# ── Championship competition keywords ─────────────────────────────────────
# Used as PRIMARY signal — team names only used as SECONDARY fallback
CHAMPIONSHIP_COMP_KEYWORDS = [
    "efl championship",
    "sky bet championship",
    "championship table",
    "championship top scorer",
    "championship play-off", "championship playoff",
    "championship promotion", "championship relegation",
]
