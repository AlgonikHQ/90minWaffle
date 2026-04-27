import anthropic
import sqlite3
import json
import logging
import os
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv('/root/90minwaffle/.env')

DB_PATH = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/script_gen.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

FORMAT_LENGTHS = {
    "F1": 60, "F2": 45, "F3": 65, "F4": 55,
    "F5": 70, "F6": 50, "F7": 40
}

FORMAT_NAMES = {
    "F1": "Confirmed Transfer",
    "F2": "Transfer Rumour",
    "F3": "Match Preview",
    "F4": "Post-Match Reaction",
    "F5": "Title Race / Narrative",
    "F6": "Star Spotlight",
    "F7": "Hot Take",
}

SYSTEM_PROMPT = """You are the script writer for 90minWaffle, a UK football short-form video brand.

VOICE: Hot-take merchant. Loud, opinionated, divisive. UK football vocabulary: 'bottled it', 'cooked', 'doing a Spurs', 'Pep masterclass'. Short, punchy sentences.

HARD RULES — never break these:
- Never attack individual players' character, mental health, families or personal lives
- Never reference race, religion, nationality in a negative way
- Never attack specific fans or fan groups
- Never attack referees as people (decisions yes, person no)
- Never use: 'Did you know', 'Let's dive into', 'Hey football fans', 'Hey guys', 'In this video', 'Like and subscribe'
- No intro. First word is the hook. Hard cut straight into content.
- Sign-off: state the answer to the video's setup → pivot to a binary question. NEVER 'follow for more'.

OUTPUT FORMAT: Respond only in valid JSON, no markdown, no preamble.
{
  "hook_1": "...",
  "hook_2": "...",
  "hook_3": "...",
  "hook_scores": {"hook_1": 0-100, "hook_2": 0-100, "hook_3": 0-100},
  "winning_hook": "hook_1|hook_2|hook_3",
  "mainstream_angle": "full script using winning hook, mainstream take",
  "contrarian_angle": "full script using winning hook, contrarian take with steel-man",
  "winning_script": "mainstream|contrarian",
  "caption": "line 1 hook\\nline 2 question\\n#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5",
  "thumbnail_text": "2-4 word ALL CAPS thumbnail headline"
}"""

def build_prompt(story, fmt):
    length = FORMAT_LENGTHS.get(fmt, 55)
    format_name = FORMAT_NAMES.get(fmt, "Football News")
    contrarian = fmt in ["F5", "F7"]
    sometimes = fmt in ["F2", "F3", "F4"]

    contrarian_instruction = ""
    if contrarian:
        contrarian_instruction = "Contrarian angle is REQUIRED for this format. Steel-man rule: acknowledge the mainstream view fairly before disagreeing."
    elif sometimes:
        contrarian_instruction = "Generate both angles. Pick the stronger one as winning_script."
    else:
        contrarian_instruction = "Contrarian angle not required. Set winning_script to 'mainstream'."

    return f"""Generate a 90minWaffle video script for this story:

HEADLINE: {story['title']}
SOURCE: {story['source']} (Tier {story['source_tier']})
FORMAT: {fmt} — {format_name}
TARGET LENGTH: ~{length} seconds of spoken word (~{length * 2} words)
SCORE: {story['score']}/100
Generate 3 hook variants. Pick the highest scoring one as winning_hook.
Scripts must end with: state the answer -> binary question CTA.
IMPORTANT: Your entire response must be a single valid JSON object. No markdown, no explanation, no preamble. Start your response with {{ and end with }}."""


def get_db():
    return sqlite3.connect(DB_PATH)

def generate_script(story):
    fmt = story.get("format", "F7")
    prompt = build_prompt(story, fmt)

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    log.info(f"Generating script for: {story['title'][:70]}")
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        result = json.loads(raw)
        log.info(f"  ✅ Script generated — winning hook: {result.get('winning_hook')}, script: {result.get('winning_script')}")
        return result

    except json.JSONDecodeError as e:
        log.error(f"  ❌ JSON parse error: {e}")
        log.error(f"  Raw response: {raw[:300]}")
        return None
    except Exception as e:
        log.error(f"  ❌ API error: {e}")
        return None

def save_script(story_id, result):
    conn = get_db()
    c = conn.cursor()

    # Handle both response shapes:
    # Simple: {"winning_hook": "text", "script": "..."}
    # Dual-angle: {"winning_hook": "text", "mainstream_angle": "...", "contrarian_angle": "...", "winning_script": "mainstream|contrarian"}
    winning_hook_text = result.get("winning_hook", "")
    if result.get("script"):
        winning_script = result.get("script", "")
    else:
        winning_script_key = result.get("winning_script", "mainstream")
        winning_script = result.get(f"{winning_script_key}_angle", "")

    c.execute('''
        UPDATE stories SET
            hook_1 = ?,
            hook_2 = ?,
            hook_3 = ?,
            winning_hook = ?,
            script = ?,
            caption = ?,
            status = 'scripted'
        WHERE id = ?
    ''', (
        result.get("hook_variants", [None, None, None])[0] if result.get("hook_variants") else result.get("hook_1"),
        result.get("hook_variants", [None, None, None])[1] if result.get("hook_variants") else result.get("hook_2"),
        result.get("hook_variants", [None, None, None])[2] if result.get("hook_variants") else result.get("hook_3"),
        winning_hook_text,
        winning_script,
        result.get("caption"),
        story_id
    ))
    conn.commit()
    conn.close()

def process_shippable_stories(limit=3):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT id, title, url, source, source_tier, score, format
        FROM stories
        WHERE status = 'shippable'
        ORDER BY score DESC
        LIMIT ?
    ''', (limit,))
    rows = c.fetchall()
    conn.close()

    stories = [
        {"id": r[0], "title": r[1], "url": r[2], "source": r[3],
         "source_tier": r[4], "score": r[5], "format": r[6]}
        for r in rows
    ]

    log.info(f"=== Script generation — {len(stories)} stories to process ===")
    success = 0
    for story in stories:
        result = generate_script(story)
        if result:
            save_script(story["id"], result)
            success += 1

    log.info(f"=== Done — {success}/{len(stories)} scripts generated ===")
    return success

if __name__ == "__main__":
    process_shippable_stories(limit=3)
