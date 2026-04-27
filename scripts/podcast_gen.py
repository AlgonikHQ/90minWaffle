#!/usr/bin/env python3
import os, json, sqlite3, logging, asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

CACHE_DIR = Path("/root/90minwaffle/data/cache")
DB_PATH = "/root/90minwaffle/data/waffle.db"
OUTPUT_DIR = Path("/root/90minwaffle/data/podcasts")
LOG_PATH = "/root/90minwaffle/logs/podcast_gen.log"
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
INSIDE_CHANNEL = int(os.getenv("TELEGRAM_INSIDE_CHANNEL", 0))
NEWS_CHANNEL = int(os.getenv("TELEGRAM_NEWS_CHANNEL", 0))

def get_db(): return sqlite3.connect(DB_PATH)

def load_cache(name):
    p = CACHE_DIR / (name + ".json")
    if not p.exists(): return None
    try: return json.loads(p.read_text())
    except: return None

def get_table(comp):
    d = load_cache("standings_" + comp)
    if not d or "standings" not in d: return []
    return d["standings"][0].get("table", [])

def get_scorers(comp, limit=5):
    d = load_cache("scorers_" + comp)
    if not d or "scorers" not in d: return []
    return d["scorers"][:limit]

def get_recent_results(comp, limit=10):
    d = load_cache("matches_" + comp)
    if not d or "matches" not in d: return []
    finished = [m for m in d["matches"] if m.get("status") == "FINISHED"]
    finished.sort(key=lambda x: x.get("utcDate",""), reverse=True)
    return finished[:limit]

def get_upcoming(comp, limit=5):
    d = load_cache("matches_" + comp)
    if not d or "matches" not in d: return []
    upcoming = [m for m in d["matches"] if m.get("status") in ("SCHEDULED","TIMED")]
    return upcoming[:limit]

def get_top_stories(limit=10):
    conn = get_db(); c = conn.cursor()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    c.execute("""SELECT title, source, score, format, winning_hook, caption
        FROM stories WHERE score >= 60
        AND date(fetched_at) >= ?
        ORDER BY score DESC LIMIT ?""", (week_ago, limit))
    rows = c.fetchall(); conn.close()
    return [{"title":r[0],"source":r[1],"score":r[2],"format":r[3],"hook":r[4],"caption":r[5]} for r in rows]

def get_hot_takes(limit=5):
    conn = get_db(); c = conn.cursor()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    c.execute("""SELECT title, source, score, winning_hook, caption
        FROM stories WHERE format="F7"
        AND date(fetched_at) >= ?
        ORDER BY score DESC LIMIT ?""", (week_ago, limit))
    rows = c.fetchall(); conn.close()
    return [{"title":r[0],"source":r[1],"score":r[2],"hook":r[3],"caption":r[4]} for r in rows]

