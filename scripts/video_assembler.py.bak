import os,requests,subprocess,sqlite3,logging,random
from dotenv import load_dotenv
load_dotenv("/root/90minwaffle/.env")
DB_PATH="/root/90minwaffle/data/waffle.db"
BROLL_DIR="/root/90minwaffle/data/broll"
OUTPUT_DIR="/root/90minwaffle/data/videos"
LOG_PATH="/root/90minwaffle/logs/video_assembler.log"
logging.basicConfig(level=logging.INFO,format="%(asctime)s [%(levelname)s] %(message)s",handlers=[logging.FileHandler(LOG_PATH),logging.StreamHandler()])
log=logging.getLogger(__name__)
PEXELS_KEY=os.getenv("PEXELS_API_KEY")
ELEVEN_KEY=os.getenv("ELEVENLABS_API_KEY")
VOICE_ID=os.getenv("ELEVENLABS_VOICE_ID","qi38gTeLFnwVRNsISsAB")
STABILITY=float(os.getenv("ELEVENLABS_STABILITY",0.5))
SIMILARITY=float(os.getenv("ELEVENLABS_SIMILARITY",0.75))
STYLE=float(os.getenv("ELEVENLABS_STYLE",0.75))
SPEED=float(os.getenv("ELEVENLABS_SPEED",1.05))
BROLL_QUERIES={"F1":["male soccer players celebrating","men football goal scored","male footballers running","men soccer match crowd"],"F2":["male soccer training session","men football players pitch","male footballers walking","men soccer coach sideline"],"F3":["men soccer stadium night","male football match crowd","men football tunnel","male soccer players warmup"],"F4":["men soccer goal celebration jump","male football fans cheering","men soccer final whistle","male football crowd stadium"],"F5":["men soccer championship trophy","male football fans chanting stadium","men soccer title winners","male football league celebration"],"F6":["male soccer player dribbling","men football skills training","male footballer sprinting ball","men soccer player close up"],"F7":["men soccer fans stadium singing","male football atmosphere crowd","men soccer match day","male football supporters"]}

BROLL_QUERIES_WOMEN={"F1":["women soccer players celebrating","female football stadium crowd","women soccer trophy celebration","female footballers running pitch"],"F2":["women soccer training pitch","female football players","women footballers walking","female soccer coach sideline"],"F3":["women soccer stadium night","female football match crowd","women football atmosphere","female soccer players warmup"],"F4":["women soccer goal celebration","female football fans cheering","women soccer final whistle","female football crowd stadium"],"F5":["women soccer championship trophy","female football fans chanting","women soccer title winners","female football league celebration"],"F6":["female soccer player dribbling","women football skills training","female footballer sprinting ball","women soccer player close up"],"F7":["women soccer fans stadium","female football atmosphere crowd","women soccer match day","female football supporters"]}

WOMEN_KEYWORDS=["women","wsl","nwsl","uwcl","lionesses","blackstenius","white","hemp","russo","kerr","harder","putellas","bonmati","womens","female","girls"]
def get_db(): return sqlite3.connect(DB_PATH)

