"""Facebook post prompts — main post + auto-comment with batch details."""

from core.banners import BANNER_CLASSIFICATION_PROMPT

_ONLY_POST = " Zwróć wyłącznie gotowy post — bez komentarza i bez opisu, co robisz."
_ONLY_COMMENT = " Zwróć wyłącznie gotowy komentarz — bez komentarza i bez opisu, co robisz."

# Emoji kategorii żywności (jedna ikona z właściwej grupy w hooku).
_FB_CATEGORY_EMOJI = """
IKONY W HOOKU — dokładnie DWA emoji na początku hooka:
1) Ikona ostrzeżenia: ⚠️ LUB 🚨 (naprzemiennie — raz jedna, raz druga; nie używaj obu naraz).
2) Ikona kategorii produktu — ZAWSZE jedna z poniższych grup (dopasuj do produktu):
   • Produkty zbożowe (chleb, mąka, pieczywo, kasze, makaron) → 🌾 lub 🍞
   • Warzywa i owoce → 🥬 lub 🍎
   • Mleko i przetwory mleczne (ser, jogurt, mleko) → 🥛 lub 🧀
   • Mięso, ryby, jaja, dania gotowe (bigos, zupa) → 🥩 lub 🍲 lub 🥘 lub 🐟 lub 🥚
   • Tłuszcze (olej, masło, margaryna) → 🫒 lub 🧈
   • Cukier i słodycze (herbatniki, ciastka, cukierki, batoniki) → 🍪 lub 🍫 lub 🍬
Format hooka: [⚠️ lub 🚨] [emoji kategorii] [zdanie]
Przykład: «⚠️ 🥘 Kupujesz produkty bezglutenowe? Sprawdź, czy nie masz tego produktu w domu»
"""

FB_SYSTEM_PROMPT = (
    "Jesteś redaktorem postów na Facebooku dla kanału z alertami konsumenckimi. "
    "Pisz PO POLSKU, zwięźle i przystępnie. "
    "Format: plain text (bez HTML, bez Markdown). Bez linków. "
    "Korzystaj wyłącznie z podanych informacji — nie wymyślaj danych.\n"
    + _FB_CATEGORY_EMOJI
    + "\n"
    "HOOK — NAJWAŻNIEJSZA LINIA. Musi być DOSADNY i maksymalnie KLIKALNY:\n"
    "• tryb bezpośredni (pytanie do czytelnika, imperatyw, pilność),\n"
    "• trafia w grupę docelową (np. alergicy, rodzice, kupujący w danej sieci),\n"
    "• budzi ciekawość i zatrzymuje scroll — ale BEZ kłamstw i bez sensacji.\n"
    "• NIE podawaj w hooku nazwy produktu ani producenta — to dopiero w pkt 2.\n"
    "Przykłady dobrych hooków:\n"
    "«⚠️ 🥘 Kupujesz produkty bezglutenowe? Sprawdź, czy nie masz tego produktu w domu»\n"
    "«🚨 🍪 Masz te herbatniki w szafce? GIS właśnie wydał alert»\n"
    "«⚠️ 🧀 Kupujesz ten ser? Uważaj — może być niebezpieczny dla zdrowia»\n"
    "\n"
    "STRUKTURA POSTA GŁÓWNEGO — DOKŁADNIE w tej kolejności, każdy element w osobnym akapicie:\n"
    "1) HOOK — jak wyżej (⚠️/🚨 + emoji kategorii + dosadne, klikalne zdanie).\n"
    "2) GIS — jedno zdanie: «GIS wydał ostrzeżenie dotyczące partii [nazwa produktu] "
    "[gramatura, jeśli jest] producenta [producent].» "
    "Jeśli w źródle podano sieć/sklep — dodaj tu wyraźnie (np. «ze sprzedaży Biedronki»). "
    "To jedyne miejsce na nazwę sklepu/sieci.\n"
    "3) ZAGROŻENIE — dokładnie JEDNO zdanie: co stwierdzono i dla kogo jest ryzyko. "
    "Czysta informacja — bez sugerowania winy producenta.\n"
    "4) CTA — dokładnie ta linia: «Szczegóły partii w komentarzu ⬇️»\n"
    "5) STOPKA — dokładnie: «Źródło: [GIS/RASFF/inne]» (bez daty — data idzie do komentarza).\n"
    "\n"
    "NIE umieszczaj w poście głównym: numeru partii, terminu ważności, szczegółowego zalecenia — "
    "to trafia do osobnego komentarza pod postem.\n"
    "\n"
    "KONTROLA PRZED ODDANIEM:\n"
    "1) Czy hook jest dosadny i klikalny (pytanie/imperatyw, grupa docelowa)?\n"
    "2) Czy są ⚠️/🚨 + emoji kategorii na początku hooka?\n"
    "3) Czy sklep/sieć jest wyraźnie w pkt 2 (jeśli jest w źródle)?\n"
    "4) Czy jest linia «Szczegóły partii w komentarzu ⬇️»?\n"
    + BANNER_CLASSIFICATION_PROMPT
)

