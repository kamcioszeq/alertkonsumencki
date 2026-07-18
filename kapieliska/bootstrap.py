"""Bootstrap: ściągnij pełną listę kąpielisk przez /ajax/lista/{page}/."""
from __future__ import annotations

import logging
import re
from html import unescape

from . import config
from .browser import browser_page, warm_session
from .store import save_list

log = logging.getLogger("kapieliska.bootstrap")

_ID_RE = re.compile(r"/kapielisko/(\d+)")
_NAME_RE = re.compile(
    r'href="[^"]*/kapielisko/(\d+)"[^>]*>(.*?)</a>',
    re.S | re.I,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _parse_ajax_page(html: str) -> list[dict[str, str]]:
    """Z HTML partial (ajax) wyciągnij unikalne id + nazwę."""
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for m in _NAME_RE.finditer(html):
        kid, raw = m.group(1), m.group(2)
        if kid in seen:
            continue
        seen.add(kid)
        name = unescape(re.sub(r"\s+", " ", _TAG_RE.sub(" ", raw))).strip()
        if not name:
            name = f"Kąpielisko {kid}"
        out.append({
            "id": kid,
            "name": name,
            "url": config.DETAIL_TMPL.format(id=kid),
            "active": "1",
        })
    # fallback: same ids bez nazwy
    if not out:
        for kid in _ID_RE.findall(html):
            if kid in seen:
                continue
            seen.add(kid)
            out.append({
                "id": kid,
                "name": f"Kąpielisko {kid}",
                "url": config.DETAIL_TMPL.format(id=kid),
                "active": "1",
            })
    return out


async def fetch_all_sites() -> list[dict[str, str]]:
    """Pobierz wszystkie strony ajax aż pusta odpowiedź."""
    async with browser_page() as (_browser, page):
        await warm_session(page)
        all_items: list[dict[str, str]] = []
        seen: set[str] = set()
        page_no = 1
        empty_streak = 0
        while page_no <= 200:
            url = config.AJAX_LIST_TMPL.format(page=page_no)
            html = await page.evaluate(
                """async (u) => {
                    const r = await fetch(u);
                    return await r.text();
                }""",
                url,
            )
            items = _parse_ajax_page(html or "")
            if not items:
                empty_streak += 1
                log.info("ajax lista/%d — pusto (streak=%d)", page_no, empty_streak)
                if empty_streak >= 2:
                    break
                page_no += 1
                continue
            empty_streak = 0
            new = 0
            for it in items:
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                all_items.append(it)
                new += 1
            log.info("ajax lista/%d — +%d (łącznie %d)", page_no, new, len(all_items))
            page_no += 1
            await page.wait_for_timeout(200)
        return all_items


async def run_bootstrap() -> int:
    items = await fetch_all_sites()
    if not items:
        raise RuntimeError("Bootstrap: pusta lista kąpielisk — sprawdź Incapsula/Playwright.")
    save_list(items)
    log.info("Zapisano %d kąpielisk → %s", len(items), config.LIST_CSV)
    return len(items)