def check_eleven_quota():
    """Return remaining ElevenLabs characters, or 0 on error."""
    try:
        r = requests.get("https://api.elevenlabs.io/v1/user",
                         headers={"xi-api-key": ELEVEN_KEY}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            sub = data.get("subscription", data)
            used = sub.get("character_count", data.get("character_count", 0))
            limit = sub.get("character_limit", data.get("character_limit", 30000))
            remaining = limit - used
            log.info(f"  ElevenLabs quota: {remaining} chars remaining ({used}/{limit})")
            return remaining
        log.warning(f"  ElevenLabs quota check failed: {r.status_code}")
        return 0
    except Exception as e:
        log.warning(f"  ElevenLabs quota check error: {e}")
        return 0

def get_sportsdb_images(story):
    """Get SportsDB images — player photos first, team badge/fanart fallback.
    Strictly football/soccer only — no crossover sports."""
    try:
        import sys, importlib.util
        sys.path.insert(0, "/root/90minwaffle/scripts")
        spec = importlib.util.spec_from_file_location("sportsdb_registry", "/root/90minwaffle/scripts/sportsdb_registry.py")
        reg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reg)
        title = story.get("title", "") or ""
        hook  = story.get("winning_hook", "") or ""
        text  = f"{title} {hook}"
        images = []

        # 1. Find team context
        team    = reg.find_team_in_text(text)
        team_id = team.get("id") if team else None

        # 2. Try player images from roster
        names = reg.extract_player_names(text)
        for name in names[:3]:
            url = reg.find_player_image(name, team_id)
            if url and url not in images:
                images.append(url)
            if len(images) >= 2:
                break

        # 3. Fill with team images — fanart/stadium first, badge last
        if team:
            for key in ["fanart","banner","stadium_thumb","equipment","badge","logo"]:
                if len(images) >= 4: break
                url = team.get(key)
                if url and url not in images:
                    images.append(url)

        # 4. Legacy player search — football ONLY, correct gender
        if not images and names:
            story_is_women = is_womens_story(title)
            for name in names[:2]:
                try:
                    r = requests.get(
                        f"{reg.BASE}/searchplayers.php",
                        params={"p": name}, timeout=10
                    )
                    players = (r.json() or {}).get("player") or []
                    for p in players:
                        sport = (p.get("strSport") or "").lower()
                        if sport not in ("soccer", "football"):
                            continue
                        # Gender check — only use women players for womens stories
                        gender = (p.get("strGender") or "Male").lower()
                        if not story_is_women and gender == "female":
                            continue
                        url = p.get("strRender") or p.get("strCutout") or p.get("strThumb")
                        if url and url not in images:
                            images.append(url)
                            break
                except Exception:
                    pass

        log.info(f"  SportsDB: {len(images)} images for: {title[:50]}")
        return images[:4]
    except Exception as e:
        log.warning("SportsDB video images failed: " + str(e))
        return []

def download_image_as_video(img_url, out_path, duration=10):
    """Download an image and convert to a video clip using ffmpeg."""
    try:
        import tempfile
        r = requests.get(img_url, timeout=15)
        if r.status_code != 200: return False
        ext = ".png" if img_url.endswith(".png") else ".jpg"
        tmp = out_path.replace(".mp4", "_img" + ext)
        open(tmp, "wb").write(r.content)
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", tmp,
               "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,zoompan=z=1.04:d=" + str(duration*25) + ":s=1080x1920",
               "-c:v", "libx264", "-t", str(duration), "-pix_fmt", "yuv420p",
               "-r", "25", out_path]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        import os; os.remove(tmp)
        return result.returncode == 0
    except Exception as e:
        log.warning("Image to video failed: " + str(e)); return False

def format_script(s):
    for w in ["done deal","confirmed","official","breaking","here we go","signed","champions","relegated","sacked","appointed"]:
        s=s.replace(w,w.upper()).replace(w.title(),w.upper())
    return s
def generate_voiceover(script,story_id):
    """Generate voiceover via ElevenLabs with-timestamps endpoint.
    Saves audio as voice_{id}.mp3 and timestamps as voice_{id}.json.
    Returns audio path or None on failure."""
    import base64, json as _json
    out=os.path.join(OUTPUT_DIR,f"voice_{story_id}.mp3")
    ts_out=os.path.join(OUTPUT_DIR,f"voice_{story_id}.json")
    os.makedirs(OUTPUT_DIR,exist_ok=True)
    if not script or not script.strip():
        log.error("  Empty script — skipping")
        return None
    log.info("  Generating ElevenLabs voiceover + timestamps")
    r=requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps",
        headers={"xi-api-key":ELEVEN_KEY,"Content-Type":"application/json"},
        json={"text":format_script(script),"model_id":"eleven_v3",
              "voice_settings":{"stability":STABILITY,"similarity_boost":SIMILARITY,
                                "style":STYLE,"use_speaker_boost":True,"speed":SPEED}},
        timeout=60
    )
    if r.status_code==200:
        data=r.json()
        # Save audio
        audio_bytes=base64.b64decode(data["audio_base64"])
        with open(out,"wb") as f: f.write(audio_bytes)
        # Save alignment timestamps
        alignment=data.get("alignment",{})
        _json.dump(alignment, open(ts_out,"w"))
        log.info(f"  Voiceover saved: {out} | timestamps: {ts_out}")
        return out
    if r.status_code==401:
        log.warning(f"  ElevenLabs auth/quota error: {r.text[:100]}"); return None
    log.error(f"  ElevenLabs error: {r.status_code} {r.text[:200]}"); return None
def is_womens_story(title):
    t=title.lower()
    return any(k in t for k in WOMEN_KEYWORDS)

