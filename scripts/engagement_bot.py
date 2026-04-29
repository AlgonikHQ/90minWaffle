import os, random, logging, requests
from datetime import datetime, timezone
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

LOG_PATH = "/root/90minwaffle/logs/engagement_bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

DISCORD_GENERAL    = os.getenv("DISCORD_WEBHOOK_GENERAL")
DISCORD_HOT_TAKES  = os.getenv("DISCORD_WEBHOOK_HOT_TAKES")
DISCORD_MATCH_DAY  = os.getenv("DISCORD_WEBHOOK_MATCH_DAY")
DISCORD_PL         = os.getenv("DISCORD_WEBHOOK_PREMIER_LEAGUE")

def post_embed(webhook, embed):
    if not webhook:
        log.warning("No webhook configured")
        return False
    try:
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=15)
        log.info("Posted embed: " + str(r.status_code))
        return r.status_code in (200, 204)
    except Exception as e:
        log.error("Post failed: " + str(e))
        return False

# ── Content banks ────────────────────────────────────────────────────────────

GUESS_PLAYERS = [
    {"clues": ["Born in Senegal", "Played for Southampton before Liverpool", "All-time Premier League top scorer"], "answer": "Mohamed Salah", "hint": "Egyptian King"},
    {"clues": ["Norwegian striker", "Scored 36 PL goals in debut season", "Son of a former Premier League player"], "answer": "Erling Haaland", "hint": "Man City No.9"},
    {"clues": ["French right back", "Won the World Cup in 2018", "Moved from Bayern to Liverpool in 2024"], "answer": "Alphonso Davies", "hint": "Left back, not right"},
    {"clues": ["Spanish midfielder", "Ballon d Or winner 2023", "Plays for Manchester City"], "answer": "Rodri", "hint": "The engine room"},
    {"clues": ["English winger", "Arsenal academy product", "Scored 16 goals in 2023/24 PL season"], "answer": "Bukayo Saka", "hint": "Mr Arsenal"},
    {"clues": ["Brazilian forward", "Real Madrid galactico", "Champions League top scorer 2023/24"], "answer": "Vinicius Jr", "hint": "Left winger, loves to dance"},
    {"clues": ["German midfielder", "Won everything at Bayern", "Joined Real Madrid on a free in 2024"], "answer": "Toni Kroos", "hint": "Came out of retirement"},
    {"clues": ["English striker", "All-time top scorer for England", "Won the Bundesliga with Bayern"], "answer": "Harry Kane", "hint": "Never won a trophy... until now?"},
    {"clues": ["Spanish teenager", "Barcelona winger", "Broke into the Spain squad at 16"], "answer": "Lamine Yamal", "hint": "The new Messi?"},
    {"clues": ["Belgian forward", "Retired from international football 2023", "Three stints in Premier League"], "answer": "Eden Hazard", "hint": "What could have been"},
    {"clues": ["Argentine manager", "Won the Premier League with unexpected club", "Known for high pressing style"], "answer": "Pep Guardiola", "hint": "Has a PhD in winning"},
    {"clues": ["Dutch manager", "Took over Liverpool in 2024", "Previously at Feyenoord"], "answer": "Arne Slot", "hint": "Klopp's successor"},
    {"clues": ["Portuguese forward", "Left Man Utd in 2022", "Plays in Saudi Arabia"], "answer": "Cristiano Ronaldo", "hint": "SIUUUU"},
    {"clues": ["French striker", "PSG captain", "Joined Real Madrid in 2024"], "answer": "Kylian Mbappe", "hint": "The fastest in the world"},
    {"clues": ["Spanish goalkeeper", "Best in the world 2023", "Plays for Barcelona"], "answer": "Marc-Andre ter Stegen", "hint": "Wait... injured all season"},
]

