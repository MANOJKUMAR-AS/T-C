from __future__ import annotations

import re
from html import unescape
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse, urldefrag

import requests

from .dynamic_scraper import scrape_dynamic_page
from .static_scraper import scrape_static_page


# ============================================================
# HTTP
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ============================================================
# POLICY PATTERNS
# ============================================================

POLICY_PATTERNS = {
    "privacy": [
        r"\bprivacy\b",
        r"privacy[-_ ]policy",
        r"privacy[-_ ]notice",
        r"privacy[-_ ]statement",
        r"privacypolicy",
        r"data[-_ ]protection",
        r"data[-_ ]privacy",
        r"personal[-_ ]data",
    ],

    "terms": [
        r"\bterms\b",
        r"terms[-_ ]?(and|&)[-_ ]?conditions",
        r"terms[-_ ]?of[-_ ]?(use|service)",
        r"termsofuse",
        r"termsandcondition",
        r"user[-_ ]agreement",
        r"user[-_ ]terms",
        r"legal[-_ ]agreement",
    ],

    "cookies": [
        r"\bcookies?\b",
        r"cookie[-_ ]policy",
        r"cookie[-_ ]notice",
        r"cookies[-_ ]policy",
        r"cookies[-_ ]and[-_ ]tracking",
    ],

    "returns": [
        r"return[-_ ]?refund",
        r"return[-_ ]policy",
        r"refund[-_ ]policy",
        r"\breturns?\b",
        r"\brefunds?\b",
    ],

    "payments": [
        r"\bpayments?\b",
        r"payment[-_ ]policy",
        r"fee[-_ ]payment",
        r"fees[-_ ]payment",
        r"payment[-_ ]terms",
    ],

    "promotions": [
        r"\bpromotions?\b",
        r"promotion[-_ ]policy",
        r"promo[-_ ]policy",
        r"sale[-_ ]policy",
        r"offer[-_ ]terms",
    ],

    "legal": [
        r"legal[-_ ]notice",
        r"legal[-_ ]notices",
        r"\bgrievance\b",
        r"\bimprint\b",
        r"corporate[-_ ]information",
        r"corp[-_ ]info",
    ],
}


# ============================================================
# KNOWN POLICY PATHS
# ============================================================

COMMON_PATHS = [
    # Privacy
    ("/privacy-policy", "privacy"),
    ("/privacy", "privacy"),
    ("/privacypolicy", "privacy"),
    ("/privacy_policy", "privacy"),
    ("/privacy/notice", "privacy"),
    ("/privacy-notice", "privacy"),
    ("/data-privacy", "privacy"),
    ("/data-protection", "privacy"),
    ("/legal/privacy", "privacy"),

    # Terms
    ("/terms", "terms"),
    ("/terms-of-use", "terms"),
    ("/terms-of-service", "terms"),
    ("/terms-and-conditions", "terms"),
    ("/termsandcondition", "terms"),
    ("/termsofuse", "terms"),
    ("/legal/terms", "terms"),
    ("/legal/termsofuse", "terms"),

    # Cookies
    ("/cookie-policy", "cookies"),
    ("/cookies", "cookies"),
    ("/cookies-policy", "cookies"),
    ("/legal/cookies", "cookies"),

    # Returns / refunds
    ("/return-policy", "returns"),
    ("/returns", "returns"),
    ("/refund-policy", "returns"),
    ("/return-refund-policy", "returns"),
    ("/return-refund", "returns"),

    # Payments
    ("/payment-policy", "payments"),
    ("/payments", "payments"),
    ("/fee-payment-policy", "payments"),
    ("/fee-payment-promotion-policy", "payments"),

    # Promotions
    ("/promotion-policy", "promotions"),
    ("/promotions", "promotions"),
    ("/sale-policy", "promotions"),
    ("/ajio-own-sale-policy", "promotions"),

    # General legal
    ("/legal", "legal"),
    ("/legal-notice", "legal"),
    ("/legal/notices", "legal"),
    ("/notices", "legal"),
    ("/grievance", "legal"),
]


