"""Draft editing: rephrase styles, manual edit, publish, reject."""
import html
from telethon import events

import config as root_config
from core.banners import apply_banner_from_llm
from . import config
from .prompts import (
    SYSTEM_PROMPT, ALERT_VARIANT_SYSTEM, REPHRASE_INSTRUCTIONS, REPHRASE_LABELS,
    SHORTEN_INSTRUCTIONS, SHORTEN_LABELS, STYLE_NAMES, MANUAL_EDIT_INSTRUCTION,
)
from .buttons import make_url_adjust_buttons, make_shorten_buttons, make_tg_published_buttons
from .format import fit_telegram_text
from .publish import send_preview, publish_to_channel, show_loading, restore_phase1_menu, handle_phase1_menu, notify_reviewers
from core.claude import ask_claude, edit_claude
from core import shared_facts
from core.state import pending_posts, track_post, save_state

# Rephrase + percentage-shorten share the same regenerate flow.
ADJUST_INSTRUCTIONS = {**REPHRASE_INSTRUCTIONS, **SHORTEN_INSTRUCTIONS}
ADJUST_LABELS = {**REPHRASE_LABELS, **SHORTEN_LABELS}


def _system_for(post):
    """Edycje wariantów Krótki/Długi alert zachowują ich styl i hook (ALERT_VARIANT_SYSTEM);
    domyślny post (url_draft) zostaje przy SYSTEM_PROMPT."""
    variant = (post.get("edit_chain") or ["url_draft"])[0]
    return ALERT_VARIANT_SYSTEM if variant in ("short_alert", "long_alert") else SYSTEM_PROMPT


