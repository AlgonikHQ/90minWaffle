#!/usr/bin/env python3
import os, sqlite3, logging, requests, asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Bot

load_dotenv("/root/90minwaffle/.env")

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/card_generator.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))

WEBHOOKS = {
    "breaking_news":  os.getenv("DISCORD_WEBHOOK_BREAKING_NEWS"),
    "match_day":      os.getenv("DISCORD_WEBHOOK_MATCH_DAY"),
    "hot_takes":      os.getenv("DISCORD_WEBHOOK_HOT_TAKES"),
    "premier_league": os.getenv("DISCORD_WEBHOOK_PREMIER_LEAGUE"),
    "championship":   os.getenv("DISCORD_WEBHOOK_CHAMPIONSHIP"),
    "general":        os.getenv("DISCORD_WEBHOOK_GENERAL"),
}

FORMAT_DISCORD = {"F1":"breaking_news","F2":"breaking_news","F3":"match_day","F4":"match_day","F5":"premier_league","F6":"general","F7":"hot_takes"}
FORMAT_EMOJI   = {"F1":"🚨","F2":"📰","F3":"⚽","F4":"📊","F5":"🏆","F6":"⭐","F7":"🔥"}
FORMAT_LABEL   = {"F1":"CONFIRMED TRANSFER","F2":"TRANSFER RUMOUR","F3":"MATCH PREVIEW","F4":"POST-MATCH","F5":"TITLE RACE","F6":"STAR SPOTLIGHT","F7":"HOT TAKE"}
COLOUR_MAP     = {"F1":0x00FF87,"F2":0xE63946,"F3":0x4361EE,"F4":0xF77F00,"F5":0xFFD60A,"F6":0x7B2D8B,"F7":0xFF4500}

def get_db(): return sqlite3.connect(DB_PATH)

def build_discord_card(story):
    fmt=story["format"]
    hook=story.get("winning_hook") or story["title"]
    caption=story.get("caption") or ""
    hashtags=" ".join(w for w in caption.split() if w.startswith("#"))
    description=f"**{hook}**"
    if hashtags: description+=f"\n\n{hashtags}"
    embed={"author":{"name":f"{FORMAT_EMOJI.get(fmt,'🔥')}  {FORMAT_LABEL.get(fmt,'HOT TAKE')}"},"title":story["title"][:256],"description":description[:2048],"color":COLOUR_MAP.get(fmt,0xE63946),"fields":[{"name":"Source","value":story.get("source",""),"inline":True}],"footer":{"text":"90minWaffle • Football. Hot takes. No filter."},"timestamp":datetime.now(timezone.utc).isoformat()}
    if story.get("url"): embed["url"]=story["url"]
    return embed

def build_telegram_card(story):
    fmt=story["format"]
    hook=story.get("winning_hook") or story["title"]
    caption=story.get("caption") or ""
    source=story.get("source","")
    body_lines=[l for l in caption.split("\n") if not l.strip().startswith("#")]
    hashtags=" ".join(w for w in caption.split() if w.startswith("#"))
    body=" ".join(body_lines).strip()
    lines=[f"{FORMAT_EMOJI.get(fmt,'🔥')} *{FORMAT_LABEL.get(fmt,'HOT TAKE')}*","",f"*{hook}*"]
    if body: lines+=["",body]
    lines+=["",f"— {source}"]
    if hashtags: lines+=["",hashtags]
    lines+=["","━━━━━━━━━━━━━━━━━━━━","🐦 @90minWaffle on X | 📺 YouTube | 🎵 TikTok"]
    return "\n".join(lines)

def build_telegram_buttons(story):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons=[]
    if story.get("url"):
        buttons.append(InlineKeyboardButton("🔗 Read More", url=story["url"]))
    buttons.append(InlineKeyboardButton("🐦 @90minWaffle", url="https://twitter.com/90minwaffle"))
    buttons.append(InlineKeyboardButton("📺 YouTube", url="https://youtube.com/@90minwaffle"))
    buttons.append(InlineKeyboardButton("🎵 TikTok", url="https://tiktok.com/@90minwaffle"))
    # Row 1: Read More (full width if present), Row 2: socials
    keyboard=[]
    if story.get("url"):
        keyboard.append([buttons[0]])
        keyboard.append(buttons[1:])
    else:
        keyboard.append(buttons)
    return InlineKeyboardMarkup(keyboard)

def post_discord_card(story):
    t = (story.get("title") or "").lower(); src = story.get("source") or ""; comp = story.get("competition") or ""; is_chip = (src in ("BBC Championship","Football365")) or (comp == "ELC") or any(k in t for k in ["championship","middlesbrough","sheffield","norwich","watford","preston","stoke","cardiff","swansea","west brom","hull city","bristol city","coventry","plymouth","blackburn","ipswich","queens park","luton","derby"]); channel_key = "championship" if is_chip else FORMAT_DISCORD.get(story["format"],"general")
    webhook=WEBHOOKS.get(channel_key)
    if not webhook: return False
    try:
        r=requests.post(webhook,json={"embeds":[build_discord_card(story)]},timeout=15)
        if r.status_code in (200,204): log.info(f"  Discord #{channel_key}: {story['title'][:60]}"); return True
        log.error(f"  Discord {r.status_code}: {r.text[:100]}"); return False
    except Exception as e: log.error(f"  Discord failed: {e}"); return False

async def post_telegram_card(story):
    if not NEWS_CHANNEL: return False
    try:
        bot=Bot(token=BOT_TOKEN)
        text=build_telegram_card(story)
        markup=build_telegram_buttons(story)
        await bot.send_message(chat_id=NEWS_CHANNEL,text=text,parse_mode="Markdown",reply_markup=markup)
        log.info(f"  Telegram: {story['title'][:60]}"); return True
    except Exception as e: log.error(f"  Telegram failed: {e}"); return False

async def process_cards(limit=5):
    conn=get_db(); c=conn.cursor()
    c.execute("""SELECT id,title,url,source,score,format,winning_hook,caption FROM stories WHERE status='shippable' AND score>=60 AND (notes IS NULL OR notes NOT LIKE '%card_sent%') AND winning_hook IS NOT NULL AND winning_hook != '' ORDER BY score DESC LIMIT ?""",(limit,))
    rows=c.fetchall(); conn.close()
    if not rows: log.info("No stories for cards"); return 0
    log.info(f"=== Generating {len(rows)} cards ===")
    sent=0
    for r in rows:
        story={"id":r[0],"title":r[1],"url":r[2],"source":r[3],"score":r[4],"format":r[5],"winning_hook":r[6],"caption":r[7]}
        d=post_discord_card(story); t=await post_telegram_card(story)
        if d or t:
            conn=get_db(); c=conn.cursor()
            c.execute("UPDATE stories SET notes='card_sent' WHERE id=?",(story["id"],))
            conn.commit(); conn.close(); sent+=1
    log.info(f"=== Cards done — {sent}/{len(rows)} ===")
    return sent

if __name__=="__main__":
    asyncio.run(process_cards(limit=5))
