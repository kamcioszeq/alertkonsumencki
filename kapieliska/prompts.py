"""Teksty i prompty FB dla alertów kąpieliskowych.

FB publikujemy TYLKO przy zagrożeniu (woda niezdatna / progi bakterii).
Posty rotują naprzemiennie: styl A (dynamiczny) ↔ styl B (krótki alarm).
"""
from __future__ import annotations

import json
from typing import Optional

from . import config as kcfg

# ── Rotacja stylu posta (A / B) ──────────────────────────────

_STYLE_FILE = kcfg.DATA_DIR / "fb_style_rotation.json"


def next_kapieliska_fb_style() -> str:
    """Naprzemiennie «A» (dynamiczna) i «B» (krótka)."""
    last = "B"
    if _STYLE_FILE.exists():
        try:
            last = json.loads(_STYLE_FILE.read_text(encoding="utf-8")).get("last", "B")
        except (json.JSONDecodeError, OSError):
            last = "B"
    nxt = "A" if last == "B" else "B"
    try:
        kcfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _STYLE_FILE.write_text(json.dumps({"last": nxt}), encoding="utf-8")
    except OSError as e:
        print(f"[KAPIELISKA] style rotation save failed: {e}")
    return nxt


def kapieliska_generate_instruction(style: str | None = None) -> str:
    """Instrukcja generacji posta — style A/B naprzemiennie (lub wymuszony)."""
    s = (style or next_kapieliska_fb_style()).upper()
    return FB_KAPIELISKA_GENERATE_B if s == "B" else FB_KAPIELISKA_GENERATE_A


# ── Prompt FB (główny post) ──────────────────────────────────

FB_KAPIELISKA_SYSTEM_PROMPT = (
    "Jesteś redaktorem postów na Facebooku dla kanału Alert Konsumencki — "
    "alerty o jakości wody w kąpieliskach. "
    "Pisz PO POLSKU. Format: plain text (bez HTML, bez Markdown, bez linków w poście). "
    "Korzystaj wyłącznie z podanych informacji — nie wymyślaj danych.\n"
    "\n"
    "Masz DOKŁADNIE dwa warianty stylu. Użyj TYLKO tego, który poda instrukcja "
    "(STYL A albo STYL B). Nie mieszaj ich.\n"
    "\n"
    "═══ STYL A — dynamiczna i bezpośrednia ═══\n"
    "Struktura (puste linie między akapitami):\n"
    "1) Hook — jedna linia, emocjonalna, z miejscowością:\n"
    "   «🚨 Czerwona flaga w [miejscowość]! Nie wchodźcie do wody! 🛑»\n"
    "2) Ważna informacja — jeden akapit zaczynający się od:\n"
    "   «Ważna informacja dla plażowiczów:» + ocena GIS z datą + że woda jest niezdatna, "
    "z pełną lokalizacją w nawiasie (akwen, nazwa kąpieliska, miejscowość, adres).\n"
    "3) Powód — jedna linia:\n"
    "   «🦠 Powód: …» — jeśli w źródle jest Przyczyna (np. Zakwit sinic), użyj jej. "
    "Inaczej E. coli / enterokoki / zakwit — tylko jeśli jest w źródle.\n"
    "4) CTA — jedna linia, np.:\n"
    "   «Dbajcie o zdrowie, omijajcie dziś to kąpielisko i podajcie info dalej! 🔄»\n"
    "\n"
    "Przykład A:\n"
    "🚨 Czerwona flaga w Szczytnie! Nie wchodźcie do wody! 🛑\n"
    "\n"
    "Ważna informacja dla plażowiczów: ocena GIS z 15.07.2026 r. nie pozostawia złudzeń – "
    "woda w Jeziorze Domowym Dużym (Kąpielisko Domowe, Szczytno, Klenczon) jest niezdatna do kąpieli.\n"
    "\n"
    "🦠 Powód: Wykryto niebezpieczne przekroczenie norm E. coli.\n"
    "\n"
    "Dbajcie o zdrowie, omijajcie dziś to kąpielisko i podajcie info dalej! 🔄\n"
    "\n"
    "═══ STYL B — maksymalnie krótka i alarmująca ═══\n"
    "Struktura:\n"
    "1) Hook — jedna linia:\n"
    "   «🚫 PILNE: Zakaz kąpieli w [akwen] ([miejscowość])!»\n"
    "2) Treść — 2–3 zdania: «Plażowicze, uwaga!» + raport GIS z datą + bakterie + "
    "nazwa kąpieliska / adres + «woda jest niezdatna do kąpieli. ❌»\n"
    "3) CTA — jedna linia:\n"
    "   «Nie ryzykujcie zdrowia i stosujcie się do wytycznych sanepidu! ⚠️»\n"
    "\n"
    "Przykład B:\n"
    "🚫 PILNE: Zakaz kąpieli w Jeziorze Domowym Dużym (Szczytno)!\n"
    "\n"
    "Plażowicze, uwaga! Raport GIS z 15.07.2026 potwierdza przekroczenie norm bakterii E. coli. "
    "Kąpielisko Domowe (Klenczon) zostaje zamknięte do odwołania – woda jest niezdatna do kąpieli. ❌\n"
    "\n"
    "Nie ryzykujcie zdrowia i stosujcie się do wytycznych sanepidu! ⚠️\n"
    "\n"
    "OBOWIĄZKOWO w każdym stylu: lokalizacja (miejscowość + kąpielisko + akwen jeśli jest).\n"
    "NIE dodawaj stopki «Źródło:…» w poście głównym (źródło jest w komentarzu).\n"
    "NIE umieszczaj tabel badań — to idzie do komentarza.\n"
    "NIE klasyfikuj banera żywnościowego (BANER:)."
)

