"""Telegram length limits and text fitting (text-only)."""

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_CAPTION_LIMIT = 1024
FOOTER_HANDLE = "@alertkonsumencki"


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

    truncated = body[:available].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "…" + footer_block
