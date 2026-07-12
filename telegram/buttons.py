"""Inline button layouts for the Telegram review flow (text-only)."""
from telethon import Button


def make_generate_button():
    """Phase-1: a dropped link/item — click to generate the draft.

    Obok domyślnego „Generuj post" dwa szybkie warianty: Krótki / Długi alert,
    które od razu generują z dedykowanego szablonu."""
    return [
        [Button.inline("🔍 Generuj post", b"url_read")],
        [Button.inline("Krótki alert", b"gen_short"), Button.inline("Długi alert", b"gen_long")],
        [Button.inline("📘 Generuj FB", b"gen_fb")],
        [Button.inline("Odrzuć", b"reject")],
    ]


def make_url_confirm_buttons():
    """Draft just generated — accept, adjust, reject, or start FB path."""
    return [
        [Button.inline("FB", b"fb_start")],
        [
            Button.inline("✅ OK", b"url_ok"),
            Button.inline("Dostosuj", b"url_adjust"),
            Button.inline("Odrzuć", b"pub_no"),
        ],
    ]


def make_url_publish_buttons():
    """Draft accepted — ready to publish."""
    return [
        [Button.inline("FB", b"fb_start")],
        [
            Button.inline("Publikuj", b"pub_yes"),
            Button.inline("Odrzuć", b"pub_no"),
        ],
    ]


def make_url_adjust_buttons():
    """Draft adjust menu — the 4 custom rephrase styles + shorten/publish/reject/edit."""
    return [
        [Button.inline("FB", b"fb_start")],
        [Button.inline("Publikuj", b"pub_yes"), Button.inline("Odrzuć", b"pub_no")],
        [Button.inline("Bardziej formalny", b"formal"), Button.inline("Mniej formalny", b"informal")],
        [Button.inline("Techniczny", b"technical"), Button.inline("Sugestia", b"suggestion")],
        [Button.inline("✍️ Gramatyka", b"grammar"), Button.inline("🔁 Powtórz", b"powtorz")],
        [Button.inline("Skróć", b"shorten_menu"), Button.inline("Edytuj", b"pub_edit")],
    ]


def make_tg_published_buttons():
    """Po publikacji na TG — generuj FB lub wróć do Phase1."""
    return [
        [Button.inline("📘 Generuj FB", b"fb_start")],
        [Button.inline("↩️ Główne menu", b"phase1_menu")],
    ]


def make_stats_period_buttons():
    """/stats — wybór okresu."""
    return [[Button.inline("📅 Miesiąc", b"stats_period:month"),
             Button.inline("📆 Rok", b"stats_period:year")]]


def make_stats_type_buttons(period: str):
    """Po wyborze okresu — rodzaj statystyki do wygenerowania."""
    return [
        [Button.inline("📊 Podsumowanie ogólne", f"stats_type:summary:{period}".encode())],
        [Button.inline("⚠️ Top zagrożenia", f"stats_type:categories:{period}".encode())],
        [Button.inline("🏷 Najczęstsze marki", f"stats_type:brands:{period}".encode())],
        [Button.inline("🔥 Najgłośniejsze przypadki", f"stats_type:notable:{period}".encode())],
        [Button.inline("📋 Lista tytułów", f"stats_type:titles:{period}".encode())],
        [Button.inline("🎨 Custom", f"stats_custom:{period}".encode())],
        [Button.inline("← Wróć", b"stats_back")],
    ]


def make_stats_adjust_buttons():
    """Wygenerowany post statystyczny — udostępnij (TG ze stopką / FB bez stopki) albo
    zmień styl przed udostępnieniem."""
    return [
        [Button.inline("📤 Share → TG", b"stats_share:tg"), Button.inline("📘 Share → FB", b"stats_share:fb")],
        [Button.inline("🌶️ Ostro", b"stats_adjust:spicy"), Button.inline("🕊️ Łagodniej", b"stats_adjust:mild")],
        [Button.inline("🔁 Retry", b"stats_adjust:retry"), Button.inline("✍️ Gramatyka", b"stats_adjust:grammar")],
        [Button.inline("💬 Odpowiedz", b"stats_edit")],
        [Button.inline("↩️ Cofnij", b"stats_undo"), Button.inline("Odrzuć", b"stats_reject")],
    ]


def make_stats_shared_buttons(*, tg_done: bool, fb_done: bool):
    """Po udostępnieniu na TG i/lub FB — pokazuje TYLKO to, co jeszcze nie zostało
    zrobione (druga platforma, PROMO), żeby jedna publikacja nie blokowała drugiej."""
    rows = []
    share_row = []
    if not tg_done:
        share_row.append(Button.inline("📤 Share → TG", b"stats_share:tg"))
    if not fb_done:
        share_row.append(Button.inline("📘 Share → FB", b"stats_share:fb"))
    if share_row:
        rows.append(share_row)
    if fb_done:
        rows.append([Button.inline("📣 PROMO", b"fb_promo")])
    return rows or None


def make_promo_buttons():
    """Post promocyjny /promocja — regeneruj, publikuj lub odrzuć."""
    return [
        [Button.inline("📤 Publikuj na FB", b"promo_pub")],
        [Button.inline("🔄 Inne pytanie", b"promo_regen")],
        [Button.inline("Odrzuć", b"promo_reject")],
    ]


def make_promo_published_buttons():
    """Po publikacji posta promocyjnego na FB."""
    return [
        [Button.inline("🔄 Inne pytanie", b"promo_regen")],
        [Button.inline("↩️ Główne menu", b"phase1_menu")],
    ]


def make_shorten_buttons():
    """Shorten submenu — reduce the draft by a chosen percentage."""
    return [
        [
            Button.inline("20%", b"short_20"),
            Button.inline("30%", b"short_30"),
            Button.inline("50%", b"short_50"),
            Button.inline("70%", b"short_70"),
        ],
        [Button.inline("← Wróć", b"shorten_back")],
    ]
