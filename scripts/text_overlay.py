#!/usr/bin/env python3
"""
90minWaffle — Text Overlay Engine v5
TikTok/YouTube Shorts style. ElevenLabs real-word-sync.
Clean, brand-consistent, no bugs.
"""
import subprocess, sqlite3, os, re, logging, json
from dotenv import load_dotenv
load_dotenv("/root/90minwaffle/.env")

DB_PATH  = "/root/90minwaffle/data/waffle.db"
FONT     = "/root/Anton.ttf"
LOG_PATH = "/root/90minwaffle/logs/text_overlay.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# Brand
RED    = "0xe63946"
YELLOW = "0xFFD60A"
WHITE  = "white"
BLACK  = "black"
W      = 1080
H      = 1920

FORMAT_LABEL = {
    "F1": "CONFIRMED TRANSFER",
    "F2": "TRANSFER RUMOUR",
    "F3": "MATCH DAY",
    "F4": "POST MATCH",
    "F5": "TITLE RACE",
    "F6": "STAR SPOTLIGHT",
    "F7": "HOT TAKE",
    "F8": "TIPS AND BETS",
}

LEAGUE_KEYWORDS = {
    "PREMIER LEAGUE":    ["premier league","man utd","man city","arsenal","chelsea","liverpool","tottenham","spurs","newcastle","aston villa","everton","brighton","fulham","wolves","forest","brentford","bournemouth","crystal palace","ipswich","leicester","southampton","west ham"],
    "CHAMPIONS LEAGUE":  ["champions league","ucl","cl final","european"],
    "FA CUP":            ["fa cup","wembley","semi-final","quarter-final"],
    "CHAMPIONSHIP":      ["championship","elc","middlesbrough","sheffield","norwich","watford","coventry","stoke","cardiff","swansea","west brom","hull","bristol city","blackburn","luton","derby","preston","plymouth"],
    "WOMENS FOOTBALL":   ["wsl","uwcl","lionesses","womens","women","female"],
    "TRANSFER NEWS":     ["transfer","signing","deal","fee","bid","contract","loan"],
    "LA LIGA":           ["la liga","real madrid","barcelona","atletico","sevilla","laliga"],
    "BUNDESLIGA":        ["bundesliga","bayern","dortmund","leverkusen"],
    "SERIE A":           ["serie a","juventus","inter milan","ac milan","napoli","roma"],
    "LIGUE 1":           ["ligue 1","psg","paris saint"],
}

def detect_league(title):
    t = title.lower()
    for league, keywords in LEAGUE_KEYWORDS.items():
        if any(k in t for k in keywords):
            return league
    return "FOOTBALL NEWS"

def get_db():
    return sqlite3.connect(DB_PATH)

def get_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except:
        return 60.0

def load_alignment(ap):
    """Load real word timestamps from ElevenLabs alignment JSON."""
    ts = ap.replace(".mp3", ".json")
    if not os.path.exists(ts):
        return None
    try:
        alignment = json.load(open(ts))
        chars = alignment.get("characters", [])
        starts = alignment.get("character_start_times_seconds", [])
        ends   = alignment.get("character_end_times_seconds", [])
        if not chars or not starts:
            return None
        words = []
        cur = ""
        ws  = None
        for i, (ch, t0) in enumerate(zip(chars, starts)):
            te = ends[i] if i < len(ends) else t0 + 0.05
            if ch == " " or i == len(chars) - 1:
                if ch != " " and i == len(chars) - 1:
                    cur += ch
                if cur.strip():
                    words.append({"word": cur.upper().strip(), "start": round(ws, 3), "end": round(te, 3)})
                cur = ""
                ws  = None
            else:
                cur += ch
                if ws is None:
                    ws = t0
        log.info(f"  Alignment: {len(words)} real word timestamps")
        return words
    except Exception as e:
        log.warning(f"  Alignment load failed: {e}")
        return None

def linear_words(script, audio_dur):
    """Fallback: distribute words linearly across audio."""
    raw   = re.sub(r"[^a-zA-Z0-9 ]", " ", script)
    raw   = re.sub(r" +", " ", raw).strip()
    wlist = [w.upper() for w in raw.split() if w.strip()]
    if not wlist:
        return []
    t0     = 2.5
    t1     = audio_dur - 3.5
    usable = max(t1 - t0, 4.0)
    spw    = usable / len(wlist)
    return [{"word": w, "start": round(t0 + i * spw, 3), "end": round(t0 + (i + 1) * spw - 0.05, 3)}
            for i, w in enumerate(wlist)]

