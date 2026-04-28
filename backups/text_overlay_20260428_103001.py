#!/usr/bin/env python3
import subprocess,sqlite3,os,re,logging
from dotenv import load_dotenv
load_dotenv("/root/90minwaffle/.env")
DB_PATH="/root/90minwaffle/data/waffle.db"
FONT_PATH="/root/90minwaffle/assets/Anton-Regular.ttf"
LOG_PATH="/root/90minwaffle/logs/text_overlay.log"
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s",handlers=[logging.FileHandler(LOG_PATH),logging.StreamHandler()])
log=logging.getLogger(__name__)
EC=r"\,"

NAME_FIXES={
    # Players
    "salas":"SALAH","sala":"SALAH","salla":"SALAH","salah":"SALAH",
    "haalands":"HAALAND","haland":"HAALAND","harland":"HAALAND",
    "mbappe":"MBAPPE","kylian":"KYLIAN",
    "bellingham":"BELLINGHAM","jude":"JUDE",
    "vinicius":"VINICIUS","vinicious":"VINICIUS","vini":"VINI",
    "rashford":"RASHFORD","marcus":"MARCUS",
    "saka":"SAKA","bukayo":"BUKAYO",
    "palmer":"PALMER","cole":"COLE",
    "eze":"EZE","eberechi":"EBERECHI",
    "isak":"ISAK","alexander":"ALEXANDER",
    "palhinha":"PALHINHA","joao":"JOAO",
    "odegaard":"ODEGAARD","martin":"MARTIN",
    "havertz":"HAVERTZ","kai":"KAI",
    "wirtz":"WIRTZ","florian":"FLORIAN",
    "yamal":"YAMAL","lamine":"LAMINE",
    "dembele":"DEMBELE","ousmane":"OUSMANE",
    "lewandowski":"LEWANDOWSKI","robert":"ROBERT",
    "kane":"KANE","harry":"HARRY",
    "son":"SON","heung":"HEUNG",
    "trent":"TRENT","alexander-arnold":"TRENT",
    "fernandes":"FERNANDES","bruno":"BRUNO",
    "mainoo":"MAINOO","kobbie":"KOBBIE",
    "amorim":"AMORIM","ruben":"RUBEN",
    "arteta":"ARTETA","mikel":"MIKEL",
    "guardiola":"GUARDIOLA","pep":"PEP",
    "slot":"SLOT","arne":"ARNE",
    "howe":"HOWE","eddie":"EDDIE",
    "zerbi":"ZERBI","de":"DE",
    "rosenior":"ROSENIOR","liam":"LIAM",
    "mourinho":"MOURINHO","jose":"JOSE",
    "klopp":"KLOPP","jurgen":"JURGEN",
    # Clubs
    "liverpool":"LIVERPOOL","arsenal":"ARSENAL","chelsea":"CHELSEA",
    "manchester":"MANCHESTER","tottenham":"TOTTENHAM","spurs":"SPURS",
    "newcastle":"NEWCASTLE","villa":"VILLA","everton":"EVERTON",
    "brighton":"BRIGHTON","fulham":"FULHAM","brentford":"BRENTFORD",
    "wolves":"WOLVES","forest":"FOREST","bournemouth":"BOURNEMOUTH",
    "southampton":"SOUTHAMPTON","leicester":"LEICESTER","ipswich":"IPSWICH",
    "madrid":"MADRID","barcelona":"BARCELONA","barca":"BARCA",
    "bayern":"BAYERN","psg":"PSG","juventus":"JUVENTUS",
    "inter":"INTER","atletico":"ATLETICO","dortmund":"DORTMUND",
    "napoli":"NAPOLI","milan":"MILAN","rome":"ROMA",
    # Cities and Countries
    "london":"LONDON","manchester":"MANCHESTER","liverpool":"LIVERPOOL",
    "paris":"PARIS","madrid":"MADRID","barcelona":"BARCELONA",
    "munich":"MUNICH","rome":"ROME","milan":"MILAN","turin":"TURIN",
    "riyadh":"RIYADH","riad":"RIYADH","riyad":"RIYADH","riard":"RIYADH","read":"RIYADH",
    "dubai":"DUBAI","doha":"DOHA","qatar":"QATAR",
    "england":"ENGLAND","france":"FRANCE","spain":"SPAIN","germany":"GERMANY",
    "italy":"ITALY","portugal":"PORTUGAL","brazil":"BRAZIL","argentina":"ARGENTINA",
    "saudi":"SAUDI","arabia":"ARABIA",
    # Competitions
    "champions":"CHAMPIONS","league":"LEAGUE","premier":"PREMIER",
    "wembley":"WEMBLEY","anfield":"ANFIELD","emirates":"EMIRATES",
    "bernabeu":"BERNABEU","nou":"NOU","camp":"CAMP","allianz":"ALLIANZ",
    "carabao":"CARABAO","bundesliga":"BUNDESLIGA","laliga":"LALIGA",
    "seriea":"SERIE A","ligue":"LIGUE",
    # Common mishears
    "utd":"UTD","fc":"FC","afc":"AFC","cfc":"CFC","mcfc":"MCFC",
}


