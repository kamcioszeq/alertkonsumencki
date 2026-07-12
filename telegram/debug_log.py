"""Bezwarunkowy logger KAŻDEJ wiadomości i callbacku — do diagnozy "bot nie odpowiada".
Loguje ZAWSZE, nawet gdy sender_id/chat_id nie pasują do REVIEWER_IDS/INTERNAL_CHAT_ID
(czyli nawet dla przypadków, które inne handlery po cichu odrzucają)."""
from telethon import events

from . import config


def register_debug_log(bot):
    @bot.on(events.NewMessage)
    async def on_any_message(event):
        text = (event.text or "")[:80]
        chat_id = getattr(event, "chat_id", None)
        print(
            f"[DEBUG_MSG] sender_id={event.sender_id} chat_id={chat_id} "
            f"is_reply={event.is_reply} text={text!r} | "
            f"REVIEWER_IDS={config.REVIEWER_IDS} INTERNAL_CHAT_ID={config.INTERNAL_CHAT_ID} | "
            f"sender_ok={event.sender_id in config.REVIEWER_IDS} chat_ok={chat_id == config.INTERNAL_CHAT_ID}"
        )

    @bot.on(events.CallbackQuery)
    async def on_any_callback(event):
        print(
            f"[DEBUG_CB] sender_id={event.sender_id} data={event.data} | "
            f"sender_ok={event.sender_id in config.REVIEWER_IDS}"
        )
