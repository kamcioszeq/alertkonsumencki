"""Odtwarza fakty alertu z cache, stanu i wiadomości TG — przyciski Generuj zawsze działają."""
import re

import config as root_config
from core.article import fetch_article
from core import shared_facts
from core.state import pending_adoption, pending_posts
from facebook.publish import html_to_plain


def _richness(post: dict) -> int:
    score = 0
    if post.get("original_text"):
        score += len(post["original_text"])
    if post.get("comment_text"):
        score += len(post["comment_text"]) + 500
    if post.get("text"):
        score += len(post["text"]) // 2
    if post.get("title"):
        score += 50
    return score


def _posts_for_phase1(phase1_msg_id: int) -> list[dict]:
    out = []
    for post in pending_posts.values():
        if post.get("phase1_msg_id") == phase1_msg_id:
            out.append(post)
    return sorted(out, key=_richness, reverse=True)


def _merge_dict(*dicts: dict) -> dict:
    merged = {}
    for d in dicts:
        if not d:
            continue
        for k, v in d.items():
            if v is not None and v != "":
                if k not in merged or _richness({k: v}) >= _richness({k: merged.get(k)}):
                    merged[k] = v
    return merged


def _parse_fb_preview_message(text: str) -> dict:
    """Wyciąga post FB i komentarz z podglądu w czacie."""
    if not text or "━━━ KOMENTARZ" not in text:
        return {}
    parts = re.split(r"━━━ KOMENTARZ \(auto po publikacji\) ━━━", text, maxsplit=1)
    if len(parts) != 2:
        return {}
    main, comment = parts[0].strip(), parts[1].strip()
    return {"text": main, "comment_text": comment}


async def _from_messages(bot, phase1_msg_id: int) -> dict:
    """Skanuje wiadomości w wątku Phase1 (reply_to = phase1)."""
    from telegram.config import INTERNAL_CHAT_ID

    result = {}
    try:
        async for msg in bot.iter_messages(
            INTERNAL_CHAT_ID, reply_to=phase1_msg_id, limit=30,
        ):
            raw = (msg.text or msg.message or "").strip()
            if not raw:
                continue
            parsed = _parse_fb_preview_message(raw)
            if parsed:
                result = _merge_dict(result, parsed)
                continue
            # Draft TG (HTML) — użyj jako text, nie jako original_text
            if "<b>" in raw or "Alert konsumencki" in raw:
                result = _merge_dict(result, {"text": raw})
    except Exception as e:
        print(f"[RESOLVE] message scan failed: {e}")
    return result


def build_source_text(artifacts: dict) -> str:
    """Tekst źródłowy do generowania TG — original + komentarz FB."""
    parts = []
    original = (artifacts.get("original_text") or "").strip()
    if original:
        parts.append(original)
    comment = (artifacts.get("comment_text") or "").strip()
    if comment:
        parts.append(f"\n--- Szczegóły partii (z wersji FB) ---\n{comment}")
    if parts:
        return "\n".join(parts)
    tg_draft = (artifacts.get("text") or "").strip()
    if tg_draft:
        return html_to_plain(tg_draft)
    return ""


async def resolve_artifacts(bot, phase1_msg_id: int, *, allow_fetch: bool = True) -> dict:
    """Zbiera fakty alertu — cache → pending_adoption → pending_posts → wiadomości → fetch."""
    cached = shared_facts.load(phase1_msg_id) or {}
    adoption = pending_adoption.get(phase1_msg_id) or {}
    posts = _posts_for_phase1(phase1_msg_id)
    best_post = posts[0] if posts else {}
    from_msgs = await _from_messages(bot, phase1_msg_id) if bot else {}

    artifacts = _merge_dict(cached, adoption, best_post, from_msgs)
    artifacts["phase1_msg_id"] = phase1_msg_id

    # Uzupełnij original_text z najbogatszego posta jeśli brak
    if not artifacts.get("original_text"):
        for p in posts:
            if p.get("original_text"):
                artifacts["original_text"] = p["original_text"]
                break

    # comment_text z dowolnego fb_draft / fb_published
    if not artifacts.get("comment_text"):
        for p in posts:
            if p.get("comment_text"):
                artifacts["comment_text"] = p["comment_text"]
                break

    article_url = artifacts.get("article_url", "")
    if allow_fetch and article_url and len((artifacts.get("original_text") or "")) < 80:
        try:
            article = await fetch_article(article_url)
            article_text = article["text"]
            if article.get("title"):
                article_text = f"{article['title']}\n\n{article_text}"
            artifacts["original_text"] = article_text
            artifacts["source"] = article.get("url", article_url)
        except Exception as e:
            print(f"[RESOLVE] fetch fallback failed: {e}")

    if not artifacts.get("image"):
        artifacts["image"] = root_config.ALERT_IMAGE

    shared_facts.merge(phase1_msg_id, **{
        k: artifacts.get(k)
        for k in (
            "original_text", "comment_text", "source", "title", "image",
            "article_url", "user_instruction", "repeat_context",
        )
        if artifacts.get(k)
    })

    return artifacts
