"""alertkonsumencki — Telegram review bot entrypoint.

Flow: drop a link/item in the internal chat → 🔍 Generuj → Claude drafts a consumer
alert → review/adjust → publish to the broadcast channel.
"""
import asyncio

import config  # noqa: F401 — loads .env before telegram.config reads it
import telegram
from telegram import config as tg_config
from telegram.client import create_bot
from telegram.queue_watcher import watch_queue
from core.state import load_state


async def main():
    load_state()

    bot = create_bot()
    await bot.start(bot_token=tg_config.BOT_TOKEN)
    telegram.register(bot)
    asyncio.create_task(watch_queue(bot))  # odbiera ostrzeżenia od crawlera

    me = await bot.get_me()
    print(
        f"[START] Bot @{me.username} gotowy. "
        f"internal={tg_config.INTERNAL_CHAT_ID} broadcast={tg_config.BROADCAST_CHANNEL_ID} "
        f"reviewers={tg_config.REVIEWER_IDS}"
    )

    # Fail-fast: sprawdź, czy bot potrafi rozwiązać kanał broadcast (częsty problem z prywatnymi kanałami).
    try:
        ch = await bot.get_entity(tg_config.BROADCAST_CHANNEL_ID)
        print(f"[START] Kanał broadcast OK: {getattr(ch, 'title', ch)}")
    except Exception as e:
        print(f"[START] UWAGA: nie mogę rozwiązać kanału broadcast ({tg_config.BROADCAST_CHANNEL_ID}): {e}")
        print("        → Najprościej: ustaw BROADCAST_CHANNEL_ID na @username kanału.")
        print("        → Albo (kanał prywatny): mając bota jako admina, wyślij dowolną wiadomość")
        print("          w kanale gdy bot działa — Telethon zcache'uje encję i publikacja zadziała.")

    await bot.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
