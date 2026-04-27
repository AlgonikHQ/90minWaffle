# 90minWaffle 🧇⚽

Autonomous UK football content brand. RSS to script to video to Discord/Telegram/YouTube — fully automated. No human intervention required after deployment.

**Status:** Live — hourly cycles, 7 Discord channels, 6 Telegram channels
**Built by:** [@AlgonikHQ](https://twitter.com/90minwaffle) — part of the FIRE@45 automated income stack

---

## Pipeline

RSS Feeds -> Score -> Corroborate -> Script (Claude AI) -> Video (ElevenLabs + Pexels) -> Discord + Telegram + YouTube

---

## Stack

| Component | Technology |
|---|---|
| Scripting | Claude claude-opus-4-5 (JSON-enforced, dual-angle) |
| Voice | ElevenLabs only — no fallbacks ever |
| Video clips | Pexels API |
| Distribution | Discord (7 channels) + Telegram (6 channels) + YouTube |
| Odds intel | Odds API + API-Football |
| Football data | football-data.org (standings, results, scorers) |
| Storage | SQLite (data/waffle.db) |
| Runtime | systemd, hourly cycles, Ubuntu 24.04 (Hetzner VPS) |

---

## RSS Sources

| Source | Tier |
|---|---|
| BBC Sport Football | 1 |
| Sky Sports Football | 1 |
| Guardian Football | 2 |
| ESPN FC | 2 |
| 90min | 2 |
| Goal.com | 2 |
| Football365 | 2 |
| BBC Championship | 2 |
| Transfermarkt | 3 |

---

## Discord Channels

| Channel | Formats | Content |
|---|---|---|
| #breaking_news | F1, F2 | Confirmed transfers + rumours |
| #match_day | F3, F4 | Previews + post-match |
| #premier_league | F5 | Title race + weekly standings digest |
| #championship | BBC Champ/F365 | EFL Championship |
| #hot_takes | F7 | Opinions + community polls |
| #general | F6 | Star spotlights |
| #bets | Odds API | Daily value bets |

## Telegram Channels

| Channel | Content |
|---|---|
| News (public) | All formats F1-F7 with social buttons |
| Bets (public) | Value bet alerts with odds and edge % |
| Inside (private) | Hourly cycle reports |
| Queue (private) | Videos ready for Reels/TikTok |
| Reports (private) | Midnight daily summary |
| Alerts (private) | ElevenLabs quota warnings + RSS failures |

---

## Video Logic

- ElevenLabs voiceover only — no robot voice fallbacks ever
- Max 3 videos per day, score >= 75 required
- Max 1 video per cycle spread across the day
- ElevenLabs quota pre-checked before every video attempt
- All other stories post as branded cards with source links and social buttons

## Automated Schedule

| Time | Output |
|---|---|
| Every hour | RSS poll, score, script, card/video, all channels |
| 8am daily | PL + Championship standings digest |
| 9am daily | Match intel + value bets |
| Midnight | Daily summary to Reports channel |
| Sunday 9am BST | Podcast PDF to Inside channel |

---

## Versions

- **v1.0** — Full autonomous pipeline
- **v1.1** — Discord 7 channels, Telegram, Match Intel, Bet Alert
- **v1.2** — ElevenLabs + gTTS fallback
- **v1.3** — Script fixes, 4 new RSS feeds, Championship routing, Discord embeds
- **v2.0** — ElevenLabs-only, daily video cap, score gate, quota pre-check
- **v2.1** — Hourly cycles, all channels wired, branded cards, social buttons, polls
- **v2.2** — Daily standings digest, top scorers, Sunday podcast PDF

---

*Part of the AlgonikHQ FIRE@45 automated income stack. Follow [@90minWaffle](https://twitter.com/90minwaffle)*
