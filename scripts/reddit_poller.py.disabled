import requests
import sqlite3
import hashlib
import logging
import json
from datetime import datetime, timezone

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/reddit_poller.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "90minWaffle/1.0 (football content bot; contact@90minwaffle.com)"}

SOURCES = [
    {
        "name": "r/soccer HereWeGo",
        "url": "https://www.reddit.com/r/soccer/search.json?q=flair%3A%22Here+We+Go%22&sort=new&limit=25&restrict_sr=1",
        "tier": 1,
        "min_score": 50,
    },
    {
        "name": "r/soccer Confirmed",
        "url": "https://www.reddit.com/r/soccer/search.json?q=flair%3A%22Transfer+Confirmed%22&sort=new&limit=15&restrict_sr=1",
        "tier": 1,
        "min_score": 30,
    },
    {
        "name": "r/PremierLeague",
        "url": "https://www.reddit.com/r/PremierLeague/new.json?limit=25",
        "tier": 2,
        "min_score": 100,
    },
    {
        "name": "r/soccer Hot",
        "url": "https://www.reddit.com/r/soccer/hot.json?limit=25",
        "tier": 2,
        "min_score": 500,
    },
]

NOISE_KEYWORDS = [
    "women", "wsl", "nwsl", "uwcl", "lionesses", "female",
    "nfl", "nba", "mlb", "rugby", "cricket", "tennis",
    "fan art", "oc:", "[oc]", "photo:", "highlight:", "gif:",
    "daily discussion", "match thread", "post match"
]

def get_db():
    return sqlite3.connect(DB_PATH)

def make_guid(url, title):
    raw = url if url else title
    return "reddit_" + hashlib.sha256(raw.encode()).hexdigest()

def is_noise(title):
    t = title.lower()
    return any(kw in t for kw in NOISE_KEYWORDS)

def story_exists(c, guid):
    c.execute("SELECT id FROM stories WHERE guid=?", (guid,))
    return c.fetchone() is not None

def poll_source(source):
    log.info(f"Polling [{source['name']}]")
    try:
        r = requests.get(source["url"], headers=HEADERS, timeout=10)
        if r.status_code != 200:
            log.warning(f"  HTTP {r.status_code}")
            return 0

        data = r.json()
        posts = data.get("data", {}).get("children", [])
        conn = get_db()
        c = conn.cursor()
        new_count = 0

        for post in posts:
            d = post.get("data", {})
            title     = d.get("title", "").strip()
            url       = f"https://reddit.com{d.get('permalink','')}"
            score     = d.get("score", 0)
            created   = d.get("created_utc", 0)
            flair     = d.get("link_flair_text", "")
            subreddit = d.get("subreddit", "")

            if not title or score < source["min_score"]:
                continue
            if is_noise(title):
                continue

            guid = make_guid(url, title)
            if story_exists(c, guid):
                continue

            published = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()

            # Here We Go gets automatic tier 1 boost
            tier = source["tier"]
            if "here we go" in title.lower() or flair == "Here We Go":
                tier = 1

            c.execute('''
                INSERT OR IGNORE INTO stories
                (guid, title, url, source, source_tier, published_at, status)
                VALUES (?,?,?,?,?,?,'new')
            ''', (guid, title, url, f"Reddit/{subreddit}", tier, published))

            new_count += 1
            log.info(f"  NEW [{score}pts] {title[:75]}")

        conn.commit()
        conn.close()
        log.info(f"  Done — {new_count} new from {source['name']}")
        return new_count

    except Exception as e:
        log.error(f"  FAIL [{source['name']}]: {e}")
        return 0

def poll_all():
    log.info("=== Reddit Poll cycle starting ===")
    total = 0
    for source in SOURCES:
        total += poll_source(source)
        import time; time.sleep(2)  # Respect Reddit rate limits
    log.info(f"=== Reddit poll complete — {total} new stories ===")
    return total

if __name__ == "__main__":
    poll_all()
