"""Wspólny helper Playwright (Incapsula na sk.gis.gov.pl)."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import Browser, Page, async_playwright

from . import config


def _ensure_browsers_path() -> None:
    path = config.PLAYWRIGHT_BROWSERS_PATH
    if path and not os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = path


@asynccontextmanager
async def browser_page() -> AsyncIterator[tuple[Browser, Page]]:
    """Uruchom Chromium + stronę z ignore_https_errors (certyfikat GIS)."""
    _ensure_browsers_path()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
            locale="pl-PL",
        )
        page = await context.new_page()
        try:
            yield browser, page
        finally:
            await browser.close()


async def warm_session(page: Page) -> None:
    """Wejdź na listę, żeby Incapsula wydała cookies sesji."""
    await page.goto(config.LIST_URL, wait_until="networkidle", timeout=90_000)
    await page.wait_for_timeout(1500)
