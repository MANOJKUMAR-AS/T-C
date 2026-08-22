import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI

from .prompts import SYSTEM_PROMPT, USER_PROMPT
from .schemas import (
    ClauseAnalysis,
    ClauseExtraction,
    DocumentAnalysis,
)


# ============================================================
# ENVIRONMENT
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")


# ============================================================
# AGENT 2
# ============================================================

class Agent2:
    """
    Agent 2 performs clause-level Terms & Conditions analysis
    using Groq through its OpenAI-compatible API.

    Important design choice:

    Groq is NOT asked to satisfy a large nested JSON schema
    through response_format=json_schema.

    Instead, Groq is asked to return JSON text and Python
    validates the result using Pydantic.

    This avoids Groq structured-output validation failures
    for longer documents.
    """

    def __init__(self, client=None, model: str | None = None):

        self.model = model or os.getenv(
            "AGENT2_MODEL",
            "openai/gpt-oss-20b",
        )

        if client is not None:
            self.client = client
            return

        groq_api_key = os.getenv("GROQ_API_KEY")

        if not groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not configured. "
                "Check your .env file."
            )

        self.client = OpenAI(
            api_key=groq_api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    # ========================================================
    # MAIN ANALYSIS
    # ========================================================

    def analyze(self, text: str) -> DocumentAnalysis:

        if not text or not text.strip():
            raise ValueError(
                "Agent 2 received empty document text."
            )

        text = text.strip()

        chunks = self._chunk_text(text)

        print(
            f"Agent 2: document contains "
            f"{len(chunks)} chunk(s)"
        )

        all_clauses: List[ClauseAnalysis] = []

        for index, chunk in enumerate(chunks, start=1):

            print(
                f"Agent 2: analyzing chunk "
                f"{index}/{len(chunks)} "
                f"({len(chunk)} characters)"
            )

            extraction = self._extract_clauses(
                chunk,
                chunk_number=index,
                total_chunks=len(chunks),
            )

            print(
                f"Agent 2: chunk "
                f"{index}/{len(chunks)} returned "
                f"{len(extraction.clauses)} clause(s)"
            )

            all_clauses.extend(
                extraction.clauses
            )

        # ----------------------------------------------------
        # Remove duplicate clauses
        # ----------------------------------------------------

        all_clauses = self._deduplicate_clauses(
            all_clauses
        )

        # ----------------------------------------------------
        # Make sure clause IDs are stable
        # ----------------------------------------------------

        all_clauses = self._normalize_clause_ids(
            all_clauses
        )

        # ----------------------------------------------------
        # Document type
        # ----------------------------------------------------

        document_type = self._infer_document_type(
            text
        )

        # ----------------------------------------------------
        # Overall risk
        # ----------------------------------------------------

        overall_risk = self._calculate_overall_risk(
            all_clauses
        )

        # ----------------------------------------------------
        # Key findings
        # ----------------------------------------------------

        key_findings = self._build_key_findings(
            all_clauses
        )

        # ----------------------------------------------------
        # Final structured result
        # ----------------------------------------------------

        return DocumentAnalysis(
            document_type=document_type,
            overall_risk=overall_risk,
            key_findings=key_findings,
            clauses=all_clauses,
        )

    # ========================================================
    # CHUNKING
    # ========================================================

    def _chunk_text(
        self,
        text: str,
        max_characters: int = 5000,
    ) -> List[str]:
        """
        Split long documents into manageable chunks.

        A smaller chunk size reduces the chance that the model
        produces incomplete JSON.
        """

        if len(text) <= max_characters:
            return [text]

        paragraphs = re.split(
            r"\n\s*\n",
            text,
        )

        chunks: List[str] = []

        current = ""

        for paragraph in paragraphs:

            paragraph = paragraph.strip()

            if not paragraph:
                continue

            candidate = (
                f"{current}\n\n{paragraph}"
                if current
                else paragraph
            )

            if len(candidate) <= max_characters:
                current = candidate
                continue

            if current:
                chunks.append(current)

            # Extremely long paragraph
            # needs hard splitting.
            if len(paragraph) > max_characters:

                for start in range(
                    0,
                    len(paragraph),
                    max_characters,
                ):
                    piece = paragraph[
                        start:start + max_characters
                    ]

                    chunks.append(
                        piece
                    )

                current = ""

            else:
                current = paragraph

        if current:
            chunks.append(current)

        return chunks

    # ========================================================
    # CLAUSE EXTRACTION
    # ========================================================

    def _extract_clauses(
        self,
        text: str,
        chunk_number: int = 1,
        total_chunks: int = 1,
    ) -> ClauseExtraction:

        prompt = f"""
Analyze the following Terms & Conditions,
privacy policy, or legal document excerpt.

Return ONLY valid JSON.

Do not return markdown.
Do not return ```json.
Do not return explanations outside the JSON.

The JSON must have exactly this structure:

{{
  "clauses": [
    {{
      "clause_id": "string",
      "title": "string",
      "category": "string",
      "summary": "string",
      "explanation": "string",
      "obligations": [],
      "permissions": [],
      "restrictions": [],
      "consequences": [],
      "risk_level": "low",
      "risk_reason": "string or null",
      "source_text": "string"
    }}
  ]
}}

Rules:

1. Always include "clauses".
2. Identify meaningful clauses from the supplied text.
3. Do not invent information.
4. source_text must come from the supplied text.
5. obligations must always be an array.
6. permissions must always be an array.
7. restrictions must always be an array.
8. consequences must always be an array.
9. risk_level must be one of:
   low
   medium
   high
   critical
10. risk_reason may be null.
11. Keep source_text reasonably concise.
12. If there are no meaningful clauses, return:
   {{"clauses":[]}}

Document chunk:
{text}
"""

        last_error = None

        # ----------------------------------------------------
        # Retry
        # ----------------------------------------------------

        for attempt in range(1, 4):

            try:

                print(
                    f"Agent 2: Groq JSON attempt "
                    f"{attempt}/3 for chunk "
                    f"{chunk_number}/{total_chunks}"
                )

                response = (
                    self.client.chat.completions.create(
                        model=self.model,

                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    SYSTEM_PROMPT
                                    + "\nReturn JSON only."
                                ),
                            },
                            {
                                "role": "user",
                                "content": prompt,
                            },
                        ],

                        temperature=0,

                        # IMPORTANT:
                        #
                        # We use JSON mode instead of
                        # json_schema mode.
                        #
                        response_format={
                            "type": "json_object"
                        },
                    )
                )

                content = (
                    response.choices[0]
                    .message
                    .content
                )

                if not content:
                    raise ValueError(
                        "Groq returned empty content."
                    )

                print(
                    f"Agent 2: Groq returned "
                    f"{len(content)} characters"
                )

                parsed = self._parse_json(
                    content
                )

                extraction = (
                    ClauseExtraction.model_validate(
                        parsed
                    )
                )

                return extraction

            except Exception as error:

                last_error = error

                print(
                    f"Agent 2: JSON attempt "
                    f"{attempt}/3 failed: "
                    f"{error}"
                )

        # ----------------------------------------------------
        # All retries failed
        # ----------------------------------------------------

        raise last_error

    # ========================================================
    # JSON PARSER
    # ========================================================

    def _parse_json(
        self,
        content: str,
    ) -> Dict[str, Any]:

        content = content.strip()

        # ----------------------------------------------------
        # Remove markdown fences if model adds them.
        # ----------------------------------------------------

        if content.startswith("```"):

            content = re.sub(
                r"^```(?:json)?\s*",
                "",
                content,
                flags=re.IGNORECASE,
            )

            content = re.sub(
                r"\s*```$",
                "",
                content,
            )

            content = content.strip()

        # ----------------------------------------------------
        # Direct JSON
        # ----------------------------------------------------

        try:

            parsed = json.loads(
                content
            )

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "Groq JSON response must be an object."
                )

            return parsed

        except json.JSONDecodeError:

            pass

        # ----------------------------------------------------
        # Attempt to locate JSON object
        # ----------------------------------------------------

        start = content.find("{")
        end = content.rfind("}")

        if start >= 0 and end > start:

            candidate = content[
                start:end + 1
            ]

            try:

                parsed = json.loads(
                    candidate
                )

                if not isinstance(
                    parsed,
                    dict,
                ):
                    raise ValueError(
                        "Extracted JSON must be an object."
                    )

                return parsed

            except json.JSONDecodeError as error:

                raise ValueError(
                    "Groq returned invalid JSON."
                ) from error

        raise ValueError(
            "Groq returned no JSON object."
        )

    # ========================================================
    # DOCUMENT TYPE
    # ========================================================

    def _infer_document_type(
        self,
        text: str,
    ) -> str:

        normalized = text.lower()

        if (
            "privacy notice" in normalized
            or "privacy policy" in normalized
            or "personal data" in normalized
        ):
            return "Privacy Notice"

        if (
            "terms of use" in normalized
            or "terms and conditions" in normalized
            or "terms & conditions" in normalized
        ):
            return "Terms & Conditions"

        if (
            "cookie policy" in normalized
            or "cookie preferences" in normalized
        ):
            return "Cookie Policy"

        if "subscription" in normalized:
            return "Subscription Terms"

        if "license agreement" in normalized:
            return "License Agreement"

        return "Legal Agreement"

    # ========================================================
    # OVERALL RISK
    # ========================================================

    def _calculate_overall_risk(
        self,
        clauses: List[ClauseAnalysis],
    ) -> str:

        if not clauses:
            return "low"

        ranking = {
            "low": 1,
            "medium": 2,
            "high": 3,
            "critical": 4,
        }

        highest = max(
            clauses,
            key=lambda clause: ranking.get(
                clause.risk_level.lower(),
                1,
            ),
        )

        return highest.risk_level.lower()

    # ========================================================
    # KEY FINDINGS
    # ========================================================

    def _build_key_findings(
        self,
        clauses: List[ClauseAnalysis],
    ) -> List[str]:

        findings: List[str] = []

        for clause in clauses:

            summary = clause.summary.strip()

            if not summary:
                continue

            if summary in findings:
                continue

            findings.append(
                summary
            )

        # Keep document-level findings manageable.
        return findings[:10]

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    def _deduplicate_clauses(
        self,
        clauses: List[ClauseAnalysis],
    ) -> List[ClauseAnalysis]:

        unique: List[ClauseAnalysis] = []

        seen = set()

        for clause in clauses:

            key = (
                clause.title.strip().lower(),
                clause.source_text.strip().lower(),
            )

            if key in seen:
                continue

            seen.add(key)

            unique.append(
                clause
            )

        return unique

    # ========================================================
    # CLAUSE ID NORMALIZATION
    # ========================================================

    def _normalize_clause_ids(
        self,
        clauses: List[ClauseAnalysis],
    ) -> List[ClauseAnalysis]:

        normalized: List[ClauseAnalysis] = []

        for index, clause in enumerate(
            clauses,
            start=1,
        ):

            data = clause.model_dump()

            data["clause_id"] = (
                f"C{index}"
            )

            normalized.append(
                ClauseAnalysis.model_validate(
                    data
                )
            )

        return normalized

    # ========================================================
    # DICTIONARY OUTPUT
    # ========================================================

    def analyze_to_dict(
        self,
        text: str,
    ) -> Dict[str, Any]:

        result = self.analyze(
            text
        )

        return result.model_dump()

    # ========================================================
    # JSON OUTPUT
    # ========================================================

    def analyze_to_json(
        self,
        text: str,
    ) -> str:

        result = self.analyze(
            text
        )

        return result.model_dump_json(
            indent=2
        )