FB_KAPIELISKA_GENERATE_A = (
    "STYL A (obowiązkowy). Napisz POST GŁÓWNY według stylu A — dynamiczna i bezpośrednia "
    "(🚨 czerwona flaga + ważna informacja + 🦠 powód + CTA). Zwróć wyłącznie gotowy post."
)

FB_KAPIELISKA_GENERATE_B = (
    "STYL B (obowiązkowy). Napisz POST GŁÓWNY według stylu B — maksymalnie krótka i alarmująca "
    "(🚫 PILNE + treść + CTA). Zwróć wyłącznie gotowy post."
)

FB_KAPIELISKA_COMMENT_SYSTEM = (
    "Jesteś redaktorem komentarzy pod postami FB o kąpieliskach. "
    "Pisz PO POLSKU. Plain text. Tylko fakty ze źródła.\n"
    "\n"
    "STRUKTURA:\n"
    "📌 Szczegóły oceny wody:\n"
    "\n"
    "🏖️ Kąpielisko: [nazwa]\n"
    "📍 Lokalizacja: [adres / woj. / powiat / akwen — co jest w źródle]\n"
    "💧 Ocena: [tekst oceny]\n"
    "⚠️ Przyczyna: [np. Zakwit sinic] (pomiń, jeśli brak)\n"
    "📅 Data oceny: [DD.MM.RRRR]\n"
    "🔬 E. coli: [wartość] (pomiń, jeśli brak)\n"
    "🔬 Enterokoki: [wartość] (pomiń, jeśli brak)\n"
    "📅 Następne badanie: [data] (pomiń, jeśli brak)\n"
    "\n"
    "Źródło: GIS — Serwis Kąpieliskowy, sk.gis.gov.pl\n"
)

FB_KAPIELISKA_COMMENT_GENERATE = (
    "Na podstawie poniższego źródła napisz KOMENTARZ ze szczegółami oceny wody "
    "pod post FB o kąpielisku. Zwróć wyłącznie gotowy komentarz."
)

FB_KAPIELISKA_STATUS_COMMENT = (
    "Napisz KRÓTKI komentarz-UPDATE pod wcześniejszym postem o zagrożeniu w kąpielisku. "
    "Podaj nową ocenę wody, datę, lokalizację (jeśli jest) i czy kąpiel jest znowu dozwolona "
    "czy nadal nie. Zacznij od: «🔄 Update:». Zwróć wyłącznie tekst komentarza."
)


def build_alert_text(row: dict, decision: dict, prev: Optional[dict] = None) -> str:
    """Materiał źródłowy pod draft (TG/FB) — zawsze z lokalizacją."""
    prev = prev or {}
    loc = _format_location(row)
    lines = [
        "Alert jakości wody w kąpielisku (Serwis Kąpieliskowy GIS).",
        f"Kąpielisko: {row.get('name', '')}",
        f"Lokalizacja: {loc}" if loc else "Lokalizacja: (brak w źródle)",
        f"URL: {row.get('url', '')}",
        f"Ocena wody: {row.get('ocena', '')}",
        f"Przyczyna: {row.get('przyczyna', '')}" if row.get("przyczyna") else "",
        f"Data oceny: {row.get('data_oceny', '')}",
        f"Następne badanie: {row.get('nastepne_badanie', '')}",
        f"E. coli: {row.get('ecoli', '') or '—'} jtk/100 ml",
        f"Enterokoki: {row.get('enterokoki', '') or '—'} jtk/100 ml",
    ]
    lines = [ln for ln in lines if ln]
    if row.get("sezon_od"):
        lines.append(f"Sezon: {row.get('sezon_od')} – {row.get('sezon_do')}")
    if prev.get("ocena"):
        lines.append(
            f"Poprzednia ocena: {prev.get('ocena')} ({prev.get('data_oceny', '—')})"
        )
    if decision.get("reason"):
        lines.append(f"Powód alertu: {decision['reason']}")
    lines.append(
        "Źródło: Główny Inspektorat Sanitarny — Serwis Kąpieliskowy (sk.gis.gov.pl)."
    )
    return "\n".join(lines)


def build_status_update_text(row: dict, prev: dict, decision: dict) -> str:
    loc = _format_location(row)
    return "\n".join([
        "Zmiana statusu kąpieliska (wcześniej było zagrożenie).",
        f"Kąpielisko: {row.get('name', '')}",
        f"Lokalizacja: {loc}" if loc else "",
        f"URL: {row.get('url', '')}",
        f"Było: {prev.get('ocena', '—')} ({prev.get('data_oceny', '—')})",
        f"Jest: {row.get('ocena', '—')} ({row.get('data_oceny', '—')})",
        f"E. coli: {row.get('ecoli', '') or '—'} · Enterokoki: {row.get('enterokoki', '') or '—'}",
        f"Powód powiadomienia: {decision.get('reason', 'zmiana statusu')}",
        "Źródło: GIS — Serwis Kąpieliskowy.",
    ])


def _format_location(row: dict) -> str:
    if row.get("lokalizacja"):
        return row["lokalizacja"]
    parts = []
    for key in ("adres", "powiat", "wojewodztwo", "akwen"):
        v = (row.get(key) or "").strip()
        if v:
            if key == "powiat" and not v.lower().startswith("pow"):
                parts.append(f"pow. {v}")
            elif key == "wojewodztwo" and not v.lower().startswith("woj"):
                parts.append(f"woj. {v}")
            else:
                parts.append(v)
    return ", ".join(parts)


def is_kapieliska_source(source: str = "", text: str = "") -> bool:
    s = (source or "").upper()
    if "KĄPIELISK" in s or "KAPIELISK" in s:
        return True
    t = (text or "").lower()
    return "serwis kąpieliskowy" in t or "kąpielisko:" in t
