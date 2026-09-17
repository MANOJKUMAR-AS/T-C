from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

try:
    from google import genai
except Exception:
    genai = None

from .risk_scoring import score_clauses, overall_score, level_for_score


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

    LEGAL_PATTERNS = [
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

            if self.client:

                result = self._request(
                    self.MODEL,
                    item["text"],
                )

                last_request = time.monotonic()

                if result is None:
                    print(
                        "Primary model failed. "
                        f"Trying fallback: {self.FALLBACK}"
                    )

                    result = self._request(
                        self.FALLBACK,
                        item["text"],
                    )

                    last_request = time.monotonic()

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

                if not title:
                    continue

                clause["document_url"] = (
                    item["document_url"]
                )

                clause["document_type"] = (
                    item["document_type"]
                )

                clause["chunk_index"] = (
                    item["chunk_index"]
                )

                clauses.append(clause)

        clauses = self._dedupe(
            clauses
        )

        clauses = score_clauses(
            clauses
        )

        summary = self._summary(
            clauses
        )

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
                        "document_url": policy.get(
                            "url",
                            "",
                        ),
                        "document_type": policy.get(
                            "type",
                            "legal",
                        ),
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
                            "document_url": policy.get(
                                "url",
                                "",
                            ),
                            "document_type": policy.get(
                                "type",
                                "legal",
                            ),
                            "chunk_index": chunk_index,
                            "text": chunk,
                            "relevance_score": 0,
                        }
                    )

        # Sort primarily by legal relevance.
        candidates.sort(
            key=lambda item: (
                item["relevance_score"],
                -item["chunk_index"],
            ),
            reverse=True,
        )

        # Prevent a single document from consuming all requests.
        selected: List[
            Dict[str, Any]
        ] = []

        per_document = {}

        for item in candidates:

            doc_index = item[
                "document_index"
            ]

            used = per_document.get(
                doc_index,
                0,
            )

            if used >= 4:
                continue

            selected.append(item)

            per_document[
                doc_index
            ] = used + 1

            if len(selected) >= self.MAX_REQUESTS:
                break

        # If fewer than MAX_REQUESTS were selected,
        # fill remaining slots from unused candidates.
        if len(selected) < self.MAX_REQUESTS:

            selected_keys = {
                (
                    item["document_index"],
                    item["chunk_index"],
                )
                for item in selected
            }

            for item in candidates:

                key = (
                    item["document_index"],
                    item["chunk_index"],
                )

                if key in selected_keys:
                    continue

                selected.append(item)

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

        # Headings are particularly useful.
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

        # Penalize obvious navigation-heavy chunks.
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

        out = []

        start = 0

        while start < len(text):

            end = min(
                len(text),
                start + self.MAX_CHUNK,
            )

            chunk = text[start:end]

            if end < len(text):

                # Prefer paragraph boundaries.
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

        return out

    # ==========================================================
    # GEMINI
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
      "risk_reason": "why this risk level applies",
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

Rules:

1. Extract substantive legal, contractual, privacy, payment,
   account, liability, intellectual-property, or user-rights
   provisions.

2. Do not return a document-level summary.

3. Do not invent information.

4. Every clause MUST be supported by source_text.

5. source_text must be copied from the supplied document.

6. Extract multiple clauses when multiple substantive provisions
   are present.

7. Do not extract menus, navigation, product listings,
   recommendations, advertisements, cookie-banner buttons,
   footer navigation, or page chrome.

8. Preserve ambiguity from the source.

9. Use [] when obligations, permissions, restrictions,
   or consequences are not present.

10. If substantive legal provisions exist in the supplied text,
    return clauses rather than an empty list.

DOCUMENT TEXT:

