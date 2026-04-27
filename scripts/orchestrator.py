#!/usr/bin/env python3
"""
90minWaffle Orchestrator
Runs the full pipeline: RSS poll → score → corroborate → script → video → queue
"""
import os
import sys
import sqlite3
import logging
import asyncio
import importlib.util
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/root/90minwaffle/.env')

sys.path.insert(0, '/root/90minwaffle/scripts')

LOG_PATH = "/root/90minwaffle/logs/orchestrator.log"
DB_PATH  = "/root/90minwaffle/data/waffle.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def get_db():
    return sqlite3.connect(DB_PATH)

def import_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def step_poll():
    log.info("━━━ STEP 1: RSS Poll ━━━")
    try:
        rss = import_module("rss_poller", "/root/90minwaffle/scripts/rss_poller.py")
        new = rss.poll_all()
        log.info(f"  RSS poll complete — {new} new stories")
        return new
    except Exception as e:
        log.error(f"  RSS poll failed: {e}")
        return 0

def step_score():
    log.info("━━━ STEP 2: Score ━━━")
    try:
        scorer = import_module("scorer", "/root/90minwaffle/scripts/scorer.py")
        ship, hold, skip = scorer.score_unscored_stories()
        log.info(f"  Scored — {ship} shippable, {hold} holding, {skip} skipped")
        return ship
    except Exception as e:
        log.error(f"  Scoring failed: {e}")
        return 0

def step_corroborate():
    log.info("━━━ STEP 3: Corroborate ━━━")
    try:
        corr = import_module("corroborate", "/root/90minwaffle/scripts/corroborate.py")
        boosted = corr.apply_corroboration_bonus()
        log.info(f"  Corroboration complete — {boosted} promoted to shippable")
        return boosted
    except Exception as e:
        log.error(f"  Corroboration failed: {e}")
        return 0

def step_cards():
    log.info("━━━ Cards ━━━")
    try:
        cg = import_module("card_generator", "/root/90minwaffle/scripts/card_generator.py")
        import asyncio as _aio
        return _aio.get_event_loop().run_until_complete(cg.process_cards(limit=5))
    except Exception as e:
        log.error(f"  Cards failed: {e}"); return 0

def step_script(limit=3):
    log.info("━━━ STEP 4: Script Generation ━━━")
    try:
        sg = import_module("script_gen", "/root/90minwaffle/scripts/script_gen.py")
        success = sg.process_shippable_stories(limit=limit)
        log.info(f"  Scripts generated: {success}")
        return success
    except Exception as e:
        log.error(f"  Script generation failed: {e}")
        return 0

