"""Telegram flow: FB draft generation, adjust, edit, publish."""
import os
from typing import Optional

from telethon import events

import config as root_config
from core.banners import apply_banner_from_llm
from core import shared_facts
from core.claude import ask_claude, edit_claude
from core.resolve_artifacts import resolve_artifacts, build_source_text
from core.state import pending_posts, track_post, save_state
from telegram.config import INTERNAL_CHAT_ID, REVIEWER_IDS
from telegram.publish import show_loading, send_preview, restore_phase1_menu, handle_phase1_menu
from telegram.buttons import (
    make_url_confirm_buttons, make_url_publish_buttons, make_url_adjust_buttons,
)
from telegram.prompts import SYSTEM_PROMPT, _build_draft_instruction
from telegram.format import fit_telegram_text
from .buttons import make_fb_adjust_buttons, make_fb_shorten_buttons, make_fb_published_buttons
from .prompts import (
    FB_SYSTEM_PROMPT, FB_COMMENT_SYSTEM_PROMPT,
    FB_GENERATE_INSTRUCTION, FB_GENERATE_FROM_SOURCE, FB_COMMENT_GENERATE_INSTRUCTION,
    FB_PROMO_TEXT, FB_ADJUST_INSTRUCTIONS, FB_ADJUST_LABELS, FB_STYLE_NAMES,
    FB_MANUAL_EDIT_INSTRUCTION,
    fit_fb_text, format_fb_preview,
)
from .publish import publish_to_facebook, comment_on_facebook, html_to_plain


def _alert_image(post: dict) -> Optional[str]:
    for candidate in (post.get("image"), root_config.ALERT_IMAGE):
        if candidate and os.path.exists(candidate):
            return candidate
    return None


def _kapieliska_image() -> str:
    p = root_config.KAPIELISKA_IMAGE
    if p and os.path.exists(p):
        return p
    return root_config.ALERT_IMAGE


def _process_fb_text(raw: str, *, fallback: Optional[str] = None) -> tuple[str, str]:
    text, banner = apply_banner_from_llm(raw, fallback=fallback)
    return fit_fb_text(text), banner


async def _send_fb_preview(bot, text: str, buttons, *, reply_to=None, image: Optional[str] = None):
    """Podgląd FB w TG — ze zdjęciem, jeśli podane (kąpieliska: Wakacje.png)."""
    img = image if (image and os.path.exists(image)) else None
    if not img:
        return await bot.send_message(
            INTERNAL_CHAT_ID,
            text,
            buttons=buttons,
            reply_to=reply_to,
        )
    # Telegram caption max 1024 — dłuższy podgląd = foto + osobna wiadomość z tekstem
    if len(text) <= 1024:
        return await bot.send_file(
            INTERNAL_CHAT_ID, img, caption=text, buttons=buttons, reply_to=reply_to,
        )
    await bot.send_file(INTERNAL_CHAT_ID, img, reply_to=reply_to)
    return await bot.send_message(
        INTERNAL_CHAT_ID, text, buttons=buttons, reply_to=reply_to,
    )


async def _generate_fb_comment(source_text: str, source: str, *, kapieliska: bool = False) -> str:
    if kapieliska:
        from kapieliska.prompts import (
            FB_KAPIELISKA_COMMENT_SYSTEM,
            FB_KAPIELISKA_COMMENT_GENERATE,
        )
        raw = await ask_claude(
            source_text, source or "fb",
            FB_KAPIELISKA_COMMENT_GENERATE,
            system_prompt=FB_KAPIELISKA_COMMENT_SYSTEM,
        )
    else:
        raw = await ask_claude(
            source_text, source or "fb",
            FB_COMMENT_GENERATE_INSTRUCTION,
            system_prompt=FB_COMMENT_SYSTEM_PROMPT,
        )
    return fit_fb_text(raw, max_chars=1000)


async def _regen_fb(bot, post: dict, instruction: str, *, label: str):
    from kapieliska.prompts import (
        is_kapieliska_source,
        FB_KAPIELISKA_SYSTEM_PROMPT,
        kapieliska_generate_instruction,
    )
    kap = (
        is_kapieliska_source(post.get("source", ""), post.get("original_text", ""))
        or post.get("kind") == "kapieliska"
    )
    sys_p = FB_KAPIELISKA_SYSTEM_PROMPT if kap else FB_SYSTEM_PROMPT
    use_instruction = kapieliska_generate_instruction() if kap else instruction
    rewritten = await ask_claude(
        post["text"], post.get("source", "fb"),
        use_instruction,
        system_prompt=sys_p,
    )
    if kap:
        return fit_fb_text(rewritten), _kapieliska_image()
    return _process_fb_text(rewritten, fallback=post.get("image"))


