# ⚽ 90minWaffle — Automated Football Media Network

**90minWaffle** is a fully automated football content engine that delivers breaking news reactions, AI-generated scripts, YouTube Shorts, Discord channel posts, and Telegram cards within minutes of real-world events — zero manual intervention required.

Built and run on a Hetzner VPS. Driven by Claude Sonnet, ElevenLabs TTS, and a multi-layer content intelligence pipeline.

---

## 🚀 Pipeline — How It Works

Every 10 minutes the bot runs a full content cycle:

1. **RSS Poll** — 11 curated sources across Tier 1 and Tier 2 (see Sources below)
2. **Score** — 9-format scoring system with UCL boost, source tier weighting, noise filter (horse racing, F1, cricket, tennis, golf all filtered)
3. **Corroborate** — cross-source entity matching: 2 sources = +20pts, 3+ sources = +35pts
4. **Cards** — Discord embeds + Telegram photo cards with 4-layer image waterfall (OG scrape → RSS media → Wikipedia → TheSportsDB → branded placeholder)
5. **Script Gen** — Claude Sonnet generates 3 hook variants, mainstream/contrarian angles, caption, thumbnail text. Verified stats fed from cache — no invented numbers
6. **Video Production** — ElevenLabs voiceover + word-sync captions + text overlay (Anton font, brand colours)
7. **YouTube Upload** — auto-uploads with winning hook as title, custom thumbnail
8. **Discord Routing** — intelligent competition-aware routing to 13 specialist channels
9. **Telegram** — branded cards to public news channel with inline buttons
10. **Match Threads** — F3 previews auto-create Discord threads, F4 results post into same thread
11. **Prediction Game** — pre-match vote embed posted to relevant channel, result resolved automatically
12. **Performance Tracking** — Telegram view counts fed back into DB, weights future similar content
13. **Cleanup** — nightly at 2am UTC

Heavy cycles run every 60 minutes (every 6th poll). Light cycles handle cards and corroboration only.

---

## 📡 RSS Sources

### Tier 1
| Source | Feed |
|--------|------|
| BBC Sport Football | Main football feed |
| Sky Sports Football | Live news and transfers |
| BBC European Football | UCL/UEL/UECL |
| BBC World Cup | World Cup 2026 build-up |
| BBC Women's Football | WSL, Lionesses, Women's UCL |

### Tier 2
| Source | Feed |
|--------|------|
| Guardian Football | Long-form and analysis |
| Football365 | Opinion and breaking news |
| Football Italia | Serie A and Italian transfers |
| Planet Football | Stats and features |
| Transfermarkt News | Transfer market intelligence |
| ESPN FC | Broad European coverage |

---

## 📊 Content Formats

| Format | Type | Threshold | Default Channel |
|--------|------|-----------|-----------------|
| F1 | Confirmed Transfer | Score ≥ 40 | #breaking-news |
| F2 | Transfer Rumour | Score ≥ 35 | #breaking-news (PL) / #general |
| F3 | Match Preview | Score ≥ 30 | #match-day |
| F4 | Post-Match | Score ≥ 30 | #match-day |
| F5 | Title Race | Score ≥ 30 | #premier-league |
| F6 | Star Spotlight | Score ≥ 35 | #premier-league / #general |
| F7 | Hot Take | Score ≥ 28 | #hot-takes |
| F8 | Tips & Bets | Score ≥ 40 | #tips |
| F9 | Women's Football | Score ≥ 28 | #womens-football |

---

## 🎯 Discord Channels

### Core channels
| Channel | Content |
|---------|---------|
| #breaking-news | Confirmed transfers and Here We Go stories only |
| #match-day | Team news, previews, results — all competitions |
| #hot-takes | Daily polls, opinion pieces, manager news, community debate |
| #premier-league | PL title race, top 4, relegation, standings digest |
| #championship | EFL Championship clubs, play-off race |
| #general | Kit news, injury updates, awards, filler engagement |
| #tips | Odds intel, value edge alerts during fixture windows |

### Specialist channels (added May 2026)
| Channel | Content | Routing |
|---------|---------|---------|
| #womens-football | WSL, NWSL, Women's UCL, Lionesses, F9 format | Hardlined — F9 always routes here |
| #world-cup | FIFA World Cup 2026, qualifiers, squad news | World Cup keywords |
| #euros-talk | UEFA Euros, Nations League | Euros/NL keywords |
| #european-cups | UCL, UEL, UECL — clubs only | Champions/Europa League keywords |
| #domestic-trophies | FA Cup, Carabao Cup, Community Shield, FA Trophy, FA Vase | Hardlined English cups only |
| #scottish-football | Scottish Premiership, Scottish Cup, Scottish League Cup | SPFL keywords + team names |

**Routing priority:** Women's → World Cup → Euros → European Cups → Domestic Trophies → Scottish → Championship → Format fallback

---

## 🧠 Content Intelligence

### Stat engine
Verified stats fed to Claude before every script — no invented numbers allowed:
- **Premier League:** title race, top scorer, team position, form, relegation zone
- **Champions League:** top 4 standings, recent results
- **Championship:** top 2, top scorer, team position
- **Scottish Premiership:** title race, bottom 3, team position

Competition auto-detected from story title. Correct stat block selected automatically.

