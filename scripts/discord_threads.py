#!/usr/bin/env python3
"""
discord_threads.py — Match day thread management for 90minWaffle Discord.

For every F3 (match preview) posted to Discord:
  - Creates a thread on that message titled "Match Thread: {title}"
  - Stores the thread ID in stories.discord_thread_id

For every F4 (post-match) posted to Discord:
  - Detects if a related F3 thread exists (same teams mentioned)
  - Posts the result into that thread
  - Keeps the full match conversation in one place for the community

Called from discord_poster.py after every F3/F4 post.
"""

import os, re, requests, sqlite3, logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

LOG_PATH = "/root/90minwaffle/logs/discord_threads.log"
DB_PATH  = "/root/90minwaffle/data/waffle.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
HEADERS   = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type":  "application/json",
}

def get_db():
    return sqlite3.connect(DB_PATH)

def _extract_teams(title: str) -> list[str]:
    """Extract team names from a match title for cross-referencing F3/F4."""
    import sys
    sys.path.insert(0, "/root/90minwaffle/scripts")
    try:
        from season_teams import PREMIER_LEAGUE, CHAMPIONSHIP, SCOTTISH_PREMIERSHIP
        all_teams = PREMIER_LEAGUE | CHAMPIONSHIP | SCOTTISH_PREMIERSHIP
    except ImportError:
        all_teams = set()

    t = title.lower()
    found = []
    for team in all_teams:
        pattern = r'\b' + re.escape(team) + r'\b'
        if re.search(pattern, t):
            found.append(team)
    return found

def create_thread_on_message(channel_id: str, message_id: str, thread_name: str) -> str | None:
    """
    Create a public thread on an existing Discord message.
    Returns the thread ID or None on failure.
    Requires the bot to have CREATE_PUBLIC_THREADS permission.
    """
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/threads"
    payload = {
        "name": thread_name[:100],
        "auto_archive_duration": 1440,  # 24 hours
    }
    try:
        r = requests.post(url, json=payload, headers=HEADERS, timeout=10)
        if r.status_code in (200, 201):
            thread_id = r.json().get("id")
            log.info(f"  Thread created: {thread_name[:60]} → {thread_id}")
            return thread_id
        else:
            log.error(f"  Thread create failed {r.status_code}: {r.text[:150]}")
            return None
    except Exception as e:
        log.error(f"  Thread create exception: {e}")
        return None

def post_to_thread(thread_id: str, content: str) -> bool:
    """Post a message into an existing thread."""
    url = f"https://discord.com/api/v10/channels/{thread_id}/messages"
    try:
        r = requests.post(url, json={"content": content}, headers=HEADERS, timeout=10)
        if r.status_code in (200, 201):
            log.info(f"  Posted to thread {thread_id}")
            return True
        else:
            log.error(f"  Thread post failed {r.status_code}: {r.text[:150]}")
            return False
    except Exception as e:
        log.error(f"  Thread post exception: {e}")
        return False

def find_related_thread(story: dict) -> str | None:
    """
    Find an existing F3 thread that covers the same teams as this F4 story.
    Looks back 48 hours for F3 stories with matching teams.
    """
    teams = _extract_teams(story.get("title", ""))
    if not teams:
        return None

    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT id, title, discord_thread_id
        FROM stories
        WHERE format = 'F3'
        AND discord_thread_id IS NOT NULL
        AND datetime(created_at) > datetime('now', '-48 hours')
        ORDER BY id DESC
        LIMIT 20
    """)
    rows = c.fetchall()
    conn.close()

    for row in rows:
        f3_teams = _extract_teams(row[1])
        # If at least one team overlaps — it's the same fixture
        if set(teams) & set(f3_teams):
            log.info(f"  Matched F4 → F3 thread: {row[1][:50]}")
            return row[2]

    return None

def handle_f3_posted(story: dict, channel_id: str, message_id: str):
    """
    Called after an F3 story is posted to Discord.
    Creates a match thread and stores the thread ID.
    """
    title      = story.get("title", "Unknown Match")
    hook       = story.get("winning_hook") or title
    thread_name = f"⚽ Match Thread: {hook[:80]}"

    thread_id = create_thread_on_message(channel_id, message_id, thread_name)
    if not thread_id:
        return

    # Store thread ID
    conn = get_db()
    c    = conn.cursor()
    c.execute(
        "UPDATE stories SET discord_thread_id = ? WHERE id = ?",
        (thread_id, story["id"])
    )
    conn.commit()
    conn.close()

    # Post opening prompt in thread
    teams = _extract_teams(title)
    if len(teams) >= 2:
        team_a = teams[0].title()
        team_b = teams[1].title()
        opener = (
            f"🗣️ **Match Thread is open!**\n\n"
            f"Drop your score predictions below 👇\n"
            f"React with your predicted winner:\n"
            f"🏠 {team_a} win\n"
            f"🤝 Draw\n"
            f"✈️ {team_b} win\n\n"
            f"_We'll post the result here after full time._"
        )
    else:
        opener = (
            f"🗣️ **Match Thread is open!**\n\n"
            f"Drop your score predictions below 👇\n"
            f"React: 🏠 Home win | 🤝 Draw | ✈️ Away win\n\n"
            f"_We'll post the result here after full time._"
        )
    post_to_thread(thread_id, opener)
    log.info(f"  F3 thread ready: {thread_name[:60]}")

def handle_f4_posted(story: dict):
    """
    Called after an F4 story is posted to Discord.
    Finds the related F3 thread and posts the result into it.
    """
    thread_id = find_related_thread(story)
    if not thread_id:
        log.info(f"  No matching F3 thread found for F4: {story.get('title','')[:50]}")
        return

    hook   = story.get("winning_hook") or story.get("title", "")
    script = (story.get("script") or "")[:300]

    result_msg = (
        f"📊 **FULL TIME**\n\n"
        f"**{hook}**\n\n"
        f"{script}\n\n"
        f"_🔥 Hot take incoming on the main channel_"
    )
    post_to_thread(thread_id, result_msg)

if __name__ == "__main__":
    # Test — list any open threads in DB
    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, discord_thread_id FROM stories "
        "WHERE discord_thread_id IS NOT NULL ORDER BY id DESC LIMIT 5"
    ).fetchall()
    conn.close()
    for r in rows:
        print(f"[{r[0]}] {r[1][:60]} → thread {r[2]}")
