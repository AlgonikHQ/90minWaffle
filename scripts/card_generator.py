#!/usr/bin/env python3
import os, sqlite3, logging, requests, asyncio, sys
sys.path.insert(0, "/root/90minwaffle/scripts")
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Bot

load_dotenv("/root/90minwaffle/.env")

DB_PATH  = "/root/90minwaffle/data/waffle.db"
LOG_PATH = "/root/90minwaffle/logs/card_generator.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)
try:
    import sportsdb as sdb
except:sdb=None

BOT_TOKEN    = os.getenv("TELEGRAM_BOT_TOKEN")
NEWS_CHANNEL = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))

WEBHOOKS = {
    "breaking_news":  os.getenv("DISCORD_WEBHOOK_BREAKING_NEWS"),
    "match_day":      os.getenv("DISCORD_WEBHOOK_MATCH_DAY"),
    "hot_takes":      os.getenv("DISCORD_WEBHOOK_HOT_TAKES"),
    "premier_league": os.getenv("DISCORD_WEBHOOK_PREMIER_LEAGUE"),
    "championship":   os.getenv("DISCORD_WEBHOOK_CHAMPIONSHIP"),
    "general":        os.getenv("DISCORD_WEBHOOK_GENERAL"),
    "tips":           os.getenv("DISCORD_WEBHOOK_BETS"),
}

FORMAT_DISCORD = {"F1":"breaking_news","F2":"breaking_news","F3":"match_day","F4":"match_day","F5":"premier_league","F6":"general","F7":"hot_takes","F8":"tips"}
FORMAT_EMOJI   = {"F1":"🚨","F2":"📰","F3":"⚽","F4":"📊","F5":"🏆","F6":"⭐","F7":"🔥","F8":"🎯","F9":"👩"}
FORMAT_LABEL   = {"F1":"CONFIRMED TRANSFER","F2":"TRANSFER RUMOUR","F3":"MATCH PREVIEW","F4":"POST-MATCH","F5":"TITLE RACE","F6":"STAR SPOTLIGHT","F7":"HOT TAKE","F8":"TIPS & BETS","F9":"WOMENS FOOTBALL"}
COLOUR_MAP     = {"F1":0x00FF87,"F2":0xE63946,"F3":0x4361EE,"F4":0xF77F00,"F5":0xFFD60A,"F6":0x7B2D8B,"F7":0xFF4500,"F8":0x00B4D8,"F9":0xFF69B4}

def get_db(): return sqlite3.connect(DB_PATH)

