"""Telegram platform package. `register(bot)` wires all handler groups."""
from .url_handlers import register_url_handlers
from .handlers import register_handlers
from .ingest import register_ingest


def register(bot):
    register_url_handlers(bot)
    register_handlers(bot)
    register_ingest(bot)