# ============================================================
# BAD / NON-POLICY URL SIGNALS
# ============================================================

BAD_URL_WORDS = [
    "legal-bribe",
    "legal-help",
    "legal-support",
    "legal-career",
    "legal-job",
    "legal-news",
    "legal-blog",
    "legal-team",
    "legal-contact",
    "legal-services",
]

BAD_FILE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".css",
    ".js",
    ".map",
    ".woff",
    ".woff2",
    ".ttf",
)


# ============================================================
# TEXT HELPERS
# ============================================================

def _clean(value: str) -> str:
    return re.sub(
        r"\s+",
        " ",
        unescape(value or ""),
    ).strip()


def _host(url: str) -> str:
    try:
        host = (
            urlparse(url).hostname or ""
        ).lower()

        if host.startswith("www."):
            host = host[4:]

        return host

    except Exception:
        return ""


def _same_site(
    source: str,
    candidate: str,
) -> bool:
    source_host = _host(source)
    candidate_host = _host(candidate)

    if not source_host or not candidate_host:
        return False

    return (
        source_host == candidate_host
        or candidate_host.endswith("." + source_host)
    )


def _normalize_url(
    url: str,
    base_url: str = "",
) -> str:
    if not url:
        return ""

    url = unescape(str(url)).strip()

    if not url:
        return ""

    if base_url:
        url = urljoin(base_url, url)

    url, _ = urldefrag(url)

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc:
        return ""

    return url


# ============================================================
# URL CLASSIFICATION
# ============================================================

def classify_policy(
    url: str,
    label: str = "",
    content: str = "",
) -> str:
    """
    Classify a page as privacy, terms, cookies, returns,
    payments, promotions, or legal.

    URL and link-label signals are intentionally stronger than
    generic words appearing in page content.
    """

    url_text = _clean(url).lower()
    label_text = _clean(label).lower()

    url_and_label = f"{url_text} {label_text}"

    # --------------------------------------------------------
    # Strong URL / label classification
    # --------------------------------------------------------

    # Privacy
    if any(
        re.search(pattern, url_and_label)
        for pattern in POLICY_PATTERNS["privacy"]
    ):
        return "privacy"

    # Terms
    if any(
        re.search(pattern, url_and_label)
        for pattern in POLICY_PATTERNS["terms"]
    ):
        return "terms"

    # Cookies
    #
    # Cookie URLs are accepted here, but the page still has to
    # pass substantive validation before becoming a document.
    if any(
        re.search(pattern, url_and_label)
        for pattern in POLICY_PATTERNS["cookies"]
    ):
        return "cookies"

    # Returns
    if any(
        re.search(pattern, url_and_label)
        for pattern in POLICY_PATTERNS["returns"]
    ):
        return "returns"

    # Payments
    if any(
        re.search(pattern, url_and_label)
        for pattern in POLICY_PATTERNS["payments"]
    ):
        return "payments"

    # Promotions
    if any(
        re.search(pattern, url_and_label)
        for pattern in POLICY_PATTERNS["promotions"]
    ):
        return "promotions"

    # Legal
    if any(
        re.search(pattern, url_and_label)
        for pattern in POLICY_PATTERNS["legal"]
    ):
        return "legal"

    # --------------------------------------------------------
    # Content classification
    # --------------------------------------------------------

    text = _clean(content[:16000]).lower()

    if not text:
        return ""

    combined = f"{url_and_label} {text}"

    if re.search(
        r"\bprivacy\s+(policy|notice|statement)\b",
        combined,
    ):
        return "privacy"

    if re.search(
        r"\bterms\s+(of\s+use|of\s+service)\b",
        combined,
    ):
        return "terms"

    if re.search(
        r"\bterms\s+and\s+conditions\b",
        combined,
    ):
        return "terms"

    if re.search(
        r"\buser\s+agreement\b",
        combined,
    ):
        return "terms"

    if re.search(
        r"\bcookie\s+(policy|notice)\b",
        combined,
    ):
        return "cookies"

    if re.search(
        r"\bcookies?\s+and\s+tracking\b",
        combined,
    ):
        return "cookies"

    if re.search(
        r"\breturn(s)?\s+and\s+refund(s)?\b",
        combined,
    ):
        return "returns"

    if re.search(
        r"\brefund\s+policy\b",
        combined,
    ):
        return "returns"

    if re.search(
        r"\bpayment\s+(policy|terms)\b",
        combined,
    ):
        return "payments"

    if re.search(
        r"\bpromotion\s+policy\b",
        combined,
    ):
        return "promotions"

    if re.search(
        r"\bsale\s+policy\b",
        combined,
    ):
        return "promotions"

    if re.search(
        r"\bgrievance\b",
        combined,
    ):
        return "legal"

    if re.search(
        r"\blegal\s+(notice|notices)\b",
        combined,
    ):
        return "legal"

    return ""


