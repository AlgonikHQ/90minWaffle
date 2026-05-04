# 90minWaffle Bot

Automated football content bot. Generates, scores, and posts short-form video content to YouTube daily, with X cross-posting and Discord channel routing.

## Architecture

- `orchestrator.py` — main loop, runs every 10 min, manages daily cap and score gate
- `script_gen.py` — generates video scripts via LLM
- `scorer.py` — scores scripts, gate threshold VIDEO_SCORE_GATE=55
- `video_assembler.py` / `ffmpeg_assembler.py` — assembles video from script + TTS
- `image_resolver.py` — resolves match/player imagery
- `text_overlay.py` — adds text overlays to video
- `telegram_poster.py` — Telegram notifications
- `queue_notifier.py` — queue management alerts
- `brand_compositor.py` — brand overlay layer
- `hook_generator.py` — generates video hooks
- `statiq_bridge.py` — StatiqFC data bridge
- `sportsdb_registry.py` — sports DB lookups
- `content_bridge.py` — content routing
- `daily_digest.py` — daily summary
- `performance_tracker.py` — video performance tracking

## Posting Schedule

- 1 video/day minimum (guaranteed floor)
- VIDEO_SCORE_GATE=55 (scripts below threshold discarded)
- POST_SPACING_SECONDS=240
- Bot checks every 10 min (--loop --interval 10)
- Reddit poller disabled (reddit_poller.py.disabled)

## TTS

- ElevenLabs Starter tier (~30K chars/month)
- ~870 chars/video average
- ~34 videos/month capacity

## Discord Channels

6 active Discord channels with intelligent content routing:
- Match threads
- Prediction game
- Performance feedback
- World Cup 2026 dedicated channel (tournament starts 11 June 2026)

## Services

- `90minwaffle.service` — main orchestrator loop
- Auth: `/root/90minwaffle/youtube_token.json`
- DB: `/root/90minwaffle/data/waffle.db`
- Logs: `/root/90minwaffle/logs/`

## Stack

- Python 3.11
- systemd (90minwaffle.service)
- Hetzner VPS Ubuntu 24.04
- YouTube Data API v3
- ElevenLabs TTS (Starter)
- Discord Webhooks
- X (Twitter) API

## Season Teams Update (Annual — 1st August)

```bash
nano /root/90minwaffle/scripts/season_teams.py
python3 -m py_compile /root/90minwaffle/scripts/season_teams.py && echo OK
systemctl restart 90minwaffle
```

A Telegram reminder fires automatically to the private alerts channel on 1st August each year.

## World Cup 2026

- Dedicated `#world-cup` Discord channel live
- BBC World Cup RSS feed ingesting
- Daily countdown posts within 90 days of tournament
- 15 World Cup 2026 facts in engagement content bank
- **Tournament starts: 11 June 2026**

## Links

- X → [@90minWaffle](https://twitter.com/90minWaffle)
- YouTube → [@90minWaffle](https://youtube.com/@90minWaffle)
- Discord → [Join the server](https://discord.gg/90minwaffle)
- GitHub → [AlgonikHQ/90minWaffle](https://github.com/AlgonikHQ/90minWaffle)

---

**Built and maintained by [AlgonikHQ](https://github.com/AlgonikHQ)**

*"Football news without delay — 90 minutes reduced to seconds."*
