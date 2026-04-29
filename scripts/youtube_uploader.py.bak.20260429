#!/usr/bin/env python3
"""
90minWaffle YouTube Uploader
Uploads videos to YouTube with proper titles, descriptions, tags and thumbnails.
"""
import os
import json
import sqlite3
import logging
import re
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv('/root/90minwaffle/.env')

import google.oauth2.credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

DB_PATH     = "/root/90minwaffle/data/waffle.db"
TOKEN_FILE  = "/root/90minwaffle/youtube_token.json"
LOG_PATH    = "/root/90minwaffle/logs/youtube_uploader.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

FORMAT_CATEGORIES = {
    "F1": "Confirmed Transfer",
    "F2": "Transfer Rumour",
    "F3": "Match Preview",
    "F4": "Post Match",
    "F5": "Title Race",
    "F6": "Star Spotlight",
    "F7": "Hot Take",
}

def get_db(): return sqlite3.connect(DB_PATH)

def get_youtube_client():
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    credentials = google.oauth2.credentials.Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"],
    )
    return build("youtube", "v3", credentials=credentials)

def clean_text(text, max_len=100):
    """Clean text for YouTube title/description."""
    if not text: return ""
    # Keep common punctuation but remove problematic chars
    text = re.sub(r'[<>]', '', text)
    return text[:max_len].strip()

def build_title(story):
    """Build YouTube title — punchy, under 100 chars."""
    hook = story.get("winning_hook", "")
    title = story.get("title", "")
    fmt = story.get("format", "F7")
    category = FORMAT_CATEGORIES.get(fmt, "")

    # Use hook if it's punchy and short enough
    if hook and len(hook) < 80:
        return clean_text(f"{hook} #Shorts")
    return clean_text(f"{title} #Shorts")

def build_description(story):
    """Build YouTube description with script excerpt + hashtags."""
    script   = story.get("script", "")
    caption  = story.get("caption", "")
    source   = story.get("source", "")
    hook     = story.get("winning_hook", "")

    # Extract hashtags from caption
    hashtags = " ".join(re.findall(r'#\w+', caption))

    # First 200 chars of script as description
    script_excerpt = script[:300] + "..." if len(script) > 300 else script

    desc = f"""{hook}

{script_excerpt}

━━━━━━━━━━━━━━━━━━━━
🔔 Subscribe for daily football takes
💬 Drop your take in the comments
━━━━━━━━━━━━━━━━━━━━

Source: {source}

{hashtags}

#Football #FootballNews #90minWaffle #PremierLeague #Shorts #FootballShorts"""

    return desc[:5000]

def build_tags(story):
    """Build YouTube tags from caption hashtags + standard tags."""
    caption = story.get("caption", "")
    hashtags = re.findall(r'#(\w+)', caption)

    standard_tags = [
        "football", "soccer", "premier league", "football news",
        "transfer news", "football shorts", "90minwaffle",
        "football takes", "football analysis"
    ]

    all_tags = hashtags + standard_tags
    return list(dict.fromkeys(all_tags))[:15]  # Max 15 unique tags

def upload_video(story):
    """Upload a single video to YouTube."""
    video_path = story.get("video_path")
    if not video_path or not os.path.exists(video_path):
        log.error(f"  Video not found: {video_path}")
        return None

    try:
        youtube = get_youtube_client()

        title       = build_title(story)
        description = build_description(story)
        tags        = build_tags(story)

        log.info(f"  Uploading: {title[:70]}")
        log.info(f"  File: {video_path} ({os.path.getsize(video_path)//1024}KB)")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "17",  # Sports category
                "defaultLanguage": "en",
                "defaultAudioLanguage": "en",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            }
        }

        media = MediaFileUpload(
            video_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024*1024  # 1MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                log.info(f"  Upload progress: {progress}%")

        video_id = response.get("id")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        log.info(f"  ✅ Uploaded: {video_url}")
        return video_id

    except HttpError as e:
        log.error(f"  ❌ YouTube API error: {e}")
        return None
    except Exception as e:
        log.error(f"  ❌ Upload error: {e}")
        return None

def process_upload_queue(limit=3):
    """Upload queued videos to YouTube."""
    conn = get_db(); c = conn.cursor()
    c.execute("""
        SELECT id, title, source, score, format,
               winning_hook, script, caption, video_path
        FROM stories
        WHERE status = 'queued'
        AND video_path IS NOT NULL
        ORDER BY score DESC LIMIT ?
    """, (limit,))
    rows = c.fetchall(); conn.close()

    if not rows:
        log.info("No queued videos to upload")
        return 0

    log.info(f"=== YouTube upload — {len(rows)} videos ===")
    uploaded = 0

    for r in rows:
        story = {
            "id": r[0], "title": r[1], "source": r[2],
            "score": r[3], "format": r[4], "winning_hook": r[5],
            "script": r[6], "caption": r[7], "video_path": r[8]
        }

        log.info(f"Processing: {story['title'][:60]}")
        video_id = upload_video(story)

        if video_id:
            conn = get_db(); c = conn.cursor()
            c.execute("""
                UPDATE stories SET
                    status = 'published',
                    notes = COALESCE(notes, '') || ' YT:' || ?
                WHERE id = ?
            """, (video_id, story["id"]))
            conn.commit(); conn.close()
            uploaded += 1

    log.info(f"=== YouTube upload complete — {uploaded}/{len(rows)} ===")
    return uploaded

if __name__ == "__main__":
    process_upload_queue(limit=3)
