"""Generate → confirm → adjust flow for a dropped item/link."""
import html
from telethon import events

import config as root_config
from core.banners import apply_banner_from_llm
from core import shared_facts
from core.gen_context import build_icon_hint
from core.resolve_artifacts import resolve_artifacts, build_source_text
from . import config
from .prompts import (
    SYSTEM_PROMPT, _build_draft_instruction,
    SHORT_ALERT_TEMPLATE, LONG_ALERT_TEMPLATE, ALERT_VARIANT_SYSTEM, _build_alert_instruction,
)
from .format import fit_telegram_text
from .buttons import make_url_confirm_buttons, make_url_adjust_buttons, make_url_publish_buttons
from .publish import send_preview, show_loading, restore_buttons, handle_phase1_menu, notify_reviewers
from core.claude import ask_claude
from core.state import pending_adoption, pending_posts, track_post, save_state


def _ensure_adoption(phase1_msg_id: int, artifacts: dict) -> dict:
    """Utrzymuj wpis pending_adoption — przyciski Phase1 zawsze mają dane."""
    post = pending_adoption.get(phase1_msg_id) or {}
    post.update({
        "original_text": artifacts.get("original_text") or post.get("original_text", ""),
        "source": artifacts.get("source") or post.get("source", "ingest"),
        "article_url": artifacts.get("article_url") or post.get("article_url", ""),
        "user_instruction": artifacts.get("user_instruction") or post.get("user_instruction", ""),
        "title": artifacts.get("title") or post.get("title", ""),
        "image": artifacts.get("image") or post.get("image") or root_config.ALERT_IMAGE,
        "has_url": bool(artifacts.get("article_url") or post.get("article_url")),
    })
    pending_adoption[phase1_msg_id] = track_post(pending_adoption, post, sent_id=phase1_msg_id)
    return post

def register_url_handlers(bot):
    @bot.on(events.CallbackQuery)
    async def on_url_button(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return

        msg_id = event.message_id
        data = event.data.decode()
        print(f"[CALLBACK][url] sender={event.sender_id} msg_id={msg_id} data={data}")

        if data == "phase1_menu":
            await handle_phase1_menu(bot, event, msg_id)
            return

        if data == "reject":
            shared_facts.delete(msg_id)
            pending_adoption.pop(msg_id, None)
            await event.answer("Odrzucono")
            try:
                await event.delete()
            except Exception:
                pass
            return

        if data in ("url_read", "gen_short", "gen_long", "gen_fb"):
            await event.answer("Generuję...")
            await show_loading(event, "Generuję post...")

            artifacts = await resolve_artifacts(bot, msg_id)
            article_text = (artifacts.get("original_text") or build_source_text(artifacts) or "").strip()
            if not article_text:
                await restore_buttons(bot, msg_id)
                await event.answer("Brak treści źródłowej", alert=True)
                return

            post = _ensure_adoption(msg_id, artifacts)
            post["original_text"] = article_text
            source = artifacts.get("source") or post.get("source", "ingest")
            title = artifacts.get("title") or post.get("title", "")

            shared_facts.merge(msg_id, original_text=article_text, source=source, title=title)

            if data == "gen_fb":
                from facebook.handlers import generate_fb_from_artifacts
                icon_hint = await build_icon_hint(msg_id, article_text, source, title)
                sent, err = await generate_fb_from_artifacts(
                    bot, artifacts=artifacts, anchor=msg_id, icon_hint=icon_hint,
                )
                await restore_buttons(bot, msg_id)
                if not sent:
                    await event.answer("Błąd generowania wersji FB", alert=True)
                    if err:
                        await notify_reviewers(bot, html.escape(f"⚠️ FB: {err}"))
                    return
                print(f"[URL_READ] FB draft gotowy msg_id={sent.id}")
                return

            user_instruction = post.get("user_instruction", "")
            icon_hint = await build_icon_hint(msg_id, article_text, source, title)

            if data == "gen_short":
                instruction = _build_alert_instruction(SHORT_ALERT_TEMPLATE, user_instruction)
                instruction += f"\n\n{icon_hint}"
                system_prompt = ALERT_VARIANT_SYSTEM
                variant_tag = "short_alert"
            elif data == "gen_long":
                instruction = _build_alert_instruction(LONG_ALERT_TEMPLATE, user_instruction)
                instruction += f"\n\n{icon_hint}"
                system_prompt = ALERT_VARIANT_SYSTEM
                variant_tag = "long_alert"
            else:
                instruction = _build_draft_instruction(user_instruction)
                instruction += f"\n\n{icon_hint}"
                system_prompt = SYSTEM_PROMPT
                variant_tag = "url_draft"

            draft_raw = await ask_claude(article_text, source, instruction, system_prompt=system_prompt)
            if draft_raw.startswith("Błąd Claude"):
                await restore_buttons(bot, msg_id)
                await event.answer("Błąd generowania posta", alert=True)
                await notify_reviewers(
                    bot,
                    html.escape(f"⚠️ Błąd Claude przy generowaniu posta: {draft_raw}\nŹródło: {source}"),
                )
                return
            draft, banner = apply_banner_from_llm(
                draft_raw, fallback=post.get("image") or root_config.ALERT_IMAGE,
            )
            draft = fit_telegram_text(draft)

            cached = shared_facts.load(msg_id)
            url_post = {
                "text": draft,
                "original_text": article_text,
                "source": source,
                "platform": "url_article",
                "phase": "confirm",
                "article_url": post.get("article_url", ""),
                "user_instruction": user_instruction,
                "title": title,
                "image": banner,
                "phase1_msg_id": msg_id,
                "edit_chain": [variant_tag],
                "repeat_context": (cached or {}).get("repeat_context") or {},
            }
            sent = await send_preview(bot, draft, make_url_confirm_buttons(), reply_to=msg_id)
            pending_posts[sent.id] = track_post(pending_posts, url_post, sent_id=sent.id)
            shared_facts.merge(msg_id, original_text=article_text, source=source, title=title)
            await restore_buttons(bot, msg_id)
            print(f"[URL_READ] Draft gotowy msg_id={sent.id}")
            return

        post = pending_posts.get(msg_id)
        if not post or post.get("platform") != "url_article":
            return

        if data == "url_ok":
            post["phase"] = "ready"
            save_state()
            await event.answer("OK — możesz publikować")
            msg = await event.get_message()
            await msg.edit(buttons=make_url_publish_buttons())
            return

        if data == "url_adjust":
            post["phase"] = "adjust"
            save_state()
            await event.answer("Dostosuj styl")
            msg = await event.get_message()
            await msg.edit(buttons=make_url_adjust_buttons())
            return