async def _generate_fb_draft(
    bot, *, source_text, source, instruction, anchor,
    image="", tg_text="", original_text="", parent_msg_id=None,
    icon_hint="", comment_text="", kapielisko_id="", lokalizacja="",
):
    """Wygeneruj draft FB (post + komentarz), wyślij podgląd. Zwraca (sent, fb_text)."""
    from kapieliska.prompts import (
        is_kapieliska_source,
        FB_KAPIELISKA_SYSTEM_PROMPT,
        kapieliska_generate_instruction,
    )

    kap = is_kapieliska_source(source or "", original_text or source_text or "")
    sys_p = FB_KAPIELISKA_SYSTEM_PROMPT if kap else FB_SYSTEM_PROMPT
    use_instruction = kapieliska_generate_instruction() if kap else instruction

    full_instruction = use_instruction
    if icon_hint and not kap:
        full_instruction += f"\n\n{icon_hint}"

    fb_text_raw = await ask_claude(
        source_text, source or "telegram", full_instruction, system_prompt=sys_p,
    )
    if fb_text_raw.startswith("Błąd Claude"):
        return None, fb_text_raw

    # Kąpieliska: stały baner Wakacje.png (bez banerów żywności)
    if kap:
        fb_text = fit_fb_text(fb_text_raw)
        banner = _kapieliska_image()
    else:
        fb_text, banner = _process_fb_text(
            fb_text_raw, fallback=image or root_config.ALERT_IMAGE,
        )

    comment_src = original_text or source_text
    fb_comment = comment_text or await _generate_fb_comment(
        comment_src, source or "telegram", kapieliska=kap,
    )
    if fb_comment.startswith("Błąd Claude"):
        return None, fb_comment

    preview = format_fb_preview(fb_text, fb_comment)
    sent = await _send_fb_preview(
        bot, preview, make_fb_adjust_buttons(), reply_to=anchor, image=banner,
    )
    fb_post = {
        "text": fb_text,
        "comment_text": fb_comment,
        "tg_text": tg_text,
        "original_text": original_text or source_text,
        "source": source or "",
        "platform": "fb_draft",
        "phase": "fb_adjust",
        "image": banner,
        "phase1_msg_id": anchor,
        "parent_msg_id": parent_msg_id,
        "edit_chain": ["fb_generated"],
        "kind": "kapieliska" if kap else "",
        "kapielisko_id": kapielisko_id,
        "lokalizacja": lokalizacja,
    }
    pending_posts[sent.id] = track_post(pending_posts, fb_post, sent_id=sent.id)
    shared_facts.merge(anchor, original_text=original_text or source_text,
                       comment_text=fb_comment, source=source or "",
                       lokalizacja=lokalizacja)
    return sent, fb_text


async def generate_fb_from_artifacts(bot, *, artifacts: dict, anchor: int, icon_hint: str = ""):
    """Generuj FB z zebranych artefaktów (Phase1 / opublikowany TG)."""
    source_text = artifacts.get("original_text") or build_source_text(artifacts)
    if not source_text.strip():
        return None, "Brak treści źródłowej"
    return await _generate_fb_draft(
        bot,
        source_text=source_text,
        source=artifacts.get("source", "telegram"),
        instruction=FB_GENERATE_FROM_SOURCE,
        anchor=anchor,
        image=artifacts.get("image", ""),
        original_text=source_text,
        icon_hint=icon_hint,
        comment_text=artifacts.get("comment_text", ""),
        kapielisko_id=artifacts.get("kapielisko_id", ""),
        lokalizacja=artifacts.get("lokalizacja", ""),
    )


async def generate_fb_from_source(bot, *, article_text, source, image, anchor, icon_hint=""):
    """Faza 1: wygeneruj post FB wprost z surowego źródła."""
    return await _generate_fb_draft(
        bot,
        source_text=article_text,
        source=source,
        instruction=FB_GENERATE_FROM_SOURCE,
        anchor=anchor,
        image=image,
        original_text=article_text,
        icon_hint=icon_hint,
    )


