"""
Firecrawl fallback scraper for Agent 1.

Purpose:
    - Provide a server-side fallback when browser/static/Playwright
      extraction cannot discover or extract policy documents.
    - Discover links from a webpage.
    - Scrape individual policy URLs.
    - Keep the Firecrawl API key strictly on the backend.

Architecture:

    Chrome browser
          ↓
    Static scraper
          ↓
    Playwright
          ↓
    Firecrawl fallback
          ↓
    Agent 1 validation / deduplication
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()

logger = logging.getLogger(__name__)

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "").strip()

FIRECRAWL_BASE_URL = "https://api.firecrawl.dev/v2"

# Keep requests bounded so one broken site cannot stall Agent 1 indefinitely.
FIRECRAWL_TIMEOUT_SECONDS = int(
    os.getenv("FIRECRAWL_TIMEOUT_SECONDS", "60")
)

# Maximum number of discovered policy URLs that we will attempt to scrape.
FIRECRAWL_MAX_POLICY_URLS = int(
    os.getenv("FIRECRAWL_MAX_POLICY_URLS", "12")
)

# Minimum extracted text that is considered potentially useful.
FIRECRAWL_MIN_CONTENT_CHARS = int(
    os.getenv("FIRECRAWL_MIN_CONTENT_CHARS", "500")
)


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def _log(message: str, *args: Any) -> None:
    logger.info("[Firecrawl] " + message, *args)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def is_configured() -> bool:
    """
    Return True when a Firecrawl API key is available.
    """
    return bool(FIRECRAWL_API_KEY)


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def _normalize_url(url: str, base_url: str = "") -> str:
    """
    Normalize a discovered URL.

    Handles:
        - relative links
        - fragments
        - whitespace
        - protocol-relative URLs
    """
    if not url:
        return ""

    url = url.strip()

    if not url:
        return ""

    if base_url:
        url = urljoin(base_url, url)

    url, _fragment = urldefrag(url)

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc:
        return ""

    return url


def _same_domain(url_a: str, url_b: str) -> bool:
    """
    Return True when two URLs belong to the same hostname.

    www.example.com and example.com are treated as the same domain.
    """
    try:
        host_a = (urlparse(url_a).hostname or "").lower()
        host_b = (urlparse(url_b).hostname or "").lower()

        host_a = host_a.removeprefix("www.")
        host_b = host_b.removeprefix("www.")

        return bool(host_a and host_b and host_a == host_b)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Policy URL classification
# ---------------------------------------------------------------------------

_POLICY_PATTERNS = {
    "privacy": [
        r"\bprivacy\b",
        r"\bprivacy-policy\b",
        r"\bprivacy_policy\b",
        r"\bprivacypolicy\b",
        r"\bdata[-_]?privacy\b",
    ],
    "terms": [
        r"\bterms\b",
        r"\bterms[-_]?and[-_]?conditions\b",
        r"\bterms[-_]?of[-_]?use\b",
        r"\btermsofuse\b",
        r"\bterms[-_]?of[-_]?service\b",
        r"\buser[-_]?agreement\b",
        r"\buser[-_]?terms\b",
    ],
    "cookies": [
        r"\bcookies?\b",
        r"\bcookie[-_]?policy\b",
        r"\bcookie[-_]?notice\b",
        r"\bcookies[-_]?policy\b",
    ],
    "returns": [
        r"\breturn[-_]?refund\b",
        r"\breturns?\b",
        r"\brefunds?\b",
        r"\brefund[-_]?policy\b",
        r"\breturn[-_]?policy\b",
    ],
    "payments": [
        r"\bpayment\b",
        r"\bpayments\b",
        r"\bfee[-_]?payment\b",
        r"\bfees[-_]?payment\b",
        r"\bpayment[-_]?policy\b",
    ],
    "promotions": [
        r"\bpromotion\b",
        r"\bpromotions\b",
        r"\bpromo[-_]?policy\b",
        r"\bsale[-_]?policy\b",
        r"\boffer[-_]?terms\b",
    ],
    "legal": [
        r"\blegal[-_]?notice\b",
        r"\blegal[-_]?notices\b",
        r"\bnotices?\b",
        r"\bcorporate[-_]?information\b",
        r"\bcorp[-_]?info\b",
        r"\bimprint\b",
    ],
}


def classify_policy_url(url: str) -> tuple[str, int]:
    """
    Classify a URL based on path/query signals.

    Returns:
        (policy_type, confidence_score)

    A score of 0 means no meaningful policy signal was found.
    """
    if not url:
        return "unknown", 0

    lowered = url.lower()

    # Ignore obvious non-policy resources.
    if re.search(
        r"\.(?:jpg|jpeg|png|gif|webp|svg|ico|css|js|map|woff|woff2|ttf)"
        r"(?:$|\?)",
        lowered,
    ):
        return "unknown", 0

    scores: dict[str, int] = {
        policy_type: 0
        for policy_type in _POLICY_PATTERNS
    }

    for policy_type, patterns in _POLICY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, lowered):
                scores[policy_type] += 10

    if not any(scores.values()):
        return "unknown", 0

    policy_type = max(scores, key=scores.get)
    return policy_type, scores[policy_type]


# ---------------------------------------------------------------------------
# Firecrawl HTTP request
# ---------------------------------------------------------------------------

def _post_scrape(
    url: str,
    formats: list[str] | None = None,
    only_main_content: bool = True,
    wait_for_ms: int = 0,
) -> dict[str, Any] | None:
    """
    Call Firecrawl v2 /scrape.

    Firecrawl currently exposes:
        POST https://api.firecrawl.dev/v2/scrape

    Authentication:
        Authorization: Bearer <API_KEY>
    """
    if not is_configured():
        logger.warning(
            "[Firecrawl] FIRECRAWL_API_KEY is not configured."
        )
        return None

    if not url:
        return None

    if formats is None:
        formats = ["markdown"]

    endpoint = f"{FIRECRAWL_BASE_URL}/scrape"

    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "url": url,
        "formats": formats,
        "onlyMainContent": only_main_content,
        "blockAds": True,
        "removeBase64Images": True,
        "proxy": "auto",
        "storeInCache": True,
    }

    if wait_for_ms > 0:
        payload["waitFor"] = wait_for_ms

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=FIRECRAWL_TIMEOUT_SECONDS,
        )

    except requests.RequestException as exc:
        logger.warning(
            "[Firecrawl] Request failed for %s: %s",
            url,
            exc,
        )
        return None

    if response.status_code != 200:
        body_preview = response.text[:500].replace("\n", " ")

        logger.warning(
            "[Firecrawl] HTTP %s for %s: %s",
            response.status_code,
            url,
            body_preview,
        )

        return None

    try:
        data = response.json()
    except ValueError:
        logger.warning(
            "[Firecrawl] Invalid JSON response for %s",
            url,
        )
        return None

    if not isinstance(data, dict):
        logger.warning(
            "[Firecrawl] Unexpected response structure for %s",
            url,
        )
        return None

    if data.get("success") is False:
        logger.warning(
            "[Firecrawl] API reported failure for %s: %s",
            url,
            data.get("error"),
        )
        return None

    return data


# ---------------------------------------------------------------------------
# Response extraction
# ---------------------------------------------------------------------------

def _extract_data(response: dict[str, Any]) -> dict[str, Any]:
    """
    Safely obtain Firecrawl's data object.
    """
    data = response.get("data")

    if isinstance(data, dict):
        return data

    # Be tolerant of alternate response wrappers.
    return response


def _extract_markdown(response: dict[str, Any]) -> str:
    """
    Extract the main Markdown/text representation.
    """
    data = _extract_data(response)

    markdown = data.get("markdown")

    if isinstance(markdown, str):
        return markdown.strip()

    # Some responses may provide HTML instead.
    html = data.get("html")

    if isinstance(html, str):
        return html.strip()

    return ""


def _extract_title(response: dict[str, Any]) -> str:
    """
    Extract page title from Firecrawl metadata.
    """
    data = _extract_data(response)

    metadata = data.get("metadata")

    if isinstance(metadata, dict):
        title = metadata.get("title")

        if isinstance(title, str):
            return title.strip()

    return ""


def _extract_source_url(response: dict[str, Any], fallback: str) -> str:
    """
    Extract Firecrawl's canonical/source URL.
    """
    data = _extract_data(response)

    metadata = data.get("metadata")

    if isinstance(metadata, dict):
        source_url = metadata.get("sourceURL")

        if isinstance(source_url, str) and source_url.strip():
            return source_url.strip()

        metadata_url = metadata.get("url")

        if isinstance(metadata_url, str) and metadata_url.strip():
            return metadata_url.strip()

    return fallback


def _extract_links(response: dict[str, Any]) -> list[str]:
    """
    Extract links returned by Firecrawl.
    """
    data = _extract_data(response)

    links = data.get("links")

    if not isinstance(links, list):
        return []

    result: list[str] = []

    for link in links:
        if not isinstance(link, str):
            continue

        link = link.strip()

        if link:
            result.append(link)

    return result


# ---------------------------------------------------------------------------
# Public scrape function
# ---------------------------------------------------------------------------

def firecrawl_scrape(
    url: str,
    include_links: bool = True,
) -> dict[str, Any] | None:
    """
    Scrape one URL using Firecrawl.

    Returns a normalized object:

    {
        "url": "...",
        "title": "...",
        "content": "...",
        "links": [...],
        "source": "firecrawl"
    }

    Returns None when Firecrawl is unavailable or fails.
    """
    normalized_url = _normalize_url(url)

    if not normalized_url:
        return None

    _log("Scraping: %s", normalized_url)

    formats = ["markdown"]

    if include_links:
        formats.append("links")

    response = _post_scrape(
        normalized_url,
        formats=formats,
        only_main_content=True,
    )

    if not response:
        return None

    content = _extract_markdown(response)
    title = _extract_title(response)
    source_url = _extract_source_url(
        response,
        normalized_url,
    )

    links = _extract_links(response)

    if not content:
        logger.warning(
            "[Firecrawl] No content returned for %s",
            normalized_url,
        )
        return None

    result = {
        "url": source_url or normalized_url,
        "title": title,
        "content": content,
        "links": links,
        "source": "firecrawl",
    }

    _log(
        "Success: %s chars, %s links: %s",
        len(content),
        len(links),
        normalized_url,
    )

    return result


# ---------------------------------------------------------------------------
# Discover policy links
# ---------------------------------------------------------------------------

def discover_policy_links(
    url: str,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """
    Use Firecrawl to scrape a homepage/page and identify likely policy URLs.

    This does NOT crawl the entire website.

    It:
        1. Scrapes the supplied page.
        2. Reads returned links.
        3. Scores URLs for policy relevance.
        4. Keeps same-domain candidates.
        5. Deduplicates them.
        6. Returns the strongest candidates.
    """
    normalized_url = _normalize_url(url)

    if not normalized_url:
        return []

    if max_results is None:
        max_results = FIRECRAWL_MAX_POLICY_URLS

    _log(
        "Discovering policy links from: %s",
        normalized_url,
    )

    scraped = firecrawl_scrape(
        normalized_url,
        include_links=True,
    )

    if not scraped:
        logger.warning(
            "[Firecrawl] Discovery scrape failed: %s",
            normalized_url,
        )
        return []

    raw_links = scraped.get("links") or []

    if not isinstance(raw_links, list):
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw_link in raw_links:
        if not isinstance(raw_link, str):
            continue

        candidate_url = _normalize_url(
            raw_link,
            base_url=normalized_url,
        )

        if not candidate_url:
            continue

        if candidate_url in seen:
            continue

        seen.add(candidate_url)

        # Policy discovery should normally remain on the site's domain.
        if not _same_domain(
            candidate_url,
            normalized_url,
        ):
            continue

        policy_type, score = classify_policy_url(
            candidate_url
        )

        if score <= 0:
            continue

        candidates.append(
            {
                "url": candidate_url,
                "type": policy_type,
                "score": score,
                "source": "firecrawl",
            }
        )

    # Strongest policy signals first.
    candidates.sort(
        key=lambda item: (
            int(item.get("score", 0)),
            str(item.get("url", "")),
        ),
        reverse=True,
    )

    candidates = candidates[:max_results]

    _log(
        "Policy candidates discovered: %s",
        len(candidates),
    )

    for candidate in candidates:
        _log(
            "Candidate [%s] score=%s %s",
            candidate["type"],
            candidate["score"],
            candidate["url"],
        )

    return candidates


# ---------------------------------------------------------------------------
# Scrape discovered policy candidates
# ---------------------------------------------------------------------------

def scrape_policy_candidates(
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Scrape a list of candidate policy URLs.

    Each successful result is normalized into the structure Agent 1 can
    consume later.
    """
    documents: list[dict[str, Any]] = []

    if not candidates:
        return documents

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue

        url = str(candidate.get("url") or "").strip()

        if not url:
            continue

        policy_type = str(
            candidate.get("type") or "unknown"
        )

        _log(
            "Scraping policy candidate [%s]: %s",
            policy_type,
            url,
        )

        result = firecrawl_scrape(
            url,
            include_links=False,
        )

        if not result:
            continue

        content = str(
            result.get("content") or ""
        ).strip()

        if len(content) < FIRECRAWL_MIN_CONTENT_CHARS:
            logger.warning(
                "[Firecrawl] Candidate too short, rejected: "
                "%s (%s chars)",
                url,
                len(content),
            )
            continue

        documents.append(
            {
                "url": result.get("url") or url,
                "type": policy_type,
                "title": result.get("title") or "",
                "content": content,
                "source": "firecrawl",
                "discovery_score": candidate.get(
                    "score",
                    0,
                ),
            }
        )

    _log(
        "Successfully scraped policy documents: %s",
        len(documents),
    )

    return documents


