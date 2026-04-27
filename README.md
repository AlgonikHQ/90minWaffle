# 90minWaffle 🧇⚽

Autonomous UK football short-form video brand. RSS to script to video to Discord/Telegram/YouTube — fully automated.

## Pipeline
RSS Feeds → Score → Corroborate → Script (Claude AI) → Video (gTTS/ElevenLabs + Pexels) → Discord + Telegram + YouTube
## Stack

- **Scripting:** Claude claude-opus-4-5 (JSON-enforced, dual-angle F2/F3/F4 support)
- **Voice:** ElevenLabs (primary) → gTTS fallback on quota exhaustion
- **Video clips:** Pexels API
- **Distribution:** Discord (7 channels) + Telegram + YouTube auto-upload
- **Odds intel:** Odds API → `#bets` at 9am daily
- **Storage:** SQLite (`data/waffle.db`)
- **Runtime:** systemd service, 2-hour cycles, VPS (Ubuntu 24.04)

## RSS Sources (9 feeds)

| Source | Tier | Coverage |
|---|---|---|
| BBC Sport Football | 1 | PL + general |
| Sky Sports Football | 1 | PL + general |
| Guardian Football | 2 | PL + analysis |
| ESPN FC | 2 | PL + European |
| 90min | 2 | General |
| Goal.com | 2 | European + transfers |
| Football365 | 2 | Championship + PL |
| BBC Championship | 2 | EFL Championship |
| Transfermarkt | 3 | Transfer rumours |

## Discord Channels

| Channel | Format | Content |
|---|---|---|
| `#breaking-news` | F1, F2 | Confirmed transfers + rumours |
| `#match-day` | F3, F4 | Previews + post-match |
| `#premier-league` | F5 | Title race |
| `#general` | F6 | Star spotlights |
| `#hot-takes` | F7 | Opinions |
| `#championship` | BBC Champ/F365 | EFL content |
| `#bets` | Odds API | Daily value bets at 9am |

## Story Formats

| Format | Type | Angle |
|---|---|---|
| F1 | Confirmed Transfer | Mainstream |
| F2 | Transfer Rumour | Both angles |
| F3 | Match Preview | Both angles |
| F4 | Post-Match | Both angles |
| F5 | Title Race | Contrarian required |
| F6 | Star Spotlight | Mainstream |
| F7 | Hot Take | Contrarian required |

## Daily Limits

- Max 2 scripts per cycle
- Max 2 videos per cycle  
- Max 3 Discord posts per cycle
- Cleanup at 2am: deletes published video files, prunes holding stories >7 days

## Versions

- **v1.0** — Full autonomous pipeline
- **v1.1** — Discord 7 channels, Telegram, Match Intel, Bet Alert
- **v1.2** — gTTS ElevenLabs fallback, Telegram wired into orchestrator
- **v1.3** — Script bug fix (JSON enforcement, dual-angle format handling), 4 new RSS feeds, Championship routing, Discord embed upgrade, daily cleanup, daily limits tightened
