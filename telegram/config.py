"""Telegram-platform configuration.

`import config` (root) runs first via main.py, so load_dotenv() has already populated
the environment by the time this module reads it.
"""
import os
import config  # noqa: F401 — ensures .env is loaded

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Numeric Telegram user IDs allowed to press buttons / issue commands.
REVIEWER_IDS = [int(x.strip()) for x in os.getenv("REVIEWER_IDS", "").split(",") if x.strip()]

# Where drafts are reviewed. For direct-DM review this is your OWN user ID — the bot
# DMs you and you accept/decline there. Leave INTERNAL_CHAT_ID blank to default to the
# first reviewer's private chat with the bot.
_internal = os.getenv("INTERNAL_CHAT_ID", "").strip()
INTERNAL_CHAT_ID = int(_internal) if _internal else (REVIEWER_IDS[0] if REVIEWER_IDS else None)

# Public broadcast channel where approved posts are published.
# Accepts a numeric id (-100…) OR a @username. For a PRIVATE channel a bot often can't
# resolve it by numeric id (entity not cached) — prefer the @username if the channel has one.
def _chat(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw  # @username


BROADCAST_CHANNEL_ID = _chat(os.getenv("BROADCAST_CHANNEL_ID"))

# Deploy-webhook (osobny kontener na hoście — patrz ~/Documents/deploy-webhook).
DEPLOY_WEBHOOK_URL = os.getenv("DEPLOY_WEBHOOK_URL", "http://deploy_webhook:8099")
DEPLOY_WEBHOOK_TOKEN = os.getenv("DEPLOY_WEBHOOK_TOKEN", "")
