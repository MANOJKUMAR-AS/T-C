"""
Gemini LLM client for Agent 3.

This module adapts Google's Gemini API to the
LLM client interface expected by Agent 3.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

try:
    from google import genai
except Exception:
    genai = None


# ============================================================
# ENVIRONMENT
# ============================================================

HERE = Path(__file__).resolve()
BACKEND = HERE.parents[2]
PROJECT = BACKEND.parent

for env in (
    PROJECT / ".env",
    BACKEND / ".env",
):
    if env.exists():
        load_dotenv(
            env,
            override=False,
        )


class GeminiLLMClient:
    """
    Gemini implementation of Agent 3's LLM client.

    The API key is read from GEMINI_API_KEY.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
    ) -> None:

        self.api_key = (
            api_key
            or os.getenv(
                "GEMINI_API_KEY",
                "",
            ).strip()
        )

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY environment variable "
                "is not set."
            )

        if genai is None:
            raise ImportError(
                "google-genai package is not installed."
            )

        try:
            self.client = genai.Client(
                api_key=self.api_key
            )

        except Exception as exc:
            raise RuntimeError(
                "Failed to initialize Gemini client: "
                f"{exc}"
            ) from exc

        print(
            "Agent 3: Gemini client initialized."
        )

    # ========================================================
    # GENERATE
    # ========================================================

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate a response using Gemini.

        Parameters
        ----------
        system_prompt:
            System instructions for Agent 3.

        user_prompt:
            Agent 3 analysis request.

        temperature:
            Gemini sampling temperature.

        max_tokens:
            Maximum output tokens.

        model:
            Gemini model name. If omitted, AGENT3_MODEL
            is used, followed by GEMINI_MODEL.
        """

        selected_model = (
            model
            or os.getenv(
                "AGENT3_MODEL",
                "",
            ).strip()
            or os.getenv(
                "GEMINI_MODEL",
                "gemini-3.5-flash-lite",
            ).strip()
        )

        print(
            f"Agent 3 Gemini request | model={selected_model}"
        )

        try:

            response = self.client.models.generate_content(
                model=selected_model,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json",
                },
            )

        except Exception as exc:

            print(
                "Agent 3 Gemini request failed."
            )
            print(
                f"Model: {selected_model}"
            )
            print(
                f"Error type: {type(exc).__name__}"
            )
            print(
                f"Error: {exc}"
            )

            raise RuntimeError(
                "Gemini API request failed: "
                f"{exc}"
            ) from exc

        output_text = getattr(
            response,
            "text",
            "",
        ) or ""

        if not output_text.strip():
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        return output_text


# ============================================================
# BACKWARD-COMPATIBILITY ALIAS
# ============================================================

# This allows older imports of OpenAILLMClient to continue
# working while the project migrates Agent 3 to Gemini.

OpenAILLMClient = GeminiLLMClient