async def generate_tg_from_artifacts(bot, *, artifacts: dict, anchor: int, parent_msg_id=None):
    """Generuj draft TG z artefaktów (FB draft / opublikowany FB)."""
    source_text = build_source_text(artifacts)
    if not source_text.strip():
        return None

    instruction = _build_draft_instruction("")
    from core.gen_context import build_icon_hint
    icon_hint = await build_icon_hint(
        anchor, source_text, artifacts.get("source", "fb"), artifacts.get("title", ""),
    )
    instruction += f"\n\n{icon_hint}"

    tg_raw = await ask_claude(
        source_text, artifacts.get("source", "fb"),
        instruction, system_prompt=SYSTEM_PROMPT,
    )
    if tg_raw.startswith("Błąd Claude"):
        return None

    tg_text, banner = apply_banner_from_llm(
        tg_raw, fallback=artifacts.get("image") or root_config.ALERT_IMAGE,
    )
    tg_text = fit_telegram_text(tg_text)
    sent = await send_preview(bot, tg_text, make_url_confirm_buttons(), reply_to=anchor)
    tg_post = {
        "text": tg_text,
        "original_text": artifacts.get("original_text", source_text),
        "source": artifacts.get("source", ""),
        "platform": "url_article",
        "phase": "confirm",
        "article_url": artifacts.get("article_url", ""),
        "user_instruction": artifacts.get("user_instruction", ""),
        "title": artifacts.get("title", ""),
        "image": banner,
        "phase1_msg_id": anchor,
        "parent_msg_id": parent_msg_id,
        "edit_chain": ["url_draft"],
        "repeat_context": artifacts.get("repeat_context") or {},
    }
    pending_posts[sent.id] = track_post(pending_posts, tg_post, sent_id=sent.id)
    shared_facts.merge(anchor, original_text=artifacts.get("original_text", source_text))
    return sent


def _tg_buttons_for_phase(phase: str):
    if phase == "ready":
        return make_url_publish_buttons()
    if phase == "adjust":
        return make_url_adjust_buttons()
    return make_url_confirm_buttons()


