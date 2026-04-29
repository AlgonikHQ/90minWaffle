import os, random, logging, requests
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from discord_poster import post_poll, WEBHOOKS

load_dotenv("/root/90minwaffle/.env")

LOG_PATH = "/root/90minwaffle/logs/engagement_bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# Example engagement content
GUESS_PLAYERS = [
    {
        "clues": [
            "Played in Serie A and Premier League",
            "Over 100 career goals",
            "Won a league title"
        ],
        "answer": "Edin Džeko"
    },
    {
        "clues": [
            "Ex-Arsenal + Chelsea midfielder",
            "Known for long shots",
            "Retired in 2022"
        ],
        "answer": "Cesc Fàbregas"
    }
]

DAILY_POLLS = [
    "Who’s been the best winger this season?",
    "Should offside VAR be scrapped?",
    "Is Arsenal a real title contender next year?"
]

scheduler = BlockingScheduler()

def post_guess_player():
    q = random.choice(GUESS_PLAYERS)
    clues = "\n".join([f"• {c}" for c in q["clues"]])
    embed = {
        "author": {"name": "🕵️ Guess The Player"},
        "title": "Can you identify this player?",
        "description": f"{clues}\n\nAnswer revealed in 1 hour 👀",
        "color": 0x1ABC9C,
        "timestamp": datetime.utcnow().isoformat()
    }
    webhook = WEBHOOKS["general"]
    r = requests.post(webhook, json={"embeds": [embed]})
    log.info(f"Guess Player posted: {r.status_code}")

def post_daily_poll():
    q = random.choice(DAILY_POLLS)
    story = {"winning_hook": q, "title": q}
    post_poll(story, "hot_takes")

scheduler.add_job(post_daily_poll, "interval", hours=6)
scheduler.add_job(post_guess_player, "interval", hours=12)

if __name__ == "__main__":
    log.info("Starting engagement bot scheduler…")
    scheduler.start()
