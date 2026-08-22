import requests
from bs4 import BeautifulSoup


# ============================================================
# HTTP HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),

    "Accept": (
        "text/html,"
        "application/xhtml+xml,"
        "application/xml;q=0.9,"
        "image/avif,"
        "image/webp,"
        "*/*;q=0.8"
    ),

    "Accept-Language": "en-US,en;q=0.9",

    # IMPORTANT:
    # Prevent servers such as Netflix from returning
    # zstd-compressed responses.
    "Accept-Encoding": "identity",
}


# ============================================================
# STATIC PAGE SCRAPER
# ============================================================

def scrape_static_page(url):

    response = requests.get(
        url,
        timeout=20,
        headers=HEADERS,
        allow_redirects=True,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    # --------------------------------------------------------
    # Remove elements that don't contain useful policy text.
    # --------------------------------------------------------

    for element in soup([
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "noscript",
    ]):
        element.decompose()

    # --------------------------------------------------------
    # Extract visible text
    # --------------------------------------------------------

    text = soup.get_text(
        "\n",
        strip=True,
    )

    # --------------------------------------------------------
    # Remove empty lines
    # --------------------------------------------------------

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)