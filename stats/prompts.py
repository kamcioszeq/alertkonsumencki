"""Prompty do generowania marketingowych podsumowań statystycznych (Facebook/Telegram)."""
import re
from datetime import date

_TITLE_PREFIX_RE = re.compile(r'^(Aktualizacja\s+ostrzeżenia\s+publicznego|Ostrzeżenie\s+publiczne)\b', re.I)


def strip_title_prefix(title: str) -> str:
    """Usuwa standardowy prefiks GIS ('Ostrzeżenie publiczne dotyczące żywności: ' itp.),
    zostawiając samą treść tytułu. Tytuły bez tego prefiksu zwraca bez zmian."""
    if not _TITLE_PREFIX_RE.match(title):
        return title
    if ":" in title:
        _, rest = title.split(":", 1)
        rest = rest.strip()
        if rest:
            return rest[0].upper() + rest[1:]
    m = re.search(r"(?:żywności|kosmetyków)\s*", title, re.I)
    if m:
        rest = title[m.end():].strip()
        if rest:
            return rest[0].upper() + rest[1:]
    return title

# Podsumowania statystyczne wymagają lepszej syntezy/pisania niż zwykłe przeredagowanie
# alertu, więc idą przez mocniejszy model niż domyślny config.CLAUDE_MODEL (Haiku).
STATS_MODEL = "claude-opus-4-8"

STATS_SYSTEM_PROMPT = (
    "Jesteś redaktorem social-media dla \"Alert Konsumencki\" — kanału ostrzegającego przed "
    "niebezpiecznymi produktami spożywczymi w Polsce (na podstawie ostrzeżeń GIS). "
    "Piszesz PODSUMOWANIA STATYSTYCZNE za dany okres, przeznaczone do publikacji na Facebooku "
    "i Telegramie. "
    "Styl: marketingowy i angażujący — ma się chcieć kliknąć i przeczytać do końca — ale NIGDY "
    "kosztem rzetelności: liczby i fakty biorą się WYŁĄCZNIE z podanych niżej danych, niczego "
    "nie zmyślasz. Piszesz jak człowiek, nie jak urząd — konkretnie, z polotem, bez sztywnego "
    "żargonu biurokratycznego. Emoji owszem, ale z umiarem.\n\n"
    "Formatowanie: HTML — <b>bold</b> do wyróżnień, NIGDY Markdown (**bold**). "
    "Zwracasz WYŁĄCZNIE gotowy post — bez wstępu, bez komentarza, bez opisu co robisz.\n\n"
    "LIMIT DŁUGOŚCI: cały post (nagłówek + treść + stopka) musi zmieścić się w wiadomości "
    "tekstowej Telegrama (max 4096 znaków). Celuj w MAX 3500 znaków. Jeśli materiału jest "
    "dużo — wybierz najważniejsze fakty zamiast wymieniać wszystko, zachowaj nagłówek i "
    "stopkę.\n\n"
    "Zawsze kończ dokładnie tą stopką, w osobnej linii, nic po niej:\n"
    "<b>Alert konsumencki</b> | @alertkonsumencki"
)

_MONTHS = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
]


def period_label(period: str) -> str:
    today = date.today()
    if period == "month":
        return f"{_MONTHS[today.month - 1]} {today.year}"
    return f"{today.year} (styczeń–{today.strftime('%d.%m')})"


def build_titles_index(records: list[dict]) -> str:
    """Zwięzła lista tytułów okresu — daty + oczyszczone tytuły, jedna linia na wpis."""
    lines = []
    for r in sorted(records, key=lambda x: x["date"], reverse=True):
        lines.append(f"- [{r['date']}] {strip_title_prefix(r['title'])}")
    return "\n".join(lines)


def build_records_blob(records: list[dict]) -> str:
    lines = []
    for r in records:
        snippet = (r.get("text") or "").strip().replace("\n", " ")[:600]
        lines.append(f"- [{r['date']}] {r['title']}\n  Fragment: {snippet}")
    return "\n\n".join(lines)


def build_stats_blob(records: list[dict]) -> str:
    """Pełny blob do promptów statystycznych: indeks tytułów + szczegóły."""
    titles_index = build_titles_index(records)
    return (
        f"LISTA TYTUŁÓW ({len(records)}):\n{titles_index}\n\n"
        f"SZCZEGÓŁY:\n{build_records_blob(records)}"
    )


_TITLES_HINT = (
    " Na początku masz LISTĘ TYTUŁÓW jako indeks skali i zakresu — korzystaj z niej "
    "do liczb i orientacji; szczegółowe fakty bierz z sekcji SZCZEGÓŁY poniżej."
)


def _instruction_summary(label: str, count: int) -> str:
    return (
        f"Napisz angażujące PODSUMOWANIE OGÓLNE ostrzeżeń GIS za okres: {label}. "
        f"W tym okresie było ich łącznie {count}. Zacznij mocnym hookiem, wspomnij skalę "
        "problemu i 2-3 najciekawsze/najważniejsze przypadki z listy poniżej, zakończ "
        "zachętą do obserwowania kanału. Korzystaj WYŁĄCZNIE z danych podanych poniżej — "
        "nie zmyślaj liczb ani faktów spoza listy." + _TITLES_HINT
    )