def _get_sportsdb():
    import importlib.util, sys
    spec = importlib.util.spec_from_file_location("sportsdb", "/root/90minwaffle/scripts/sportsdb.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def build_discord_card(story):
    fmt=story["format"]
    hook=story.get("winning_hook") or story["title"]
    caption=story.get("caption") or ""
    hashtags=" ".join(w for w in caption.split() if w.startswith("#"))
    description=f"**{hook}**"
    if hashtags: description+=f"\n\n{hashtags}"
    embed={"author":{"name":f"{FORMAT_EMOJI.get(fmt,'🔥')}  {FORMAT_LABEL.get(fmt,'HOT TAKE')}"},"title":story["title"][:256],"description":description[:2048],"color":COLOUR_MAP.get(fmt,0xE63946),"fields":[{"name":"Source","value":story.get("source",""),"inline":True}],"footer":{"text":"90minWaffle • Football. Hot takes. No filter."},"timestamp":datetime.now(timezone.utc).isoformat()}
    if story.get("url"): embed["url"]=story["url"]
    # Image — 4-layer waterfall (OG scrape > RSS media > SportsDB > badge)
    try:
        from image_resolver import resolve_image
        img_url = resolve_image(story)
        if img_url: embed["image"] = {"url": img_url}
    except Exception as e:
        log.warning("Discord image failed: " + str(e))
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

def _route_channel(story):
    """Single source of truth for Discord channel routing."""
    t   = (story.get("title") or "").lower()
    src = story.get("source") or ""
    fmt = story.get("format", "F6")

    champ_clubs = [
        "middlesbrough","sheffield united","sheffield wednesday","norwich",
        "watford","preston","stoke","cardiff","swansea","west brom","hull",
        "bristol city","coventry","plymouth","blackburn","ipswich","luton",
        "derby","millwall","sunderland","leeds","burnley","oxford","portsmouth",
        "qpr","queens park rangers"
    ]
    ucl_terms = [
        "champions league","ucl","europa league","conference league",
        "semi-final","quarter-final","second leg","first leg","aggregate"
    ]
    pl_clubs = [
        "arsenal","manchester city","man city","liverpool","chelsea",
        "tottenham","spurs","newcastle","aston villa","west ham","fulham",
        "everton","brighton","crystal palace","brentford","wolves",
        "nottingham forest","forest","bournemouth","manchester united","man utd"
    ]
    pl_narrative = [
        "title race","title charge","top of the table","points clear",
        "points behind","relegation battle","drop zone","staying up",
        "top four","top 4","european spot","premier league title","prem title",
        "golden boot","league leaders"
    ]
    kit_terms   = ["kit","strip","jersey","shirt release","third kit","home kit","away kit","vineyard","leaked kit"]
    injury_terms= ["injur","surgery","ruled out","set to miss","facial","scan results","out for","fitness doubt"]
    personal_terms = ["commercial","advert","beer ","campaign","retires","retirement","award","nominated","charity"]
    wc_terms    = ["world cup","world cup 2026","squad announcement","nations league","international break","warm-up"]
    confirmed   = ["here we go","confirmed","signs for","signed for","done deal","completes move","joins","unveiled","agrees deal","medical booked"]
    rumour      = ["transfer","bid","loan fee","release clause","transfer target","transfer talks","transfer approach"]

    is_champ    = (src == "BBC Championship") or any(k in t for k in champ_clubs)
    is_ucl      = any(k in t for k in ucl_terms)
    is_pl_club  = any(k in t for k in pl_clubs)
    is_pl_narr  = any(k in t for k in pl_narrative)
    is_kit      = any(k in t for k in kit_terms)
    is_injury   = any(k in t for k in injury_terms)
    is_personal = any(k in t for k in personal_terms)
    is_wc       = any(k in t for k in wc_terms)
    is_confirmed= any(k in t for k in confirmed)
    is_rumour   = any(k in t for k in rumour)

    # 1. Tips
    if fmt == "F8": return "bets"
    # 1b. Women's football — always general
    if fmt == "F9": return "general"
    # 2. Championship
    if is_champ: return "championship"
    # 3. Confirmed transfer — breaking news
    if fmt in ("F1","F2") and is_confirmed: return "breaking_news"
    # 4. Transfer rumour with PL club — breaking news
    if fmt in ("F1","F2") and is_rumour and is_pl_club: return "breaking_news"
    # 5. Transfer rumour without PL club — general
    if fmt in ("F1","F2"): return "general"
    # 6. Kit/personal/World Cup — general
    if is_kit or is_personal or is_wc: return "general"
    # 7. Injury — general
    if is_injury: return "general"
    # 8. UCL match content — match_day
    if is_ucl and fmt in ("F3","F4"): return "match_day"
    # 9. UCL other — breaking_news
    if is_ucl and fmt in ("F1","F2"): return "breaking_news"
    # 10. All other match previews/results — match_day
    if fmt in ("F3","F4"): return "match_day"
    # 11. PL title race/relegation — premier_league (PL clubs only)
    if is_pl_narr and is_pl_club: return "premier_league"
    # 12. Hot takes — hot_takes
    if fmt == "F7": return "hot_takes"
    # 13. Star spotlight with PL club — premier_league
    if fmt == "F6" and is_pl_club and not is_kit and not is_injury: return "premier_league"
    # 14. Everything else — general
    return "general"


def post_discord_card(story):
    channel_key = _route_channel(story)
    webhook = WEBHOOKS.get(channel_key)
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
        # Try to get best image — 4-layer waterfall
        img_url = None
        try:
            from image_resolver import resolve_image
            img_url = resolve_image(story)
        except Exception as e:
            log.warning("Telegram image failed: " + str(e))
        if img_url:
            await bot.send_photo(chat_id=NEWS_CHANNEL, photo=img_url,
                caption=text, parse_mode="Markdown", reply_markup=markup)
        else:
            await bot.send_message(chat_id=NEWS_CHANNEL,text=text,parse_mode="Markdown",reply_markup=markup)
        log.info(f"  Telegram: {story['title'][:60]}"); return True
    except Exception as e: log.error(f"  Telegram failed: {e}"); return False

async def process_cards(limit=10):
    conn=get_db(); c=conn.cursor()
    c.execute("""SELECT id,title,url,source,score,format,winning_hook,caption FROM stories WHERE status IN ('shippable','holding') AND score>=45 AND (notes IS NULL OR notes NOT LIKE '%card_sent%') ORDER BY score DESC LIMIT ?""",(limit,))
    rows=c.fetchall(); conn.close()
    if not rows: log.info("No stories for cards"); return 0
    log.info(f"=== Generating {len(rows)} cards ===")
    sent=0
    for r in rows:
        story={"id":r[0],"title":r[1],"url":r[2],"source":r[3],"score":r[4],"format":r[5],"winning_hook":r[6] or r[1],"caption":r[7] or ""}
        d=post_discord_card(story); t=await post_telegram_card(story)
        if d or t:
            conn=get_db(); c=conn.cursor()
            c.execute("UPDATE stories SET notes='card_sent' WHERE id=?",(story["id"],))
            conn.commit(); conn.close(); sent+=1
    log.info(f"=== Cards done — {sent}/{len(rows)} ===")
    return sent

if __name__=="__main__":
    asyncio.run(process_cards(limit=5))