FB_COMMENT_SYSTEM_PROMPT = (
    "Jesteś redaktorem komentarzy pod postami FB z alertami konsumenckimi. "
    "Pisz PO POLSKU. Plain text, bez HTML. Korzystaj wyłącznie z podanych informacji.\n"
    "\n"
    "STRUKTURA KOMENTARZA — DOKŁADNIE w tej kolejności:\n"
    "📌 Szczegóły wycofanej partii:\n"
    "\n"
    "🥘 Produkt: [pełna nazwa + gramatura]\n"
    "🏭 Producent: [nazwa]\n"
    "🔢 Numer partii: [nr] (pomiń linię, jeśli brak w źródle)\n"
    "📅 Termin przydatności do spożycia: [data] (pomiń linię, jeśli brak w źródle)\n"
    "\n"
    "[Jedno zdanie zalecenia dla konsumenta — WYŁĄCZNIE z oficjalnego powiadomienia, nie wymyślaj. "
    "Jeśli w źródle brak zalecenia — pomiń ten akapit.]\n"
    "\n"
    "Źródło: [GIS/RASFF/inne], komunikat z [DD.MM.RRRR].\n"
    "\n"
    "Emoji w komentarzu: użyj 🥘 przy produkcie (lub emoji kategorii pasujące do produktu). "
    "Nie powtarzaj nazwy sklepu, jeśli była już w poście głównym."
)

FB_GENERATE_INSTRUCTION = (
    "Na podstawie poniższego alertu napisz POST GŁÓWNY na Facebooka według narzuconej struktury. "
    "Hook musi być dosadny i maksymalnie klikalny. "
    "Szczegóły partii i zalecenie — NIE w poście, tylko w komentarzu (osobno)."
    + _ONLY_POST
)

FB_GENERATE_FROM_SOURCE = (
    "Na podstawie poniższego źródła napisz POST GŁÓWNY na Facebooka według narzuconej struktury. "
    "Hook musi być dosadny i maksymalnie klikalny. "
    "Pomiń szczegóły urzędowe i powtórzenia."
    + _ONLY_POST
)

FB_COMMENT_GENERATE_INSTRUCTION = (
    "Na podstawie poniższego źródła napisz KOMENTARZ ze szczegółami partii "
    "do opublikowania pod postem głównym na Facebooku."
    + _ONLY_COMMENT
)

# Statyczny post PROMO publikowany po opublikowaniu alertu (z obrazkiem QR).
FB_PROMO_TEXT = (
    "📣 Dołącz do społeczności Alert konsumencki! Powiadomienia w ulubionej aplikacji\n"
    "\n"
    "💬 WhatsApp (społeczność):\n"
    "📱 Alert Konsumencki 🚨 - Społeczność\n"
    "https://chat.whatsapp.com/FGyQ9e9O9gq9cAhsCiVtrS\n"
    "\n"
    "📢 Telegram — więcej informacji i powiadomienia bezpośrednio na kanale:\n"
    "https://t.me/alertkonsumencki"
)

FB_REPHRASE_LABELS = {
    "fb_formal": "BARDZIEJ FORMALNY",
    "fb_informal": "MNIEJ FORMALNY",
    "fb_technical": "TECHNICZNY",
    "fb_suggestion": "SUGESTIA",
    "fb_grammar": "GRAMATYKA",
}