DID_YOU_KNOW = [
    {"fact": "Shearer scored 260 Premier League goals — a record that still stands 18 years after his retirement.", "emoji": "⚽"},
    {"fact": "Leicester City won the Premier League in 2015/16 at odds of 5000/1. Bookmakers paid out over £25 million.", "emoji": "🏆"},
    {"fact": "Cristiano Ronaldo has scored against 700+ different goalkeepers in his professional career.", "emoji": "🎯"},
    {"fact": "The fastest goal in Premier League history was scored by Shane Long — 7.69 seconds after kick-off in 2019.", "emoji": "⚡"},
    {"fact": "Arsenal went 49 league games unbeaten between 2003 and 2004. No PL team has come close since.", "emoji": "🔴"},
    {"fact": "Haaland scored 36 Premier League goals in his debut season (2022/23) — breaking the record by 5.", "emoji": "🇳🇴"},
    {"fact": "The 2005 Champions League final — Liverpool 3-3 AC Milan — is the only final to go from 0-3 down to penalties.", "emoji": "🏅"},
    {"fact": "Real Madrid have won the Champions League 15 times — more than any other club by a distance.", "emoji": "🏆"},
    {"fact": "Messi won the Ballon d Or 8 times. The next highest is Ronaldo with 5.", "emoji": "🐐"},
    {"fact": "The 2022 World Cup final between Argentina and France is widely considered the greatest final ever played.", "emoji": "🌍"},
    {"fact": "Peter Schmeichel went an entire 1995/96 Premier League season without being beaten at home.", "emoji": "🧤"},
    {"fact": "Paolo Maldini played for AC Milan for 25 years — from 1985 to 2009 — all for one club.", "emoji": "🔴🖤"},
    {"fact": "The fastest hat-trick in World Cup history was scored by Hungary vs El Salvador in 1982 — 7 minutes.", "emoji": "🎩"},
    {"fact": "Nottingham Forest were European champions in 1979 AND 1980 — less than 10 years after being in the second division.", "emoji": "🌳"},
    {"fact": "Only 8 clubs have ever won the Premier League since it began in 1992.", "emoji": "📊"},
    {"fact": "Thierry Henry holds the record for most Premier League Player of the Season awards — winning it 3 times.", "emoji": "🇫🇷"},
    {"fact": "The largest victory in World Cup history was Australia 31-0 American Samoa in 2001.", "emoji": "😳"},
    {"fact": "Frank Lampard scored 211 goals for Chelsea — an extraordinary number for a central midfielder.", "emoji": "💙"},
]

ON_THIS_DAY = [
    {"month": 4, "day": 29, "event": "In 1953, Hungary became the first team to beat England at Wembley, winning 6-3.", "emoji": "📅"},
    {"month": 5, "day": 6,  "event": "In 2012, Manchester City won the Premier League on goal difference on the final day — Aguerooooo.", "emoji": "📅"},
    {"month": 5, "day": 25, "event": "In 2005, Liverpool won the Champions League in Istanbul, coming back from 3-0 down against AC Milan.", "emoji": "📅"},
    {"month": 4, "day": 26, "event": "In 1989, Arsenal won the title at Anfield in the last minute of the season — Michael Thomas.", "emoji": "📅"},
    {"month": 5, "day": 29, "event": "In 1985, the Heysel Stadium disaster occurred before the European Cup final, killing 39 supporters.", "emoji": "📅"},
    {"month": 6, "day": 25, "event": "In 1998, David Beckham was sent off vs Argentina at the World Cup — sparking national outrage.", "emoji": "📅"},
]