def register_facebook_handlers(bot):
    @bot.on(events.CallbackQuery)
    async def on_fb_button(event):
        if event.sender_id not in REVIEWER_IDS:
            return

        msg_id = event.message_id
        data = event.data.decode()

        if data == "phase1_menu":
            await handle_phase1_menu(bot, event, msg_id)
            return

        # ── Generuj TG z FB (draft lub opublikowany) ──
        if data == "tg_start":
            post = pending_posts.get(msg_id)
            if not post or post.get("platform") not in ("fb_draft", "fb_published"):
                return

            await event.answer("Generuję wersję Telegram...")
            await show_loading(event, "Generuję wersję TG...")
            print("[TG] Generuję wersję Telegram z artefaktów FB...")

            anchor = post.get("phase1_msg_id") or msg_id
            artifacts = await resolve_artifacts(bot, anchor)
            artifacts = {**artifacts, **{k: post.get(k) for k in (
                "original_text", "comment_text", "source", "title", "image", "repeat_context",
            ) if post.get(k)}}

            sent = await generate_tg_from_artifacts(
                bot, artifacts=artifacts, anchor=anchor, parent_msg_id=msg_id,
            )
            if not sent:
                await event.answer("Błąd generowania wersji TG", alert=True)
                try:
                    buttons = (
                        make_fb_published_buttons()
                        if post.get("platform") == "fb_published"
                        else make_fb_adjust_buttons()
                    )
                    await (await event.get_message()).edit(buttons=buttons)
                except Exception:
                    pass
                return

            await restore_phase1_menu(bot, post)
            return

        # ── Generuj FB z draftu TG lub opublikowanego TG ──
        if data == "fb_start":
            tg_post = pending_posts.get(msg_id)
            if not tg_post or tg_post.get("platform") not in ("url_article", "published"):
                return

            await event.answer("Generuję wersję FB...")
            await show_loading(event, "Generuję wersję FB...")
            print("[FB] Generuję wersję na Facebooka z artefaktów TG...")

            anchor = tg_post.get("phase1_msg_id") or msg_id
            artifacts = await resolve_artifacts(bot, anchor)
            artifacts = {**artifacts, **{k: tg_post.get(k) for k in (
                "original_text", "source", "title", "image", "repeat_context", "text",
            ) if tg_post.get(k)}}

            from core.gen_context import build_icon_hint
            source_text = artifacts.get("original_text") or build_source_text(artifacts)
            icon_hint = await build_icon_hint(
                anchor, source_text,
                artifacts.get("source", "telegram"),
                artifacts.get("title", ""),
            )

            sent, err = await generate_fb_from_artifacts(
                bot, artifacts=artifacts, anchor=anchor, icon_hint=icon_hint,
            )
            if not sent:
                await event.answer("Błąd generowania wersji FB", alert=True)
                return

            try:
                tg_msg = await event.get_message()
                if tg_post.get("platform") == "url_article":
                    await tg_msg.edit(buttons=_tg_buttons_for_phase(tg_post.get("phase", "confirm")))
            except Exception:
                pass
            return

        if data == "fb_promo":
            promo_post = pending_posts.get(msg_id)
            fb_post_id = promo_post.get("fb_post_id") if promo_post else None
            if not fb_post_id:
                await event.answer("Brak ID opublikowanego posta FB", alert=True)
                return

            await event.answer("Dodaję PROMO w komentarzu...")
            await show_loading(event, "Dodaję PROMO...")
            print(f"[PROMO_FB] Komentuję post {fb_post_id}...")

            promo_img = root_config.PROMO_IMAGE if os.path.exists(root_config.PROMO_IMAGE) else None
            ok, result = await comment_on_facebook(fb_post_id, FB_PROMO_TEXT, image_path=promo_img)
            original_msg = await event.get_message()
            if ok:
                print(f"[PROMO_FB] OK: {result}")
                save_state()
                await original_msg.edit(
                    original_msg.text + "\n\n📣 PROMO DODANE W KOMENTARZU",
                    buttons=make_fb_published_buttons(),
                )
                return
            print(f"[PROMO_FB] Błąd: {result}")
            await event.answer(f"FB PROMO: {result}", alert=True)
            try:
                await original_msg.edit(buttons=make_fb_published_buttons())
            except Exception:
                pass
            return

        post = pending_posts.get(msg_id)
        if not post or post.get("platform") != "fb_draft":
            return

        if data == "fb_pub":
            await event.answer("Publikuję na FB...")
            await show_loading(event, "Publikuję na FB...")
            print("[PUB_FB] Publikuję na Facebooku...")

            ok, result = await publish_to_facebook(
                post["text"],
                image_path=_alert_image(post),
            )
            original_msg = await event.get_message()
            if ok:
                print(f"[PUB_FB] OK: {result}")
                status = "\n\n✅ OPUBLIKOWANO NA FB"
                comment = post.get("comment_text", "")
                if comment:
                    c_ok, c_result = await comment_on_facebook(result, comment)
                    if c_ok:
                        print(f"[PUB_FB] Komentarz OK: {c_result}")
                        status += "\n💬 KOMENTARZ ZE SZCZEGÓŁAMI DODANY"
                    else:
                        print(f"[PUB_FB] Komentarz błąd: {c_result}")
                        status += f"\n⚠️ Komentarz nie dodany: {c_result}"
                await original_msg.edit(
                    original_msg.text + status,
                    buttons=make_fb_published_buttons(),
                )
                post["platform"] = "fb_published"
                post["fb_post_id"] = result
                # Kąpieliska: zapamiętaj post FB na 30 dni (update statusu → komentarz)
                if post.get("kind") == "kapieliska" or "KĄPIELISK" in (post.get("source") or "").upper():
                    try:
                        from kapieliska.store import register_active_alert, set_active_fb_post
                        kid = post.get("kapielisko_id") or ""
                        if not kid:
                            # spróbuj z URL w original_text / article
                            import re
                            m = re.search(r"/kapielisko/(\d+)", post.get("original_text", "") + " " + post.get("source", ""))
                            if m:
                                kid = m.group(1)
                        if kid:
                            set_active_fb_post(kid, result)
                            register_active_alert(
                                {
                                    "id": kid,
                                    "name": post.get("title", ""),
                                    "url": f"https://sk.gis.gov.pl/kapielisko/{kid}",
                                    "lokalizacja": post.get("lokalizacja", ""),
                                    "ocena": "",
                                    "data_oceny": "",
                                },
                                fb_post_id=result,
                            )
                            print(f"[PUB_FB] active alert 30d: kapielisko {kid} → {result}")
                    except Exception as e:
                        print(f"[PUB_FB] active alert save failed: {e}")
                shared_facts.merge(
                    post.get("phase1_msg_id", msg_id),
                    original_text=post.get("original_text", ""),
                    comment_text=post.get("comment_text", ""),
                )
                await restore_phase1_menu(bot, post)
                save_state()
                return

            print(f"[PUB_FB] Błąd: {result}")
            await event.answer(f"FB: {result}", alert=True)
            try:
                await original_msg.edit(buttons=make_fb_adjust_buttons())
            except Exception:
                pass
            return

        if data == "fb_no":
            pending_posts.pop(msg_id, None)
            await event.answer("Odrzucono wersję FB")
            try:
                await event.delete()
            except Exception:
                pass
            return

        if data == "fb_edit":
            await event.answer("Edycja FB...")
            await bot.send_message(
                INTERNAL_CHAT_ID,
                "Odpowiedz na wiadomość z wersją FB.\n"
                "! — podmień post główny dosłownie\n"
                "!! — podmień komentarz ze szczegółami dosłownie\n"
                "bez prefiksu — instrukcja przeróbki posta głównego:",
                reply_to=msg_id,
            )
            return

        if data == "fb_shorten_menu":
            await event.answer("O ile skrócić?")
            await (await event.get_message()).edit(buttons=make_fb_shorten_buttons())
            return

        if data == "fb_shorten_back":
            await event.answer("Powrót")
            await (await event.get_message()).edit(buttons=make_fb_adjust_buttons())
            return

        if data in FB_ADJUST_INSTRUCTIONS:
            label = FB_ADJUST_LABELS[data]
            await event.answer(f"Przerabiam ({label})...")
            await show_loading(event, f"{label}...")
            print(f"[FB {label}] Przerabiam post...")

            chain = post.get("edit_chain", [])
            style_context = ""
            if chain:
                applied = [FB_STYLE_NAMES.get(s, s) for s in chain]
                style_context = (
                    f"WAŻNE: Dotychczas zastosowane style: {', '.join(applied)}. "
                    "Zachowaj charakter poprzednich edycji, tylko zastosuj nowe polecenie.\n\n"
                )

            rewritten, banner = await _regen_fb(
                bot, post, style_context + FB_ADJUST_INSTRUCTIONS[data], label=label,
            )
            if rewritten.startswith("Błąd Claude"):
                await event.answer(rewritten, alert=True)
                try:
                    await (await event.get_message()).edit(buttons=make_fb_adjust_buttons())
                except Exception:
                    pass
                return
            anchor = post.get("phase1_msg_id")
            preview = format_fb_preview(rewritten, post.get("comment_text", ""))
            sent = await _send_fb_preview(
                bot, preview, make_fb_adjust_buttons(), reply_to=anchor, image=banner,
            )

            post["text"] = rewritten
            post["image"] = banner
            post.setdefault("edit_chain", []).append(data)
            pending_posts.pop(msg_id, None)
            pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
            shared_facts.merge(anchor, comment_text=post.get("comment_text", ""))

            try:
                await (await event.get_message()).delete()
            except Exception:
                pass
            return

    @bot.on(events.NewMessage(func=lambda e: (
        e.is_reply and getattr(e, "chat_id", None) == INTERNAL_CHAT_ID
    )))
    async def on_fb_edit_reply(event):
        if event.sender_id not in REVIEWER_IDS:
            return

        reply_msg = await event.get_reply_message()
        original_msg_id = reply_msg.reply_to_msg_id if reply_msg.reply_to_msg_id else reply_msg.id

        post = pending_posts.get(original_msg_id)
        if not post or post.get("platform") != "fb_draft":
            return

        text = event.text.strip()
        is_kap = post.get("kind") == "kapieliska" or "KĄPIELISK" in (post.get("source") or "").upper()
        if text.startswith("!"):
            post["text"] = fit_fb_text(text[1:].strip())
            await event.reply("Tekst FB zaktualizowany.")
        elif text.startswith("!!"):
            post["comment_text"] = fit_fb_text(text[2:].strip(), max_chars=1000)
            await event.reply("Komentarz FB zaktualizowany.")
        else:
            await event.reply("Przerabiam wersję FB...")
            from kapieliska.prompts import FB_KAPIELISKA_SYSTEM_PROMPT
            sys_p = FB_KAPIELISKA_SYSTEM_PROMPT if is_kap else FB_SYSTEM_PROMPT
            new_text = await edit_claude(
                post["text"],
                FB_MANUAL_EDIT_INSTRUCTION(text),
                source_facts=post.get("original_text", ""),
                source=post.get("source", "fb"),
                system_prompt=sys_p,
            )
            if is_kap:
                post["text"] = fit_fb_text(new_text)
                post["image"] = _kapieliska_image()
            else:
                post["text"], post["image"] = _process_fb_text(
                    new_text, fallback=post.get("image"),
                )

        if is_kap:
            post["image"] = _kapieliska_image()

        anchor = post.get("phase1_msg_id")
        preview = format_fb_preview(post["text"], post.get("comment_text", ""))
        sent = await _send_fb_preview(
            bot, preview, make_fb_adjust_buttons(),
            reply_to=anchor, image=post.get("image"),
        )
        pending_posts.pop(original_msg_id, None)
        pending_posts[sent.id] = track_post(pending_posts, post, sent_id=sent.id)
        if anchor:
            shared_facts.merge(anchor, comment_text=post.get("comment_text", ""))
