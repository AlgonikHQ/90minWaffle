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
    "breaking_news":     os.getenv("DISCORD_WEBHOOK_BREAKING_NEWS"),
    "match_day":         os.getenv("DISCORD_WEBHOOK_MATCH_DAY"),
    "hot_takes":         os.getenv("DISCORD_WEBHOOK_HOT_TAKES"),
    "premier_league":    os.getenv("DISCORD_WEBHOOK_PREMIER_LEAGUE"),
    "championship":      os.getenv("DISCORD_WEBHOOK_CHAMPIONSHIP"),
    "general":           os.getenv("DISCORD_WEBHOOK_GENERAL"),
    "tips":              os.getenv("DISCORD_WEBHOOK_BETS"),
    "bets":              os.getenv("DISCORD_WEBHOOK_BETS"),
    "womens_football":   os.getenv("DISCORD_WEBHOOK_WOMENS_FOOTBALL"),
    "world_cup":         os.getenv("DISCORD_WEBHOOK_WORLD_CUP"),
    "euros":             os.getenv("DISCORD_WEBHOOK_EUROS"),
    "domestic_trophies": os.getenv("DISCORD_WEBHOOK_DOMESTIC_TROPHIES"),
    "scottish_football": os.getenv("DISCORD_WEBHOOK_SCOTTISH_FOOTBALL"),
    "european_cups":     os.getenv("DISCORD_WEBHOOK_EUROPEAN_CUPS"),
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
    thumbnail=story.get("thumbnail_text") or ""
    hashtags=" ".join(w for w in caption.split() if w.startswith("#"))
    # Extract CTA question from caption for engagement
    cap_lines=[l.strip() for l in caption.split("\n") if l.strip()]
    cta_lines=[l for l in cap_lines if "?" in l and not l.startswith("#")]
    cta=cta_lines[0][:120] if cta_lines else ""
    # Build description: hook + CTA question if available
    description=f"**{hook}**"
    if cta: description+=f"\n\n_{cta}_"
    if hashtags: description+=f"\n\n{hashtags}"
    # Use thumbnail_text as title if available (punchy 2-4 word AI headline)
    # else fall back to cleaned article title
    source_clean=story.get("source","").replace(" Football","").replace(" Sport Football","").replace(" FC","").strip()
    embed_title = thumbnail if thumbnail else story["title"][:256]
    embed={"author":{"name":f"{FORMAT_EMOJI.get(fmt,'🔥')}  {FORMAT_LABEL.get(fmt,'HOT TAKE')}"},"title":embed_title[:256],"description":description[:2048],"color":COLOUR_MAP.get(fmt,0xE63946),"fields":[{"name":"Source","value":source_clean,"inline":True}],"footer":{"text":"90minWaffle • Football. Hot takes. No filter."},"timestamp":datetime.now(timezone.utc).isoformat()}
    if story.get("url"): embed["url"]=story["url"]
    # Image — waterfall (OG scrape > RSS media > Wikipedia > SportsDB > brand placeholder)
    # Local file paths (branded placeholder) are skipped for Discord — Telegram only
    try:
        from image_resolver import resolve_image
        img_url = resolve_image(story)
        if img_url and img_url.startswith("http"):
            embed["image"] = {"url": img_url}
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
    lines+=["","━━━━━━━━━━━━━━━━━━━━","_Football. Hot Takes. No Filter._"]
    return "\n".join(lines)

def build_telegram_buttons(story):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    buttons=[]
    if story.get("url"):
        buttons.append(InlineKeyboardButton("🔗 Read More", url=story["url"]))
    buttons.append(InlineKeyboardButton("🐦 @90minWaffle", url="https://twitter.com/90minwaffle"))
    buttons.append(InlineKeyboardButton("📺 YouTube", url="https://youtube.com/@90minwaffle"))
    buttons.append(InlineKeyboardButton("🎵 TikTok", url="https://tiktok.com/@90minwaffle"))
    keyboard=[]
    if story.get("url"):
        keyboard.append([buttons[0]])
        keyboard.append(buttons[1:])
    else:
        keyboard.append(buttons)
    return InlineKeyboardMarkup(keyboard)