WORD_BLOCKLIST = {
    "read","reed","rid","riad","riard","gonna","wanna","gotta",
    "uhh","uh","um","hmm","ah","eh","ok","okay",
}

def fix_names(text):
    words = text.split()
    fixed = []
    for w in words:
        key = w.lower().rstrip(".,!?")
        fixed.append(NAME_FIXES.get(key, w))
    return " ".join(fixed)

def get_db(): return sqlite3.connect(DB_PATH)

def clean(t):
    t = t.replace(chr(163),"").replace(chr(8217),"").replace(chr(8216),"")
    t = t.replace("'","").replace(chr(39),"").replace(chr(96),"")
    t = t.replace("-"," ").replace("."," ").replace(","," ")
    t = re.sub(r"[^a-zA-Z0-9 ]","",t)
    t = re.sub(r" +"," ",t)
    return t.strip()

def get_duration(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",path],capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except: return 60.0

def get_word_timestamps(audio_path, script=None):
    """Generate word timestamps directly from script text using audio duration.
    No Whisper — perfect spelling, faster, no RAM overhead."""
    dur = get_duration(audio_path)
    if not script or not dur:
        log.warning("  No script or duration — cannot generate timestamps")
        return []
    log.info(f"  Script-based timing: {dur:.1f}s audio")
    # Clean script to plain words
    raw = re.sub(r"[^a-zA-Z0-9 '-]", " ", script)
    raw = re.sub(r" +", " ", raw).strip()
    word_list = [w.upper() for w in raw.split() if w.strip()]
    if not word_list:
        return []
    # Distribute words evenly across audio duration
    # Reserve first 3.5s for hook display, last 4s for CTA
    start_offset = 3.6
    end_offset = max(dur - 4.0, dur * 0.82)
    usable = end_offset - start_offset
    if usable <= 0:
        usable = dur - start_offset
    per_word = usable / len(word_list)
    words = []
    for i, w in enumerate(word_list):
        t_start = round(start_offset + i * per_word, 2)
        t_end = round(t_start + max(per_word - 0.05, 0.15), 2)
        words.append({"word": w, "start": t_start, "end": t_end})
    log.info(f"  {len(words)} words timed across {usable:.1f}s")
    return words

def group_words(words,n=3):
    groups=[]
    i=0
    while i<len(words):
        chunk=words[i:i+n]
        if chunk:
            text=" ".join(w["word"] for w in chunk)
            text=" ".join(w["word"] for w in chunk if w["word"].lower() not in WORD_BLOCKLIST)
            if text.strip(): groups.append({"text":text,"start":chunk[0]["start"],"end":chunk[-1]["end"]+0.05})
        i+=n
    return groups

def bt(a,b): return f"between(t{EC}{a}{EC}{b})"
def gt(a): return f"gte(t{EC}{a})"

def build_filters(groups,hook,cta,duration,fp):
    fa=f"fontfile={fp}:" if os.path.exists(fp) else ""
    cs=round(max(duration-4,duration*0.82),1)
    hook=re.sub(r"[^a-zA-Z0-9 !?.,\-]","",hook.upper())
    cta=re.sub(r"[^a-zA-Z0-9 !?.,\-]","",cta)
    hw=hook.split()
    f=[]
    # Bars
    f.append("drawbox=x=0:y=0:w=1080:h=100:color=black@0.75:t=fill")
    f.append("drawbox=x=0:y=1640:w=1080:h=280:color=black@0.65:t=fill")
    # Watermark
    f.append(f"drawtext={fa}text=90minWaffle:fontsize=32:fontcolor=white:x=22:y=32:shadowcolor=black:shadowx=2:shadowy=2")
    f.append("drawbox=x=0:y=94:w=1080:h=4:color=0xe63946:t=fill")
    # Hook 0-3.5s
    line1=" ".join(hw[:4])
    line2=" ".join(hw[4:]) if len(hw)>4 else ""
    f.append(f"drawtext={fa}text={line1}:fontsize=82:fontcolor=white:x=(w-text_w)/2:y=820:shadowcolor=black:shadowx=5:shadowy=5:enable={bt(0,3.5)}")
    if line2:
        f.append(f"drawtext={fa}text={line2}:fontsize=82:fontcolor=white:x=(w-text_w)/2:y=912:shadowcolor=black:shadowx=5:shadowy=5:enable={bt(0.2,3.5)}")
    f.append(f"drawbox=x=80:y=1005:w=920:h=6:color=0xe63946:t=fill:enable={bt(0.3,3.5)}")
    # Word sync groups
    for g in groups:
        if g["start"]<3.5 or g["end"]<g["start"]+0.12 or g["start"]>=cs: continue
        txt=g["text"]
        if len(txt)>32: txt=txt[:32]
        f.append(f"drawtext={fa}text={txt}:fontsize=78:fontcolor=white:x=(w-text_w)/2:y=870:shadowcolor=black:shadowx=4:shadowy=4:enable={bt(g['start'],g['end'])}")
        f.append(f"drawbox=x=60:y=850:w=960:h=90:color=0xe63946@0.12:t=fill:enable={bt(g['start'],g['end'])}")
    # CTA
    if cta:
        cw=cta.split()
        cl1=" ".join(cw[:5])
        cl2=" ".join(cw[5:10]) if len(cw)>5 else ""
        f.append(f"drawtext={fa}text={cl1}:fontsize=50:fontcolor=white:x=(w-text_w)/2:y=1650:shadowcolor=black:shadowx=3:shadowy=3:enable={gt(cs)}")
        if cl2:
            f.append(f"drawtext={fa}text={cl2}:fontsize=50:fontcolor=white:x=(w-text_w)/2:y=1705:shadowcolor=black:shadowx=3:shadowy=3:enable={gt(cs)}")
        f.append(f"drawtext={fa}text=DROP YOUR TAKE BELOW:fontsize=28:fontcolor=0xe63946:x=(w-text_w)/2:y=1800:shadowcolor=black:shadowx=2:shadowy=2:enable={gt(cs+0.5)}")
    return ",".join(f)

def extract_cta(caption):
    lines=[l.strip() for l in caption.split("\n") if "?" in l]
    result=lines[0][:55] if lines else "Agree or disagree"
    return re.sub(r"[^a-zA-Z0-9 !?,.\-]","",result)

def apply_overlay(vp,ap,out,hook,cta,script=None):
    words=get_word_timestamps(ap,script=script)
    if not words: return None
    groups=group_words(words,3)
    dur=get_duration(vp)
    filters=build_filters(groups,hook,cta,dur,FONT_PATH)
    r=subprocess.run(["ffmpeg","-y","-i",vp,"-vf",filters,"-c:v","libx264","-preset","fast","-crf","21","-c:a","copy",out],capture_output=True,text=True)
    if r.returncode==0:
        log.info(f"  OK {out} ({os.path.getsize(out)//1024}KB)"); return out
    log.error(f"  FAIL {r.stderr[-300:]}"); return None

def process_videos(limit=2):
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT id,title,winning_hook,caption,video_path,script FROM stories WHERE status IN ('video_ready','queued') AND video_path IS NOT NULL ORDER BY score DESC LIMIT ?",(limit,))
    rows=c.fetchall(); conn.close()
    if not rows: log.info("No videos"); return 0
    log.info(f"=== Word-sync overlay {len(rows)} videos ===")
    success=0
    for r in rows:
        sid,title,hook,caption,vp,script=r
        if not vp or not os.path.exists(vp): continue
        base_vp=vp.replace("_overlay","").replace("_wordsync","")
        if not os.path.exists(base_vp): base_vp=vp
        ap=base_vp.replace("video_","voice_").replace(".mp4",".mp3")
        if not os.path.exists(ap): ap=ap.replace(".mp3","_gtts.mp3")
        if not os.path.exists(ap): log.warning(f"  No audio: {ap}"); continue
        hook=re.sub(r"[^a-zA-Z0-9 !?,.\-]","",fix_names((hook or title).upper()))
        cta=extract_cta(caption or "")
        out=base_vp.replace(".mp4","_overlay.mp4")
        log.info(f"  {title[:60]}")
        if apply_overlay(base_vp,ap,out,hook,cta,script=script):
            conn=get_db(); c=conn.cursor()
            c.execute("UPDATE stories SET video_path=? WHERE id=?",(out,sid))
            conn.commit(); conn.close(); success+=1
    log.info(f"=== Done {success} ===")
    return success

if __name__=="__main__":
    process_videos(limit=2)
