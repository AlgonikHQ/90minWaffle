import os, random, logging, nextcord
from nextcord.ext import commands
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

LOG_PATH = "/root/90minwaffle/logs/interaction_bot.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger("interaction_bot")

intents = nextcord.Intents.default()
intents.message_content = True  # required for reading messages

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    log.info(f"✅ Logged in as {bot.user}")

# Simple “Guess the Player” interactive post
@bot.slash_command(description="Post an interactive Guess-The-Player message")
async def guess(interaction: nextcord.Interaction):
    players = [
        {"clues": ["Played in Serie A & Premier League", "100+ career goals"], "answer": "Edin Džeko"},
        {"clues": ["Ex‑Arsenal + Chelsea midfielder", "Known for long shots"], "answer": "Cesc Fàbregas"},
    ]
    p = random.choice(players)
    clues = "\n".join([f"• {c}" for c in p["clues"]])

    button = nextcord.ui.Button(label="Reveal Answer", style=nextcord.ButtonStyle.primary)
    async def reveal(interaction_inner: nextcord.Interaction):
        await interaction_inner.response.send_message(f"✅ Answer: **{p['answer']}**", ephemeral=False)
    button.callback = reveal

    view = nextcord.ui.View()
    view.add_item(button)

    embed = nextcord.Embed(
        title="🕵️ Guess The Player!",
        description=f"{clues}\n\nClick below to reveal 👇",
        color=0x3498DB,
    )
    await interaction.response.send_message(embed=embed, view=view)

# Poll with agree/disagree buttons
@bot.slash_command(description="Create an interactive poll")
async def poll(interaction: nextcord.Interaction, question: str):
    yes = nextcord.ui.Button(label="Agree ✅", style=nextcord.ButtonStyle.success)
    no  = nextcord.ui.Button(label="Disagree ❌", style=nextcord.ButtonStyle.danger)

    async def yes_cb(i):
        await i.response.send_message("✅ You agreed!", ephemeral=True)
    async def no_cb(i):
        await i.response.send_message("❌ You disagreed!", ephemeral=True)

    yes.callback, no.callback = yes_cb, no_cb
    view = nextcord.ui.View()
    for b in (yes, no):
        view.add_item(b)

    embed = nextcord.Embed(title="🗳 Community Poll", description=question, color=0xFF9800)
    await interaction.response.send_message(embed=embed, view=view)

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not DISCORD_TOKEN:
    log.error("Missing DISCORD_BOT_TOKEN in .env")
else:
    bot.run(DISCORD_TOKEN)
