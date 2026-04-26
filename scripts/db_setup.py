import sqlite3
import os

DB_PATH = "/root/90minwaffle/data/waffle.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Stories table — every news item seen
    c.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guid TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            url TEXT,
            source TEXT,
            source_tier INTEGER,
            published_at TEXT,
            fetched_at TEXT DEFAULT (datetime('now')),
            score INTEGER DEFAULT 0,
            score_breakdown TEXT,
            status TEXT DEFAULT 'new',
            format TEXT,
            expires_at TEXT,
            contrarian_angle TEXT,
            mainstream_angle TEXT,
            hook_1 TEXT,
            hook_2 TEXT,
            hook_3 TEXT,
            winning_hook TEXT,
            script TEXT,
            caption TEXT,
            hashtags TEXT,
            video_path TEXT,
            thumbnail_path TEXT,
            queued_at TEXT,
            published_at_tg TEXT,
            telegram_msg_id TEXT,
            performance_score INTEGER DEFAULT 0,
            views_1h INTEGER DEFAULT 0,
            views_24h INTEGER DEFAULT 0,
            views_7d INTEGER DEFAULT 0,
            notes TEXT
        )
    ''')

    # Star index table — rolling 14-day player index
    c.execute('''
        CREATE TABLE IF NOT EXISTS star_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_name TEXT UNIQUE NOT NULL,
            mention_count INTEGER DEFAULT 0,
            reddit_velocity INTEGER DEFAULT 0,
            goal_contributions INTEGER DEFAULT 0,
            award_context INTEGER DEFAULT 0,
            transfer_involvement INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT (datetime('now'))
        )
    ''')

    # Source health table — tracks per-source reliability
    c.execute('''
        CREATE TABLE IF NOT EXISTS source_health (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT UNIQUE NOT NULL,
            last_fetched TEXT,
            last_success TEXT,
            fail_count INTEGER DEFAULT 0,
            stories_today INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        )
    ''')

    # Queue table — videos ready for owner review
    c.execute('''
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            story_id INTEGER,
            confidence TEXT,
            suggested_window TEXT,
            action TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            actioned_at TEXT,
            FOREIGN KEY (story_id) REFERENCES stories(id)
        )
    ''')

    # Bot state table — key/value store for bot state
    c.execute('''
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    # Seed bot state defaults
    defaults = [
        ('status', 'active'),
        ('holiday_until', None),
        ('videos_today', '0'),
        ('last_star_refresh', None),
        ('paused_formats', ''),
        ('paused_pillars', ''),
    ]
    for key, value in defaults:
        c.execute('INSERT OR IGNORE INTO bot_state (key, value) VALUES (?, ?)', (key, value))

    conn.commit()
    conn.close()
    print(f"[OK] Database initialised at {DB_PATH}")
    print("[OK] Tables: stories, star_index, source_health, queue, bot_state")

if __name__ == "__main__":
    init_db()
