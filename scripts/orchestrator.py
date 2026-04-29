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

async def step_cards():
    log.info("━━━ Cards ━━━")
    try:
        cg = import_module("card_generator", "/root/90minwaffle/scripts/card_generator.py")
        
        return await cg.process_cards(limit=10)
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

def get_dynamic_video_cap():
    """Calculate daily video cap based on ElevenLabs quota and days remaining in billing period."""
    try:
        import requests as _req
        from datetime import datetime, timezone
        key = os.getenv("ELEVENLABS_API_KEY", "")
        r = _req.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key}, timeout=10)
        if r.status_code != 200: return 1
        data = r.json().get("subscription", {})
        remaining = data.get("character_limit", 10000) - data.get("character_count", 0)
        reset_ts  = data.get("next_character_count_reset_unix", 0)
        days_left = max(1, (datetime.fromtimestamp(reset_ts, tz=timezone.utc) - datetime.now(timezone.utc)).days)
        chars_per_video = 850
        affordable = int(remaining / chars_per_video)
        daily_cap = 1 if affordable >= days_left else 0
        log.info(f"  ElevenLabs quota: {remaining} chars | {days_left} days left | affordable: {affordable} videos | daily cap: {daily_cap}")
        return daily_cap
    except Exception as e:
        log.warning(f"  Dynamic cap failed: {e} — defaulting to 1")
        return 1

DAILY_VIDEO_CAP = 3
VIDEO_SCORE_GATE = 55
MIN_ELEVEN_CHARS = 500

def videos_produced_today():
    """Count videos already produced today (UTC date)."""
    try:
        conn = get_db()
        c = conn.cursor()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        c.execute("""
            SELECT COUNT(*) FROM stories
            WHERE video_path IS NOT NULL
            AND date(updated_at) = ?
        """, (today,))
        count = c.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

def step_video(limit=1):
    log.info("━━━ STEP 5: Video Production ━━━")
    try:
        va = import_module("video_assembler", "/root/90minwaffle/scripts/video_assembler.py")

        # Daily cap check
        today_count = videos_produced_today()
        dynamic_cap = get_dynamic_video_cap()
        if today_count >= dynamic_cap:
            log.info(f"  Daily video cap reached ({today_count}/{dynamic_cap}) — skipping, cards will post instead")
            return 0

        # ElevenLabs quota check
        remaining_chars = va.check_eleven_quota()
        if remaining_chars < MIN_ELEVEN_CHARS:
            log.warning(f"  ElevenLabs quota too low ({remaining_chars} chars) — skipping video, cards will post instead")
            return 0

        slots = dynamic_cap - today_count
        effective_limit = min(limit, slots)

        conn = get_db()
        c = conn.cursor()
        c.execute("""
            SELECT id, title, source, score, format, script
            FROM stories WHERE status='scripted'
            AND score >= ?
            ORDER BY score DESC LIMIT ?
        """, (VIDEO_SCORE_GATE, effective_limit))
        rows = c.fetchall()
        conn.close()

        stories = [{"id":r[0],"title":r[1],"source":r[2],
                    "score":r[3],"format":r[4],"script":r[5]} for r in rows]

        if not stories:
            log.info(f"  No stories meet video gate (score≥{VIDEO_SCORE_GATE}) — cards will post instead")
            return 0

        produced = 0
        for story in stories:
            log.info(f"  Video candidate: [{story['score']}] {story['title'][:60]}")
            result = va.produce_video(story)
            if result:
                produced += 1

        log.info(f"  Videos produced: {produced}/{len(stories)} | Today total: {today_count + produced}/{DAILY_VIDEO_CAP}")
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

def step_bet_alerts():
    log.info("━━━ STEP 9: Bet Alerts ━━━")
    try:
        ba = import_module("bet_alert", "/root/90minwaffle/scripts/bet_alert.py")
        sent = ba.run_bet_alerts()
        log.info(f"  Bet alerts sent: {sent}")
        return sent
    except Exception as e:
        log.error(f"  Bet alerts failed: {e}")
        return 0

async def step_podcast():
    log.info("━━━ STEP 11: Podcast PDF ━━━")
    try:
        pg = import_module("podcast_gen", "/root/90minwaffle/scripts/podcast_gen.py")
        path = await pg.run_podcast()
        log.info(f"  Podcast PDF: {path}")
    except Exception as e:
        log.error(f"  Podcast PDF failed: {e}")

async def step_digest():
    log.info("\u2501\u2501\u2501 STEP 10: Daily Digest \u2501\u2501\u2501")
    try:
        dg = import_module("digest_poster", "/root/90minwaffle/scripts/digest_poster.py")
        sent = await dg.run_digest()
        log.info(f"  Digest posted: {sent}")
        return sent
    except Exception as e:
        log.error(f"  Digest failed: {e}")
        return 0