def _instruction_categories(label: str) -> str:
    return (
        f"Na podstawie listy ostrzeżeń GIS za okres: {label} (poniżej), pogrupuj je wg "
        "RODZAJU ZAGROŻENIA (np. bakterie: Listeria/Salmonella, alergeny, zanieczyszczenia "
        "chemiczne/metale, ciała obce, inne) i napisz angażujący post pokazujący, jaki typ "
        "zagrożenia dominował w tym okresie i dlaczego to ważne dla czytelnika. Liczby w "
        "każdej kategorii policz sam na podstawie listy poniżej — nie zmyślaj." + _TITLES_HINT
    )


def _instruction_brands(label: str) -> str:
    return (
        f"Na podstawie listy ostrzeżeń GIS za okres: {label} (poniżej), wskaż, którzy "
        "producenci/marki pojawiali się najczęściej (o ile da się to ustalić z treści). "
        "Napisz angażujący, ale rzeczowy post — bez oskarżycielskiego tonu. Jeśli w danych "
        "nie widać jednoznacznie powtarzających się marek, napisz to wprost i skup się na "
        "ogólnym obrazie (ile różnych producentów, jakie kategorie produktów). Nie zmyślaj "
        "nazw, których nie ma w danych." + _TITLES_HINT
    )


def _instruction_notable(label: str) -> str:
    return (
        f"Z listy ostrzeżeń GIS za okres: {label} (poniżej) wybierz 3-5 NAJBARDZIEJ "
        "'klikalnych'/poważnych przypadków (największe ryzyko zdrowotne, najbardziej "
        "rozpoznawalne produkty, największa skala wycofania) i opisz je w formie chwytliwego "
        "wypunktowania z krótkim komentarzem do każdego. Korzystaj wyłącznie z podanych "
        "faktów — nie zmyślaj szczegółów." + _TITLES_HINT
    )


STATS_TYPE_LABELS = {
    "summary": "📊 Podsumowanie ogólne",
    "categories": "⚠️ Top zagrożenia",
    "brands": "🏷 Najczęstsze marki",
    "notable": "🔥 Najgłośniejsze przypadki",
    "titles": "📋 Lista tytułów",
}

_BUILDERS = {
    "summary": _instruction_summary,
    "categories": _instruction_categories,
    "brands": _instruction_brands,
    "notable": _instruction_notable,
}


def instruction_for(stat_type: str, label: str, count: int) -> str:
    if stat_type == "summary":
        return _instruction_summary(label, count)
    return _BUILDERS[stat_type](label)


# ─── Udostępnianie: TG zachowuje stopkę "Alert konsumencki | @alertkonsumencki"
# (dodaje ją STATS_SYSTEM_PROMPT); FB nie ma tego formatu, więc na Facebooka idzie
# bez niej — usuwana programowo, bez dodatkowego wywołania modelu.
_FOOTER_RE = re.compile(r"\n*<b>Alert konsumencki</b>\s*\|\s*@alertkonsumencki\s*$", re.I)


def strip_footer(text: str) -> str:
    return _FOOTER_RE.sub("", text).strip()


_ONLY_POST = " Zwróć wyłącznie gotowy post — bez komentarza i bez opisu, co robisz."

STATS_ADJUST_LABELS = {
    "formal": "Bardziej formalny",
    "informal": "Mniej formalny",
    "plain": "Plain (bez ikon)",
    "angel": "😇 Anioł (bez firm)",
}

STATS_ADJUST_INSTRUCTIONS = {
    "formal": (
        "Przeredaguj powyższe podsumowanie statystyczne bardziej formalnie i oficjalnie — "
        "ton rzeczowy, bez poufałości i bez clickbaitu. Zachowaj wszystkie liczby/fakty "
        "i stopkę." + _ONLY_POST
    ),
    "informal": (
        "Przeredaguj powyższe podsumowanie mniej formalnie — luźniej, bardziej przystępnie, "
        "jakbyś pisał do znajomych. Zachowaj wszystkie liczby/fakty i stopkę." + _ONLY_POST
    ),
    "plain": (
        "Przeredaguj powyższe podsumowanie na wersję PLAIN: usuń WSZYSTKIE emoji/ikony "
        "(także z ewentualnej stopki) i wszelkie marketingowe zabiegi (hooki, clickbait, "
        "wykrzykniki) — zostaw suchą, rzeczową listę faktów/liczb w prostej formie. "
        "Zachowaj wszystkie liczby i fakty oraz stopkę (samą treść stopki, bez emoji)."
        + _ONLY_POST
    ),
    "angel": (
        "Przeredaguj powyższe podsumowanie tak, aby NIE wskazywać żadnych konkretnych nazw "
        "firm/marek/producentów — zastąp je ogólnymi określeniami (np. 'jeden z producentów', "
        "'popularna marka z tej kategorii'). Zachowaj wszystkie liczby i fakty dotyczące "
        "samych zagrożeń — usuń wyłącznie identyfikację konkretnych podmiotów. Zachowaj "
        "stopkę." + _ONLY_POST
    ),
}

STATS_SHORTEN_LABELS = {
    "stats_short_20": "SKRÓĆ 20%",
    "stats_short_30": "SKRÓĆ 30%",
    "stats_short_50": "SKRÓĆ 50%",
    "stats_short_70": "SKRÓĆ 70%",
}

STATS_SHORTEN_INSTRUCTIONS = {
    key: (
        f"Skróć powyższe podsumowanie o około {pct}% (usuń mniej więcej {pct}% objętości "
        "tekstu). Zostaw najważniejsze liczby i fakty. Zachowaj stopkę." + _ONLY_POST
    )
    for key, pct in (("stats_short_20", 20), ("stats_short_30", 30), ("stats_short_50", 50), ("stats_short_70", 70))
}
