#!/usr/bin/env python3
"""
90minWaffle Animated Text Overlay System
Creates TikTok-style animated text burns over b-roll footage.

Text layers:
- Hook slam (0-3s): Big white bold text, scale in from 0.5x to 1x
- Key claim (4-8s): Highlight word pops centre
- Mid pull quote: Script extract burns in with fade
- CTA question (last 4s): Binary question slides up from bottom
- Watermark: Always present top-left
"""
import subprocess
import sqlite3
import os
import re
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/root/90minwaffle/.env')

DB_PATH    = "/root/90minwaffle/data/waffle.db"
OUTPUT_DIR = "/root/90minwaffle/data/videos"
FONT_PATH  = "/root/90minwaffle/assets/Anton-Regular.ttf"
LOG_PATH   = "/root/90minwaffle/logs/text_overlay.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

def get_db(): return sqlite3.connect(DB_PATH)

def clean_text(text):
    """Remove special chars that break FFmpeg drawtext."""
    text = text.replace("'", "").replace('"', '').replace(':', ' ')
    text = text.replace('[', '').replace(']', '').replace('\\', '')
    text = re.sub(r'[^\x00-\x7F]', '', text)  # Remove non-ASCII (emojis)
    return text.strip()

def wrap_text(text, max_chars=20):
    """Wrap text at word boundaries."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = f"{current} {word}".strip()
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]  # Max 3 lines

def extract_key_claim(script):
    """Pull a punchy 2-6 word claim from the script."""
    sentences = [s.strip() for s in script.split('.') if len(s.strip()) > 10]
    # Find sentences with capitals (emphatic words)
    for s in sentences[1:4]:
        words = s.split()
        if 3 <= len(words) <= 8:
            return ' '.join(words[:6])
    return sentences[1][:40] if len(sentences) > 1 else ""

def extract_cta(caption):
    """Pull the binary question from caption."""
    lines = [l.strip() for l in caption.split('\n') if '?' in l]
    return lines[0][:60] if lines else "Agree or disagree?"

def build_filter_complex(hook, key_claim, cta, duration, font_path):
    """
    Build FFmpeg filter_complex for animated text overlays.
    Uses drawtext with enable expressions for timing.
    """
    hook_clean     = clean_text(hook.upper())
    claim_clean    = clean_text(key_claim.upper())
    cta_clean      = clean_text(cta)
    wm             = "90minWaffle"

    hook_lines = wrap_text(hook_clean, max_chars=18)
    mid         = duration / 2
    cta_start   = max(duration - 5, duration * 0.75)

    # Font path for FFmpeg
    fp = font_path.replace(':', '\\:') if os.path.exists(font_path) else ""
    font_arg = f"fontfile={fp}:" if fp else ""

    filters = []

    # ── Layer 0: Dark gradient overlay on bottom third (always) ──────────────
    filters.append(
        "drawbox=x=0:y=ih*0.75:w=iw:h=ih*0.25:color=black@0.6:t=fill"
    )

    # ── Layer 1: Watermark (always, top-left) ────────────────────────────────
    filters.append(
        f"drawtext={font_arg}text='{wm}':fontsize=36:fontcolor=white@0.8:"
        f"x=30:y=40:shadowcolor=black:shadowx=2:shadowy=2"
    )

    # ── Layer 2: Hook text (0s-4s) — scale effect via fontsize pulse ─────────
    # Line 1
    if hook_lines:
        l1 = hook_lines[0]
        # Animate: start small (fontsize 60), grow to 90 over 0.5s, hold, fade out
        filters.append(
            f"drawtext={font_arg}text='{l1}':"
            f"fontsize='if(lt(t,0.5),60+60*t,90)':"
            f"fontcolor='white@if(lt(t,0.3),t/0.3,if(lt(t,3.5),1,max(0,(4-t)/0.5)))':"
            f"x=(w-text_w)/2:y=h*0.35:"
            f"shadowcolor=black@0.8:shadowx=3:shadowy=3:"
            f"enable='between(t,0,4)'"
        )

    # Line 2
    if len(hook_lines) > 1:
        l2 = hook_lines[1]
        filters.append(
            f"drawtext={font_arg}text='{l2}':"
            f"fontsize='if(lt(t,0.7),50+57*t,90)':"
            f"fontcolor='white@if(lt(t,0.5),t/0.5,if(lt(t,3.5),1,max(0,(4-t)/0.5)))':"
            f"x=(w-text_w)/2:y=h*0.35+100:"
            f"shadowcolor=black@0.8:shadowx=3:shadowy=3:"
            f"enable='between(t,0,4)'"
        )

    # Line 3
    if len(hook_lines) > 2:
        l3 = hook_lines[2]
        filters.append(
            f"drawtext={font_arg}text='{l3}':"
            f"fontsize=90:"
            f"fontcolor='white@if(lt(t,0.8),t/0.8,if(lt(t,3.5),1,max(0,(4-t)/0.5)))':"
            f"x=(w-text_w)/2:y=h*0.35+200:"
            f"shadowcolor=black@0.8:shadowx=3:shadowy=3:"
            f"enable='between(t,0.2,4)'"
        )

    # ── Layer 3: RED accent bar under hook (0.3s-3.5s) ──────────────────────
    filters.append(
        f"drawbox=x=80:y=h*0.62:w=iw-160:h=6:color=0xe63946@"
        f"'if(lt(t,0.5),t/0.5,if(lt(t,3.5),1,max(0,(4-t)/0.5)))':t=fill:"
        f"enable='between(t,0.3,4)'"
    )

    # ── Layer 4: Key claim pop (5s-9s) ───────────────────────────────────────
    if claim_clean and len(claim_clean) > 5:
        claim_lines = wrap_text(claim_clean, max_chars=16)
        for i, cl in enumerate(claim_lines[:2]):
            y_pos = f"h*0.4+{i*90}"
            filters.append(
                f"drawtext={font_arg}text='{cl}':"
                f"fontsize='if(lt(t,5.3),70+(t-5)*100,80)':"
                f"fontcolor='white@if(lt(t,5.2),(t-5)/0.2,if(lt(t,8.5),1,max(0,(9-t)/0.5)))':"
                f"x=(w-text_w)/2:y={y_pos}:"
                f"shadowcolor=black@0.9:shadowx=4:shadowy=4:"
                f"enable='between(t,5,9)'"
            )

        # Red highlight box behind claim
        filters.append(
            f"drawbox=x=(iw-600)/2:y=h*0.37:w=600:h={len(claim_lines[:2])*95+20}:"
            f"color=0xe63946@'if(lt(t,5.2),(t-5)/0.2,if(lt(t,8.5),0.25,max(0,(9-t)/0.5*0.25)))':t=fill:"
            f"enable='between(t,5,9)'"
        )

    # ── Layer 5: CTA binary question (last 5s) — slides up ──────────────────
    if cta_clean:
        cta_lines = wrap_text(cta_clean, max_chars=28)
        for i, cl in enumerate(cta_lines[:2]):
            # Slide up: start at y=h, end at y=h*0.82
            y_expr = f"'if(lt(t,{cta_start+0.5}),h+(t-{cta_start})*(-h*0.18+h)*2,h*0.82+{i*55})'"
            filters.append(
                f"drawtext={font_arg}text='{cl}':"
                f"fontsize=52:"
                f"fontcolor='white@if(lt(t,{cta_start+0.4}),(t-{cta_start})/0.4,0.95)':"
                f"x=(w-text_w)/2:y={y_expr}:"
                f"shadowcolor=black@0.9:shadowx=3:shadowy=3:"
                f"enable='gte(t,{cta_start})'"
            )

        # CTA label
        filters.append(
            f"drawtext={font_arg}text='COMMENT BELOW 👇':"
            f"fontsize=32:"
            f"fontcolor='0xe63946@if(lt(t,{cta_start+0.6}),(t-{cta_start})/0.6,0.9)':"
            f"x=(w-text_w)/2:y=h*0.91:"
            f"shadowcolor=black@0.8:shadowx=2:shadowy=2:"
            f"enable='gte(t,{cta_start})'"
        )

    return ",".join(filters)

def apply_text_overlay(input_path, output_path, hook, key_claim, cta, duration):
    """Apply animated text overlay to a video file."""

    filter_complex = build_filter_complex(hook, key_claim, cta, duration, FONT_PATH)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", filter_complex,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "21",
        "-c:a", "copy",
        output_path
    ]

    log.info(f"  Applying text overlays...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        size = os.path.getsize(output_path)
        log.info(f"  ✅ Overlay applied: {output_path} ({size//1024}KB)")
        return output_path
    else:
        log.error(f"  ❌ FFmpeg error: {result.stderr[-400:]}")
        return None

def get_video_duration(path):
    r = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path
    ], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except: return 60.0

def process_scripted_videos(limit=3):
    """Apply text overlays to scripted videos that don't have them yet."""
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        SELECT id, title, winning_hook, script, caption, video_path
        FROM stories
        WHERE status IN ('scripted','queued')
        AND video_path IS NOT NULL
        ORDER BY score DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        log.info("No videos to overlay")
        return 0

    log.info(f"=== Text overlay — {len(rows)} videos ===")
    success = 0

    for r in rows:
        story_id, title, hook, script, caption, video_path = r

        if not video_path or not os.path.exists(video_path):
            log.warning(f"  Video not found: {video_path}")
            continue

        # Skip if already has overlay (filename contains _overlay)
        if "_overlay" in video_path:
            continue

        hook      = hook or title
        key_claim = extract_key_claim(script or title)
        cta       = extract_cta(caption or "")
        duration  = get_video_duration(video_path)

        output_path = video_path.replace(".mp4", "_overlay.mp4")

        log.info(f"  Processing: {title[:60]}")
        log.info(f"  Hook: {hook[:50]}")
        log.info(f"  Claim: {key_claim[:50]}")
        log.info(f"  CTA: {cta[:50]}")

        result = apply_text_overlay(video_path, output_path, hook, key_claim, cta, duration)

        if result:
            # Update DB to point to overlay version
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE stories SET video_path=? WHERE id=?", (output_path, story_id))
            conn.commit()
            conn.close()
            success += 1
            log.info(f"  ✅ Story {story_id} overlay complete")

    log.info(f"=== Overlay complete — {success}/{len(rows)} done ===")
    return success

if __name__ == "__main__":
    process_scripted_videos(limit=3)