def make_groups(words, n=3, maxch=14):
    """Group words into caption flashes, respecting max char width."""
    out = []
    i   = 0
    while i < len(words):
        chunk = words[i:i + n]
        txt   = " ".join(c["word"] for c in chunk)
        while len(txt) > maxch and len(chunk) > 1:
            chunk = chunk[:-1]
            txt   = " ".join(c["word"] for c in chunk)
        if txt.strip():
            out.append({"text": txt, "t0": chunk[0]["start"], "t1": chunk[-1]["end"]})
        i += len(chunk)
    return out

def fa():
    return f"fontfile={FONT}:" if os.path.exists(FONT) else ""

def bt(a, b):
    return f"between(t\\,{a}\\,{b})"

def gt(a):
    return f"gte(t\\,{a})"

def safe(s, maxlen=20):
    """Strip unsafe chars for ffmpeg drawtext, uppercase, cap length."""
    s = re.sub(r"[^A-Z0-9 !?.]", "", str(s).upper())
    return s[:maxlen].strip()

def build(groups, hook, cta, duration, fmt="F2", title=""):
    f         = fa()
    cta_start = round(max(duration - 3.5, duration * 0.85), 1)
    hook_end  = 2.5
    league    = detect_league(title or hook)
    fmt_label = FORMAT_LABEL.get(fmt, "FOOTBALL NEWS")
    parts     = []

    # ── TOP BAR ──────────────────────────────────────────────────────────────
    parts.append(f"drawbox=x=0:y=0:w={W}:h=90:color=black@0.90:t=fill")
    parts.append(f"drawbox=x=0:y=87:w={W}:h=3:color={RED}:t=fill")

    # Brand name
    parts.append(
        f"drawtext={f}text=90minWaffle:fontsize=36:fontcolor={WHITE}:"
        f"x=22:y=28:shadowcolor=black:shadowx=2:shadowy=2"
    )

    # League label (top left, below brand)
    parts.append(
        f"drawtext={f}text={safe(league, 22)}:fontsize=22:fontcolor={YELLOW}:"
        f"x=22:y=60:shadowcolor=black:shadowx=1:shadowy=1"
    )

    # Format badge (top right)
    badge = safe(fmt_label, 18)
    parts.append(
        f"drawbox=x=700:y=10:w=360:h=32:color={RED}@0.90:t=fill"
    )
    parts.append(
        f"drawtext={f}text={badge}:fontsize=20:fontcolor={WHITE}:"
        f"x=880-text_w/2:y=18:shadowcolor=black:shadowx=1:shadowy=1"
    )

    # ── HOOK TITLE (0 → hook_end) ────────────────────────────────────────────
    hw    = safe(hook, 40).split()
    line1 = " ".join(hw[:3])
    line2 = " ".join(hw[3:6]) if len(hw) > 3 else ""

    if line1:
        parts.append(
            f"drawtext={f}text={line1}:fontsize=82:fontcolor={YELLOW}:"
            f"x=(1080-text_w)/2:y=800:"
            f"shadowcolor=black:shadowx=5:shadowy=5:"
            f"enable={bt(0, hook_end)}"
        )
    if line2:
        parts.append(
            f"drawtext={f}text={line2}:fontsize=82:fontcolor={YELLOW}:"
            f"x=(1080-text_w)/2:y=892:"
            f"shadowcolor=black:shadowx=5:shadowy=5:"
            f"enable={bt(0, hook_end)}"
        )

    # Red underline under hook
    parts.append(
        f"drawbox=x=80:y=980:w=920:h=4:color={RED}:t=fill:"
        f"enable={bt(0, hook_end)}"
    )

    # ── WORD-SYNC CAPTIONS ───────────────────────────────────────────────────
    for g in groups:
        t0  = g["t0"]
        t1  = g["t1"]
        txt = safe(g["text"], 14)
        if not txt:
            continue

        # Caption pill background
        parts.append(
            f"drawbox=x=80:y=870:w=920:h=95:color=black@0.72:t=fill:"
            f"enable={bt(t0, t1)}"
        )
        # Left red accent bar
        parts.append(
            f"drawbox=x=80:y=870:w=6:h=95:color={RED}:t=fill:"
            f"enable={bt(t0, t1)}"
        )
        # Caption text
        parts.append(
            f"drawtext={f}text={txt}:fontsize=78:fontcolor={WHITE}:"
            f"x=(1080-text_w)/2:y=888:"
            f"shadowcolor=black:shadowx=3:shadowy=3:"
            f"enable={bt(t0, t1)}"
        )

    # ── BOTTOM BAR ───────────────────────────────────────────────────────────
    parts.append(
        f"drawbox=x=0:y=1700:w={W}:h=220:color=black@0.85:t=fill"
    )
    parts.append(
        f"drawbox=x=0:y=1700:w={W}:h=3:color={RED}:t=fill"
    )

    # Social handles
    parts.append(
        f"drawtext={f}text=@90minWaffle  X  YouTube  TikTok:"
        f"fontsize=26:fontcolor={WHITE}@0.60:"
        f"x=(1080-text_w)/2:y=1860:"
        f"shadowcolor=black:shadowx=1:shadowy=1"
    )

    # ── CTA (last 3.5s) ──────────────────────────────────────────────────────
    if cta:
        cta_clean = re.sub(r"[^A-Za-z0-9 !?.]", "", cta)[:45]
        cta_words = cta_clean.split()
        cta_l1    = " ".join(cta_words[:6])
        cta_l2    = " ".join(cta_words[6:]) if len(cta_words) > 6 else ""

        parts.append(
            f"drawtext={f}text={cta_l1}:fontsize=42:fontcolor={WHITE}:"
            f"x=(1080-text_w)/2:y=1715:"
            f"shadowcolor=black:shadowx=2:shadowy=2:"
            f"enable={gt(cta_start)}"
        )
        if cta_l2:
            parts.append(
                f"drawtext={f}text={cta_l2}:fontsize=42:fontcolor={WHITE}:"
                f"x=(1080-text_w)/2:y=1762:"
                f"shadowcolor=black:shadowx=2:shadowy=2:"
                f"enable={gt(cta_start)}"
            )

        parts.append(
            f"drawtext={f}text=DROP YOUR TAKE BELOW:"
            f"fontsize=32:fontcolor={RED}:"
            f"x=(1080-text_w)/2:y=1820:"
            f"shadowcolor=black:shadowx=2:shadowy=2:"
            f"enable={gt(cta_start + 0.3)}"
        )

    return ",".join(parts)

