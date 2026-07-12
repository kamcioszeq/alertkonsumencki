"""/help i /status — informacyjne komendy bota (bez efektów ubocznych)."""
import time
from datetime import datetime, timedelta

from telethon import events

from . import config
from core.state import pending_adoption, pending_posts
from core.queue import pending_files

_START_TIME = time.time()

HELP_TEXT = (
    "📖 <b>Dostępne komendy</b>\n\n"
    "<b>Ingest</b>\n"
    "• Wklej link lub tekst wprost na czat — bot zaproponuje wygenerowanie posta\n"
    "• <code>/new &lt;treść lub URL&gt;</code> — to samo, jawną komendą\n"
    "• <code>/test</code> — wygeneruj przykładowy alert testowy\n\n"
    "<b>Statystyki</b>\n"
    "• <code>/stats</code> — podsumowania GIS (miesiąc/rok → rodzaj → post)\n\n"
    "<b>Promocja</b>\n"
    "• <code>/promocja</code> — krótki tekst promocyjny z przyciskiem 📋 Kopiuj (na grupy)\n\n"
    "<b>Deploy</b>\n"
    "• <code>/redeploy</code> — git pull + build + restart\n"
    "• <code>/restart</code>, <code>/rebuild</code> — to samo (pełny rebuild)\n"
    "• <code>/check</code> — status ostatniego deployu\n\n"
    "<b>Info</b>\n"
    "• <code>/status</code> — stan bota (uptime, kolejki)\n"
    "• <code>/help</code> — ta wiadomość"
)


def _format_uptime(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    days, rem = td.days, td.seconds
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}min")
    return " ".join(parts)


def register_status_commands(bot):
    @bot.on(events.NewMessage(pattern=r"^/help$"))
    async def on_help(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        await event.reply(HELP_TEXT, parse_mode="html")

    @bot.on(events.NewMessage(pattern=r"^/status$"))
    async def on_status(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return

        uptime = _format_uptime(time.time() - _START_TIME)
        started_at = datetime.fromtimestamp(_START_TIME).strftime("%Y-%m-%d %H:%M:%S")
        adoption_count = len(pending_adoption)
        active_posts = sum(
            1 for p in pending_posts.values()
            if p.get("platform") not in ("published", "fb_published")
        )
        queue_backlog = len(pending_files())

        await event.reply(
            "🟢 <b>Status bota</b>\n\n"
            f"Działa od: {started_at} ({uptime})\n"
            f"📥 Oczekujące na wygenerowanie: {adoption_count}\n"
            f"📝 Aktywne drafty: {active_posts}\n"
            f"📬 Kolejka od crawlera: {queue_backlog}\n\n"
            "Status ostatniego deployu: /check",
            parse_mode="html",
        )
