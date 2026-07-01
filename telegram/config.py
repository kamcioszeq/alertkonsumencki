"""Telegram-platform configuration.

`import config` (root) runs first via main.py, so load_dotenv() has already populated
the environment by the time this module reads it.
"""
import os
import config  # noqa: F401 — ensures .env is loaded

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Internal review chat (drafts land here) and public broadcast channel (published posts).
INTERNAL_CHAT_ID = int(os.getenv("INTERNAL_CHAT_ID"))
BROADCAST_CHANNEL_ID = int(os.getenv("BROADCAST_CHANNEL_ID"))

# Numeric Telegram user IDs allowed to press buttons / issue commands.
REVIEWER_IDS = [int(x.strip()) for x in os.getenv("REVIEWER_IDS", "").split(",") if x.strip()]
