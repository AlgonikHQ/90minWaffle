# ⚽ 90minWaffle — Automated Football Media Network

**90minWaffle** is a fully automated football content engine that delivers breaking news reactions, AI-generated scripts, YouTube Shorts, Discord engagement, and Telegram cards within minutes of real-world events.

Built and run on a Hetzner VPS. Zero manual intervention required.

---

## 🚀 Pipeline — How It Works

Every 10 minutes the bot runs a full content cycle:

1. **RSS Poll** — 12 sources including BBC Sport, Sky Sports, Guardian, Football Italia, Planet Football, BBC European, BBC World Cup, Transfermarkt
2. **Reddit Poll** — r/soccer Here We Go, r/PremierLeague, r/soccer Hot (on heavy cycles)
3. **Score** — 8-format scoring system (F1 Confirmed Transfer → F9 Women's Football) with UCL boost, corroboration bonus, noise filter
4. **Corroborate** — cross-source entity matching promotes holding stories to shippable
5. **Cards** — Discord embeds + Telegram photo cards with player renders, editorial photos, Wikipedia images
6. **Script Gen** — Claude Sonnet generates hooks, mainstream/contrarian angles, captions
7. **Video Production** — ElevenLabs voiceover + word-sync captions + text overlay (Anton font, brand colours)
8. **YouTube Upload** — auto-uploads with custom thumbnail, winning hook as title
9. **Cleanup** — nightly at 2am UTC, resets stale scripts, frees video files, prunes old stories

Heavy cycles run every 60 minutes (every 6th poll). Light cycles handle cards and corroboration only.

---

## 📡 Content Formats

| Format | Type | Channel |
|--------|------|---------|
| F1 | Confirmed Transfer | #breaking-news |
| F2 | Transfer Rumour | #breaking-news (PL clubs) / #general |
| F3 | Match Preview | #match-day |
| F4 | Post-Match | #match-day |
| F5 | Title Race | #premier-league |
| F6 | Star Spotlight | #premier-league / #general |
| F7 | Hot Take | #hot-takes |
| F8 | Tips & Bets | #tips |
| F9 | Women's Football | #general |

---

## 🎯 Discord Channels

| Channel | Content |
|---------|---------|
| #breaking-news | Confirmed transfers and Here We Go stories only |
| #match-day | Team news, previews, UCL/Europa results, weekend previews |
| #hot-takes | Daily polls, opinion pieces, manager news |
| #premier-league | PL title race, top 4, relegation, standings digest |
| #championship | Championship clubs, play-off race |
| #general | Kit news, injury updates, women's football, awards, World Cup build-up, engagement content |
| #tips | Odds intel, value edge alerts (during fixture windows) |

---

## 🤖 Bot Stack

| Service | File | Purpose |
|---------|------|---------|
| `90minwaffle.service` | `orchestrator.py` | Main content pipeline — 10min cycles |
| `engagement_bot.service` | `engagement_bot.py` | Scheduled engagement — polls, trivia, guess the player |
| `interaction_bot.service` | `interaction_bot.py` | Discord slash commands — /poll, /guess |

---

## 🕐 Daily Schedule (UTC)

| Time | Content | Channel |
|------|---------|---------|
| 07:30 | Monday motivation quote | #general (Mon only) |
| 08:00 | On this day in football | #general |
| 08:00 | Morning standings digest (6 leagues) | #premier-league / #championship |
| 09:00 | Did you know? football fact | #general |
| 10:00 | Weekend preview prompt | #match-day (Fri/Sat only) |
| 10:30 | World Cup 2026 countdown + fact | #general (within 90 days) |
| 12:00 | Daily community poll | #hot-takes |
| 15:00 | Football trivia (spoiler answer) | #general (Mon/Wed/Fri) |
| 18:00 | Guess the player puzzle | #general (Tue/Thu) |
| 19:00 | Guess the player answer reveal | #general (Tue/Thu) |
| All day | Live news cards as stories break | Various channels |
| 02:00 | Nightly cleanup | Internal |

---

## 📊 Engagement Content Bank

492 items across 7 content types — no-repeat rotation tracked in SQLite:

- **256** On this day entries (full year coverage)
- **62** Did you know facts
- **50** Guess the player puzzles
- **49** Daily polls (day-aware)
- **40** Trivia questions
- **20** Monday motivation quotes
- **15** World Cup 2026 countdown facts

---

## 🛠️ Tech Stack

- **Language:** Python 3.12
- **Database:** SQLite (waffle.db)
- **Scheduler:** APScheduler
- **Discord:** nextcord (slash commands) + webhook embeds
- **Telegram:** python-telegram-bot
- **AI:** Claude Sonnet (script generation)
- **TTS:** ElevenLabs Starter (word-sync timestamps)
- **Video:** FFmpeg + Anton.ttf overlay
- **Images:** TheSportsDB (player renders) + Wikipedia API + Pexels + OG scrape
- **Hosting:** Hetzner VPS — Ubuntu 24.04
- **Process:** systemd services with auto-restart

---

## 💰 Quota Management

| Service | Plan | Limit | Strategy |
|---------|------|-------|----------|
| ElevenLabs | Starter | 30,401 chars/month | 1 video/day cap, dynamic quota check |
| Odds API | Free | 500 req/month | 2 leagues/day rotation (~60/month) |
| API-Football | Free | 100 req/day | Live match data only during fixture windows |
| YouTube Data API | Free | 10,000 units/day | ~6 uploads/day available |
| Anthropic Claude | Pay-per-use | ~$0.05/script | 1-3 scripts/heavy cycle |

---

## 🌍 World Cup 2026

The bot is World Cup ready:
- BBC World Cup RSS feed live and ingesting
- World Cup scoring keywords active (squad announcements, group draws, etc.)
- Daily countdown posts firing within 90 days of tournament
- F9 Women's Football format for diversity coverage
- 15 World Cup 2026 facts in the engagement content bank

**Tournament starts: 11 June 2026**

---

## 📡 Links

- X → [@90minWaffle](https://twitter.com/90minWaffle)
- YouTube → [@90minWaffle](https://youtube.com/@90minWaffle)
- TikTok → [@90minWaffle](https://tiktok.com/@90minWaffle)
- GitHub → [AlgonikHQ/90minWaffle](https://github.com/AlgonikHQ/90minWaffle)

---

**Built and maintained by [AlgonikHQ](https://github.com/AlgonikHQ)**

*"Football news without delay — 90 minutes reduced to seconds."*
