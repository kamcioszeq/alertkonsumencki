"""/stats: wybór okresu (Miesiąc/Rok) → rodzaj statystyki → marketingowy post →
udostępnij (TG ze stopką / FB bez stopki, z automatycznym PROMO w komentarzu).

Posty statystyczne żyją w pending_posts pod własnym platform="stats_post" — CELOWO
odizolowane od platform="url_article"/"fb_draft", bo generyczny flow FB (facebook/handlers.py
fb_start) narzuca sztywną strukturę alertu (HOOK/GIS/ZAGROŻENIE/CTA), zupełnie nietrafioną
dla podsumowania statystycznego. Dlatego /stats ma własne przyciski stylu (Ostro/Łagodniej/
Retry/Gramatyka) i własne udostępnianie zamiast reużywania tamtego flow.

PROMO po publikacji na FB działa "za darmo": facebook/handlers.py -> fb_promo tylko
sprawdza obecność post["fb_post_id"] w pending_posts, bez patrzenia na platform.

Odpowiedz na wygenerowany post (dowolny tekst = instrukcja przeróbki, "!" = dosłowna
podmiana) pozwala zasugerować drobną zmianę bez regenerowania całości od danych źródłowych.
Każda przeróbka (przycisk stylu lub Odpowiedz) odkłada poprzednią wersję na stos historii —
Cofnij przywraca ją.
"""
import html

from telethon import events

import config as root_config
from core.banners import apply_banner_from_llm
from core.claude import ask_claude
from core.state import pending_posts, track_post
from facebook.publish import html_to_plain, publish_to_facebook
from . import config
from .buttons import (
    make_stats_period_buttons, make_stats_type_buttons, make_stats_adjust_buttons,
    make_stats_shared_buttons,
)
from .format import fit_telegram_text
from .publish import send_preview, publish_to_channel, show_loading, notify_reviewers
from stats.gis_archive import fetch_period
from stats.prompts import (
    STATS_MODEL, STATS_SYSTEM_PROMPT, STATS_TYPE_LABELS, STATS_ADJUST_LABELS,
    STATS_ADJUST_INSTRUCTIONS, build_stats_blob, period_label, instruction_for,
    custom_instruction, strip_title_prefix, strip_footer,
)

PERIOD_LABELS = {"month": "Miesiąc", "year": "Rok"}

# msg_id (wiadomości z prośbą "napisz czego ma dotyczyć") -> period, dopóki użytkownik
# nie odpowie. Ulotny, w pamięci — nie trzeba go przeżywać restartu bota.
_pending_custom: dict[int, str] = {}


def _chunk_lines(lines, max_chars=3500):
    chunks, current = [], ""
    for line in lines:
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _chain_context(post):
    chain = post.get("edit_chain", [])
    if not chain:
        return ""
    applied = [STATS_TYPE_LABELS.get(chain[0], chain[0])] + [STATS_ADJUST_LABELS.get(s, s) for s in chain[1:]]
    return (
        f"WAŻNE: Dotychczas zastosowane style: {', '.join(applied)}. "
        "ZACHOWAJ charakter poprzednich edycji, tylko zastosuj nowe polecenie.\n\n"
    )


def _snapshot(post):
    """Zrzut aktualnej wersji na stos historii — do przywrócenia przez Cofnij."""
    post.setdefault("history", []).append({
        "text": post["text"],
        "image": post.get("image"),
        "edit_chain": list(post.get("edit_chain", [])),
    })


async def _regen_and_resend(bot, post, msg_id, instruction, *, chain_key=None):
    """Przerabia post["text"] wg `instruction`, wysyła nowy podgląd, aktualizuje pending_posts.
    Zwraca (ok, sent_msg_or_error)."""
    rewritten_raw = await ask_claude(
        post["text"], post["source"], instruction, system_prompt=STATS_SYSTEM_PROMPT, model=STATS_MODEL,
    )
    if rewritten_raw.startswith("Błąd Claude"):
        return False, rewritten_raw
    rewritten, banner = apply_banner_from_llm(rewritten_raw, fallback=post.get("image"))
    rewritten = fit_telegram_text(rewritten)

    _snapshot(post)
    post["text"] = rewritten
    post["image"] = banner
    if chain_key:
        post.setdefault("edit_chain", []).append(chain_key)
    sent = await send_preview(bot, rewritten, make_stats_adjust_buttons())
    pending_posts.pop(msg_id, None)
    pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
    return True, sent


