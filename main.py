"""
╔══════════════════════════════════════════════════╗
║          Linuxx Ticketing System                 ║
║          Developed by wmikon                     ║
║          discord.py 2.7+ • Python 3.10+          ║
╚══════════════════════════════════════════════════╝
"""

import os
os.environ["PYTHONMALLOC"] = "malloc"
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN not found in .env — copy .env.example to .env and fill it in.")

# ── Intents ────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# ── Bot ────────────────────────────────────────────────────────
bot = commands.Bot(
    command_prefix="k!",
    intents=intents,
    help_command=None,
    case_insensitive=True,
    chunk_guilds_at_startup=False,  
    max_messages=100                 
)

COGS = ["cogs.setup", "cogs.tickets"]


@bot.event
async def on_ready():
    print("=" * 52)
    print("  ██╗     ██╗███╗   ██╗██╗   ██╗██╗  ██╗██╗  ██╗")
    print("  ██║     ██║████╗  ██║██║   ██║╚██╗██╔╝╚██╗██╔╝")
    print("  ██║     ██║██╔██╗ ██║██║   ██║ ╚███╔╝  ╚███╔╝ ")
    print("  ██║     ██║██║╚██╗██║██║   ██║ ██╔██╗  ██╔██╗ ")
    print("  ███████╗██║██║ ╚████║╚██████╔╝██╔╝ ██╗██╔╝ ██╗")
    print("  ╚══════╝╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝")
    print("=" * 52)
    print(f"  Bot      : {bot.user}")
    print(f"  ID       : {bot.user.id}")
    print(f"  Servers  : {len(bot.guilds)}")
    print(f"  Dev      : wmikon")
    print(f"  Brand    : Linuxx Ticketing")
    print("=" * 52)
    try:
        synced = await bot.tree.sync()
        print(f"  Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"  Slash sync failed: {e}")
    print("=" * 52)


async def main():
    async with bot:
        for cog in COGS:
            try:
                await bot.load_extension(cog)
                print(f"  ✅ Loaded: {cog}")
            except Exception as e:
                print(f"  ❌ Failed: {cog} — {e}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
