"""Sending drafts to the internal chat and publishing to the broadcast channel."""
from telethon import Button
from . import config
from .buttons import make_generate_button


async def show_loading(event, label="Przerabiam..."):
    """Swap buttons for a transient loading indicator."""
    try:
        msg = await event.get_message()
        await msg.edit(buttons=[[Button.inline(f"⏳ {label}", b"_noop")]])
    except Exception:
        pass


async def send_preview(bot, text, buttons, *, formatting_entities=None, reply_to=None):
    """Send a draft/message into the internal review chat (text-only)."""
    if formatting_entities:
        return await bot.send_message(
            config.INTERNAL_CHAT_ID, text, buttons=buttons,
            formatting_entities=formatting_entities, reply_to=reply_to,
        )
    return await bot.send_message(
        config.INTERNAL_CHAT_ID, text, buttons=buttons,
        parse_mode="html", reply_to=reply_to,
    )


async def publish_to_channel(bot, text):
    """Publish the final post to the public broadcast channel."""
    await bot.send_message(config.BROADCAST_CHANNEL_ID, text, parse_mode="html")


async def restore_buttons(bot, msg_id):
    """Restore the 🔍 Generuj button on the Phase-1 message (e.g. after a failed read)."""
    try:
        msg = await bot.get_messages(config.INTERNAL_CHAT_ID, ids=msg_id)
        if msg:
            await msg.edit(buttons=make_generate_button())
    except Exception:
        pass
