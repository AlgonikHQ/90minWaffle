#!/usr/bin/env python3
"""
season_reminder.py
Sends an annual Telegram reminder to update season_teams.py for the new season.
Scheduled via cron to fire 1st August each year.
"""
import asyncio, os, sys
sys.path.insert(0, "/root/90minwaffle/scripts")
from dotenv import load_dotenv
load_dotenv("/root/90minwaffle/.env")

from telegram import Bot

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
ALERTS_CHAT = int(os.getenv("TELEGRAM_ALERTS_CHAT_ID", 0))

MSG = (
    "🗓 SEASON UPDATE REMINDER — Action Required\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "New football season starting soon. Update Discord channel routing.\n\n"
    "FILE TO EDIT:\n"
    "/root/90minwaffle/scripts/season_teams.py\n\n"
    "WHAT TO UPDATE (top of file only):\n"
    "• PREMIER_LEAGUE — add promoted teams, remove relegated\n"
    "• CHAMPIONSHIP — add relegated PL teams, remove promoted\n"
    "• SCOTTISH_PREMIERSHIP — add promoted teams, remove relegated\n\n"
    "CHECK STANDINGS AT:\n"
    "• PL: bbc.co.uk/sport/football/premier-league/table\n"
    "• Championship: efl.com/competitions/efl-championship\n"
    "• Scottish: spfl.co.uk\n\n"
    "THEN RUN:\n"
    "python3 -m py_compile /root/90minwaffle/scripts/season_teams.py && echo OK\n"
    "systemctl restart 90minwaffle\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "Competition keywords (World Cup, Euros, UCL etc) are dynamic — no changes needed."
)

async def send():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id=ALERTS_CHAT,
        text=MSG
    )
    print("Season reminder sent to ALERTS_CHAT")

if __name__ == "__main__":
    asyncio.run(send())
