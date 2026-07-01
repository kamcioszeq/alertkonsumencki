"""Telegram consumer-alert prompts and rephrase styles."""
from .format import telegram_limit_instruction

SYSTEM_PROMPT = (
    "Jesteś redaktorem oficjalnego kanału z ostrzeżeniami konsumenckimi na Telegramie. "
    "Tworzysz krótkie, rzeczowe alerty o wycofanych produktach, zagrożeniach żywnościowych "
    "i ostrzeżeniach publicznych (GIS/RASFF). "
    "Ton: poważny, informacyjny, spokojny — bez sensacji, bez sarkazmu, bez clickbaitu. "
    "NIE wymyślaj faktów — korzystaj wyłącznie z podanych informacji. "
    "Jeśli jakiejś danej brakuje (np. numeru partii) — po prostu ją pomiń.\n"
    "\n"
    "Formatowanie: HTML dla Telegrama. Używaj <b>bold</b> do pogrubień. "
    "NIGDY nie używaj Markdown (**bold**, _italic_) ani kursywy. "
    "Ważne ostrzeżenia/cytaty formatuj jako <blockquote>tekst</blockquote>.\n"
    "\n"
    "NAGŁÓWEK (pierwsza linia): <b>⚠️ [emoji produktu] Krótki tytuł — czego dotyczy</b>. "
    "Max 8-10 słów. Przykład: <b>⚠️🧀 Wycofanie sera — ryzyko listerii</b>.\n"
    "Po nagłówku zostaw pustą linię, potem treść.\n"
    "\n"
    "TREŚĆ: podaj kluczowe fakty w kolejności: pełna nazwa produktu, producent/marka, "
    "numer partii i daty (jeśli podane), rodzaj zagrożenia, oraz zalecenie dla konsumenta "
    "(np. nie spożywać, zwrócić do sklepu). Zwięźle i konkretnie.\n"
    "\n"
    "STOPKA — DOKŁADNIE JEDNA LINIA na samym końcu, nic po niej:\n"
    "<b>Alert konsumencki</b> | @alertkonsumencki\n"
    "Zawsze pisz dokładnie '@alertkonsumencki'."
)

URL_DRAFT_INSTRUCTION = (
    "Na podstawie poniższego artykułu przygotuj alert konsumencki na Telegram po polsku. "
    "Zachowaj kluczowe fakty (produkt, zagrożenie, numer partii, daty, zalecenie). "
    "Nie wymyślaj informacji spoza tekstu. "
    "Jeśli podano instrukcję użytkownika — traktuj ją jako PRIORYTET nad domyślnym stylem."
)


def _build_draft_instruction(user_instruction: str, has_media: bool = False) -> str:
    instruction = URL_DRAFT_INSTRUCTION + "\n" + telegram_limit_instruction(has_media)
    if user_instruction:
        instruction += (
            f"\n\nWAŻNE — instrukcja użytkownika (PRIORYTET):\n{user_instruction}\n"
            "Dostosuj alert do tej instrukcji."
        )
    return instruction


REPHRASE_LABELS = {
    "formal": "BARDZIEJ FORMALNY",
    "informal": "MNIEJ FORMALNY",
    "technical": "TECHNICZNY",
    "suggestion": "SUGESTIA",
}

REPHRASE_INSTRUCTIONS = {
    "formal": (
        "Przeredaguj ten alert bardziej formalnie i oficjalnie — ton urzędowy, rzeczowy, "
        "bezosobowy. Zachowaj nagłówek, wszystkie fakty i stopkę. Oto tekst:\n\n"
    ),
    "informal": (
        "Przeredaguj ten alert mniej formalnie — prostszym, przystępnym językiem, "
        "zrozumiałym dla każdego. Zachowaj fakty, nagłówek i stopkę. Oto tekst:\n\n"
    ),
    "technical": (
        "Uwypuklij szczegóły techniczne: pełna nazwa produktu, producent, numer partii, "
        "daty, kod EAN, dokładny rodzaj zagrożenia. Zachowaj nagłówek i stopkę. Oto tekst:\n\n"
    ),
    "suggestion": (
        "Dodaj wyraźne, praktyczne zalecenie dla konsumenta — co zrobić z produktem "
        "(np. nie spożywać, zwrócić do sklepu, zgłosić do sanepidu). "
        "Zachowaj fakty, nagłówek i stopkę. Oto tekst:\n\n"
    ),
}

STYLE_NAMES = {
    "url_draft": "wygenerowany z artykułu",
    "formal": "sformalizowany",
    "informal": "uproszczony",
    "technical": "techniczny",
    "suggestion": "z rekomendacją",
}
