"""/promocja — krótki tekst promocyjny z przyciskiem Kopiuj (wklejka na grupy FB)."""
import html

from telethon import events

from core.claude import ask_claude
from core.state import pending_posts, track_post
from promo.prompts import (
    PROMO_MODEL, PROMO_SYSTEM_PROMPT,
    PROMO_WITH_STATS_INSTRUCTION, PROMO_GENERIC_INSTRUCTION, PROMO_REGEN_HINT,
)
from stats.gis_archive import fetch_period
from stats.prompts import build_stats_blob, period_label, strip_title_prefix
from . import config
from .buttons import make_promo_buttons, make_promo_buttons_fallback
from .publish import show_loading, notify_reviewers


def _format_preview(promo_text: str) -> str:
    """Podgląd w Telegramie: krótki tekst + instrukcja kopiowania."""
    return (
        "📋 <b>Tekst promocyjny</b> (krótki, pod grupy)\n"
        "Kliknij <b>📋 Kopiuj</b> i wklej gdzie chcesz 👇\n\n"
        f"<pre>{html.escape(promo_text.strip())}</pre>"
    )


async def _build_source_blob() -> tuple[str, str]:
    """Zbierz kontekst z GIS (miesiąc) albo zwróć pusty — do promptu."""
    try:
        records = await fetch_period("month")
    except Exception as e:
        print(f"[PROMO] Nie udało się pobrać GIS: {e}")
        records = []

    if records:
        label = period_label("month")
        titles = [
            strip_title_prefix(r["title"])
            for r in sorted(records, key=lambda x: x["date"], reverse=True)[:5]
        ]
        summary = (
            f"Okres: {label}\n"
            f"Liczba ostrzeżeń GIS: {len(records)}\n"
            f"Przykładowe tytuły (najnowsze):\n"
            + "\n".join(f"• {t}" for t in titles)
        )
        blob = build_stats_blob(records)
        return summary, blob

    return "Brak świeżych danych GIS — pisz ogólnie o bezpieczeństwie żywności.", ""


async def _generate_promo(*, regen: bool = False) -> tuple[bool, str]:
    """Generuj tekst promocyjny. Zwraca (ok, text_or_error)."""
    summary, blob = await _build_source_blob()
    instruction = PROMO_WITH_STATS_INSTRUCTION if blob else PROMO_GENERIC_INSTRUCTION
    if regen:
        instruction += f"\n\n{PROMO_REGEN_HINT}"

    source_text = f"{summary}\n\n{blob}".strip() if blob else summary
    source = f"Promocja Alert Konsumencki — {period_label('month')}"

    raw = await ask_claude(
        source_text, source, instruction,
        system_prompt=PROMO_SYSTEM_PROMPT, model=PROMO_MODEL,
    )
    if raw.startswith("Błąd Claude"):
        return False, raw
    return True, raw.strip()


async def _send_promo_preview(bot, promo_text: str):
    """Wyślij podgląd z przyciskiem Kopiuj i zapisz w pending_posts."""
    preview = _format_preview(promo_text)
    try:
        sent = await bot.send_message(
            config.INTERNAL_CHAT_ID, preview,
            buttons=make_promo_buttons(promo_text),
            parse_mode="html",
        )
    except Exception as e:
        print(f"[PROMO] Błąd wysyłki z przyciskiem Kopiuj ({type(e).__name__}: {e}) — fallback")
        preview += "\n\n<i>Przycisk Kopiuj niedostępny — skopiuj tekst z bloku powyżej.</i>"
        sent = await bot.send_message(
            config.INTERNAL_CHAT_ID, preview,
            buttons=make_promo_buttons_fallback(),
            parse_mode="html",
        )
    post = {
        "text": promo_text,
        "platform": "promo_post",
        "source": "promocja",
    }
    pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
    print(f"[PROMO] Wygenerowano tekst promocyjny → msg_id={sent.id}")
    return sent


def register_promo_commands(bot):
    @bot.on(events.NewMessage(pattern=r"^/promocja(?:@\w+)?$"))
    async def on_promocja(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return

        status = await event.reply("✨ Generuję krótki tekst promocyjny...")
        ok, result = await _generate_promo()
        if not ok:
            await notify_reviewers(
                bot, html.escape(f"⚠️ Błąd Claude przy /promocja: {result}"),
            )
            await status.edit("Błąd generowania. Spróbuj ponownie później.")
            return
        try:
            await _send_promo_preview(bot, result)
        except Exception as e:
            print(f"[PROMO] Krytyczny błąd podglądu: {type(e).__name__}: {e}")
            await notify_reviewers(
                bot, html.escape(f"⚠️ Błąd /promocja przy wysyłce podglądu: {e}"),
            )
            await status.edit(f"Nie udało się wysłać podglądu: {e}")
            return
        try:
            await status.delete()
        except Exception:
            pass

    @bot.on(events.CallbackQuery)
    async def on_promo_button(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return

        data = event.data.decode()
        msg_id = event.message_id

        if data == "promo_regen":
            post = pending_posts.get(msg_id)
            if not post or post.get("platform") != "promo_post":
                return
            await event.answer("Generuję inną wersję...")
            await show_loading(event, "Inna wersja...")
            ok, result = await _generate_promo(regen=True)
            if not ok:
                await event.answer("Błąd modelu", alert=True)
                await notify_reviewers(
                    bot, html.escape(f"⚠️ Błąd Claude przy regeneracji promocji: {result}"),
                )
                return
            preview = _format_preview(result)
            try:
                await (await event.get_message()).edit(
                    preview,
                    buttons=make_promo_buttons(result),
                    parse_mode="html",
                )
            except Exception as e:
                print(f"[PROMO] Błąd edycji z Kopiuj ({type(e).__name__}: {e}) — fallback")
                preview += "\n\n<i>Przycisk Kopiuj niedostępny — skopiuj tekst z bloku powyżej.</i>"
                await (await event.get_message()).edit(
                    preview,
                    buttons=make_promo_buttons_fallback(),
                    parse_mode="html",
                )
            post["text"] = result
            return

        if data == "promo_copy":
            post = pending_posts.get(msg_id)
            if not post or post.get("platform") != "promo_post":
                return
            await event.answer("Tekst poniżej — przytrzymaj i skopiuj")
            await bot.send_message(
                config.INTERNAL_CHAT_ID,
                f"📋 Skopiuj i wklej:\n\n{post['text']}",
            )
            return

        if data == "promo_reject":
            post = pending_posts.get(msg_id)
            if not post or post.get("platform") != "promo_post":
                return
            pending_posts.pop(msg_id, None)
            await event.answer("Odrzucono")
            try:
                await event.delete()
            except Exception:
                pass
            return
