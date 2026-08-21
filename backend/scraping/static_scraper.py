import requests
from bs4 import BeautifulSoup


def scrape_static_page(url):

    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        },
        allow_redirects=True
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    # Remove elements that don't contain
    # useful policy text.
    for element in soup([
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "noscript"
    ]):

        element.decompose()

    text = soup.get_text(
        "\n",
        strip=True
    )

    # Remove empty lines.
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)