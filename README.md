# 90minWaffle — Autonomous Football Content Bot

> Fully automated football content pipeline. Ingests news, generates scripts, produces videos and distributes across YouTube Shorts, Discord and Telegram — hands free, every 2 hours.

## What it does

- Polls 5+ football news sources every 2 hours
- Scores stories 0-100 using a custom signal engine
- Generates punchy scripts with hook variants using Claude AI
- Produces vertical videos with ElevenLabs MLE voiceover
- Burns word-synced captions using Whisper AI
- Auto-posts to YouTube Shorts, Discord and Telegram queue
- Sends daily summaries and weekly performance reports

## Stack

- **AI:** Claude API (scripts), ElevenLabs (voice), Whisper (captions)
- **Video:** FFmpeg, Pexels b-roll
- **Distribution:** YouTube Data API v3, Telegram Bot API, Discord Webhooks
- **Infrastructure:** Ubuntu 24.04 VPS, systemd, SQLite, Python 3.12

## Architecture
RSS Sources → Scorer → Corroboration Engine → Claude Script Generator
→ ElevenLabs Voice → Pexels B-Roll → FFmpeg Assembly → Whisper Word-Sync
→ Telegram Queue → Discord → YouTube Shorts
## Services

- `90minwaffle.service` — Main orchestrator, runs every 2 hours
- Cron: Daily summary 21:00, Weekly report Sundays 20:00, Cleanup 03:00

## Built by

[@AlgonikHQ](https://x.com/AlgonikHQ) — Part of the AlgonikHQ trading and automation stack.

*Live bot: [@90minWaffle](https://x.com/90minWaffle)*
