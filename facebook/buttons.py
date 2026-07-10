"""Inline button layouts for the Facebook review flow."""
from telethon import Button


def make_fb_adjust_buttons():
    """FB draft — adjust, edit, publish, or reject."""
    return [
        [Button.inline("Publikuj FB", b"fb_pub"), Button.inline("Odrzuć", b"fb_no")],
        [Button.inline("➡️ Zrób wersję TG", b"tg_start")],
        [
            Button.inline("Bardziej formalny", b"fb_formal"),
            Button.inline("Mniej formalny", b"fb_informal"),
        ],
        [
            Button.inline("Techniczny", b"fb_technical"),
            Button.inline("Sugestia", b"fb_suggestion"),
        ],
        [Button.inline("✍️ Gramatyka", b"fb_grammar")],
        [
            Button.inline("Skróć", b"fb_shorten_menu"),
            Button.inline("Edytuj", b"fb_edit"),
        ],
    ]


def make_fb_published_buttons():
    """Po publikacji na FB — generuj TG, PROMO, powrót do Phase1."""
    return [
        [Button.inline("➡️ Generuj TG", b"tg_start")],
        [Button.inline("📣 PROMO", b"fb_promo")],
        [Button.inline("↩️ Główne menu", b"phase1_menu")],
    ]


def make_fb_shorten_buttons():
    return [
        [
            Button.inline("20%", b"fb_short_20"),
            Button.inline("30%", b"fb_short_30"),
            Button.inline("50%", b"fb_short_50"),
            Button.inline("70%", b"fb_short_70"),
        ],
        [Button.inline("← Wróć", b"fb_shorten_back")],
    ]
