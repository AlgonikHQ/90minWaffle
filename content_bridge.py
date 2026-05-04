import sys
sys.path.insert(0, "/root")
import requests
import json
import os
import sqlite3
from datetime import datetime
from shared_intel import get_pending_content

DISCORD_BETS = os.getenv("DISCORD_WEBHOOK_BETS")
TELEGRAM_BETS = os.getenv("TELEGRAM_BETS_CHANNEL")

def mark_processed(fixture_id):
    conn = sqlite3.connect("/root/statiq/data/cache.db")
    conn.execute("UPDATE high_confidence_bets SET content_generated = 1 WHERE fixture_id = ?", (fixture_id,))
    conn.commit()
    conn.close()

def send_telegram(text, chat_id):
    if not chat_id: return
    try:
        from telegram_brain import TelegramOpsBrain
        brain = TelegramOpsBrain()
        brain._send("🔥", "Bet Edge", text)
    except:
        url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})

def generate_rich_preview(bet, public=False):
    data = json.loads(bet[1]) if isinstance(bet[1], str) else bet[1]
    score = data.get("score", 0)
    emoji = "🔒🔥" if score >= 10 else "🔒💎" if score >= 8 else "🔒✅"
    
    try:
        from image_resolver import get_match_image
        image_url = get_match_image(data.get("home"), data.get("away"))
    except:
        image_url = "https://via.placeholder.com/800x400/1a1a2e/ffffff?text=90minWaffle"

    if public:
        title = f"🔥 {data.get('home')} vs {data.get('away')} — Interesting Game!"
        color = 0xffaa00
        tagline = "Strong stats — worth watching!"
    else:
        title = f"{emoji} VIP EDGE: {data.get('home')} vs {data.get('away')}"
        color = 0xff00ff if score >= 10 else 0x00ff88
        tagline = "High confidence edge."

    embed = {
        "title": title,
        "description": f"**{data.get('market')}** • Confidence **{score}/12**",
        "color": color,
        "fields": [
            {"name": "Reason", "value": data.get("reasoning", "Strong stats")[:500]},
            {"name": "Factors", "value": " • ".join(data.get("layers", []))}
        ],
        "image": {"url": image_url},
        "footer": {"text": f"Kickoff ≈ {data.get('kickoff', 'Soon')} • {'VIP' if not public else 'Teaser'}"}
    }
    return {"embeds": [embed]}

def process_pending_bets():
    bets = get_pending_content()
    if not bets:
        return
    for bet in bets:
        try:
            if bet[2] and int(bet[2]) >= 9:   # Strong = VIP
                payload = generate_rich_preview(bet, public=False)
                if DISCORD_BETS:
                    requests.post(DISCORD_BETS, json=payload, timeout=10)
                send_telegram("VIP Edge Alert", TELEGRAM_BETS)
            else:   # Milder = Teaser
                payload = generate_rich_preview(bet, public=True)
                public_webhook = os.getenv("DISCORD_WEBHOOK_GENERAL")
                if public_webhook:
                    requests.post(public_webhook, json=payload, timeout=10)
                send_telegram("Bet Teaser", TELEGRAM_BETS)
            mark_processed(bet[0])
        except Exception as e:
            print("Error:", e)

if __name__ == "__main__":
    process_pending_bets()
