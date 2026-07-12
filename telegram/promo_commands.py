"""/promocja — generuje angażujący post promocyjny na FB (pytanie + tekst do skopiowania)."""
import html
import os

from telethon import events

import config as root_config
from core.claude import ask_claude
from core.state import pending_posts, track_post
from facebook.publish import publish_to_facebook
from promo.prompts import (
    PROMO_MODEL, PROMO_SYSTEM_PROMPT,
    PROMO_WITH_STATS_INSTRUCTION, PROMO_GENERIC_INSTRUCTION, PROMO_REGEN_HINT,
)
from stats.gis_archive import fetch_period
from stats.prompts import build_stats_blob, period_label, strip_title_prefix
from . import config
from .buttons import make_promo_buttons, make_promo_published_buttons
from .publish import show_loading, notify_reviewers


def _format_preview(fb_text: str) -> str:
    """Podgląd w Telegramie: gotowy tekst do skopiowania + krótka wskazówka."""
    return (
        "📣 <b>Post promocyjny na Facebooka</b>\n"
        "Skopiuj tekst poniżej i wklej na FB 👇\n\n"
        f"<pre>{html.escape(fb_text.strip())}</pre>\n\n"
        "💡 <i>Wskazówka: dodaj grafikę QR (assets/qr.png) — lepszy zasięg. "
        "Odpowiadaj na komentarze w pierwszej godzinie, żeby algorytm podbił post.</i>"
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
    """Generuj tekst posta promocyjnego. Zwraca (ok, text_or_error)."""
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


async def _send_promo_preview(bot, fb_text: str, *, regen: bool = False):
    """Wyślij podgląd i zapisz w pending_posts."""
    preview = _format_preview(fb_text)
    sent = await bot.send_message(
        config.INTERNAL_CHAT_ID, preview,
        buttons=make_promo_buttons(),
        parse_mode="html",
    )
    post = {
        "text": fb_text,
        "platform": "promo_post",
        "image": root_config.PROMO_IMAGE,
        "source": "promocja",
    }
    pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
    print(f"[PROMO] Wygenerowano post promocyjny → msg_id={sent.id} regen={regen}")
    return sent


def register_promo_commands(bot):
    @bot.on(events.NewMessage(pattern=r"^/promocja$"))
    async def on_promocja(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return

        await event.reply("✨ Generuję post promocyjny na FB...")
        ok, result = await _generate_promo()
        if not ok:
            await notify_reviewers(
                bot, html.escape(f"⚠️ Błąd Claude przy /promocja: {result}"),
            )
            await event.reply("Błąd generowania. Spróbuj ponownie później.")
            return
        await _send_promo_preview(bot, result)

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
            await event.answer("Generuję inne pytanie...")
            await show_loading(event, "Inne pytanie...")
            ok, result = await _generate_promo(regen=True)
            if not ok:
                await event.answer("Błąd modelu", alert=True)
                await notify_reviewers(
                    bot, html.escape(f"⚠️ Błąd Claude przy regeneracji promocji: {result}"),
                )
                return
            preview = _format_preview(result)
            await (await event.get_message()).edit(
                preview, buttons=make_promo_buttons(), parse_mode="html",
            )
            post["text"] = result
            return

        if data == "promo_pub":
            post = pending_posts.get(msg_id)
            if not post or post.get("platform") != "promo_post":
                return
            await event.answer("Publikuję na FB...")
            await show_loading(event, "Publikuję na FB...")
            promo_img = post.get("image") if os.path.exists(post.get("image", "")) else None
            ok, result = await publish_to_facebook(post["text"], image_path=promo_img)
            original_msg = await event.get_message()
            if not ok:
                print(f"[PROMO] Błąd publikacji FB: {result}")
                await event.answer(f"FB: {result}", alert=True)
                try:
                    await original_msg.edit(buttons=make_promo_buttons())
                except Exception:
                    pass
                return
            print(f"[PROMO] Opublikowano na FB: {result}")
            post["fb_post_id"] = result
            await original_msg.edit(
                original_msg.text + "\n\n✅ OPUBLIKOWANO NA FB",
                buttons=make_promo_published_buttons(),
                parse_mode="html",
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
