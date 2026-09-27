"""
Gemini LLM client for Agent 3.

Provides:
- Gemini API client initialization
- Controlled application-level retry handling for transient 503/429 errors
- Explicit fallback-model handling
- Stable generate() interface expected by Agent 3
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

try:
    from google import genai
except Exception:
    genai = None


# ============================================================
# PATH / ENVIRONMENT LOADING
# ============================================================

HERE = Path(__file__).resolve()
BACKEND = HERE.parents[2]
PROJECT = BACKEND.parent

for env in (
    PROJECT / ".env",
    BACKEND / ".env",
):
    if env.exists():
        load_dotenv(env, override=False)


# ============================================================
# GEMINI CLIENT
# ============================================================

class GeminiLLMClient:
    """
    Gemini client used by Agent 3.

    The client performs a small amount of application-level
    retry handling for provider 503 errors and then switches
    to a configured fallback model.
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
                "GEMINI_API_KEY environment variable is not set."
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
    # HELPERS
    # ========================================================

    @staticmethod
    def _is_retryable_error(
        exc: Exception,
    ) -> bool:
        """
        Detect transient Gemini provider failures that are safe
        to retry at the application layer.

        Supported transient conditions:
        - HTTP 503 / UNAVAILABLE
        - HTTP 429 / RESOURCE_EXHAUSTED
        - RATE_LIMIT_EXCEEDED
        """

        error_text = str(exc).upper()

        return (
            "503" in error_text
            or "UNAVAILABLE" in error_text
            or "SERVICE_UNAVAILABLE" in error_text
            or "429" in error_text
            or "RESOURCE_EXHAUSTED" in error_text
            or "RATE_LIMIT_EXCEEDED" in error_text
        )


    @staticmethod
    def _get_retry_count() -> int:
        """
        Read application-level transient-error retry count.

        Default:
            2 retries

        Therefore the primary model receives:
            initial attempt + 2 retries = 3 attempts
        """

        raw_value = os.getenv(
            "AGENT3_TRANSIENT_RETRIES",
            "2",
        ).strip()

        try:
            return max(
                0,
                int(raw_value),
            )
        except ValueError:
            print(
                "Agent 3: Invalid AGENT3_TRANSIENT_RETRIES value "
                f"'{raw_value}'. Using 2."
            )
            return 2


    @staticmethod
    def _get_primary_model(
        explicit_model: Optional[str],
    ) -> str:
        """
        Resolve the primary Gemini model.
        """

        return (
            explicit_model
            or os.getenv(
                "AGENT3_MODEL",
                "",
            ).strip()
            or os.getenv(
                "GEMINI_MODEL",
                "gemini-3.5-flash-lite",
            ).strip()
        )


    @staticmethod
    def _get_fallback_model() -> str:
        """
        Resolve the fallback Gemini model.
        """

        return os.getenv(
            "AGENT3_FALLBACK_MODEL",
            "gemini-2.5-flash-lite",
        ).strip()


    # ========================================================
    # SINGLE REQUEST
    # ========================================================

    def _request_model(
        self,
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        attempt: int,
        total_attempts: int,
    ) -> str:
        """
        Execute one Gemini request.
        """

        print(
            "Agent 3 Gemini request | "
            f"model={model_name} | "
            f"attempt={attempt}/{total_attempts}"
        )

        try:
            response = (
                self.client.models.generate_content(
                    model=model_name,
                    contents=user_prompt,
                    config={
                        "system_instruction": system_prompt,
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                        "response_mime_type": "application/json",
                    },
                )
            )

        except Exception as exc:
            print(
                "Agent 3 Gemini request failed."
            )
            print(
                f"Model: {model_name}"
            )
            print(
                f"Attempt: {attempt}/{total_attempts}"
            )
            print(
                f"Error type: {type(exc).__name__}"
            )
            print(
                f"Error: {exc}"
            )

            raise


        output_text = (
            getattr(
                response,
                "text",
                "",
            )
            or ""
        )

        if not output_text.strip():
            raise RuntimeError(
                "Gemini returned an empty response."
            )

        print(
            "Agent 3 Gemini request succeeded | "
            f"model={model_name} | "
            f"attempt={attempt}/{total_attempts}"
        )

        return output_text


    # ========================================================
    # PUBLIC GENERATE METHOD
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
        Generate a Gemini response.

        Model selection order:

        1. Explicit model argument
        2. AGENT3_MODEL
        3. GEMINI_MODEL
        4. gemini-3.5-flash-lite

        On transient 503/429 errors:

        1. Retry the primary model
        2. Switch to the fallback model
        3. Retry the fallback model using the same controlled
           transient-error retry budget

        Non-transient errors are not retried.
        """

        primary_model = self._get_primary_model(
            model
        )

        fallback_model = self._get_fallback_model()

        retry_count = self._get_retry_count()

        print(
            "Agent 3 model configuration | "
            f"primary={primary_model} | "
            f"fallback={fallback_model} | "
            f"503_retries={retry_count}"
        )


        # ====================================================
        # BUILD MODEL PLAN
        # ====================================================

        model_plan = [
            primary_model,
        ]

        if (
            fallback_model
            and fallback_model != primary_model
        ):
            model_plan.append(
                fallback_model
            )


        last_exception: Optional[Exception] = None


        # ====================================================
        # PRIMARY MODEL
        # ====================================================

        primary_attempts = retry_count + 1

        for attempt in range(
            1,
            primary_attempts + 1,
        ):

            try:
                return self._request_model(
                    model_name=primary_model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    attempt=attempt,
                    total_attempts=primary_attempts,
                )

            except Exception as exc:

                last_exception = exc

                if not self._is_retryable_error(exc):
                    raise RuntimeError(
                        "Gemini API request failed: "
                        f"{exc}"
                    ) from exc

                if attempt < primary_attempts:

                    delay_seconds = (
                        2 ** (attempt - 1)
                    )

                    error_text = str(exc).upper()

                    if (
                        "429" in error_text
                        or "RESOURCE_EXHAUSTED" in error_text
                        or "RATE_LIMIT_EXCEEDED" in error_text
                    ):
                        error_kind = "429/quota"
                    else:
                        error_kind = "503/unavailable"

                    print(
                        "Agent 3 Gemini "
                        f"{error_kind} detected. "
                        f"Primary model retry in "
                        f"{delay_seconds}s..."
                    )

                    time.sleep(
                        delay_seconds
                    )

                    continue

                print(
                    "Agent 3 primary Gemini model "
                    "remained unavailable or rate-limited "
                    "after "
                    f"{primary_attempts} attempt(s)."
                )


        # ====================================================
        # FALLBACK MODEL
        # ====================================================

        if len(model_plan) > 1:

            print(
                "Agent 3 switching to fallback model: "
                f"{fallback_model}"
            )

            # The fallback receives the same controlled retry
            # budget for transient provider failures.
            fallback_attempts = retry_count + 1

            for attempt in range(
                1,
                fallback_attempts + 1,
            ):

                try:
                    response = self._request_model(
                        model_name=fallback_model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        attempt=attempt,
                        total_attempts=fallback_attempts,
                    )

                    print(
                        "Agent 3 fallback model succeeded | "
                        f"model={fallback_model}"
                    )

                    return response

                except Exception as exc:

                    last_exception = exc

                    if not self._is_retryable_error(exc):
                        raise RuntimeError(
                            "Gemini fallback model failed: "
                            f"{exc}"
                        ) from exc

                    if attempt < fallback_attempts:

                        delay_seconds = (
                            2 ** (attempt - 1)
                        )

                        error_text = str(exc).upper()

                        if (
                            "429" in error_text
                            or "RESOURCE_EXHAUSTED" in error_text
                            or "RATE_LIMIT_EXCEEDED" in error_text
                        ):
                            error_kind = "429/quota"
                        else:
                            error_kind = "503/unavailable"

                        print(
                            "Agent 3 fallback "
                            f"{error_kind} detected. "
                            f"Fallback retry in "
                            f"{delay_seconds}s..."
                        )

                        time.sleep(
                            delay_seconds
                        )

                        continue

                    print(
                        "Agent 3 fallback model exhausted "
                        "its transient-error retry budget."
                    )


        # ====================================================
        # FINAL FAILURE
        # ====================================================

        if last_exception is not None:
            raise RuntimeError(
                "Gemini API request failed after "
                "primary retry and fallback handling: "
                f"{last_exception}"
            ) from last_exception

        raise RuntimeError(
            "Gemini API request failed for an unknown reason."
        )


# ============================================================
# BACKWARD-COMPATIBILITY ALIAS
# ============================================================

OpenAILLMClient = GeminiLLMClient