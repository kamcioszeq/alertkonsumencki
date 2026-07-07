"""Prompty do generowania marketingowych podsumowań statystycznych (Facebook/Telegram)."""
from datetime import date

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


def build_records_blob(records: list[dict]) -> str:
    lines = []
    for r in records:
        snippet = (r.get("text") or "").strip().replace("\n", " ")[:600]
        lines.append(f"- [{r['date']}] {r['title']}\n  Fragment: {snippet}")
    return "\n\n".join(lines)


def _instruction_summary(label: str, count: int) -> str:
    return (
        f"Napisz angażujące PODSUMOWANIE OGÓLNE ostrzeżeń GIS za okres: {label}. "
        f"W tym okresie było ich łącznie {count}. Zacznij mocnym hookiem, wspomnij skalę "
        "problemu i 2-3 najciekawsze/najważniejsze przypadki z listy poniżej, zakończ "
        "zachętą do obserwowania kanału. Korzystaj WYŁĄCZNIE z danych podanych poniżej — "
        "nie zmyślaj liczb ani faktów spoza listy."
    )


def _instruction_categories(label: str) -> str:
    return (
        f"Na podstawie listy ostrzeżeń GIS za okres: {label} (poniżej), pogrupuj je wg "
        "RODZAJU ZAGROŻENIA (np. bakterie: Listeria/Salmonella, alergeny, zanieczyszczenia "
        "chemiczne/metale, ciała obce, inne) i napisz angażujący post pokazujący, jaki typ "
        "zagrożenia dominował w tym okresie i dlaczego to ważne dla czytelnika. Liczby w "
        "każdej kategorii policz sam na podstawie listy poniżej — nie zmyślaj."
    )


def _instruction_brands(label: str) -> str:
    return (
        f"Na podstawie listy ostrzeżeń GIS za okres: {label} (poniżej), wskaż, którzy "
        "producenci/marki pojawiali się najczęściej (o ile da się to ustalić z treści). "
        "Napisz angażujący, ale rzeczowy post — bez oskarżycielskiego tonu. Jeśli w danych "
        "nie widać jednoznacznie powtarzających się marek, napisz to wprost i skup się na "
        "ogólnym obrazie (ile różnych producentów, jakie kategorie produktów). Nie zmyślaj "
        "nazw, których nie ma w danych."
    )


def _instruction_notable(label: str) -> str:
    return (
        f"Z listy ostrzeżeń GIS za okres: {label} (poniżej) wybierz 3-5 NAJBARDZIEJ "
        "'klikalnych'/poważnych przypadków (największe ryzyko zdrowotne, najbardziej "
        "rozpoznawalne produkty, największa skala wycofania) i opisz je w formie chwytliwego "
        "wypunktowania z krótkim komentarzem do każdego. Korzystaj wyłącznie z podanych "
        "faktów — nie zmyślaj szczegółów."
    )


STATS_TYPE_LABELS = {
    "summary": "📊 Podsumowanie ogólne",
    "categories": "⚠️ Top zagrożenia",
    "brands": "🏷 Najczęstsze marki",
    "notable": "🔥 Najgłośniejsze przypadki",
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
