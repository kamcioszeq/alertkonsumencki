"""Telegram platform package. `register(bot)` wires all handler groups."""
from .url_handlers import register_url_handlers
from .handlers import register_handlers
from .ingest import register_ingest


def register(bot):
    register_url_handlers(bot)
    register_handlers(bot)
    from facebook.handlers import register_facebook_handlers
    register_facebook_handlers(bot)
    register_ingest(bot)