def step_video(limit=2):
    log.info("━━━ STEP 5: Video Production ━━━")
    try:
        va = import_module("video_assembler", "/root/90minwaffle/scripts/video_assembler.py")

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT id, title, source, score, format, script
            FROM stories WHERE status='scripted'
            ORDER BY score DESC LIMIT ?
        """, (limit,))
        rows = c.fetchall()
        conn.close()

        stories = [{"id":r[0],"title":r[1],"source":r[2],
                    "score":r[3],"format":r[4],"script":r[5]} for r in rows]

        produced = 0
        for story in stories:
            result = va.produce_video(story)
            if result:
                produced += 1

        log.info(f"  Videos produced: {produced}/{len(stories)}")
        return produced
    except Exception as e:
        log.error(f"  Video production failed: {e}")
        return 0


async def step_overlay():
    log.info("━━━ STEP 5b: Text Overlay ━━━")
    try:
        import sys
        sys.path.insert(0, '/root/90minwaffle/scripts')
        import importlib.util
        spec = importlib.util.spec_from_file_location("text_overlay", "/root/90minwaffle/scripts/text_overlay.py")
        to = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(to)
        done = to.process_videos(limit=2)
        log.info(f"  Overlays applied: {done}")
        return done
    except Exception as e:
        log.error(f"  Overlay failed: {e}")
        return 0

async def step_telegram():
    log.info("━━━ STEP 7b: Telegram Posting ━━━")
    try:
        tp = import_module("telegram_poster", "/root/90minwaffle/scripts/telegram_poster.py")
        posted = await tp.process_news_queue(limit=3)
        log.info(f"  Telegram posted: {posted}")
        return posted
    except Exception as e:
        log.error(f"  Telegram posting failed: {e}")
        return 0

def step_match_intel():
    log.info("━━━ STEP 8: Match Intel (Odds) ━━━")
    try:
        mi = import_module("match_intel", "/root/90minwaffle/scripts/match_intel.py")
        mi.run_match_intel()
        log.info("  Match Intel done")
    except Exception as e:
        log.error(f"  Match Intel failed: {e}")

def step_discord():
    log.info("━━━ STEP 7: Discord Posting ━━━")
    try:
        dp = import_module("discord_poster", "/root/90minwaffle/scripts/discord_poster.py")
        posted = dp.process_discord_queue(limit=3)
        log.info(f"  Discord posted: {posted}")
        return posted
    except Exception as e:
        log.error(f"  Discord posting failed: {e}")
        return 0
async def step_queue():
    log.info("━━━ STEP 6: Queue Notification ━━━")
    try:
        qn = import_module("queue_notifier", "/root/90minwaffle/scripts/queue_notifier.py")
        sent = await qn.process_queue()
        log.info(f"  Queue notifications sent: {sent}")
        return sent
    except Exception as e:
        log.error(f"  Queue notification failed: {e}")
        return 0


async def step_youtube():
    log.info("━━━ STEP 8: YouTube Upload ━━━")
    try:
        yt = import_module("youtube_uploader", "/root/90minwaffle/scripts/youtube_uploader.py")
        uploaded = yt.process_upload_queue(limit=3)
        log.info(f"  YouTube uploaded: {uploaded}")
        return uploaded
    except Exception as e:
        log.error(f"  YouTube upload failed: {e}")
        return 0

async def send_cycle_report(new_stories, shippable, scripted, produced, queued):
    """Send a brief cycle report to the Reports channel."""
    try:
        qn = import_module("queue_notifier", "/root/90minwaffle/scripts/queue_notifier.py")
        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        msg = (
            f"📊 *90minWaffle Cycle Report — {now}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 New stories ingested: `{new_stories}`\n"
            f"🟢 Shippable after scoring: `{shippable}`\n"
            f"✍️ Scripts generated: `{scripted}`\n"
            f"🎬 Videos produced: `{produced}`\n"
            f"📤 Sent to queue: `{queued}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_Next cycle in 2 hours_"
        )
        await qn.send_report(msg)
        # Also send to Inside channel (private dev channel)
        tp = import_module("telegram_poster", "/root/90minwaffle/scripts/telegram_poster.py")
        await tp.send_report(msg)
    except Exception as e:
        log.error(f"  Cycle report failed: {e}")

async def run_cycle(script_limit=2, video_limit=2):
    start = datetime.now(timezone.utc)
    log.info(f"{'='*50}")
    log.info(f"90minWaffle Cycle — {start.strftime('%Y-%m-%d %H:%M UTC')}")
    log.info(f"{'='*50}")

    new_stories  = step_poll()
    shippable    = step_score()
    shippable   += step_corroborate()
    cards        = asyncio.run(step_cards())
    scripted     = step_script(limit=script_limit)
    produced     = step_video(limit=video_limit)
    await step_overlay()
    queued       = await step_queue()
    step_discord()
    await step_telegram()
    await step_youtube()
    step_match_intel()

    # Daily cleanup — runs once per day at 2am
    if datetime.now(timezone.utc).hour == 2:
        log.info("━━━ Daily Cleanup ━━━")
        import_module("cleanup", "/root/90minwaffle/scripts/cleanup.py").cleanup()

    elapsed = (datetime.now(timezone.utc) - start).seconds
    log.info(f"{'='*50}")
    log.info(f"Cycle complete in {elapsed}s")
    log.info(f"  New: {new_stories} | Shippable: {shippable} | Scripts: {scripted} | Videos: {produced} | Queued: {queued}")
    log.info(f"{'='*50}")

    await send_cycle_report(new_stories, shippable, scripted, produced, queued)
    return queued

async def run_loop(interval_minutes=120):
    """Run continuously every interval_minutes."""
    log.info(f"90minWaffle Bot starting — cycle every {interval_minutes} minutes")
    while True:
        try:
            await run_cycle()
        except Exception as e:
            log.error(f"Cycle error: {e}")
        log.info(f"Sleeping {interval_minutes} minutes until next cycle...")
        await asyncio.sleep(interval_minutes * 60)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=120, help="Loop interval in minutes")
    parser.add_argument("--scripts", type=int, default=3, help="Max scripts per cycle")
    parser.add_argument("--videos", type=int, default=2, help="Max videos per cycle")
    args = parser.parse_args()

    if args.loop:
        asyncio.run(run_loop(interval_minutes=args.interval))
    else:
        asyncio.run(run_cycle(script_limit=args.scripts, video_limit=args.videos))
