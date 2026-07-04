"""Trwały stan crawlera: ostatnie widziane ostrzeżenie (URL + data + temat),
żeby nie pomijać ani nie dublować wpisów między sprawdzeniami."""
import json

import config


def load() -> dict:
    try:
        with open(config.CRAWLER_STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(last) -> None:
    data = {
        "last_url": last.url,
        "last_date": last.date.isoformat(),
        "last_title": last.title,
    }
    with open(config.CRAWLER_STATE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