def extract_cta(caption):
    if not caption:
        return "Agree or disagree?"
    lines = [l.strip() for l in caption.split("\n") if "?" in l]
    result = lines[0][:50] if lines else "Agree or disagree?"
    return re.sub(r"[^A-Za-z0-9 !?.,]", "", result)

def apply_overlay(vp, ap, out, hook, cta, script=None, fmt="F2", title=""):
    # Real timestamps first, linear fallback
    ws = load_alignment(ap)
    if not ws:
        log.info("  No alignment — using linear distribution")
        ws = linear_words(script or "", get_dur(ap))
    if not ws:
        log.warning("  No words — skipping overlay")
        return None

    gs   = make_groups(ws)
    d    = get_dur(vp)
    filt = build(gs, hook, cta, d, fmt=fmt, title=title)

    log.info(f"  {len(gs)} caption groups | filter {len(filt)} chars")

    r = subprocess.run(
        ["ffmpeg", "-y", "-i", vp, "-vf", filt,
         "-c:v", "libx264", "-preset", "fast", "-crf", "21",
         "-c:a", "copy", out],
        capture_output=True, text=True
    )

    if r.returncode == 0:
        log.info(f"  OK {out} ({os.path.getsize(out) // 1024}KB)")
        return out

    log.error(f"  FAIL {r.stderr[-400:]}")
    return None

def process_videos(limit=2):
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        SELECT id, title, winning_hook, caption, video_path, script, format
        FROM stories
        WHERE status IN ('video_ready','queued')
        AND video_path IS NOT NULL
        ORDER BY score DESC
        LIMIT ?
    """, (limit,))
    rows = c.fetchall()
    conn.close()

    if not rows:
        log.info("No videos")
        return 0

    log.info(f"=== Overlay {len(rows)} videos ===")
    sent = 0

    for r in rows:
        sid, title, hook, caption, vp, script, fmt = r
        if not vp or not os.path.exists(vp):
            continue

        base = vp.replace("_overlay", "").replace("_wordsync", "")
        if not os.path.exists(base):
            base = vp

        ap = base.replace("video_", "voice_").replace(".mp4", ".mp3")
        if not os.path.exists(ap):
            log.warning(f"  No audio: {ap}")
            continue

        hook_t = re.sub(r"[^A-Za-z0-9 !?.]", "", (hook or title).upper())
        cta_t  = extract_cta(caption or "")
        out    = base.replace(".mp4", "_overlay.mp4")

        log.info(f"  {title[:60]}")

        if apply_overlay(base, ap, out, hook_t, cta_t,
                         script=script, fmt=fmt or "F2", title=title or ""):
            conn = get_db()
            c    = conn.cursor()
            c.execute("UPDATE stories SET video_path=? WHERE id=?", (out, sid))
            conn.commit()
            conn.close()
            sent += 1

    log.info(f"=== Done {sent}/{len(rows)} ===")
    return sent

if __name__ == "__main__":
    process_videos(limit=2)