FB_REPHRASE_INSTRUCTIONS = {
    "fb_formal": (
        "Przeredaguj powyższy POST GŁÓWNY FB bardziej formalnie — ton urzędowy, rzeczowy. "
        "Zachowaj strukturę (hook → GIS → zagrożenie → CTA → Źródło). "
        "Hook nadal klikalny, ale stonowany." + _ONLY_POST
    ),
    "fb_informal": (
        "Przeredaguj powyższy POST GŁÓWNY FB prostszym, przystępnym językiem. "
        "Hook jeszcze bardziej dosadny i klikalny. Zachowaj strukturę." + _ONLY_POST
    ),
    "fb_technical": (
        "Uwypuklij w poście głównym rodzaj zagrożenia i producenta. "
        "Zachowaj strukturę i hook. Szczegóły partii zostaw poza postem." + _ONLY_POST
    ),
    "fb_suggestion": (
        "Wzmocnij hook — bardziej dosadny i klikalny. Zachowaj strukturę posta głównego." + _ONLY_POST
    ),
    "fb_grammar": (
        "Popraw w powyższym poście FB WYŁĄCZNIE błędy językowe: gramatyka, ortografia, "
        "interpunkcja, odmiana, składnia i literówki w języku polskim. "
        "NIE zmieniaj treści, faktów, struktury, tonu, emoji ani stopki — popraw tylko język. "
        "Jeśli tekst jest już poprawny — zwróć go bez zmian." + _ONLY_POST
    ),
}

FB_SHORTEN_LABELS = {
    "fb_short_20": "SKRÓĆ 20%",
    "fb_short_30": "SKRÓĆ 30%",
    "fb_short_50": "SKRÓĆ 50%",
    "fb_short_70": "SKRÓĆ 70%",
}

FB_SHORTEN_INSTRUCTIONS = {
    key: (
        f"Skróć powyższy POST GŁÓWNY FB o około {pct}%. "
        "Zostaw hook, produkt, zagrożenie i CTA. Zachowaj stopkę."
        + _ONLY_POST
    )
    for key, pct in (
        ("fb_short_20", 20), ("fb_short_30", 30), ("fb_short_50", 50), ("fb_short_70", 70)
    )
}

FB_STYLE_NAMES = {
    "fb_generated": "wygenerowany na FB",
    **{k: v.lower() for k, v in FB_REPHRASE_LABELS.items()},
    **{k: v.lower() for k, v in FB_SHORTEN_LABELS.items()},
}

FB_ADJUST_INSTRUCTIONS = {**FB_REPHRASE_INSTRUCTIONS, **FB_SHORTEN_INSTRUCTIONS}
FB_ADJUST_LABELS = {**FB_REPHRASE_LABELS, **FB_SHORTEN_LABELS}

FB_MAX_CHARS = 500
FB_COMMENT_MAX_CHARS = 1000


def _is_fb_footer(line: str) -> bool:
    """Ostatnia linia stopki FB — nigdy nie ucinaj przy skracaniu."""
    s = (line or "").strip().lower()
    if not s:
        return False
    if "@alertkonsumencki" in s:
        return True
    if s.startswith(("źródło:", "zrodło:", "zrodlo:", "source:")):
        return True
    return "data powiadomienia" in s or "komunikat z" in s


def fit_fb_text(text: str, *, max_chars: int = FB_MAX_CHARS) -> str:
    """Keep FB posts short, ale nigdy nie ucinaj stopki (ostatniej linii)."""
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    lines = text.split("\n")
    footer = ""
    body = text
    if len(lines) > 1 and _is_fb_footer(lines[-1]):
        footer = "\n" + lines[-1].strip()
        body = "\n".join(lines[:-1]).rstrip()
    budget = max_chars - len(footer) - 1
    truncated = body[:budget].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated + "…" + footer


def format_fb_preview(main: str, comment: str) -> str:
    """Podgląd w Telegramie: post główny + komentarz auto."""
    return (
        f"{main.strip()}\n\n"
        "━━━ KOMENTARZ (auto po publikacji) ━━━\n"
        f"{comment.strip()}"
    )
