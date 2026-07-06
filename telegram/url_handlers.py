"""Generate → confirm → adjust flow for a dropped item/link."""
from telethon import events

import config as root_config
from core.banners import apply_banner_from_llm
from . import config
from .prompts import (
    SYSTEM_PROMPT, _build_draft_instruction,
    SHORT_ALERT_TEMPLATE, LONG_ALERT_TEMPLATE, ALERT_VARIANT_SYSTEM, _build_alert_instruction,
)
from .format import fit_telegram_text
from .buttons import make_url_confirm_buttons, make_url_adjust_buttons, make_url_publish_buttons
from .publish import send_preview, show_loading, restore_buttons, handle_phase1_menu
from core.claude import ask_claude
from core.article import fetch_article
from core.state import pending_adoption, pending_posts, track_post, save_state


def register_url_handlers(bot):
    @bot.on(events.CallbackQuery)
    async def on_url_button(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return

        msg_id = event.message_id
        data = event.data.decode()

        if data == "phase1_menu":
            await handle_phase1_menu(bot, event, msg_id)
            return

        # ── Reject a Phase-1 item ──
        if data == "reject":
            pending_adoption.pop(msg_id, None)
            await event.answer("Odrzucono")
            try:
                await event.delete()
            except Exception:
                pass
            return

        # ── Generate a draft from the dropped item/link ──
        # url_read = domyślny „Generuj post"; gen_short / gen_long = szybkie warianty (osobne szablony).
        if data in ("url_read", "gen_short", "gen_long", "gen_fb"):
            post = pending_adoption.get(msg_id)
            if not post:
                await event.answer("Post wygasł", alert=True)
                return

            await event.answer("Generuję...")
            await show_loading(event, "Generuję post...")

            if post.get("article_url"):
                print(f"[URL_READ] msg_id={msg_id} → {post['article_url']}")
                try:
                    article = await fetch_article(post["article_url"])
                except Exception as e:
                    print(f"[URL_READ] Błąd: {e}")
                    await restore_buttons(bot, msg_id)
                    await event.answer("Nie udało się odczytać artykułu", alert=True)
                    return
                article_text = article["text"]
                if article.get("title"):
                    article_text = f"{article['title']}\n\n{article_text}"
                source = article["url"]
            else:
                # Plain-text item (e.g. /test seed) — summarize the raw text directly.
                article_text = post.get("original_text", "")
                source = post.get("source", "ingest")

            # ── FB wprost z oryginału (osobny post) — nie tworzy draftu TG ──
            if data == "gen_fb":
                from facebook.handlers import generate_fb_from_source
                sent, _ = await generate_fb_from_source(
                    bot, article_text=article_text, source=source,
                    image=post.get("image", ""), anchor=msg_id,
                )
                await restore_buttons(bot, msg_id)
                if not sent:
                    await event.answer("Błąd generowania wersji FB", alert=True)
                    return
                print(f"[URL_READ] FB draft gotowy msg_id={sent.id}")
                return

            # Wariant decyduje o szablonie i system prompcie. Domyślny „Generuj post"
            # (url_read) zachowuje dotychczasowe zachowanie bez zmian.
            user_instruction = post.get("user_instruction", "")
            if data == "gen_short":
                instruction = _build_alert_instruction(SHORT_ALERT_TEMPLATE, user_instruction)
                system_prompt = ALERT_VARIANT_SYSTEM
                variant_tag = "short_alert"
            elif data == "gen_long":
                instruction = _build_alert_instruction(LONG_ALERT_TEMPLATE, user_instruction)
                system_prompt = ALERT_VARIANT_SYSTEM
                variant_tag = "long_alert"
            else:
                instruction = _build_draft_instruction(user_instruction)
                system_prompt = SYSTEM_PROMPT
                variant_tag = "url_draft"

            draft_raw = await ask_claude(article_text, source, instruction, system_prompt=system_prompt)
            if draft_raw.startswith("Błąd Claude"):
                await restore_buttons(bot, msg_id)
                await event.answer("Błąd generowania posta", alert=True)
                return
            draft, banner = apply_banner_from_llm(
                draft_raw, fallback=post.get("image") or root_config.ALERT_IMAGE,
            )
            draft = fit_telegram_text(draft)

            url_post = {
                "text": draft,
                "original_text": article_text,
                "source": source,
                "platform": "url_article",
                "phase": "confirm",
                "article_url": post.get("article_url", ""),
                "user_instruction": post.get("user_instruction", ""),
                "title": post.get("title", ""),
                "image": banner,
                "phase1_msg_id": msg_id,
                "edit_chain": [variant_tag],
            }
            sent = await send_preview(bot, draft, make_url_confirm_buttons(), reply_to=msg_id)
            pending_posts[sent.id] = track_post(pending_posts, url_post, sent_id=sent.id)
            await restore_buttons(bot, msg_id)
            print(f"[URL_READ] Draft gotowy msg_id={sent.id}")
            return

        # ── Confirm / adjust an existing draft ──
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
