"""Inline button layouts for the Telegram review flow (text-only)."""
from telethon import Button


def make_generate_button():
    """Phase-1: a dropped link/item — click to generate the draft."""
    return [
        [Button.inline("🔍 Generuj post", b"url_read")],
        [Button.inline("Odrzuć", b"reject")],
    ]


def make_url_confirm_buttons():
    """Draft just generated — accept, adjust, or reject."""
    return [[
        Button.inline("✅ OK", b"url_ok"),
        Button.inline("Dostosuj", b"url_adjust"),
        Button.inline("Odrzuć", b"pub_no"),
    ]]


def make_url_publish_buttons():
    """Draft accepted — ready to publish."""
    return [[
        Button.inline("Publikuj", b"pub_yes"),
        Button.inline("Odrzuć", b"pub_no"),
    ]]


def make_url_adjust_buttons():
    """Draft adjust menu — the 4 custom rephrase styles + publish/reject/edit."""
    return [
        [Button.inline("Publikuj", b"pub_yes"), Button.inline("Odrzuć", b"pub_no")],
        [Button.inline("Bardziej formalny", b"formal"), Button.inline("Mniej formalny", b"informal")],
        [Button.inline("Techniczny", b"technical"), Button.inline("Sugestia", b"suggestion"), Button.inline("Edytuj", b"pub_edit")],
    ]