WEEKLY_POLLS = {
    0: [  # Monday
        "Who will win the Champions League this season?",
        "Is the Premier League the best league in the world?",
        "Should VAR be scrapped entirely?",
    ],
    1: [  # Tuesday — UCL night
        "Best team left in the Champions League?",
        "Will an English club win the UCL this season?",
        "Mbappe or Vinicius — who has been better this season?",
    ],
    2: [  # Wednesday — UCL night
        "Can Arsenal win the Champions League?",
        "Best manager in Europe right now?",
        "Who will be Ballon d Or 2025?",
    ],
    3: [  # Thursday
        "Most overrated player in the Premier League?",
        "Best young player in Europe right now?",
        "Should clubs be able to loan players mid-season?",
    ],
    4: [  # Friday — weekend build-up
        "Your prediction for this weekend?",
        "Who scores first this weekend?",
        "Biggest game of the weekend?",
    ],
    5: [  # Saturday — match day
        "Match of the Day rating: who impressed you most?",
        "Best goal of the weekend so far?",
        "Shock result incoming this weekend?",
    ],
    6: [  # Sunday
        "Player of the weekend?",
        "Manager of the month for April?",
        "Which club has the best squad depth in the PL?",
    ],
}

FOOTBALL_TRIVIA = [
    {"q": "How many times have Liverpool won the European Cup/Champions League?", "a": "6 times — 1977, 1978, 1981, 1984, 2005, 2019"},
    {"q": "Who holds the record for most goals in a single World Cup?", "a": "Just Fontaine — 13 goals for France at the 1958 World Cup"},
    {"q": "Which club has the most Premier League titles?", "a": "Manchester United with 13"},
    {"q": "Who was the first player to score 100 Premier League goals?", "a": "Alan Shearer — in 1999"},
    {"q": "How many teams are in the Champions League group stage?", "a": "36 teams from the 2024/25 season (expanded format)"},
    {"q": "Which country has won the most World Cups?", "a": "Brazil — 5 times (1958, 1962, 1970, 1994, 2002)"},
    {"q": "What is the record transfer fee paid?", "a": "Neymar to PSG in 2017 — £198 million"},
    {"q": "Who scored the fastest Champions League goal?", "a": "Roy Makaay — 10.2 seconds for Bayern vs Real Madrid in 2007"},
]

# ── Post functions ────────────────────────────────────────────────────────────

