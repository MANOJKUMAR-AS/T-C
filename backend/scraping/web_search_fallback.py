"""
Web Search + Deterministic Policy Route Fallback

Purpose:
    Third and final policy-discovery fallback for Agent 1.

Discovery order:
    1. Browser-collected policy links/documents
    2. Backend/static/dynamic extraction + Firecrawl
    3. Public web search + deterministic policy route discovery

Important:
    Search engines are used only for discovery.
    Legal content is accepted only after fetching the actual
    company-domain page and validating its contents.

This module is intentionally generic and should work across
different companies without site-specific hardcoding.
"""

from __future__ import annotations

import base64
import re
from typing import Dict, List
from urllib.parse import (
    parse_qs,
    unquote,
    urlparse,
    urlunparse,
)

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

REQUEST_TIMEOUT = 15

MIN_PAGE_CHARS = 500

MIN_POLICY_SCORE = 3

SEARCH_RESULTS_PER_QUERY = 8

MAX_ROUTE_CANDIDATES = 80

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

SEARCH_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-US,en;q=0.9",
}

PAGE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


# ---------------------------------------------------------------------
# Search phrases
# ---------------------------------------------------------------------

POLICY_QUERIES = {
    "terms": [
        '"terms and conditions"',
        '"terms of use"',
        '"terms of service"',
    ],
    "privacy": [
        '"privacy policy"',
        '"privacy notice"',
    ],
    "cookies": [
        '"cookie policy"',
        '"cookie notice"',
        '"cookies policy"',
    ],
    "returns": [
        '"return policy"',
        '"refund policy"',
        '"cancellation policy"',
    ],
    "payments": [
        '"payment policy"',
        '"payment terms"',
    ],
    "legal": [
        '"legal notice"',
        '"disclaimer"',
    ],
}


# ---------------------------------------------------------------------
# Generic policy routes
#
# These are candidate paths only.
# They are NOT automatically accepted.
#
# The actual URL is fetched and its content is validated before
# becoming a policy document.
# ---------------------------------------------------------------------

