# ⚽ 90minWaffle — Automated Football Media Network

**90minWaffle** is a fully automated football content engine designed to deliver breaking‑news reactions, AI‑generated scripts, and YouTube Shorts within minutes of real‑world events.

---

## 🚀 How It Works
Every 60 minutes the bot runs an end‑to‑end content pipeline:

1. Refreshes fixtures, standings & top scorers  
2. Collects news from trusted RSS feeds  
3. Scores stories for "postability" — transfers, manager moves, match previews, hot takes  
4. Cross‑checks multiple sources → marks top stories as “shippable”  
5. Auto‑generates branded cards and pushes to Discord + Telegram within seconds  
6. Uses Claude for scriptwriting and hook selection  
7. Generates voiceovers via ElevenLabs  
8. Edits and renders Shorts with subtitles  
9. Auto‑uploads to YouTube Shorts (+ manual posting to TikTok / Reels)

---

## 🧠 Engagement Automation
Two Python services run alongside the main news cycle:

- **`engagement_bot.py`** — daily polls (“Who wins tonight?”, “Rate this transfer”), guess‑the‑player games, and scheduled discussion prompts.  
- **`interaction_bot.py`** — interactive slash‑commands (`/poll`, `/guess`) with real Discord buttons.

Together, they turn Discord into a 24/7 football community.

---

## 🛠️ Stack
`Python 3.12`  `APScheduler`  `nextcord`  `requests`  `sqlite3`  `discord.py (webhooks)`  
`Claude API`  `ElevenLabs TTS`  `YouTube Data API v3`  `systemd`  `Hetzner VPS`

---

## 📂 Key Channels
| Channel | Purpose |
|----------|----------|
| 📰 `#breaking-news` | instant feeds of verified stories |
| ⚽ `#match-day` | live chat during fixtures |
| 🔥 `#hot-takes` | daily debate threads |
| 🧩 `#guess-the-player` | interactive games every noon |

---

## 🕹️ Automation Schedule
| Time (UTC) | Task |
|-------------|------|
| 08:00 | standings + top‑scorers digest |
| 09:00 | morning poll |
| 12:00 | guess‑the‑player |
| 15:00 | hot‑take debate |
| 18:00 | match predictions |
| 00:00 | summary + cleanup |

---

## 📡 Links
X → [@90minWaffle](https://twitter.com/90minWaffle) • YouTube → [@90minWaffle](https://youtube.com/@90minWaffle) • TikTok → [@90minWaffle](https://tiktok.com/@90minWaffle)

---

**Built and maintained by [AlgonikHQ](https://github.com/AlgonikHQ)**  
“Football news without delay — 90 minutes reduced to seconds.”
