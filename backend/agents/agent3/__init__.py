"""
Agent 3 - Terms & Conditions Risk Analyzer.

This package analyzes normalized Terms & Conditions clauses
and produces structured risk findings.
"""

from .agent import Agent3
from .config import Agent3Config
from .llm_client import OpenAILLMClient
from .models import (
    Agent3Request,
    Agent3Response,
    ClauseAnalysis,
    ClauseCategory,
    ClauseInput,
    RiskFinding,
    RiskLevel,
)

__all__ = [
    "Agent3",
    "Agent3Config",
    "OpenAILLMClient",
    "Agent3Request",
    "Agent3Response",
    "ClauseAnalysis",
    "ClauseCategory",
    "ClauseInput",
    "RiskFinding",
    "RiskLevel",
]