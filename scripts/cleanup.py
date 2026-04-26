#!/usr/bin/env python3
"""
90minWaffle Disk Cleanup
Deletes videos and b-roll older than 48 hours that have been published or binned.
Keeps: queued, scripted (not yet sent)
Deletes: published, binned, skipped — older than 48h
"""
import os
import sqlite3
import logging
from datetime import datetime, timezone, timedelta

DB_PATH    = "/root/90minwaffle/data/waffle.db"
VIDEO_DIR  = "/root/90minwaffle/data/videos"
BROLL_DIR  = "/root/90minwaffle/data/broll"
LOG_PATH   = "/root/90minwaffle/logs/cleanup.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def get_db(): return sqlite3.connect(DB_PATH)

def cleanup_videos():
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    conn = get_db(); c = conn.cursor()

    # Get published/binned stories with video paths older than 48h
    c.execute("""
        SELECT id, video_path FROM stories
        WHERE status IN ('published','binned','skipped')
        AND video_path IS NOT NULL
        AND fetched_at < ?
    """, (cutoff,))
    rows = c.fetchall()

    deleted_count = 0
    freed_bytes = 0

    for story_id, video_path in rows:
        if video_path and os.path.exists(video_path):
            size = os.path.getsize(video_path)
            os.remove(video_path)
            freed_bytes += size
            deleted_count += 1
            log.info(f"  Deleted video: {video_path} ({size//1024}KB)")

        # Also delete matching voice file
        voice_path = video_path.replace(f"video_{story_id}", f"voice_{story_id}").replace(".mp4", ".mp3") if video_path else None
        if voice_path and os.path.exists(voice_path):
            size = os.path.getsize(voice_path)
            os.remove(voice_path)
            freed_bytes += size

        # Clear video_path in DB
        c.execute("UPDATE stories SET video_path=NULL WHERE id=?", (story_id,))

    conn.commit(); conn.close()
    log.info(f"Videos cleaned: {deleted_count} deleted, {freed_bytes//1024//1024}MB freed")
    return freed_bytes

def cleanup_broll():
    """Delete all b-roll clips older than 24 hours — they're always re-fetched."""
    cutoff_time = datetime.now(timezone.utc).timestamp() - (24 * 3600)
    deleted = 0
    freed = 0

    for fname in os.listdir(BROLL_DIR):
        fpath = os.path.join(BROLL_DIR, fname)
        if os.path.isfile(fpath):
            if os.path.getmtime(fpath) < cutoff_time:
                size = os.path.getsize(fpath)
                os.remove(fpath)
                freed += size
                deleted += 1

    log.info(f"B-roll cleaned: {deleted} files, {freed//1024//1024}MB freed")
    return freed

def cleanup_old_stories():
    """Remove stories older than 30 days from DB to keep it lean."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    conn = get_db(); c = conn.cursor()
    c.execute("""
        DELETE FROM stories
        WHERE fetched_at < ?
        AND status IN ('published','binned','skipped')
    """, (cutoff,))
    deleted = c.rowcount
    conn.commit(); conn.close()
    log.info(f"Old stories purged: {deleted} rows removed")
    return deleted

def run_cleanup():
    log.info("=== Cleanup starting ===")
    video_freed = cleanup_videos()
    broll_freed = cleanup_broll()
    stories_purged = cleanup_old_stories()
    total_freed = (video_freed + broll_freed) // 1024 // 1024
    log.info(f"=== Cleanup complete — {total_freed}MB freed, {stories_purged} old stories purged ===")

    # Report disk usage
    statvfs = os.statvfs('/root')
    free_gb = (statvfs.f_frsize * statvfs.f_bavail) / 1024**3
    log.info(f"  Disk free: {free_gb:.1f}GB")

if __name__ == "__main__":
    run_cleanup()
