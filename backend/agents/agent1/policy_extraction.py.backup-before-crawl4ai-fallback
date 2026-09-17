from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any, Dict, List
from urllib.parse import urlparse, urlunparse

import httpx

from scraping.policy_detector import find_policy_links

try:
    from scraping.web_search_fallback import (
        search_policy_documents,
    )
except ImportError:
    search_policy_documents = None


class PolicyExtractionAgent:

    def __init__(self):
        self.name = "Policy Extraction Agent"

        # Minimum amount of text required for a usable policy.
        self.MIN_POLICY_CHARS = 500

        # Never allow thousands of links to become backend jobs.
        self.MAX_DOCUMENTS = 20
        self.MAX_BACKEND_CANDIDATES = 8

        # Crawl4AI settings.
        self.CRAWL4AI_TIMEOUT = 30
        self.CRAWL4AI_WAIT_SECONDS = 2

        # Jina Reader settings.
        self.JINA_TIMEOUT = 35

    # ============================================================
    # MAIN
    # ============================================================

    def run(
        self,
        url: str,
        browser_links: List[Dict[str, Any]] | None = None,
        browser_documents: List[Dict[str, Any]] | None = None,
        browser_all_links: List[Dict[str, Any]] | None = None,
        browser_page_text: str = "",
        browser_title: str = "",
    ) -> Dict[str, Any]:

        browser_links = browser_links or []
        browser_documents = browser_documents or []
        browser_all_links = browser_all_links or []

        source_url = str(url or "").strip()

        print()
        print("=" * 70)
        print("AGENT 1 - UNIVERSAL POLICY DISCOVERY + EXTRACTION")
        print("=" * 70)
        print(f"URL: {source_url}")
        print(f"Browser links: {len(browser_links)}")
        print(f"Browser all links: {len(browser_all_links)}")
        print(f"Browser documents: {len(browser_documents)}")
        print(f"Browser page text: {len(browser_page_text)}")
        print("=" * 70)

        result: Dict[str, Any] = {
            "agent": self.name,
            "source_url": source_url,
            "status": "complete",
            "policy_count": 0,
            "document_count": 0,
            "documents": [],
            "policy_documents": [],
            "policy_pages": [],
            "browser_documents": [],
            "summary": {
                "terms": 0,
                "privacy": 0,
                "cookies": 0,
                "legal": 0,
                "returns": 0,
                "payments": 0,
                "promotions": 0,
            },
        }

        # ========================================================
        # 1. BACKEND POLICY DETECTOR
        # ========================================================

        detector_candidates: List[Dict[str, Any]] = []

        try:
            detector_result = self._run_policy_detector(
                source_url,
                browser_links,
            )

            if isinstance(detector_result, list):
                detector_candidates = detector_result

        except Exception as exc:
            print(f"Policy detector failed: {exc}")

        print(
            f"Policy detector candidates: "
            f"{len(detector_candidates)}"
        )

        # ========================================================
        # 2. COLLECT POLICY CANDIDATES
        # ========================================================

        candidates: List[Dict[str, Any]] = []

        # --------------------------------------------------------
        # Backend detector candidates
        # --------------------------------------------------------

        for item in detector_candidates:

            normalized = self._normalize_candidate(
                item,
                source_url,
            )

            if not normalized:
                continue

            if not self._is_policy_candidate(
                normalized
            ):
                print(
                    "Rejected detector candidate: "
                    f"{normalized['url']}"
                )
                continue

            candidates.append(normalized)

        # --------------------------------------------------------
        # Browser policy links
        # --------------------------------------------------------

        browser_policy_links = 0
        browser_rejected_links = 0

        combined_browser_links = (
            list(browser_links)
            + list(browser_all_links)
        )

        for item in combined_browser_links:

            normalized = self._normalize_candidate(
                item,
                source_url,
            )

            if not normalized:
                continue

            if not self._is_policy_candidate(
                normalized
            ):
                browser_rejected_links += 1
                continue

            browser_policy_links += 1
            candidates.append(normalized)

        print(
            f"Browser policy links accepted: "
            f"{browser_policy_links}"
        )

        print(
            f"Browser commerce/non-policy links rejected: "
            f"{browser_rejected_links}"
        )

        # --------------------------------------------------------
        # Browser-rendered documents
        # --------------------------------------------------------

        browser_document_count = 0

        for item in browser_documents:

            normalized = self._normalize_candidate(
                item,
                source_url,
            )

            if not normalized:
                continue

            if not self._is_policy_candidate(
                normalized
            ):
                print(
                    "Rejected browser document URL: "
                    f"{normalized['url']}"
                )
                continue

            if not self._is_real_policy_document(
                normalized
            ):
                print(
                    "Rejected browser document content: "
                    f"{normalized['url']}"
                )
                continue

            browser_document_count += 1
            candidates.append(normalized)

        print(
            f"Browser policy documents accepted: "
            f"{browser_document_count}"
        )

        # --------------------------------------------------------
        # Additional discovery directly from browser links.
        #
        # This specifically helps sites such as AJIO where
        # /help/termsAndCondition may be present in the complete
        # link list but the old detector rejected it.
        # --------------------------------------------------------

        discovered_from_all_links = (
            self._discover_policy_candidates_from_browser_links(
                source_url,
                browser_all_links,
            )
        )

        print(
            "Policy candidates discovered directly from "
            f"browser all-links: {len(discovered_from_all_links)}"
        )

        candidates.extend(
            discovered_from_all_links
        )

        # ========================================================
        # 3. DEDUPLICATE
        # ========================================================

        candidates = self._deduplicate_candidates(
            candidates
        )

        print(
            f"Unique policy candidates after hard filter: "
            f"{len(candidates)}"
        )

        # ========================================================
        # 4. EXTRACT
        # ========================================================

        documents: List[Dict[str, Any]] = []

        backend_attempts = 0

        for candidate in candidates:

            if len(documents) >= self.MAX_DOCUMENTS:
                break

            policy_url = candidate["url"]
            policy_type = candidate["type"]
            source = candidate.get(
                "source",
                "unknown",
            )

            print()
            print("-" * 70)
            print(f"Candidate: {policy_url}")
            print(f"Initial type: {policy_type}")
            print(f"Source: {source}")

            # ----------------------------------------------------
            # HARD SAFETY GATE
            # ----------------------------------------------------

            if not self._is_policy_candidate(candidate):
                print(
                    "SKIPPED: candidate failed policy URL gate."
                )
                continue

            # ----------------------------------------------------
            # Browser-provided content
            # ----------------------------------------------------

            content = self._candidate_content(
                candidate
            )

            if (
                content
                and len(content) >= self.MIN_POLICY_CHARS
            ):

                if self._is_real_policy_content(
                    policy_url,
                    content,
                    policy_type,
                ):

                    document = self._build_document(
                        policy_url,
                        policy_type,
                        content,
                        source,
                    )

                    if document:
                        documents.append(document)

                        print(
                            "Browser extraction accepted."
                        )

                        continue

                print(
                    "Browser content rejected: "
                    "not substantive policy content."
                )

            # ----------------------------------------------------
            # Crawl4AI + Playwright / Jina fallback
            # ----------------------------------------------------

            if backend_attempts >= self.MAX_BACKEND_CANDIDATES:

                print(
                    "Backend fallback limit reached. "
                    "Skipping candidate."
                )

                continue

            backend_attempts += 1

            fallback_content, fallback_source = (
                self._try_backend_extraction(
                    policy_url
                )
            )

            if (
                fallback_content
                and len(fallback_content) >= self.MIN_POLICY_CHARS
                and self._is_real_policy_content(
                    policy_url,
                    fallback_content,
                    policy_type,
                )
            ):

                document = self._build_document(
                    policy_url,
                    policy_type,
                    fallback_content,
                    fallback_source,
                )

                if document:
                    documents.append(document)

                    print(
                        f"{fallback_source} extraction accepted."
                    )

                    continue

            print(
                "Policy extraction failed."
            )

        # ========================================================
        # 5. WEB SEARCH FALLBACK
        #
        # Final fallback after browser, Crawl4AI and Jina fail.
        # ========================================================

        if (
            not documents
            and search_policy_documents
        ):

            print()
            print("=" * 70)
            print("WEB SEARCH FALLBACK ACTIVATED")
            print("=" * 70)

            try:

                search_docs = search_policy_documents(
                    source_url,
                    max_documents=self.MAX_DOCUMENTS,
                )

                if isinstance(
                    search_docs,
                    list,
                ):

                    for item in search_docs:

                        if (
                            len(documents)
                            >= self.MAX_DOCUMENTS
                        ):
                            break

                        if not isinstance(
                            item,
                            dict,
                        ):
                            continue

                        search_url = str(
                            item.get(
                                "url",
                                "",
                            )
                            or ""
                        ).strip()

                        search_type = (
                            self._normalize_type(
                                item.get(
                                    "type",
                                    "other",
                                )
                            )
                        )

                        search_content = str(
                            item.get(
                                "content",
                                "",
                            )
                            or ""
                        ).strip()

                        if not search_url:
                            continue

                        source_host = (
                            urlparse(
                                source_url
                            ).hostname
                            or ""
                        ).lower()

                        result_host = (
                            urlparse(
                                search_url
                            ).hostname
                            or ""
                        ).lower()

                        source_host = source_host.removeprefix(
                            "www."
                        )

                        result_host = result_host.removeprefix(
                            "www."
                        )

                        if not (
                            result_host == source_host
                            or result_host.endswith(
                                "." + source_host
                            )
                        ):
                            print(
                                "Web search result rejected "
                                "because it is external: "
                                f"{search_url}"
                            )
                            continue

                        candidate = {
                            "url": search_url,
                            "type": search_type,
                            "content": search_content,
                            "title": item.get(
                                "title",
                                "",
                            ),
                            "source": "web_search",
                        }

                        if not self._is_policy_candidate(
                            candidate
                        ):
                            print(
                                "Web search candidate rejected "
                                "by policy URL gate: "
                                f"{search_url}"
                            )
                            continue

                        if (
                            len(search_content)
                            < self.MIN_POLICY_CHARS
                        ):
                            print(
                                "Web search evidence too short: "
                                f"{search_url}"
                            )
                            continue

                        if not self._is_real_policy_content(
                            search_url,
                            search_content,
                            search_type,
                        ):
                            print(
                                "Web search evidence rejected "
                                "by policy content validation: "
                                f"{search_url}"
                            )
                            continue

                        document = self._build_document(
                            search_url,
                            search_type,
                            search_content,
                            "web_search",
                        )

                        if document:

                            document[
                                "complete_page_extracted"
                            ] = False

                            document[
                                "search_query"
                            ] = item.get(
                                "search_query",
                                "",
                            )

                            document[
                                "search_title"
                            ] = item.get(
                                "search_title",
                                "",
                            )

                            document[
                                "search_snippet"
                            ] = item.get(
                                "search_snippet",
                                "",
                            )

                            documents.append(
                                document
                            )

                            print(
                                "Web search evidence accepted: "
                                f"[{search_type}] "
                                f"{search_url} "
                                f"-> "
                                f"{len(search_content)} chars"
                            )

            except Exception as exc:

                print(
                    f"Web search fallback failed: {exc}"
                )

        # ========================================================
        # 6. FINAL DEDUPLICATION
        # ========================================================

        documents = self._deduplicate_documents(
            documents
        )

        # ========================================================
        # 7. SUMMARY
        # ========================================================

        summary = {
            "terms": 0,
            "privacy": 0,
            "cookies": 0,
            "legal": 0,
            "returns": 0,
            "payments": 0,
            "promotions": 0,
        }

        for document in documents:

            policy_type = self._normalize_type(
                document.get("type")
            )

            if policy_type in summary:
                summary[policy_type] += 1
            else:
                summary["legal"] += 1

        result["documents"] = documents
        result["policy_documents"] = documents
        result["policy_pages"] = documents
        result["browser_documents"] = documents

        result["policy_count"] = len(documents)
        result["document_count"] = len(documents)
        result["summary"] = summary

        # ========================================================
        # 8. FINAL LOG
        # ========================================================

        print()
        print("=" * 70)
        print(
            f"AGENT 1 COMPLETE: "
            f"{len(documents)} policy documents"
        )
        print("=" * 70)

        for index, document in enumerate(
            documents,
            start=1,
        ):

            print(
                f"[{index}] "
                f"[{document['type']}] "
                f"{document['url']} "
                f"-> "
                f"{len(document['content'])} chars "
                f"({document.get('source', 'unknown')})"
            )

        return result

    # ============================================================
    # POLICY DETECTOR COMPATIBILITY
    # ============================================================

    def _run_policy_detector(
        self,
        source_url: str,
        browser_links: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        try:

            result = find_policy_links(
                source_url,
                browser_links,
            )

            if isinstance(result, list):
                return result

        except TypeError:
            pass

        result = find_policy_links(
            source_url
        )

        if isinstance(result, list):
            return result

        return []

    # ============================================================
    # DIRECT BROWSER-LINK POLICY DISCOVERY
    # ============================================================

    def _discover_policy_candidates_from_browser_links(
        self,
        source_url: str,
        browser_all_links: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        candidates: List[Dict[str, Any]] = []

        seen = set()

        for item in browser_all_links:

            normalized = self._normalize_candidate(
                item,
                source_url,
            )

            if not normalized:
                continue

            url = normalized["url"]

            canonical = self._canonical_url(
                url
            )

            if canonical in seen:
                continue

            seen.add(canonical)

            if self._looks_like_policy_url(
                url
            ):

                if self._looks_like_commerce_page(
                    url
                ):
                    continue

                normalized["source"] = (
                    normalized.get("source")
                    if normalized.get("source") != "unknown"
                    else "browser_all_links"
                )

                candidates.append(
                    normalized
                )

        return candidates

    # ============================================================
    # NORMALIZE CANDIDATE
    # ============================================================

    def _normalize_candidate(
        self,
        item: Any,
        source_url: str,
    ) -> Dict[str, Any] | None:

        if not isinstance(item, dict):
            return None

        raw_url = (
            item.get("url")
            or item.get("href")
            or item.get("source_url")
        )

        if not raw_url:
            return None

        raw_url = str(raw_url).strip()

        if not raw_url:
            return None

        # Relative URL
        if raw_url.startswith("/"):

            parsed_source = urlparse(
                source_url
            )

            raw_url = (
                f"{parsed_source.scheme}://"
                f"{parsed_source.netloc}"
                f"{raw_url}"
            )

        # Protocol-relative URL
        elif raw_url.startswith("//"):

            parsed_source = urlparse(
                source_url
            )

            raw_url = (
                f"{parsed_source.scheme}:"
                f"{raw_url}"
            )

        try:
            parsed = urlparse(raw_url)
        except Exception:
            return None

        if parsed.scheme.lower() not in (
            "http",
            "https",
        ):
            return None

        if not parsed.netloc:
            return None

        normalized_url = urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path or "/",
                "",
                parsed.query,
                "",
            )
        )

        policy_type = self._normalize_type(
            item.get("type")
        )

        if policy_type == "other":
            policy_type = self._classify_url(
                normalized_url
            )

        content = str(
            item.get("content")
            or item.get("text")
            or ""
        ).strip()

        title = str(
            item.get("title")
            or item.get("name")
            or ""
        ).strip()

        source = str(
            item.get("source")
            or item.get("source_type")
            or "unknown"
        ).strip()

        return {
            "url": normalized_url,
            "type": policy_type,
            "content": content,
            "title": title,
            "source": source,
        }

    # ============================================================
    # NORMALIZE TYPE
    # ============================================================

    def _normalize_type(
        self,
        value: Any,
    ) -> str:

        value = str(
            value or ""
        ).strip().lower()

        aliases = {
            "terms and conditions": "terms",
            "terms & conditions": "terms",
            "terms-of-use": "terms",
            "terms_of_use": "terms",
            "terms of use": "terms",
            "terms of service": "terms",
            "terms-of-service": "terms",

            "privacy policy": "privacy",
            "privacy-policy": "privacy",
            "privacy notice": "privacy",

            "cookie policy": "cookies",
            "cookie-policy": "cookies",
            "cookies policy": "cookies",

            "return": "returns",
            "refund": "returns",
            "return policy": "returns",
            "refund policy": "returns",
            "return/refund": "returns",

            "fee": "payments",
            "payment": "payments",
            "payment policy": "payments",

            "promotion": "promotions",
            "promotions": "promotions",

            "legal / other policy": "legal",
        }

        return aliases.get(
            value,
            value
            if value in {
                "terms",
                "privacy",
                "cookies",
                "legal",
                "returns",
                "payments",
                "promotions",
            }
            else "other",
        )

    # ============================================================
    # URL CLASSIFICATION
    # ============================================================

    def _classify_url(
        self,
        url: str,
    ) -> str:

        path = (
            urlparse(url)
            .path
            .lower()
        )

        compact = re.sub(
            r"[^a-z0-9]+",
            "",
            path,
        )

        if (
            "privacy" in compact
            or "dataprotection" in compact
            or "privacynotice" in compact
        ):
            return "privacy"

        if "cookie" in compact:
            return "cookies"

        if (
            "termsandconditions" in compact
            or "termsofuse" in compact
            or "termsofservice" in compact
            or "useragreement" in compact
            or compact.endswith("terms")
            or compact.endswith("termsconditions")
        ):
            return "terms"

        if (
            "return" in compact
            or "refund" in compact
            or "cancellation" in compact
        ):
            return "returns"

        if (
            "payment" in compact
            or "payments" in compact
            or "fees" in compact
        ):
            return "payments"

        if (
            "promotion" in compact
            or "promotions" in compact
            or "offerterms" in compact
        ):
            return "promotions"

        if (
            "legal" in compact
            or "disclaimer" in compact
            or "agreement" in compact
        ):
            return "legal"

        if (
            compact == "policy"
            or compact.endswith("policy")
        ):
            return "legal"

        return "other"

    # ============================================================
    # POLICY URL DETECTION
    # ============================================================

    def _looks_like_policy_url(
        self,
        url: str,
    ) -> bool:

        parsed = urlparse(url)

        path = parsed.path.lower()

        compact = re.sub(
            r"[^a-z0-9]+",
            "",
            path,
        )

        # --------------------------------------------------------
        # Commerce routes are never policy routes.
        #
        # Check this FIRST because pages such as
        # /brands/legal-bribe/c/12329 contain "legal" but are
        # ordinary commerce pages.
        # --------------------------------------------------------

        if self._looks_like_commerce_page(url):
            return False

        # --------------------------------------------------------
        # Strong policy keywords.
        #
        # Handles:
        # terms
        # terms-and-conditions
        # termsAndCondition
        # privacyPolicy
        # privacypolicy
        # return-refund
        # cancellationPolicy
        # --------------------------------------------------------

        policy_keywords = [
            "terms",
            "termsandcondition",
            "termsandconditions",
            "termsofuse",
            "termsofservice",
            "useragreement",

            "privacy",
            "privacypolicy",
            "privacynotice",
            "dataprotection",

            "cookie",
            "cookies",

            "return",
            "returns",
            "refund",
            "refunds",
            "returnrefund",
            "cancellation",

            "paymentpolicy",
            "payment",
            "payments",
            "fees",

            "promotionpolicy",
            "promotions",
            "promotionterms",

            "legal",
            "disclaimer",
            "agreement",
        ]

        if any(
            keyword in compact
            for keyword in policy_keywords
        ):
            return True

        # Generic policy routes.
        if (
            compact == "policy"
            or compact.endswith("policy")
        ):
            return True

        # Common legal/policy endpoints.
        policy_endpoints = {
            "/terms",
            "/terms/",
            "/privacy",
            "/privacy/",
            "/cookies",
            "/cookies/",
            "/legal",
            "/legal/",
            "/refund",
            "/refund/",
            "/returns",
            "/returns/",
        }

        if path in policy_endpoints:
            return True

        return False

    # ============================================================
    # HARD POLICY CANDIDATE GATE
    # ============================================================

    def _is_policy_candidate(
        self,
        candidate: Dict[str, Any],
    ) -> bool:

        url = str(
            candidate.get("url", "")
        ).strip()

        if not url:
            return False

        if self._looks_like_commerce_page(url):
            return False

        policy_type = self._normalize_type(
            candidate.get("type")
        )

        if self._looks_like_policy_url(url):
            return True

        # A detector may explicitly classify a URL as policy,
        # but don't trust "payments" or "legal" by themselves.
        if policy_type in {
            "terms",
            "privacy",
            "cookies",
            "returns",
            "promotions",
        }:
            return True

        path = (
            urlparse(url)
            .path
            .lower()
        )

        policy_path_patterns = [
            "privacy",
            "cookie",
            "cookies",
            "terms",
            "termsofuse",
            "termsofservice",
            "policy",
            "legal",
            "agreement",
            "refund",
            "return",
            "cancellation",
            "payment-policy",
            "payment_policy",
            "fees",
            "promotion",
            "promotions",
        ]

        return any(
            pattern in path
            for pattern in policy_path_patterns
        )

    # ============================================================
    # REAL POLICY DOCUMENT
    # ============================================================

    def _is_real_policy_document(
        self,
        candidate: Dict[str, Any],
    ) -> bool:

        if not self._is_policy_candidate(
            candidate
        ):
            return False

        content = str(
            candidate.get("content", "")
            or ""
        ).strip()

        if not content:
            return False

        return self._is_real_policy_content(
            candidate["url"],
            content,
            self._normalize_type(
                candidate.get("type")
            ),
        )

    # ============================================================
    # POLICY CONTENT VALIDATION
    # ============================================================

    def _is_real_policy_content(
        self,
        url: str,
        content: str,
        policy_type: str,
    ) -> bool:

        text = re.sub(
            r"\s+",
            " ",
            str(content or ""),
        ).strip()

        if len(text) < self.MIN_POLICY_CHARS:
            return False

        lower = text.lower()

        # --------------------------------------------------------
        # Commerce signals
        # --------------------------------------------------------

        commerce_signals = [
            "sort by popularity",
            "add to bag",
            "add to cart",
            "buy now",
            "shop now",
            "regular price",
            "discounted price",
            "bestseller",
            "featured products",
            "all products",
            "product listing",
            "products online",
            "filter by",
        ]

        commerce_hits = sum(
            1
            for signal in commerce_signals
            if signal in lower
        )

        if commerce_hits >= 2:
            return False

        # --------------------------------------------------------
        # Policy semantic signals
        # --------------------------------------------------------

        policy_signal_groups = {

            "terms": [
                "terms and conditions",
                "terms of use",
                "terms of service",
                "agreement",
                "you agree",
                "conditions of use",
                "user agreement",
                "govern your use",
                "these terms",
            ],

            "privacy": [
                "privacy policy",
                "privacy notice",
                "personal information",
                "personal data",
                "collect your information",
                "data protection",
                "processing of personal data",
                "information we collect",
                "how we use your information",
            ],

            "cookies": [
                "cookie policy",
                "cookies",
                "tracking technologies",
                "cookie notice",
                "similar technologies",
            ],

            "returns": [
                "return policy",
                "refund policy",
                "returns and refunds",
                "cancellation and refund",
                "return and refund",
                "eligible for return",
                "refund will be",
                "return window",
            ],

            "payments": [
                "fees and payments",
                "payment policy",
                "payment methods",
                "payment gateway",
                "financial information",
                "payment terms",
                "payment transactions",
            ],

            "promotions": [
                "promotions terms",
                "promotion terms",
                "promotional offers",
                "coupon terms",
                "promotional activities",
                "offer terms and conditions",
            ],

            "legal": [
                "legal notice",
                "disclaimer",
                "limitation of liability",
                "governing law",
                "jurisdiction",
                "intellectual property",
                "indemnification",
            ],
        }

        signals = policy_signal_groups.get(
            policy_type,
            []
        )

        matched = sum(
            1
            for signal in signals
            if signal in lower
        )

        if matched >= 2:
            return True

        # Combined policy pages.
        groups_matched = 0

        for group in policy_signal_groups.values():

            if any(
                signal in lower
                for signal in group
            ):
                groups_matched += 1

        if groups_matched >= 2:
            return True

        # --------------------------------------------------------
        # URL itself is strongly policy-specific.
        #
        # For a very clearly named policy page, allow one strong
        # semantic signal when the page is sufficiently long.
        # --------------------------------------------------------

        if (
            self._looks_like_policy_url(url)
            and len(text) >= 1000
        ):

            strong_signals = [
                "terms",
                "privacy",
                "personal data",
                "personal information",
                "refund",
                "return",
                "governing law",
                "payment",
                "cookies",
                "agreement",
            ]

            if any(
                signal in lower
                for signal in strong_signals
            ):
                return True

        return False

    # ============================================================
    # COMMERCE URL DETECTION
    # ============================================================

    def _looks_like_commerce_page(
        self,
        url: str,
    ) -> bool:

        parsed = urlparse(url)

        path = parsed.path.lower()
        query = parsed.query.lower()

        # --------------------------------------------------------
        # COMMERCE MUST WIN OVER GENERIC POLICY WORDS.
        #
        # Example:
        # /brands/legal-bribe/c/12329
        #
        # contains the word "legal", but it is a product/brand
        # category and must never be treated as a policy page.
        # --------------------------------------------------------

        segments = [
            segment
            for segment in path.split("/")
            if segment
        ]

        commerce_exact = {
            "c",
            "category",
            "categories",
            "product",
            "products",
            "search",
            "shop",
            "listing",
            "collections",
            "collection",
            "brands",
            "brand",
        }

        for segment in segments:

            if segment in commerce_exact:
                return True

        commerce_patterns = [
            r"/c/\d+",
            r"/p/\d+",
            r"/product/",
            r"/products/",
            r"/search(?:/|$)",
            r"/category/",
            r"/categories/",
            r"/collections/",
            r"/shop/",
            r"/brands/",
            r"/brand/",
            r"/beauty-partners/",
        ]

        for pattern in commerce_patterns:

            if re.search(
                pattern,
                path,
            ):
                return True

        # Nykaa-style listing query parameters.
        if (
            "/c/" in path
            or "ptype=lst" in query
            or "root=brand_menu" in query
            or "root=category" in query
        ):
            return True

        return False

    # ============================================================
    # CANDIDATE CONTENT
    # ============================================================

    def _candidate_content(
        self,
        candidate: Dict[str, Any],
    ) -> str:

        return str(
            candidate.get(
                "content",
                "",
            )
            or ""
        ).strip()

    # ============================================================
    # BACKEND EXTRACTION
    #
    # Order:
    #
    # 1. Crawl4AI + Playwright
    # 2. Existing static scraper
    # 3. Existing dynamic scraper
    # 4. Jina Reader
    #
    # ============================================================

    def _try_backend_extraction(
        self,
        url: str,
    ) -> tuple[str, str]:

        if self._looks_like_commerce_page(url):
            print(
                "Backend extraction blocked for commerce URL."
            )
            return "", ""

        # --------------------------------------------------------
        # Crawl4AI
        # --------------------------------------------------------

        print(
            "Trying Crawl4AI + Playwright..."
        )

        try:

            content = self._crawl4ai_scrape(
                url
            )

            if (
                content
                and len(content.strip())
                >= self.MIN_POLICY_CHARS
            ):

                print(
                    "Crawl4AI extraction: "
                    f"{len(content)} characters."
                )

                return (
                    content,
                    "crawl4ai",
                )

        except Exception as exc:

            print(
                f"Crawl4AI failed: {exc}"
            )

        # --------------------------------------------------------
        # Existing static scraper
        # --------------------------------------------------------

        try:

            from scraping.static_scraper import (
                scrape_static_page,
            )

            print(
                "Trying static scraper..."
            )

            content = scrape_static_page(
                url
            )

            if (
                content
                and len(
                    content.strip()
                ) >= self.MIN_POLICY_CHARS
            ):

                print(
                    "Static extraction: "
                    f"{len(content)} characters."
                )

                return (
                    content,
                    "static",
                )

        except Exception as exc:

            print(
                f"Static scraper failed: {exc}"
            )

        # --------------------------------------------------------
        # Existing dynamic scraper
        # --------------------------------------------------------

        try:

            from scraping.dynamic_scraper import (
                scrape_dynamic_page,
            )

            print(
                "Trying dynamic scraper..."
            )

            content = scrape_dynamic_page(
                url
            )

            if (
                content
                and len(
                    content.strip()
                ) >= self.MIN_POLICY_CHARS
            ):

                print(
                    "Dynamic extraction: "
                    f"{len(content)} characters."
                )

                return (
                    content,
                    "dynamic",
                )

        except Exception as exc:

            print(
                f"Dynamic scraper failed: {exc}"
            )

        # --------------------------------------------------------
        # Jina Reader
        # --------------------------------------------------------

        print(
            "Trying Jina Reader..."
        )

        try:

            content = self._jina_reader_scrape(
                url
            )

            if (
                content
                and len(content.strip())
                >= self.MIN_POLICY_CHARS
            ):

                print(
                    "Jina Reader extraction: "
                    f"{len(content)} characters."
                )

                return (
                    content,
                    "jina_reader",
                )

        except Exception as exc:

            print(
                f"Jina Reader failed: {exc}"
            )

        return "", ""

    # ============================================================
    # CRAWL4AI SCRAPER
    # ============================================================

    def _crawl4ai_scrape(
        self,
        url: str,
    ) -> str:

        from crawl4ai import (
            AsyncWebCrawler,
            BrowserConfig,
            CrawlerRunConfig,
            CacheMode,
        )

        async def _run() -> str:

            browser_config = BrowserConfig(
                headless=True,
                verbose=False,
            )

            run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                wait_until="domcontentloaded",
                delay_before_return_html=(
                    self.CRAWL4AI_WAIT_SECONDS
                ),
                page_timeout=(
                    self.CRAWL4AI_TIMEOUT * 1000
                ),
            )

            async with AsyncWebCrawler(
                config=browser_config
            ) as crawler:

                result = await crawler.arun(
                    url=url,
                    config=run_config,
                )

                if not result:
                    return ""

                # Crawl4AI normally exposes cleaned markdown
                # through markdown, but keep HTML as fallback.
                markdown = getattr(
                    result,
                    "markdown",
                    "",
                )

                if callable(markdown):
                    markdown = markdown()

                markdown = str(
                    markdown or ""
                ).strip()

                if markdown:
                    return self._clean_scraped_text(
                        markdown
                    )

                html = str(
                    getattr(
                        result,
                        "cleaned_html",
                        "",
                    )
                    or getattr(
                        result,
                        "html",
                        "",
                    )
                    or ""
                )

                if html:
                    return self._html_to_text(
                        html
                    )

                return ""

        return asyncio.run(
            _run()
        )

    # ============================================================
    # JINA READER
    # ============================================================

    def _jina_reader_scrape(
        self,
        url: str,
    ) -> str:

        reader_url = (
            "https://r.jina.ai/"
            + url
        )

        headers = {
            "Accept": "text/plain",
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            ),
        }

        with httpx.Client(
            timeout=self.JINA_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:

            response = client.get(
                reader_url
            )

            response.raise_for_status()

            return self._clean_scraped_text(
                response.text
            )

    # ============================================================
    # HTML TO TEXT
    # ============================================================

    def _html_to_text(
        self,
        html: str,
    ) -> str:

        text = str(
            html or ""
        )

        # Remove scripts/styles/noscript.
        text = re.sub(
            r"<script\b[^>]*>.*?</script>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        text = re.sub(
            r"<style\b[^>]*>.*?</style>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        text = re.sub(
            r"<noscript\b[^>]*>.*?</noscript>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Convert block-ish HTML to newlines.
        text = re.sub(
            r"</?(p|div|section|article|main|h[1-6]|li|br|tr)\b[^>]*>",
            "\n",
            text,
            flags=re.IGNORECASE,
        )

        # Remove remaining tags.
        text = re.sub(
            r"<[^>]+>",
            " ",
            text,
        )

        # Basic HTML entities.
        replacements = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&#39;": "'",
        }

        for old, new in replacements.items():
            text = text.replace(
                old,
                new,
            )

        return self._clean_scraped_text(
            text
        )

    # ============================================================
    # TEXT CLEANING
    # ============================================================

    def _clean_scraped_text(
        self,
        text: str,
    ) -> str:

        text = str(
            text or ""
        )

        # Remove common markdown image syntax.
        text = re.sub(
            r"!\[[^\]]*\]\([^)]+\)",
            " ",
            text,
        )

        # Remove repeated blank lines.
        text = re.sub(
            r"\n\s*\n+",
            "\n\n",
            text,
        )

        # Remove excessive spaces.
        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        return text.strip()

    # ============================================================
    # BUILD DOCUMENT
    # ============================================================

    def _build_document(
        self,
        url: str,
        policy_type: str,
        content: str,
        source: str,
    ) -> Dict[str, Any] | None:

        content = self._clean_scraped_text(
            content
        )

        if len(content) < self.MIN_POLICY_CHARS:
            return None

        return {
            "url": url,
            "type": self._normalize_type(
                policy_type
            ),
            "content": content,
            "content_length": len(content),
            "source": source,
        }

    # ============================================================
    # CANDIDATE DEDUPLICATION
    # ============================================================

    def _deduplicate_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        seen_urls = set()
        result = []

        for candidate in candidates:

            url = candidate.get(
                "url",
                "",
            )

            if not url:
                continue

            key = self._canonical_url(
                url
            )

            if key in seen_urls:
                continue

            seen_urls.add(key)
            result.append(candidate)

        return result

    # ============================================================
    # DOCUMENT DEDUPLICATION
    # ============================================================

    def _deduplicate_documents(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        seen_urls = set()
        seen_hashes = set()
        result = []

        for document in documents:

            url = self._canonical_url(
                document.get(
                    "url",
                    "",
                )
            )

            content = str(
                document.get(
                    "content",
                    "",
                )
                or ""
            )

            if not content:
                continue

            content_hash = hashlib.sha256(
                re.sub(
                    r"\s+",
                    " ",
                    content.lower(),
                ).strip().encode(
                    "utf-8"
                )
            ).hexdigest()

            if url in seen_urls:
                continue

            if content_hash in seen_hashes:
                continue

            seen_urls.add(url)
            seen_hashes.add(content_hash)

            result.append(document)

        return result

    # ============================================================
    # CANONICAL URL
    # ============================================================

    def _canonical_url(
        self,
        url: str,
    ) -> str:

        try:

            parsed = urlparse(url)

            path = (
                parsed.path
                or "/"
            ).rstrip("/").lower()

            return (
                f"{parsed.scheme.lower()}://"
                f"{parsed.netloc.lower()}"
                f"{path}"
            )

        except Exception:

            return str(
                url
            ).strip().lower()

    # ============================================================
    # HOST
    # ============================================================

    def _host(
        self,
        url: str,
    ) -> str:

        try:

            return (
                urlparse(url)
                .netloc
                .lower()
                .split(":")[0]
            )

        except Exception:

            return ""