def _route_channel(story):
    """
    Single source of truth for Discord channel routing in card_generator.
    Delegates to the same classify_competition logic as discord_poster
    by importing from season_teams — both files stay in sync automatically.
    """
    import sys, re
    sys.path.insert(0, "/root/90minwaffle/scripts")
    try:
        from season_teams import (
            PREMIER_LEAGUE, CHAMPIONSHIP, SCOTTISH_PREMIERSHIP,
            WOMENS_KEYWORDS, SCOTTISH_COMP_KEYWORDS, SCOTTISH_SOURCES,
            EUROPEAN_CUPS_KEYWORDS, DOMESTIC_TROPHIES_KEYWORDS,
            WORLD_CUP_KEYWORDS, EUROS_KEYWORDS, CHAMPIONSHIP_COMP_KEYWORDS,
        )
    except ImportError as e:
        log.error(f"season_teams import failed in card_generator: {e}")
        return "general"

    t   = (story.get("title") or "").lower()
    src = (story.get("source") or "").lower()
    fmt = story.get("format", "F7")

    def _team_match(title_lower, team_set):
        for team in team_set:
            pattern = r'\b' + re.escape(team) + r'\b'
            if re.search(pattern, title_lower):
                return True
        return False

    # F9 always womens_football
    if fmt == "F9":
        return "womens_football"

    # F8 always bets
    if fmt == "F8":
        return "bets"

    # 1. Women's football — first, catches women's UCL before european_cups
    if any(kw in t for kw in WOMENS_KEYWORDS) or any(kw in src for kw in WOMENS_KEYWORDS):
        return "womens_football"

    # 2. World Cup
    if any(kw in t for kw in WORLD_CUP_KEYWORDS):
        return "world_cup"

    # 3. Euros / Nations League
    if any(kw in t for kw in EUROS_KEYWORDS):
        return "euros"

    # 4. European club cups
    if any(kw in t for kw in EUROPEAN_CUPS_KEYWORDS):
        return "european_cups"

    # 5. Domestic trophies — hardlined English cups only
    if any(kw in t for kw in DOMESTIC_TROPHIES_KEYWORDS):
        return "domestic_trophies"

    # 6. Scottish football
    if any(kw in t for kw in SCOTTISH_COMP_KEYWORDS):
        return "scottish_football"
    if any(kw in src for kw in SCOTTISH_SOURCES):
        return "scottish_football"
    has_scottish = _team_match(t, SCOTTISH_PREMIERSHIP)
    if has_scottish and not any(kw in t for kw in EUROPEAN_CUPS_KEYWORDS):
        return "scottish_football"

    # 7. Championship — competition keyword first, team names secondary
    if any(kw in t for kw in CHAMPIONSHIP_COMP_KEYWORDS):
        return "championship"
    if _team_match(t, CHAMPIONSHIP) and not _team_match(t, PREMIER_LEAGUE):
        return "championship"

    # 8. Transfers — confirmed to breaking_news, rumour to breaking_news if PL club
    confirmed = ["here we go","confirmed","signs for","signed for","done deal",
                 "completes move","joins","unveiled","agrees deal","medical booked"]
    rumour    = ["transfer","bid","loan fee","release clause","transfer target",
                 "transfer talks","transfer approach"]
    is_confirmed = any(k in t for k in confirmed)
    is_rumour    = any(k in t for k in rumour)
    is_pl_club   = _team_match(t, PREMIER_LEAGUE)

    if fmt in ("F1","F2") and is_confirmed:
        return "breaking_news"
    if fmt in ("F1","F2") and is_rumour and is_pl_club:
        return "breaking_news"
    if fmt in ("F1","F2"):
        return "general"

    # 9. Match content
    if fmt in ("F3","F4"):
        return "match_day"

    # 10. PL title race narrative
    pl_narrative = ["title race","title charge","top of the table","points clear",
                    "relegation battle","drop zone","staying up","league leaders",
                    "premier league title","golden boot"]
    if any(k in t for k in pl_narrative) and is_pl_club:
        return "premier_league"

    # 11. Hot takes
    if fmt == "F7":
        return "hot_takes"

    # 12. Star spotlight with PL club
    if fmt == "F6" and is_pl_club:
        return "premier_league"

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
        # Image — waterfall (OG scrape > RSS media > Wikipedia > SportsDB > brand placeholder)
        img_url = None
        try:
            from image_resolver import resolve_image
            img_url = resolve_image(story)
        except Exception as e:
            log.warning("Telegram image failed: " + str(e))
        if img_url and img_url.startswith("http"):
            # Remote URL — send directly
            await bot.send_photo(chat_id=NEWS_CHANNEL, photo=img_url,
                caption=text, parse_mode="Markdown", reply_markup=markup)
        elif img_url and img_url.startswith("/"):
            # Local file path — branded placeholder, send as bytes
            with open(img_url, "rb") as f:
                await bot.send_photo(chat_id=NEWS_CHANNEL, photo=f,
                    caption=text, parse_mode="Markdown", reply_markup=markup)
        else:
            await bot.send_message(chat_id=NEWS_CHANNEL, text=text,
                parse_mode="Markdown", reply_markup=markup)
        log.info(f"  Telegram: {story['title'][:60]}"); return True
    except Exception as e: log.error(f"  Telegram failed: {e}"); return False

async def process_cards(limit=10):
    conn=get_db(); c=conn.cursor()
    c.execute("""SELECT id,title,url,source,score,format,winning_hook,caption,thumbnail_text FROM stories WHERE status IN ('shippable','holding','scripted') AND score>=30 AND (notes IS NULL OR notes NOT LIKE '%card_sent%') ORDER BY score DESC LIMIT ?""",(limit,))
    rows=c.fetchall(); conn.close()
    if not rows: log.info("No stories for cards"); return 0
    log.info(f"=== Generating {len(rows)} cards ===")
    sent=0
    for r in rows:
        story={"id":r[0],"title":r[1],"url":r[2],"source":r[3],"score":r[4],"format":r[5],"winning_hook":r[6] or r[1],"caption":r[7] or "","thumbnail_text":r[8] or ""}
        d=post_discord_card(story); t=await post_telegram_card(story)
        if d or t:
            conn=get_db(); c=conn.cursor()
            c.execute("UPDATE stories SET notes='card_sent' WHERE id=?",(story["id"],))
            conn.commit(); conn.close(); sent+=1
    log.info(f"=== Cards done — {sent}/{len(rows)} ===")
    return sent

if __name__=="__main__":
    asyncio.run(process_cards(limit=5))
