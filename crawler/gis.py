"""Parsowanie listingu ostrzeżeń GIS (https://www.gov.pl/web/gis/ostrzezenia).

Każdy wpis na stronie ma postać:
    <span class="date"> DD.MM.YYYY </span> ... <div class="title"><a href="/web/gis/...">Tytuł</a></div>
Najnowsze wpisy są na górze.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime

import httpx
import config

BASE = "https://www.gov.pl"
FETCH_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AlertKonsumenckiBot/1.0)"}

_ENTRY_RE = re.compile(
    r'class="date">\s*(\d{2}\.\d{2}\.\d{4})\s*<'
    r'.*?class="title">\s*<a[^>]+href="(/web/gis/[^"]+)"[^>]*>(.*?)</a>',
    re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Warning:
    date: date
    date_str: str
    title: str
    url: str

    @property
    def slug(self) -> str:
        return self.url.rstrip("/").rsplit("/", 1)[-1]


def parse_listing(html: str) -> list[Warning]:
    out: list[Warning] = []
    for m in _ENTRY_RE.finditer(html):
        date_str, href, raw_title = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"\s+", " ", _TAG_RE.sub(" ", raw_title)).strip()
        try:
            d = datetime.strptime(date_str, "%d.%m.%Y").date()
        except ValueError:
            continue
        url = href if href.startswith("http") else BASE + href
        out.append(Warning(date=d, date_str=date_str, title=title, url=url))
    return out


async def fetch_listing() -> list[Warning]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=FETCH_HEADERS) as client:
        r = await client.get(config.GIS_LISTING_URL)
        r.raise_for_status()
        return parse_listing(r.text)
