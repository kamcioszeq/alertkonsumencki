"""Pętla serwisu: start → zawsze zrzuć najnowsze ostrzeżenie (test), potem w interwale
sprawdzaj nowe, pobieraj szczegóły i zapisuj do katalogu jako .txt. Dużo logów."""
import asyncio
import logging
import os
import re
from datetime import datetime

import config
from core.article import fetch_article
from core import queue as handoff
from . import state as crawler_state
from .gis import Warning, fetch_listing

log = logging.getLogger("crawler")


def _safe_filename(w: Warning) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", w.slug.lower())[:80].strip("-")
    return f"{w.date.isoformat()}_{slug}.txt"


def dump_warning(w: Warning, text: str) -> str:
    os.makedirs(config.CRAWLER_OUTPUT_DIR, exist_ok=True)
    path = os.path.join(config.CRAWLER_OUTPUT_DIR, _safe_filename(w))
    content = (
        f"Tytuł: {w.title}\n"
        f"Data: {w.date_str}\n"
        f"URL: {w.url}\n"
        f"Pobrano: {datetime.now().isoformat(timespec='seconds')}\n"
        f"{'-' * 60}\n\n"
        f"{text}\n"
    )
    with open(path, "w") as f:
        f.write(content)
    return path


async def _process(w: Warning, *, notify: bool) -> None:
    log.info("Przetwarzam ostrzeżenie: %s (%s)", w.title, w.date_str)
    log.info("  → wchodzę w link: %s", w.url)
    try:
        art = await fetch_article(w.url)
    except Exception as e:
        log.error("  ✗ nie udało się pobrać szczegółów: %s", e)
        return
    text = art.get("text", "")
    path = dump_warning(w, text)
    log.info("  ✓ zapisano szczegóły (%d znaków) → %s", len(text), path)

    if notify:
        handoff.enqueue({
            "source": "GIS",
            "title": w.title,
            "date": w.date_str,
            "url": w.url,
            "text": text,
        })
        log.info("  → przekazano do kolejki Telegrama (%s)", config.QUEUE_DIR)


def _new_since(warnings: list[Warning], st: dict) -> list[Warning]:
    """Ostrzeżenia nowsze niż ostatnio widziane (od góry do markera). Puste, gdy brak stanu."""
    last_url = st.get("last_url")
    if not last_url:
        return []
    new: list[Warning] = []
    for w in warnings:
        if w.url == last_url:
            return new
        new.append(w)
    # markera nie ma już na liście — fallback po dacie
    last_date = st.get("last_date")
    if last_date:
        return [w for w in warnings if w.date.isoformat() > last_date]
    return new


async def run(force_latest: bool) -> None:
    """Jeden przebieg. force_latest=True (start) zawsze zrzuca najnowsze ostrzeżenie."""
    st = crawler_state.load()
    warnings = await fetch_listing()
    if not warnings:
        log.warning("Listing pusty lub nie udało się sparsować — pomijam.")
        return

    latest = warnings[0]
    log.info("Pobrano listing: %d ostrzeżeń, najnowsze: %s (%s)",
             len(warnings), latest.title, latest.date_str)

    new = list(reversed(_new_since(warnings, st)))  # od najstarszego z nowych
    # Nowe ostrzeżenia → do Telegrama. force_latest (start) dodatkowo zawsze zrzuca
    # najnowsze do .txt jako health-check, ale BEZ powiadamiania Telegrama.
    if new:
        log.info("Nowe ostrzeżenia do przetworzenia: %d.", len(new))
        for w in new:
            await _process(w, notify=True)
    else:
        log.info("Brak nowych ostrzeżeń (ostatnie widziane: %s).", st.get("last_title", "—"))

    if force_latest and latest not in new:
        log.info("Start serwisu: wysyłam najnowsze ostrzeżenie do Telegrama (dowód działania).")
        await _process(latest, notify=True)

    crawler_state.save(latest)
    log.info("Zaktualizowano stan (ostatnie: %s).", latest.date_str)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [crawler] %(levelname)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)  # bez szumu z każdego GET
    log.info("Serwis crawler GIS startuje. Interwał=%ds, katalog=%s, listing=%s",
             config.CRAWLER_INTERVAL, config.CRAWLER_OUTPUT_DIR, config.GIS_LISTING_URL)

    try:
        await run(force_latest=True)  # start: zawsze wyślij najnowsze do Telegrama (dowód działania)
    except Exception as e:
        log.exception("Błąd startowego przebiegu: %s", e)

    while True:
        log.info("Następne sprawdzenie za %ds…", config.CRAWLER_INTERVAL)
        await asyncio.sleep(config.CRAWLER_INTERVAL)
        try:
            await run(force_latest=False)
        except Exception as e:
            log.exception("Błąd podczas sprawdzania: %s", e)
