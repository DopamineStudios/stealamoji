import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Tokens (nom nom nom, tasty 🤤😝)
TOKEN = os.getenv("DISCORD_TOKEN")
DEBUG_MODE = os.getenv("LOGGING_DEBUG_MODE")
HEARTBEAT_URL = os.getenv("HEARTBEAT_URL")
if not DEBUG_MODE is None and DEBUG_MODE.lower() == "true":
    LOGGING_DEBUG_MODE = True
else:
    LOGGING_DEBUG_MODE = False
if not TOKEN:
    raise SystemExit("Set DISCORD_TOKEN in .env")