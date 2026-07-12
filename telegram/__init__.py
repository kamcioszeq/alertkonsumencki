"""Telegram platform package. `register(bot)` wires all handler groups."""
from .url_handlers import register_url_handlers
from .handlers import register_handlers
from .ingest import register_ingest
from .deploy_commands import register_deploy_commands
from .stats_handlers import register_stats_handlers
from .status_commands import register_status_commands


def register(bot):
    register_url_handlers(bot)
    register_handlers(bot)
    from facebook.handlers import register_facebook_handlers
    register_facebook_handlers(bot)
    register_ingest(bot)
    register_deploy_commands(bot)
    register_stats_handlers(bot)
    register_status_commands(bot)
