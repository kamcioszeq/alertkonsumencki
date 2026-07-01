"""Telethon bot client factory (single bot — no userbot)."""
import os
from telethon import TelegramClient
from . import config


def create_bot() -> TelegramClient:
    os.makedirs("session", exist_ok=True)
    return TelegramClient("session/bot", config.API_ID, config.API_HASH)
