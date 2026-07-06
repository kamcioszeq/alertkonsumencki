"""Item ingestion: dropped links, /new, /test.

Everything funnels into a Phase-1 message carrying the 🔍 Generuj post button.
The future GIS crawler will call `ingest_alert()` the same way.
"""
import html

from telethon import events

import config as root_config
from . import config
from .buttons import make_generate_button
from .publish import send_alert_photo
from core.article import has_url, apply_url_fields
from core.state import pending_adoption, track_post

SAMPLE_ALERT = (
    "GIS: Wycofanie partii sera pleśniowego \"Przykładowy Ser\" 200 g z powodu wykrycia "
    "bakterii Listeria monocytogenes. Producent: Przykładowa Mleczarnia Sp. z o.o. "
    "Numer partii: L2026-07-01, data ważności: 2026-08-15. "
    "Zaleca się nie spożywać produktu i zwrócić go do sklepu."
)


def _phase1_message(post: dict) -> str:
    if post.get("has_url"):
        line = f"🔗 Nowy link: {post['article_url']}"
        if post.get("user_instruction"):
            line += f"\n📝 Uwaga: {post['user_instruction']}"
        return line + "\n\nKliknij, aby wygenerować post."
    return "🆕 Nowy alert (tekst). Kliknij, aby wygenerować post."


async def ingest_warning(bot, *, title: str, url: str, text: str, date_str: str = ""):
    """Handoff from the GIS crawler: DM the alert image + summary + 🔍 Generuj button.

    The crawler already fetched the article text, so it's stored as original_text and the
    draft is generated from it directly (no re-fetch)."""
    caption = (
        "🆕 <b>Nowe ostrzeżenie GIS</b>\n"
        f"<b>{html.escape(title)}</b>\n"
        + (f"📅 {html.escape(date_str)}\n" if date_str else "")
        + (f"🔗 {html.escape(url)}\n" if url else "")
        + "\nWygenerować post?"
    )
    sent = await send_alert_photo(bot, caption, make_generate_button())
    post = {
        "original_text": text,
        "source": url or "GIS",
        "has_url": False,
        "article_url": "",  # tekst mamy z crawlera — url_read użyje original_text
        "user_instruction": "",
        "title": title,
        "image": root_config.ALERT_IMAGE,
    }
    pending_adoption[sent.id] = track_post(pending_adoption, post, sent_id=sent.id)
    print(f"[QUEUE_INGEST] {title[:60]}")
    return sent


async def ingest_alert(bot, text: str, *, source: str = "ingest"):
    """Register a new item and post the 🔍 Generuj button in the internal chat."""
    post = {
        "original_text": text, "source": source, "has_url": False,
        "article_url": "", "user_instruction": "", "image": root_config.ALERT_IMAGE,
    }
    apply_url_fields(post, text)
    sent = await bot.send_message(
        config.INTERNAL_CHAT_ID, _phase1_message(post), buttons=make_generate_button(),
    )
    pending_adoption[sent.id] = track_post(pending_adoption, post, sent_id=sent.id)
    return sent


def register_ingest(bot):
    @bot.on(events.NewMessage(func=lambda e: (
        getattr(e, "chat_id", None) == config.INTERNAL_CHAT_ID
        and not e.forward and not e.is_reply and e.text
        and not e.text.startswith("/") and has_url(e.text)
    )))
    async def on_direct_url(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        text = event.text.strip()
        post = {
            "original_text": text, "source": "link", "has_url": False,
            "article_url": "", "user_instruction": "", "image": root_config.ALERT_IMAGE,
        }
        apply_url_fields(post, text)
        sent = await bot.send_message(
            config.INTERNAL_CHAT_ID, _phase1_message(post),
            buttons=make_generate_button(), reply_to=event.id,
        )
        pending_adoption[sent.id] = track_post(pending_adoption, post, sent_id=sent.id)
        print(f"[DIRECT_URL] {post.get('article_url', '?')}")

    @bot.on(events.NewMessage(pattern=r"^/new(?:\s+([\s\S]+))?$"))
    async def on_new(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        body = (event.pattern_match.group(1) or "").strip()
        if not body:
            await event.reply("Użycie: /new <treść lub URL>")
            return
        await ingest_alert(bot, body, source="/new")

    @bot.on(events.NewMessage(pattern=r"^/test$"))
    async def on_test(event):
        if event.sender_id not in config.REVIEWER_IDS:
            return
        if getattr(event, "chat_id", None) != config.INTERNAL_CHAT_ID:
            return
        await ingest_alert(bot, SAMPLE_ALERT, source="/test")
