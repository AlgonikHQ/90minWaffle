import feedparser
import sqlite3
import hashlib
import logging
from datetime import datetime, timezone

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/rss_poller.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ── RSS source stack ───────────────────────────────────────────────────────
# Removed: 90min (avg score 5.3, 0 published — pure noise)
# Removed: BBC Championship (avg 16.9, 0 published — covered by BBC Sport Football)
# Added:   BBC Women's Football (direct WSL/Lionesses feed for F9 content)
# Added:   The Athletic Football (high quality long-form, tier 1)
# Kept:    BBC World Cup (World Cup 2026 prep content)

RSS_SOURCES = [
    # ── Tier 1 ────────────────────────────────────────────────────────────
    {"name": "BBC Sport Football",    "url": "https://feeds.bbci.co.uk/sport/football/rss.xml",               "tier": 1},
    {"name": "Sky Sports Football",   "url": "https://www.skysports.com/rss/12040",                            "tier": 1},
    {"name": "BBC European Football", "url": "https://feeds.bbci.co.uk/sport/football/european/rss.xml",       "tier": 1},
    {"name": "BBC World Cup",         "url": "https://feeds.bbci.co.uk/sport/football/world-cup/rss.xml",      "tier": 1},
    {"name": "BBC Women's Football",  "url": "https://feeds.bbci.co.uk/sport/football/womens/rss.xml",         "tier": 1},
    # ── Tier 2 ────────────────────────────────────────────────────────────
    {"name": "Guardian Football",     "url": "https://www.theguardian.com/football/rss",                       "tier": 2},
    {"name": "Football365",           "url": "https://www.football365.com/feed",                               "tier": 2},
    {"name": "Football Italia",       "url": "https://www.football-italia.net/rss.xml",                        "tier": 2},
    {"name": "Planet Football",       "url": "https://www.planetfootball.com/feed/",                           "tier": 2},
    {"name": "Transfermarkt News",    "url": "https://www.transfermarkt.co.uk/aktuell/newsticker/news/1",      "tier": 2},
    {"name": "ESPN FC",               "url": "https://www.espn.co.uk/espn/rss/football/news",                  "tier": 2},
]

def get_db():
    return sqlite3.connect(DB_PATH)

def make_guid(url, title):
    raw = url if url else title
    return hashlib.sha256(raw.encode()).hexdigest()

def parse_date(entry):
    for attr in ["published_parsed", "updated_parsed"]:
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
    return datetime.now(timezone.utc).isoformat()

def story_exists(c, guid):
    c.execute("SELECT id FROM stories WHERE guid = ?", (guid,))
    return c.fetchone() is not None

def insert_story(c, story):
    c.execute('''
        INSERT OR IGNORE INTO stories
        (guid, title, url, source, source_tier, published_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'new')
    ''', (
        story["guid"], story["title"], story["url"],
        story["source"], story["tier"], story["published_at"],
    ))
    return c.lastrowid

def update_source_health(c, source_name, success):
    now = datetime.now(timezone.utc).isoformat()
    c.execute('''
        INSERT INTO source_health (source, last_fetched, last_success, fail_count, stories_today)
        VALUES (?, ?, ?, 0, 0)
        ON CONFLICT(source) DO UPDATE SET
            last_fetched = ?,
            last_success = CASE WHEN ? THEN ? ELSE last_success END,
            fail_count   = CASE WHEN ? THEN 0 ELSE fail_count + 1 END
    ''', (source_name, now, now if success else None,
          now, success, now, success))

def poll_source(source):
    log.info(f"Polling [{source['name']}] tier={source['tier']}")
    try:
        feed = feedparser.parse(source["url"])
        if feed.bozo and not feed.entries:
            raise ValueError(f"Feed parse error: {feed.bozo_exception}")

        conn = get_db()
        c    = conn.cursor()
        new_count = 0

        for entry in feed.entries:
            title = getattr(entry, "title", "").strip()
            url   = getattr(entry, "link",  "").strip()
            if not title:
                continue
            guid = make_guid(url, title)
            if story_exists(c, guid):
                continue
            story = {
                "guid": guid, "title": title, "url": url,
                "source": source["name"], "tier": source["tier"],
                "published_at": parse_date(entry),
            }
            insert_story(c, story)
            new_count += 1
            log.info(f"  NEW: {title[:80]}")

        update_source_health(c, source["name"], success=True)
        conn.commit()
        conn.close()
        log.info(f"  Done — {new_count} new from {source['name']}")
        return new_count

    except Exception as e:
        log.error(f"  FAIL [{source['name']}]: {e}")
        conn = get_db()
        c    = conn.cursor()
        update_source_health(c, source["name"], success=False)
        conn.commit()
        conn.close()
        return 0

def poll_all():
    log.info("=== RSS Poll cycle starting ===")
    total = 0
    for source in RSS_SOURCES:
        total += poll_source(source)
    log.info(f"=== Poll complete — {total} new stories total ===")
    return total

if __name__ == "__main__":
    poll_all()