def step_data_refresh():
    log.info("━━━ STEP 0: Data Refresh ━━━")
    try:
        df = import_module("data_fetcher", "/root/90minwaffle/scripts/data_fetcher.py")
        success = df.refresh_all()
        log.info(f"  Data refresh — {success}/9 caches updated")
        return success
    except Exception as e:
        log.error(f"  Data refresh failed: {e}")
        return 0

def step_discord():
    log.info("━━━ STEP 7: Discord Posting ━━━")
    try:
        dp = import_module("discord_poster", "/root/90minwaffle/scripts/discord_poster.py")
        posted = dp.process_discord_queue(limit=3)
        # Post poll after every F7 hot take
        conn = get_db(); c = conn.cursor()
        c.execute("""SELECT id, title, winning_hook, format FROM stories
            WHERE status='published' AND format='F7'
            AND (notes IS NULL OR notes NOT LIKE '%poll_sent%')
            ORDER BY id DESC LIMIT 2""")
        hot_takes = c.fetchall(); conn.close()
        for ht in hot_takes:
            story = {"id": ht[0], "title": ht[1], "winning_hook": ht[2], "format": ht[3]}
            dp.post_poll(story, "hot_takes")
            conn = get_db(); c = conn.cursor()
            c.execute("UPDATE stories SET notes='poll_sent' WHERE id=?", (ht[0],))
            conn.commit(); conn.close()
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
            f"_Next cycle in 10 minutes_"
        )
        await qn.send_report(msg)
    except Exception as e:
        log.error(f"  Cycle report failed: {e}")

async def run_cycle(script_limit=2, video_limit=2, force_digest=False, force_podcast=False):
    start = datetime.now(timezone.utc)
    log.info(f"{'='*50}")
    log.info(f"90minWaffle Cycle — {start.strftime('%Y-%m-%d %H:%M UTC')}")
    log.info(f"{'='*50}")

    step_data_refresh()
    new_stories  = step_poll()
    shippable    = step_score()
    shippable   += step_corroborate()
    cards        = await step_cards()
    scripted     = step_script(limit=script_limit)
    produced     = step_video(limit=video_limit)
    await step_overlay()
    queued       = await step_queue()
    step_discord()
    await step_telegram()
    await step_youtube()
    step_match_intel()

    # Bet alerts — every cycle
    step_bet_alerts()

    # Daily digest — standings + top scorers at 8am
    if datetime.now(timezone.utc).hour == 8 or force_digest:
        await step_digest()

    # Podcast PDF — Sundays at 9am
    if (datetime.now(timezone.utc).weekday() == 6 and datetime.now(timezone.utc).hour == 9) or force_podcast:
        await step_podcast()

    # Daily cleanup — runs once per day at 2am
    if datetime.now(timezone.utc).hour == 2:
        log.info("━━━ Daily Cleanup ━━━")
        import_module("cleanup", "/root/90minwaffle/scripts/cleanup.py").cleanup()

    # Midnight daily summary to Reports channel
    if datetime.now(timezone.utc).hour == 0:
        log.info("━━━ Midnight Summary ━━━")
        try:
            tp = import_module("telegram_poster", "/root/90minwaffle/scripts/telegram_poster.py")
            conn = get_db(); c = conn.cursor()
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            c.execute("SELECT COUNT(*) FROM stories WHERE date(created_at) = ?", (today,))
            s = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM stories WHERE status='shippable' AND date(created_at) = ?", (today,))
            sh = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM stories WHERE video_path IS NOT NULL AND date(updated_at) = ?", (today,))
            v = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM stories WHERE status='published' AND date(updated_at) = ?", (today,))
            p = c.fetchone()[0]
            conn.close()
            await tp.send_midnight_summary({"stories": s, "shippable": sh, "videos": v, "posted": p})
        except Exception as e:
            log.error(f"  Midnight summary failed: {e}")

    # ElevenLabs quota check — alert if under 10%
    try:
        va = import_module("video_assembler", "/root/90minwaffle/scripts/video_assembler.py")
        tp = import_module("telegram_poster", "/root/90minwaffle/scripts/telegram_poster.py")
        remaining = va.check_eleven_quota()
        if 0 < remaining < 1000:
            await tp.send_quota_alert(remaining, 10000)
    except Exception as e:
        log.error(f"  Quota check failed: {e}")

    elapsed = (datetime.now(timezone.utc) - start).seconds
    log.info(f"{'='*50}")
    log.info(f"Cycle complete in {elapsed}s")
    log.info(f"  New: {new_stories} | Shippable: {shippable} | Scripts: {scripted} | Videos: {produced} | Queued: {queued}")
    log.info(f"{'='*50}")

    await send_cycle_report(new_stories, shippable, scripted, produced, queued)
    return queued

