"""Telegram length limits and text fitting (text-only)."""
import re

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024
FOOTER_HANDLE = "@alertkonsumencki"

_SENTENCE_END_RE = re.compile(r"[.!?](?=\s|$)")


def telegram_char_limit(has_media: bool = False) -> int:
    return TELEGRAM_CAPTION_LIMIT if has_media else TELEGRAM_MESSAGE_LIMIT


def telegram_limit_instruction(has_media: bool = False) -> str:
    """Claude instruction fragment enforcing Telegram length limits."""
    limit = 900 if has_media else 3500
    kind = "podpisu ze zdjęciem (max 1024 znaki)" if has_media else "wiadomości tekstowej (max 4096 znaki)"
    return (
        f"LIMIT DŁUGOŚCI: cały post (nagłówek + treść + stopka) musi zmieścić się w {kind}. "
        f"Celuj w MAX {limit} znaków. Jeśli tekst jest za długi — skróć treść, zachowaj nagłówek i stopkę."
    )


def _trim_body(body: str, available: int) -> tuple[str, bool]:
    """Trim `body` to `available` chars. Tries a clean sentence-boundary cut first
    (no ellipsis needed); falls back to word-boundary + ellipsis when no sentence
    end is close enough to the budget to be worth using.

    Returns (trimmed_body, needs_ellipsis).
    """
    if len(body) <= available:
        return body, False

    slack = max(60, min(350, available // 4))
    candidates = [m.end() for m in _SENTENCE_END_RE.finditer(body) if m.end() <= available]
    if candidates:
        cut_at = max(candidates)
        if available - cut_at <= slack:
            return body[:cut_at].rstrip(), False

    truncated = body[:available].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated, True


def _balance_html_tags(text: str) -> str:
    """Close any <b>/<blockquote> left open by truncation (the only tags the
    system prompts ever produce). <b> can be nested inside <blockquote>, never
    the reverse, so close innermost-first."""
    closers = ""
    if text.count("<b>") > text.count("</b>"):
        closers += "</b>"
    if text.count("<blockquote>") > text.count("</blockquote>"):
        closers += "</blockquote>"
    return text + closers


def fit_telegram_text(text: str, has_media: bool = False) -> str:
    """Truncate text to fit Telegram limits, preserving the footer line when possible."""
    limit = telegram_char_limit(has_media)
    buffer = 15 if has_media else 50
    safe = limit - buffer
    if len(text) <= safe:
        return text

    lines = text.split("\n")
    footer = ""
    if lines and FOOTER_HANDLE in lines[-1]:
        footer = lines[-1]
        lines = lines[:-1]
        if lines and not lines[-1].strip():
            lines = lines[:-1]

    body = "\n".join(lines).strip()
    footer_block = f"\n\n{footer}" if footer else ""
    available = safe - len(footer_block)
    if available < 100:
        return text[:safe] + "…"

    truncated, needs_ellipsis = _trim_body(body, available)
    truncated = _balance_html_tags(truncated)
    suffix = "…" if needs_ellipsis else ""
    return truncated + suffix + footer_block
