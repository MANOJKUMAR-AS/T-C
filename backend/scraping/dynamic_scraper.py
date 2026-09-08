
from __future__ import annotations

import re

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except Exception:
    sync_playwright = None
    PlaywrightTimeoutError = Exception


def _clean(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(x.strip() for x in text.splitlines() if x.strip()).strip()


def scrape_dynamic_page(url: str) -> str:
    if not sync_playwright:
        return ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1440, "height": 1000},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        )
        try:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=25000)
            except PlaywrightTimeoutError:
                pass
            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except PlaywrightTimeoutError:
                pass
            page.wait_for_timeout(1500)
            text = page.locator("body").inner_text(timeout=8000)
            return _clean(text)
        finally:
            browser.close()