def register_handlers(bot):
    @bot.on(events.CallbackQuery)
    async def on_button(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return

        msg_id = event.message_id
        data = event.data.decode()
        print(f"[CALLBACK][edit] sender={event.sender_id} msg_id={msg_id} data={data}")

        post = pending_posts.get(msg_id)

        if data == "phase1_menu":
            await handle_phase1_menu(bot, event, msg_id)
            return

        if not post or post.get("platform") != "url_article":
            return

        if data == "pub_yes":
            await event.answer("Publikuję...")
            await show_loading(event, "Publikuję...")
            print("[PUBLISH] Publikuję na kanale broadcast...")
            try:
                await publish_to_channel(
                    bot, post["text"], image=post.get("image") or root_config.ALERT_IMAGE,
                )
            except Exception as e:
                print(f"[PUBLISH] Błąd: {e}")
                await event.answer(f"Nie udało się opublikować: {e}", alert=True)
                # przywróć przyciski, żeby można było poprawić/ponowić
                try:
                    await (await event.get_message()).edit(buttons=make_url_adjust_buttons())
                except Exception:
                    pass
                return
            original_msg = await event.get_message()
            await original_msg.edit(
                original_msg.text + "\n\n✅ OPUBLIKOWANO",
                buttons=make_tg_published_buttons(),
            )
            post["platform"] = "published"
            shared_facts.merge(
                post.get("phase1_msg_id", msg_id),
                original_text=post.get("original_text", ""),
            )
            await restore_phase1_menu(bot, post)
            save_state()
            return

        if data == "pub_no":
            pending_posts.pop(msg_id, None)
            await event.answer("Odrzucono")
            try:
                await event.delete()
            except Exception:
                pass
            return

        if data == "pub_edit":
            await event.answer("Edycja...")
            await bot.send_message(
                config.INTERNAL_CHAT_ID,
                "Odpowiedz na tę wiadomość nowym tekstem. Zacznij od ! aby podmienić "
                "dosłownie, albo napisz instrukcję do przerobienia:",
                reply_to=msg_id,
            )
            return

        # ── Shorten submenu (toggle buttons in place, no regen) ──
        if data == "shorten_menu":
            await event.answer("O ile skrócić?")
            await (await event.get_message()).edit(buttons=make_shorten_buttons())
            return

        if data == "shorten_back":
            await event.answer("Powrót")
            await (await event.get_message()).edit(buttons=make_url_adjust_buttons())
            return

        if data in ADJUST_INSTRUCTIONS:
            label = ADJUST_LABELS[data]
            await event.answer(f"Przerabiam ({label})...")
            await show_loading(event, f"{label}...")
            print(f"[{label}] Przerabiam post...")

            chain = post.get("edit_chain", [])
            style_context = ""
            if chain:
                applied = [STYLE_NAMES.get(s, s) for s in chain]
                style_context = (
                    f"WAŻNE: Dotychczas zastosowane style: {', '.join(applied)}. "
                    "ZACHOWAJ charakter poprzednich edycji, tylko zastosuj nowe polecenie.\n\n"
                )

            # Operujemy na AKTUALNYM drafcie (nie na surowym artykule) — inaczej model
            # dostaje dwa teksty i potrafi opisać co zrobi zamiast zwrócić gotowy post.
            instruction = style_context + ADJUST_INSTRUCTIONS[data]
            rewritten_raw = await ask_claude(post["text"], post["source"], instruction,
                                         system_prompt=_system_for(post))
            if rewritten_raw.startswith("Błąd Claude"):
                await event.answer("Błąd modelu. Spróbuj ponownie później.", alert=True)
                await notify_reviewers(
                    bot,
                    html.escape(f"⚠️ Błąd Claude przy edycji: {rewritten_raw}\nŹródło: {post.get('source', '')}"),
                )
                return
            rewritten, banner = apply_banner_from_llm(
                rewritten_raw, fallback=post.get("image") or root_config.ALERT_IMAGE,
            )
            rewritten = fit_telegram_text(rewritten)

            anchor = post.get("phase1_msg_id")
            sent = await send_preview(bot, rewritten, make_url_adjust_buttons(), reply_to=anchor)

            post["text"] = rewritten
            post["image"] = banner
            post.setdefault("edit_chain", []).append(data)
            post["phase"] = "adjust"
            pending_posts.pop(msg_id, None)
            pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)

            try:
                await (await event.get_message()).delete()
            except Exception:
                pass
            return

    # ── Manual text edit via reply ──
    @bot.on(events.NewMessage(func=lambda e: (
        e.is_reply and getattr(e, "chat_id", None) == config.INTERNAL_CHAT_ID
    )))
    async def on_edit_reply(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return

        reply_msg = await event.get_reply_message()
        original_msg_id = reply_msg.reply_to_msg_id if reply_msg.reply_to_msg_id else reply_msg.id

        post = pending_posts.get(original_msg_id)
        if not post or post.get("platform") != "url_article":
            return

        text = event.text.strip()
        if text.startswith("!"):
            post["text"] = text[1:].strip()
            await event.reply("Tekst zaktualizowany.")
        else:
            await event.reply("Przerabiam...")
            new_text_raw = await edit_claude(
                post["text"],
                MANUAL_EDIT_INSTRUCTION(text),
                source_facts=post.get("original_text", ""),
                source=post.get("source", ""),
                system_prompt=_system_for(post),
            )
            if new_text_raw.startswith("Błąd Claude"):
                await event.reply("Błąd modelu. Spróbuj ponownie później.")
                await notify_reviewers(
                    bot,
                    html.escape(f"⚠️ Błąd Claude przy ręcznej edycji: {new_text_raw}\nŹródło: {post.get('source', '')}"),
                )
                return
            new_text, banner = apply_banner_from_llm(
                new_text_raw, fallback=post.get("image") or root_config.ALERT_IMAGE,
            )
            post["text"] = fit_telegram_text(new_text)
            post["image"] = banner

        anchor = post.get("phase1_msg_id")
        sent = await send_preview(bot, post["text"], make_url_adjust_buttons(), reply_to=anchor)
        pending_posts.pop(original_msg_id, None)
        pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
