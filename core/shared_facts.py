"""Opcjonalny cache faktów alertu keyed by phase1_msg_id (przyspiesza cross-platform gen)."""
import json
import os

FACTS_DIR = os.getenv("SHARED_FACTS_DIR", "shared_facts")


def _path(phase1_msg_id: int) -> str:
    return os.path.join(FACTS_DIR, f"{phase1_msg_id}.json")


def load(phase1_msg_id: int) -> dict | None:
    path = _path(phase1_msg_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save(phase1_msg_id: int, data: dict) -> None:
    os.makedirs(FACTS_DIR, exist_ok=True)
    payload = dict(data)
    payload["phase1_msg_id"] = phase1_msg_id
    try:
        with open(_path(phase1_msg_id), "w") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[SHARED_FACTS] save failed: {e}")


def merge(phase1_msg_id: int, **fields) -> dict:
    """Wczytaj istniejące i nadpisz podanymi polami; zapisz i zwróć."""
    current = load(phase1_msg_id) or {}
    current.update({k: v for k, v in fields.items() if v is not None})
    save(phase1_msg_id, current)
    return current


def delete(phase1_msg_id: int) -> None:
    path = _path(phase1_msg_id)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as e:
        print(f"[SHARED_FACTS] delete failed: {e}")
