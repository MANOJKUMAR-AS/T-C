from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

try:
    from google import genai
except Exception:
    genai = None

from .risk_scoring import (
    score_clauses,
    overall_score,
    level_for_score,
)

from .classifier import suggest_category


HERE = Path(__file__).resolve()
BACKEND = HERE.parents[2]
PROJECT = BACKEND.parent

for env in (PROJECT / ".env", BACKEND / ".env"):
    if env.exists():
        load_dotenv(env, override=False)


class Agent2:
    name = "Clause and Risk Analysis Agent"

    MAX_CHUNK = int(
        os.getenv("LLM_CHUNK_CHARS", "9000")
    )

    OVERLAP = int(
        os.getenv("LLM_CHUNK_OVERLAP_CHARS", "300")
    )

    MAX_REQUESTS = int(
        os.getenv("LLM_MAX_REQUESTS_PER_RUN", "12")
    )

    DELAY = float(
        os.getenv("LLM_REQUEST_DELAY_SECONDS", "12.5")
    )

    OUTPUT_TOKENS = int(
        os.getenv("LLM_MAX_OUTPUT_TOKENS", "3000")
    )

    MODEL = os.getenv(
        "GEMINI_MODEL",
        "gemini-3.5-flash-lite",
    )

    FALLBACK = os.getenv(
        "GEMINI_FALLBACK_MODEL",
        "gemini-3.5-flash",
    )

    MIN_TEXT_LENGTH = 220

    # ----------------------------------------------------------
    # Allowed categories
    # ----------------------------------------------------------

    ALLOWED_CATEGORIES = {
        "privacy",
        "data_collection",
        "data_sharing",
        "payments",
        "subscription",
        "cancellation",
        "refund",
        "auto_renewal",
        "intellectual_property",
        "license",
        "liability",
        "indemnification",
        "arbitration",
        "dispute_resolution",
        "governing_law",
        "termination",
        "account",
        "user_content",
        "advertising",
        "tracking",
        "security",
        "age_requirement",
        "prohibited_use",
        "third_party_services",
        "warranty",
        "limitation_of_liability",
        "other",
    }

    ALLOWED_RISK_LEVELS = {
        "low",
        "medium",
        "high",
        "critical",
    }

    # Strong indicators that a chunk contains substantive
    # legal/privacy material rather than page navigation.
    RELEVANCE_TERMS = [
        "terms and conditions",
        "terms of use",
        "terms of service",
        "privacy policy",
        "privacy",
        "personal information",
        "personal data",
        "collect",
        "use of information",
        "share",
        "third party",
        "service provider",
        "cookies",
        "tracking",
        "retention",
        "security",
        "consent",
        "disclosure",
        "intellectual property",
        "license",
        "copyright",
        "liability",
        "indemnification",
        "arbitration",
        "dispute",
        "governing law",
        "termination",
        "suspend",
        "refund",
        "cancellation",
        "payment",
        "fee",
        "charge",
        "subscription",
        "renewal",
        "warranty",
        "damages",
        "user content",
        "account",
        "prohibited",
        "eligible",
        "age",
        "grievance",
    ]

    # ----------------------------------------------------------
    # Deterministic navigation / page-chrome filtering
    # ----------------------------------------------------------
    #
    # Policy pages often contain navigation, product menus, footer
    # links, banners, and other website chrome. These can contain
    # legal-looking keywords without being legal provisions.
    NAVIGATION_PATTERNS = [
        r"\b(add to cart|shop now|buy now|product details|best sellers|wishlist)\b",
        r"\b(categories|sort by|filter by|filter|menu|navigation)\b",
        r"\b(home|about us|contact us|careers|press|blog|news|login|sign in|sign up)\b",
        r"\b(quick links|useful links|related links|site map|sitemap)\b",
        r"\b(corporate banking|current accounts|card management|net banking)\b",
    ]

    NAVIGATION_TERMS = {
        "home", "about us", "contact us", "careers", "press", "blog",
        "news", "login", "sign in", "sign up", "menu", "navigation",
        "quick links", "useful links", "related links", "site map",
        "sitemap", "categories", "sort by", "filter", "wishlist",
        "add to cart", "shop now", "buy now", "product details",
        "best sellers", "corporate banking", "current accounts",
        "card management", "net banking",
    }

    SUBSTANTIVE_LEGAL_TERMS = [
        "shall", "must", "may", "agree", "consent", "obligation",
        "prohibited", "permitted", "rights", "responsible", "liable",
        "liability", "indemnif", "arbitrat", "governed by", "terminate",
        "suspend", "collect", "personal data", "personal information",
        "disclose", "share", "retain", "refund", "fee", "charge",
        "payment", "subscription", "renew", "license", "copyright",
        "trademark", "warranty", "damages", "privacy", "security",
        "cookies", "tracking",
    ]

    # ----------------------------------------------------------
    # Deterministic legal patterns
    # ----------------------------------------------------------

    LEGAL_PATTERNS = [
        (
            "Age Requirement",
            "age_requirement",
            [
                r"\bminors?\b",
                r"\b18 years of age\b",
                r"\bunder the age of\b",
                r"\bat least 18\b",
                r"\bchildren under\b",
                r"\bage requirement\b",
                r"\bminimum age\b",
            ],
        ),
        (
            "Prohibited Use",
            "prohibited_use",
            [
                r"\bexpressly restricted\b",
                r"\bprohibited conduct\b",
                r"\bprohibited activities\b",
                r"\byou must not\b",
                r"\byou agree not to\b",
                r"\bnot permitted to\b",
                r"\brestrictions\b",
            ],
        ),
        (
            "Data Collection",
            "data_collection",
            [
                r"\bcollect(?:s|ed|ing)?\b.{0,220}\b(?:personal|user|customer)\b.{0,160}\b(?:data|information)\b",
                r"\bpersonal information\b.{0,220}\bcollect",
                r"\bwe collect\b",
                r"\bpersonal data\b.{0,180}\bcollect",
            ],
        ),
        (
            "Data Sharing",
            "data_sharing",
            [
                r"\bshare(?:s|d|ing)?\b.{0,220}\b(?:third parties|partners|service providers)\b",
                r"\bservice providers\b.{0,220}\b(?:data|information)\b",
                r"\b(?:business|advertising) partners\b",
                r"\bthird[- ]party\b.{0,180}\b(?:data|information)\b",
            ],
        ),
        (
            "Cookies and Tracking",
            "tracking",
            [
                r"\bcookies?\b",
                r"\btracking technologies\b",
                r"\bpixels?\b",
                r"\bweb beacons?\b",
                r"\banalytics\b",
            ],
        ),
        (
            "Data Retention",
            "privacy",
            [
                r"\bretain(?:s|ed|ing)?\b.{0,220}\b(?:data|information)\b",
                r"\bretention\b.{0,220}\b(?:data|information)\b",
                r"\bkeep\b.{0,150}\b(?:data|information)\b",
            ],
        ),
        (
            "Policy Changes",
            "other",
            [
                r"\bmay change\b.{0,220}\b(?:terms|policy|agreement)\b",
                r"\bmodify\b.{0,220}\b(?:terms|policy|agreement)\b",
                r"\bcontinued use\b.{0,220}\b(?:accept|agree)\b",
                r"\bwithout notice\b",
            ],
        ),
        (
            "Account Termination",
            "termination",
            [
                r"\bterminate\b.{0,220}\b(?:account|service)\b",
                r"\bsuspend\b.{0,220}\b(?:account|service)\b",
                r"\btermination\b.{0,220}\b(?:account|service)\b",
            ],
        ),
        (
            "Limitation of Liability",
            "limitation_of_liability",
            [
                r"\blimitation of liability\b",
                r"\bnot liable\b",
                r"\bmaximum liability\b",
                r"\bexclude\b.{0,140}\bdamages\b",
                r"\blimited liability\b",
            ],
        ),
        (
            "Arbitration",
            "arbitration",
            [
                r"\bbinding arbitration\b",
                r"\bmandatory arbitration\b",
                r"\barbitrat(?:e|ion)\b",
            ],
        ),
        (
            "Class Action Waiver",
            "dispute_resolution",
            [
                r"\bclass[- ]action\b",
                r"\bclass action waiver\b",
            ],
        ),
        (
            "Indemnification",
            "indemnification",
            [
                r"\bindemnif(?:y|ies|ied|ication)\b",
                r"\bhold harmless\b",
            ],
        ),
        (
            "User Content License",
            "license",
            [
                r"\broyalty[- ]free\b",
                r"\birrevocable\b.{0,120}\blicense\b",
                r"\bworldwide\b.{0,120}\blicense\b",
                r"\blicense\b.{0,180}\buser content\b",
                r"\buser content\b.{0,180}\blicense\b",
            ],
        ),
        (
            "Government Disclosure",
            "privacy",
            [
                r"\blaw enforcement\b",
                r"\bgovernment authorities\b",
                r"\blegal process\b",
                r"\bgovernment request\b",
            ],
        ),
        (
            "Advertising and Targeting",
            "advertising",
            [
                r"\btargeted advertising\b",
                r"\binterest[- ]based advertising\b",
                r"\bpersonalized advertising\b",
                r"\badvertising partners\b",
            ],
        ),
        (
            "Sensitive Personal Information",
            "privacy",
            [
                r"\bhealth information\b",
                r"\bbiometric\b",
                r"\bprecise location\b",
                r"\bfinancial information\b",
                r"\bsexual orientation\b",
            ],
        ),
        (
            "Cancellation and Refunds",
            "refund",
            [
                r"\bcancel(?:lation)?\b.{0,220}\b(?:subscription|order|service)\b",
                r"\brefund(?:s)?\b",
                r"\bnon[- ]refundable\b",
            ],
        ),
        (
            "Payment Obligations",
            "payments",
            [
                r"\bpayment\b.{0,220}\b(?:credit card|debit card|fee|charge)\b",
                r"\bfees?\b.{0,220}\b(?:pay|payment|charge)\b",
                r"\bautomatically charge\b",
            ],
        ),
        (
            "Subscription and Auto-Renewal",
            "auto_renewal",
            [
                r"\bauto(?:matic|matically)[- ]?renew",
                r"\bauto[- ]renewal\b",
                r"\bsubscription\b.{0,220}\brenew",
            ],
        ),
        (
            "Governing Law",
            "governing_law",
            [
                r"\bgoverning law\b",
                r"\bgoverned by the laws\b",
                r"\bjurisdiction\b",
            ],
        ),
        (
            "Intellectual Property",
            "intellectual_property",
            [
                r"\bintellectual property\b",
                r"\bcopyright\b",
                r"\btrademark\b",
                r"\bproprietary rights\b",
            ],
        ),
        (
            "Warranty Disclaimer",
            "warranty",
            [
                r"\bwithout warranty\b",
                r"\bdisclaim(?:s|ed|er)?\b.{0,180}\bwarrant",
                r"\bas is\b.{0,120}\bwithout\b.{0,120}\bwarrant",
            ],
        ),
    ]

    # ==========================================================
    # INITIALIZATION
    # ==========================================================

    def __init__(self):
        self.api_key = os.getenv(
            "GEMINI_API_KEY",
            "",
        ).strip()

        self.client = None

        if self.api_key and genai:
            try:
                self.client = genai.Client(
                    api_key=self.api_key
                )

                print(
                    "Agent 2: Gemini client initialized."
                )

            except Exception as exc:
                print(
                    f"Agent 2: Gemini initialization failed: {exc}"
                )
        else:
            print(
                "Agent 2: GEMINI_API_KEY not configured "
                "or google-genai missing."
            )

    # ==========================================================
    # MAIN
    # ==========================================================

    def run(
        self,
        policies: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        print()
        print("=" * 70)
        print("AGENT 2 - CLAUSE AND RISK ANALYSIS")
        print("=" * 70)

        print(
            f"Policy documents received: {len(policies)}"
        )

        if not policies:
            return self._result(
                clauses=[],
                errors=[
                    "No policy documents were supplied to Agent 2."
                ],
                status="complete",
            )

        chunks = self._build_balanced_chunks(
            policies
        )

        print(
            f"Analysis chunks selected: {len(chunks)}"
        )

        if not chunks:
            return self._result(
                clauses=[],
                errors=[
                    "No usable policy text was found."
                ],
                status="complete",
            )

        clauses: List[Dict[str, Any]] = []
        errors: List[str] = []

        last_request = 0.0

        for request_number, item in enumerate(
            chunks,
            1,
        ):

            wait = self.DELAY - (
                time.monotonic() - last_request
            )

            if wait > 0:
                time.sleep(wait)

            print(
                f"Gemini request #{request_number}/"
                f"{len(chunks)} | "
                f"{item['document_type']} | "
                f"chunk {item['chunk_index']} | "
                f"relevance {item['relevance_score']}"
            )

            result = None

            # --------------------------------------------------
            # Primary Gemini
            # --------------------------------------------------

            if self.client:

                result = self._request(
                    self.MODEL,
                    item["text"],
                )

                last_request = time.monotonic()

            # --------------------------------------------------
            # Gemini fallback model
            # --------------------------------------------------

            if result is None and self.client:

                print(
                    "Primary model failed. "
                    f"Trying fallback: {self.FALLBACK}"
                )

                result = self._request(
                    self.FALLBACK,
                    item["text"],
                )

                last_request = time.monotonic()

            # --------------------------------------------------
            # Deterministic extraction fallback
            # --------------------------------------------------

            if not result:

                print(
                    "Gemini returned no usable clauses. "
                    "Running deterministic fallback."
                )

                result = self._fallback_extract(
                    item["text"]
                )

            if not result:

                errors.append(
                    f"Chunk {request_number} produced no clauses."
                )

                continue

            # --------------------------------------------------
            # Remove navigation/page-chrome clauses before they
            # enter normalization, scoring, or downstream agents.
            # --------------------------------------------------

            result = self._filter_extracted_clauses(
                result
            )

            if not result:

                print(
                    "All extracted clauses were rejected as "
                    "navigation/page chrome or non-substantive text."
                )

                continue

            # --------------------------------------------------
            # Attach deterministic document metadata
            # --------------------------------------------------

            for clause in result:

                if not isinstance(
                    clause,
                    dict,
                ):
                    continue

                title = str(
                    clause.get(
                        "title",
                        "",
                    )
                ).strip()

                source_text = str(
                    clause.get(
                        "source_text",
                        "",
                    )
                ).strip()

                if not title or not source_text:
                    continue

                clause["document_url"] = str(
                    item.get(
                        "document_url",
                        "",
                    )
                    or ""
                ).strip()

                clause["document_type"] = str(
                    item.get(
                        "document_type",
                        "legal",
                    )
                    or "legal"
                ).strip()

                clause["chunk_index"] = int(
                    item.get(
                        "chunk_index",
                        0,
                    )
                    or 0
                )

                # Risk generated by Gemini is intentionally NOT
                # trusted as the final risk value.
                #
                # risk_scoring.py is the authoritative risk engine.
                clause.pop(
                    "_gemini_risk_level",
                    None,
                )

                clauses.append(
                    clause
                )

        # ------------------------------------------------------
        # Deterministic clause normalization
        # ------------------------------------------------------

        clauses = self._normalize_and_dedupe(
            clauses
        )

        # ------------------------------------------------------
        # Deterministic clause-level risk
        #
        # Agent 2 risk_scoring.py is the single source of truth.
        # ------------------------------------------------------

        clauses = score_clauses(
            clauses
        )

        # Stable final ordering.
        clauses.sort(
            key=self._clause_sort_key
        )

        # ------------------------------------------------------
        # IMPORTANT:
        #
        # Overall risk is calculated from deterministic source
        # evidence, NOT from whichever variable set Gemini
        # happened to return during this particular request.
        # ------------------------------------------------------

        summary = self._summary(
            clauses,
            chunks=chunks,
        )

        # ------------------------------------------------------
        # FINAL CLAUSE AUDIT
        #
        # This diagnostic block prints the exact clauses that
        # survived grounding, substantive-content filtering,
        # category reconciliation, normalization, deduplication,
        # and deterministic risk scoring.
        #
        # It does not modify the clauses or their values.
        # ------------------------------------------------------

        print()
        print("=" * 70)
        print("AGENT 2 FINAL CLAUSE AUDIT")
        print("=" * 70)

        for final_index, clause in enumerate(
            clauses,
            1,
        ):
            print()
            print(
                f"AGENT 2 FINAL CLAUSE #{final_index}"
            )
            print(
                f"title={clause.get('title', '')}"
            )
            print(
                f"category={clause.get('category', '')}"
            )
            print(
                f"risk_level={clause.get('risk_level', '')}"
            )
            print(
                f"risk_score={clause.get('risk_score', '')}"
            )
            print(
                f"document_type={clause.get('document_type', '')}"
            )
            print(
                f"document_url={clause.get('document_url', '')}"
            )
            print(
                f"chunk_index={clause.get('chunk_index', '')}"
            )
            print(
                f"source_text={clause.get('source_text', '')}"
            )

        print()
        print("=" * 70)
        print(
            f"AGENT 2 FINAL CLAUSE AUDIT COMPLETE: "
            f"{len(clauses)} clauses"
        )
        print("=" * 70)

        status = "complete"

        if errors and clauses:
            status = "partial"

        if errors and not clauses:
            status = "failed"

        print()
        print(
            f"AGENT 2 COMPLETE: {len(clauses)} clauses"
        )

        print(
            f"Overall risk: "
            f"{summary['overall_risk']} "
            f"({summary['overall_score']})"
        )

        print("=" * 70)

        return self._result(
            clauses=clauses,
            errors=errors,
            status=status,
            summary=summary,
        )

    # ==========================================================
    # CHUNK SELECTION
    # ==========================================================

    def _build_balanced_chunks(
        self,
        policies: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        candidates: List[
            Dict[str, Any]
        ] = []

        for doc_index, policy in enumerate(
            policies
        ):

            text = str(
                policy.get("content")
                or policy.get("text")
                or ""
            ).strip()

            if len(text) < self.MIN_TEXT_LENGTH:
                continue

            chunks = self._chunks(text)

            print(
                f"Document {doc_index + 1}: "
                f"{len(text)} chars -> "
                f"{len(chunks)} chunks"
            )

            for chunk_index, chunk in enumerate(
                chunks
            ):

                score = self._relevance_score(
                    chunk
                )

                if score <= 0:
                    continue

                candidates.append(
                    {
                        "document_index": doc_index,
                        "document_url": str(
                            policy.get(
                                "url",
                                "",
                            )
                            or ""
                        ).strip(),
                        "document_type": str(
                            policy.get(
                                "type",
                                "legal",
                            )
                            or "legal"
                        ).strip(),
                        "chunk_index": chunk_index,
                        "text": chunk,
                        "relevance_score": score,
                    }
                )

        if not candidates:

            print(
                "No high-relevance chunks found. "
                "Using first available chunks."
            )

            for doc_index, policy in enumerate(
                policies
            ):

                text = str(
                    policy.get("content")
                    or policy.get("text")
                    or ""
                ).strip()

                if len(text) < self.MIN_TEXT_LENGTH:
                    continue

                for chunk_index, chunk in enumerate(
                    self._chunks(text)
                ):

                    candidates.append(
                        {
                            "document_index": doc_index,
                            "document_url": str(
                                policy.get(
                                    "url",
                                    "",
                                )
                                or ""
                            ).strip(),
                            "document_type": str(
                                policy.get(
                                    "type",
                                    "legal",
                                )
                                or "legal"
                            ).strip(),
                            "chunk_index": chunk_index,
                            "text": chunk,
                            "relevance_score": 0,
                        }
                    )

        # ------------------------------------------------------
        # DETERMINISTIC RANKING
        # ------------------------------------------------------

        candidates.sort(
            key=lambda item: (
                -int(
                    item.get(
                        "relevance_score",
                        0,
                    )
                    or 0
                ),
                self._canonical_url(
                    item.get(
                        "document_url",
                        "",
                    )
                ),
                str(
                    item.get(
                        "document_type",
                        "legal",
                    )
                    or "legal"
                ).strip().lower(),
                int(
                    item.get(
                        "chunk_index",
                        0,
                    )
                    or 0
                ),
            )
        )

        # Prevent one document from consuming all requests.
        selected: List[
            Dict[str, Any]
        ] = []

        per_document: Dict[
            str,
            int,
        ] = {}

        for item in candidates:

            document_key = self._canonical_url(
                item.get(
                    "document_url",
                    "",
                )
            )

            used = per_document.get(
                document_key,
                0,
            )

            if used >= 4:
                continue

            selected.append(
                item
            )

            per_document[
                document_key
            ] = used + 1

            if len(selected) >= self.MAX_REQUESTS:
                break

        # Fill remaining slots deterministically.
        if len(selected) < self.MAX_REQUESTS:

            selected_keys = {
                (
                    self._canonical_url(
                        item.get(
                            "document_url",
                            "",
                        )
                    ),
                    int(
                        item.get(
                            "chunk_index",
                            0,
                        )
                        or 0
                    ),
                )
                for item in selected
            }

            for item in candidates:

                key = (
                    self._canonical_url(
                        item.get(
                            "document_url",
                            "",
                        )
                    ),
                    int(
                        item.get(
                            "chunk_index",
                            0,
                        )
                        or 0
                    ),
                )

                if key in selected_keys:
                    continue

                selected.append(
                    item
                )

                if len(selected) >= self.MAX_REQUESTS:
                    break

        return selected

    def _relevance_score(
        self,
        text: str,
    ) -> int:

        normalized = re.sub(
            r"\s+",
            " ",
            text.lower(),
        )

        score = 0

        for term in self.RELEVANCE_TERMS:

            occurrences = normalized.count(
                term
            )

            if occurrences:
                score += min(
                    occurrences,
                    4,
                )

        heading_count = len(
            re.findall(
                r"(?:^|\n)\s{0,3}(?:#+\s+|"
                r"[A-Z][A-Z\s]{4,80}:)",
                text,
            )
        )

        score += min(
            heading_count,
            6,
        )

        navigation_terms = [
            "add to cart",
            "shop now",
            "buy now",
            "product details",
            "best sellers",
            "categories",
            "sort by",
            "filter",
            "wishlist",
        ]

        for term in navigation_terms:

            if term in normalized:
                score -= 1

        return max(
            0,
            score,
        )

    # ==========================================================
    # CHUNKING
    # ==========================================================

    def _chunks(
        self,
        text: str,
    ) -> List[str]:

        if len(text) <= self.MAX_CHUNK:
            return [text]

        out: List[str] = []

        start = 0

        while start < len(text):

            end = min(
                len(text),
                start + self.MAX_CHUNK,
            )

            chunk = text[start:end]

            if end < len(text):

                cut = chunk.rfind(
                    "\n\n"
                )

                if cut > self.MAX_CHUNK * 0.55:
                    chunk = chunk[:cut]
                    end = start + cut

                else:

                    cut = chunk.rfind(
                        ". "
                    )

                    if cut > self.MAX_CHUNK * 0.65:
                        chunk = chunk[:cut + 1]
                        end = start + cut + 1

            if chunk.strip():
                out.append(
                    chunk.strip()
                )

            next_start = (
                end - self.OVERLAP
            )

            if next_start <= start:
                next_start = end
                start = next_start
                continue

            # ------------------------------------------------
            # WORD-BOUNDARY SAFETY:
            # Advance next_start forward so the next chunk
            # never begins inside a word.
            #
            # Without this guard the overlap calculation can
            # place next_start in the middle of a token (e.g.
            # "Whi | le, we process...") causing every clause
            # Gemini extracts from that chunk to start with a
            # truncated word fragment that _repair_source_
            # boundaries cannot fix (the missing prefix is
            # before the chunk boundary).
            #
            # Step 1: skip past any remaining alphanumeric
            #         characters of the current word.
            # Step 2: skip any non-alphanumeric, non-space
            #         punctuation still attached to that word
            #         (apostrophes, commas, hyphens etc.).
            # Step 3: skip whitespace to land on the first
            #         character of the next word.
            # ------------------------------------------------

            # Step 1 – skip rest of partial word
            while (
                next_start < len(text)
                and next_start > 0
                and text[next_start - 1].isalnum()
                and text[next_start].isalnum()
            ):
                next_start += 1

            # Step 2 – skip attached punctuation (e.g. comma
            # directly after a word: "word,")
            while (
                next_start < len(text)
                and not text[next_start].isspace()
                and not text[next_start].isalnum()
            ):
                next_start += 1

            # Step 3 – skip whitespace
            while (
                next_start < len(text)
                and text[next_start].isspace()
            ):
                next_start += 1

            if next_start <= start:
                next_start = end

            start = next_start

        return out

    # ==========================================================
    # GEMINI EXTRACTION
    # ==========================================================

    def _request(
        self,
        model: str,
        text: str,
    ) -> Optional[
        List[Dict[str, Any]]
    ]:

        prompt = f"""
You are the clause extraction engine of an AI Terms & Conditions
Analyzer.

Analyze ONLY the supplied document text.

Return ONLY valid JSON in exactly this structure:

{{
  "clauses": [
    {{
      "clause_id": "unique short id",
      "title": "short clause title",
      "category": "one of the allowed categories",
      "summary": "plain-language summary",
      "explanation": "why this matters to a user",
      "obligations": [],
      "permissions": [],
      "restrictions": [],
      "consequences": [],
      "risk_level": "low",
      "risk_reason": "brief factual reason",
      "source_text": "brief exact excerpt from the supplied text"
    }}
  ]
}}

Allowed categories:

privacy
data_collection
data_sharing
payments
subscription
cancellation
refund
auto_renewal
intellectual_property
license
liability
indemnification
arbitration
dispute_resolution
governing_law
termination
account
user_content
advertising
tracking
security
age_requirement
prohibited_use
third_party_services
warranty
limitation_of_liability
other

Allowed risk levels:

low
medium
high
critical

IMPORTANT RISK RULE:

The risk_level and risk_reason fields are only auxiliary extraction
metadata. The final risk score and final risk level will be calculated
deterministically by the application's risk_scoring engine.

Extraction rules:

1. Extract substantive legal, contractual, privacy, payment,
   account, liability, intellectual-property, or user-rights
   provisions.

2. Do not return a document-level summary.

3. Do not invent information.

4. Every clause MUST be supported by source_text.

5. source_text MUST be copied verbatim from the supplied document
   text as one contiguous excerpt.

6. Do NOT paraphrase, summarize, rewrite, reorder, normalize, or
   translate source_text.

7. Do NOT add words, headings, labels, bullets, or explanations
   that are not present in the supplied document text.

8. Do NOT use ellipses unless the omitted middle text is actually
   represented by an ellipsis in the supplied document.

9. If you cannot copy a contiguous source excerpt exactly, do not
   return that clause.

10. Extract multiple clauses when multiple substantive provisions
    are present.

11. Do not extract menus, navigation, product listings,
   recommendations, advertisements, cookie-banner buttons,
   footer navigation, or page chrome.

12. Preserve ambiguity from the source.

13. Use [] when obligations, permissions, restrictions,
   or consequences are not present.

14. If substantive legal provisions exist in the supplied text,
    return clauses rather than an empty list.

15. Keep each clause focused on one substantive provision.

16. Do not merge unrelated provisions merely to reduce the
    number of clauses.

17. Policy amendment classification rule:
    If the primary purpose of a clause is to state that a Privacy Policy,
    Terms, Agreement, Notice, or similar legal document may be amended,
    modified, updated, revised, changed, or replaced, classify it as 'other'.
    Do not classify it as 'data_collection' merely because the amendment
    clause mentions data collection, data use, information, privacy
    practices, technology, or changes in law. Use 'data_collection' only
    when the clause itself describes an actual practice of collecting,
    obtaining, gathering, receiving, recording, or acquiring user or
    personal data.

    Negative example:
    "We reserve the right to amend this Privacy Policy from time to time to reflect changes in the law, our data collection and use practices, the features of our services, or advances in technology."
    Expected category: "other"
    Reason: "The clause governs amendment of the Privacy Policy. 'data collection and use practices' is only a subject of possible future policy changes and does not describe an actual data-collection practice."

DOCUMENT TEXT:

{text}
"""

        if not self.client:
            return None

        try:

            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": 0.1,
                    "max_output_tokens": self.OUTPUT_TOKENS,
                    "response_mime_type": "application/json",
                },
            )

            raw = getattr(
                response,
                "text",
                "",
            ) or ""

            if not raw.strip():

                print(
                    "Gemini response contained no text."
                )

                return None

            data = self._parse_json(
                raw
            )

            if not isinstance(
                data,
                dict,
            ):
                return None

            raw_clauses = data.get(
                "clauses",
                [],
            )

            if not isinstance(
                raw_clauses,
                list,
            ):
                return None

            clean: List[
                Dict[str, Any]
            ] = []

            grounding_rejections: List[
                Dict[str, Any]
            ] = []

            for index, clause in enumerate(
                raw_clauses[:30],
                1,
            ):

                if not isinstance(
                    clause,
                    dict,
                ):
                    continue

                title = self._clean_text(
                    clause.get(
                        "title",
                        "",
                    )
                )

                source_text = self._clean_text(
                    clause.get(
                        "source_text",
                        "",
                    )
                )

                if not title or not source_text:
                    continue

                # --------------------------------------------------
                # Validate that Gemini's source excerpt actually
                # exists in the supplied chunk.
                #
                # IMPORTANT:
                # Do not accept an ungrounded excerpt. Instead, keep
                # the rejected clause so a dedicated grounding-repair
                # request can attempt to recover the exact source text.
                # --------------------------------------------------

                if not self._source_exists(
                    text,
                    source_text,
                ):

                    print(
                        "Rejected Gemini clause: "
                        "source_text not found in source chunk."
                    )

                    grounding_rejections.append(
                        dict(clause)
                    )

                    continue

                # --------------------------------------------------
                # Deterministic source-boundary repair
                #
                # _source_exists() proves that the excerpt is grounded,
                # but a grounded substring can still begin or end in
                # the middle of a word when Gemini selects a fragment
                # from a chunk boundary.
                #
                # Expand only across actual adjacent word characters
                # in the supplied source. No text is invented and no
                # fuzzy matching is used.
                #
                # If the repair returns "" it means the sentence start
                # lies before the chunk boundary and cannot be reached.
                # In that case reject the clause to grounding_rejections
                # so the overlapping chunk can supply a clean excerpt.
                # --------------------------------------------------

                repaired_source_text = (
                    self._repair_source_boundaries(
                        text,
                        source_text,
                    )
                )

                if repaired_source_text == "":
                    # Repair detected an unresolvable boundary cut.
                    print(
                        "Rejected Gemini clause: "
                        "source_text starts at chunk boundary "
                        "(sentence start not in this chunk)."
                    )
                    grounding_rejections.append(
                        dict(clause)
                    )
                    continue

                if repaired_source_text:
                    source_text = repaired_source_text

                category = self._normalize_category(
                    clause.get(
                        "category",
                        "other",
                    )
                )

                gemini_risk = self._normalize_risk(
                    clause.get(
                        "risk_level",
                        "medium",
                    )
                )

                risk_reason = self._clean_text(
                    clause.get(
                        "risk_reason",
                        "",
                    )
                )

                normalized = {
                    "clause_id": (
                        self._stable_clause_id(
                            title=title,
                            category=category,
                            source_text=source_text,
                        )
                    ),

                    "title": title,

                    "category": category,

                    "summary": self._clean_text(
                        clause.get(
                            "summary",
                            "",
                        )
                    ),

                    "explanation": self._clean_text(
                        clause.get(
                            "explanation",
                            "",
                        )
                    ),

                    "obligations": self._list_value(
                        clause.get(
                            "obligations",
                            [],
                        )
                    ),

                    "permissions": self._list_value(
                        clause.get(
                            "permissions",
                            [],
                        )
                    ),

                    "restrictions": self._list_value(
                        clause.get(
                            "restrictions",
                            [],
                        )
                    ),

                    "consequences": self._list_value(
                        clause.get(
                            "consequences",
                            [],
                        )
                    ),

                    # Gemini risk is retained only as internal
                    # metadata and is removed before final scoring.
                    "_gemini_risk_level": gemini_risk,

                    "risk_level": gemini_risk,

                    "risk_reason": risk_reason,

                    "source_text": source_text[:1200],
                }

                clean.append(
                    normalized
                )

            # --------------------------------------------------
            # Dedicated grounding repair
            #
            # Gemini sometimes understands the clause correctly but
            # paraphrases the requested source excerpt. The primary
            # extraction is rejected in that case. A second, narrowly
            # scoped request is used only to repair the source excerpt.
            #
            # The repair request cannot invent or paraphrase text:
            # every repaired source_text is validated again with the
            # same deterministic _source_exists() gate.
            # --------------------------------------------------

            if grounding_rejections:

                repaired = self._repair_grounding(
                    model=model,
                    text=text,
                    rejected_clauses=grounding_rejections,
                )

                if repaired:
                    clean.extend(
                        repaired
                    )

            if clean:

                print(
                    f"Gemini extracted "
                    f"{len(clean)} clauses."
                )

            return clean

        except Exception as exc:

            print(
                f"Gemini error: {exc}"
            )

            return None

    def _repair_grounding(
        self,
        model: str,
        text: str,
        rejected_clauses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Repair only source excerpts rejected by the primary extraction.

        This is intentionally narrower than re-running full clause
        extraction. The semantic clause generated by the first request
        is preserved, while Gemini is asked to replace only its
        source_text with an exact contiguous excerpt from the supplied
        chunk.

        The repaired excerpt is still passed through _source_exists().
        Therefore this method never weakens the grounding guarantee.
        """

        if not self.client or not rejected_clauses:
            return []

        repair_items = []

        for index, clause in enumerate(
            rejected_clauses[:10],
            1,
        ):
            repair_items.append(
                {
                    "repair_index": index,
                    "title": self._clean_text(
                        clause.get("title", "")
                    ),
                    "category": self._normalize_category(
                        clause.get("category", "other")
                    ),
                    "summary": self._clean_text(
                        clause.get("summary", "")
                    ),
                    "explanation": self._clean_text(
                        clause.get("explanation", "")
                    ),
                    "obligations": self._list_value(
                        clause.get("obligations", [])
                    ),
                    "permissions": self._list_value(
                        clause.get("permissions", [])
                    ),
                    "restrictions": self._list_value(
                        clause.get("restrictions", [])
                    ),
                    "consequences": self._list_value(
                        clause.get("consequences", [])
                    ),
                    "risk_level": self._normalize_risk(
                        clause.get("risk_level", "medium")
                    ),
                    "risk_reason": self._clean_text(
                        clause.get("risk_reason", "")
                    ),
                    "invalid_source_text": self._clean_text(
                        clause.get("source_text", "")
                    ),
                }
            )

        repair_payload = json.dumps(
            repair_items,
            ensure_ascii=False,
        )

        prompt = f"""
You are a source-grounding repair engine for an AI Terms &
Conditions Analyzer.

A previous extraction identified the clauses below, but their
source_text values FAILED exact grounding validation.

Your ONLY task is to repair the source_text fields.

Do NOT change the meaning of the clauses.
Do NOT invent clauses.
Do NOT add new clauses.
Do NOT rewrite, summarize, translate, or paraphrase source text.

Return ONLY valid JSON in exactly this structure:

{{
  "clauses": [
    {{
      "repair_index": 1,
      "source_text": "exact contiguous excerpt copied from DOCUMENT TEXT"
    }}
  ]
}}

GROUNDING RULES:

1. source_text MUST be copied verbatim from DOCUMENT TEXT.

2. source_text MUST be one contiguous excerpt from DOCUMENT TEXT.

3. Do not add, remove, reorder, translate, or paraphrase words.

4. Do not normalize punctuation, spelling, capitalization, or wording.

5. Do not create an excerpt by combining separate parts of the
   document.

6. Do not use ellipses unless the exact ellipsis appears in DOCUMENT
   TEXT.

7. Prefer a complete sentence or a small number of consecutive
   sentences that directly support the clause.

8. If an exact contiguous excerpt cannot be found, OMIT that repair
   item rather than guessing.

9. Navigation, menus, footer links, product listings, and page chrome
   are not valid source evidence.

CLAUSES REQUIRING REPAIR:

{repair_payload}

DOCUMENT TEXT:

{text}
"""

        try:

            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config={
                    "temperature": 0.0,
                    "max_output_tokens": min(
                        self.OUTPUT_TOKENS,
                        1800,
                    ),
                    "response_mime_type": "application/json",
                },
            )

            raw = getattr(
                response,
                "text",
                "",
            ) or ""

            if not raw.strip():
                print(
                    "Grounding repair returned no text."
                )
                return []

            data = self._parse_json(
                raw
            )

            if not isinstance(
                data,
                dict,
            ):
                return []

            repaired_items = data.get(
                "clauses",
                [],
            )

            if not isinstance(
                repaired_items,
                list,
            ):
                return []

            by_index = {
                int(item["repair_index"]): item
                for item in repair_items
                if str(
                    item.get("repair_index", "")
                ).isdigit()
            }

            repaired: List[
                Dict[str, Any]
            ] = []

            for item in repaired_items:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                try:
                    repair_index = int(
                        item.get(
                            "repair_index",
                            0,
                        )
                    )
                except Exception:
                    continue

                original = by_index.get(
                    repair_index
                )

                if not original:
                    continue

                source_text = self._clean_text(
                    item.get(
                        "source_text",
                        "",
                    )
                )

                if not source_text:
                    continue

                # The repair is accepted only if the exact repaired
                # excerpt can independently pass the same grounding
                # validator used by the primary extraction.
                if not self._source_exists(
                    text,
                    source_text,
                ):
                    print(
                        "Rejected grounding repair: "
                        "source_text not found in source chunk."
                    )
                    continue

                # Apply the same deterministic word-boundary repair
                # after independent grounding validation.
                # If repair returns "" the sentence start is before
                # the chunk boundary; skip this repair item.
                repaired_source_text = (
                    self._repair_source_boundaries(
                        text,
                        source_text,
                    )
                )

                if repaired_source_text == "":
                    print(
                        "Rejected grounding repair: "
                        "source_text starts at chunk boundary "
                        "(sentence start not in this chunk)."
                    )
                    continue

                if repaired_source_text:
                    source_text = repaired_source_text

                category = self._normalize_category(
                    original.get(
                        "category",
                        "other",
                    )
                )

                repaired.append(
                    {
                        "clause_id": self._stable_clause_id(
                            title=original.get(
                                "title",
                                "",
                            ),
                            category=category,
                            source_text=source_text,
                        ),
                        "title": original.get(
                            "title",
                            "",
                        ),
                        "category": category,
                        "summary": original.get(
                            "summary",
                            "",
                        ),
                        "explanation": original.get(
                            "explanation",
                            "",
                        ),
                        "obligations": original.get(
                            "obligations",
                            [],
                        ),
                        "permissions": original.get(
                            "permissions",
                            [],
                        ),
                        "restrictions": original.get(
                            "restrictions",
                            [],
                        ),
                        "consequences": original.get(
                            "consequences",
                            [],
                        ),
                        "_gemini_risk_level": original.get(
                            "risk_level",
                            "medium",
                        ),
                        "risk_level": original.get(
                            "risk_level",
                            "medium",
                        ),
                        "risk_reason": original.get(
                            "risk_reason",
                            "",
                        ),
                        "source_text": source_text[:1200],
                    }
                )

            if repaired:
                print(
                    "Grounding repair accepted: "
                    f"{len(repaired)} clause(s)."
                )
            else:
                print(
                    "Grounding repair produced no "
                    "independently grounded clauses."
                )

            return repaired

        except Exception as exc:
            print(
                f"Grounding repair error: {exc}"
            )
            return []

    # ==========================================================
    # EXTRACTION QUALITY FILTER
    # ==========================================================
    #
    # This gate evaluates SOURCE TEXT only. Titles, categories, and
    # Gemini summaries are not allowed to make a non-legal sentence
    # look substantive.
    #
    # A valid clause should normally do at least one of these things:
    #   * impose an obligation/restriction
    #   * grant a permission/right
    #   * state a contractual consequence
    #   * define a material legal/privacy term
    #   * state a substantive policy about data/security/payments/etc.
    #
    # Pure page descriptions such as "Lists links related to..." are
    # rejected even when they contain words like payment or renewal.

    DESCRIPTIVE_NAVIGATION_PATTERNS = [
        r"\b(?:lists?|mentions?|provides?|contains?|shows?|highlights?)\s+(?:links?|navigation|menu|features?|options?|information)\b",
        r"\b(?:lists?|mentions?)\s+(?:payment|refund|renewal|subscription|account|card)\s+(?:mechanisms?|options?|features?|links?)\b",
        r"\b(?:navigation|menu|footer|header|page|website)\b.{0,100}\b(?:links?|features?|categories?)\b",
        r"\b(?:links?|features?|categories?)\b.{0,100}\b(?:navigation|menu|page|website)\b",
        r"\b(?:related to|available under|found under)\b.{0,100}\b(?:links?|navigation|menu|features?|categories?)\b",
    ]

    OPERATIVE_PATTERNS = [
        # Direct user/customer obligations or permissions.
        r"\b(?:you|user|customer|account holder|member)\s+(?:must|shall|may|may not|cannot|can|agree(?:s)?|acknowledge(?:s)?|consent(?:s)?|are required to|is required to|are responsible for|is responsible for|will be charged|grant(?:s)?|warrant(?:s)?)\b",
        r"\b(?:you|user|customer|account holder|member)\s+(?:will|would)\s+(?:be|have|receive|pay|lose|forfeit)\b",
        # Provider/company/bank obligations, permissions, or actions.
        r"\b(?:we|the company|the bank|the service provider|the provider|the website|the service)\s+(?:may|can|will|shall|must|collect|use|share|disclose|retain|store|process|require|charge|refund|terminate|suspend|restrict|protect|secure|provide|grant(?:s)?)\b",
        # Standard contractual constructions.
        r"\b(?:shall|must|may not|cannot|is prohibited|are prohibited|is required|are required|is entitled|are entitled|is responsible|are responsible|is liable|are liable|expressly restricted|not allowed to)\b",
        r"\b(?:will be charged|is charged|are charged|is subject to|are subject to|subject to)\b",
        r"\b(?:agree to|agrees to|consent to|acknowledge that|understand that|responsible for|liable for|indemnify|hold harmless|grant a|grants a|grant.*license)\b",
        # Material legal/privacy operations even when the actor is omitted.
        r"\b(?:collect(?:s|ed|ing)?|use(?:s|d|ing)?|share(?:s|d|ing)?|disclose(?:s|d|ing)?|retain(?:s|ed|ing)?|store(?:s|d|ing)?|process(?:es|ed|ing)?|transfer(?:s|red|ring)?|sell(?:s|ing)?|charge(?:s|d)?|refund(?:s|ed)?|terminate(?:s|d)?|suspend(?:s|ed)?|restrict(?:s|ed)?|protect(?:s|ed|ing)?|secure(?:s|d|ing)?|grant(?:s|ed|ing)?)\b",
        # Strong contractual/legal phrases.
        r"\b(?:governed by|governing law|binding arbitration|mandatory arbitration|limitation of liability|not liable|maximum liability|without warranty|non[- ]refundable|auto[- ]renewal|automatically renew|intellectual property|proprietary rights|class[- ]action waiver|worldwide irrevocable|royalty[- ]free|user content license)\b",
    ]

    DEFINITION_PATTERNS = [
        r"\b(?:means|mean|refers to|defined as|is defined as|includes|include)\b",
        r"\bfor purposes of (?:this|the) (?:policy|agreement|terms|service)\b",
    ]

    MATERIAL_POLICY_PATTERNS = [
        r"\b(?:we|the company|the bank|the service provider)\s+(?:respect|protect|keep|maintain|ensure|safeguard|secure)\b.{0,180}\b(?:privacy|information|data|security|confidential)\b",
        r"\b(?:privacy|security|data protection|confidentiality)\b.{0,180}\b(?:policy|commitment|practice|measures?|safeguards?)\b",
        r"\b(?:optional service|at .* discretion|not a legal right|subject to .* discretion)\b",
    ]

    def _filter_extracted_clauses(
        self,
        clauses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        filtered: List[Dict[str, Any]] = []

        for clause in clauses:

            if not isinstance(clause, dict):
                continue

            title = self._clean_text(
                clause.get("title", "")
            )

            source_text = self._clean_text(
                clause.get("source_text", "")
            )

            if not title or not source_text:
                continue

            if not self._is_substantive_clause(source_text):
                print(
                    "Rejected non-substantive Agent 2 clause: "
                    f"{title}"
                )
                continue

            filtered.append(clause)

        return filtered

    def _category_source_is_valid(
        self,
        source_text: str,
        category: str = "",
    ) -> bool:
        """
        Apply category-specific semantic guards to source_text.

        Category keywords alone are not enough. In particular:
        - "Online Auto Renewal" in a navigation menu is not an
          auto-renewal contractual provision.
        - ASBA/payment navigation or an incidental use of the word
          "refund" is not a refund provision.
        """
        normalized = self._clean_text(source_text).lower()
        category = self._clean_text(category).lower()

        if category == "auto_renewal":
            auto_renewal_evidence = [
                r"\bautomatically\s+(?:renew|renews|renewed|renewing)\b",
                r"\bauto[- ]renew(?:al)?\b.{0,180}\b(?:subscription|plan|service|term|membership)\b",
                r"\b(?:subscription|plan|service|membership)\b.{0,180}\b(?:auto[- ]renew|automatically\s+renew|renew(?:s|ed)?)\b",
                r"\b(?:renew|renews|renewed|renewal)\b.{0,180}\b(?:unless|until|cancel|cancellation|notice|fee|charge|term)\b",
            ]

            return any(
                re.search(pattern, normalized, re.I)
                for pattern in auto_renewal_evidence
            )

        if category == "refund":
            refund_evidence = [
                r"\b(?:eligible|eligibility)\b.{0,160}\brefund(?:ed|s)?\b",
                r"\brefund(?:ed|s|ing)?\b.{0,220}\b(?:amount|request|process|issue|receive|customer|customer'?s|payment|purchase|order|transaction)\b",
                r"\b(?:amount|payment|money|funds)\b.{0,180}\b(?:refund(?:ed|s|ing)?|returned|reimbursed)\b",
                r"\bnon[- ]refundable\b",
                r"\brefund policy\b",
                r"\brefund(?:ed|s|ing)?\b.{0,180}\b(?:cancel|cancellation|return|reimburse)\b",
            ]

            return any(
                re.search(pattern, normalized, re.I)
                for pattern in refund_evidence
            )

        return True

    def _source_excerpt_quality_ok(
        self,
        source_text: str,
    ) -> bool:
        """
        Reject grounded excerpts that are technically copied from the
        source chunk but are still contaminated by page chrome.

        Grounding and source quality are separate guarantees:
        - _source_exists() answers: "Does this text occur in the chunk?"
        - this method answers: "Does this look like a focused policy
          provision rather than a scraped website block?"

        This remains deterministic and conservative. It does not use
        fuzzy similarity or an LLM judgment.
        """
        normalized = self._clean_text(
            source_text
        ).lower()

        if not normalized:
            return False

        # Markdown/HTML link artifacts are a particularly strong signal
        # that Gemini copied surrounding navigation instead of the
        # actual provision.
        url_hits = len(
            re.findall(
                r"https?://",
                normalized,
                re.I,
            )
        )

        markdown_link_hits = len(
            re.findall(
                r"\]\s*\(",
                normalized,
            )
        )

        javascript_link_hits = len(
            re.findall(
                r"javascript\s*:",
                normalized,
                re.I,
            )
        )

        # A focused legal clause may contain a single reference link,
        # but multiple links strongly indicate page chrome.
        if url_hits >= 2:
            return False

        if markdown_link_hits >= 2:
            return False

        if javascript_link_hits >= 1:
            return False

        # Scraped page chrome commonly appears as a sequence of short
        # UI labels around the substantive text.
        chrome_terms = [
            "search",
            "english",
            "tamil",
            "hindi",
            "home",
            "retail",
            "loan products",
            "card management",
            "quick links",
            "useful links",
            "related links",
            "site map",
            "sitemap",
        ]

        chrome_hits = sum(
            1
            for term in chrome_terms
            if re.search(
                rf"\b{re.escape(term)}\b",
                normalized,
                re.I,
            )
        )

        if chrome_hits >= 4:
            return False

        # Repeated bracketed link labels are another strong signal of
        # scraped navigation. Do not reject ordinary legal brackets,
        # only repeated link-like forms.
        bracket_link_hits = len(
            re.findall(
                r"\[[^\]]{1,120}\]\s*\(",
                normalized,
            )
        )

        if bracket_link_hits >= 2:
            return False

        # If the excerpt is very large, require it to remain focused.
        # A genuine clause can be long, but a 1,000+ character excerpt
        # containing navigation markers is usually an extraction block.
        if len(normalized) > 900:
            navigation_markers = (
                url_hits
                + markdown_link_hits
                + javascript_link_hits
                + bracket_link_hits
            )

            if navigation_markers >= 1:
                return False

        return True

    def _is_navigation_heavy_source(
        self,
        normalized: str,
    ) -> bool:
        """
        Detect source excerpts that are primarily menu/footer/link
        material. Legal keywords inside such a block must not turn it
        into a policy clause.
        """
        navigation_hits = sum(
            1 for term in self.NAVIGATION_TERMS
            if term in normalized
        )

        navigation_pattern_hits = sum(
            1 for pattern in self.NAVIGATION_PATTERNS
            if re.search(pattern, normalized, re.I)
        )

        strong_navigation_fragments = [
            r"\b(?:lists?|mentions?|provides?|contains?|shows?|highlights?)\s+(?:links?|navigation|menu|features?|options?)\b",
            r"\b(?:navigation|menu|footer|header|website)\b.{0,120}\b(?:links?|features?|categories?|options?)\b",
            r"\b(?:links?|features?|categories?|options?)\b.{0,120}\b(?:navigation|menu|footer|header|website)\b",
            r"\b(?:click|select|visit|go to|learn more|view all|explore)\b.{0,100}\b(?:link|page|section|menu)\b",
            r"\b(?:set or reset|set your own|open bank accounts|card limits|green pin)\b",
        ]

        strong_fragment_hits = sum(
            1
            for pattern in strong_navigation_fragments
            if re.search(pattern, normalized, re.I)
        )

        # A navigation description is sufficient by itself.
        if strong_fragment_hits >= 1:
            return True

        # Multiple menu/link terms are strong evidence of page chrome.
        if navigation_hits >= 2:
            return True

        if navigation_pattern_hits >= 1 and navigation_hits >= 1:
            return True

        return False

    def _is_substantive_clause(
        self,
        source_text: str,
        category: str = "",
    ) -> bool:

        normalized = self._clean_text(source_text).lower()

        if len(normalized) < 40:
            return False

        # Source-excerpt quality is stricter than grounding.
        #
        # _source_exists() only proves that Gemini copied text that
        # exists in the supplied chunk. A copied block can still be
        # mostly website chrome, markdown links, search controls, or
        # product navigation. Reject those blocks before category
        # reconciliation and risk scoring.
        if not self._source_excerpt_quality_ok(
            source_text
        ):
            return False

        # First reject source excerpts that are clearly describing the
        # website rather than stating a policy provision.
        if self._is_navigation_heavy_source(normalized):
            # A source can mention a website in passing while still
            # containing a genuine legal provision. Allow that only
            # when strong operative/definitional/policy evidence exists.
            operative_hits = sum(
                1
                for pattern in self.OPERATIVE_PATTERNS
                if re.search(pattern, normalized, re.I)
            )
            definition_hits = sum(
                1
                for pattern in self.DEFINITION_PATTERNS
                if re.search(pattern, normalized, re.I)
            )
            policy_hits = sum(
                1
                for pattern in self.MATERIAL_POLICY_PATTERNS
                if re.search(pattern, normalized, re.I)
            )

            if operative_hits == 0 and definition_hits == 0 and policy_hits == 0:
                return False

        descriptive_hits = sum(
            1
            for pattern in self.DESCRIPTIVE_NAVIGATION_PATTERNS
            if re.search(pattern, normalized, re.I)
        )

        operative_hits = sum(
            1
            for pattern in self.OPERATIVE_PATTERNS
            if re.search(pattern, normalized, re.I)
        )

        definition_hits = sum(
            1
            for pattern in self.DEFINITION_PATTERNS
            if re.search(pattern, normalized, re.I)
        )

        policy_hits = sum(
            1
            for pattern in self.MATERIAL_POLICY_PATTERNS
            if re.search(pattern, normalized, re.I)
        )

        # Explicit page-description language is not a legal clause.
        if descriptive_hits >= 1 and operative_hits == 0 and policy_hits == 0:
            return False

        # A descriptive/navigation sentence with only one incidental
        # legal construction is still not substantive.
        if (
            descriptive_hits >= 1
            and operative_hits < 2
            and definition_hits == 0
            and policy_hits == 0
        ):
            return False

        # A source excerpt must contain an operative, definitional, or
        # material-policy construction. Category keywords by themselves
        # are never sufficient.
        if (
            operative_hits == 0
            and definition_hits == 0
            and policy_hits == 0
        ):
            return False

        # Finally apply category-specific guards using source_text only.
        # This prevents navigation items such as "Online Auto Renewal"
        # or incidental "refund" mentions in ASBA text from becoming
        # findings.
        if not self._category_source_is_valid(
            source_text,
            category,
        ):
            return False

        return True

    def _filter_extracted_clauses(
        self,
        clauses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        filtered: List[Dict[str, Any]] = []

        for clause in clauses:

            if not isinstance(clause, dict):
                continue

            title = self._clean_text(
                clause.get("title", "")
            )

            source_text = self._clean_text(
                clause.get("source_text", "")
            )

            category = self._clean_text(
                clause.get("category", "")
            )

            if not title or not source_text:
                continue

            if not self._is_substantive_clause(
                source_text,
                category,
            ):
                print(
                    "Rejected non-substantive Agent 2 clause: "
                    f"{title}"
                )
                continue

            filtered.append(clause)

        return filtered

    # ==========================================================
    # DETERMINISTIC FALLBACK
    # ==========================================================

    def _fallback_extract(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:

        if not text or len(text.strip()) < self.MIN_TEXT_LENGTH:
            return []

        clean_text = re.sub(
            r"\s+",
            " ",
            text or "",
        ).strip()

        clauses: List[
            Dict[str, Any]
        ] = []

        seen_keys = set()

        # Step 1: Section/paragraph-based extraction to keep distinct legal topics separate.
        raw_sections = re.split(
            r"(?:\n\s*\n|\n(?=\s*(?:[0-9]+[\.\)]|[A-Z\s]{3,}:|#+\s+|Section\s+[0-9]+)))",
            text,
        )

        for sec in raw_sections:
            sec_clean = re.sub(r"\s+", " ", sec).strip()
            if len(sec_clean) < 40:
                continue

            for (
                title,
                category,
                patterns,
            ) in self.LEGAL_PATTERNS:
                matched = any(re.search(p, sec_clean, re.I) for p in patterns)
                if not matched:
                    continue

                excerpt = self._repair_source_boundaries(
                    text,
                    sec_clean,
                )

                if len(excerpt) < 40:
                    continue

                clause_key = (category, excerpt[:100].lower())
                if clause_key in seen_keys:
                    continue
                seen_keys.add(clause_key)

                clause_id = self._stable_clause_id(
                    title=title,
                    category=category,
                    source_text=excerpt[:1200],
                )

                clauses.append(
                    {
                        "clause_id": clause_id,
                        "title": title,
                        "category": category,
                        "summary": self._fallback_summary(title, excerpt),
                        "explanation": (
                            f"This provision concerns {title.lower()} and may affect "
                            f"the user's rights, obligations, privacy, account, payments, "
                            f"or other use of the service."
                        ),
                        "obligations": [],
                        "permissions": [],
                        "restrictions": [],
                        "consequences": [],
                        "risk_level": "low",
                        "risk_reason": f"The document contains a provision concerning {title.lower()}.",
                        "source_text": excerpt[:1200],
                    }
                )

        # Step 2: Global pattern pass for provisions that might span or sit outside segmented paragraphs.
        for (
            title,
            category,
            patterns,
        ) in self.LEGAL_PATTERNS:

            match = None
            for pattern in patterns:
                match = re.search(
                    pattern,
                    clean_text,
                    re.I,
                )
                if match:
                    break

            if not match:
                continue

            # Bounded sentence search around the match
            start_search = max(0, match.start() - 250)
            prefix = clean_text[start_search:match.start()]
            prefix_breaks = [m.end() for m in re.finditer(r"[.!?]\s+", prefix)]
            if prefix_breaks:
                start = start_search + prefix_breaks[-1]
            else:
                start = start_search

            end_search = min(len(clean_text), match.end() + 350)
            suffix = clean_text[match.end():end_search]
            suffix_breaks = [m.end() for m in re.finditer(r"[.!?](?:\s+|$)", suffix)]
            if suffix_breaks:
                end = match.end() + suffix_breaks[0]
            else:
                end = end_search

            excerpt = clean_text[start:end].strip()
            excerpt = self._repair_source_boundaries(
                clean_text,
                excerpt,
            )

            if len(excerpt) < 40:
                continue

            clause_key = (category, excerpt[:100].lower())
            if clause_key in seen_keys:
                continue
            seen_keys.add(clause_key)

            clause_id = self._stable_clause_id(
                title=title,
                category=category,
                source_text=excerpt[:1200],
            )

            clauses.append(
                {
                    "clause_id": clause_id,
                    "title": title,
                    "category": category,
                    "summary": self._fallback_summary(title, excerpt),
                    "explanation": (
                        f"This provision concerns {title.lower()} and may affect "
                        f"the user's rights, obligations, privacy, account, payments, "
                        f"or other use of the service."
                    ),
                    "obligations": [],
                    "permissions": [],
                    "restrictions": [],
                    "consequences": [],
                    "risk_level": "low",
                    "risk_reason": f"The document contains a provision concerning {title.lower()}.",
                    "source_text": excerpt[:1200],
                }
            )

        return self._filter_extracted_clauses(
            clauses[:20]
        )

    # ==========================================================
    # DETERMINISTIC SOURCE-BASED RISK EVIDENCE
    # ==========================================================

    def _build_risk_evidence(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        evidence: List[
            Dict[str, Any]
        ] = []

        seen = set()

        # Every selected chunk is processed in its already
        # deterministic order.
        for item in chunks:

            text = str(
                item.get(
                    "text",
                    "",
                )
                or ""
            ).strip()

            if not text:
                continue

            normalized_text = re.sub(
                r"\s+",
                " ",
                text,
            ).strip()

            for (
                title,
                category,
                patterns,
            ) in self.LEGAL_PATTERNS:

                match = None

                for pattern in patterns:

                    match = re.search(
                        pattern,
                        normalized_text,
                        re.I,
                    )

                    if match:
                        break

                if not match:
                    continue

                # Bounded sentence search around the match
                start_search = max(0, match.start() - 200)
                prefix = normalized_text[start_search:match.start()]
                prefix_breaks = [m.end() for m in re.finditer(r"[.!?]\s+", prefix)]
                if prefix_breaks:
                    start = start_search + prefix_breaks[-1]
                else:
                    start = start_search

                end_search = min(len(normalized_text), match.end() + 350)
                suffix = normalized_text[match.end():end_search]
                suffix_breaks = [m.end() for m in re.finditer(r"[.!?](?:\s+|$)", suffix)]
                if suffix_breaks:
                    end = match.end() + suffix_breaks[0]
                else:
                    end = end_search

                excerpt = normalized_text[
                    start:end
                ].strip()

                excerpt = self._repair_source_boundaries(
                    normalized_text,
                    excerpt,
                )

                if len(excerpt) < 40:
                    continue

                key = (
                    self._canonical_url(
                        item.get(
                            "document_url",
                            "",
                        )
                    ),
                    int(
                        item.get(
                            "chunk_index",
                            0,
                        )
                        or 0
                    ),
                    category,
                    re.sub(
                        r"\W+",
                        " ",
                        excerpt.lower(),
                    ).strip(),
                )

                if key in seen:
                    continue

                seen.add(key)

                evidence.append(
                    {
                        "clause_id": (
                            "risk-"
                            + hashlib.sha256(
                                (
                                    "|".join(
                                        map(
                                            str,
                                            key,
                                        )
                                    )
                                ).encode(
                                    "utf-8"
                                )
                            ).hexdigest()[:16]
                        ),

                        "title": title,

                        "category": category,

                        "summary": (
                            f"Deterministic source evidence "
                            f"for {title.lower()}."
                        ),

                        "explanation": (
                            "Risk calculated from the "
                            "deterministically selected "
                            "source text."
                        ),

                        "obligations": [],

                        "permissions": [],

                        "restrictions": [],

                        "consequences": [],

                        "risk_level": "low",

                        "risk_reason": (
                            f"Source text contains evidence "
                            f"related to {title.lower()}."
                        ),

                        "source_text": excerpt[:1200],
                    }
                )

        evidence.sort(
            key=self._clause_sort_key
        )

        return evidence

    # ==========================================================
    # RISK
    # ==========================================================

    def _fallback_risk(
        self,
        category: str,
    ) -> str:

        high_categories = {
            "data_collection",
            "data_sharing",
            "tracking",
            "privacy",
            "payments",
            "auto_renewal",
            "arbitration",
            "dispute_resolution",
            "limitation_of_liability",
            "indemnification",
        }

        if category in high_categories:
            return "high"

        medium_categories = {
            "termination",
            "refund",
            "cancellation",
            "license",
            "intellectual_property",
            "governing_law",
        }

        if category in medium_categories:
            return "medium"

        return "low"

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    def _normalize_and_dedupe(
        self,
        clauses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        unique: Dict[
            str,
            Dict[str, Any],
        ] = {}

        for clause in clauses:

            if not isinstance(
                clause,
                dict,
            ):
                continue

            title = self._clean_text(
                clause.get(
                    "title",
                    "",
                )
            )

            source_text = self._clean_text(
                clause.get(
                    "source_text",
                    "",
                )
            )

            if not title or not source_text:
                continue

            gemini_category = self._normalize_category(
                clause.get(
                    "category",
                    "other",
                )
            )

            # Gemini's category is a candidate, not the final authority.
            # Validate it against the actual source excerpt before the
            # clause enters scoring or Agent 3.
            category = self._reconcile_category(
                gemini_category,
                source_text,
            )

            if not self._is_substantive_clause(
                source_text,
                category,
            ):
                continue

            CATEGORY_DEFAULT_TITLES = {
                "age_requirement": "Age Requirement",
                "intellectual_property": "Intellectual Property",
                "prohibited_use": "Prohibited Use and Restrictions",
                "license": "User Content and License",
                "liability": "Limitation of Liability",
                "limitation_of_liability": "Limitation of Liability",
                "indemnification": "Indemnification",
                "governing_law": "Governing Law and Jurisdiction",
                "arbitration": "Arbitration",
                "dispute_resolution": "Dispute Resolution",
                "termination": "Account Termination",
                "privacy": "Privacy Policy",
                "data_collection": "Data Collection",
                "data_sharing": "Data Sharing",
                "tracking": "Cookies and Tracking",
                "payments": "Payment Obligations",
                "refund": "Cancellation and Refund Policy",
                "auto_renewal": "Subscription and Auto-Renewal",
                "warranty": "Warranty Disclaimer",
                "security": "Data Security",
                "other": "Policy Changes",
            }

            title_lower = title.lower()
            if "policy change" in title_lower and category != "other":
                title = CATEGORY_DEFAULT_TITLES.get(category, title)
            elif "license" in title_lower and category not in {"license", "other"}:
                title = CATEGORY_DEFAULT_TITLES.get(category, title)
            elif "data collection" in title_lower and category == "other":
                title = "Policy Changes"
            elif "governing law" in title_lower and category != "governing_law":
                title = CATEGORY_DEFAULT_TITLES.get(category, title)
            elif category != gemini_category and category in CATEGORY_DEFAULT_TITLES and not any(w in title_lower for w in category.split("_")):
                title = CATEGORY_DEFAULT_TITLES.get(category, title)

            normalized = dict(
                clause
            )

            normalized["title"] = title
            normalized["category"] = category
            normalized["source_text"] = source_text[:1200]

            normalized["summary"] = self._clean_text(
                normalized.get(
                    "summary",
                    "",
                )
            )

            normalized["explanation"] = self._clean_text(
                normalized.get(
                    "explanation",
                    "",
                )
            )

            normalized["risk_reason"] = self._clean_text(
                normalized.get(
                    "risk_reason",
                    "",
                )
            )

            normalized["obligations"] = self._list_value(
                normalized.get(
                    "obligations",
                    [],
                )
            )

            normalized["permissions"] = self._list_value(
                normalized.get(
                    "permissions",
                    [],
                )
            )

            normalized["restrictions"] = self._list_value(
                normalized.get(
                    "restrictions",
                    [],
                )
            )

            normalized["consequences"] = self._list_value(
                normalized.get(
                    "consequences",
                    [],
                )
            )

            # Do not allow Gemini risk to become the final
            # authoritative risk value.
            normalized["risk_level"] = "low"

            # Stable ID is rebuilt after source/category normalization.
            normalized["clause_id"] = self._stable_clause_id(
                title=title,
                category=category,
                source_text=normalized["source_text"],
            )

            # --------------------------------------------------
            # Stage 1: exact grounded-source deduplication
            #
            # The same source excerpt can be returned by multiple
            # overlapping chunks. Chunk index, title, and category are
            # intentionally excluded from this identity.
            # --------------------------------------------------

            source_dedupe_key = self._source_dedupe_key(
                document_url=normalized.get(
                    "document_url",
                    "",
                ),
                document_type=normalized.get(
                    "document_type",
                    "legal",
                ),
                source_text=normalized["source_text"],
            )

            if source_dedupe_key not in unique:
                unique[source_dedupe_key] = normalized

        exact_unique = list(
            unique.values()
        )

        # ------------------------------------------------------
        # Stage 2: deterministic source-containment deduplication
        #
        # Adjacent LLM chunks overlap by design. Gemini can therefore
        # return the same legal provision twice with different excerpt
        # boundaries, for example:
        #
        #   "merchant partners ... through our Services..."
        #
        # and:
        #
        #   "partners ... through our Services..."
        #
        # Exact hashing cannot catch that because the source strings
        # differ. We therefore apply a deliberately narrow rule:
        #
        #   same canonical document URL
        #   + same document type
        #   + one normalized source excerpt is a substantial contiguous
        #     substring of the other
        #
        # No fuzzy similarity, embeddings, semantic matching, title
        # matching, or category matching are used.
        #
        # The longer grounded excerpt wins because it preserves more
        # source evidence. A minimum length prevents short common
        # phrases from collapsing unrelated legal provisions.
        # ------------------------------------------------------

        deduped: List[
            Dict[str, Any]
        ] = []

        # Deterministic ordering makes the result stable across runs.
        exact_unique.sort(
            key=self._clause_sort_key
        )

        for candidate in exact_unique:

            duplicate_index: Optional[int] = None

            for index, existing in enumerate(
                deduped
            ):

                if not self._same_document_scope(
                    candidate,
                    existing,
                ):
                    continue

                if not self._source_overlap_duplicate(
                    candidate.get(
                        "source_text",
                        "",
                    ),
                    existing.get(
                        "source_text",
                        "",
                    ),
                ):
                    continue

                duplicate_index = index
                break

            if duplicate_index is None:
                deduped.append(
                    candidate
                )
                continue

            existing = deduped[
                duplicate_index
            ]

            candidate_length = len(
                self._normalize_source_for_dedupe(
                    candidate.get(
                        "source_text",
                        "",
                    )
                )
            )

            existing_length = len(
                self._normalize_source_for_dedupe(
                    existing.get(
                        "source_text",
                        "",
                    )
                )
            )

            # Keep the more informative grounded excerpt. If lengths
            # are equal, retain the already-selected deterministic
            # occurrence so ordering remains stable.
            if candidate_length > existing_length:
                deduped[
                    duplicate_index
                ] = candidate

                print(
                    "Agent 2 overlap dedupe: "
                    f"replaced '{existing.get('title', '')}' "
                    f"with longer grounded source for "
                    f"'{candidate.get('title', '')}'"
                )
            else:
                print(
                    "Agent 2 overlap dedupe: "
                    f"removed duplicate '{candidate.get('title', '')}' "
                    f"overlapping '{existing.get('title', '')}'"
                )

        result = deduped

        result.sort(
            key=self._clause_sort_key
        )

        return result

    def _same_document_scope(
        self,
        first: Dict[str, Any],
        second: Dict[str, Any],
    ) -> bool:
        """
        Return True only when two clauses belong to the same policy
        document scope.

        URL and document type are both required so identical legal
        wording on separate policy documents is never collapsed.
        """
        first_url = self._canonical_url(
            first.get(
                "document_url",
                "",
            )
        )

        second_url = self._canonical_url(
            second.get(
                "document_url",
                "",
            )
        )

        if first_url != second_url:
            return False

        first_type = str(
            first.get(
                "document_type",
                "legal",
            )
            or "legal"
        ).strip().lower()

        second_type = str(
            second.get(
                "document_type",
                "legal",
            )
            or "legal"
        ).strip().lower()

        return first_type == second_type

    def _source_overlap_duplicate(
        self,
        first_source: Any,
        second_source: Any,
    ) -> bool:
        """
        Detect deterministic duplicate source excerpts.

        A duplicate is accepted only when the shorter normalized
        excerpt is a contiguous substring of the longer normalized
        excerpt and the shorter excerpt is sufficiently substantial.

        This deliberately does NOT perform:
        - fuzzy matching;
        - semantic similarity;
        - token-set similarity;
        - embeddings;
        - title/category matching;
        - LLM-based deduplication.

        Therefore two merely similar legal provisions remain separate.
        """
        first = self._normalize_source_for_dedupe(
            first_source
        )

        second = self._normalize_source_for_dedupe(
            second_source
        )

        if not first or not second:
            return False

        if first == second:
            return True

        shorter, longer = (
            (first, second)
            if len(first) <= len(second)
            else (second, first)
        )

        # Avoid collapsing clauses because they share a short legal
        # phrase such as "we may", "third parties", or "you agree".
        MIN_OVERLAP_SOURCE_CHARS = 80

        if len(shorter) < MIN_OVERLAP_SOURCE_CHARS:
            return False

        return shorter in longer

    def _deterministic_category(
        self,
        source_text: str,
    ) -> str:
        """
        Get a deterministic category from the actual source excerpt.
        """
        try:
            return self._normalize_category(
                suggest_category(
                    source_text
                )
            )
        except Exception as exc:
            print(
                f"Agent 2 category classifier error: {exc}"
            )
            return "other"

    def _is_investment_payment_context(
        self,
        source_text: str,
    ) -> bool:
        """
        Detect IPO/ASBA/investment payment language.

        Financial documents can use "subscription" or "refund" in an
        investment-transaction sense. Those are not automatically
        service-subscription or refund-policy clauses.
        """
        normalized = self._clean_text(
            source_text
        ).lower()

        investment_terms = [
            r"\bipo\b",
            r"\basba\b",
            r"application supported by blocked amount",
            r"\bpublic issue\b",
            r"\bpublic issues\b",
            r"\bshare issue\b",
            r"\bshare issues\b",
            r"\bsecurities issue\b",
            r"\binvestor(?:s)?\b.{0,100}\bsubscription(?:s)?\b",
            r"\bsubscription(?:s)?\b.{0,100}\b(?:shares|securities|ipo|public issue)\b",
        ]

        return any(
            re.search(
                pattern,
                normalized,
                re.I,
            )
            for pattern in investment_terms
        )

    def _reconcile_category(
        self,
        gemini_category: str,
        source_text: str,
    ) -> str:
        """
        Reconcile Gemini's proposed category with deterministic evidence
        from the actual source excerpt.

        Gemini remains useful for nuanced legal categories, but known
        high-impact false positives are corrected from source evidence.
        No fuzzy similarity is used.
        """
        gemini_category = self._normalize_category(
            gemini_category
        )

        deterministic_category = (
            self._deterministic_category(
                source_text
            )
        )

        investment_context = (
            self._is_investment_payment_context(
                source_text
            )
        )

        normalized = self._clean_text(
            source_text
        ).lower()

        # ----------------------------------------------------------
        # Strong investment/payment context guard.
        # ----------------------------------------------------------

        if investment_context:
            if gemini_category in {
                "refund",
                "subscription",
                "auto_renewal",
            }:
                if deterministic_category == "payments":
                    print(
                        "Agent 2 category correction: "
                        f"{gemini_category} -> payments "
                        "(investment/IPO/ASBA source evidence)"
                    )
                    return "payments"

                if gemini_category in {
                    "subscription",
                    "auto_renewal",
                }:
                    print(
                        "Agent 2 category correction: "
                        f"{gemini_category} -> other "
                        "(investment subscription is not a service subscription)"
                    )
                    return "other"

                # For refund, distinguish an actual refund operation
                # from incidental wording in an ASBA explanation.
                actual_refund_patterns = [
                    r"\brefund(?:s|ed|ing)?\b.{0,180}\b(?:request|process|issue|issued|receive|received|amount|payment|purchase|order|transaction)\b",
                    r"\b(?:request|process|issue|issued|receive|received|amount|payment|purchase|order|transaction)\b.{0,180}\brefund(?:s|ed|ing)?\b",
                    r"\bnon[- ]refundable\b",
                    r"\breimburse(?:ment|ments|d)?\b",
                ]

                actual_refund = any(
                    re.search(
                        pattern,
                        normalized,
                        re.I,
                    )
                    for pattern in actual_refund_patterns
                )

                if not actual_refund:
                    print(
                        "Agent 2 category correction: "
                        "refund -> payments "
                        "(incidental refund wording in investment-payment source)"
                    )
                    return "payments"

        # ----------------------------------------------------------
        # Explicit deterministic contradiction rules.
        # ----------------------------------------------------------

        if gemini_category == "refund":
            if deterministic_category == "payments":
                print(
                    "Agent 2 category correction: "
                    "refund -> payments "
                    "(source is payment/billing evidence)"
                )
                return "payments"

            if deterministic_category == "other":
                explicit_refund = any(
                    re.search(
                        pattern,
                        normalized,
                        re.I,
                    )
                    for pattern in [
                        r"\brefund(?:s|ed|ing)?\b",
                        r"\breimburse(?:ment|ments|d)?\b",
                        r"\bnon[- ]refundable\b",
                        r"\bmoney back\b",
                    ]
                )

                if not explicit_refund:
                    print(
                        "Agent 2 category correction: "
                        "refund -> other "
                        "(no explicit refund evidence)"
                    )
                    return "other"

        if gemini_category == "subscription":
            if deterministic_category == "payments":
                print(
                    "Agent 2 category correction: "
                    "subscription -> payments "
                    "(payment/investment source evidence)"
                )
                return "payments"

        if gemini_category == "auto_renewal":
            if deterministic_category in {
                "payments",
                "other",
            }:
                actual_auto_renewal = any(
                    re.search(
                        pattern,
                        normalized,
                        re.I,
                    )
                    for pattern in [
                        r"\bautomatically\s+(?:renew|renews|renewed|renewing)\b",
                        r"\bauto[- ]renew(?:al)?\b",
                        r"\b(?:subscription|plan|service|membership)\b.{0,180}\brenew(?:s|ed|al)?\b",
                    ]
                )

                if not actual_auto_renewal:
                    replacement = (
                        deterministic_category
                        if deterministic_category != "other"
                        else "other"
                    )

                    print(
                        "Agent 2 category correction: "
                        f"auto_renewal -> {replacement} "
                        "(no automatic-renewal evidence)"
                    )

                    return replacement

        # ----------------------------------------------------------
        # Policy-amendment contradiction guard.
        #
        # A clause such as "We may amend this Privacy Policy ... to
        # reflect changes in our data collection practices" is about
        # changing the policy itself. The words "data collection" are
        # contextual reasons for the amendment, not evidence that the
        # clause governs how data is collected.
        #
        # Keep this guard narrow. A genuine collection clause such as
        # "We collect personal information..." must remain
        # data_collection.
        # ----------------------------------------------------------

        if gemini_category == "data_collection":
            policy_change_category = self._deterministic_category(
                source_text
            )

            if policy_change_category == "other":
                policy_change_patterns = [
                    r"\b(?:may|can|will|reserve\s+the\s+right\s+to)\s+"
                    r"(?:change|modify|update|amend|revise|replace)\b.{0,220}"
                    r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
                    r"terms\s+and\s+conditions|terms\s+of\s+service|agreement|notice)\b",
                    r"\b(?:change|changes|modify|modification|update|updates|"
                    r"amend|amendment|amendments|revise|revision|revisions)\b.{0,160}"
                    r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
                    r"agreement|notice)\b",
                    r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
                    r"agreement|notice)\b.{0,160}"
                    r"\b(?:from\s+time\s+to\s+time|periodically|occasionally)\b",
                    r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
                    r"agreement|notice)\b.{0,180}"
                    r"\b(?:reflect|reflecting)\s+(?:changes|updates|revisions)\b",
                ]

                if any(
                    re.search(
                        pattern,
                        normalized,
                        re.I,
                    )
                    for pattern in policy_change_patterns
                ):
                    print(
                        "Agent 2 category correction: "
                        "data_collection -> other "
                        "(policy-amendment clause mentions data practices "
                        "as amendment context)"
                    )
                    return "other"

        if gemini_category == "governing_law":
            genuine_governing_law_patterns = [
                r"\bgoverned\s+by\b",
                r"\bgoverned\s+in\s+accordance\s+with\b",
                r"\bgoverning\s+law\b",
                r"\blaws\s+of\b",
                r"\blaw\s+of\b",
                r"\bjurisdiction\b",
                r"\bexclusive\s+jurisdiction\b",
                r"\bcourts?\s+(?:of|in|at)\b",
                r"\bvenue\b",
                r"\bdispute\s+resolution\b",
                r"\bproper\s+law\b",
            ]

            is_genuine_governing_law = any(
                re.search(
                    pattern,
                    normalized,
                    re.I,
                )
                for pattern in genuine_governing_law_patterns
            )

            if not is_genuine_governing_law:
                replacement = (
                    deterministic_category
                    if deterministic_category != "other"
                    else "privacy" if any(
                        p in normalized
                        for p in [
                            "personal information",
                            "personal data",
                            "privacy",
                            "data controller",
                            "data protection",
                        ]
                    )
                    else "other"
                )

                print(
                    "Agent 2 category correction: "
                    f"governing_law -> {replacement} "
                    "(incidental applicable-law compliance phrasing without governing law/jurisdiction terms)"
                )
                return replacement

        # ----------------------------------------------------------
        # If Gemini says "other", use deterministic evidence when
        # the source clearly supports a known category.
        # ----------------------------------------------------------

        if gemini_category == "other":
            if deterministic_category != "other":
                print(
                    "Agent 2 category promotion: "
                    f"other -> {deterministic_category}"
                )
                return deterministic_category

        return gemini_category

    def _normalize_category(
        self,
        value: Any,
    ) -> str:

        category = str(
            value
            or "other"
        ).strip().lower()

        category = re.sub(
            r"[\s-]+",
            "_",
            category,
        )

        if category not in self.ALLOWED_CATEGORIES:
            return "other"

        return category

    def _normalize_risk(
        self,
        value: Any,
    ) -> str:

        risk = str(
            value
            or "medium"
        ).strip().lower()

        if risk not in self.ALLOWED_RISK_LEVELS:
            return "medium"

        return risk

    def _source_dedupe_key(
        self,
        document_url: Any,
        document_type: Any,
        source_text: str,
    ) -> tuple:
        """
        Build a deterministic identity for the same grounded source
        provision across overlapping chunks.

        Chunk index, title, and category are intentionally excluded.
        Gemini can produce different metadata for the same source
        excerpt when that excerpt appears in more than one chunk.

        The key is scoped to the canonical document URL and document
        type so identical wording on two different policy documents
        is not collapsed together.
        """
        normalized_source = self._normalize_source_for_dedupe(
            source_text
        )

        source_digest = hashlib.sha256(
            normalized_source.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            self._canonical_url(
                document_url
            ),
            str(
                document_type
                or "legal"
            ).strip().lower(),
            source_digest,
        )

    def _stable_clause_id(
        self,
        title: str,
        category: str,
        source_text: str,
    ) -> str:

        normalized_source = re.sub(
            r"\s+",
            " ",
            source_text.strip().lower(),
        )

        payload = "|".join(
            [
                re.sub(
                    r"\s+",
                    " ",
                    title.strip().lower(),
                ),
                category.strip().lower(),
                normalized_source[:1200],
            ]
        )

        digest = hashlib.sha256(
            payload.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        return f"clause-{digest}"

    def _clause_sort_key(
        self,
        clause: Dict[str, Any],
    ):

        return (
            self._canonical_url(
                clause.get(
                    "document_url",
                    "",
                )
            ),
            str(
                clause.get(
                    "document_type",
                    "legal",
                )
                or "legal"
            ).strip().lower(),
            int(
                clause.get(
                    "chunk_index",
                    0,
                )
                or 0
            ),
            str(
                clause.get(
                    "category",
                    "other",
                )
                or "other"
            ).strip().lower(),
            str(
                clause.get(
                    "title",
                    "",
                )
                or ""
            ).strip().lower(),
            str(
                clause.get(
                    "clause_id",
                    "",
                )
                or ""
            ),
        )

    # ==========================================================
    # HELPERS
    # ==========================================================

    def _clean_text(
        self,
        value: Any,
    ) -> str:

        text = str(
            value
            or ""
        ).strip()

        return re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

    def _normalize_source_for_dedupe(
        self,
        value: Any,
    ) -> str:
        """
        Normalize grounded source text for cross-chunk deduplication.

        This is intentionally stronger than _clean_text() because the
        same scraped provision can arrive from overlapping chunks with
        harmless representation differences, for example:
        - HTML entities versus their decoded characters;
        - Unicode whitespace or zero-width characters;
        - Unicode quote/dash variants;
        - Markdown emphasis around words;
        - different whitespace around punctuation.

        The method does not perform fuzzy matching, stemming, synonym
        matching, or semantic similarity. It only canonicalizes textual
        representation before the deterministic SHA-256 identity is built.
        """
        text = html.unescape(
            str(
                value
                or ""
            )
        )

        text = unicodedata.normalize(
            "NFKC",
            text,
        )

        # Remove invisible formatting characters that can split otherwise
        # identical source excerpts.
        text = re.sub(
            r"[\u200b\u200c\u200d\u2060\ufeff]",
            "",
            text,
        )

        # Canonicalize common Unicode punctuation variants.
        punctuation_map = str.maketrans(
            {
                "\u2018": "'",
                "\u2019": "'",
                "\u201a": "'",
                "\u201b": "'",
                "\u201c": '"',
                "\u201d": '"',
                "\u201e": '"',
                "\u201f": '"',
                "\u00ab": '"',
                "\u00bb": '"',
                "\u2010": "-",
                "\u2011": "-",
                "\u2012": "-",
                "\u2013": "-",
                "\u2014": "-",
                "\u2015": "-",
                "\u2212": "-",
                "\u2026": "...",
                "\u00a0": " ",
            }
        )
        text = text.translate(
            punctuation_map
        )

        # Markdown emphasis/backtick markers can differ between overlapping
        # extraction paths without changing the underlying provision.
        text = re.sub(
            r"[`*_]+",
            "",
            text,
        )

        # Normalize whitespace, including newlines and tabs.
        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        # Canonicalize whitespace around punctuation so:
        # "policy , however ." and "policy, however."
        # produce the same dedupe identity.
        text = re.sub(
            r"\s+([,.;:!?])",
            r"\1",
            text,
        )
        text = re.sub(
            r"([([{])\s+",
            r"\1",
            text,
        )
        text = re.sub(
            r"\s+([)\]}])",
            r"\1",
            text,
        )

        return text.lower().strip()

    def _repair_source_boundaries(
        self,
        source: str,
        excerpt: str,
    ) -> str:
        """
        Repair only word-boundary and sentence-boundary cuts in an already grounded excerpt.

        Gemini or deterministic slicing can return a contiguous substring that is
        technically present in the source but begins or ends in the middle of a word or sentence.

        This method:
        - locates the grounded excerpt using deterministic whitespace normalization;
        - maps that match back to the original source;
        - expands backwards and forwards across adjacent alphanumeric characters (no mid-word cuts);
        - expands to clean sentence/heading boundaries when available;
        - returns source characters only;
        - never invents, paraphrases, or hallucinates text.
        """

        if not source or not excerpt:
            return excerpt

        source_text = str(source)
        excerpt_text = str(excerpt)

        def normalize_with_mapping(value: str):
            normalized_chars = []
            source_indices = []
            previous_was_space = False

            for index, char in enumerate(value):
                if char.isspace():
                    if not normalized_chars:
                        continue

                    if previous_was_space:
                        continue

                    normalized_chars.append(" ")
                    source_indices.append(index)
                    previous_was_space = True
                    continue

                normalized_chars.append(char.lower())
                source_indices.append(index)
                previous_was_space = False

            while normalized_chars and normalized_chars[0] == " ":
                normalized_chars.pop(0)
                source_indices.pop(0)

            while normalized_chars and normalized_chars[-1] == " ":
                normalized_chars.pop()
                source_indices.pop()

            return "".join(normalized_chars), source_indices

        normalized_source, source_indices = (
            normalize_with_mapping(source_text)
        )
        normalized_excerpt, _ = (
            normalize_with_mapping(excerpt_text)
        )

        if not normalized_source or not normalized_excerpt:
            return excerpt

        position = normalized_source.find(
            normalized_excerpt
        )

        if position < 0:
            return excerpt

        end_position = (
            position + len(normalized_excerpt) - 1
        )

        if end_position >= len(source_indices):
            return excerpt

        start_index = source_indices[position]
        end_index = source_indices[end_position] + 1

        # 1. Expand start_index across cut word characters.
        while (
            start_index > 0
            and source_text[start_index - 1].isalnum()
        ):
            start_index -= 1

        # 2. Expand start_index backwards to sentence/heading boundary if mid-sentence (up to 250 chars).
        def is_at_sentence_start(idx: int) -> bool:
            if idx <= 0:
                return True
            prev = source_text[:idx].rstrip()
            if not prev:
                return True
            if prev[-1] in ".!?\n":
                return True
            if re.search(r"(?:^|\n)\s*(?:[0-9]+[\.\)]|[A-Z\s]{3,}:|#+\s+|[A-Z][a-zA-Z\s]{2,40}\n)\s*$", source_text[:idx]):
                return True
            return False

        if not is_at_sentence_start(start_index):
            lookback_limit = max(0, start_index - 250)
            prefix = source_text[lookback_limit:start_index]
            sentence_breaks = [m.end() for m in re.finditer(r"(?:[.!?]\s+|\n+)", prefix)]
            if sentence_breaks:
                best_break = lookback_limit + sentence_breaks[-1]
                while best_break < start_index and source_text[best_break].isspace():
                    best_break += 1
                start_index = best_break
            elif lookback_limit == 0:
                start_index = 0

        # 3. Expand end_index across cut word characters.
        while (
            end_index < len(source_text)
            and source_text[end_index - 1].isalnum()
            and source_text[end_index].isalnum()
        ):
            end_index += 1

        # 4. Expand end_index forwards to sentence/section end if mid-sentence (up to 350 chars).
        def is_at_sentence_end(idx: int) -> bool:
            if idx >= len(source_text):
                return True
            if source_text[idx - 1] in ".!?\n":
                return True
            after = source_text[idx:].lstrip()
            if not after or after[0] == "\n":
                return True
            return False

        if not is_at_sentence_end(end_index):
            lookahead_limit = min(len(source_text), end_index + 350)
            suffix = source_text[end_index:lookahead_limit]
            sentence_ends = [m.end() for m in re.finditer(r"(?:[.!?](?:\s+|$|\"|')|\n+)", suffix)]
            if sentence_ends:
                best_end = end_index + sentence_ends[0]
                end_index = best_end

        repaired = self._clean_text(
            source_text[start_index:end_index]
        )

        if not repaired:
            return excerpt

        # The repair must remain independently grounded.
        if not self._source_exists(
            source_text,
            repaired,
        ):
            return excerpt

        # --------------------------------------------------------
        # POST-REPAIR START-BOUNDARY GUARD
        #
        # Even after word-boundary expansion (step 1) and sentence-
        # boundary expansion (step 2), the repaired text can still
        # start mid-sentence when the sentence start lies BEFORE the
        # chunk boundary.
        #
        # Two-part check using start_index (already computed above):
        #
        # PART A — predecessor character check (start_index > 0):
        #   When the repair did not reach position 0, the character
        #   immediately before start_index in source_text must be a
        #   sentence terminator ('.', '!', '?', '\n') or whitespace
        #   following one.  If it is not, the result still starts
        #   mid-sentence regardless of case.
        #
        #   This is the authoritative check because it is derived
        #   directly from the source text, not from the surface form
        #   of the result.  It catches ALL-CAPS mid-sentence
        #   continuations such as "OR IMPLIED, INCLUDING..." which
        #   the previous lowercase-only guard missed entirely.
        #
        # PART B — first-character/first-word check (start_index == 0):
        #   When start_index == 0 the predecessor is unavailable
        #   (chunk boundary or document start).  Fall back to the
        #   surface form of the repaired text:
        #   - lowercase first character → mid-word or mid-sentence
        #   - sentence-continuation punctuation (comma, semicolon…)
        #   - first word is a known mid-sentence connector (OR, AND,
        #     INCLUDING, FITNESS, NON-INFRINGEMENT …)
        #
        # When either part fires the guard returns "" (falsy).
        # The caller treats "" as a repair failure and routes the
        # clause to grounding_rejections so the overlapping chunk —
        # which DOES contain the sentence start — can supply a clean
        # excerpt.
        # --------------------------------------------------------

        if repaired:
            fired = False
            reason = ""

            # PART A: predecessor check when start_index > 0
            if start_index > 0:
                # Walk back past any whitespace to find the last
                # non-whitespace character before the repaired start.
                prev_idx = start_index - 1
                while prev_idx > 0 and source_text[prev_idx].isspace():
                    prev_idx -= 1
                prev_char = source_text[prev_idx]
                if prev_char not in ".!?\n":
                    # The character before the result is not a sentence
                    # terminator → still mid-sentence.
                    fired = True
                    reason = (
                        f"predecessor char {prev_char!r} is not a "
                        "sentence terminator"
                    )

            # PART B: surface-form check when start_index == 0
            # (also applied as a secondary check when start_index > 0
            # passed, as an extra safety net for the lowercase case)
            if not fired:
                first_char = repaired[0]

                # Lowercase start: mid-word or mid-sentence
                if first_char.isalpha() and first_char.islower():
                    fired = True
                    reason = f"starts lowercase {first_char!r}"

                # Sentence-continuation punctuation
                elif first_char in (",", ";", ")", "]", "}"):
                    fired = True
                    reason = f"starts with continuation punctuation {first_char!r}"

                # ALL-CAPS first word that is a known mid-sentence connector.
                # Applied only when start_index == 0 because Part A
                # already handles the start_index > 0 case definitively.
                elif start_index == 0:
                    _MID_SENTENCE_CONNECTORS = frozenset({
                        # Coordinating / subordinating conjunctions
                        "or", "and", "but", "nor", "for", "yet", "so",
                        # Additive / inclusive
                        "including", "such", "as", "well",
                        # All-caps warranty/legal mid-list continuations
                        "fitness", "merchantability", "non-infringement",
                        "implied", "express", "uninterrupted",
                        "unlimited", "indirect", "incidental",
                        "consequential", "punitive", "special",
                    })
                    first_word = re.match(
                        r"[A-Za-z][A-Za-z\-]*",
                        repaired,
                    )
                    if first_word:
                        fw = first_word.group(0).lower().rstrip("-")
                        if fw in _MID_SENTENCE_CONNECTORS:
                            fired = True
                            reason = (
                                f"first word {first_word.group(0)!r} is a "
                                "known mid-sentence connector"
                            )

            if fired:
                print(
                    "Agent 2 source boundary guard: "
                    "repair could not reach sentence start — "
                    f"{reason} — "
                    f"{repaired[:80]!r}"
                )
                return ""

        if repaired != self._clean_text(excerpt):
            print(
                "Agent 2 source boundary repaired: "
                f"{self._clean_text(excerpt)[:100]} -> "
                f"{repaired[:100]}"
            )

        return repaired

    def _source_exists(
        self,
        source: str,
        excerpt: str,
    ) -> bool:
        """
        Verify that Gemini's source excerpt is grounded in the
        supplied chunk.

        Grounding remains deterministic and conservative:
        - exact normalized containment is preferred;
        - HTML entities, zero-width characters, Unicode punctuation,
          and whitespace differences are normalized;
        - an excerpt containing an explicit ellipsis is accepted only
          when every non-empty fragment occurs in the source in the
          same order;
        - no semantic, fuzzy, or similarity-based matching is used.
        """

        if not source or not excerpt:
            return False

        def normalize_for_grounding(
            value: str,
        ) -> str:

            text = str(value)

            # Decode common HTML entities that may appear in scraped
            # source text but not in Gemini's rendered text.
            text = html.unescape(text)

            # Remove invisible formatting characters that can split
            # otherwise identical source text.
            for invisible in (
                "\u200b",
                "\u200c",
                "\u200d",
                "\u2060",
                "\ufeff",
                "\u00ad",
            ):
                text = text.replace(
                    invisible,
                    "",
                )

            # Unicode whitespace variants.
            text = (
                text
                .replace("\u00a0", " ")
                .replace("\u2007", " ")
                .replace("\u202f", " ")
            )

            # Unicode quotation/apostrophe variants.
            text = (
                text
                .replace("\u2018", "'")
                .replace("\u2019", "'")
                .replace("\u201a", "'")
                .replace("\u201b", "'")
                .replace("\u2032", "'")
                .replace("\u201c", '"')
                .replace("\u201d", '"')
                .replace("\u201e", '"')
                .replace("\u201f", '"')
                .replace("\u2033", '"')
            )

            # Unicode dash/minus variants.
            for dash in (
                "\u2010",
                "\u2011",
                "\u2012",
                "\u2013",
                "\u2014",
                "\u2015",
                "\u2212",
            ):
                text = text.replace(
                    dash,
                    "-",
                )

            # Normalize case and all whitespace.
            text = re.sub(
                r"\s+",
                " ",
                text,
            ).strip().lower()

            # Normalize spaces around punctuation.
            text = re.sub(
                r"\s+([,.;:!?])",
                r"\1",
                text,
            )

            text = re.sub(
                r"([\(\[\{])\s+",
                r"\1",
                text,
            )

            text = re.sub(
                r"\s+([\)\]\}])",
                r"\1",
                text,
            )

            # Treat " - " and "-" consistently.
            text = re.sub(
                r"\s*-\s*",
                "-",
                text,
            )

            return text

        source_normalized = normalize_for_grounding(
            source
        )

        excerpt_normalized = normalize_for_grounding(
            excerpt
        )

        if not excerpt_normalized:
            return False

        # Very short excerpts are too weak to prove grounding.
        if len(excerpt_normalized) < 20:
            return False

        # Primary path: the complete normalized excerpt is present.
        if excerpt_normalized in source_normalized:
            return True

        # Secondary path: Gemini occasionally inserts an ellipsis
        # when quoting a long provision. Accept this only when every
        # meaningful fragment is an exact source fragment and the
        # fragments occur in the same order. This is still deterministic
        # and does not permit paraphrasing.
        ellipsis_pattern = r"\.{3,}|…"
        if re.search(
            ellipsis_pattern,
            excerpt_normalized,
        ):
            fragments = [
                fragment.strip()
                for fragment in re.split(
                    ellipsis_pattern,
                    excerpt_normalized,
                )
                if fragment.strip()
            ]

            if len(fragments) >= 2:
                cursor = 0
                valid = True

                for fragment in fragments:
                    if len(fragment) < 12:
                        valid = False
                        break

                    position = source_normalized.find(
                        fragment,
                        cursor,
                    )

                    if position < 0:
                        valid = False
                        break

                    cursor = position + len(fragment)

                if valid:
                    return True

        return False

    def _list_value(
        self,
        value: Any,
    ) -> List[str]:

        if isinstance(
            value,
            list,
        ):

            result = []

            for item in value:

                cleaned = self._clean_text(
                    item
                )

                if cleaned:
                    result.append(
                        cleaned
                    )

            return result

        if isinstance(
            value,
            str,
        ) and value.strip():

            return [
                self._clean_text(
                    value
                )
            ]

        return []

    def _canonical_url(
        self,
        value: Any,
    ) -> str:

        url = str(
            value
            or ""
        ).strip()

        url = url.split(
            "#",
            1,
        )[0]

        return url.lower().rstrip("/")

    # ==========================================================
    # JSON PARSING
    # ==========================================================

    def _parse_json(
        self,
        raw: str,
    ) -> Dict[str, Any]:

        if not raw or not isinstance(raw, str):
            return {}

        text = raw.strip()

        # 1. Extract from markdown code fences if present anywhere in the string.
        code_block_match = re.search(
            r"```(?:json)?\s*([\s\S]*?)\s*```",
            text,
            re.I,
        )
        candidate = code_block_match.group(1).strip() if code_block_match else text

        def clean_json_str(s: str) -> str:
            # Remove trailing commas before closing braces/brackets
            return re.sub(r",\s*([\]}])", r"\1", s)

        def try_parse(s: str):
            cleaned = clean_json_str(s)
            try:
                return json.loads(cleaned, strict=False)
            except Exception:
                pass

            # Try finding outermost { ... }
            start_brace = cleaned.find("{")
            end_brace = cleaned.rfind("}")
            if start_brace >= 0 and end_brace > start_brace:
                sub = cleaned[start_brace : end_brace + 1]
                try:
                    return json.loads(clean_json_str(sub), strict=False)
                except Exception:
                    pass

            # Try finding outermost [ ... ]
            start_bracket = cleaned.find("[")
            end_bracket = cleaned.rfind("]")
            if start_bracket >= 0 and end_bracket > start_bracket:
                sub = cleaned[start_bracket : end_bracket + 1]
                try:
                    parsed_list = json.loads(clean_json_str(sub), strict=False)
                    if isinstance(parsed_list, list):
                        return {"clauses": parsed_list}
                except Exception:
                    pass

            return None

        data = try_parse(candidate)
        if data is None and candidate != text:
            data = try_parse(text)

        if isinstance(data, list):
            data = {"clauses": data}

        if isinstance(data, dict):
            return data

        # 2. Resilient partial extraction of individual valid clause JSON objects
        # if the overall stream was cut off or had an unterminated string in a later clause.
        clause_matches = re.finditer(
            r"\{[^{}]*(?:\"title\"|\"source_text\")[^{}]*\}",
            text,
            re.DOTALL,
        )
        salvaged_clauses = []
        for m in clause_matches:
            c_str = clean_json_str(m.group(0))
            try:
                c_obj = json.loads(c_str, strict=False)
                if isinstance(c_obj, dict) and ("title" in c_obj or "source_text" in c_obj):
                    salvaged_clauses.append(c_obj)
            except Exception:
                continue

        if salvaged_clauses:
            return {"clauses": salvaged_clauses}

        raise ValueError("No valid JSON could be extracted from response")

    # ==========================================================
    # FALLBACK SUMMARY
    # ==========================================================

    def _fallback_summary(
        self,
        title: str,
        excerpt: str,
    ) -> str:

        sentences = re.split(
            r"(?<=[.!?])\s+",
            excerpt,
        )

        for sentence in sentences:

            sentence = sentence.strip()

            if len(sentence) >= 40:
                return sentence[:500]

        return excerpt[:500]

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def _summary(
        self,
        clauses: List[Dict[str, Any]],
        chunks: Optional[
            List[Dict[str, Any]]
        ] = None,
    ) -> Dict[str, Any]:

        # ------------------------------------------------------
        # Overall risk uses deterministic source evidence whenever
        # chunks are available.
        #
        # Therefore:
        #
        # Run 1 Gemini output
        # Run 2 Gemini output
        # Gemini timeout
        # Gemini JSON failure
        #
        # cannot change the overall risk score as long as the
        # deterministic selected chunks remain the same.
        # ------------------------------------------------------

        if chunks:

            evidence = self._build_risk_evidence(
                chunks
            )

            if evidence:

                scored_evidence = score_clauses(
                    evidence
                )

                score = overall_score(
                    scored_evidence
                )

            else:

                score = 0

        else:

            # Backward-compatible behavior for callers/tests that
            # invoke _summary() directly without chunks.
            score = overall_score(
                clauses
            )

        # ------------------------------------------------------
        # Clause counts must use lowercase because risk_scoring.py
        # normalizes the final risk values to lowercase.
        # ------------------------------------------------------

        levels = {
            "critical": sum(
                str(
                    c.get(
                        "risk_level",
                        "",
                    )
                    or ""
                ).strip().lower()
                == "critical"
                for c in clauses
            ),

            "high": sum(
                str(
                    c.get(
                        "risk_level",
                        "",
                    )
                    or ""
                ).strip().lower()
                == "high"
                for c in clauses
            ),

            "medium": sum(
                str(
                    c.get(
                        "risk_level",
                        "",
                    )
                    or ""
                ).strip().lower()
                == "medium"
                for c in clauses
            ),

            "low": sum(
                str(
                    c.get(
                        "risk_level",
                        "",
                    )
                    or ""
                ).strip().lower()
                == "low"
                for c in clauses
            ),
        }

        findings = []

        # Sort findings deterministically.
        finding_clauses = sorted(
            [
                c
                for c in clauses
                if str(
                    c.get(
                        "risk_level",
                        "",
                    )
                    or ""
                ).strip().lower()
                in {
                    "critical",
                    "high",
                }
            ],
            key=self._clause_sort_key,
        )

        for clause in finding_clauses:

            findings.append(
                f"{clause.get('title', 'Important clause')}: "
                f"{clause.get('risk_reason', 'Review this clause carefully.')}"
            )

        return {
            "overall_score": score,

            "overall_risk": level_for_score(
                score
            ),

            "critical": levels["critical"],

            "high": levels["high"],

            "medium": levels["medium"],

            "low": levels["low"],

            "key_findings": findings[:8],
        }

    # ==========================================================
    # RESPONSE
    # ==========================================================

    def _result(
        self,
        clauses: List[Dict[str, Any]],
        errors: List[str],
        status: str,
        summary: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        if summary is None:

            summary = self._summary(
                clauses
            )

        return {
            "agent": self.name,

            "status": status,

            "model": self.MODEL,

            "fallback_model": self.FALLBACK,

            "analyses": [
                {
                    "analysis": {
                        "clauses": clauses
                    }
                }
            ],

            "clauses": clauses,

            "clause_count": len(
                clauses
            ),

            "summary": summary,

            "overall_risk": summary[
                "overall_risk"
            ],

            "overall_risk_score": summary[
                "overall_score"
            ],

            "key_findings": summary[
                "key_findings"
            ],

            "errors": errors,
        }