import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# ============================================================
# POLICY KEYWORDS
# ============================================================

POLICY_PATTERNS = {
    "terms": [
        "terms",
        "terms of service",
        "terms and conditions",
        "terms-of-service",
        "terms_and_conditions",
        "termsconditions",
        "user agreement",
        "user-agreement",
        "legal terms",
        "service agreement",
    ],

    "privacy": [
        "privacy",
        "privacy policy",
        "privacy notice",
        "privacy-policy",
        "privacy_notice",
        "data privacy",
        "data protection",
    ],

    "cookies": [
        "cookie",
        "cookies",
        "cookie policy",
        "cookie-policy",
        "cookies policy",
    ],
}


# ============================================================
# COMMON POLICY URL PATHS
# ============================================================

COMMON_POLICY_PATHS = {
    "terms": [
        "/terms/",
        "/terms",
        "/terms-of-service/",
        "/terms-of-service",
        "/terms-and-conditions/",
        "/terms-and-conditions",
        "/legal/terms/",
        "/legal/terms",
        "/user-agreement/",
        "/user-agreement",
        "/legal/",
    ],

    "privacy": [
        "/privacy/",
        "/privacy",
        "/privacy-policy/",
        "/privacy-policy",
        "/legal/privacy/",
        "/legal/privacy",
        "/data-privacy/",
        "/data-privacy",
        "/data-protection/",
        "/data-protection",
    ],

    "cookies": [
        "/cookies/",
        "/cookies",
        "/cookie-policy/",
        "/cookie-policy",
        "/legal/cookies/",
        "/legal/cookies",
    ],
}


# ============================================================
# REQUEST HEADERS
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 "
        "Safari/537.36"
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
}


# ============================================================
# DOWNLOAD PAGE
# ============================================================

def get_page(url):
    """
    Download a webpage and return the requests Response object.
    """

    response = requests.get(
        url,
        timeout=15,
        headers=HEADERS,
        allow_redirects=True,
    )

    response.raise_for_status()

    return response


# ============================================================
# NORMALIZE DOMAIN
# ============================================================

def normalize_domain(domain):
    """
    Normalize domains so that:

        www.example.com
        example.com

    are treated as the same domain.
    """

    domain = domain.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain


# ============================================================
# SAME DOMAIN CHECK
# ============================================================

def is_same_domain(url1, url2):
    """
    Check whether two URLs belong to the same base domain.
    """

    domain1 = normalize_domain(
        urlparse(url1).netloc
    )

    domain2 = normalize_domain(
        urlparse(url2).netloc
    )

    return domain1 == domain2


# ============================================================
# POLICY CLASSIFICATION
# ============================================================

def classify_policy(text):
    """
    Determine whether a piece of text is most likely:

        terms
        privacy
        cookies

    Returns:
        "terms"
        "privacy"
        "cookies"
        None
    """

    if not text:
        return None

    text = text.lower()

    scores = {
        "terms": 0,
        "privacy": 0,
        "cookies": 0,
    }

    for category, patterns in POLICY_PATTERNS.items():

        for pattern in patterns:

            if pattern in text:
                scores[category] += 1

    best_category = max(
        scores,
        key=scores.get
    )

    if scores[best_category] == 0:
        return None

    return best_category


# ============================================================
# NORMALIZE URL
# ============================================================

def normalize_url(url):
    """
    Normalize a URL for duplicate comparison.
    """

    parsed = urlparse(url)

    scheme = parsed.scheme.lower()

    netloc = parsed.netloc.lower()

    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path.rstrip("/")

    if not path:
        path = ""

    return (
        f"{scheme}://"
        f"{netloc}"
        f"{path}"
    )


# ============================================================
# ADD POLICY LINK
# ============================================================

def add_policy_link(
    policy_links,
    url,
    policy_type,
    text="",
    source="unknown",
):
    """
    Add a policy link to the collection.

    Duplicate URLs are ignored.
    """

    if not url:
        return

    normalized = normalize_url(url)

    # Check whether this URL already exists.
    for existing in policy_links:

        existing_normalized = normalize_url(
            existing["url"]
        )

        if existing_normalized == normalized:
            return

    policy_links.append({
        "url": url,
        "type": policy_type,
        "text": text,
        "source": source,
    })


