"""/stats: wybór okresu (Miesiąc/Rok) → rodzaj statystyki → marketingowy post.

Wygenerowany post ląduje w pending_posts jako zwykły draft platform="url_article" —
dzięki temu od razu działa na nim cały istniejący flow: OK/Dostosuj/Publikuj/FB,
w tym formalny/nieformalny (patrz telegram/handlers.py _system_for dla STATS_SYSTEM_PROMPT).
"""
import html

from telethon import events

import config as root_config
from core.banners import apply_banner_from_llm
from core.claude import ask_claude
from core.state import pending_posts, track_post
from . import config
from .buttons import make_stats_period_buttons, make_stats_type_buttons, make_url_confirm_buttons
from .format import fit_telegram_text
from .publish import send_preview, show_loading, notify_reviewers
from stats.gis_archive import fetch_period
from stats.prompts import STATS_SYSTEM_PROMPT, STATS_TYPE_LABELS, build_records_blob, period_label, instruction_for

PERIOD_LABELS = {"month": "Miesiąc", "year": "Rok"}


def register_stats_handlers(bot):
    @bot.on(events.NewMessage(pattern=r"^/stats$"))
    async def on_stats(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        await event.reply("📊 Statystyki ostrzeżeń GIS — wybierz okres:", buttons=make_stats_period_buttons())

    @bot.on(events.CallbackQuery)
    async def on_stats_button(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        data = event.data.decode()

        if data == "stats_back":
            await event.answer()
            await (await event.get_message()).edit(
                "📊 Statystyki ostrzeżeń GIS — wybierz okres:", buttons=make_stats_period_buttons(),
            )
            return

        if data.startswith("stats_period:"):
            period = data.split(":", 1)[1]
            await event.answer()
            await (await event.get_message()).edit(
                f"📊 Okres: {PERIOD_LABELS[period]} — wybierz rodzaj statystyk:",
                buttons=make_stats_type_buttons(period),
            )
            return

        if data.startswith("stats_type:"):
            _, stat_type, period = data.split(":")
            await event.answer("Zbieram dane...")
            await show_loading(event, "Zbieram statystyki GIS...")

            try:
                records = await fetch_period(period)
            except Exception as e:
                print(f"[STATS] Błąd pobierania listingu GIS: {e}")
                await notify_reviewers(bot, html.escape(f"⚠️ Błąd pobierania statystyk GIS ({period}): {e}"))
                await (await event.get_message()).edit(
                    "Nie udało się pobrać danych GIS. Spróbuj ponownie później.",
                    buttons=make_stats_period_buttons(),
                )
                return

            if not records:
                await (await event.get_message()).edit(
                    f"Brak ostrzeżeń GIS w tym okresie ({PERIOD_LABELS[period]}).",
                    buttons=make_stats_period_buttons(),
                )
                return

            label = period_label(period)
            blob = build_records_blob(records)
            instruction = instruction_for(stat_type, label, len(records))
            source = f"Statystyki GIS — {label}"

            draft_raw = await ask_claude(blob, source, instruction, system_prompt=STATS_SYSTEM_PROMPT)
            if draft_raw.startswith("Błąd Claude"):
                await event.answer("Błąd generowania statystyk", alert=True)
                await notify_reviewers(bot, html.escape(f"⚠️ Błąd Claude przy statystykach: {draft_raw}"))
                return

            draft, banner = apply_banner_from_llm(draft_raw, fallback=root_config.ALERT_IMAGE)
            draft = fit_telegram_text(draft)

            post = {
                "text": draft,
                "original_text": blob,
                "source": source,
                "platform": "url_article",
                "phase": "confirm",
                "has_url": False,
                "article_url": "",
                "user_instruction": "",
                "title": f"{STATS_TYPE_LABELS[stat_type]} — {label}",
                "image": banner,
                "edit_chain": [f"stats_{stat_type}"],
            }
            sent = await send_preview(bot, draft, make_url_confirm_buttons())
            pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
            try:
                await event.delete()
            except Exception:
                pass
            print(f"[STATS] {stat_type}/{period}: {len(records)} ostrzeżeń → msg_id={sent.id}")
            return
