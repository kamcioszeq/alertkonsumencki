"""Banery alertów — klasyfikacja LLM + mapowanie na pliki w assets/nowe/."""
import os
import re
from typing import Optional, Tuple

import config

BANNER_DIR = "assets/nowe"

# Slug (ostatnia linia BANER: …) → plik w assets/nowe/
BANNER_FILES = {
    "listeria": "listeria.png",
    "salmonella": "salmonella.png",
    "niezadeklarowanygluten": "niezadeklarowanygluten.png",
    "alertalergika": "alertalergika.png",
    "nieuzywajtychnaczyn": "nieuzywajtychnaczyn.png",
    "slodycze": "słodycze.png",
    "produktznikazesklepu": "produktznikazesklepu.png",
    "niebpartproduktu": "niebpartproduktu.png",
    "sprawdzczymaszwdomu": "sprawdzczymaszwdomu.png",
}

DEFAULT_BANNER = "sprawdzczymaszwdomu"

_BANER_LINE = re.compile(r"^BANER:\s*(\S+)\s*$", re.IGNORECASE)
# Stare posty / edycje mogą mieć jeszcze KATEGORIA: — ignorujemy slug, mapujemy na domyślny.
_LEGACY_CATEGORY_LINE = re.compile(r"^KATEGORIA:\s*(\S+)\s*$", re.IGNORECASE)

BANNER_CLASSIFICATION_PROMPT = (
    "\n"
    "KLASYFIKACJA BANERA — na SAMYM KOŃCU odpowiedzi (ostatnia linia, po stopce) dodaj dokładnie jedną linię:\n"
    "BANER: [nazwa]\n"
    "Wybierz JEDEN baner pasujący do GŁÓWNEGO zagrożenia (priorytet od góry — pierwsze pasujące):\n"
    "• listeria — wykryto Listerię / Listeria monocytogenes\n"
    "• salmonella — wykryto Salmonellę / salmonella\n"
    "• niezadeklarowanygluten — gluten niezadeklarowany na etykiecie, ryzyko dla osób z celiakią\n"
    "• alertalergika — inne alergeny (orzechy, mleko, soja, jaja, seler itd.), niebezpieczne dla alergików\n"
    "• nieuzywajtychnaczyn — garnki, patelnie, talerze, szklanki, naczynia; migracja metali/chemii z opakowania\n"
    "• slodycze — wycofanie słodyczy: czekolada, baton, ciastka, lody, cukierki\n"
    "• produktznikazesklepu — wycofanie produktu spożywczego ze sklepów (recall), gdy nie pasuje slodycze\n"
    "• niebpartproduktu — niebezpieczna partia (chemia, ciało obce, inna mikrobiologia niż listeria/salmonella)\n"
    "• sprawdzczymaszwdomu — gdy nic powyżej nie pasuje (suplementy, kosmetyki, leki, ogólne ostrzeżenia)\n"
    "Ta linia służy tylko do wyboru grafiki — zostanie usunięta przed publikacją. "
    "Użyj wyłącznie jednej z podanych nazw (bez .png)."
)


def default_banner_path() -> str:
    return banner_path(DEFAULT_BANNER)


def extract_banner(text: str) -> Tuple[str, Optional[str]]:
    """Zwraca (tekst bez linii BANER/KATEGORIA, slug lub None)."""
    text = (text or "").strip()
    if not text:
        return text, None
    lines = text.split("\n")
    last = lines[-1].strip()
    m = _BANER_LINE.match(last)
    if m:
        slug = m.group(1).lower().removesuffix(".png")
        body = "\n".join(lines[:-1]).rstrip()
        return body, slug
    if _LEGACY_CATEGORY_LINE.match(last):
        body = "\n".join(lines[:-1]).rstrip()
        return body, None
    return text, None


# Alias dla kompatybilności wewnętrznej
extract_category = extract_banner


def banner_path(slug: Optional[str]) -> str:
    """Ścieżka do banera; nieznany slug → domyślny baner."""
    key = (slug or "").lower().strip().removesuffix(".png")
    if not key or key not in BANNER_FILES:
        key = DEFAULT_BANNER
    filename = BANNER_FILES[key]
    path = os.path.join(BANNER_DIR, filename)
    if os.path.exists(path):
        return path
    fallback = os.path.join(BANNER_DIR, BANNER_FILES[DEFAULT_BANNER])
    return fallback if os.path.exists(fallback) else config.ALERT_IMAGE


def apply_banner_from_llm(text: str, *, fallback: Optional[str] = None) -> Tuple[str, str]:
    """Usuń linię BANER i zwróć (czysty tekst, ścieżka banera)."""
    clean, slug = extract_banner(text)
    if slug is None:
        fb = fallback or default_banner_path()
        return clean, fb if os.path.exists(fb) else default_banner_path()
    return clean, banner_path(slug)