# ============================================================
# CANDIDATE VALIDATION
# ============================================================

def _is_bad_candidate(url: str) -> bool:
    low = (url or "").lower()

    if any(
        word in low
        for word in BAD_URL_WORDS
    ):
        return True

    parsed = urlparse(low)

    path = parsed.path or ""

    if path.endswith(BAD_FILE_EXTENSIONS):
        return True

    return False


def _substantive(
    content: str,
    expected: str = "",
) -> bool:
    """
    Determine whether extracted content looks like a real
    policy document rather than a homepage/shell/error page.
    """

    content = _clean(content)

    if len(content) < 500:
        return False

    low = content.lower()

    signals = {
        "privacy": [
            "privacy policy",
            "privacy notice",
            "personal information",
            "personal data",
            "data protection",
            "collect your information",
        ],

        "terms": [
            "terms and conditions",
            "terms of use",
            "terms of service",
            "user agreement",
            "these terms",
        ],

        "cookies": [
            "cookie policy",
            "cookie notice",
            "cookies",
            "tracking technologies",
            "similar technologies",
        ],

        "returns": [
            "return policy",
            "returns",
            "refund policy",
            "refund",
            "exchange",
        ],

        "payments": [
            "payment policy",
            "payment terms",
            "payments",
            "fees",
            "transaction",
        ],

        "promotions": [
            "promotion",
            "promotional",
            "sale policy",
            "offer terms",
            "discount",
        ],

        "legal": [
            "legal notice",
            "grievance",
            "corporate information",
            "legal information",
            "notice",
        ],
    }

    expected_signals = signals.get(
        expected,
        [],
    )

    if expected_signals:
        if not any(
            signal in low
            for signal in expected_signals
        ):
            return False

    # Reject obvious generic homepage shells.
    homepage_shell_signals = [
        "shop men",
        "shop women",
        "shop kids",
        "new arrivals",
        "trending now",
        "download the app",
    ]

    shell_hits = sum(
        1
        for signal in homepage_shell_signals
        if signal in low
    )

    if shell_hits >= 3 and len(content) < 5000:
        return False

    return True


# ============================================================
# HTML LINK EXTRACTION
# ============================================================

def _extract_links(
    html: str,
    base: str,
) -> List[Dict[str, Any]]:
    """
    Extract candidate policy links from raw HTML.
    """

    output: List[Dict[str, Any]] = []

    if not html:
        return output

    pattern = re.compile(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>'
        r'(.*?)'
        r'</a>',
        flags=re.I | re.S,
    )

    for match in pattern.finditer(html):
        href = unescape(
            match.group(1)
        ).strip()

        label = _clean(
            re.sub(
                r"<[^>]+>",
                " ",
                match.group(2),
            )
        )

        full_url = _normalize_url(
            href,
            base,
        )

        if not full_url:
            continue

        kind = classify_policy(
            full_url,
            label,
        )

        if not kind:
            continue

        if _is_bad_candidate(full_url):
            continue

        output.append(
            {
                "url": full_url,
                "type": kind,
                "text": label,
                "source": "backend_html",
            }
        )

    return output