def build_pdf(output_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm, topMargin=15*mm, bottomMargin=15*mm)

    # Colours
    C_BLACK   = HexColor("#0D0D0D")
    C_GREEN   = HexColor("#00FF87")
    C_ORANGE  = HexColor("#FF6B35")
    C_PURPLE  = HexColor("#3D0059")
    C_GREY    = HexColor("#F4F4F4")
    C_MUTED   = HexColor("#888888")
    C_WHITE   = white

    styles = getSampleStyleSheet()
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).strftime("%d %b")
    week_end = now.strftime("%d %b %Y")

    def style(name, **kw):
        return ParagraphStyle(name, **kw)

    S_COVER_TITLE = style("ct", fontSize=36, leading=42, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT)
    S_COVER_SUB   = style("cs", fontSize=14, leading=20, textColor=C_MUTED, fontName="Helvetica", alignment=TA_LEFT)
    S_COVER_DATE  = style("cd", fontSize=11, leading=16, textColor=C_MUTED, fontName="Helvetica", alignment=TA_LEFT)
    S_SECTION     = style("sec", fontSize=16, leading=22, textColor=C_WHITE, fontName="Helvetica-Bold", alignment=TA_LEFT, backColor=C_PURPLE, borderPad=6)
    S_STORY_HOOK  = style("sh", fontSize=13, leading=18, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT)
    S_STORY_BODY  = style("sb", fontSize=10, leading=15, textColor=HexColor("#333333"), fontName="Helvetica", alignment=TA_LEFT)
    S_SOURCE      = style("sr", fontSize=9, leading=13, textColor=C_MUTED, fontName="Helvetica-Oblique", alignment=TA_LEFT)
    S_SCRIPT_INTRO= style("si", fontSize=11, leading=17, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT)
    S_SCRIPT_BODY = style("scb", fontSize=10, leading=16, textColor=HexColor("#1a1a1a"), fontName="Helvetica", alignment=TA_LEFT)
    S_TABLE_HDR   = style("th", fontSize=9, leading=12, textColor=C_WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER)
    S_TABLE_CELL  = style("tc", fontSize=9, leading=12, textColor=C_BLACK, fontName="Helvetica", alignment=TA_CENTER)
    S_TABLE_TEAM  = style("tt", fontSize=9, leading=12, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT)
    S_FOOTER      = style("ft", fontSize=8, leading=11, textColor=C_MUTED, fontName="Helvetica", alignment=TA_CENTER)
    S_LABEL       = style("lb", fontSize=9, leading=12, textColor=C_ORANGE, fontName="Helvetica-Bold", alignment=TA_LEFT)

    story = []

    # ── COVER ──────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("90minWaffle", S_COVER_TITLE))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("Weekly Football Podcast Script", S_COVER_SUB))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("Week of " + week_start + " – " + week_end, S_COVER_DATE))
    story.append(Spacer(1, 4*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=C_GREEN))
    story.append(Spacer(1, 8*mm))

    # ── INTRO SCRIPT ──────────────────────────────────────────────────────────
    story.append(Paragraph("INTRO", S_SECTION))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("[HOST — READ ALOUD]", S_SCRIPT_INTRO))
    story.append(Spacer(1, 2*mm))

    pl_table = get_table("PL")
    leader = pl_table[0] if pl_table else None
    second = pl_table[1] if len(pl_table) > 1 else None
    scorers = get_scorers("PL", 3)

    if leader and second:
        gap = leader["points"] - second["points"]
        games_left = 38 - leader["playedGames"]
        intro_text = (
            "Welcome back to 90minWaffle — the podcast where football meets hot takes and zero filter. "
            "I\'m your host and this is your weekly roundup of everything that mattered in football this week. "
            "We\'ve got the stories, the stats, the takes — and as always, we\'re not holding back. "
            "Let\'s get into it. "
            "First up — the Premier League title race. " +
            leader["team"]["name"].replace(" FC","") + " sit top with " + str(leader["points"]) +
            " points — " + str(gap) + " clear of " + second["team"]["name"].replace(" FC","") +
            " with " + str(games_left) + " games to go. "
        )
        if scorers:
            top = scorers[0]
            intro_text += (top["player"]["name"] + " leads the golden boot race with " +
                str(top["goals"]) + " goals. The question is — can anyone catch him?")
    else:
        intro_text = "Welcome back to 90minWaffle — the podcast where football meets hot takes and zero filter. Let\'s get into this week\'s biggest stories."

    story.append(Paragraph(intro_text, S_SCRIPT_BODY))
    story.append(Spacer(1, 6*mm))

    # ── PREMIER LEAGUE TABLE ─────────────────────────────────────────────────
    story.append(Paragraph("PREMIER LEAGUE — TOP 6", S_SECTION))
    story.append(Spacer(1, 3*mm))

    if pl_table:
        tdata = [[
            Paragraph("Pos", S_TABLE_HDR), Paragraph("Team", S_TABLE_HDR),
            Paragraph("P", S_TABLE_HDR), Paragraph("W", S_TABLE_HDR),
            Paragraph("D", S_TABLE_HDR), Paragraph("L", S_TABLE_HDR),
            Paragraph("GD", S_TABLE_HDR), Paragraph("Pts", S_TABLE_HDR),
            Paragraph("Form", S_TABLE_HDR)
        ]]
        for r in pl_table[:6]:
            form_raw = r.get("form","") or ""
            form_str = " ".join(list(form_raw[-5:])) if form_raw else "-"
            tdata.append([
                Paragraph(str(r["position"]), S_TABLE_CELL),
                Paragraph(r["team"]["name"].replace(" FC","").replace(" AFC",""), S_TABLE_TEAM),
                Paragraph(str(r["playedGames"]), S_TABLE_CELL),
                Paragraph(str(r["won"]), S_TABLE_CELL),
                Paragraph(str(r["draw"]), S_TABLE_CELL),
                Paragraph(str(r["lost"]), S_TABLE_CELL),
                Paragraph(("{:+d}".format(r["goalDifference"])), S_TABLE_CELL),
                Paragraph(str(r["points"]), S_TABLE_CELL),
                Paragraph(form_str, S_TABLE_CELL),
            ])
        col_widths = [12*mm, 52*mm, 12*mm, 12*mm, 12*mm, 12*mm, 14*mm, 14*mm, 30*mm]
        t = Table(tdata, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), C_PURPLE),
            ("BACKGROUND", (0,1), (-1,1), HexColor("#E8FFE8")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_GREY]),
            ("GRID", (0,0), (-1,-1), 0.3, HexColor("#DDDDDD")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 3*mm))

    # Top Scorers
    if scorers:
        story.append(Paragraph("TOP SCORERS", S_LABEL))
        scorer_data = [[Paragraph("Rank", S_TABLE_HDR), Paragraph("Player", S_TABLE_HDR),
            Paragraph("Team", S_TABLE_HDR), Paragraph("Goals", S_TABLE_HDR), Paragraph("Assists", S_TABLE_HDR)]]
        for i, s in enumerate(scorers, 1):
            scorer_data.append([
                Paragraph(str(i), S_TABLE_CELL),
                Paragraph(s["player"]["name"], S_TABLE_TEAM),
                Paragraph(s["team"]["name"].replace(" FC",""), S_TABLE_CELL),
                Paragraph(str(s["goals"]), S_TABLE_CELL),
                Paragraph(str(s.get("assists",0) or 0), S_TABLE_CELL),
            ])
        st = Table(scorer_data, colWidths=[12*mm, 55*mm, 50*mm, 18*mm, 18*mm])
        st.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), C_ORANGE),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_GREY]),
            ("GRID", (0,0), (-1,-1), 0.3, HexColor("#DDDDDD")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(st)
    story.append(Spacer(1, 6*mm))

    # ── CHAMPIONSHIP TABLE ────────────────────────────────────────────────────
    champ_table = get_table("ELC")
    if champ_table:
        story.append(Paragraph("CHAMPIONSHIP — TOP 6", S_SECTION))
        story.append(Spacer(1, 3*mm))
        tdata = [[
            Paragraph("Pos", S_TABLE_HDR), Paragraph("Team", S_TABLE_HDR),
            Paragraph("P", S_TABLE_HDR), Paragraph("GD", S_TABLE_HDR),
            Paragraph("Pts", S_TABLE_HDR), Paragraph("Form", S_TABLE_HDR)
        ]]
        for r in champ_table[:6]:
            form_raw = r.get("form","") or ""
            form_str = " ".join(list(form_raw[-5:])) if form_raw else "-"
            tdata.append([
                Paragraph(str(r["position"]), S_TABLE_CELL),
                Paragraph(r["team"]["name"].replace(" FC","").replace(" AFC",""), S_TABLE_TEAM),
                Paragraph(str(r["playedGames"]), S_TABLE_CELL),
                Paragraph(("{:+d}".format(r["goalDifference"])), S_TABLE_CELL),
                Paragraph(str(r["points"]), S_TABLE_CELL),
                Paragraph(form_str, S_TABLE_CELL),
            ])
        ct = Table(tdata, colWidths=[12*mm, 70*mm, 14*mm, 14*mm, 14*mm, 30*mm])
        ct.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), HexColor("#F77F00")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [C_WHITE, C_GREY]),
            ("GRID", (0,0), (-1,-1), 0.3, HexColor("#DDDDDD")),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("LEFTPADDING", (0,0), (-1,-1), 4),
            ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(ct)
        story.append(Spacer(1, 6*mm))

    # ── RECENT RESULTS ────────────────────────────────────────────────────────
    results = get_recent_results("PL", 6)
    if results:
        story.append(Paragraph("LAST WEEK — KEY RESULTS", S_SECTION))
        story.append(Spacer(1, 3*mm))
        for m in results:
            home = m["homeTeam"]["name"].replace(" FC","")
            away = m["awayTeam"]["name"].replace(" FC","")
            score = m.get("score",{}).get("fullTime",{})
            hs = score.get("home","?")
            as_ = score.get("away","?")
            date_str = m.get("utcDate","")[:10]
            story.append(Paragraph(
                home + " <b>" + str(hs) + " – " + str(as_) + "</b> " + away + "  <font color='#888888' size='8'>" + date_str + "</font>",
                S_STORY_BODY))
            story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 4*mm))

    # ── THIS WEEK\'S TOP STORIES ───────────────────────────────────────────────
    top_stories = get_top_stories(8)
    if top_stories:
        story.append(Paragraph("THIS WEEK\'S TOP STORIES", S_SECTION))
        story.append(Spacer(1, 3*mm))
        FORMAT_LABELS = {"F1":"CONFIRMED TRANSFER","F2":"TRANSFER RUMOUR","F3":"MATCH PREVIEW",
            "F4":"POST-MATCH","F5":"TITLE RACE","F6":"STAR SPOTLIGHT","F7":"HOT TAKE"}
        for i, s in enumerate(top_stories, 1):
            story.append(Paragraph(str(i) + ". " + FORMAT_LABELS.get(s["format"],"NEWS") + " — " + s["source"], S_LABEL))
            story.append(Paragraph(s["hook"] or s["title"], S_STORY_HOOK))
            caption = (s["caption"] or "").replace("#","").strip()
            caption_clean = " ".join(w for w in caption.split() if not w.startswith("#"))
            if caption_clean:
                story.append(Paragraph(caption_clean[:300], S_STORY_BODY))
            story.append(Paragraph("[HOST NOTES] Discuss with your co-host — push back or agree? Any stats to add?", S_SOURCE))
            story.append(Spacer(1, 4*mm))

    # ── HOT TAKES SCRIPT ─────────────────────────────────────────────────────
    hot_takes = get_hot_takes(4)
    if hot_takes:
        story.append(Paragraph("HOT TAKES — DEBATE SEGMENT", S_SECTION))
        story.append(Spacer(1, 3*mm))
        story.append(Paragraph("[HOST — THIS IS YOUR UNFILTERED SEGMENT. GO IN HARD.]", S_SCRIPT_INTRO))
        story.append(Spacer(1, 3*mm))
        for i, ht in enumerate(hot_takes, 1):
            story.append(Paragraph("TAKE " + str(i) + ":", S_LABEL))
            story.append(Paragraph(ht["hook"] or ht["title"], S_STORY_HOOK))
            caption = (ht["caption"] or "")
            caption_clean = " ".join(w for w in caption.split() if not w.startswith("#"))
            if caption_clean:
                story.append(Paragraph(caption_clean[:400], S_SCRIPT_BODY))
            story.append(Paragraph("[CO-HOST CUE] Do you agree? What does the data say?", S_SOURCE))
            story.append(Spacer(1, 5*mm))

    # ── LOOKING AHEAD ─────────────────────────────────────────────────────────
    upcoming = get_upcoming("PL", 5)
    if upcoming:
        story.append(Paragraph("LOOKING AHEAD — FIXTURES TO WATCH", S_SECTION))
        story.append(Spacer(1, 3*mm))
        for m in upcoming:
            home = m["homeTeam"]["name"].replace(" FC","")
            away = m["awayTeam"]["name"].replace(" FC","")
            date_str = m.get("utcDate","")[:10]
            story.append(Paragraph(
                "<b>" + home + " vs " + away + "</b>  <font color=\'#888888\' size=\'8\'>" + date_str + "</font>",
                S_STORY_BODY))
            story.append(Spacer(1, 1*mm))
        story.append(Spacer(1, 4*mm))

    # ── OUTRO SCRIPT ─────────────────────────────────────────────────────────
    story.append(Paragraph("OUTRO", S_SECTION))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("[HOST — CLOSE OUT]", S_SCRIPT_INTRO))
    story.append(Spacer(1, 2*mm))
    outro = (
        "That\'s a wrap on this week\'s 90minWaffle. "
        "If you enjoyed this episode, do us a favour — follow us on X at 90minWaffle, "
        "subscribe on YouTube and TikTok at the same handle. "
        "Drop us your hottest take of the week in the comments — we read every single one. "
        "We\'ll be back next Sunday with another week of football, hot takes, and absolutely no filter. "
        "See you then."
    )
    story.append(Paragraph(outro, S_SCRIPT_BODY))
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=C_MUTED))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("90minWaffle • Football. Hot takes. No filter. • twitter.com/90minwaffle • youtube.com/@90minwaffle • tiktok.com/@90minwaffle", S_FOOTER))

    doc.build(story)
    log.info("PDF built: " + str(output_path))
    return str(output_path)

async def send_podcast_pdf(pdf_path):
    if not BOT_TOKEN: return
    from telegram import Bot
    bot = Bot(token=BOT_TOKEN)
    now = datetime.now(timezone.utc).strftime("%d %b %Y")
    caption = "90minWaffle Weekly Podcast Script — " + now
    try:
        with open(pdf_path, "rb") as f:
            if INSIDE_CHANNEL:
                await bot.send_document(chat_id=INSIDE_CHANNEL, document=f,
                    filename="90minWaffle_Podcast_" + now.replace(" ","_") + ".pdf",
                    caption=caption)
                log.info("PDF sent to Inside channel")
    except Exception as e:
        log.error("PDF send failed: " + str(e))

async def run_podcast():
    log.info("=== Podcast PDF generator starting ===")
    now = datetime.now(timezone.utc)
    fname = "90minWaffle_Podcast_" + now.strftime("%Y_%m_%d") + ".pdf"
    output_path = OUTPUT_DIR / fname
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = build_pdf(output_path)
    await send_podcast_pdf(pdf_path)
    log.info("=== Podcast PDF done: " + pdf_path + " ===")
    return pdf_path

if __name__ == "__main__":
    asyncio.run(run_podcast())
