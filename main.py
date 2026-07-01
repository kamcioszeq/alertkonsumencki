"""alertkonsumencki — Telegram review bot entrypoint.

Flow: drop a link/item in the internal chat → 🔍 Generuj → Claude drafts a consumer
alert → review/adjust → publish to the broadcast channel.
"""
import asyncio

import config  # noqa: F401 — loads .env before telegram.config reads it
import telegram
from telegram import config as tg_config
from telegram.client import create_bot
from core.state import load_state


async def main():
    load_state()

    bot = create_bot()
    await bot.start(bot_token=tg_config.BOT_TOKEN)
    telegram.register(bot)

    me = await bot.get_me()
    print(
        f"[START] Bot @{me.username} gotowy. "
        f"internal={tg_config.INTERNAL_CHAT_ID} broadcast={tg_config.BROADCAST_CHANNEL_ID} "
        f"reviewers={tg_config.REVIEWER_IDS}"
    )

    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
