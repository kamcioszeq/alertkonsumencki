"""Naprzemienna rotacja ikon ⚠️ / 🚨 w hookach alertów."""
import json
import os

_ROTATION_FILE = os.getenv("ICON_ROTATION_FILE", "icon_rotation.json")


def _load() -> str:
    if not os.path.exists(_ROTATION_FILE):
        return "⚠️"
    try:
        with open(_ROTATION_FILE) as f:
            data = json.load(f)
        last = data.get("last", "⚠️")
        return "🚨" if last == "⚠️" else "⚠️"
    except (json.JSONDecodeError, OSError):
        return "⚠️"


def _save(icon: str) -> None:
    try:
        with open(_ROTATION_FILE, "w") as f:
            json.dump({"last": icon}, f)
    except OSError as e:
        print(f"[ICON_ROTATION] save failed: {e}")


def next_warning_icon() -> str:
    """Zwraca następną ikonę ostrzeżenia i zapisuje stan."""
    icon = _load()
    _save(icon)
    return icon
