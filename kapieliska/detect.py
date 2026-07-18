"""Reguły: zagrożenie → FB; zmiana statusu przy aktywnym alercie → TG update."""
from __future__ import annotations

from typing import Optional

from . import config


def _is_bad(ocena: str) -> bool:
    o = (ocena or "").lower()
    return any(
        x in o
        for x in (
            "niezdatna",
            "zakaz",
            "przyczyna:",
            "nieprzydatna",
            "woda nie ",
        )
    )


def _is_ok(ocena: str) -> bool:
    o = (ocena or "").lower()
    return "przydatna" in o and "niezdatna" not in o and "nieprzydatna" not in o


def _to_int(val: str) -> Optional[int]:
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return None


def _ignore_noise(ocena: str) -> bool:
    oc = (ocena or "").lower()
    if "brak" in oc and "badań" in oc:
        return True
    if "zamknię" in oc:
        return True
    return False


def is_threat(row: dict) -> bool:
    """Czy aktualna ocena to zagrożenie (kandydat do posta FB)."""
    if _ignore_noise(row.get("ocena", "")):
        return False
    if _is_bad(row.get("ocena", "")):
        return True
    ecoli = _to_int(row.get("ecoli", ""))
    enter = _to_int(row.get("enterokoki", ""))
    if ecoli is not None and ecoli > config.ECOLI_LIMIT:
        return True
    if enter is not None and enter > config.ENTEROKOKI_LIMIT:
        return True
    return False


def evaluate_change(prev: Optional[dict], new: dict) -> dict:
    """Zwraca:
    - is_new_assessment: zmieniła się data/ocena
    - should_alert: zagrożenie → propozycja posta FB (tylko threat)
    - should_status_notify: zmiana przy śledzonym alercie (30 dni) → TG + update komentarza
    """
    if not new.get("data_oceny") and not new.get("ocena"):
        return {
            "is_new_assessment": False,
            "should_alert": False,
            "should_status_notify": False,
            "reason": "",
        }

    if not prev:
        return {
            "is_new_assessment": False,
            "should_alert": False,
            "should_status_notify": False,
            "reason": "baseline",
        }

    same_date = (prev.get("data_oceny") or "") == (new.get("data_oceny") or "")
    same_ocena = (prev.get("ocena") or "") == (new.get("ocena") or "")
    if same_date and same_ocena:
        return {
            "is_new_assessment": False,
            "should_alert": False,
            "should_status_notify": False,
            "reason": "",
        }

    is_new = not same_date or not same_ocena
    reasons: list[str] = []

    if _is_ok(prev.get("ocena", "")) and _is_bad(new.get("ocena", "")):
        reasons.append("zmiana: przydatna → niezdatna")
    elif _is_bad(new.get("ocena", "")):
        reasons.append(f"ocena: {new.get('ocena', '')}")
    elif _is_bad(prev.get("ocena", "")) and _is_ok(new.get("ocena", "")):
        reasons.append("zmiana: niezdatna → przydatna")
    elif not same_ocena:
        reasons.append(f"zmiana oceny: {prev.get('ocena', '—')} → {new.get('ocena', '—')}")

    ecoli = _to_int(new.get("ecoli", ""))
    enter = _to_int(new.get("enterokoki", ""))
    if ecoli is not None and ecoli > config.ECOLI_LIMIT:
        reasons.append(f"E. coli={ecoli} > {config.ECOLI_LIMIT}")
    if enter is not None and enter > config.ENTEROKOKI_LIMIT:
        reasons.append(f"enterokoki={enter} > {config.ENTEROKOKI_LIMIT}")
    if (new.get("przyczyna") or "").strip():
        reasons.append(f"przyczyna: {new['przyczyna'].strip()}")

    should_alert = is_new and is_threat(new)
    # Status notify: zmiana oceny gdy mamy aktywny alert (poller sprawdzi active_alerts)
    should_status_notify = is_new and bool(reasons)

    return {
        "is_new_assessment": is_new,
        "should_alert": should_alert,
        "should_status_notify": should_status_notify,
        "reason": "; ".join(reasons),
        "is_threat": is_threat(new),
        "was_threat": is_threat(prev) if prev else False,
    }
