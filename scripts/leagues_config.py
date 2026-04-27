"""TheSportsDB league IDs we cover for image lookups.

League IDs verified at https://www.thesportsdb.com/api/v1/json/{key}/all_leagues.php
or by browsing https://www.thesportsdb.com/league/{id}-{name}

Keep this list focused on leagues whose teams will appear in 90minWaffle
and StatiqFC content. Adding a league = one line + a refresh run.
"""

LEAGUES = [
    # English football pyramid
    {"id": "4328", "name": "English Premier League",         "tier": "england-1"},
    {"id": "4329", "name": "English League Championship",    "tier": "england-2"},
    {"id": "4396", "name": "English League 1",               "tier": "england-3"},
    {"id": "4397", "name": "English League 2",               "tier": "england-4"},

    # Top European leagues
    {"id": "4335", "name": "Spanish La Liga",                "tier": "spain-1"},
    {"id": "4331", "name": "German Bundesliga",              "tier": "germany-1"},
    {"id": "4332", "name": "Italian Serie A",                "tier": "italy-1"},
    {"id": "4334", "name": "French Ligue 1",                 "tier": "france-1"},
    {"id": "4337", "name": "Dutch Eredivisie",               "tier": "netherlands-1"},
    {"id": "4344", "name": "Portuguese Primeira Liga",       "tier": "portugal-1"},
    {"id": "4330", "name": "Scottish Premiership",           "tier": "scotland-1"},
    {"id": "4346", "name": "American Major League Soccer",   "tier": "usa-1"},

    # UEFA / international club competitions
    {"id": "4480", "name": "UEFA Champions League",          "tier": "uefa-cl"},
    {"id": "4481", "name": "UEFA Europa League",             "tier": "uefa-el"},
    {"id": "5071", "name": "UEFA Europa Conference League",  "tier": "uefa-ecl"},

    # English domestic cups
    {"id": "4482", "name": "FA Cup",                         "tier": "england-cup"},
    {"id": "4483", "name": "EFL Cup",                        "tier": "england-lcup"},
]
