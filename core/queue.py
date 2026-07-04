"""Plikowa kolejka handoff: crawler → bot Telegram.

Crawler zapisuje nowe ostrzeżenia jako pliki .json (atomowo), bot je odczytuje,
ingestuje i usuwa. Prosty, odporny na restart, działa też przez współdzielony wolumen
między osobnymi kontenerami.
"""
import json
import os
import time
import uuid

import config


def enqueue(item: dict) -> str:
    os.makedirs(config.QUEUE_DIR, exist_ok=True)
    name = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.json"
    path = os.path.join(config.QUEUE_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(item, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomowo — czytelnik nigdy nie zobaczy połowicznego pliku
    return path


def pending_files() -> list[str]:
    d = config.QUEUE_DIR
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f) for f in os.listdir(d) if f.endswith(".json")
    )


def read(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def remove(path: str) -> None:
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
