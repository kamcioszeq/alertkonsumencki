"""Sending drafts to the internal chat and publishing to the broadcast channel.

Drafts stay text-only (easy to edit/regenerate); the static alert image is attached to
the handoff message and to the final published post.
"""
import os

from telethon import Button

import config as root_config
from . import config
from .buttons import make_generate_button


def _alert_image():
    p = root_config.ALERT_IMAGE
    return p if p and os.path.exists(p) else None


async def show_loading(event, label="Przerabiam..."):
    """Swap buttons for a transient loading indicator."""
    try:
        msg = await event.get_message()
        await msg.edit(buttons=[[Button.inline(f"⏳ {label}", b"_noop")]])
    except Exception:
        pass


async def send_preview(bot, text, buttons, *, formatting_entities=None, reply_to=None):
    """Send a draft/message (text-only) into the internal review chat."""
    if formatting_entities:
        return await bot.send_message(
            config.INTERNAL_CHAT_ID, text, buttons=buttons,
            formatting_entities=formatting_entities, reply_to=reply_to,
        )
    return await bot.send_message(
        config.INTERNAL_CHAT_ID, text, buttons=buttons,
        parse_mode="html", reply_to=reply_to,
    )


async def send_alert_photo(bot, caption, buttons, *, reply_to=None):
    """Send the static alert image + caption + buttons to the internal chat.
    Falls back to a text message if the image file is missing."""
    img = _alert_image()
    if img:
        return await bot.send_file(
            config.INTERNAL_CHAT_ID, img, caption=caption, buttons=buttons,
            parse_mode="html", reply_to=reply_to,
        )
    return await bot.send_message(
        config.INTERNAL_CHAT_ID, caption, buttons=buttons,
        parse_mode="html", reply_to=reply_to,
    )


async def publish_to_channel(bot, text, *, image=None):
    """Publish the final post to the broadcast channel, always with alert.png when available.

    Telegram photo captions max out at 1024 chars, so longer posts go as image + text message.
    """
    img = image if (image and os.path.exists(image)) else _alert_image()
    if not img:
        await bot.send_message(config.BROADCAST_CHANNEL_ID, text, parse_mode="html")
        return
    if len(text) <= 1024:
        await bot.send_file(config.BROADCAST_CHANNEL_ID, img, caption=text, parse_mode="html")
    else:
        await bot.send_file(config.BROADCAST_CHANNEL_ID, img)
        await bot.send_message(config.BROADCAST_CHANNEL_ID, text, parse_mode="html")


async def restore_buttons(bot, msg_id):
    """Restore the 🔍 Generuj button on the Phase-1 message (e.g. after a failed read)."""
    try:
        msg = await bot.get_messages(config.INTERNAL_CHAT_ID, ids=msg_id)
        if msg:
            await msg.edit(buttons=make_generate_button())
    except Exception:
        pass