# ============================================================
# FIND POLICY LINKS
# ============================================================

def find_policy_links(url):

    print("\nStarting policy discovery...")
    print(f"Website: {url}")

    policy_links = []

    # ========================================================
    # STEP 1
    # Fetch homepage
    # ========================================================

    try:

        response = get_page(url)

        print(
            f"Homepage status: "
            f"{response.status_code}"
        )

        print(
            f"Final URL: "
            f"{response.url}"
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # ====================================================
        # Scan all homepage links
        # ====================================================

        for link in soup.find_all(
            "a",
            href=True
        ):

            href = link.get(
                "href",
                ""
            ).strip()

            if not href:
                continue

            link_text = link.get_text(
                " ",
                strip=True
            )

            # Convert relative URL to absolute URL.
            full_url = urljoin(
                response.url,
                href
            )

            parsed = urlparse(
                full_url
            )

            # Only HTTP / HTTPS
            if parsed.scheme not in (
                "http",
                "https",
            ):
                continue

            # Only same website.
            #
            # Note:
            # www.example.com and example.com
            # are treated as the same domain.
            if not is_same_domain(
                response.url,
                full_url
            ):
                continue

            # Search both the visible link text
            # and the href.
            search_text = (
                f"{link_text} "
                f"{href}"
            ).lower()

            policy_type = classify_policy(
                search_text
            )

            if policy_type:

                add_policy_link(
                    policy_links=policy_links,
                    url=full_url,
                    policy_type=policy_type,
                    text=link_text,
                    source="homepage",
                )

                print(
                    f"Found {policy_type}: "
                    f"{full_url}"
                )

    except requests.RequestException as error:

        print(
            f"Homepage request failed: "
            f"{error}"
        )

    except Exception as error:

        print(
            f"Homepage discovery failed: "
            f"{error}"
        )

    # ========================================================
    # STEP 2
    # Try common policy paths
    # ========================================================

    print(
        "\nChecking common policy URLs..."
    )

    for policy_type, paths in (
        COMMON_POLICY_PATHS.items()
    ):

        for path in paths:

            candidate_url = urljoin(
                url,
                path
            )

            try:

                response = get_page(
                    candidate_url
                )

                # Only accept successful pages.
                if response.status_code != 200:
                    continue

                # Get page text.
                soup = BeautifulSoup(
                    response.text,
                    "html.parser"
                )

                page_text = soup.get_text(
                    " ",
                    strip=True
                )

                # Look at the URL + page text.
                detection_text = (
                    f"{candidate_url} "
                    f"{page_text[:10000]}"
                )

                detected_type = classify_policy(
                    detection_text
                )

                # We specifically tried this category,
                # so accept the page only when the
                # content actually looks like a policy.
                if detected_type:

                    add_policy_link(
                        policy_links=policy_links,
                        url=response.url,
                        policy_type=detected_type,
                        text="",
                        source="common_path",
                    )

                    print(
                        f"Found {detected_type}: "
                        f"{response.url}"
                    )

            except requests.RequestException:
                # Most common paths won't exist.
                # This is normal.
                continue

            except Exception as error:

                print(
                    f"Error checking "
                    f"{candidate_url}: "
                    f"{error}"
                )

    # ========================================================
    # STEP 3
    # Final duplicate removal
    # ========================================================

    unique_links = {}

    for item in policy_links:

        normalized_url = (
            item["url"]
            .rstrip("/")
            .lower()
        )

        if normalized_url not in unique_links:

            unique_links[
                normalized_url
            ] = item

    result = list(
        unique_links.values()
    )

    # ========================================================
    # STEP 4
    # Print result
    # ========================================================

    print(
        "\nPolicy discovery complete."
    )

    print(
        f"Policies found: "
        f"{len(result)}"
    )

    for item in result:

        print(
            f"  [{item['type']}] "
            f"{item['url']}"
        )

    return result