def fetch_pexels_images(title, fmt):
    """Fallback image search via Pexels — men's or women's based on story content."""
    if not PEXELS_KEY: return []
    t = title.lower()
    is_women = is_womens_story(title)
    gender = "women's" if is_women else "men's"

    # Use BROLL_QUERIES dicts for consistent gender-correct queries
    queries = BROLL_QUERIES_WOMEN if is_women else BROLL_QUERIES
    fmt_queries = queries.get(fmt, [])

    # Context-aware override for specific story types
    if any(k in t for k in ["manager","boss","appointed","sacked","head coach"]):
        query = f"{'women' if is_women else 'men'} soccer manager dugout touchline"
    elif any(k in t for k in ["transfer","signing","deal","bid","fee","contract"]):
        query = f"{'women' if is_women else 'men'} soccer football transfer signing"
    elif any(k in t for k in ["stadium","wembley","anfield","emirates","bernabeu","nou camp","etihad"]):
        query = "soccer football stadium crowd atmosphere night"
    elif any(k in t for k in ["preview","vs","v ","facing","ahead of"]):
        query = fmt_queries[2] if len(fmt_queries) > 2 else f"{'women' if is_women else 'men'} soccer stadium night"
    elif any(k in t for k in ["reaction","win","loss","defeat","goal","scored"]):
        query = fmt_queries[0] if fmt_queries else f"{'women' if is_women else 'men'} soccer goal celebration"
    elif fmt_queries:
        query = fmt_queries[0]
    else:
        query = f"{'women' if is_women else 'men'} soccer football premier league match action"

    log.info(f"  Pexels query ({gender}): {query}")
    try:
        r = requests.get("https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": query, "per_page": 4, "size": "medium", "orientation": "portrait"},
            timeout=15)
        if r.status_code != 200:
            log.warning(f"  Pexels {r.status_code}: {r.text[:100]}")
            return []
        videos = r.json().get("videos", [])
        urls = []
        for v in videos:
            files = v.get("video_files", [])
            # Prefer HD portrait files
            hd = [f for f in files if f.get("height", 0) >= 720]
            pick = hd[0] if hd else (files[0] if files else None)
            if pick: urls.append(pick["link"])
        log.info(f"  Pexels fallback: {len(urls)} videos for '{query}'")
        return urls[:4]
    except Exception as e:
        log.warning(f"  Pexels fallback failed: {e}")
        return []

