#!/usr/bin/env python3
import os,sys,asyncio,logging,requests
sys.path.insert(0,"/root/90minwaffle/scripts")
from datetime import datetime,timezone
from dotenv import load_dotenv
from telegram import Bot,InlineKeyboardButton,InlineKeyboardMarkup
load_dotenv("/root/90minwaffle/.env")
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s")
log=logging.getLogger(__name__)
BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN")
REPORTS_CHAT_ID=int(os.getenv("TELEGRAM_REPORTS_CHAT_ID",0))
DISCORD_BREAKING=os.getenv("DISCORD_WEBHOOK_BREAKING_NEWS")
FAKE_STORY={"id":0,"title":"Declan Rice signs new long-term contract with Arsenal","url":"https://example.com/rice-arsenal","source":"The Athletic","score":95,"format":"F1","winning_hook":"Rice commits his future to the Gunners","caption":"Declan Rice has put pen to paper on a new deal at Arsenal. #Arsenal #DeclanRice #PremierLeague","competition":"PL"}
def _get_sportsdb():
    import importlib.util
    spec=importlib.util.spec_from_file_location("sportsdb","/root/90minwaffle/scripts/sportsdb.py")
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def post_discord(story):
    if not DISCORD_BREAKING: log.error("DISCORD_WEBHOOK_BREAKING_NEWS not set");return False
    embed={"author":{"name":"🚨  CONFIRMED TRANSFER [TEST]"},"title":story["title"][:256],"description":f"**{story['winning_hook']}**\n\n#Arsenal #DeclanRice #PremierLeague","color":0x00FF87,"fields":[{"name":"Source","value":story["source"],"inline":True}],"footer":{"text":"90minWaffle • TEST CARD — not live"},"timestamp":datetime.now(timezone.utc).isoformat()}
    try:
        sdb=_get_sportsdb()
        img=sdb.get_image_for_story(story["title"],story["winning_hook"])
        log.info(f"  Discord image: {img}")
        if img: embed["image"]={"url":img}
        else: log.warning("  Discord image: None")
    except Exception as e: log.warning(f"  Discord image failed: {e}")
    r=requests.post(DISCORD_BREAKING,json={"embeds":[embed]},timeout=15)
    if r.status_code in(200,204): log.info("  ✅ Discord posted");return True
    log.error(f"  ❌ Discord {r.status_code}: {r.text[:200]}");return False
async def post_telegram(story):
    if not REPORTS_CHAT_ID: log.error("TELEGRAM_REPORTS_CHAT_ID not set");return False
    bot=Bot(token=BOT_TOKEN)
    text="🚨 *CONFIRMED TRANSFER* \\[TEST\\]\n\n*Rice commits his future to the Gunners*\n\nDeclan Rice has put pen to paper on a new deal at Arsenal.\n\n— The Athletic\n\n#Arsenal #DeclanRice #PremierLeague\n\n━━━━━━━━━━━━━━━━━━━━\n🐦 @90minWaffle on X | 📺 YouTube | 🎵 TikTok"
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("🐦 @90minWaffle",url="https://twitter.com/90minwaffle"),InlineKeyboardButton("📺 YouTube",url="https://youtube.com/@90minwaffle")]])
    img=None
    try:
        sdb=_get_sportsdb()
        img=sdb.get_image_for_story(story["title"],story["winning_hook"])
        log.info(f"  Telegram image: {img}")
    except Exception as e: log.warning(f"  Telegram image failed: {e}")
    try:
        if img: await bot.send_photo(chat_id=REPORTS_CHAT_ID,photo=img,caption=text,parse_mode="Markdown",reply_markup=kb)
        else: log.warning("  Telegram image: None — text only");await bot.send_message(chat_id=REPORTS_CHAT_ID,text=text,parse_mode="Markdown",reply_markup=kb)
        log.info("  ✅ Telegram posted");return True
    except Exception as e: log.error(f"  ❌ Telegram failed: {e}");return False
async def main():
    log.info("=== test_card.py v1.8 ===")
    d=post_discord(FAKE_STORY);t=await post_telegram(FAKE_STORY)
    log.info(f"=== Discord={'✅' if d else '❌'}  Telegram={'✅' if t else '❌'} — no DB writes ===")
asyncio.run(main())
