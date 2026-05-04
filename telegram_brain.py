import os
import requests
from datetime import datetime
from typing import Dict
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")   # Force load every time

class TelegramOpsBrain:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_REPORTS_CHAT_ID") or os.getenv("TELEGRAM_CHANNEL_ID")
        self.enabled = os.getenv("TELEGRAM_ENABLE", "true").lower() == "true"
        
        if not self.token or not self.chat_id:
            print("⚠️ Telegram Brain disabled - check .env")
            self.enabled = False
            return

        print(f"🟢 Telegram Ops Brain ACTIVE → 90min reports channel ({self.chat_id})")
        self.last_stats: Dict = {}

    def _send(self, emoji: str, title: str, body: str = "", priority: str = "normal"):
        if not self.enabled: return
        ts = datetime.now().strftime("%H:%M")
        msg = f"{emoji} <b>{title}</b> • {ts}\n\n{body}".strip()
        
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        if "WOMENS FOOTBALL" in body and "BBC" in body: return  # reduce noise
        payload = {
            "chat_id": self.chat_id,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": {"inline_keyboard": [[{"text": "Join Discussion on Discord", "url": "https://discord.com/channels/YOUR_SERVER/YOUR_BETS_CHANNEL"}]]},
            "disable_notification": priority != "high"
        }
        try:
            payload["text"] = payload.get("text", "") + "\n\n<a href=\"https://discord.gg/FdUSWMvE9C\">Join Discord for Full Discussion</a> | <a href=\"https://t.me/+u3BbsvldBAY4Zjlk\">Join VIP Telegram</a>"
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Telegram send failed: {e}")

    # 1. LIVE HEALTH
    def health_signal(self, stories=0, scripts=0, videos=0, queue="healthy"):
        body = f"Stories: {stories} | Scripts: {scripts} | Videos: {videos}\nQueue: {queue}"
        self._send("🟢", "Pipeline Cycle Complete - Healthy", body)

    # 2. ALERT
    def alert(self, issue: str, details: str = "", critical=True):
        emoji = "🔴" if critical else "🟠"
        self._send(emoji, f"ALERT: {issue}", details, priority="high")

    # 3. PERFORMANCE
    def performance_signal(self, content_type: str, change_pct: float, note: str = ""):
        if abs(change_pct) < 8: return
        dir = "↑" if change_pct > 0 else "↓"
        self._send("🟡", f"{content_type} {dir}{abs(change_pct):.0f}%", note)

    # 4. DAILY SUMMARY
    def daily_summary(self, stats: Dict):
        body = (f"Ingestion: {stats.get('ingested',0)}\n"
                f"Outputs: {stats.get('outputs',0)}\n"
                f"Best: {stats.get('best','N/A')}\n"
                f"Worst: {stats.get('worst','N/A')}")
        self._send("🔵", "Daily Intelligence Summary", body)
