#!/usr/bin/env python3
import sqlite3, os, glob, logging
from datetime import datetime, timedelta

DB_PATH   = "/root/90minwaffle/data/waffle.db"
VIDEO_DIR = "/root/90minwaffle/data/videos"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def cleanup():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    freed = 0

    # 1. Delete video files for published stories older than 24hrs
    cutoff_24h = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    c.execute("""SELECT id, video_path FROM stories
        WHERE status='published'
        AND fetched_at < ?
        AND video_path IS NOT NULL""", (cutoff_24h,))
    published = c.fetchall()
    for sid, vpath in published:
        for pattern in [vpath, vpath.replace("_overlay",""), vpath.replace("_overlay","_thumb").replace(".mp4",".jpg")]:
            if pattern and os.path.exists(pattern):
                freed += os.path.getsize(pattern)
                os.remove(pattern)
        for f in glob.glob(VIDEO_DIR + "/voice_" + str(sid) + "*.mp3"):
            freed += os.path.getsize(f); os.remove(f)
        for f in glob.glob(VIDEO_DIR + "/voice_" + str(sid) + "*.json"):
            os.remove(f)
        for f in glob.glob(VIDEO_DIR + "/seg_" + str(sid) + "_*.mp4"):
            os.remove(f)
        c.execute("UPDATE stories SET video_path=NULL, thumbnail_path=NULL WHERE id=?", (sid,))
    log.info("  Published videos cleaned: " + str(len(published)))

    # 2. Reset stale scripted stories back to shippable after 48hrs
    # so they can be re-scripted with fresher context if still relevant
    cutoff_48h = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    c.execute("""UPDATE stories SET status='shippable', script=NULL,
        winning_hook=NULL, hook_1=NULL, hook_2=NULL, hook_3=NULL
        WHERE status='scripted'
        AND video_path IS NULL
        AND fetched_at < ?""", (cutoff_48h,))
    reset_scripts = c.rowcount
    log.info("  Stale scripts reset to shippable: " + str(reset_scripts))

    # 3. Expire shippable stories older than 48hrs — move to skipped
    c.execute("""UPDATE stories SET status='skipped'
        WHERE status='shippable'
        AND fetched_at < ?""", (cutoff_48h,))
    expired = c.rowcount
    log.info("  Expired shippable stories: " + str(expired))

    # 4. Prune holding stories older than 7 days
    cutoff_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
    c.execute("DELETE FROM stories WHERE status='holding' AND fetched_at < ?", (cutoff_7d,))
    pruned_holding = c.rowcount

    # 5. Prune skipped stories older than 3 days
    cutoff_3d = (datetime.utcnow() - timedelta(days=3)).isoformat()
    c.execute("DELETE FROM stories WHERE status='skipped' AND fetched_at < ?", (cutoff_3d,))
    pruned_skipped = c.rowcount

    # 6. Clean up orphaned segment files
    for f in glob.glob(VIDEO_DIR + "/seg_*.mp4"):
        os.remove(f)

    # 7. Clean up thumbnail files for published stories
    for f in glob.glob(VIDEO_DIR + "/*_thumb.jpg"):
        sid_str = os.path.basename(f).replace("_thumb.jpg","").replace("video_","")
        try:
            sid = int(sid_str)
            c.execute("SELECT status FROM stories WHERE id=?", (sid,))
            row = c.fetchone()
            if row and row[0] == "published":
                os.remove(f)
        except Exception:
            pass

    conn.commit()
    conn.close()

    mb = freed / 1024 / 1024
    log.info(
        "=== Cleanup done: " +
        str(len(published)) + " videos removed, " +
        str(reset_scripts) + " scripts reset, " +
        str(expired) + " stories expired, " +
        str(pruned_holding + pruned_skipped) + " stories pruned, " +
        str(round(mb, 1)) + "MB freed ==="
    )

if __name__ == "__main__":
    cleanup()
