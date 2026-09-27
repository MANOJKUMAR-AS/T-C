from __future__ import annotations

import asyncio
import difflib
import hashlib
import io
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

        # Short pages with policy-looking titles are often only
        # navigation shells, profile pages, or framework-generated
        # route pages. They must contain stronger evidence before
        # being accepted as real policy documents.
        self.MIN_SUBSTANTIVE_POLICY_CHARS = 1200

        # Never allow thousands of links to become backend jobs.
        self.MAX_DOCUMENTS = 20
        self.MAX_BACKEND_CANDIDATES = 8

        # Crawl4AI settings.
        self.CRAWL4AI_TIMEOUT = 30
        self.CRAWL4AI_WAIT_SECONDS = 2

        # Jina Reader settings.
        self.JINA_TIMEOUT = 35

        # Direct PDF download settings.
        self.PDF_TIMEOUT = 45
        self.PDF_MAX_BYTES = 25 * 1024 * 1024

        # PDF extraction sanity limits.
        self.PDF_MIN_TEXT_CHARS = 500
        self.PDF_MAX_PAGE_TEXT_CHARS = 2_000_000

        # Browser/PDF viewer text that must never be accepted
        # as actual PDF document content.
        self.PDF_VIEWER_SIGNALS = [
            "pdf viewer",
            "failed to load pdf",
            "this document requires",
            "get adobe reader",
            "please wait...",
            "loading...",
            "enable javascript",
            "chrome://pdf",
            "about:blank",
        ]

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

        # ========================================================
        # 1. BROWSER DOCUMENTS FAST PATH
        #
        # If the Chrome extension already supplied browser-rendered
        # policy documents, validate them through all safety gates
        # FIRST. If valid policy documents are found, skip expensive
        # backend detector discovery and web search fallbacks.
        # ========================================================

        if browser_documents:
            print("Evaluating supplied browser documents...")
            browser_extracted_docs: List[Dict[str, Any]] = []

            for item in browser_documents:
                normalized = self._normalize_candidate(
                    item,
                    source_url,
                )
                if not normalized:
                    continue

                if not self._is_policy_candidate(normalized):
                    print(
                        f"Rejected browser document candidate URL: {normalized['url']}"
                    )
                    continue

                if self._is_obvious_non_policy_route(normalized["url"]):
                    print(
                        f"Rejected browser document candidate non-policy route: {normalized['url']}"
                    )
                    continue

                policy_url = normalized["url"]
                policy_type = normalized["type"]

                # PDF documents MUST go through direct PDF byte extraction
                if self._is_pdf_url(policy_url):
                    print(f"Browser document is PDF. Using direct PDF extraction: {policy_url}")
                    pdf_content, pdf_source = self._try_pdf_extraction(policy_url)
                    if (
                        pdf_content
                        and len(pdf_content) >= self.MIN_POLICY_CHARS
                        and self._is_real_policy_content(policy_url, pdf_content, policy_type)
                    ):
                        doc = self._build_document(policy_url, policy_type, pdf_content, pdf_source)
                        if doc:
                            doc["extraction_method"] = "direct_pdf"
                            browser_extracted_docs.append(doc)
                            print(f"{pdf_source} PDF extraction accepted for browser document.")
                    continue

                # HTML documents
                content = self._candidate_content(normalized)
                if (
                    content
                    and len(content) >= self.MIN_POLICY_CHARS
                    and self._is_real_policy_document(normalized)
                    and self._is_real_policy_content(policy_url, content, policy_type)
                ):
                    doc = self._build_document(
                        policy_url,
                        policy_type,
                        content,
                        normalized.get("source", "browser"),
                    )
                    if doc:
                        doc["extraction_method"] = "browser"
                        browser_extracted_docs.append(doc)
                        print(f"Browser document accepted: [{policy_type}] {policy_url}")

            if browser_extracted_docs:
                browser_extracted_docs = self._deduplicate_documents(browser_extracted_docs)
                if browser_extracted_docs:
                    print(
                        f"Fast path: accepted {len(browser_extracted_docs)} valid browser documents. "
                        "Skipping expensive backend detector discovery."
                    )
                    return self._build_final_result(source_url, browser_extracted_docs)

        # ========================================================
        # 2. BACKEND POLICY DETECTOR (FALLBACK)
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
        # 3. COLLECT POLICY CANDIDATES
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

            if self._is_obvious_non_policy_route(
                normalized["url"]
            ):
                print(
                    "Rejected detector candidate "
                    "because URL is a non-policy route: "
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

            if self._is_obvious_non_policy_route(
                normalized["url"]
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

            if self._is_obvious_non_policy_route(
                normalized["url"]
            ):
                print(
                    "Rejected browser document URL "
                    "because URL is a non-policy route: "
                    f"{normalized['url']}"
                )
                continue

            # ----------------------------------------------------
            # IMPORTANT:
            #
            # Browser-provided PDF content is NOT automatically
            # trusted anymore. If the URL is a PDF, we validate
            # it using the dedicated PDF path during extraction.
            # ----------------------------------------------------

            if self._is_pdf_url(normalized["url"]):
                candidates.append(normalized)
                browser_document_count += 1
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
        # 4. DEDUPLICATE
        # ========================================================

        candidates = self._deduplicate_candidates(
            candidates
        )

        print(
            f"Unique policy candidates after hard filter: "
            f"{len(candidates)}"
        )

        # ========================================================
        # 5. EXTRACT
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
            # PDF CANDIDATES
            #
            # NEVER trust browser PDF viewer text.
            #
            # Always download the actual PDF and extract text
            # from the bytes.
            # ----------------------------------------------------

            if self._is_pdf_url(policy_url):
                print(
                    "PDF detected. "
                    "Using direct PDF-byte extraction."
                )

                pdf_content, pdf_source = (
                    self._try_pdf_extraction(
                        policy_url
                    )
                )

                if (
                    pdf_content
                    and len(pdf_content) >= self.MIN_POLICY_CHARS
                    and self._is_real_policy_content(
                        policy_url,
                        pdf_content,
                        policy_type,
                    )
                ):

                    document = self._build_document(
                        policy_url,
                        policy_type,
                        pdf_content,
                        pdf_source,
                    )

                    if document:
                        document["extraction_method"] = (
                            "direct_pdf"
                        )

                        documents.append(document)

                        print(
                            f"{pdf_source} extraction accepted."
                        )

                        continue

                print(
                    "Direct PDF extraction failed "
                    "or produced invalid policy content."
                )

                # ------------------------------------------------
                # Do NOT feed a browser PDF viewer into Agent 2.
                #
                # If direct PDF extraction fails, we skip this
                # candidate instead of accepting potentially
                # corrupted browser content.
                # ------------------------------------------------

                continue

            # ----------------------------------------------------
            # Browser-provided HTML content
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
                        document["extraction_method"] = (
                            "browser"
                        )

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
                    document["extraction_method"] = (
                        fallback_source
                    )

                    documents.append(document)

                    print(
                        f"{fallback_source} extraction accepted."
                    )

                    continue

            print(
                "Policy extraction failed."
            )

        # ========================================================
        # 6. WEB SEARCH FALLBACK
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
                            "discovery_method": item.get(
                                "discovery_method",
                                "web_search",
                            ),
                            "complete_page_extracted": bool(
                                item.get(
                                    "complete_page_extracted",
                                    False,
                                )
                            ),
                            "search_score": item.get(
                                "search_score",
                                0,
                            ),
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

                        # Web-search PDFs must also go through
                        # direct PDF extraction instead of trusting
                        # snippets or browser content.
                        if self._is_pdf_url(search_url):

                            print(
                                "Web search returned PDF. "
                                "Using direct PDF extraction: "
                                f"{search_url}"
                            )

                            search_content, pdf_source = (
                                self._try_pdf_extraction(
                                    search_url
                                )
                            )

                            if not search_content:
                                continue

                            extraction_source = pdf_source

                        else:
                            extraction_source = "web_search"

                        if (
                            len(search_content)
                            < self.MIN_POLICY_CHARS
                        ):
                            print(
                                "Web search evidence too short: "
                                f"{search_url}"
                            )
                            continue

                        complete_page_extracted = bool(
                            item.get(
                                "complete_page_extracted",
                                False,
                            )
                        )

                        discovery_method = str(
                            item.get(
                                "discovery_method",
                                extraction_source,
                            )
                            or extraction_source
                        ).strip()

                        # A generic web-search result is never trusted solely
                        # because the search provider marked it as a complete
                        # page. Search engines can return forum posts, profile
                        # pages, and navigation-heavy pages whose URL/title
                        # contains "privacy", "terms", etc.
                        #
                        # There is one explicit trusted provenance exception:
                        # the deterministic policy-route searcher already fetched
                        # the page and validated its full content before returning
                        # it. Its discovery_method is therefore authoritative.
                        #
                        # This preserves the false-positive protection added for
                        # LeetCode while allowing genuine deterministic fallback
                        # pages such as City Union Bank /terms and /privacy-policy
                        # to survive this outer Agent 1 validation pass.
                        if self._is_obvious_non_policy_route(
                            search_url
                        ):
                            print(
                                "Web search result rejected "
                                "because URL is a non-policy route: "
                                f"{search_url}"
                            )
                            continue

                        trusted_deterministic_page = (
                            complete_page_extracted
                            and discovery_method
                            == "deterministic_policy_route"
                        )

                        if trusted_deterministic_page:
                            print(
                                "Trusted deterministic policy route "
                                "accepted after prior full-page "
                                "validation: "
                                f"{search_url}"
                            )
                        elif not self._is_real_policy_content(
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
                        elif complete_page_extracted:
                            print(
                                "Web search complete page passed "
                                "policy content validation: "
                                f"{search_url}"
                            )

                        document = self._build_document(
                            search_url,
                            search_type,
                            search_content,
                            discovery_method,
                        )

                        if document:

                            document[
                                "complete_page_extracted"
                            ] = complete_page_extracted

                            document[
                                "discovery_method"
                            ] = discovery_method

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
        # 7. FINAL DEDUPLICATION
        # ========================================================

        documents = self._deduplicate_documents(
            documents
        )

        return self._build_final_result(
            source_url,
            documents,
        )

    # ============================================================
    # BUILD FINAL RESULT
    # ============================================================

    def _build_final_result(
        self,
        source_url: str,
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the authoritative Agent 1 response dictionary from
        extracted policy documents.
        """

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

        return {
            "agent": self.name,
            "source_url": source_url,
            "status": "complete",
            "policy_count": len(documents),
            "document_count": len(documents),
            "documents": documents,
            "policy_documents": documents,
            "policy_pages": documents,
            "browser_documents": documents,
            "summary": summary,
        }

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

                if self._is_obvious_non_policy_route(
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
    # PDF URL DETECTION
    # ============================================================

    def _is_pdf_url(
        self,
        url: str,
    ) -> bool:

        try:
            parsed = urlparse(url)
        except Exception:
            return False

        path = parsed.path.lower()

        return (
            path.endswith(".pdf")
            or ".pdf/" in path
            or path.endswith(".pdf/ ")
        )

    # ============================================================
    # PDF CONTENT DETECTION
    # ============================================================

    def _looks_like_pdf_bytes(
        self,
        content: bytes,
    ) -> bool:

        if not content:
            return False

        # PDF files must begin with %PDF-
        # Allow a small UTF-8/BOM or whitespace prefix because
        # some servers incorrectly prepend bytes.
        prefix = content[:1024]

        return (
            b"%PDF-" in prefix
        )

    # ============================================================
    # DIRECT PDF EXTRACTION
    #
    # This is intentionally independent of browser rendering.
    #
    # 1. Download actual bytes.
    # 2. Verify PDF signature.
    # 3. Extract using pypdf.
    # 4. Fall back to PyMuPDF.
    # 5. Reject browser/viewer garbage.
    # ============================================================

    def _try_pdf_extraction(
        self,
        url: str,
    ) -> tuple[str, str]:

        print(
            "Downloading actual PDF bytes..."
        )

        try:

            response = self._download_pdf(
                url
            )

            if response is None:
                return "", ""

            content_type = (
                response.headers.get(
                    "content-type",
                    "",
                )
                or ""
            ).lower()

            pdf_bytes = response.content

            print(
                "PDF HTTP response: "
                f"{response.status_code}, "
                f"{len(pdf_bytes)} bytes, "
                f"content-type={content_type or 'unknown'}"
            )

            if not self._looks_like_pdf_bytes(
                pdf_bytes
            ):

                print(
                    "Rejected PDF candidate: "
                    "response does not contain a valid "
                    "%PDF- signature."
                )

                return "", ""

            # ----------------------------------------------------
            # pypdf
            # ----------------------------------------------------

            text = self._extract_pdf_with_pypdf(
                pdf_bytes
            )

            if self._is_valid_pdf_text(text):

                print(
                    "pypdf extraction: "
                    f"{len(text)} characters."
                )

                return (
                    text,
                    "pypdf",
                )

            print(
                "pypdf extraction produced "
                "insufficient/invalid text."
            )

            # ----------------------------------------------------
            # PyMuPDF
            # ----------------------------------------------------

            text = self._extract_pdf_with_pymupdf(
                pdf_bytes
            )

            if self._is_valid_pdf_text(text):

                print(
                    "PyMuPDF extraction: "
                    f"{len(text)} characters."
                )

                return (
                    text,
                    "pymupdf",
                )

            print(
                "PyMuPDF extraction produced "
                "insufficient/invalid text."
            )

        except Exception as exc:

            print(
                f"Direct PDF extraction failed: {exc}"
            )

        return "", ""

    # ============================================================
    # DOWNLOAD PDF
    # ============================================================

    def _download_pdf(
        self,
        url: str,
    ) -> httpx.Response | None:

        headers = {
            "Accept": (
                "application/pdf,"
                "application/octet-stream,"
                "*/*"
            ),
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            ),
        }

        with httpx.Client(
            timeout=self.PDF_TIMEOUT,
            follow_redirects=True,
            headers=headers,
        ) as client:

            with client.stream(
                "GET",
                url,
            ) as response:

                response.raise_for_status()

                chunks: List[bytes] = []
                total = 0

                for chunk in response.iter_bytes(
                    chunk_size=64 * 1024
                ):

                    total += len(chunk)

                    if total > self.PDF_MAX_BYTES:

                        raise ValueError(
                            "PDF exceeds maximum allowed size "
                            f"of {self.PDF_MAX_BYTES} bytes."
                        )

                    chunks.append(chunk)

                body = b"".join(chunks)

                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=body,
                    request=response.request,
                )

    # ============================================================
    # PYPDF EXTRACTION
    # ============================================================

    def _extract_pdf_with_pypdf(
        self,
        pdf_bytes: bytes,
    ) -> str:

        try:

            from pypdf import PdfReader

            reader = PdfReader(
                io.BytesIO(pdf_bytes)
            )

            parts: List[str] = []

            for page_number, page in enumerate(
                reader.pages
            ):

                try:

                    page_text = page.extract_text(
                        extraction_mode="layout"
                    )

                except TypeError:

                    page_text = page.extract_text()

                except Exception as exc:

                    print(
                        f"pypdf page {page_number + 1} "
                        f"failed: {exc}"
                    )
                    page_text = ""

                page_text = str(
                    page_text or ""
                ).strip()

                if page_text:
                    parts.append(page_text)

                if sum(
                    len(part)
                    for part in parts
                ) >= self.PDF_MAX_PAGE_TEXT_CHARS:
                    break

            return self._clean_scraped_text(
                "\n\n".join(parts)
            )

        except Exception as exc:

            print(
                f"pypdf failed: {exc}"
            )

            return ""

    # ============================================================
    # PYMUPDF EXTRACTION
    # ============================================================

    def _extract_pdf_with_pymupdf(
        self,
        pdf_bytes: bytes,
    ) -> str:

        try:

            import fitz

            document = fitz.open(
                stream=pdf_bytes,
                filetype="pdf",
            )

            parts: List[str] = []

            try:

                for page_number in range(
                    document.page_count
                ):

                    try:

                        page = document.load_page(
                            page_number
                        )

                        page_text = page.get_text(
                            "text"
                        )

                        page_text = str(
                            page_text or ""
                        ).strip()

                        if page_text:
                            parts.append(page_text)

                    except Exception as exc:

                        print(
                            f"PyMuPDF page "
                            f"{page_number + 1} failed: "
                            f"{exc}"
                        )

                    if sum(
                        len(part)
                        for part in parts
                    ) >= self.PDF_MAX_PAGE_TEXT_CHARS:
                        break

            finally:

                document.close()

            return self._clean_scraped_text(
                "\n\n".join(parts)
            )

        except Exception as exc:

            print(
                f"PyMuPDF failed: {exc}"
            )

            return ""

    # ============================================================
    # PDF TEXT VALIDATION
    # ============================================================

    def _is_valid_pdf_text(
        self,
        text: str,
    ) -> bool:

        text = self._clean_scraped_text(
            text
        )

        if len(text) < self.PDF_MIN_TEXT_CHARS:
            return False

        lower = text.lower()

        # Browser/PDF-viewer content is not a document.
        viewer_hits = sum(
            1
            for signal in self.PDF_VIEWER_SIGNALS
            if signal in lower
        )

        if viewer_hits >= 2:
            return False

        # If nearly everything consists of a tiny repeated
        # navigation/viewer string, reject it.
        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        if len(lines) >= 10:

            unique_lines = {
                line.lower()
                for line in lines
            }

            uniqueness_ratio = (
                len(unique_lines)
                / max(len(lines), 1)
            )

            if uniqueness_ratio < 0.10:
                return False

        # Actual PDFs normally contain a mixture of letters,
        # numbers and punctuation. Reject content that looks like
        # pure UI boilerplate.
        alnum_count = sum(
            1
            for char in text
            if char.isalnum()
        )

        if alnum_count < 250:
            return False

        return True

    # ============================================================
    # PDF CONTENT FINGERPRINT
    # ============================================================

    def _content_fingerprint(
        self,
        content: str,
    ) -> str:

        normalized = re.sub(
            r"\s+",
            " ",
            str(content or "").lower(),
        ).strip()

        return hashlib.sha256(
            normalized.encode(
                "utf-8"
            )
        ).hexdigest()

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

    def _looks_like_commerce_page(
        self,
        url: str,
    ) -> bool:
        """
        Identify obvious product/service/transaction pages.

        This is intentionally URL-focused. Content-level validation
        remains the responsibility of _is_real_policy_content().
        """

        if not url:
            return True

        path = urlparse(url).path.lower()

        commerce_patterns = [
            r"/products?(?:/|$)",
            r"/product-details?(?:/|$)",
            r"/creditcard(?:/|$)",
            r"/credit-card(?:/|$)",
            r"/debit-card(?:/|$)",
            r"/cards?(?:/|$)",
            r"/loans?(?:/|$)",
            r"/personal-loan(?:/|$)",
            r"/home-loan(?:/|$)",
            r"/vehicle-loan(?:/|$)",
            r"/business-loan(?:/|$)",
            r"/deposits?(?:/|$)",
            r"/savings-account(?:/|$)",
            r"/current-account(?:/|$)",
            r"/bill-payment(?:/|$)",
            r"/electricity-bill-payment(?:/|$)",
            r"/gst-payment(?:/|$)",
            r"/tax-payment(?:/|$)",
            r"/payments?\.jsp(?:$|/)",
            r"/checkout(?:/|$)",
            r"/transaction(?:/|$)",
            r"/point-of-sale(?:/|$)",
            r"/pos(?:/|$)",
            r"/bharat-qr(?:/|$)",
            r"/upi(?:/|$)",
            r"/fastag(?:/|$)",
            r"/salaryse(?:/|$)",
            r"/foreign-exchange-rates(?:/|$)",
            r"/correspondent-banks-for-currency-exchange(?:/|$)",
            r"/fee-collection(?:/|$)",
            r"/offers?(?:/|$)",
            r"/promotions?(?:/|$)",
            r"/order(?:s)?(?:/|$)",
            r"/restaurant(?:s)?(?:/|$)",
            r"/dining(?:/|$)",
            r"/dineout(?:/|$)",
            r"/menus?(?:/|$)",
            r"/delivery(?:/|$)",
            r"/food(?:/|$)",
            r"/checkout(?:/|$)",
            r"/cart(?:/|$)",
            r"/bookings?(?:/|$)",
            r"/reservations?(?:/|$)",
            r"/reviews?(?:/|$)",
            r"/ratings?(?:/|$)",
            r"/locations?(?:/|$)",
            r"/cities?(?:/|$)",
            r"/search(?:/|$)",
            r"/discover(?:/|$)",
            r"/collections?(?:/|$)",
            r"/calculators?(?:/|$)",
            r"/emi-calculator(?:/|$)",
            r"/apr-calculator(?:/|$)",
            r"/branch(?:-locator)?(?:/|$)",
            r"/atm(?:-locator)?(?:/|$)",
        ]

        return any(
            re.search(pattern, path)
            for pattern in commerce_patterns
        )

    # ============================================================
    # HARD POLICY CANDIDATE GATE
    # ============================================================

    def _is_policy_candidate(
        self,
        candidate: Dict[str, Any],
    ) -> bool:
        """
        Decide whether a URL should be allowed into the extraction
        stage.

        IMPORTANT:
        This method is a FETCH GATE, not the final policy validator.

        Strong legal/policy URLs are allowed through so that their
        actual page content can be fetched and evaluated by
        _is_real_policy_content().

        Obvious commerce/service pages are rejected immediately.
        """

        if not isinstance(candidate, dict):
            return False

        url = str(
            candidate.get("url", "")
            or ""
        ).strip()

        if not url:
            return False

        # --------------------------------------------------------
        # First: reject obvious commerce/service pages.
        # --------------------------------------------------------

        if self._looks_like_commerce_page(url):
            return False

        path = urlparse(url).path.lower()

        # --------------------------------------------------------
        # Strong legal/policy URL signals.
        #
        # These are intentionally allowed through WITHOUT requiring
        # content at this stage. The page may need to be fetched
        # before we can validate it.
        # --------------------------------------------------------

        strong_policy_patterns = [
            r"(?:^|/)terms(?:$|[-_/])",
            r"(?:^|/)terms-and-conditions(?:$|[-_/])",
            r"(?:^|/)terms-of-use(?:$|[-_/])",
            r"(?:^|/)terms-of-service(?:$|[-_/])",
            r"(?:^|/)termsandcondition(?:$|[-_/])",
            r"(?:^|/)termsofuse(?:$|[-_/])",

            r"(?:^|/)privacy(?:$|[-_/])",
            r"(?:^|/)privacy-policy(?:$|[-_/])",
            r"(?:^|/)privacy-notice(?:$|[-_/])",
            r"(?:^|/)privacy_policy(?:$|[-_/])",
            r"(?:^|/)privacypolicy(?:$|[-_/])",
            r"(?:^|/)data-privacy(?:$|[-_/])",
            r"(?:^|/)data-protection(?:$|[-_/])",
            r"(?:^|/)mobile-banking-privacy-policy(?:$|[-_/])",

            r"(?:^|/)cookie(?:$|[-_/])",
            r"(?:^|/)cookies(?:$|[-_/])",
            r"(?:^|/)cookie-policy(?:$|[-_/])",

            r"(?:^|/)disclaimer(?:$|[-_/])",
            r"(?:^|/)legal(?:$|[-_/])",
            r"(?:^|/)legal-notice(?:$|[-_/])",
            r"(?:^|/)agreement(?:$|[-_/])",

            r"(?:^|/)policy(?:$|[-_/])",
            r"(?:^|/)policies(?:$|[-_/])",
            r"(?:^|/)msme-policy(?:$|[-_/])",

            r"(?:^|/)mitc(?:$|[-_/])",
            r"(?:^|/)kfs(?:$|[-_/])",

            r"(?:^|/)return-policy(?:$|[-_/])",
            r"(?:^|/)refund-policy(?:$|[-_/])",
            r"(?:^|/)return-refund(?:$|[-_/])",
            r"(?:^|/)return-refund-policy(?:$|[-_/])",

            r"(?:^|/)payment-policy(?:$|[-_/])",
            r"(?:^|/)fee-payment-policy(?:$|[-_/])",
            r"(?:^|/)fee-payment-promotion-policy(?:$|[-_/])",

            r"(?:^|/)code-of-banks?(?:$|[-_/])",
            r"(?:^|/)code-of-banks?-commitment(?:$|[-_/])",
            r"(?:^|/)customer-commitment(?:$|[-_/])",
            r"(?:^|/)customer-rights(?:$|[-_/])",
            r"(?:^|/)guidelines?(?:$|[-_/])",
            r"(?:^|/)regulatory(?:$|[-_/])",
        ]

        if any(
            re.search(pattern, path)
            for pattern in strong_policy_patterns
        ):
            return True

        # --------------------------------------------------------
        # PDF URLs need to reach the PDF extraction layer.
        #
        # Actual PDF-byte validation is handled later by
        # _try_pdf_extraction().
        # --------------------------------------------------------

        if self._is_pdf_url(url):
            return True

        # --------------------------------------------------------
        # Candidate metadata can provide additional evidence.
        # This is useful for detector-discovered policy pages whose
        # URL is not strongly named.
        # --------------------------------------------------------

        policy_type = self._normalize_type(
            candidate.get("type")
        )

        if policy_type in {
            "terms",
            "privacy",
            "cookies",
            "returns",
            "legal",
            "promotions",
        }:
            return True

        # --------------------------------------------------------
        # For weak/unknown URLs without content, do not fetch them.
        # This keeps discovery conservative.
        # --------------------------------------------------------

        content = str(
            candidate.get("content", "")
            or candidate.get("text", "")
            or ""
        ).strip()

        if content:
            return self._is_real_policy_content(
                url,
                content,
                policy_type,
            )

        return False

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
    # WEB SEARCH NON-POLICY ROUTE GATE
    # ============================================================

    def _is_obvious_non_policy_route(
        self,
        url: str,
    ) -> bool:
        """
        Reject URL routes that are structurally associated with
        forums, user profiles, community posts, search pages, or
        product/application content.

        This gate is intentionally used for WEB-SEARCH RESULTS.
        A URL containing words such as ``privacy`` or ``terms`` is
        not enough when the route itself identifies a discussion,
        profile, or community page.

        Strong policy endpoints such as /privacy, /terms, and
        /privacy-policy are not blocked here.
        """

        if not url:
            return True

        try:
            path = urlparse(url).path.lower()
        except Exception:
            return True

        # Normalize repeated slashes and inspect individual segments.
        segments = [
            segment
            for segment in path.split("/")
            if segment
        ]

        blocked_exact_segments = {
            "discuss",
            "discussion",
            "discussions",
            "forum",
            "forums",
            "community",
            "profile",
            "profiles",
            "post",
            "posts",
            "search",
            "results",
            "problems",
            "problem",
            "contest",
            "contests",
            "store",
            "interview",
            "interviews",
            "editorial",
            "playground",
            "order",
            "orders",
            "restaurant",
            "restaurants",
            "menu",
            "menus",
            "delivery",
            "dineout",
            "dining",
            "reviews",
            "review",
            "ratings",
            "rating",
            "checkout",
            "cart",
            "booking",
            "bookings",
            "reservation",
            "reservations",
            "discover",
            "collection",
            "collections",
        }

        if any(
            segment in blocked_exact_segments
            for segment in segments
        ):
            return True

        # User/profile routes commonly use /u/<name>.
        if segments and segments[0] in {
            "u",
            "user",
            "users",
        }:
            return True

        return False

    # ============================================================
    # GENERIC PAGE-SHELL DETECTION
    # ============================================================

    def _is_generic_policy_shell(
        self,
        content: str,
    ) -> bool:
        """
        Reject framework/navigation shells that mention legal pages
        without actually containing the policy itself.

        This is intentionally content-based rather than site-specific.
        It protects against routes such as /returns or /privacy-policy
        returning a generic application page that contains links to
        Terms, Privacy and Cookie Policy.
        """

        text = re.sub(
            r"\s+",
            " ",
            str(content or ""),
        ).strip()

        if not text:
            return True

        lower = text.lower()

        shell_phrases = [
            "by continuing past this page, you agree to our terms of service",
            "terms of service, cookie policy, privacy policy and content policies",
            "terms of service cookie policy privacy policy",
        ]

        shell_hits = sum(
            1
            for phrase in shell_phrases
            if phrase in lower
        )

        # A generic agreement sentence is not itself a policy.
        if shell_hits >= 1:
            policy_body_signals = [
                "personal information",
                "personal data",
                "information we collect",
                "how we use",
                "data protection",
                "tracking technologies",
                "cookie policy",
                "cookies and similar",
                "return policy",
                "refund policy",
                "returns and refunds",
                "eligible for return",
                "refund will be",
                "terms and conditions",
                "terms of use",
                "terms of service",
                "limitation of liability",
                "governing law",
                "arbitration",
                "indemnification",
                "effective date",
                "retention",
                "termination",
            ]

            body_hits = sum(
                1
                for signal in policy_body_signals
                if signal in lower
            )

            # One shell phrase plus only the linked policy names is
            # page chrome, not a policy document.
            if body_hits <= 2:
                return True

        # Link-heavy pages are usually navigation/application shells.
        url_like_count = len(
            re.findall(
                r"https?://",
                lower,
            )
        )

        markdown_link_count = len(
            re.findall(
                r"\]\(",
                lower,
            )
        )

        navigation_terms = [
            "home",
            "search",
            "login",
            "sign up",
            "contact us",
            "careers",
            "blog",
            "download app",
            "company",
            "for restaurants",
            "for business",
            "investor relations",
        ]

        navigation_hits = sum(
            1
            for term in navigation_terms
            if term in lower
        )

        if (
            len(text) < 5000
            and (
                url_like_count >= 3
                or markdown_link_count >= 3
            )
            and navigation_hits >= 3
        ):
            return True

        return False

    def _policy_content_is_type_specific(
        self,
        content: str,
        policy_type: str,
    ) -> bool:
        """
        Require type-specific evidence for weakly named policy routes.

        A generic legal/footer page must not become a returns, payments,
        promotions, cookies, or privacy document merely because it links
        to those policies.
        """

        lower = re.sub(
            r"\s+",
            " ",
            str(content or ""),
        ).lower()

        type_signals = {
            "terms": [
                "terms and conditions",
                "terms of use",
                "terms of service",
                "these terms",
                "user agreement",
                "conditions of use",
            ],
            "privacy": [
                "privacy policy",
                "privacy notice",
                "personal information",
                "personal data",
                "information we collect",
                "data protection",
                "retention of personal data",
            ],
            "cookies": [
                "cookie policy",
                "cookie notice",
                "tracking technologies",
                "cookies and similar",
                "manage cookies",
                "control and manage cookies",
            ],
            "returns": [
                "return policy",
                "refund policy",
                "returns and refunds",
                "return and refund",
                "eligible for return",
                "return window",
                "refund will be",
                "refund terms",
                "non-refundable",
                "cancellation and refund",
            ],
            "payments": [
                "payment policy",
                "payment terms",
                "fees and charges",
                "fees and payments",
                "charges applicable",
                "charges payable",
                "payment obligations",
            ],
            "promotions": [
                "promotion terms",
                "promotional offers",
                "coupon terms",
                "offer terms and conditions",
                "promotional activities",
            ],
            "legal": [
                "legal notice",
                "disclaimer",
                "limitation of liability",
                "governing law",
                "jurisdiction",
                "arbitration",
                "indemnification",
            ],
        }

        signals = type_signals.get(policy_type)

        if not signals:
            return True

        return any(
            signal in lower
            for signal in signals
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
        # Reject generic application/navigation shells before any
        # semantic policy scoring. A shell can mention Terms, Privacy
        # and Cookies while containing none of the actual policy.
        # --------------------------------------------------------

        if self._is_generic_policy_shell(text):
            return False

        # --------------------------------------------------------
        # Type-specific content validation.
        #
        # This prevents /returns, /payments, /cookies, etc. from
        # being accepted solely because a generic page links to those
        # policies.
        # --------------------------------------------------------

        if not self._policy_content_is_type_specific(
            text,
            policy_type,
        ):
            return False

        # --------------------------------------------------------
        # Short-page substantive-content gate.
        #
        # Common-path discovery deliberately finds URL variants such
        # as /privacy-policy, /privacy_policy, /privacypolicy and
        # /cookies. Some sites return a tiny application shell or
        # navigation page for these routes. Such pages can contain
        # "privacy", "terms", or "cookies" and still pass the normal
        # semantic checks.
        #
        # Keep the general 500-character minimum for extraction, but
        # require stronger evidence for short policy-looking pages.
        # Genuine longer policy pages continue through the normal
        # validation rules below.
        # --------------------------------------------------------

        is_short_policy_page = (
            len(text) < self.MIN_SUBSTANTIVE_POLICY_CHARS
        )

        # --------------------------------------------------------
        # Structural rejection for obvious non-policy routes.
        #
        # This is especially important for web-search results:
        # forum/discussion/profile pages can contain legal/privacy
        # vocabulary without being policy documents.
        # --------------------------------------------------------

        if self._is_obvious_non_policy_route(url):
            return False

        # --------------------------------------------------------
        # Hard service / product content rejection.
        #
        # A real policy may mention products or payments, but a
        # service page normally contains several of these signals.
        # --------------------------------------------------------

        service_signals = [
            "apply online",
            "apply now",
            "login now",
            "register now",
            "learn more",
            "calculate emi",
            "emi calculator",
            "apr calculator",
            "branch locator",
            "atm locator",
            "customer care",
            "open account",
            "interest rates",
            "foreign exchange rates",
            "bill payment",
            "electricity bill",
            "gst payment",
            "tax payment",
            "credit card",
            "debit card",
            "point of sale",
            "pos facility",
            "upi payment",
            "qr payment",
            "fastag",
            "cash withdrawal",
        ]

        service_hits = sum(
            1
            for signal in service_signals
            if signal in lower
        )

        # Strong rejection for pages dominated by service/product
        # content. Do not reject a genuine legal document for one
        # incidental mention.
        if service_hits >= 4:
            return False

        # --------------------------------------------------------
        # Commerce/content-navigation rejection.
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
        # Strong legal/policy semantic groups.
        # --------------------------------------------------------

        policy_signal_groups = {

            "terms": [
                "terms and conditions",
                "terms of use",
                "terms of service",
                "user agreement",
                "customer agreement",
                "you agree to",
                "these terms",
                "conditions of use",
                "govern your use",
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
                "retention of personal data",
            ],

            "cookies": [
                "cookie policy",
                "cookie notice",
                "cookies and similar",
                "tracking technologies",
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
                "refund terms",
            ],

            "payments": [
                "payment policy",
                "payment terms",
                "fees and charges",
                "fees and payments",
                "service charges",
                "charges applicable",
                "charges payable",
                "payment obligations",
            ],

            "promotions": [
                "promotion terms",
                "promotions terms",
                "promotional offers",
                "coupon terms",
                "offer terms and conditions",
                "promotional activities",
            ],

            "legal": [
                "legal notice",
                "disclaimer",
                "limitation of liability",
                "governing law",
                "jurisdiction",
                "intellectual property",
                "indemnification",
                "arbitration",
                "confidentiality",
            ],

            "banking_policy": [
                "policy document",
                "this policy",
                "bank's policy",
                "banks policy",
                "board approved policy",
                "regulatory guidelines",
                "regulatory framework",
                "applicable regulations",
                "in accordance with",
                "shall comply",
                "customer rights",
                "customer obligations",
                "rights and obligations",
            ],

            "mitc_kfs": [
                "key fact statement",
                "key facts statement",
                "mitc",
                "most important terms and conditions",
                "most important terms",
                "principal terms and conditions",
            ],
        }

        # --------------------------------------------------------
        # Count semantic groups, not individual generic words.
        # --------------------------------------------------------

        matched_groups = []

        for group_name, signals in policy_signal_groups.items():

            if any(
                signal in lower
                for signal in signals
            ):
                matched_groups.append(
                    group_name
                )

        # --------------------------------------------------------
        # Very strong document-level evidence.
        # --------------------------------------------------------

        structural_signals = [
            r"\b1\.\s+[A-Z]",
            r"\b2\.\s+[A-Z]",
            r"\b3\.\s+[A-Z]",
            r"\b1\.\d+\s+",
            r"\b2\.\d+\s+",
            r"\b3\.\d+\s+",
            "definitions",
            "scope",
            "applicability",
            "obligations",
            "responsibilities",
            "rights",
            "restrictions",
            "termination",
            "grievance",
            "complaint",
            "dispute resolution",
            "effective date",
            "version",
        ]

        structural_hits = sum(
            1
            for signal in structural_signals
            if (
                re.search(signal, lower)
                if signal.startswith(r"\b")
                else signal in lower
            )
        )

        # --------------------------------------------------------
        # Explicit document titles/headings embedded in content.
        # --------------------------------------------------------

        title_signals = [
            "terms and conditions",
            "privacy policy",
            "privacy notice",
            "cookie policy",
            "return policy",
            "refund policy",
            "disclaimer",
            "policy on",
            "policy document",
            "key fact statement",
            "most important terms and conditions",
            "code of bank",
            "code of banks commitment",
            "customer commitment",
            "mobile banking privacy policy",
        ]

        title_hits = sum(
            1
            for signal in title_signals
            if signal in lower
        )

        # --------------------------------------------------------
        # Strong legal verbs / obligations.
        # --------------------------------------------------------

        obligation_signals = [
            "shall",
            "must",
            "may not",
            "is required to",
            "are required to",
            "will be responsible",
            "you are responsible",
            "customer shall",
            "bank shall",
            "we may",
            "we reserve the right",
        ]

        obligation_hits = sum(
            1
            for signal in obligation_signals
            if signal in lower
        )

        # --------------------------------------------------------
        # Decision rules
        # --------------------------------------------------------

        # Short policy-looking pages require stronger evidence.
        #
        # In particular, a title plus one or two generic obligation
        # words is not sufficient. This prevents tiny common-path
        # pages such as LeetCode's /privacy-policy variants from
        # becoming policy documents merely because their URL/title
        # contains a policy keyword.
        if is_short_policy_page:
            if len(matched_groups) >= 2:
                return True

            if (
                structural_hits >= 3
                and obligation_hits >= 3
                and title_hits >= 1
            ):
                return True

            return False

        # A clear policy title plus substantive structure is enough.
        if title_hits >= 1 and (
            structural_hits >= 2
            or obligation_hits >= 2
        ):
            return True

        # Two independent policy categories are strong evidence.
        if len(matched_groups) >= 2:
            return True

        # A single strong policy category needs structural support.
        if len(matched_groups) == 1:
            group = matched_groups[0]

            if group in {
                "terms",
                "privacy",
                "cookies",
                "returns",
                "legal",
                "banking_policy",
                "mitc_kfs",
            }:
                if (
                    structural_hits >= 2
                    or obligation_hits >= 3
                    or title_hits >= 1
                ):
                    return True

            if group in {
                "payments",
                "promotions",
            }:
                # Payment/promotion language is intentionally held
                # to a higher standard because ordinary service pages
                # use the same vocabulary.
                if (
                    title_hits >= 1
                    and (
                        structural_hits >= 2
                        or obligation_hits >= 3
                    )
                ):
                    return True

        # A strongly named legal URL still needs meaningful legal
        # structure. Generic words such as "payment" are not enough.
        if self._looks_like_policy_url(url):

            strong_url_path = re.sub(
                r"[^a-z0-9]+",
                " ",
                urlparse(url).path.lower(),
            )

            strong_url_terms = [
                "terms",
                "privacy",
                "cookie",
                "disclaimer",
                "legal",
                "agreement",
                "policy",
                "refund policy",
                "return policy",
                "data protection",
                "mitc",
                "kfs",
            ]

            url_strength = sum(
                1
                for term in strong_url_terms
                if term in strong_url_path
            )

            if url_strength >= 1 and (
                structural_hits >= 2
                or obligation_hits >= 3
                or title_hits >= 1
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
        """
        Return browser-provided candidate content.

        Candidates without content are intentionally returned as an
        empty string. They will proceed to backend extraction.
        """

        if not isinstance(candidate, dict):
            return ""

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
    # 1. Direct PDF extraction, if PDF
    # 2. Crawl4AI + Playwright
    # 3. Existing static scraper
    # 4. Existing dynamic scraper
    # 5. Jina Reader
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
        # PDF
        # --------------------------------------------------------

        if self._is_pdf_url(url):

            print(
                "Backend extraction received PDF URL. "
                "Using direct PDF extraction."
            )

            return self._try_pdf_extraction(
                url
            )

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
            "content_fingerprint": self._content_fingerprint(
                content
            ),
        }

    # ============================================================
    # CANDIDATE DEDUPLICATION
    # ============================================================

    def _deduplicate_candidates(
        self,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Deterministically deduplicate policy candidates.

        Candidate order must not depend on crawler/link-discovery order.
        Otherwise the MAX_BACKEND_CANDIDATES limit can cause different
        policies to be extracted on different runs.
        """

        unique = {}

        for candidate in candidates:

            if not isinstance(candidate, dict):
                continue

            url = str(
                candidate.get(
                    "url",
                    "",
                )
                or ""
            ).strip()

            if not url:
                continue

            key = self._canonical_url(url)

            if not key:
                continue

            if key not in unique:
                candidate = dict(candidate)
                candidate["url"] = key
                unique[key] = candidate

        # --------------------------------------------------------
        # Prefer a site's canonical policy route over locale/market
        # variants when both are present.
        #
        # Example:
        #   /policies/privacy
        #   /policies/br/privacy
        #   /policies/it/privacy
        #
        # These route variants are frequently alternate copies of the
        # same policy. Do not collapse arbitrary paths. Only suppress
        # a locale variant when the exact non-locale family route is
        # also present in this candidate set.
        # --------------------------------------------------------

        canonical_keys = set(unique.keys())
        locale_variants = []

        for key, candidate in unique.items():
            base_key = self._canonical_policy_family_key(key)

            if base_key and base_key != key:
                if base_key in canonical_keys:
                    locale_variants.append(key)

        for key in locale_variants:
            print(
                "Duplicate policy route rejected in favor of "
                f"canonical policy route: {key}"
            )
            unique.pop(key, None)

        # IMPORTANT:
        # Never preserve crawler discovery order.
        #
        # Sorting by canonical URL makes candidate selection stable
        # across repeated crawls of the same source page.
        return [
            unique[key]
            for key in sorted(
                unique.keys()
            )
        ]

    # ============================================================
    # POLICY FAMILY CANONICALIZATION
    # ============================================================

    def _canonical_policy_family_key(
        self,
        url: str,
    ) -> str:
        """
        Return the canonical non-locale route for narrowly defined
        policy URL families.

        This intentionally handles only locale-shaped policy routes,
        such as /policies/br/privacy. It does not merge arbitrary
        policy URLs because two independently named policy documents
        can legitimately contain different content.
        """

        try:
            parsed = urlparse(url)
        except Exception:
            return ""

        segments = [
            segment.lower()
            for segment in parsed.path.split("/")
            if segment
        ]

        if len(segments) < 3:
            return ""

        if segments[0] not in {
            "policy",
            "policies",
        }:
            return ""

        locale = segments[1]

        # Only treat a simple two-letter locale/market code as a
        # locale variant. This avoids swallowing meaningful policy
        # path segments such as /policies/business/privacy.
        if not re.fullmatch(
            r"[a-z]{2}",
            locale,
        ):
            return ""

        canonical_path = (
            "/"
            + "/".join(
                [segments[0]]
                + segments[2:]
            )
        )

        return self._canonical_url(
            (
                f"{parsed.scheme.lower()}://"
                f"{parsed.netloc.lower()}"
                f"{canonical_path}"
            )
        )

    # ============================================================
    # DOCUMENT DEDUPLICATION
    # ============================================================

    def _documents_are_near_duplicates(
        self,
        first: str,
        second: str,
    ) -> bool:
        """
        Detect substantially identical policy documents whose URLs differ.

        This is used only for whole-document deduplication. It is not used
        for Agent 2 source grounding, where exact source containment remains
        mandatory.

        Limit the comparison to a deterministic prefix/suffix window so
        very large privacy policies do not create excessive CPU cost.
        """

        def normalize(value: str) -> str:
            value = str(value or "").lower()

            value = re.sub(
                r"\s+",
                " ",
                value,
            )

            value = re.sub(
                r"\b(?:last updated|effective date|revision date)\s*[:\-]?\s*[a-z0-9, /.-]+",
                " ",
                value,
            )

            return value.strip()

        a = normalize(first)
        b = normalize(second)

        if not a or not b:
            return False

        # Very different document sizes are unlikely to be duplicate
        # policies, but allow modest variation for wrappers/appendices.
        shorter = min(len(a), len(b))
        longer = max(len(a), len(b))

        if shorter < 1000:
            return a == b

        if shorter / max(longer, 1) < 0.90:
            return False

        window = 20000

        if len(a) > window:
            a = a[:10000] + " " + a[-10000:]

        if len(b) > window:
            b = b[:10000] + " " + b[-10000:]

        similarity = difflib.SequenceMatcher(
            None,
            a,
            b,
            autojunk=False,
        ).ratio()

        return similarity >= 0.96

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

            content_hash = self._content_fingerprint(
                content
            )

            if url in seen_urls:
                continue

            if content_hash in seen_hashes:
                print(
                    "Duplicate document content rejected: "
                    f"{document.get('url', '')}"
                )
                continue

            duplicate_of = None

            for existing in result:
                existing_content = str(
                    existing.get(
                        "content",
                        "",
                    )
                    or ""
                )

                if self._documents_are_near_duplicates(
                    existing_content,
                    content,
                ):
                    duplicate_of = existing
                    break

            if duplicate_of is not None:
                existing_url = duplicate_of.get(
                    "url",
                    "",
                )

                # Prefer the canonical policy-family route when one
                # exists. Otherwise prefer the longer substantive
                # document because it gives downstream agents more
                # complete source material.
                existing_family = (
                    self._canonical_policy_family_key(
                        self._canonical_url(
                            existing_url
                        )
                    )
                )

                current_family = (
                    self._canonical_policy_family_key(
                        url
                    )
                )

                prefer_current = False

                if (
                    current_family
                    and not existing_family
                ):
                    prefer_current = True
                elif (
                    len(content)
                    > len(existing_content)
                ):
                    prefer_current = True

                if prefer_current:
                    print(
                        "Near-duplicate policy replaced by "
                        f"more canonical/substantive route: "
                        f"{existing_url} -> {url}"
                    )

                    result.remove(
                        duplicate_of
                    )

                    # Remove the old fingerprint from the exact
                    # duplicate set. It is no longer represented.
                    seen_hashes.discard(
                        self._content_fingerprint(
                            existing_content
                        )
                    )

                else:
                    print(
                        "Near-duplicate policy rejected: "
                        f"{document.get('url', '')} "
                        f"(duplicate of {existing_url})"
                    )
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