# ============================================================
# CANDIDATE CREATION
# ============================================================

def _candidate(
    url: str,
    kind: str,
    source: str = "common_path",
) -> Dict[str, Any]:
    return {
        "url": url,
        "type": kind,
        "text": "",
        "source": source,
    }


# ============================================================
# BACKEND VALIDATION
# ============================================================

def _validate_candidate(
    item: Dict[str, Any],
) -> Dict[str, Any] | None:

    url = _normalize_url(
        item.get("url", "")
    )

    if not url:
        return None

    if _is_bad_candidate(url):
        return None

    expected = (
        item.get("type")
        or classify_policy(
            url,
            item.get("text", ""),
        )
    )

    if not expected:
        return None

    # --------------------------------------------------------
    # Static extraction
    # --------------------------------------------------------

    try:
        content = scrape_static_page(url)
    except Exception:
        content = ""

    if _substantive(
        content,
        expected,
    ):
        return {
            **item,
            "url": url,
            "type": classify_policy(
                url,
                item.get("text", ""),
                content,
            ) or expected,
            "content": content,
            "source": item.get(
                "source",
                "backend_static",
            ),
        }

    # --------------------------------------------------------
    # Dynamic extraction
    # --------------------------------------------------------

    try:
        content = scrape_dynamic_page(url)
    except Exception:
        content = ""

    if _substantive(
        content,
        expected,
    ):
        return {
            **item,
            "url": url,
            "type": classify_policy(
                url,
                item.get("text", ""),
                content,
            ) or expected,
            "content": content,
            "source": item.get(
                "source",
                "backend_dynamic",
            ),
        }

    return None


# ============================================================
# MAIN POLICY DISCOVERY
# ============================================================