POLICY_ROUTES = {
    "terms": [
        "/terms",
        "/terms-of-use",
        "/terms-of-service",
        "/terms-and-conditions",
        "/terms-conditions",
        "/terms_conditions",
        "/termsofuse",
        "/termsconditions",
        "/terms-and-condition",
        "/termsconditions",
        "/legal/terms",
        "/legal/terms-of-use",
        "/legal/terms-and-conditions",
        "/legal/terms-conditions",
        "/policies/terms",
        "/policies/terms-of-use",
        "/policies/terms-and-conditions",
        "/policy/terms",
        "/policy/terms-of-use",
        "/policy/terms-and-conditions",
        "/app-terms-conditions",
        "/app/terms",
        "/app/terms-and-conditions",
    ],
    "privacy": [
        "/privacy",
        "/privacy-policy",
        "/privacy_policy",
        "/privacypolicy",
        "/privacy-notice",
        "/privacy_notice",
        "/privacy-policy-app",
        "/privacy-policy-mobile",
        "/privacy/app",
        "/legal/privacy",
        "/legal/privacy-policy",
        "/policies/privacy",
        "/policies/privacy-policy",
        "/policy/privacy",
        "/policy/privacy-policy",
        "/policy",
    ],
    "cookies": [
        "/cookies",
        "/cookie-policy",
        "/cookie_policy",
        "/cookies-policy",
        "/cookies_policy",
        "/cookie-notice",
        "/cookie_notice",
        "/legal/cookies",
        "/legal/cookie-policy",
        "/policies/cookies",
        "/policies/cookie-policy",
        "/policy/cookies",
        "/policy/cookie-policy",
    ],
    "returns": [
        "/returns",
        "/return-policy",
        "/return_policy",
        "/refund-policy",
        "/refund_policy",
        "/returns-policy",
        "/returns_policy",
        "/cancellation-policy",
        "/cancellation_policy",
        "/return-refund-policy",
        "/refund-and-return-policy",
        "/returns-and-refunds",
        "/legal/returns",
        "/legal/return-policy",
        "/policies/returns",
        "/policies/return-policy",
        "/policy/returns",
        "/policy/return-policy",
    ],
    "payments": [
        "/payments",
        "/payment-policy",
        "/payment_policy",
        "/payments-policy",
        "/payments_policy",
        "/payment-terms",
        "/payment_terms",
        "/legal/payments",
        "/legal/payment-policy",
        "/policies/payments",
        "/policies/payment-policy",
        "/policy/payments",
        "/policy/payment-policy",
    ],
    "legal": [
        "/legal",
        "/legal-notice",
        "/legal_notice",
        "/legal-information",
        "/legal_information",
        "/disclaimer",
        "/disclaimers",
        "/notices",
        "/legal/notices",
        "/legal/disclaimer",
        "/policies/legal",
        "/policies/legal-notice",
        "/policy/legal",
        "/policy/legal-notice",
    ],
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _host(url: str) -> str:
    """Return normalized hostname."""
    try:
        return (urlparse(url).hostname or "").lower().strip(".")
    except Exception:
        return ""


def _root_domain(host: str) -> str:
    """
    Approximate registrable domain without external dependencies.

    Examples:
        www.nykaa.com -> nykaa.com
        help.nykaa.com -> nykaa.com
    """
    host = (host or "").lower().strip(".")

    parts = host.split(".")

    if len(parts) >= 2:
        return ".".join(parts[-2:])

    return host


def _same_site(url: str, target_host: str) -> bool:
    """Return True when URL belongs to the target domain."""
    candidate_host = _host(url)

    if not candidate_host or not target_host:
        return False

    return (
        _root_domain(candidate_host)
        == _root_domain(target_host)
    )


def _canonical_url(url: str) -> str:
    """
    Normalize URL for deduplication.
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()

        if not scheme or not hostname:
            return ""

        port = parsed.port

        if port:
            if (
                (scheme == "http" and port == 80)
                or (
                    scheme == "https"
                    and port == 443
                )
            ):
                netloc = hostname
            else:
                netloc = f"{hostname}:{port}"
        else:
            netloc = hostname

        path = parsed.path or "/"

        if path != "/":
            path = path.rstrip("/")

        return urlunparse(
            (
                scheme,
                netloc,
                path,
                "",
                parsed.query,
                "",
            )
        )

    except Exception:
        return ""


def _clean_text(text: str) -> str:
    """Normalize extracted text."""
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(
        r"\n\s*\n\s*\n+",
        "\n\n",
        text,
    )

    return text.strip()


# ---------------------------------------------------------------------
# Search redirect decoding
# ---------------------------------------------------------------------


def _decode_bing_u_parameter(value: str) -> str:
    """
    Decode Bing's redirect URL.

    Typical form:

        u=a1<URL-safe-base64>

    The a1 prefix is removed before decoding.
    """
    if not value:
        return ""

    value = unquote(value).strip()

    candidates = [value]

    if value.startswith("a1"):
        candidates.insert(
            0,
            value[2:],
        )

    for candidate in candidates:
        if not candidate:
            continue

        try:
            padding = "=" * (
                -len(candidate) % 4
            )

            decoded_bytes = (
                base64.urlsafe_b64decode(
                    candidate + padding
                )
            )

            decoded = decoded_bytes.decode(
                "utf-8",
                errors="ignore",
            )

            decoded = unquote(
                decoded
            ).strip()

            if decoded.startswith(
                ("http://", "https://")
            ):
                return decoded

        except Exception:
            continue

    # Ordinary Base64 fallback.
    for candidate in candidates:
        if not candidate:
            continue

        try:
            padding = "=" * (
                -len(candidate) % 4
            )

            decoded_bytes = base64.b64decode(
                candidate + padding,
                altchars=b"-_",
                validate=False,
            )

            decoded = decoded_bytes.decode(
                "utf-8",
                errors="ignore",
            )

            decoded = unquote(
                decoded
            ).strip()

            if decoded.startswith(
                ("http://", "https://")
            ):
                return decoded

        except Exception:
            continue

    if value.startswith(
        ("http://", "https://")
    ):
        return value

    return ""


def _unwrap_search_url(url: str) -> str:
    """
    Convert search-engine redirects into actual URLs.

    Supported:
        Bing /ck/a?...&u=...
        DuckDuckGo /l/?uddg=...
        Google redirects
        Normal URLs
    """
    if not url:
        return ""

    try:
        parsed = urlparse(url)

        host = (
            parsed.hostname or ""
        ).lower()

        # -------------------------------------------------------------
        # Bing
        # -------------------------------------------------------------

        if (
            "bing.com" in host
            and parsed.path.startswith("/ck/a")
        ):
            params = parse_qs(
                parsed.query,
                keep_blank_values=True,
            )

            values = params.get(
                "u",
                [],
            )

            if values:
                decoded = (
                    _decode_bing_u_parameter(
                        values[0]
                    )
                )

                if decoded:
                    return decoded

            return ""

        # -------------------------------------------------------------
        # DuckDuckGo
        # -------------------------------------------------------------

        if "duckduckgo.com" in host:
            params = parse_qs(
                parsed.query,
                keep_blank_values=True,
            )

            values = params.get(
                "uddg",
                [],
            )

            if values:
                decoded = unquote(
                    values[0]
                ).strip()

                if decoded.startswith(
                    ("http://", "https://")
                ):
                    return decoded

            return ""

        # -------------------------------------------------------------
        # Google
        # -------------------------------------------------------------

        if "google.com" in host:
            params = parse_qs(
                parsed.query,
                keep_blank_values=True,
            )

            for key in (
                "url",
                "q",
                "u",
            ):
                values = params.get(
                    key,
                    [],
                )

                if values:
                    candidate = unquote(
                        values[0]
                    ).strip()

                    if candidate.startswith(
                        ("http://", "https://")
                    ):
                        return candidate

        # -------------------------------------------------------------
        # Normal URL
        # -------------------------------------------------------------

        if url.startswith(
            ("http://", "https://")
        ):
            return url

    except Exception:
        return ""

    return ""


# ---------------------------------------------------------------------
# Search result classification
# ---------------------------------------------------------------------


def _classify_result(
    url: str,
    title: str,
    snippet: str,
    policy_type: str,
) -> int:
    """
    Score a discovered URL/result for policy relevance.
    """
    combined = (
        f"{url} {title} {snippet}"
    ).lower()

    score = 0

    url_signals = {
        "terms": [
            "terms",
            "terms-of-use",
            "terms-of-service",
            "terms-and-conditions",
            "terms-conditions",
            "termsofuse",
        ],
        "privacy": [
            "privacy",
            "privacy-policy",
            "privacypolicy",
            "privacy-notice",
        ],
        "cookies": [
            "cookie",
            "cookies",
        ],
        "returns": [
            "return",
            "returns",
            "refund",
            "cancellation",
        ],
        "payments": [
            "payment",
            "payments",
        ],
        "legal": [
            "legal",
            "disclaimer",
            "notice",
        ],
    }

    for signal in url_signals.get(
        policy_type,
        [],
    ):
        if signal in url.lower():
            score += 3
            break

    text_signals = {
        "terms": [
            "terms and conditions",
            "terms of use",
            "terms of service",
        ],
        "privacy": [
            "privacy policy",
            "privacy notice",
        ],
        "cookies": [
            "cookie policy",
            "cookie notice",
            "cookies",
        ],
        "returns": [
            "return policy",
            "refund policy",
            "cancellation policy",
        ],
        "payments": [
            "payment policy",
            "payment terms",
        ],
        "legal": [
            "legal notice",
            "disclaimer",
        ],
    }

    for signal in text_signals.get(
        policy_type,
        [],
    ):
        if signal in combined:
            score += 2

    return score


# ---------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------


def _extract_page_text(html: str) -> str:
    """
    Extract readable page text.
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # Remove technical/non-content elements.
        for tag in soup.find_all(
            [
                "script",
                "style",
                "noscript",
                "svg",
                "template",
                "iframe",
                "canvas",
                "nav",
                "header",
                "footer",
                "form",
            ]
        ):
            tag.decompose()

        # Remove common UI elements.
        for tag in soup.find_all(
            attrs={
                "class": re.compile(
                    r"(cookie|consent|banner|modal|popup)",
                    re.I,
                )
            }
        ):
            tag.decompose()

        for tag in soup.find_all(
            attrs={
                "id": re.compile(
                    r"(cookie|consent|banner|modal|popup)",
                    re.I,
                )
            }
        ):
            tag.decompose()

        # Prefer actual content containers.
        main = soup.find("main")

        if main is None:
            main = soup.find("article")

        if main is None:
            main = soup.body

        if main is None:
            main = soup

        text = main.get_text(
            separator="\n",
            strip=True,
        )

        return _clean_text(text)

    except Exception:
        return ""


# ---------------------------------------------------------------------
# Content validation
# ---------------------------------------------------------------------


def _is_policy_content(
    text: str,
    policy_type: str,
    url: str = "",
) -> bool:
    """
    Verify that the page contains actual policy/legal content.
    """
    if not text or len(text) < MIN_PAGE_CHARS:
        return False

    combined = (
        f"{url}\n{text}"
    ).lower()

    commerce_signals = [
        "add to bag",
        "add to cart",
        "shop now",
        "sort by popularity",
        "sort by price",
        "all products",
        "buy now",
        "wishlist",
        "shopping cart",
    ]

    commerce_hits = sum(
        1
        for signal in commerce_signals
        if signal in combined
    )

    if commerce_hits >= 3:
        return False

    groups = {
        "terms": [
            "terms and conditions",
            "terms of use",
            "terms of service",
            "user agreement",
            "governing law",
            "intellectual property",
            "limitation of liability",
        ],
        "privacy": [
            "privacy policy",
            "personal information",
            "personal data",
            "data protection",
            "information we collect",
            "third party",
            "cookies",
        ],
        "cookies": [
            "cookie policy",
            "cookie notice",
            "cookies",
            "strictly necessary",
            "analytics cookies",
            "advertising cookies",
            "cookie preferences",
        ],
        "returns": [
            "return policy",
            "cancellation policy",
            "refund",
            "return request",
            "replacement",
            "return period",
        ],
        "payments": [
            "payment policy",
            "payment methods",
            "payment terms",
            "credit card",
            "debit card",
            "payment gateway",
        ],
        "legal": [
            "legal notice",
            "disclaimer",
            "grievance officer",
            "jurisdiction",
            "applicable law",
            "copyright",
        ],
    }

    signals = groups.get(
        policy_type,
        [],
    )

    hits = sum(
        1
        for signal in signals
        if signal in combined
    )

    return hits >= 2


# ---------------------------------------------------------------------
# Fetch actual page
# ---------------------------------------------------------------------


def _fetch_policy_page(url: str) -> str:
    """
    Fetch actual policy page and extract text.
    """
    try:
        response = requests.get(
            url,
            headers=PAGE_HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code != 200:
            print(
                f"Policy page fetch failed: "
                f"HTTP {response.status_code} "
                f"{url}"
            )
            return ""

        content_type = (
            response.headers.get(
                "content-type",
                "",
            ).lower()
        )

        if (
            "text/html" not in content_type
            and "application/xhtml+xml"
            not in content_type
        ):
            print(
                f"Policy page skipped, "
                f"non-HTML: {content_type} "
                f"{url}"
            )
            return ""

        text = _extract_page_text(
            response.text
        )

        if len(text) < MIN_PAGE_CHARS:
            print(
                f"Policy page too short: "
                f"{len(text)} chars "
                f"{url}"
            )
            return ""

        final_url = (
            response.url
            or url
        )

        if final_url != url:
            print(
                f"Policy page redirected: "
                f"{url} -> {final_url}"
            )

        print(
            f"Policy page fetched successfully: "
            f"{len(text)} chars "
            f"{final_url}"
        )

        return text

    except requests.RequestException as exc:
        print(
            f"Policy page request failed: "
            f"{url} | {exc}"
        )
        return ""

    except Exception as exc:
        print(
            f"Policy page extraction failed: "
            f"{url} | {exc}"
        )
        return ""


# ---------------------------------------------------------------------
# Bing
# ---------------------------------------------------------------------


def _search_bing(
    query: str,
    max_results: int = SEARCH_RESULTS_PER_QUERY,
) -> List[Dict[str, str]]:
    """
    Search Bing.
    """
    try:
        response = requests.get(
            "https://www.bing.com/search",
            params={
                "q": query,
                "count": max_results,
            },
            headers=SEARCH_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            print(
                f"Bing search failed: "
                f"HTTP {response.status_code}"
            )
            return []

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        results: List[Dict[str, str]] = []

        for item in soup.select(
            "li.b_algo"
        ):
            link = item.find("a")

            if not link:
                continue

            href = link.get(
                "href",
                "",
            ).strip()

            if not href:
                continue

            title = link.get_text(
                " ",
                strip=True,
            )

            paragraph = item.find("p")

            snippet = (
                paragraph.get_text(
                    " ",
                    strip=True,
                )
                if paragraph
                else ""
            )

            results.append(
                {
                    "url": href,
                    "title": title,
                    "snippet": snippet,
                }
            )

            if len(results) >= max_results:
                break

        return results

    except Exception as exc:
        print(
            f"Bing search exception: {exc}"
        )
        return []


# ---------------------------------------------------------------------
# DuckDuckGo
# ---------------------------------------------------------------------


def _search_duckduckgo(
    query: str,
    max_results: int = SEARCH_RESULTS_PER_QUERY,
) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo HTML endpoint.
    """
    try:
        response = requests.get(
            "https://html.duckduckgo.com/html/",
            params={
                "q": query,
            },
            headers=SEARCH_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code != 200:
            print(
                f"DuckDuckGo search failed: "
                f"HTTP {response.status_code}"
            )
            return []

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        results: List[Dict[str, str]] = []

        for item in soup.select(
            ".result"
        ):
            link = item.select_one(
                ".result__a"
            )

            if not link:
                continue

            href = link.get(
                "href",
                "",
            ).strip()

            if not href:
                continue

            title = link.get_text(
                " ",
                strip=True,
            )

            snippet_node = item.select_one(
                ".result__snippet"
            )

            snippet = (
                snippet_node.get_text(
                    " ",
                    strip=True,
                )
                if snippet_node
                else ""
            )

            results.append(
                {
                    "url": href,
                    "title": title,
                    "snippet": snippet,
                }
            )

            if len(results) >= max_results:
                break

        return results

    except Exception as exc:
        print(
            f"DuckDuckGo search exception: "
            f"{exc}"
        )
        return []


# ---------------------------------------------------------------------
# Search wrapper
# ---------------------------------------------------------------------


def _search(
    query: str,
    max_results: int = SEARCH_RESULTS_PER_QUERY,
) -> List[Dict[str, str]]:
    """
    Search Bing first, then DuckDuckGo.
    """
    results = _search_bing(
        query,
        max_results=max_results,
    )

    if results:
        return results

    print(
        "Bing returned no usable results. "
        "Trying DuckDuckGo..."
    )

    return _search_duckduckgo(
        query,
        max_results=max_results,
    )


# ---------------------------------------------------------------------
# Deterministic candidate routes
# ---------------------------------------------------------------------


def _build_route_candidates(
    base_url: str,
) -> List[Dict[str, str]]:
    """
    Generate generic policy route candidates from the company's
    base URL.

    The routes are only candidates. Actual content must still be
    fetched and validated.
    """
    parsed = urlparse(base_url)

    if not parsed.scheme or not parsed.hostname:
        return []

    origin = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            "",
            "",
            "",
            "",
        )
    ).rstrip("/")

    candidates: List[Dict[str, str]] = []

    for policy_type, routes in POLICY_ROUTES.items():

        for route in routes:

            candidate = (
                f"{origin}{route}"
            )

            candidates.append(
                {
                    "url": candidate,
                    "type": policy_type,
                    "discovery_method": (
                        "deterministic_policy_route"
                    ),
                }
            )

            if (
                len(candidates)
                >= MAX_ROUTE_CANDIDATES
            ):
                return candidates

    return candidates


# ---------------------------------------------------------------------
# Main public fallback
# ---------------------------------------------------------------------


def search_policy_documents(
    url: str,
    max_documents: int = 8,
) -> List[Dict]:
    """
    Third and final policy-discovery fallback.

    Strategy:

        1. Search engine discovery
        2. Unwrap search URLs
        3. Same-site validation
        4. Fetch actual company page
        5. Validate legal content

    Then:

        6. Deterministic policy-route discovery
        7. Fetch actual company page
        8. Validate legal content

    Search engines are NOT treated as sources of legal text.
    """

    print()
    print("=" * 70)
    print("WEB SEARCH + POLICY ROUTE FALLBACK ACTIVATED")
    print("=" * 70)

    target_host = _host(url)

    if not target_host:
        print(
            "Fallback aborted: invalid target URL"
        )
        return []

    print(
        f"Target domain: {target_host}"
    )

    documents: List[Dict] = []

    seen_urls = set()

    # ================================================================
    # PHASE 1
    # Search-engine discovery
    # ================================================================

    print()
    print(
        "PHASE 1: SEARCH ENGINE DISCOVERY"
    )
    print("-" * 70)

    for policy_type, phrases in POLICY_QUERIES.items():

        if len(documents) >= max_documents:
            break

        for phrase in phrases:

            if len(documents) >= max_documents:
                break

            query = (
                f"site:{target_host} {phrase}"
            )

            print(
                f"Web search query "
                f"[{policy_type}]: {query}"
            )

            results = _search(
                query,
                max_results=SEARCH_RESULTS_PER_QUERY,
            )

            print(
                f"Search results returned: "
                f"{len(results)}"
            )

            for result in results:

                if len(documents) >= max_documents:
                    break

                raw_url = result.get(
                    "url",
                    "",
                ).strip()

                if not raw_url:
                    continue

                candidate_url = (
                    _unwrap_search_url(
                        raw_url
                    )
                )

                if not candidate_url:
                    continue

                candidate_url = (
                    _canonical_url(
                        candidate_url
                    )
                )

                if not candidate_url:
                    continue

                if not _same_site(
                    candidate_url,
                    target_host,
                ):
                    print(
                        f"External search result "
                        f"rejected: {candidate_url}"
                    )
                    continue

                if candidate_url in seen_urls:
                    continue

                seen_urls.add(
                    candidate_url
                )

                score = _classify_result(
                    candidate_url,
                    result.get(
                        "title",
                        "",
                    ),
                    result.get(
                        "snippet",
                        "",
                    ),
                    policy_type,
                )

                if score < MIN_POLICY_SCORE:
                    continue

                print(
                    f"Search discovered candidate "
                    f"[{policy_type}]: "
                    f"{candidate_url}"
                )

                text = _fetch_policy_page(
                    candidate_url
                )

                if not text:
                    continue

                if not _is_policy_content(
                    text,
                    policy_type,
                    candidate_url,
                ):
                    print(
                        f"Fetched search candidate "
                        f"failed policy validation: "
                        f"{candidate_url}"
                    )
                    continue

                document = {
                    "url": candidate_url,
                    "type": policy_type,
                    "content": text,
                    "title": result.get(
                        "title",
                        "",
                    ),
                    "snippet": result.get(
                        "snippet",
                        "",
                    ),
                    "source": "web_search",
                    "discovery_method": (
                        "web_search_then_fetch"
                    ),
                    "complete_page_extracted": True,
                    "search_score": score,
                }

                documents.append(
                    document
                )

                print(
                    f"Web search policy accepted: "
                    f"[{policy_type}] "
                    f"{candidate_url} "
                    f"({len(text)} chars)"
                )

    # ================================================================
    # PHASE 2
    # Deterministic route discovery
    # ================================================================

    if len(documents) < max_documents:

        print()
        print(
            "PHASE 2: DETERMINISTIC POLICY ROUTE DISCOVERY"
        )
        print("-" * 70)

        route_candidates = (
            _build_route_candidates(
                url
            )
        )

        print(
            f"Generated "
            f"{len(route_candidates)} "
            f"policy route candidates"
        )

        for candidate in route_candidates:

            if len(documents) >= max_documents:
                break

            candidate_url = _canonical_url(
                candidate["url"]
            )

            policy_type = candidate["type"]

            if not candidate_url:
                continue

            if not _same_site(
                candidate_url,
                target_host,
            ):
                continue

            if candidate_url in seen_urls:
                continue

            seen_urls.add(
                candidate_url
            )

            print(
                f"Route candidate "
                f"[{policy_type}]: "
                f"{candidate_url}"
            )

            text = _fetch_policy_page(
                candidate_url
            )

            if not text:
                continue

            if not _is_policy_content(
                text,
                policy_type,
                candidate_url,
            ):
                print(
                    f"Route candidate rejected "
                    f"after content validation: "
                    f"{candidate_url}"
                )
                continue

            document = {
                "url": candidate_url,
                "type": policy_type,
                "content": text,
                "title": "",
                "snippet": "",
                "source": "web_search",
                "discovery_method": (
                    "deterministic_policy_route"
                ),
                "complete_page_extracted": True,
                "search_score": 0,
            }

            documents.append(
                document
            )

            print(
                f"Deterministic policy route "
                f"accepted: "
                f"[{policy_type}] "
                f"{candidate_url} "
                f"({len(text)} chars)"
            )

    # ================================================================
    # COMPLETE
    # ================================================================

    print()
    print(
        "=" * 70
    )
    print(
        f"WEB SEARCH FALLBACK COMPLETE: "
        f"{len(documents)} policy documents"
    )
    print(
        "=" * 70
    )

    return documents