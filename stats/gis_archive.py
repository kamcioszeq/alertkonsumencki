"""Pełna, historyczna lista ostrzeżeń GIS (paginowany listing) dla danego okresu
(bieżący miesiąc / rok od 1 stycznia — YTD), z cache'owaniem treści artykułów na dysku.

Listing (https://www.gov.pl/web/gis/ostrzezenia) jest posortowany od najnowszych —
więc dla zapytania o okres wystarczy iść stronami aż natrafimy na wpis starszy niż
początek okresu, zamiast zawsze ściągać wszystkie ~33 strony.

Każde ostrzeżenie, którego treść już raz pobraliśmy, ląduje jako plik .json w
gis_alerts/archive/ — kolejne wywołania /stats dociągają tylko to, czego tam jeszcze nie ma.
"""
import hashlib
import json
import os
import re
from datetime import date

import httpx

import config
from core.article import fetch_article
from crawler.gis import Warning, parse_listing, FETCH_HEADERS

ARCHIVE_DIR = "gis_alerts/archive"


def _period_start(period: str) -> date:
    today = date.today()
    if period == "month":
        return today.replace(day=1)
    if period == "year":
        return today.replace(month=1, day=1)
    raise ValueError(f"Nieznany okres: {period!r}")


def _cache_path(w: Warning) -> str:
    """Nazwa pliku cache dla jednego ostrzeżenia. Slug (z tytułu) ucinamy do 80
    znaków dla czytelności, ale dwa różne ostrzeżenia z tego samego dnia mogą mieć
    identyczny obcięty slug (np. warianty "200 g"/"100 g" tego samego produktu) —
    stąd dopisany krótki hash pełnego URL-a, żeby nazwy plików nigdy się nie zderzyły."""
    slug = re.sub(r"[^a-z0-9-]+", "-", w.slug.lower())[:80].strip("-")
    url_hash = hashlib.sha1(w.url.encode()).hexdigest()[:8]
    return os.path.join(ARCHIVE_DIR, f"{w.date.isoformat()}_{slug}-{url_hash}.json")


async def _fetch_page(client: httpx.AsyncClient, page: int) -> list[Warning]:
    url = config.GIS_LISTING_URL if page <= 1 else f"{config.GIS_LISTING_URL}?page={page}"
    r = await client.get(url)
    r.raise_for_status()
    return parse_listing(r.text)


async def _warnings_since(min_date: date) -> list[Warning]:
    """Idzie stronami listingu (najnowsze first) aż CAŁA strona spadnie poniżej min_date.

    Listing GIS nie zawsze jest ściśle malejący chronologicznie — zdarzają się
    pojedyncze błędnie wpisane daty (np. literówka roku na stronie rządowej),
    które potrafią wypaść między dwoma nowszymi wpisami. Zatrzymywanie się na
    PIERWSZYM wpisie poniżej progu ucinało wtedy resztę prawdziwie nowszych
    wpisów za tą anomalią — dlatego próg sprawdzamy dopiero po przetworzeniu
    całej strony."""
    out: list[Warning] = []
    seen_urls: set[str] = set()
    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=FETCH_HEADERS) as client:
        page = 1
        while True:
            warnings = await _fetch_page(client, page)
            new_on_page = [w for w in warnings if w.url not in seen_urls]
            if not new_on_page:
                break  # strona pusta albo witryna zaczęła powtarzać ostatnią (koniec listy)
            for w in new_on_page:
                seen_urls.add(w.url)
                if w.date >= min_date:
                    out.append(w)
            if all(w.date < min_date for w in new_on_page):
                break
            page += 1
    return out


def _load_cached(w: Warning) -> dict | None:
    path = _cache_path(w)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(w: Warning, text: str) -> dict:
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    record = {"date": w.date.isoformat(), "title": w.title, "url": w.url, "text": text}
    with open(_cache_path(w), "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


async def fetch_period(period: str) -> list[dict]:
    """Zwraca [{date, title, url, text}, ...] dla ostrzeżeń GIS w danym okresie
    ('month' = bieżący miesiąc, 'year' = YTD), najstarsze na końcu.
    Treść artykułów już widzianych wcześniej pochodzi z cache — dociąga się
    tylko te ostrzeżenia, których jeszcze nie ma w gis_alerts/archive/."""
    min_date = _period_start(period)
    warnings = await _warnings_since(min_date)
    records = []
    for w in warnings:
        cached = _load_cached(w)
        if cached:
            records.append(cached)
            continue
        try:
            art = await fetch_article(w.url)
            text = art.get("text", "")
        except Exception:
            text = ""
        records.append(_save_cache(w, text))
    return records