### Corroboration
Stories covered by multiple sources get boosted:
- 2 sources: +20 points
- 3+ sources: +35 points

### Performance feedback
Telegram view counts written back to DB after 1h, 24h, 7d. Performance score (0-100) applied to weight future similar format/source combinations.

### Match threads
- F3 preview posted → Discord thread created automatically
- Community prediction prompt dropped in thread (🏠 home / 🤝 draw / ✈️ away)
- F4 result posted → automatically routes into same thread

### Prediction game
Pre-match vote embed posted to relevant channel. Bot seeds 🏠/🤝/✈️ reactions. Result resolved and posted when F4 publishes.

---

## 🤖 Bot Stack

| Service | File | Purpose |
|---------|------|---------|
| `90minwaffle.service` | `orchestrator.py` | Main content pipeline — 10min cycles |
| `engagement_bot.service` | `engagement_bot.py` | Scheduled engagement — polls, trivia, guess the player |
| `interaction_bot.service` | `interaction_bot.py` | Discord slash commands |

---

## 🕐 Engagement Schedule (UTC)

| Time | Content | Channel |
|------|---------|---------|
| 07:30 | Monday motivation quote | #general (Mon only) |
| 08:00 | On this day in football | #general |
| 09:00 | Did you know? football fact | #general |
| 10:00 | Weekend preview prompt | #match-day (Fri/Sat) |
| 10:30 | World Cup 2026 countdown | #world-cup (within 90 days) |
| 12:00 | Daily community poll | #hot-takes (or specialist channel) |
| 15:00 | Football trivia | #general (Mon/Wed/Fri) |
| 18:00 | Guess the player puzzle | #general (Tue/Thu) |
| 19:00 | Guess the player answer | #general (Tue/Thu) |
| All day | Live news cards as stories break | Specialist channels |
| 02:00 | Nightly cleanup | Internal |

---

## 📊 Engagement Content Bank

492 items across 7 content types — no-repeat rotation tracked in SQLite:

| Type | Count | Notes |
|------|-------|-------|
| On this day | 256 | Full year coverage |
| Did you know | 62 | Football facts |
| Guess the player | 50 | Clue-based puzzles |
| Daily polls | 49 | Day-aware routing |
| Trivia | 40 | Spoiler answers |
| Monday quotes | 20 | Manager/player quotes |
| World Cup facts | 15 | 2026 countdown |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.12 |
| Database | SQLite (waffle.db) |
| Scheduler | APScheduler |
| Discord | nextcord + webhook embeds |
| Telegram | python-telegram-bot |
| AI Scripts | Claude Sonnet 4 |
| TTS | ElevenLabs Starter |
| Video | FFmpeg + Anton.ttf overlay |
| Images | OG scrape → Wikipedia → TheSportsDB → branded placeholder |
| Season data | season_teams.py — single source of truth, update each August |
| Hosting | Hetzner VPS — Ubuntu 24.04, 135.181.47.92 |
| Process | systemd services with Restart=always |

---

## 💰 Quota Management

| Service | Plan | Limit | Strategy |
|---------|------|-------|----------|
| ElevenLabs | Starter | 30,401 chars/month | 1 video/day cap, dynamic quota check |
| Odds API | Free | 500 req/month | 2 leagues/day rotation (~60/month) |
| Anthropic Claude | Pay-per-use | ~$0.05/script | 1-3 scripts/heavy cycle |
| YouTube Data API | Free | 10,000 units/day | ~6 uploads/day available |

---

## 🗓️ Season Maintenance

Team lists (Premier League, Championship, Scottish Premiership) are stored in one file:
/root/90minwaffle/scripts/season_teams.py
**Update each August when promotion/relegation is confirmed:**

```bash
nano /root/90minwaffle/scripts/season_teams.py
# Edit PREMIER_LEAGUE, CHAMPIONSHIP, SCOTTISH_PREMIERSHIP only
python3 -m py_compile /root/90minwaffle/scripts/season_teams.py && echo OK
systemctl restart 90minwaffle
```

A Telegram reminder fires automatically to the private alerts channel on 1st August each year.

Competition keywords (World Cup, Euros, UCL, FA Cup etc) never need updating.

---

## 🌍 World Cup 2026

The bot is fully World Cup ready:
- Dedicated `#world-cup` Discord channel live
- BBC World Cup RSS feed ingesting
- World Cup scoring keywords active
- Daily countdown posts routing to `#world-cup` within 90 days of tournament
- 15 World Cup 2026 facts in engagement content bank

**Tournament starts: 11 June 2026**

---

## 📡 Links

- X → [@90minWaffle](https://twitter.com/90minWaffle)
- YouTube → [@90minWaffle](https://youtube.com/@90minWaffle)
- TikTok → [@90minWaffle](https://tiktok.com/@90minWaffle)
- Instagram → [@90minWaffle](https://instagram.com/90minwaffle)
- Discord → [Join the server](https://discord.gg/90minwaffle)
- GitHub → [AlgonikHQ/90minWaffle](https://github.com/AlgonikHQ/90minWaffle)

---

**Built and maintained by [AlgonikHQ](https://github.com/AlgonikHQ)**

*"Football news without delay — 90 minutes reduced to seconds."*
