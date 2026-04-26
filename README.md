# 90minWaffle — Autonomous Football Content Bot

> Fully automated football content pipeline. Ingests news, generates scripts, produces videos and distributes across YouTube Shorts, Discord (7 channels) and Telegram — hands free, every 2 hours.

## What it does

- Polls 5+ football news sources every 2 hours via RSS
- Scores stories 0-100 using a custom multi-signal engine
- Corroborates stories across sources to surface high-confidence content
- Generates punchy scripts with hook variants using Claude AI
- Produces vertical videos with ElevenLabs voiceover + Whisper word-synced captions
- Routes content across 7 Discord channels by format type
- Posts to Telegram news channel with clean card formatting
- Posts daily odds cards to Discord #bets channel (Odds API)
- Sends cycle reports, daily summaries and weekly performance digests

## Stack

- **AI:** Claude API (scripts), ElevenLabs (voice), Whisper (captions)
- **Video:** FFmpeg, Pexels b-roll
- **Distribution:** YouTube Data API v3, Telegram Bot API, Discord Webhooks (7 channels)
- **Data:** The Odds API (UK football odds, daily)
- **Infrastructure:** Ubuntu 24.04 VPS, systemd, SQLite, Python 3.12

## Architecture
RSS Sources → Scorer → Corroboration Engine → Claude Script Generator
→ ElevenLabs Voice → Pexels B-Roll → FFmpeg Assembly → Whisper Word-Sync
→ Telegram Queue → Discord (7 channels) → YouTube Shorts
→ Match Intel (Odds API 9am daily) → Discord #bets
## Discord Channel Routing

| Format | Channel |
|--------|---------|
| F1 Confirmed Transfer | #breaking-news |
| F2 Transfer Rumour | #breaking-news |
| F3 Match Preview | #match-day |
| F4 Post-Match | #match-day |
| F5 Title Race | #premier-league |
| F6 Star Spotlight | #general |
| F7 Hot Take | #hot-takes |
| Odds Cards | #bets |

## Services

- `90minwaffle.service` — Main orchestrator, runs every 2 hours
- Cron: Daily summary 21:00, Weekly report Sundays 20:00, Cleanup 03:00

## Scripts

| Script | Purpose |
|--------|---------|
| `orchestrator.py` | Main cycle controller — 8 steps |
| `rss_poller.py` | Ingests football news from 5+ sources |
| `scorer.py` | Scores and classifies stories 0-100 |
| `script_generator.py` | Claude AI script + hook generation |
| `video_producer.py` | FFmpeg video assembly |
| `text_overlay.py` | Whisper caption burning |
| `discord_poster.py` | Routes stories to 7 Discord channels |
| `telegram_poster.py` | Posts news cards to Telegram |
| `match_intel.py` | Daily odds cards via Odds API |
| `bet_alert.py` | Value bet scanner (Odds API) |
| `queue_notifier.py` | Telegram queue notifications |
| `youtube_uploader.py` | YouTube Shorts upload |
| `report_generator.py` | Daily/weekly digest reports |

## Changelog

### v1.1 — 2026-04-26
- Discord poster rebuilt: all 7 channels wired, clean public embed format
- Telegram poster syntax fixed, posting live
- Match Intel added: daily odds cards to #bets at 9am
- Bet alert scanner added (Odds API, value edge detection)
- Orchestrator async errors fixed, full 8-step cycle running clean
- README updated

### v1.0 — Launch
- Full pipeline live: RSS → Score → Script → Video → Whisper → Telegram → Discord → YouTube

## Built by

[@AlgonikHQ](https://x.com/AlgonikHQ) — Part of the AlgonikHQ trading and automation stack.

*Live bot: [@90minWaffle](https://x.com/90minWaffle)*
