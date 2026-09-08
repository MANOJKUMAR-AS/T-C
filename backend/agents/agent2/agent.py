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

    MAX_CHUNK = int(os.getenv("LLM_CHUNK_CHARS", "9000"))
    OVERLAP = int(os.getenv("LLM_CHUNK_OVERLAP_CHARS", "300"))
    MAX_REQUESTS = int(os.getenv("LLM_MAX_REQUESTS_PER_RUN", "12"))
    DELAY = float(os.getenv("LLM_REQUEST_DELAY_SECONDS", "12.5"))
    OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "2500"))

    MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    FALLBACK = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")

    MIN_TEXT_LENGTH = 220

    LEGAL_PATTERNS = [
        (
            "Data Collection",
            [
                r"\bcollect(?:s|ed|ing)?\b.{0,180}\b(?:personal|user|customer)\b.{0,120}\b(?:data|information)\b",
                r"\bpersonal information\b.{0,180}\bcollect",
                r"\bwe collect\b",
            ],
        ),
        (
            "Data Sharing",
            [
                r"\bshare(?:s|d|ing)?\b.{0,180}\b(?:third parties|partners|service providers)\b",
                r"\bservice providers\b.{0,180}\b(?:data|information)\b",
                r"\b(?:business|advertising) partners\b",
            ],
        ),
        (
            "Cookies and Tracking",
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
            [
                r"\bretain(?:s|ed|ing)?\b.{0,180}\b(?:data|information)\b",
                r"\bretention\b.{0,180}\b(?:data|information)\b",
                r"\bkeep\b.{0,120}\b(?:data|information)\b",
            ],
        ),
        (
            "Policy Changes",
            [
                r"\bmay change\b.{0,180}\b(?:terms|policy|agreement)\b",
                r"\bmodify\b.{0,180}\b(?:terms|policy|agreement)\b",
                r"\bcontinued use\b.{0,180}\b(?:accept|agree)\b",
                r"\bwithout notice\b",
            ],
        ),
        (
            "Account Termination",
            [
                r"\bterminate\b.{0,180}\b(?:account|service)\b",
                r"\bsuspend\b.{0,180}\b(?:account|service)\b",
                r"\btermination\b.{0,180}\b(?:account|service)\b",
            ],
        ),
        (
            "Limitation of Liability",
            [
                r"\blimitation of liability\b",
                r"\bnot liable\b",
                r"\bmaximum liability\b",
                r"\bexclude\b.{0,100}\bdamages\b",
            ],
        ),
        (
            "Arbitration",
            [
                r"\bbinding arbitration\b",
                r"\bmandatory arbitration\b",
                r"\barbitrat(?:e|ion)\b",
            ],
        ),
        (
            "Class Action Waiver",
            [
                r"\bclass[- ]action\b",
                r"\bclass action waiver\b",
            ],
        ),
        (
            "Indemnification",
            [
                r"\bindemnif(?:y|ies|ied|ication)\b",
                r"\bhold harmless\b",
            ],
        ),
        (
            "User Content License",
            [
                r"\broyalty[- ]free\b",
                r"\birrevocable\b.{0,100}\blicense\b",
                r"\bworldwide\b.{0,100}\blicense\b",
                r"\blicense\b.{0,160}\buser content\b",
                r"\buser content\b.{0,160}\blicense\b",
            ],
        ),
        (
            "Government Disclosure",
            [
                r"\blaw enforcement\b",
                r"\bgovernment authorities\b",
                r"\blegal process\b",
                r"\bgovernment request\b",
            ],
        ),
        (
            "Advertising and Targeting",
            [
                r"\btargeted advertising\b",
                r"\binterest[- ]based advertising\b",
                r"\bpersonalized advertising\b",
                r"\badvertising partners\b",
            ],
        ),
        (
            "Sensitive Personal Information",
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
            [
                r"\bcancel(?:lation)?\b.{0,180}\b(?:subscription|order|service)\b",
                r"\brefund(?:s)?\b",
                r"\bnon[- ]refundable\b",
            ],
        ),
        (
            "Payment Obligations",
            [
                r"\bpayment\b.{0,180}\b(?:credit card|debit card|fee|charge)\b",
                r"\bfees?\b.{0,180}\b(?:pay|payment|charge)\b",
                r"\bautomatically charge\b",
            ],
        ),
    ]

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.client = None

        if self.api_key and genai:
            try:
                self.client = genai.Client(api_key=self.api_key)
                print("Agent 2: Gemini client initialized.")
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

    def run(self, policies: List[Dict[str, Any]]) -> Dict[str, Any]:
        print()
        print("=" * 70)
        print("AGENT 2 - CLAUSE AND RISK ANALYSIS")
        print("=" * 70)
        print(f"Policy documents received: {len(policies)}")

        if not policies:
            return self._result(
                clauses=[],
                errors=["No policy documents were supplied to Agent 2."],
                status="complete",
            )

        chunks = self._build_balanced_chunks(policies)

        print(f"Analysis chunks selected: {len(chunks)}")

        if not chunks:
            return self._result(
                clauses=[],
                errors=["No usable policy text was found."],
                status="complete",
            )

        clauses: List[Dict[str, Any]] = []
        errors: List[str] = []
        last_request = 0.0

        for request_number, item in enumerate(chunks, 1):
            wait = self.DELAY - (
                time.monotonic() - last_request
            )

            if wait > 0:
                time.sleep(wait)

            print(
                f"Gemini request #{request_number}/{len(chunks)} "
                f"| {item['document_type']} "
                f"| chunk {item['chunk_index']}"
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

            if result is None or len(result) == 0:
                print(
                    "Gemini returned no clauses. "
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
                if not isinstance(clause, dict):
                    continue

                title = str(
                    clause.get("title", "")
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

        clauses = self._dedupe(clauses)

        clauses = score_clauses(clauses)

        summary = self._summary(clauses)

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
            f"Overall risk: {summary['overall_risk']} "
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
    # BALANCED CHUNK SELECTION
    # ==========================================================

    def _build_balanced_chunks(
        self,
        policies: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        per_document: List[List[Dict[str, Any]]] = []

        for doc_index, policy in enumerate(policies):
            text = str(
                policy.get("content")
                or policy.get("text")
                or ""
            ).strip()

            if len(text) < self.MIN_TEXT_LENGTH:
                continue

            document_chunks = []

            for chunk_index, chunk in enumerate(
                self._chunks(text)
            ):
                document_chunks.append(
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
                    }
                )

            if document_chunks:
                per_document.append(
                    document_chunks
                )

        # Round-robin allocation prevents one huge
        # privacy document from consuming every request.
        result = []

        cursor = 0

        while (
            len(result) < self.MAX_REQUESTS
            and per_document
        ):
            added = False

            for document_chunks in per_document:
                if cursor < len(document_chunks):
                    result.append(
                        document_chunks[cursor]
                    )

                    if len(result) >= self.MAX_REQUESTS:
                        break

                    added = True

            if not added:
                break

            cursor += 1

        return result

    # ==========================================================
    # CHUNKING
    # ==========================================================

    def _chunks(self, text: str) -> List[str]:
        if len(text) <= self.MAX_CHUNK:
            return [text]

        out = []

        start = 0

        step = max(
            1,
            self.MAX_CHUNK - self.OVERLAP,
        )

        while start < len(text):
            end = min(
                len(text),
                start + self.MAX_CHUNK,
            )

            chunk = text[start:end]

            if end < len(text):
                cut = chunk.rfind("\n\n")

                if cut > self.MAX_CHUNK * 0.65:
                    chunk = chunk[:cut]
                    end = start + cut

            if chunk.strip():
                out.append(chunk)

            if end <= start:
                end = start + step

            start = end

        return out

    # ==========================================================
    # GEMINI
    # ==========================================================

    def _request(
        self,
        model: str,
        text: str,
    ) -> Optional[List[Dict[str, Any]]]:

        prompt = f"""
You analyze a Terms & Conditions, Privacy Policy, Cookie Policy,
legal agreement, returns policy, payment policy, or similar document.

Return ONLY valid JSON.
No markdown.
No commentary.

Schema:

{{
  "clauses": [
    {{
      "title": "short clause title",
      "summary": "plain-language summary",
      "explanation": "why this matters to the user",
      "obligations": [],
      "permissions": [],
      "restrictions": [],
      "consequences": [],
      "risk_reason": "short reason",
      "risk_factors": [],
      "source_text": "brief exact excerpt supporting the clause"
    }}
  ]
}}

Rules:

- Extract substantive legal or privacy clauses.
- Extract actual obligations, permissions, restrictions,
  disclosures, rights, tracking, data practices, retention,
  sharing, advertising, payment, cancellation, liability,
  arbitration, termination, licensing, indemnification,
  government disclosure, and policy-change provisions.
- Do not extract navigation, menus, product listings,
  cookie banners, footer boilerplate, or page chrome.
- Do not invent facts.
- Every clause must be supported by source_text.
- Keep source_text concise.
- Return multiple clauses when multiple substantive provisions
  exist in the supplied text.
- If the supplied text contains substantive legal provisions,
  do NOT return an empty clauses array.

DOCUMENT CHUNK:

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
                return None

            data = self._parse_json(raw)

            clauses = (
                data.get("clauses", [])
                if isinstance(data, dict)
                else None
            )

            if not isinstance(clauses, list):
                return None

            clean = []

            for clause in clauses[:30]:
                if not isinstance(clause, dict):
                    continue

                if not clause.get("title"):
                    continue

                if not clause.get("source_text"):
                    continue

                clean.append(clause)

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

        for title, patterns in self.LEGAL_PATTERNS:

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
                match.start() - 260,
            )

            end = min(
                len(clean_text),
                match.end() + 420,
            )

            excerpt = clean_text[
                start:end
            ].strip()

            if len(excerpt) < 40:
                continue

            clauses.append(
                {
                    "title": title,
                    "summary": (
                        self._fallback_summary(
                            title,
                            excerpt,
                        )
                    ),
                    "explanation": (
                        "This provision is relevant "
                        "because it establishes how "
                        "the service handles this "
                        "legal or user-facing issue."
                    ),
                    "obligations": [],
                    "permissions": [],
                    "restrictions": [],
                    "consequences": [],
                    "risk_reason": (
                        f"The document contains a "
                        f"provision concerning {title.lower()}."
                    ),
                    "risk_factors": [],
                    "source_text": excerpt[:900],
                }
            )

        return clauses[:20]

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
    # JSON
    # ==========================================================

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
            return json.loads(raw)

        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")

            if start >= 0 and end > start:
                return json.loads(
                    raw[start:end + 1]
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
                    f"{clause.get('summary', '')}"
                ).lower(),
            ).strip()

            if len(key) < 15:
                continue

            if key in seen:
                continue

            seen.add(key)
            result.append(clause)

        return result

    # ==========================================================
    # SUMMARY
    # ==========================================================

    def _summary(
        self,
        clauses: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        score = overall_score(clauses)

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
            if clause.get("risk_level") in (
                "CRITICAL",
                "HIGH",
            ):
                findings.append(
                    f"{clause.get('title', 'Important clause')}: "
                    f"{clause.get('risk_reason', 'Review this clause carefully.')}"
                )

        return {
            "overall_score": score,
            "overall_risk": level_for_score(score),
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
        summary: Optional[Dict[str, Any]] = None,
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