{text}
"""

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

            clean = []

            for index, clause in enumerate(
                raw_clauses[:30],
                1,
            ):

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

                category = str(
                    clause.get(
                        "category",
                        "other",
                    )
                ).strip().lower()

                if not category:
                    category = "other"

                risk_level = str(
                    clause.get(
                        "risk_level",
                        "medium",
                    )
                ).strip().lower()

                if risk_level not in {
                    "low",
                    "medium",
                    "high",
                    "critical",
                }:
                    risk_level = "medium"

                clean.append(
                    {
                        "clause_id": str(
                            clause.get(
                                "clause_id",
                                f"clause-{index}",
                            )
                        ).strip()
                        or f"clause-{index}",

                        "title": title,

                        "category": category,

                        "summary": str(
                            clause.get(
                                "summary",
                                "",
                            )
                        ).strip(),

                        "explanation": str(
                            clause.get(
                                "explanation",
                                "",
                            )
                        ).strip(),

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

                        "risk_level": risk_level,

                        "risk_reason": str(
                            clause.get(
                                "risk_reason",
                                "",
                            )
                        ).strip(),

                        "source_text": source_text[
                            :1200
                        ],
                    }
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

    # ==========================================================
    # DETERMINISTIC FALLBACK
    # ==========================================================

    def _fallback_extract(
        self,
        text: str,
    ) -> List[Dict[str, Any]]:

        clean_text = re.sub(
            r"\s+",
            " ",
            text or "",
        ).strip()

        if len(clean_text) < self.MIN_TEXT_LENGTH:
            return []

        clauses = []

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

            start = max(
                0,
                match.start() - 350,
            )

            end = min(
                len(clean_text),
                match.end() + 650,
            )

            excerpt = clean_text[
                start:end
            ].strip()

            if len(excerpt) < 40:
                continue

            clauses.append(
                {
                    "clause_id": (
                        f"fallback-{len(clauses) + 1}"
                    ),

                    "title": title,

                    "category": category,

                    "summary": (
                        self._fallback_summary(
                            title,
                            excerpt,
                        )
                    ),

                    "explanation": (
                        f"This provision concerns "
                        f"{title.lower()} and may affect "
                        f"the user's rights, obligations, "
                        f"privacy, account, payments, "
                        f"or other use of the service."
                    ),

                    "obligations": [],

                    "permissions": [],

                    "restrictions": [],

                    "consequences": [],

                    "risk_level": (
                        self._fallback_risk(
                            category
                        )
                    ),

                    "risk_reason": (
                        f"The document contains a "
                        f"provision concerning "
                        f"{title.lower()}."
                    ),

                    "source_text": excerpt[:1200],
                }
            )

        return clauses[:20]

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
    # HELPERS
    # ==========================================================

    def _list_value(
        self,
        value: Any,
    ) -> List[str]:

        if isinstance(
            value,
            list,
        ):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        if isinstance(
            value,
            str,
        ) and value.strip():
            return [value.strip()]

        return []

    def _parse_json(
        self,
        raw: str,
    ) -> Dict[str, Any]:

        raw = raw.strip()

        raw = re.sub(
            r"^```(?:json)?\s*",
            "",
            raw,
            flags=re.I,
        )

        raw = re.sub(
            r"\s*```$",
            "",
            raw,
        )

        try:
            return json.loads(
                raw
            )

        except Exception:

            start = raw.find(
                "{"
            )

            end = raw.rfind(
                "}"
            )

            if start >= 0 and end > start:

                return json.loads(
                    raw[
                        start:end + 1
                    ]
                )

            raise

    # ==========================================================
    # DEDUPLICATION
    # ==========================================================

    def _dedupe(
        self,
        clauses: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        result = []

        seen = set()

        for clause in clauses:

            key = re.sub(
                r"\W+",
                " ",
                (
                    f"{clause.get('title', '')} "
                    f"{clause.get('summary', '')} "
                    f"{clause.get('source_text', '')}"
                ).lower(),
            ).strip()

            if len(key) < 15:
                continue

            if key in seen:
                continue

            seen.add(key)

            result.append(
                clause
            )

        return result

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def _summary(
        self,
        clauses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        score = overall_score(
            clauses
        )

        levels = {
            "CRITICAL": sum(
                c.get("risk_level") == "CRITICAL"
                for c in clauses
            ),
            "HIGH": sum(
                c.get("risk_level") == "HIGH"
                for c in clauses
            ),
            "MEDIUM": sum(
                c.get("risk_level") == "MEDIUM"
                for c in clauses
            ),
            "LOW": sum(
                c.get("risk_level") == "LOW"
                for c in clauses
            ),
        }

        findings = []

        for clause in clauses:

            if clause.get(
                "risk_level"
            ) in (
                "CRITICAL",
                "HIGH",
            ):

                findings.append(
                    f"{clause.get('title', 'Important clause')}: "
                    f"{clause.get('risk_reason', 'Review this clause carefully.')}"
                )

        return {
            "overall_score": score,
            "overall_risk": level_for_score(
                score
            ),
            "critical": levels["CRITICAL"],
            "high": levels["HIGH"],
            "medium": levels["MEDIUM"],
            "low": levels["LOW"],
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
            "clause_count": len(clauses),
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
