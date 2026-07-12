"""Slash commands (/redeploy, /restart, /rebuild, /check) — wołają deploy-webhook,
osobny mały serwis w podmanie (~/Documents/deploy-webhook, wspólna sieć deploy_net),
który MA dostęp do prawdziwego podmana hosta (przez zamontowany socket) i robi
realny git pull + podman-compose rebuild/restart.

Bot NIE czeka na wynik — wysyła żądanie i od razu odpowiada. Powody:
1) deploy-webhook sam robi to w tle i sam wysyła "🔄 initiated"/"✅ done" na
   Telegram (czyta BOT_TOKEN wprost z zamontowanego .env) — nie musimy czekać.
2) Nawet gdybyśmy chcieli czekać, nie moglibyśmy: /restart każe zrestartować
   WŁASNY kontener bota — proces obsługujący to żądanie może zginąć w trakcie
   force-recreate, zanim zdąży odebrać odpowiedź HTTP.

/check czyta session/deploy_status.json, który zapisuje deploy-webhook (ten sam
format co wcześniej pisał deploy.sh) — więc działa bez zmian.

UWAGA przy dalszej pracy nad tym plikiem: deploy-webhook przed KAŻDYM rebuildem
robi `git reset --hard origin/main` na tym repo (bo to ten sam bind-mount) —
jeśli zmienisz ten plik i przetestujesz /rebuild PRZED commitem+pushem, webhook
skasuje Twoje niezacommitowane zmiany w trakcie własnego testu. Commituj i pushuj
PRZED testowaniem, nie po.
"""
import json
from datetime import datetime, timezone

import httpx
from telethon import events

from . import config

DEPLOY_STATUS_FILE = "session/deploy_status.json"

TRIGGER_LABELS = {
    "manual_redeploy": "/redeploy",
    "manual_rebuild": "/restart lub /rebuild",
    "origin_main": "nowy commit na main",
    "cli": "ręcznie (terminal)",
}

MODE_LABELS = {"deploy": "deploy", "rebuild": "rebuild", "restart": "restart (bez builda)"}


async def _trigger_webhook(mode: str) -> str:
    """Wysyła żądanie do deploy-webhook. Zwraca komunikat błędu albo "" gdy przyjęte."""
    url = f"{config.DEPLOY_WEBHOOK_URL}/deploy/alertkonsumencki"
    print(f"[DEPLOY_CMD] próba połączenia: POST {url} mode={mode}")
    if not config.DEPLOY_WEBHOOK_TOKEN:
        print("[DEPLOY_CMD] brak DEPLOY_WEBHOOK_TOKEN w .env")
        return "Brak DEPLOY_WEBHOOK_TOKEN w .env — deploy-webhook nie skonfigurowany."
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                url, json={"mode": mode}, headers={"X-Auth-Token": config.DEPLOY_WEBHOOK_TOKEN},
            )
        print(f"[DEPLOY_CMD] odpowiedź: HTTP {r.status_code} {r.text[:200]}")
        if r.status_code == 202:
            return ""
        if r.status_code == 401:
            return "Zły token — sprawdź DEPLOY_WEBHOOK_TOKEN w obu .env (bot i deploy-webhook)."
        return f"deploy-webhook: HTTP {r.status_code} {r.text[:200]}"
    except Exception as e:
        print(f"[DEPLOY_CMD] BŁĄD połączenia ({type(e).__name__}): {e}")
        return f"Nie udało się połączyć z deploy-webhook ({type(e).__name__}): {e}"


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
        err = await _trigger_webhook("deploy")
        if err:
            await event.reply(f"❌ {err}")
            return
        await event.reply(
            "🔄 Redeploy zlecony do deploy-webhook — zaciągnie origin/main, zbuduje "
            "i wystartuje. Dostaniesz powiadomienie o postępie."
        )

    @bot.on(events.NewMessage(pattern=r"^/(restart|rebuild)$"))
    async def on_rebuild(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        err = await _trigger_webhook("rebuild")
        if err:
            await event.reply(f"❌ {err}")
            return
        await event.reply(
            "🔄 Rebuild zlecony do deploy-webhook — zaciągnie origin/main, zbuduje "
            "i wystartuje. Dostaniesz powiadomienie o postępie."
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
            await event.reply("Brak informacji o żadnym deployu (deploy-webhook jeszcze nic nie zapisał).")
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