async def _generate_stats_draft(bot, *, period, build_instruction, title, chain_key=None, reply_to=None):
    """Ściąga dane za `period`, generuje draft wg instrukcji zwróconej przez
    `build_instruction(records, label)`, wysyła podgląd. Wspólne dla ścieżki z gotowym
    typem statystyk i ścieżki Custom (własna instrukcja użytkownika).
    Zwraca (ok, sent_msg_or_error_str)."""
    try:
        records = await fetch_period(period)
    except Exception as e:
        print(f"[STATS] Błąd pobierania listingu GIS: {e}")
        return False, f"Nie udało się pobrać danych GIS: {e}"

    if not records:
        return False, f"Brak ostrzeżeń GIS w tym okresie ({PERIOD_LABELS[period]})."

    label = period_label(period)
    blob = build_stats_blob(records)
    source = f"Statystyki GIS — {label}"
    instruction = build_instruction(records, label)

    draft_raw = await ask_claude(
        blob, source, instruction, system_prompt=STATS_SYSTEM_PROMPT, model=STATS_MODEL,
    )
    if draft_raw.startswith("Błąd Claude"):
        return False, draft_raw

    draft, banner = apply_banner_from_llm(draft_raw, fallback=root_config.ALERT_IMAGE)
    draft = fit_telegram_text(draft)

    post = {
        "text": draft,
        "original_text": blob,
        "source": source,
        "platform": "stats_post",
        "has_url": False,
        "title": f"{title} — {label}",
        "image": banner,
        "edit_chain": [chain_key] if chain_key else [],
        "history": [],
    }
    sent = await send_preview(bot, draft, make_stats_adjust_buttons(), reply_to=reply_to)
    pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
    print(f"[STATS] {chain_key or 'custom'}/{period}: {len(records)} ostrzeżeń → msg_id={sent.id}")
    return True, sent


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
        msg_id = event.message_id

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

        if data.startswith("stats_custom:"):
            period = data.split(":", 1)[1]
            await event.answer()
            msg = await event.get_message()
            await msg.edit(
                f"✍️ Napisz, czego ma dotyczyć podsumowanie ({PERIOD_LABELS[period]}) — "
                "np. 'skup się na alergenach' albo 'porównaj do zeszłego miesiąca'. "
                "Odpowiedz na tę wiadomość:",
                buttons=None,
            )
            _pending_custom[msg_id] = period
            return

        if data.startswith("stats_type:"):
            _, stat_type, period = data.split(":")
            await event.answer("Zbieram dane...")
            await show_loading(event, "Zbieram statystyki GIS...")

            if stat_type == "titles":
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
                lines = [
                    f"• {r['date']}: {strip_title_prefix(r['title'])}"
                    for r in sorted(records, key=lambda r: r["date"], reverse=True)
                ]
                header = f"📋 <b>Lista tytułów — {label}</b> ({len(records)})"
                for i, chunk in enumerate(_chunk_lines(lines)):
                    text = f"{header}\n\n{chunk}" if i == 0 else chunk
                    await bot.send_message(config.INTERNAL_CHAT_ID, text, parse_mode="html")
                try:
                    await event.delete()
                except Exception:
                    pass
                print(f"[STATS] titles/{period}: {len(records)} ostrzeżeń wylistowanych")
                return

            ok, result = await _generate_stats_draft(
                bot, period=period,
                build_instruction=lambda records, label, st=stat_type: instruction_for(st, label, len(records)),
                title=STATS_TYPE_LABELS[stat_type],
                chain_key=f"stats_{stat_type}",
            )
            if not ok:
                if result.startswith("Błąd Claude"):
                    await event.answer("Błąd generowania statystyk", alert=True)
                    await notify_reviewers(bot, html.escape(f"⚠️ Błąd Claude przy statystykach: {result}"))
                else:
                    await (await event.get_message()).edit(result, buttons=make_stats_period_buttons())
                return
            try:
                await event.delete()
            except Exception:
                pass
            return

        # ── Poniżej: akcje na już wygenerowanym poście statystycznym ──
        post = pending_posts.get(msg_id)
        if not post or post.get("platform") != "stats_post":
            return

        if data == "stats_reject":
            pending_posts.pop(msg_id, None)
            await event.answer("Odrzucono")
            try:
                await event.delete()
            except Exception:
                pass
            return

        if data == "stats_edit":
            await event.answer("Odpowiedz na wiadomość...")
            await bot.send_message(
                config.INTERNAL_CHAT_ID,
                "Odpowiedz na tę wiadomość — napisz co zmienić w statystykach, a prompt "
                "się dostosuje. Zacznij od ! aby podmienić tekst dosłownie:",
                reply_to=msg_id,
            )
            return

        if data == "stats_undo":
            history = post.get("history") or []
            if not history:
                await event.answer("Brak wcześniejszej wersji do cofnięcia", alert=True)
                return
            prev = history.pop()
            post["text"] = prev["text"]
            post["image"] = prev["image"]
            post["edit_chain"] = prev["edit_chain"]
            sent = await send_preview(bot, post["text"], make_stats_adjust_buttons())
            pending_posts.pop(msg_id, None)
            pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
            try:
                await event.delete()
            except Exception:
                pass
            await event.answer("Cofnięto")
            return

        if data.startswith("stats_adjust:"):
            key = data.split(":", 1)[1]
            style_label = STATS_ADJUST_LABELS[key]
            await event.answer(f"Przerabiam ({style_label})...")
            await show_loading(event, f"{style_label}...")
            print(f"[STATS][{style_label}] Przerabiam post...")

            instruction = _chain_context(post) + STATS_ADJUST_INSTRUCTIONS[key]
            ok, result = await _regen_and_resend(bot, post, msg_id, instruction, chain_key=key)
            if not ok:
                await event.answer("Błąd modelu. Spróbuj ponownie później.", alert=True)
                await notify_reviewers(bot, html.escape(f"⚠️ Błąd Claude przy edycji statystyk: {result}"))
                return
            try:
                await (await event.get_message()).delete()
            except Exception:
                pass
            return

        if data == "stats_share:tg":
            await event.answer("Publikuję na TG...")
            await show_loading(event, "Publikuję na TG...")
            print("[STATS] Publikuję statystyki na TG...")
            try:
                await publish_to_channel(bot, post["text"], image=post.get("image") or root_config.ALERT_IMAGE)
            except Exception as e:
                print(f"[STATS] Błąd publikacji TG: {e}")
                await event.answer(f"Nie udało się opublikować: {e}", alert=True)
                try:
                    await (await event.get_message()).edit(buttons=make_stats_adjust_buttons())
                except Exception:
                    pass
                return
            post["tg_published"] = True
            original_msg = await event.get_message()
            await original_msg.edit(
                original_msg.text + "\n\n✅ OPUBLIKOWANO NA TG",
                buttons=make_stats_shared_buttons(tg_done=True, fb_done=bool(post.get("fb_post_id"))),
            )
            return

        if data == "stats_share:fb":
            await event.answer("Publikuję na FB...")
            await show_loading(event, "Publikuję na FB...")
            print("[STATS] Publikuję statystyki na FB (bez stopki)...")
            fb_text = html_to_plain(strip_footer(post["text"]))
            ok, result = await publish_to_facebook(
                fb_text, image_path=post.get("image") or root_config.ALERT_IMAGE,
            )
            original_msg = await event.get_message()
            if not ok:
                print(f"[STATS] Błąd publikacji FB: {result}")
                await event.answer(f"FB: {result}", alert=True)
                try:
                    await original_msg.edit(buttons=make_stats_adjust_buttons())
                except Exception:
                    pass
                return
            print(f"[STATS] Opublikowano na FB: {result}")
            post["fb_post_id"] = result
            await original_msg.edit(
                original_msg.text + "\n\n✅ OPUBLIKOWANO NA FB",
                buttons=make_stats_shared_buttons(tg_done=bool(post.get("tg_published")), fb_done=True),
            )
            return

    # ── Sugestia zmiany przez reply (bez regenerowania całości od danych źródłowych) ──
    @bot.on(events.NewMessage(func=lambda e: (
        e.is_reply and getattr(e, "chat_id", None) == config.INTERNAL_CHAT_ID
    )))
    async def on_stats_edit_reply(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return

        reply_msg = await event.get_reply_message()

        # Odpowiedź na "✍️ Napisz, czego ma dotyczyć..." z przycisku 🎨 Custom.
        if reply_msg.id in _pending_custom:
            period = _pending_custom.pop(reply_msg.id)
            user_text = event.text.strip()
            await event.reply("Generuję...")
            ok, result = await _generate_stats_draft(
                bot, period=period,
                build_instruction=lambda records, label, t=user_text: custom_instruction(t),
                title=STATS_TYPE_LABELS["custom"],
                chain_key="stats_custom",
                reply_to=reply_msg.id,
            )
            if not ok:
                if result.startswith("Błąd Claude"):
                    await notify_reviewers(bot, html.escape(f"⚠️ Błąd Claude przy custom statystykach: {result}"))
                    await event.reply("Błąd modelu. Spróbuj ponownie później.")
                else:
                    await event.reply(result)
            return

        original_msg_id = reply_msg.reply_to_msg_id if reply_msg.reply_to_msg_id else reply_msg.id

        post = pending_posts.get(original_msg_id)
        if not post or post.get("platform") != "stats_post":
            return

        text = event.text.strip()
        if text.startswith("!"):
            _snapshot(post)
            post["text"] = fit_telegram_text(text[1:].strip())
            sent = await send_preview(bot, post["text"], make_stats_adjust_buttons())
            pending_posts.pop(original_msg_id, None)
            pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
            return

        await event.reply("Przerabiam...")
        instruction = (
            f"Zastosuj do powyższego podsumowania statystycznego polecenie: {text}. "
            "Zwróć wyłącznie gotowy post — nie generuj całości od nowa, zmień tylko to, "
            "o co proszono."
        )
        ok, result = await _regen_and_resend(bot, post, original_msg_id, instruction)
        if not ok:
            await event.reply("Błąd modelu. Spróbuj ponownie później.")
            await notify_reviewers(bot, html.escape(f"⚠️ Błąd Claude przy ręcznej edycji statystyk: {result}"))
            return
