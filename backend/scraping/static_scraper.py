
from __future__ import annotations

import io
import re
from typing import Optional
from urllib.parse import urlparse

import requests

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

TIMEOUT = 20
MAX_BYTES = 15 * 1024 * 1024

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _clean(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text or "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    return "\n".join(x.strip() for x in text.splitlines() if x.strip()).strip()


def _pdf_text(data: bytes) -> str:
    if not PdfReader:
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        parts = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return _clean("\n".join(parts))
    except Exception:
        return ""


def scrape_static_page(url: str) -> str:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )
    response.raise_for_status()

    data = response.content[:MAX_BYTES]
    content_type = (response.headers.get("content-type") or "").lower()
    final_url = response.url.lower()

    if "application/pdf" in content_type or final_url.endswith(".pdf"):
        return _pdf_text(data)

    encoding = response.encoding or "utf-8"
    html = data.decode(encoding, errors="ignore")

    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "template"]):
            tag.decompose()
        return _clean(soup.get_text("\n"))

    return _clean(re.sub(r"<[^>]+>", " ", html))
