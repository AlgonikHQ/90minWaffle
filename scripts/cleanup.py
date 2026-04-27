#!/usr/bin/env python3
import sqlite3, os, glob, logging
from datetime import datetime, timedelta

DB_PATH = "/root/90minwaffle/data/waffle.db"
VIDEO_DIR = "/root/90minwaffle/data/videos"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def cleanup():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    freed = 0

    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    c.execute("SELECT id, video_path FROM stories WHERE status='published' AND fetched_at < ? AND video_path IS NOT NULL", (cutoff,))
    published = c.fetchall()

    for sid, vpath in published:
        if vpath and os.path.exists(vpath):
            freed += os.path.getsize(vpath)
            os.remove(vpath)
            log.info(f"  Deleted video {sid}: {vpath}")
        for f in glob.glob(f"{VIDEO_DIR}/voice_{sid}*.mp3"):
            freed += os.path.getsize(f)
            os.remove(f)
        for f in glob.glob(f"{VIDEO_DIR}/seg_{sid}_*.mp4"):
            if os.path.exists(f): os.remove(f)
        c.execute("UPDATE stories SET video_path=NULL WHERE id=?", (sid,))

    old_cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    c.execute("DELETE FROM stories WHERE status='holding' AND fetched_at < ?", (old_cutoff,))
    pruned = c.rowcount

    for f in glob.glob(f"{VIDEO_DIR}/seg_*.mp4"):
        os.remove(f)

    conn.commit()
    conn.close()
    log.info(f"=== Cleanup: {len(published)} videos removed, {pruned} old stories pruned, {freed/1024/1024:.1f}MB freed ===")

if __name__ == "__main__":
    cleanup()
