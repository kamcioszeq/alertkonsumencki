"""Slash commands (/redeploy, /restart) that trigger a host-side deploy.sh run.

The bot runs inside a container with no access to podman/podman-compose, so it
can't invoke deploy.sh directly. Instead it drops a trigger file into session/ —
already bind-mounted to the host — which the host's deploy.sh watch loop (polling
every few seconds) picks up, actions, and deletes.
"""
from telethon import events

from . import config

REDEPLOY_TRIGGER_FILE = "session/.redeploy_trigger"


def _write_trigger(mode: str):
    with open(REDEPLOY_TRIGGER_FILE, "w") as f:
        f.write(mode)


def register_deploy_commands(bot):
    @bot.on(events.NewMessage(pattern=r"^/redeploy$"))
    async def on_redeploy(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        _write_trigger("deploy")
        await event.reply(
            "🔄 Redeploy zlecony — deploy.sh zaciągnie origin/main, zbuduje i "
            "podejmie akcję w ciągu kilku sekund."
        )

    @bot.on(events.NewMessage(pattern=r"^/restart$"))
    async def on_restart(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        _write_trigger("rebuild")
        await event.reply(
            "🔄 Restart zlecony — deploy.sh zaciągnie origin/main, zrobi rebuild "
            "i podejmie akcję w ciągu kilku sekund."
        )
