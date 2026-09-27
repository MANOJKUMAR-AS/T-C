"""
Utility functions for Agent 3.

Handles parsing, validation, normalization, and conversion.

Production rule:
Agent 2 is authoritative for risk.
"""

import json
from typing import Any, Dict, List

from .models import (
    ClauseAnalysis,
    ClauseCategory,
    RiskLevel,
)


def parse_json_response(
    response: str,
) -> Dict[str, Any]:
    """
    Parse an LLM response into a Python dictionary.
    """

    if not response:
        raise ValueError(
            "Agent 3 received an empty response."
        )

    cleaned = response.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]

    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Agent 3 returned invalid JSON: {exc}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(
            "Agent 3 response must be a JSON object."
        )

    return result


def normalize_risk_score(
    score: Any,
) -> int:
    """
    Normalize Agent 3's legacy standalone 0-10 score.

    Production Agent 2 scores are normally 0-100 and are
    preserved separately by Agent 3.
    """

    try:
        score = int(score)

    except (TypeError, ValueError):
        return 0

    return max(
        0,
        min(10, score),
    )


def normalize_agent2_risk_score(
    score: Any,
) -> int:
    """
    Normalize Agent 2's authoritative 0-100 risk score.
    """

    try:
        score = int(score)

    except (TypeError, ValueError):
        return 0

    return max(
        0,
        min(100, score),
    )


def normalize_risk_level(
    risk_level: Any,
    risk_score: int,
) -> RiskLevel:
    """
    Normalize a legacy Agent 3 0-10 risk level.
    """

    if isinstance(risk_level, str):
        normalized = (
            risk_level
            .strip()
            .lower()
        )

        mapping = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "moderate": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }

        if normalized in mapping:
            return mapping[normalized]

    if risk_score <= 2:
        return RiskLevel.LOW

    if risk_score <= 6:
        return RiskLevel.MEDIUM

    if risk_score <= 8:
        return RiskLevel.HIGH

    return RiskLevel.CRITICAL


def normalize_agent2_risk_level(
    risk_level: Any,
    score: int,
) -> RiskLevel:
    """
    Normalize Agent 2's authoritative risk level.

    Agent 2 uses:
        0-44   LOW
        45-80  MEDIUM
        81-100 HIGH
    """

    if isinstance(risk_level, str):
        normalized = (
            risk_level
            .strip()
            .lower()
        )

        mapping = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "moderate": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }

        if normalized in mapping:
            return mapping[normalized]

    if score > 80:
        return RiskLevel.HIGH

    if score >= 45:
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def normalize_category(
    category: Any,
) -> ClauseCategory:
    """
    Convert a category string into ClauseCategory.
    """

    if isinstance(category, str):
        normalized = (
            category
            .strip()
            .lower()
        )

        try:
            return ClauseCategory(
                normalized
            )

        except ValueError:
            pass

    return ClauseCategory.OTHER


def safe_text(
    value: Any,
    default: str = "",
) -> str:
    """
    Safely convert a value to a string.
    """

    if value is None:
        return default

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def convert_analysis(
    raw_analysis: Dict[str, Any],
) -> ClauseAnalysis:
    """
    Convert one LLM JSON analysis object into a ClauseAnalysis.

    SCALE CONTRACT
    ==============
    convert_analysis() always uses the 0-100 normaliser
    (normalize_agent2_risk_score / normalize_agent2_risk_level).

    Reasoning:
    - In the production pipeline (Agent 2 → Agent 3) the LLM is
      instructed to echo back Agent 2's 0-100 scores unchanged.
      _preserve_agent2_risk() then unconditionally replaces every
      risk_score/risk_level with the authoritative ClauseInput value
      from Agent 2 before anything leaves Agent 3, so the value
      produced here never reaches the final result for production calls.
    - In standalone unit tests the mock LLM returns small integers
      (e.g. 6).  Clamping 6 into 0-100 gives 6, which is correct.
      The legacy 0-10 thresholds apply only in
      calculate_overall_risk_score() / calculate_overall_risk_level(),
      which are already isolated to the standalone-mode overall score
      fallback path inside analyze().

    Therefore a single 0-100 normaliser is safe here and removes any
    need to guess the scale from the numeric value.
    """

    clause_id = safe_text(
        raw_analysis.get("clause_id")
    )

    if not clause_id:
        raise ValueError(
            "Agent 3 returned an analysis "
            "without clause_id."
        )

    # Always use the 0-100 normaliser.
    # Scores that are genuinely small (0-10) survive unchanged because
    # clamping them to [0, 100] does not alter their value.
    risk_score = normalize_agent2_risk_score(
        raw_analysis.get("risk_score", 0)
    )

    # Always use the Agent 2 level normaliser.
    # For standalone tests the risk_level string ("low", "medium", …)
    # is parsed first and returned directly, so the score-based
    # fallback (which uses Agent 2 thresholds) is never reached for
    # well-formed standalone responses.
    risk_level = normalize_agent2_risk_level(
        raw_analysis.get("risk_level"),
        risk_score,
    )

    category = normalize_category(
        raw_analysis.get(
            "category"
        )
    )

    return ClauseAnalysis(
        clause_id=clause_id,
        category=category,
        risk_level=risk_level,
        risk_score=risk_score,
        summary=safe_text(
            raw_analysis.get("summary"),
            "No summary provided.",
        ),
        explanation=safe_text(
            raw_analysis.get("explanation"),
            "No explanation provided.",
        ),
        user_impact=safe_text(
            raw_analysis.get("user_impact"),
            "No user impact identified.",
        ),
        recommendation=safe_text(
            raw_analysis.get("recommendation"),
            "Review this clause carefully.",
        ),
        evidence=safe_text(
            raw_analysis.get("evidence")
        ),
    )