def post_guess_player():
    p = random.choice(GUESS_PLAYERS)
    clues = chr(10).join(["• " + c for c in p["clues"]])
    embed = {
        "author": {"name": "🕵️  GUESS THE PLAYER"},
        "title": "Who am I?",
        "description": clues + chr(10) + chr(10) + "💡 Hint: " + p["hint"] + chr(10) + chr(10) + "Reply with your answer below 👇",
        "color": 0x1ABC9C,
        "footer": {"text": "Answer revealed in the next post | 90minWaffle"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_GENERAL, embed)

def post_guess_answer():
    p = random.choice(GUESS_PLAYERS)
    embed = {
        "author": {"name": "✅  ANSWER REVEALED"},
        "title": "The answer was: " + p["answer"],
        "color": 0x2ECC71,
        "footer": {"text": "90minWaffle | New puzzle coming soon"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_GENERAL, embed)

def post_did_you_know():
    fact = random.choice(DID_YOU_KNOW)
    embed = {
        "author": {"name": fact["emoji"] + "  DID YOU KNOW?"},
        "description": "**" + fact["fact"] + "**",
        "color": 0x9B59B6,
        "footer": {"text": "90minWaffle | Football facts daily"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_GENERAL, embed)

def post_on_this_day():
    now = datetime.now(timezone.utc)
    matches = [e for e in ON_THIS_DAY if e["month"] == now.month and e["day"] == now.day]
    if not matches:
        return
    event = matches[0]
    embed = {
        "author": {"name": "📅  ON THIS DAY IN FOOTBALL"},
        "description": "**" + event["event"] + "**",
        "color": 0xF39C12,
        "footer": {"text": "90minWaffle | Football history"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_GENERAL, embed)

def post_daily_poll():
    now = datetime.now(timezone.utc)
    weekday = now.weekday()
    pool = WEEKLY_POLLS.get(weekday, WEEKLY_POLLS[0])
    question = random.choice(pool)
    embed = {
        "author": {"name": "🗳️  COMMUNITY POLL"},
        "title": question,
        "description": "React with your answer below!" + chr(10) + chr(10) + "🟢 Agree / Yes" + chr(10) + "🔴 Disagree / No",
        "color": 0xFF4500,
        "footer": {"text": "90minWaffle | Drop your take in the comments"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_HOT_TAKES, embed)

def post_trivia():
    t = random.choice(FOOTBALL_TRIVIA)
    embed = {
        "author": {"name": "🧠  FOOTBALL TRIVIA"},
        "title": t["q"],
        "description": "Think you know the answer?" + chr(10) + chr(10) + "||" + t["a"] + "||",
        "color": 0x3498DB,
        "footer": {"text": "90minWaffle | Click the spoiler to reveal"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_GENERAL, embed)

def post_weekend_preview():
    now = datetime.now(timezone.utc)
    if now.weekday() not in (4, 5):
        return
    embed = {
        "author": {"name": "⚽  WEEKEND FOOTBALL IS HERE"},
        "title": "What are you watching this weekend?",
        "description": "Drop your predictions below 👇" + chr(10) + chr(10) + "• Biggest upset?" + chr(10) + "• Top scorer?" + chr(10) + "• Match of the day?",
        "color": 0x4361EE,
        "footer": {"text": "90minWaffle | Football. Hot takes. No filter."},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_MATCH_DAY, embed)

def post_monday_motivation():
    now = datetime.now(timezone.utc)
    if now.weekday() != 0:
        return
    quotes = [
        "Football is not just a game. It is a way of life. — Pele",
        "Some people believe football is a matter of life and death. I am very disappointed with that attitude. I can assure you it is much, much more important than that. — Bill Shankly",
        "You have to fight to reach your dream. You have to sacrifice and work hard for it. — Lionel Messi",
        "The more difficult the victory, the greater the happiness in winning. — Pele",
        "I learned all about life with a ball at my feet. — Ronaldinho",
    ]
    quote = random.choice(quotes)
    parts = quote.rsplit(" — ", 1)
    text = parts[0]
    author = parts[1] if len(parts) > 1 else "Football"
    embed = {
        "author": {"name": "💬  MONDAY FOOTBALL QUOTE"},
        "description": "**"" + text + ""**" + chr(10) + chr(10) + "— *" + author + "*",
        "color": 0xE9C46A,
        "footer": {"text": "90minWaffle | New week, new football"},
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    post_embed(DISCORD_GENERAL, embed)

# ── Scheduler ─────────────────────────────────────────────────────────────────

scheduler = BlockingScheduler(timezone="UTC")

# Daily poll — 12:00 UTC every day
scheduler.add_job(post_daily_poll, "cron", hour=12, minute=0)

# Did you know — 09:00 UTC every day
scheduler.add_job(post_did_you_know, "cron", hour=9, minute=0)

# Guess the player — Tue and Thu at 18:00 UTC
scheduler.add_job(post_guess_player, "cron", day_of_week="tue,thu", hour=18, minute=0)

# Trivia — Mon, Wed, Fri at 15:00 UTC
scheduler.add_job(post_trivia, "cron", day_of_week="mon,wed,fri", hour=15, minute=0)

# On this day — 08:00 UTC every day (only posts if match found)
scheduler.add_job(post_on_this_day, "cron", hour=8, minute=0)

# Weekend preview — Fri and Sat at 10:00 UTC
scheduler.add_job(post_weekend_preview, "cron", day_of_week="fri,sat", hour=10, minute=0)

# Monday motivation — Mon at 07:30 UTC
scheduler.add_job(post_monday_motivation, "cron", day_of_week="mon", hour=7, minute=30)

if __name__ == "__main__":
    log.info("Starting engagement bot scheduler...")
    log.info("Schedule: Daily poll 12:00 | Did you know 09:00 | Guess player Tue/Thu 18:00 | Trivia Mon/Wed/Fri 15:00 | On this day 08:00 | Weekend preview Fri/Sat 10:00 | Monday motivation Mon 07:30")
    scheduler.start()
