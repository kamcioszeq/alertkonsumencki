"""Banery kategorii produktów — klasyfikacja LLM + mapowanie na pliki w assets/."""
import os
import re
from typing import Optional, Tuple

import config

# Slug (ostatnia linia KATEGORIA: …) → plik w assets/
CATEGORY_BANNERS = {
    "cukierislodycze": "cukierislodycze.png",
    "garnki": "garnki.png",
    "miesarybyiinneodzwierzece": "miesarybyiinneodzwierzece.png",
    "mlekoiprzetworymleczne": "mlekoiprzetworymleczne.png",
    "owoceiwarzywa": "owoceiwarzywa.png",
    "produktyzbozowe": "Produkty zbożowe.png",
    "talerzeiprzyborykuchenne": "talerzeiprzyborykuchenne.png",
    "tluszczeioleje": "tluszczeioleje.png",
}

DEFAULT_BANNER = "alert"

_CATEGORY_LINE = re.compile(r"^KATEGORIA:\s*(\S+)\s*$", re.IGNORECASE)

BANNER_CLASSIFICATION_PROMPT = (
    "\n"
    "KLASYFIKACJA BANERA — na SAMYM KOŃCU odpowiedzi (ostatnia linia, po stopce) dodaj dokładnie jedną linię:\n"
    "KATEGORIA: [nazwa]\n"
    "Wybierz baner pasujący do GŁÓWNEGO produktu ostrzeżenia:\n"
    "• produktyzbozowe — pieczywo, mąka, chleb, kasze, płatki, makaron, produkty zbożowe, gluten\n"
    "• miesarybyiinneodzwierzece — mięso, wędliny, ryby, owoce morza, jaja, drób, dania gotowe z mięsem (bigos, zupa), karma dla zwierząt\n"
    "• cukierislodycze — cukier, słodycze, herbatniki, ciastka, batoniki, czekolada, lody, przekąski słodkie\n"
    "• mlekoiprzetworymleczne — mleko, ser, jogurt, maślanka, śmietana, nabiał\n"
    "• owoceiwarzywa — warzywa, owoce, soki, sałatki warzywne/owocowe, mrożonki owocowo-warzywne\n"
    "• tluszczeioleje — oleje, oliwa, masło, margaryna, tłuszcze\n"
    "• garnki — garnki, patelnie, rondle, naczynia do gotowania (kontakt z żywnością)\n"
    "• talerzeiprzyborykuchenne — talerze, szklanki, sztućce, pojemniki, wyroby stołowe (kontakt z żywnością)\n"
    "• alert — gdy nic nie pasuje (suplementy, kosmetyki, leki, elektronika itp.)\n"
    "Ta linia służy tylko do wyboru grafiki — zostanie usunięta przed publikacją. "
    "Użyj wyłącznie jednej z podanych nazw (bez .png)."
)


def extract_category(text: str) -> Tuple[str, Optional[str]]:
    """Zwraca (tekst bez linii KATEGORIA, slug lub None)."""
    text = (text or "").strip()
    if not text:
        return text, None
    lines = text.split("\n")
    last = lines[-1].strip()
    m = _CATEGORY_LINE.match(last)
    if not m:
        return text, None
    slug = m.group(1).lower().removesuffix(".png")
    body = "\n".join(lines[:-1]).rstrip()
    return body, slug


def banner_path(category: Optional[str]) -> str:
    """Ścieżka do banera; nieznana kategoria → alert.png."""
    slug = (category or "").lower().strip().removesuffix(".png")
    if slug == DEFAULT_BANNER or not slug:
        return config.ALERT_IMAGE
    filename = CATEGORY_BANNERS.get(slug)
    if not filename:
        return config.ALERT_IMAGE
    path = os.path.join("assets", filename)
    return path if os.path.exists(path) else config.ALERT_IMAGE


def apply_banner_from_llm(text: str, *, fallback: Optional[str] = None) -> Tuple[str, str]:
    """Usuń linię KATEGORIA i zwróć (czysty tekst, ścieżka banera)."""
    clean, cat = extract_category(text)
    if cat is None:
        fb = fallback or config.ALERT_IMAGE
        return clean, fb if os.path.exists(fb) else config.ALERT_IMAGE
    return clean, banner_path(cat)