# ---------------------------------------------------------------------------
# One-call fallback helper
# ---------------------------------------------------------------------------

def firecrawl_discover_and_scrape(
    url: str,
    max_results: int | None = None,
) -> list[dict[str, Any]]:
    """
    Complete Firecrawl fallback pipeline:

        webpage
          ↓
        discover links
          ↓
        identify policy candidates
          ↓
        scrape candidates
          ↓
        return documents
    """
    if not is_configured():
        logger.warning(
            "[Firecrawl] Skipping fallback because "
            "FIRECRAWL_API_KEY is not configured."
        )
        return []

    candidates = discover_policy_links(
        url,
        max_results=max_results,
    )

    if not candidates:
        logger.info(
            "[Firecrawl] No policy candidates discovered: %s",
            url,
        )
        return []

    return scrape_policy_candidates(
        candidates
    )


# ---------------------------------------------------------------------------
# Health / diagnostics
# ---------------------------------------------------------------------------

def firecrawl_status() -> dict[str, Any]:
    """
    Return configuration information without exposing the API key.
    """
    return {
        "configured": is_configured(),
        "base_url": FIRECRAWL_BASE_URL,
        "timeout_seconds": FIRECRAWL_TIMEOUT_SECONDS,
        "max_policy_urls": FIRECRAWL_MAX_POLICY_URLS,
        "min_content_chars": FIRECRAWL_MIN_CONTENT_CHARS,
    }