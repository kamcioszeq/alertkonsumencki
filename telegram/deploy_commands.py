"""Slash commands (/redeploy, /restart, /rebuild, /check) that trigger a host-side
deploy.sh run, or report its last-known status.

The bot runs inside a container with no access to podman/podman-compose, so it
can't invoke deploy.sh directly. Instead it drops a trigger file into session/ —
already bind-mounted to the host — which the host's deploy.sh watch loop (polling
every few seconds) picks up, actions, and deletes. deploy.sh also writes its own
status (last mode/trigger/result) to session/deploy_status.json after every run,
which /check reads back.
"""
import json
from datetime import datetime, timezone

from telethon import events

from . import config

REDEPLOY_TRIGGER_FILE = "session/.redeploy_trigger"
DEPLOY_STATUS_FILE = "session/deploy_status.json"

TRIGGER_LABELS = {
    "manual_redeploy": "/redeploy",
    "manual_rebuild": "/restart lub /rebuild",
    "origin_main": "nowy commit na main",
    "local_files": "lokalne zmiany plików",
    "cli": "ręcznie (terminal)",
}

MODE_LABELS = {"deploy": "deploy", "rebuild": "rebuild (bez cache)", "restart": "restart (bez builda)"}


def _write_trigger(mode: str):
    with open(REDEPLOY_TRIGGER_FILE, "w") as f:
        f.write(mode)


def _format_ago(dt: datetime) -> str:
    delta = datetime.now(timezone.utc) - dt.astimezone(timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return f"{seconds}s temu"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min temu"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} godz. temu"
    return f"{hours // 24} dni temu"


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

    @bot.on(events.NewMessage(pattern=r"^/(restart|rebuild)$"))
    async def on_rebuild(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        _write_trigger("rebuild")
        await event.reply(
            "🔄 Rebuild zlecony — deploy.sh zaciągnie origin/main, zrobi rebuild "
            "i podejmie akcję w ciągu kilku sekund."
        )

    @bot.on(events.NewMessage(pattern=r"^/check$"))
    async def on_check(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        try:
            with open(DEPLOY_STATUS_FILE) as f:
                data = json.load(f)
        except FileNotFoundError:
            await event.reply("Brak informacji o żadnym deployu (deploy.sh jeszcze nie zapisał statusu).")
            return
        except (json.JSONDecodeError, OSError) as e:
            await event.reply(f"Nie udało się odczytać statusu deployu: {e}")
            return

        dt = datetime.fromisoformat(data["timestamp"])
        mode = MODE_LABELS.get(data.get("mode", ""), data.get("mode", "?"))
        trigger = TRIGGER_LABELS.get(data.get("trigger", ""), data.get("trigger", "?"))
        status = data.get("status", "?")
        icon = "✅" if status == "success" else "❌"

        await event.reply(
            f"📦 Ostatni deploy: {mode}\n"
            f"Źródło: {trigger}\n"
            f"{icon} Status: {'sukces' if status == 'success' else 'błąd'}\n"
            f"🕐 {dt.strftime('%Y-%m-%d %H:%M:%S')} ({_format_ago(dt)})"
        )
