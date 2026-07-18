"""Telegram callbacks: update komentarza FB po zmianie statusu kąpieliska."""
import html

from telethon import events

from core.claude import ask_claude
from core.state import pending_posts, save_state
from . import config
from .publish import show_loading


def register_kapieliska_handlers(bot):
    @bot.on(events.CallbackQuery(pattern=rb"^kap_status_(comment|skip)$"))
    async def on_kap_status(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        msg_id = event.message_id
        post = pending_posts.get(msg_id)
        if not post or post.get("platform") != "kapieliska_status":
            await event.answer("Brak powiadomienia statusu", alert=True)
            return

        action = event.data.decode().split("_")[-1]  # comment | skip
        if action == "skip":
            await event.answer("Pominięto")
            try:
                await (await event.get_message()).edit(
                    buttons=None,
                )
            except Exception:
                pass
            pending_posts.pop(msg_id, None)
            save_state()
            return

        fb_post_id = post.get("fb_post_id") or ""
        if not fb_post_id:
            await event.answer(
                "Brak ID posta FB — opublikuj najpierw alert zagrożenia, "
                "albo dodaj fb_post_id ręcznie.",
                alert=True,
            )
            return

        await event.answer("Generuję update komentarza...")
        await show_loading(event, "Update komentarza FB...")

        from kapieliska.prompts import (
            FB_KAPIELISKA_STATUS_COMMENT,
            FB_KAPIELISKA_COMMENT_SYSTEM,
        )
        from facebook.publish import comment_on_facebook
        from facebook.prompts import fit_fb_text

        raw = await ask_claude(
            post.get("original_text", ""),
            "KĄPIELISKA_STATUS",
            FB_KAPIELISKA_STATUS_COMMENT,
            system_prompt=FB_KAPIELISKA_COMMENT_SYSTEM,
        )
        if raw.startswith("Błąd Claude"):
            await event.answer(raw[:180], alert=True)
            return

        comment = fit_fb_text(raw, max_chars=1000)
        ok, result = await comment_on_facebook(fb_post_id, comment)
        msg = await event.get_message()
        if ok:
            text = (msg.text or "") + (
                f"\n\n✅ <b>Update w komentarzu FB</b>\n"
                f"<code>{html.escape(comment[:400])}</code>"
            )
            await msg.edit(text, buttons=None, parse_mode="html")
            pending_posts.pop(msg_id, None)
            save_state()
            print(f"[KAP_STATUS] comment OK on {fb_post_id}")
        else:
            await event.answer(f"FB comment: {result}", alert=True)
            print(f"[KAP_STATUS] comment FAIL: {result}")
