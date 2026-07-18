"""CSV / JSON store dla listy kąpielisk, ocen, update’ów i aktywnych alertów (30 dni)."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

from . import config

LIST_FIELDS = ["id", "name", "url", "active"]
OCENA_FIELDS = [
    "id", "name", "url", "ocena", "data_oceny", "nastepne_badanie",
    "ecoli", "enterokoki", "przyczyna", "sezon_od", "sezon_do",
    "adres", "powiat", "wojewodztwo", "akwen", "lokalizacja",
    "updated_at",
]
UPDATE_FIELDS = [
    "ts", "id", "name", "url", "ocena", "data_oceny", "ecoli", "enterokoki",
    "przyczyna", "reason", "prev_ocena", "prev_data_oceny", "lokalizacja", "kind",
]


def ensure_data_dir() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)


def _read_csv(path, fields: list[str]) -> list[dict[str, str]]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, fieldnames=None))


def _write_csv(path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    ensure_data_dir()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})


def _append_csv(path, fields: list[str], row: dict[str, Any]) -> None:
    ensure_data_dir()
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in fields})


# ── lista ────────────────────────────────────────────────────

def save_list(items: list[dict[str, str]]) -> None:
    _write_csv(config.LIST_CSV, LIST_FIELDS, items)


def load_list() -> list[dict[str, str]]:
    rows = _read_csv(config.LIST_CSV, LIST_FIELDS)
    return [r for r in rows if r.get("id")]


# ── cursor round-robin ───────────────────────────────────────

def load_cursor() -> dict:
    if not os.path.exists(config.CURSOR_JSON):
        return {"next_index": 0, "last_run": ""}
    with open(config.CURSOR_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_cursor(next_index: int, last_run: Optional[str] = None) -> None:
    ensure_data_dir()
    data = {
        "next_index": next_index,
        "last_run": last_run or datetime.now().isoformat(timespec="seconds"),
    }
    with open(config.CURSOR_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── oceny (current) ──────────────────────────────────────────

def load_oceny() -> dict[str, dict[str, str]]:
    """id → wiersz oceny."""
    rows = _read_csv(config.OCENY_CSV, OCENA_FIELDS)
    return {r["id"]: r for r in rows if r.get("id")}


def save_oceny(by_id: dict[str, dict[str, str]]) -> None:
    rows = sorted(by_id.values(), key=lambda r: r.get("id", ""))
    _write_csv(config.OCENY_CSV, OCENA_FIELDS, rows)


def upsert_ocena(new_row: dict[str, str], *, prev: Optional[dict[str, str]] = None) -> None:
    """Zapisz aktualną ocenę; jeśli była poprzednia z inną data_oceny — do history."""
    by_id = load_oceny()
    old = prev if prev is not None else by_id.get(new_row["id"])
    if old and old.get("data_oceny") and old.get("data_oceny") != new_row.get("data_oceny"):
        hist = dict(old)
        hist["archived_at"] = datetime.now().isoformat(timespec="seconds")
        _append_csv(
            config.HISTORY_CSV,
            OCENA_FIELDS + ["archived_at"],
            hist,
        )
    by_id[new_row["id"]] = new_row
    save_oceny(by_id)


# ── updates (dla /kapieliska) ────────────────────────────────

def append_update(row: dict[str, Any]) -> None:
    row = dict(row)
    row.setdefault("ts", datetime.now().isoformat(timespec="seconds"))
    row.setdefault("kind", "threat")
    _append_csv(config.UPDATES_CSV, UPDATE_FIELDS, row)


def recent_updates(limit: int = 5) -> list[dict[str, str]]:
    rows = _read_csv(config.UPDATES_CSV, UPDATE_FIELDS)
    if not rows:
        return []
    return list(reversed(rows[-limit:]))


def _parse_pl_date(s: str) -> datetime:
    """DD/MM/YYYY → datetime; invalid → epoch."""
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s[:19] if "T" in s else s, fmt)
        except ValueError:
            continue
    return datetime(1970, 1, 1)


def freshest_ocena() -> Optional[dict[str, str]]:
    """Najświeższa ocena: najpierw po data_oceny, potem updated_at.

    Preferuj zagrożenie, jeśli jest wśród top świeżości (ostatnie 14 dni ocen).
    """
    from .detect import is_threat

    rows = list(load_oceny().values())
    if not rows:
        return None

    def sort_key(r: dict) -> tuple:
        return (_parse_pl_date(r.get("data_oceny", "")), _parse_pl_date(r.get("updated_at", "")))

    rows.sort(key=sort_key, reverse=True)
    # Prefer threat among the freshest ~50 by assessment date
    top = rows[:50]
    for r in top:
        if is_threat(r):
            return r
    return rows[0]


# ── aktywne alerty (30 dni) ──────────────────────────────────

def _load_active_raw() -> dict[str, dict]:
    if not os.path.exists(config.ACTIVE_ALERTS_JSON):
        return {}
    try:
        with open(config.ACTIVE_ALERTS_JSON, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_active_raw(data: dict[str, dict]) -> None:
    ensure_data_dir()
    with open(config.ACTIVE_ALERTS_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def purge_expired_alerts(now: Optional[datetime] = None) -> int:
    """Usuń alerty starsze niż ACTIVE_ALERT_DAYS. Zwraca ile usunięto."""
    now = now or datetime.now()
    data = _load_active_raw()
    keep = {}
    removed = 0
    for kid, rec in data.items():
        exp = rec.get("expires_at") or ""
        try:
            exp_dt = datetime.fromisoformat(exp)
        except ValueError:
            removed += 1
            continue
        if exp_dt >= now:
            keep[kid] = rec
        else:
            removed += 1
    if removed:
        _save_active_raw(keep)
    return removed


def get_active_alert(kapielisko_id: str) -> Optional[dict]:
    purge_expired_alerts()
    return _load_active_raw().get(str(kapielisko_id))


def register_active_alert(
    row: dict,
    *,
    fb_post_id: str = "",
    opened_at: Optional[str] = None,
) -> dict:
    """Zapisz / odśwież aktywny alert na 30 dni (pod update statusu)."""
    purge_expired_alerts()
    data = _load_active_raw()
    now = datetime.now()
    opened = opened_at or now.isoformat(timespec="seconds")
    try:
        base = datetime.fromisoformat(opened)
    except ValueError:
        base = now
    expires = (base + timedelta(days=config.ACTIVE_ALERT_DAYS)).isoformat(timespec="seconds")
    kid = str(row.get("id", ""))
    prev = data.get(kid) or {}
    rec = {
        "id": kid,
        "name": row.get("name", prev.get("name", "")),
        "url": row.get("url", prev.get("url", "")),
        "lokalizacja": row.get("lokalizacja", prev.get("lokalizacja", "")),
        "ocena": row.get("ocena", ""),
        "data_oceny": row.get("data_oceny", ""),
        "fb_post_id": fb_post_id or prev.get("fb_post_id", ""),
        "opened_at": prev.get("opened_at") or opened,
        "expires_at": expires,
        "updated_at": now.isoformat(timespec="seconds"),
    }
    data[kid] = rec
    _save_active_raw(data)
    return rec


def set_active_fb_post(kapielisko_id: str, fb_post_id: str) -> None:
    data = _load_active_raw()
    kid = str(kapielisko_id)
    if kid not in data:
        return
    data[kid]["fb_post_id"] = fb_post_id
    data[kid]["updated_at"] = datetime.now().isoformat(timespec="seconds")
    _save_active_raw(data)


def list_active_alerts() -> list[dict]:
    purge_expired_alerts()
    return list(_load_active_raw().values())
