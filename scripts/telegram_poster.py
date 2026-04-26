#!/usr/bin/env python3
import asyncio,sqlite3,logging,os,re
from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime,timezone
from dotenv import load_dotenv
load_dotenv("/root/90minwaffle/.env")

DB_PATH="/root/90minwaffle/data/waffle.db"
LOG_PATH="/root/90minwaffle/logs/telegram_poster.log"
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s",handlers=[logging.FileHandler(LOG_PATH),logging.StreamHandler()])
log=logging.getLogger(__name__)

BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL=int(os.getenv("TELEGRAM_NEWS_CHANNEL",0))
INSIDE_CHANNEL=int(os.getenv("TELEGRAM_INSIDE_CHANNEL",0))

FORMAT_EMOJI={
    "F1":"✅","F2":"🔁","F3":"🏟","F4":"📊","F5":"🏆","F6":"⭐","F7":"🔥"
}

def get_db(): return sqlite3.connect(DB_PATH)

def build_news_message(story):
    fmt=story.get("format","F7")
    emoji=FORMAT_EMOJI.get(fmt,"📰")
    caption=story.get("caption","")
    source=story.get("source","")
    hook=story.get("winning_hook","")
    msg = emoji + " *" + hook + "*\n\n" + caption + "\n\n- " + source
    return msg


async def post_to_news(story):
    bot=Bot(token=BOT_TOKEN)
    video_path=story.get("video_path")
    msg=build_news_message(story)
    try:
        if video_path and os.path.exists(video_path):
            with open(video_path,"rb") as vf:
                await bot.send_video(
                    chat_id=NEWS_CHANNEL,
                    video=vf,
                    caption=msg,
                    parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=True
                )
        else:
            await bot.send_message(chat_id=NEWS_CHANNEL,text=msg,parse_mode=ParseMode.MARKDOWN)
        log.info(f"  Posted to News: {story["title"][:60]}")
        return True
    except Exception as e:
        log.error(f"  News post failed: {e}")
        return False

async def process_news_queue(limit=3):
    conn=get_db(); c=conn.cursor()
    c.execute("""SELECT id,title,source,score,format,winning_hook,caption,video_path
        FROM stories WHERE status="queued" AND video_path IS NOT NULL
        AND format IN ("F1","F2","F5","F7")
        ORDER BY score DESC LIMIT ?""",(limit,))
    rows=c.fetchall(); conn.close()
    if not rows: log.info("No stories for News channel"); return 0
    log.info(f"=== Posting {len(rows)} to News channel ===")
    posted=0
    for r in rows:
        story={"id":r[0],"title":r[1],"source":r[2],"score":r[3],"format":r[4],"winning_hook":r[5],"caption":r[6],"video_path":r[7]}
        if await post_to_news(story):
            conn=get_db(); c=conn.cursor()
            c.execute("UPDATE stories SET status='published' WHERE id=?",(story["id"],))
            conn.commit(); conn.close()
            posted+=1
    log.info(f"=== News posting done — {posted}/{len(rows)} ===")
    return posted

if __name__=="__main__":
    asyncio.run(process_news_queue(limit=3))