def fetch_clips(fmt,story_id,n=4,title=""):
    """Fetch SportsDB images, falling back to Pexels if none found."""
    os.makedirs(BROLL_DIR,exist_ok=True)
    story = {"title": title, "format": fmt}
    images = get_sportsdb_images(story)
    if not images:
        log.warning(f"  No SportsDB images — trying Pexels fallback for: {title[:50]}")
        images = fetch_pexels_images(title, fmt)
    if not images:
        log.warning(f"  No images found at all — skipping video")
        return []
    # Pad to n by cycling
    while len(images) < n:
        images.append(images[len(images) % len(images)])
    images = images[:n]
    clips = []
    for i, url in enumerate(images):
        log.info(f"  Asset {i+1}: {url[:60]}")
        p = os.path.join(BROLL_DIR, f"broll_{story_id}_{i}.mp4")
        try:
            is_video = any(url.lower().endswith(e) for e in [".mp4",".mov",".webm"]) or "videos/files" in url
            if is_video:
                # Download Pexels video directly
                r = requests.get(url, timeout=30, stream=True)
                if r.status_code != 200:
                    log.warning(f"  Video {i+1} download failed: {r.status_code}"); continue
                tmp_v = os.path.join(BROLL_DIR, f"tmp_{story_id}_{i}.mp4")
                with open(tmp_v, "wb") as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
                cmd = ["ffmpeg", "-y", "-i", tmp_v,
                       "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
                       "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                       "-t", "15", "-pix_fmt", "yuv420p", "-r", "25", p]
                result = subprocess.run(cmd, capture_output=True, timeout=90)
                os.remove(tmp_v)
            else:
                # Download SportsDB image and convert with blur background
                ext = ".png" if url.lower().endswith(".png") else ".jpg"
                tmp_img = os.path.join(BROLL_DIR, f"img_{story_id}_{i}{ext}")
                r = requests.get(url, timeout=15)
                if r.status_code != 200:
                    log.warning(f"  Image {i+1} download failed: {r.status_code}"); continue
                open(tmp_img, "wb").write(r.content)
                # Blurred background fill + sharp centred image + dark overlay
                vf_img = (
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
                    "crop=1080:1920,gblur=sigma=35,eq=brightness=-0.3[bg];"
                    "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
                    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black@0[fg];"
                    "[bg][fg]overlay=0:0,"
                    "drawbox=x=0:y=0:w=1080:h=1920:color=black@0.35:t=fill,"
                    "eq=contrast=1.05:saturation=1.1"
                )
                cmd = ["ffmpeg", "-y", "-loop", "1", "-i", tmp_img,
                       "-filter_complex", vf_img,
                       "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                       "-t", "15", "-pix_fmt", "yuv420p", "-r", "25", p]
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                os.remove(tmp_img)
            if result.returncode == 0:
                log.info(f"  Clip {i+1} ready ({os.path.getsize(p)//1024}KB)")
                clips.append(p)
            else:
                log.error(f"  Clip {i+1} ffmpeg failed: {result.stderr[-100:]}")
        except Exception as e:
            log.error(f"  Clip {i+1} failed: {e}")
    return clips
def get_dur(p):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",p],capture_output=True,text=True)
    try: return float(r.stdout.strip())
    except: return 60.0
def assemble(story_id,clips,audio):
    os.makedirs(OUTPUT_DIR,exist_ok=True)
    out=os.path.join(OUTPUT_DIR,f"video_{story_id}.mp4")
    dur=min(get_dur(audio),58.0); cdur=dur/len(clips)
    log.info(f"  {dur:.1f}s audio / {len(clips)} clips / {cdur:.1f}s each")
    segs=[]
    for i,c in enumerate(clips):
        seg=os.path.join(BROLL_DIR,f"seg_{story_id}_{i}.mp4")
        vf=f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=brightness=-0.12:contrast=1.05,zoompan=z=\'min(zoom+0.0005,1.04)\':d={int(cdur*25)}:s=1080x1920:fps=25"
        r=subprocess.run(["ffmpeg","-y","-stream_loop","-1","-i",c,"-t",str(cdur),"-vf",vf,"-c:v","libx264","-preset","fast","-crf","23","-pix_fmt","yuv420p","-an",seg],capture_output=True,text=True)
        if r.returncode==0: segs.append(seg); log.info(f"  Seg {i+1} done")
        else: log.error(f"  Seg {i+1} failed: {r.stderr[-100:]}")
    if not segs: return None
    lp=os.path.join(BROLL_DIR,f"list_{story_id}.txt"); cp=os.path.join(BROLL_DIR,f"concat_{story_id}.mp4")
    with open(lp,"w") as f:
        for s in segs: f.write(f"file \'{s}\'\n")
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",lp,"-c","copy",cp],capture_output=True,text=True)
    r=subprocess.run(["ffmpeg","-y","-i",cp,"-i",audio,"-t",str(dur),"-vf","drawtext=text=\'90minWaffle\':fontsize=42:fontcolor=white@0.8:x=40:y=50:shadowcolor=black:shadowx=2:shadowy=2","-c:v","libx264","-preset","fast","-crf","22","-c:a","aac","-b:a","192k","-pix_fmt","yuv420p","-shortest",out],capture_output=True,text=True)
    if r.returncode==0:
        log.info(f"  Video: {out} ({os.path.getsize(out)//1024}KB)"); return out
    log.error(f"  Assembly failed: {r.stderr[-200:]}"); return None
def produce_video(story):
    sid=story["id"]; log.info(f"=== Story {sid}: {story['title'][:60]} ===")
    audio=generate_voiceover(story["script"],sid)
    if not audio: return None
    clips=fetch_clips(story.get("format","F7"),sid,n=4,title=story.get("title",""))
    video=assemble(sid,clips,audio) if clips else None
    if video:
        conn=get_db(); c=conn.cursor()
        c.execute("UPDATE stories SET video_path=?,status=\'video_ready\' WHERE id=?",(video,sid))
        conn.commit(); conn.close()
    return video
if __name__=="__main__":
    conn=get_db(); c=conn.cursor()
    c.execute("SELECT id,title,source,score,format,script FROM stories WHERE status=\'scripted\' ORDER BY score DESC LIMIT 1")
    r=c.fetchone(); conn.close()
    if r: produce_video({"id":r[0],"title":r[1],"source":r[2],"score":r[3],"format":r[4],"script":r[5]})
    else: print("No scripted stories")
