"""
Data models for Agent 3.

Agent 3 receives clauses that may already contain authoritative
risk information from Agent 2 and returns explanations.

IMPORTANT:
Agent 2 is the source of truth for production risk.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


# ============================================================
# RISK LEVEL
# ============================================================

class RiskLevel(str, Enum):
    """Risk classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================
# CLAUSE CATEGORY
# ============================================================

class ClauseCategory(str, Enum):
    """
    Categories understood by Agent 3.

    The Agent 2 categories are included explicitly so that
    authoritative Agent 2 classifications are preserved
    instead of being silently converted to OTHER.
    """

    # --------------------------------------------------------
    # Agent 2 categories
    # --------------------------------------------------------

    SUBSCRIPTION = "subscription"
    AUTO_RENEWAL = "auto_renewal"
    CANCELLATION = "cancellation"
    PAYMENTS = "payments"
    PRIVACY = "privacy"
    DATA_COLLECTION = "data_collection"
    DATA_SHARING = "data_sharing"
    REFUND = "refund"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    LICENSE = "license"
    LIABILITY = "liability"
    INDEMNIFICATION = "indemnification"
    ARBITRATION = "arbitration"
    TERMINATION = "termination"
    TRACKING = "tracking"
    SECURITY = "security"
    PROHIBITED_USE = "prohibited_use"

    # --------------------------------------------------------
    # Existing Agent 3 categories
    #
    # Keep these for backward compatibility with existing
    # Agent 3 tests and standalone usage.
    # --------------------------------------------------------

    DATA_PRIVACY = "data_privacy"
    DATA_RETENTION = "data_retention"
    USER_CONTENT = "user_content"
    PAYMENT = "payment"
    GOVERNING_LAW = "governing_law"
    ACCOUNT_TERMINATION = "account_termination"
    COOKIES = "cookies"
    THIRD_PARTY = "third_party"
    MARKETING = "marketing"

    # --------------------------------------------------------
    # Fallback
    # --------------------------------------------------------

    OTHER = "other"


# ============================================================
# CLAUSE INPUT
# ============================================================

@dataclass
class ClauseInput:
    """
    A clause sent to Agent 3.

    The risk fields are optional for backward compatibility
    with the existing Agent 3 unit tests.

    In the production Agent 1 -> Agent 2 -> Agent 3 pipeline,
    Agent 2 supplies these fields.
    """

    clause_id: str
    text: str
    title: Optional[str] = None
    source: Optional[str] = None

    # --------------------------------------------------------
    # Agent 2 authoritative fields
    # --------------------------------------------------------

    category: Optional[str] = None
    risk_score: Optional[int] = None
    risk_level: Optional[str] = None
    risk_reason: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert the clause to a dictionary."""

        data = {
            "clause_id": self.clause_id,
            "text": self.text,
            "title": self.title,
            "source": self.source,
        }

        if self.category is not None:
            data["category"] = self.category

        if self.risk_score is not None:
            data["risk_score"] = self.risk_score

        if self.risk_level is not None:
            data["risk_level"] = self.risk_level

        if self.risk_reason is not None:
            data["risk_reason"] = self.risk_reason

        return data


# ============================================================
# RISK FINDING
# ============================================================

@dataclass
class RiskFinding:
    """
    Risk identified in a specific clause.

    Kept for backward compatibility with the existing Agent 3
    package exports.
    """

    clause_id: str
    category: ClauseCategory
    risk_level: RiskLevel
    risk_score: int

    summary: str
    explanation: str

    user_impact: str
    recommendation: str

    evidence: str = ""

    def to_dict(self) -> dict:
        """Convert the finding to a dictionary."""

        return {
            "clause_id": self.clause_id,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "summary": self.summary,
            "explanation": self.explanation,
            "user_impact": self.user_impact,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }


# ============================================================
# CLAUSE ANALYSIS
# ============================================================

@dataclass
class ClauseAnalysis:
    """
    Explanation generated by Agent 3.

    In production, risk_level and risk_score are preserved
    from Agent 2.
    """

    clause_id: str
    category: ClauseCategory
    risk_level: RiskLevel
    risk_score: int

    summary: str
    explanation: str

    user_impact: str
    recommendation: str

    evidence: str = ""

    def to_dict(self) -> dict:
        """Convert the analysis to a dictionary."""

        return {
            "clause_id": self.clause_id,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "risk_score": self.risk_score,
            "summary": self.summary,
            "explanation": self.explanation,
            "user_impact": self.user_impact,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
        }


# ============================================================
# AGENT 3 REQUEST
# ============================================================

@dataclass
class Agent3Request:
    """
    Complete request sent to Agent 3.

    overall_risk_score and overall_risk_level are supplied
    by Agent 2 in production.
    """

    clauses: List[ClauseInput] = field(
        default_factory=list
    )

    document_id: Optional[str] = None
    document_title: Optional[str] = None

    # --------------------------------------------------------
    # Agent 2 authoritative document-level risk
    # --------------------------------------------------------

    overall_risk_score: Optional[int] = None
    overall_risk_level: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert the request to a dictionary."""

        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "overall_risk_score": self.overall_risk_score,
            "overall_risk_level": self.overall_risk_level,
            "clauses": [
                clause.to_dict()
                for clause in self.clauses
            ],
        }


# ============================================================
# AGENT 3 RESPONSE
# ============================================================

@dataclass
class Agent3Response:
    """
    Complete response returned by Agent 3.

    The response deliberately exposes both the native Agent 3
    fields and compatibility aliases used by the wider backend
    pipeline.
    """

    document_id: Optional[str]

    analyses: List[ClauseAnalysis] = field(
        default_factory=list
    )

    overall_risk_level: RiskLevel = (
        RiskLevel.LOW
    )

    overall_risk_score: int = 0

    total_clauses: int = 0
    analyzed_clauses: int = 0

    warnings: List[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict:
        """
        Convert the response to a JSON-safe dictionary.

        Compatibility fields are included so Agent 3 can be
        consumed consistently with Agent 2.
        """

        risk_level = (
            self.overall_risk_level.value
        )

        analyses = [
            analysis.to_dict()
            for analysis in self.analyses
        ]

        return {
            # ------------------------------------------------
            # Explicit Agent 3 status
            # ------------------------------------------------
            "status": "complete",

            # ------------------------------------------------
            # Metadata
            # ------------------------------------------------
            "document_id": self.document_id,

            # ------------------------------------------------
            # Canonical Agent 3 risk fields
            # ------------------------------------------------
            "overall_risk_level": risk_level,
            "overall_risk_score": (
                int(self.overall_risk_score)
            ),

            # ------------------------------------------------
            # Compatibility aliases
            # ------------------------------------------------
            "overall_risk": risk_level,
            "clause_count": int(
                self.total_clauses
            ),

            # ------------------------------------------------
            # Coverage
            # ------------------------------------------------
            "total_clauses": int(
                self.total_clauses
            ),
            "analyzed_clauses": int(
                self.analyzed_clauses
            ),

            # ------------------------------------------------
            # Diagnostics
            # ------------------------------------------------
            "warnings": list(
                self.warnings
            ),

            # ------------------------------------------------
            # Findings
            # ------------------------------------------------
            "analyses": analyses,

            # Compatibility alias used by some consumers.
            "risk_findings": analyses,
        }


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "RiskLevel",
    "ClauseCategory",
    "ClauseInput",
    "RiskFinding",
    "ClauseAnalysis",
    "Agent3Request",
    "Agent3Response",
]