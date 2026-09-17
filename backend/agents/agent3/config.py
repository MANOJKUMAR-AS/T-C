"""
Configuration for Agent 3.

Agent 3 analyzes normalized Terms & Conditions clauses
and identifies potentially important or risky clauses.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

HERE = Path(__file__).resolve()
BACKEND = HERE.parents[2]
PROJECT = BACKEND.parent

for env_file in (
    PROJECT / ".env",
    BACKEND / ".env",
):
    if env_file.exists():
        load_dotenv(
            env_file,
            override=False,
        )


# ============================================================
# ENVIRONMENT HELPERS
# ============================================================

def _get_int_env(
    name: str,
    default: int,
) -> int:
    """
    Safely read an integer environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_float_env(
    name: str,
    default: float,
) -> float:
    """
    Safely read a float environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_bool_env(
    name: str,
    default: bool,
) -> bool:
    """
    Safely read a boolean environment variable.
    """

    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "true",
        "1",
        "yes",
        "y",
    }


def _get_model_env() -> str:
    """
    Get the Agent 3 Gemini model.

    Priority:
        1. AGENT3_MODEL
        2. GEMINI_MODEL
        3. Gemini default
    """

    model = (
        os.getenv(
            "AGENT3_MODEL",
            "",
        ).strip()
        or os.getenv(
            "GEMINI_MODEL",
            "",
        ).strip()
        or "gemini-3.5-flash-lite"
    )

    return model


# ============================================================
# CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class Agent3Config:
    """
    Runtime configuration for Agent 3.
    """

    model_name: str = _get_model_env()

    temperature: float = _get_float_env(
        "AGENT3_TEMPERATURE",
        0.1,
    )

    max_tokens: int = _get_int_env(
        "AGENT3_MAX_TOKENS",
        4000,
    )

    min_risk_score: int = _get_int_env(
        "AGENT3_MIN_RISK_SCORE",
        0,
    )

    max_risk_score: int = _get_int_env(
        "AGENT3_MAX_RISK_SCORE",
        10,
    )

    max_clauses: int = _get_int_env(
        "AGENT3_MAX_CLAUSES",
        100,
    )

    include_explanations: bool = _get_bool_env(
        "AGENT3_INCLUDE_EXPLANATIONS",
        True,
    )


# ============================================================
# DEFAULT CONFIGURATION
# ============================================================

DEFAULT_CONFIG = Agent3Config()