def convert_analyses(
    raw_response: Dict[str, Any],
) -> List[ClauseAnalysis]:
    """
    Convert all analyses in an LLM response.
    """

    if isinstance(
        raw_response,
        list,
    ):
        raw_analyses = raw_response

    elif isinstance(
        raw_response,
        dict,
    ):
        raw_analyses = raw_response.get(
            "analyses",
            [],
        )

    else:
        raise ValueError(
            "Agent 3 response must be "
            "a dictionary or list."
        )

    if not isinstance(
        raw_analyses,
        list,
    ):
        raise ValueError(
            "'analyses' must be a list."
        )

    analyses: List[
        ClauseAnalysis
    ] = []

    for item in raw_analyses:

        if not isinstance(
            item,
            dict,
        ):
            continue

        try:
            analysis = convert_analysis(
                item
            )

            analyses.append(
                analysis
            )

        except ValueError:
            continue

    return analyses


def calculate_overall_risk_score(
    analyses: List[ClauseAnalysis],
) -> int:
    """
    Calculate the legacy standalone Agent 3 0-10 score.

    This exists for backward-compatible unit tests.

    Production Agent 2 risk is NOT calculated here.
    """

    if not analyses:
        return 0

    scores = sorted(
        (
            analysis.risk_score
            for analysis in analyses
        ),
        reverse=True,
    )

    top_scores = scores[:5]

    if len(top_scores) == 1:
        return top_scores[0]

    weights = [
        0.40,
        0.25,
        0.15,
        0.10,
        0.10,
    ]

    weighted_score = 0.0
    total_weight = 0.0

    for score, weight in zip(
        top_scores,
        weights,
    ):
        weighted_score += (
            score * weight
        )

        total_weight += weight

    if total_weight == 0:
        return 0

    return round(
        weighted_score / total_weight
    )


def calculate_overall_risk_level(
    score: int,
) -> RiskLevel:
    """
    Convert a legacy Agent 3 0-10 score into RiskLevel.
    """

    score = normalize_risk_score(
        score
    )

    if score <= 2:
        return RiskLevel.LOW

    if score <= 6:
        return RiskLevel.MEDIUM

    if score <= 8:
        return RiskLevel.HIGH

    return RiskLevel.CRITICAL


def validate_clause_count(
    analyses: List[ClauseAnalysis],
    expected_count: int,
) -> List[str]:
    """
    Detect missing or duplicate clause analyses.
    """

    warnings: List[str] = []

    if len(analyses) != expected_count:
        warnings.append(
            "Agent 3 did not return an analysis "
            "for every clause."
        )

    clause_ids = [
        analysis.clause_id
        for analysis in analyses
    ]

    duplicates = {
        clause_id
        for clause_id in clause_ids
        if clause_ids.count(
            clause_id
        ) > 1
    }

    if duplicates:
        warnings.append(
            "Duplicate clause analyses detected: "
            + ", ".join(
                sorted(duplicates)
            )
        )

    return warnings