def find_policy_links(
    url: str,
    browser_links: List[Dict[str, Any]] | None = None,
    browser_documents: List[Dict[str, Any]] | None = None,
    browser_all_links: List[Dict[str, Any]] | None = None,
    browser_page_text: str = "",
    browser_title: str = "",
) -> List[Dict[str, Any]]:

    candidates: List[Dict[str, Any]] = []

    # ========================================================
    # 1. Browser documents
    # ========================================================

    for item in browser_documents or []:
        if not isinstance(item, dict):
            continue

        item_url = _normalize_url(
            item.get("url", ""),
            url,
        )

        if not item_url:
            continue

        if not _same_site(url, item_url):
            continue

        item_copy = dict(item)

        item_copy["url"] = item_url

        item_copy["type"] = (
            item_copy.get("type")
            or classify_policy(
                item_url,
                item_copy.get("title", ""),
                item_copy.get("content", ""),
            )
        )

        item_copy["source"] = item_copy.get(
            "source",
            "browser_document",
        )

        candidates.append(item_copy)

    # ========================================================
    # 2. Browser policy links
    # ========================================================

    for item in browser_links or []:
        if not isinstance(item, dict):
            continue

        item_url = _normalize_url(
            item.get("url", ""),
            url,
        )

        if not item_url:
            continue

        if not _same_site(url, item_url):
            continue

        if _is_bad_candidate(item_url):
            continue

        item_copy = dict(item)

        item_copy["url"] = item_url

        item_copy["type"] = (
            item_copy.get("type")
            or classify_policy(
                item_url,
                item_copy.get("text", ""),
                "",
            )
        )

        if not item_copy["type"]:
            continue

        item_copy["source"] = item_copy.get(
            "source",
            "browser_link",
        )

        candidates.append(item_copy)

    # ========================================================
    # 3. Scan ALL browser links
    # ========================================================

    for item in browser_all_links or []:
        if not isinstance(item, dict):
            continue

        item_url = _normalize_url(
            item.get("url", ""),
            url,
        )

        if not item_url:
            continue

        if not _same_site(url, item_url):
            continue

        if _is_bad_candidate(item_url):
            continue

        label = " ".join(
            str(item.get(key, ""))
            for key in (
                "text",
                "title",
                "aria",
            )
        )

        kind = classify_policy(
            item_url,
            label,
        )

        if not kind:
            continue

        candidates.append(
            {
                "url": item_url,
                "type": kind,
                "text": label,
                "source": "browser_all_links",
            }
        )

    # ========================================================
    # 4. Browser page text/title
    #
    # If the actual page itself is a policy page, recognize it.
    # This is especially useful when Chrome is already sitting
    # directly on a policy URL.
    # ========================================================

    page_kind = classify_policy(
        url,
        browser_title,
        browser_page_text,
    )

    if page_kind:
        if _substantive(
            browser_page_text,
            page_kind,
        ):
            candidates.append(
                {
                    "url": url,
                    "type": page_kind,
                    "text": browser_title,
                    "content": browser_page_text,
                    "source": "browser_current_page",
                }
            )

    # ========================================================
    # 5. Backend homepage HTML
    # ========================================================

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15,
            allow_redirects=True,
        )

        if (
            response.ok
            and "text/html"
            in (
                response.headers.get(
                    "content-type",
                    "",
                ).lower()
            )
        ):
            candidates.extend(
                _extract_links(
                    response.text,
                    response.url,
                )
            )

    except Exception:
        pass

    # ========================================================
    # 6. Common policy paths
    #
    # These are discovery candidates only.
    # They still require validation.
    # ========================================================

    parsed = urlparse(url)

    if parsed.scheme and parsed.netloc:
        origin = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}"
        )

        for path, kind in COMMON_PATHS:
            candidate_url = _normalize_url(
                urljoin(
                    origin,
                    path,
                )
            )

            if not candidate_url:
                continue

            candidates.append(
                _candidate(
                    candidate_url,
                    kind,
                )
            )

    # ========================================================
    # 7. Deduplicate candidates
    # ========================================================

    unique: Dict[str, Dict[str, Any]] = {}

    for item in candidates:
        item_url = _normalize_url(
            item.get("url", ""),
            url,
        )

        if not item_url:
            continue

        if not _same_site(url, item_url):
            continue

        if _is_bad_candidate(item_url):
            continue

        key = item_url.rstrip("/").lower()

        if key not in unique:
            item_copy = dict(item)
            item_copy["url"] = item_url
            unique[key] = item_copy

    # ========================================================
    # 8. Validate candidates
    # ========================================================

    results: List[Dict[str, Any]] = []

    for item in unique.values():

        content = (
            item.get("content")
            or item.get("text_content")
            or ""
        )

        expected = (
            item.get("type")
            or classify_policy(
                item.get("url", ""),
                item.get("text", ""),
                content,
            )
        )

        # ----------------------------------------------------
        # Browser already supplied substantive content
        # ----------------------------------------------------

        if content and _substantive(
            content,
            expected,
        ):
            item["content"] = content

            item["type"] = (
                classify_policy(
                    item.get("url", ""),
                    item.get("text", ""),
                    content,
                )
                or expected
            )

            results.append(item)
            continue

        # ----------------------------------------------------
        # Otherwise use static + dynamic backend validation
        # ----------------------------------------------------

        validated = _validate_candidate(item)

        if validated:
            results.append(validated)

    # ========================================================
    # 9. Final deduplication
    # ========================================================

    final: Dict[str, Dict[str, Any]] = {}

    for item in results:

        item_url = _normalize_url(
            item.get("url", "")
        )

        if not item_url:
            continue

        key = item_url.rstrip("/").lower()

        if key not in final:
            final[key] = item
            continue

        existing = final[key]

        if len(
            item.get("content", "")
        ) > len(
            existing.get("content", "")
        ):
            final[key] = item

    return list(final.values())