async def run_loop(interval_minutes=10):
    """Run continuously - poll every 10 mins, fire cards as they arrive."""
    POST_SPACING_SECONDS = 240
    HEAVY_STEPS_INTERVAL = 6
    log.info("90minWaffle Bot starting - live feed mode, polling every %d minutes" % interval_minutes)
    cycle_count = 0

    while True:
        cycle_count += 1
        run_heavy = (cycle_count % HEAVY_STEPS_INTERVAL == 1)
        try:
            start = datetime.now(timezone.utc)
            log.info("=" * 50)
            log.info("90minWaffle Cycle #%d - %s | heavy=%s" % (cycle_count, start.strftime("%Y-%m-%d %H:%M UTC"), run_heavy))
            log.info("=" * 50)

            if run_heavy:
                step_data_refresh()
            new_stories = step_poll()
            shippable   = step_score()
            shippable  += step_corroborate()

            # Also fire any existing shippable stories from previous cycles
            conn = sqlite3.connect(DB_PATH)
            existing = conn.execute(
                "SELECT COUNT(*) FROM stories WHERE status='shippable' AND (notes IS NULL OR notes NOT LIKE '%card_sent%')"
            ).fetchone()[0]
            conn.close()
            if existing > 0:
                log.info("  %d existing shippable stories in queue" % existing)
            shippable += existing

            if shippable > 0:
                log.info("  %d new shippable - firing cards with %ds spacing" % (shippable, POST_SPACING_SECONDS))
                cg = import_module("card_generator", "/root/90minwaffle/scripts/card_generator.py")
                for _ in range(min(shippable, 5)):
                    await cg.process_cards(limit=1)
                    await asyncio.sleep(POST_SPACING_SECONDS)
            else:
                log.info("  No new shippable stories this cycle - nothing to post")

            scripted = produced = queued = 0
            if run_heavy:
                scripted = step_script(limit=3)
                produced = step_video(limit=2)
                await step_overlay()
                queued   = await step_queue()
                step_discord()
                await step_telegram()
                await step_youtube()
                step_match_intel()
                step_bet_alerts()

            now_hour = datetime.now(timezone.utc).hour
            if now_hour == 8:
                await step_digest()
            if datetime.now(timezone.utc).weekday() == 6 and now_hour == 9:
                await step_podcast()
            if now_hour == 2:
                log.info("Daily Cleanup")
                import_module("cleanup", "/root/90minwaffle/scripts/cleanup.py").cleanup()
            if now_hour == 0:
                log.info("Midnight Summary")
                try:
                    tp = import_module("telegram_poster", "/root/90minwaffle/scripts/telegram_poster.py")
                    conn = get_db()
                    c = conn.cursor()
                    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    c.execute("SELECT COUNT(*) FROM stories WHERE date(created_at) = ?", (today,))
                    s = c.fetchone()[0]
                    c.execute("SELECT COUNT(*) FROM stories WHERE status='shippable' AND date(created_at) = ?", (today,))
                    sh = c.fetchone()[0]
                    c.execute("SELECT COUNT(*) FROM stories WHERE video_path IS NOT NULL AND date(updated_at) = ?", (today,))
                    v = c.fetchone()[0]
                    c.execute("SELECT COUNT(*) FROM stories WHERE status='published' AND date(updated_at) = ?", (today,))
                    p = c.fetchone()[0]
                    conn.close()
                    await tp.send_midnight_summary({"stories": s, "shippable": sh, "videos": v, "posted": p})
                except Exception as e:
                    log.error("Midnight summary failed: %s" % e)

            try:
                va = import_module("video_assembler", "/root/90minwaffle/scripts/video_assembler.py")
                tp = import_module("telegram_poster", "/root/90minwaffle/scripts/telegram_poster.py")
                remaining = va.check_eleven_quota()
                if 0 < remaining < 1000:
                    await tp.send_quota_alert(remaining, 10000)
            except Exception as e:
                log.error("Quota check failed: %s" % e)

            elapsed = (datetime.now(timezone.utc) - start).seconds
            log.info("Cycle #%d done in %ds | new=%d ship=%d scripts=%d videos=%d" % (
                cycle_count, elapsed, new_stories, shippable, scripted, produced))
            if run_heavy:
                await send_cycle_report(new_stories, shippable, scripted, produced, queued)

        except Exception as e:
            log.error("Cycle #%d error: %s" % (cycle_count, e))

        log.info("Sleeping %d minutes until next cycle..." % interval_minutes)
        await asyncio.sleep(interval_minutes * 60)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=60, help="Loop interval in minutes")
    parser.add_argument("--scripts", type=int, default=3, help="Max scripts per cycle")
    parser.add_argument("--videos", type=int, default=2, help="Max videos per cycle")
    parser.add_argument("--force-digest", action="store_true", help="Force daily digest now")
    parser.add_argument("--force-podcast", action="store_true", help="Force podcast PDF now")
    args = parser.parse_args()

    if args.loop:
        asyncio.run(run_loop(interval_minutes=args.interval))
    else:
        asyncio.run(run_cycle(script_limit=args.scripts, video_limit=args.videos))
