"""Wykrywanie powtórek alertów GIS w bieżącym miesiącu (bakteria / produkt)."""
import re

_BACTERIA_PATTERNS = [
    (re.compile(r"listeria\s+monocytogenes", re.I), "Listeria monocytogenes"),
    (re.compile(r"\blisteria\b", re.I), "Listeria"),
    (re.compile(r"\bsalmonella\b", re.I), "Salmonella"),
    (re.compile(r"e\.?\s*coli", re.I), "E. coli"),
    (re.compile(r"pałecz(?:ka|ki)\s+(?:gr(?:-| )?ujemna|aeruginosa)", re.I), "pałeczka"),
    (re.compile(r"\bclostridium\b", re.I), "Clostridium"),
    (re.compile(r"\bcampylobacter\b", re.I), "Campylobacter"),
    (re.compile(r"\bstaphylococcus\b", re.I), "Staphylococcus"),
    (re.compile(r"bakter(?:i|ii|ie)\s", re.I), "bakterie"),
    (re.compile(r"mikrobiologiczn", re.I), "skażenie mikrobiologiczne"),
]


def _extract_bacteria(text: str) -> list[str]:
    found = []
    for pattern, label in _BACTERIA_PATTERNS:
        if pattern.search(text or "") and label not in found:
            found.append(label)
    return found


def _normalize_product_key(text: str) -> str:
    """Prosty klucz produktu z tytułu/treści GIS."""
    t = (text or "").lower()
    t = re.sub(
        r"^(aktualizacja\s+ostrzeżenia\s+publicznego|ostrzeżenie\s+publiczne)\s*",
        "",
        t,
        flags=re.I,
    )
    if ":" in t:
        t = t.split(":", 1)[1]
    t = re.sub(r"\s+", " ", t).strip()
    # Usuń ogólne słowa, zostaw rdzeń (max 80 znaków)
    t = re.sub(r"\b(dotyczące|dotyczy|żywności|produktu)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()[:80]
    return t


def _record_text(record: dict) -> str:
    return f"{record.get('title', '')}\n{record.get('text', '')}"


def _same_source(current_url: str, record: dict) -> bool:
    if not current_url:
        return False
    return (record.get("url") or "").rstrip("/") == current_url.rstrip("/")


async def detect_repeat(
    article_text: str,
    *,
    source_url: str = "",
    title: str = "",
) -> dict:
    """Sprawdza powtórki w archiwum bieżącego miesiąca. Bez wywołań LLM."""
    from stats.gis_archive import fetch_period

    combined = f"{title}\n{article_text}".strip()
    bacteria = _extract_bacteria(combined)
    product_key = _normalize_product_key(title or article_text[:200])

    try:
        records = await fetch_period("month")
    except Exception as e:
        print(f"[REPEAT] fetch_period failed: {e}")
        return {"is_repeat": False, "repeat_type": None}

    prior_bacteria_dates: list[str] = []
    prior_product_dates: list[str] = []
    matched_bacteria: list[str] = []
    matched_product = ""

    for rec in records:
        if _same_source(source_url, rec):
            continue
        rec_text = _record_text(rec)
        rec_date = rec.get("date", "")

        if bacteria:
            rec_bacteria = _extract_bacteria(rec_text)
            overlap = [b for b in bacteria if b in rec_bacteria]
            if overlap:
                matched_bacteria = overlap
                prior_bacteria_dates.append(rec_date)

        if product_key and len(product_key) >= 8:
            rec_key = _normalize_product_key(rec.get("title", ""))
            if rec_key and (
                product_key in rec_key or rec_key in product_key
                or _fuzzy_overlap(product_key, rec_key)
            ):
                matched_product = (title or product_key)[:120]
                prior_product_dates.append(rec_date)

    if matched_bacteria and prior_bacteria_dates:
        return {
            "is_repeat": True,
            "repeat_type": "bacteria",
            "matched_bacteria": matched_bacteria,
            "matched_product": matched_product,
            "prior_dates": sorted(set(prior_bacteria_dates)),
        }

    if matched_product and prior_product_dates:
        return {
            "is_repeat": True,
            "repeat_type": "product",
            "matched_bacteria": [],
            "matched_product": matched_product,
            "prior_dates": sorted(set(prior_product_dates)),
        }

    return {"is_repeat": False, "repeat_type": None}


def _fuzzy_overlap(a: str, b: str) -> bool:
    """Czy dwa klucze produktu mają wspólny znaczący token (>=5 znaków)."""
    tokens_a = {t for t in re.split(r"[^\wąćęłńóśźż]+", a) if len(t) >= 5}
    tokens_b = {t for t in re.split(r"[^\wąćęłńóśźż]+", b) if len(t) >= 5}
    return bool(tokens_a & tokens_b)
