from beacon import BeaconAutoShardedBot
import discord
import logging
from logging.handlers import RotatingFileHandler
from config import TOKEN, LOGGING_DEBUG_MODE, PROXY_USERNAME, PROXY_PASSWORD
import os
import traceback
import asyncio
import urllib.parse
from discord.gateway import DiscordWebSocket

if not TOKEN:
    raise SystemExit("ERROR: Set DISCORD_TOKEN in a .env in root folder.")

_original_send_as_json = DiscordWebSocket.send_as_json

async def mobile_send_as_json(self, data):
    if isinstance(data, dict) and data.get('op') == 2:
        properties = data.setdefault('d', {}).setdefault('properties', {})
        properties['$browser'] = 'Discord Android'
        properties['$device'] = 'Discord Android'
        properties['$os'] = 'Android'
        properties['browser'] = 'Discord Android'
        properties['device'] = 'Discord Android'
        properties['os'] = 'Android'

    await _original_send_as_json(self, data)

DiscordWebSocket.send_as_json = mobile_send_as_json

logger = logging.getLogger("discord")
if LOGGING_DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    print("Running logger in DEBUG mode")
else:
    logger.setLevel(logging.INFO)
    print("Running logger in PRODUCTION mode")
log_path = os.path.join(os.path.dirname(__file__), "discord.log")
handler = RotatingFileHandler(
    filename=log_path,
    encoding="utf-8",
    mode="a",
    maxBytes=1 * 1024 * 1024,
    backupCount=5
)
logger.addHandler(handler)

log_format = '%(asctime)s||%(levelname)s: %(message)s'
date_format = '%H:%M:%S %d-%m'

formatter = logging.Formatter(log_format, datefmt=date_format)

handler.setFormatter(formatter)

bot = BeaconAutoShardedBot(intents=discord.Intents.default(), minimal_caching=True, accent_colour=discord.Colour(0xf7c22b), bot_logger=logger)

if __name__ == "__main__":
    async def main_async():
        try:
            async with bot:
                await bot.start(TOKEN)
        except Exception as e:
            print(f"ERROR: Failed to start the bot: {e}")
            traceback.print_exc()


    asyncio.run(main_async())