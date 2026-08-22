from typing import List, Optional

from pydantic import BaseModel, Field


# ============================================================
# CLAUSE ANALYSIS
# ============================================================

class ClauseAnalysis(BaseModel):
    """
    Represents the analysis of one meaningful clause
    extracted from a Terms & Conditions or privacy document.
    """

    clause_id: str
    title: str
    category: str

    summary: str
    explanation: str

    obligations: List[str] = Field(
        default_factory=list
    )

    permissions: List[str] = Field(
        default_factory=list
    )

    restrictions: List[str] = Field(
        default_factory=list
    )

    consequences: List[str] = Field(
        default_factory=list
    )

    risk_level: str

    risk_reason: Optional[str] = None

    source_text: str


# ============================================================
# CLAUSE EXTRACTION
# ============================================================

class ClauseExtraction(BaseModel):
    """
    Internal schema used by Agent 2 when communicating
    with the Groq model.

    Groq is responsible only for extracting clauses.

    Document-level information such as:

        - document_type
        - overall_risk
        - key_findings

    is constructed by Python after all chunks have
    been processed.
    """

    clauses: List[ClauseAnalysis] = Field(
        default_factory=list
    )


# ============================================================
# DOCUMENT ANALYSIS
# ============================================================

class DocumentAnalysis(BaseModel):
    """
    Final structured output returned by Agent 2.
    """

    document_type: str

    overall_risk: str

    key_findings: List[str] = Field(
        default_factory=list
    )

    clauses: List[ClauseAnalysis] = Field(
        default_factory=list
    )