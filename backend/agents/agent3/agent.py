"""
Agent 3 - Terms & Conditions Explanation Agent.

Agent 2 is the single source of truth for risk.

Agent 3:
- explains clauses
- explains user impact
- gives recommendations
- provides evidence

Agent 3 does NOT independently determine production risk.
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import replace
from typing import Any, List, Optional, Protocol

from .config import (
    Agent3Config,
    DEFAULT_CONFIG,
)
from .models import (
    Agent3Request,
    Agent3Response,
    ClauseAnalysis,
    ClauseInput,
    ClauseCategory,
    RiskLevel,
)
from .prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from .utils import (
    calculate_overall_risk_level,
    calculate_overall_risk_score,
    convert_analyses,
    normalize_agent2_risk_level,
    normalize_agent2_risk_score,
    normalize_category,
    parse_json_response,
    validate_clause_count,
)


logger = logging.getLogger(__name__)


# ============================================================
# LLM INTERFACE
# ============================================================

class LLMClient(Protocol):
    """
    Interface required by Agent 3 LLM clients.
    """

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        model: Optional[str] = None,
    ) -> str:
        """
        Generate an LLM response.
        """
        ...


# ============================================================
# AGENT 3
# ============================================================

class Agent3:
    """
    Agent 3 explanation agent.

    Production architecture:

        Agent 2
           |
           | authoritative risk
           v
        Agent 3
           |
           | explanation
           v
        Frontend
    """

    BATCH_SIZE = 10

    def __init__(
        self,
        llm_client: LLMClient,
        config: Agent3Config = DEFAULT_CONFIG,
    ) -> None:
        """
        Initialize Agent 3.
        """

        self.llm_client = llm_client
        self.config = config

        logger.info(
            "Agent 3 initialized with model: %s",
            self.config.model_name,
        )

    # ========================================================
    # MAIN ANALYSIS
    # ========================================================

    def analyze(
        self,
        request: Agent3Request,
    ) -> Agent3Response:
        """
        Analyze all clauses.

        If Agent 2 risk is present in the request,
        Agent 3 preserves it exactly.
        """

        self._validate_request(
            request
        )

        clauses = list(
            request.clauses
        )

        batches = self._create_batches(
            clauses
        )

        all_analyses: List[
            ClauseAnalysis
        ] = []

        # Track clause occurrences already consumed by earlier
        # batches. Positions are used instead of clause IDs because
        # duplicate IDs can occasionally appear in model output or
        # upstream input.
        assigned_clause_positions = set()

        warnings: List[str] = []

        # ----------------------------------------------------
        # Process batches
        # ----------------------------------------------------

        for batch_number, batch in enumerate(
            batches,
            start=1,
        ):
            print(
                f"Agent 3 batch "
                f"{batch_number}/{len(batches)} "
                f"| clauses={len(batch)}"
            )

            logger.info(
                "Agent 3 processing batch %d/%d.",
                batch_number,
                len(batches),
            )

            try:
                batch_analyses = (
                    self._analyze_batch(
                        batch=batch,
                        request=request,
                        batch_number=batch_number,
                        total_batches=len(batches),
                        assigned_clause_positions=assigned_clause_positions,
                    )
                )

                all_analyses.extend(
                    batch_analyses
                )

            except Exception:
                logger.exception(
                    "Agent 3 batch %d failed.",
                    batch_number,
                )
                raise

        # ----------------------------------------------------
        # Deduplicate
        # ----------------------------------------------------

        all_analyses = (
            self._deduplicate_analyses(
                all_analyses
            )
        )

        # ----------------------------------------------------
        # Preserve Agent 2 risk in every analysis
        # ----------------------------------------------------

        all_analyses = (
            self._preserve_agent2_risk(
                analyses=all_analyses,
                clauses=clauses,
            )
        )

        # ----------------------------------------------------
        # Coverage validation
        # ----------------------------------------------------

        coverage_warnings = (
            validate_clause_count(
                analyses=all_analyses,
                expected_count=len(
                    clauses
                ),
            )
        )

        warnings.extend(
            coverage_warnings
        )

        # ----------------------------------------------------
        # Overall risk
        #
        # PRODUCTION:
        # If Agent 2 supplied overall risk, use it directly.
        #
        # STANDALONE TESTS:
        # If no Agent 2 risk exists, use the legacy Agent 3
        # calculation so the existing 15 tests remain valid.
        # ----------------------------------------------------

        if (
            request.overall_risk_score
            is not None
            or request.overall_risk_level
            is not None
        ):
            overall_score = (
                normalize_agent2_risk_score(
                    request.overall_risk_score
                )
            )

            overall_level = (
                normalize_agent2_risk_level(
                    request.overall_risk_level,
                    overall_score,
                )
            )

        else:
            overall_score = (
                calculate_overall_risk_score(
                    all_analyses
                )
            )

            overall_level = (
                calculate_overall_risk_level(
                    overall_score
                )
            )

        # ----------------------------------------------------
        # Response
        # ----------------------------------------------------

        response = Agent3Response(
            document_id=request.document_id,
            analyses=all_analyses,
            overall_risk_level=overall_level,
            overall_risk_score=overall_score,
            total_clauses=len(
                clauses
            ),
            analyzed_clauses=len(
                all_analyses
            ),
            warnings=warnings,
        )

        print(
            "Agent 3 complete "
            f"| analyzed={len(all_analyses)}/"
            f"{len(clauses)} "
            f"| risk={overall_level.value} "
            f"({overall_score}/100)"
            if (
                request.overall_risk_score
                is not None
                or request.overall_risk_level
                is not None
            )
            else
            "Agent 3 complete "
            f"| analyzed={len(all_analyses)}/"
            f"{len(clauses)} "
            f"| risk={overall_level.value} "
            f"({overall_score}/10)"
        )

        return response

    # ========================================================
    # CONVENIENCE METHOD
    # ========================================================

    def analyze_clauses(
        self,
        clauses: List[ClauseInput],
        document_id: Optional[str] = None,
        document_title: Optional[str] = None,
        overall_risk_score: Optional[int] = None,
        overall_risk_level: Optional[str] = None,
    ) -> Agent3Response:
        """
        Convenience method for analyzing clauses.
        """

        request = Agent3Request(
            clauses=clauses,
            document_id=document_id,
            document_title=document_title,
            overall_risk_score=(
                overall_risk_score
            ),
            overall_risk_level=(
                overall_risk_level
            ),
        )

        return self.analyze(
            request
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_request(
        self,
        request: Agent3Request,
    ) -> None:
        """
        Validate Agent 3 input.
        """

        if request is None:
            raise ValueError(
                "Agent 3 request cannot be None."
            )

        if not request.clauses:
            raise ValueError(
                "Agent 3 requires at least one clause."
            )

        if (
            len(request.clauses)
            > self.config.max_clauses
        ):
            raise ValueError(
                f"Agent 3 received "
                f"{len(request.clauses)} clauses, "
                f"but the maximum is "
                f"{self.config.max_clauses}."
            )

        for index, clause in enumerate(
            request.clauses
        ):
            if not clause.clause_id:
                raise ValueError(
                    f"Clause at index {index} "
                    "does not have a clause_id."
                )

            if not clause.text.strip():
                raise ValueError(
                    f"Clause '{clause.clause_id}' "
                    "contains empty text."
                )

    # ========================================================
    # BATCHING
    # ========================================================

    def _create_batches(
        self,
        clauses: List[ClauseInput],
    ) -> List[List[ClauseInput]]:
        """
        Split clauses into controlled batches.
        """

        return [
            clauses[
                index:index + self.BATCH_SIZE
            ]
            for index in range(
                0,
                len(clauses),
                self.BATCH_SIZE,
            )
        ]

    # ========================================================
    # BATCH ANALYSIS
    # ========================================================

    def _analyze_batch(
        self,
        batch: List[ClauseInput],
        request: Agent3Request,
        batch_number: int,
        total_batches: int,
        assigned_clause_positions: set,
    ) -> List[ClauseAnalysis]:
        """
        Analyze one batch.

        Document metadata and Agent 2 risk are passed into
        the prompt.
        """

        serialized_clauses = (
            self._serialize_clauses(
                batch
            )
        )

        overall_score = (
            request.overall_risk_score
        )

        overall_level = (
            request.overall_risk_level
        )

        user_prompt = build_user_prompt(
            clauses=serialized_clauses,
            document_id=(
                request.document_id
                or "unknown"
            ),
            document_title=(
                request.document_title
                or "Terms & Conditions"
            ),
            overall_risk_score=(
                str(overall_score)
                if overall_score is not None
                else "not supplied"
            ),
            overall_risk_level=(
                str(overall_level)
                if overall_level is not None
                else "not supplied"
            ),
        )

        raw_response = self._call_llm(
            user_prompt=user_prompt,
            batch_number=batch_number,
            total_batches=total_batches,
        )

        analyses = self._parse_analyses_with_repair(
            raw_response=raw_response,
            original_user_prompt=user_prompt,
            batch=batch,
            batch_number=batch_number,
        )

        batch_start_index = (
            (batch_number - 1) * self.BATCH_SIZE
        )

        analyses = self._rebind_batch_clause_ids(
            analyses=analyses,
            batch=batch,
            batch_number=batch_number,
            batch_start_index=batch_start_index,
            assigned_clause_positions=assigned_clause_positions,
        )

        return analyses

    # ========================================================
    # JSON PARSING WITH ONE CONSTRAINED REPAIR
    # ========================================================

    def _parse_analyses_with_repair(
        self,
        raw_response: str,
        original_user_prompt: str,
        batch: List[ClauseInput],
        batch_number: int,
    ) -> List[ClauseAnalysis]:
        """
        Parse Gemini output and make one constrained repair attempt
        if the first response contains malformed JSON.
        """

        try:
            return self._parse_analyses(raw_response)

        except ValueError as parse_error:
            logger.warning(
                "Agent 3 batch %d returned invalid JSON. "
                "Attempting one constrained JSON repair. Error: %s",
                batch_number,
                parse_error,
            )

        repair_prompt = self._build_json_repair_prompt(
            original_user_prompt=original_user_prompt,
            raw_response=raw_response,
            batch=batch,
        )

        repaired_response = self._call_llm(
            user_prompt=repair_prompt,
            batch_number=batch_number,
            total_batches=batch_number,
            temperature_override=0.0,
            max_tokens_override=min(
                self.config.max_tokens,
                6000,
            ),
        )

        try:
            analyses = self._parse_analyses(
                repaired_response
            )
        except ValueError as repair_error:
            logger.exception(
                "Agent 3 batch %d JSON repair failed.",
                batch_number,
            )
            raise ValueError(
                "Agent 3 returned malformed JSON and "
                "the single constrained repair attempt "
                "also returned invalid JSON."
            ) from repair_error

        if not analyses:
            raise ValueError(
                "Agent 3 JSON repair returned no valid analyses "
                f"for batch {batch_number}."
            )

        return analyses

    def _build_json_repair_prompt(
        self,
        original_user_prompt: str,
        raw_response: str,
        batch: List[ClauseInput],
    ) -> str:
        """
        Build a narrowly scoped JSON-syntax repair request.

        The model is instructed to preserve the existing response
        and repair syntax only.
        """

        expected_ids = [
            clause.clause_id
            for clause in batch
        ]

        return f"""
Repair the JSON syntax of the Agent 3 response below.

This is a JSON repair task, NOT a new analysis task.

STRICT RULES:

1. Return ONLY valid JSON.
2. Return a JSON object with an "analyses" array.
3. Preserve every analysis that exists in the original response.
4. Do NOT add an analysis.
5. Do NOT remove an analysis.
6. Do NOT rewrite, summarize, or improve explanations.
7. Do NOT change clause_id values.
8. Do NOT change category values.
9. Do NOT change risk_level values.
10. Do NOT change risk_score values.
11. Do NOT change summary, explanation, user_impact,
    recommendation, or evidence values.
12. Fix ONLY JSON syntax errors such as missing commas,
    missing colons, incorrect quotes, or unmatched brackets.
13. Do not use Markdown fences.
14. Do not include commentary outside the JSON object.
15. The expected input clause IDs are:
    {json.dumps(expected_ids, ensure_ascii=False)}

The original analysis request was:

--- ORIGINAL REQUEST ---
{original_user_prompt}
--- END ORIGINAL REQUEST ---

The malformed model response was:

--- MALFORMED RESPONSE ---
{raw_response}
--- END MALFORMED RESPONSE ---

Return the repaired JSON object now.
"""

    # ========================================================
    # CLAUSE ID REBINDING
    # ========================================================

    def _rebind_batch_clause_ids(
        self,
        analyses: List[ClauseAnalysis],
        batch: List[ClauseInput],
        batch_number: int,
        batch_start_index: int,
        assigned_clause_positions: set,
    ) -> List[ClauseAnalysis]:
        """
        Associate every returned analysis with one input clause
        occurrence.

        Gemini is instructed to preserve clause IDs, but an LLM can
        occasionally repeat an ID, return an ID from another batch,
        or omit an ID. The previous implementation tracked consumed
        clause IDs globally. That is unsafe when an ID is duplicated
        upstream or when Gemini repeats an earlier ID, because a valid
        current-batch occurrence could appear to be unavailable.

        This implementation tracks the physical input-clause position
        instead. Each input occurrence can therefore be consumed once,
        even when two occurrences share the same clause_id.

        Deterministic association order:

        1. Preserve a returned ID when it matches an unused occurrence
           in the current batch.
        2. If that ID is already consumed or unknown, keep the analysis
           pending.
        3. Rebind pending analyses, in their original response order,
           to the remaining unused input occurrences, also in input
           order.
        4. Never invent a new clause ID.
        5. Never associate more analyses than there are input clauses.

        No fuzzy matching, embeddings, semantic similarity, or model
        calls are used here.
        """

        if not analyses:
            return analyses

        # Keep occurrence-level information so duplicate clause IDs
        # are handled safely.
        expected_occurrences = [
            (
                batch_start_index + local_index,
                clause.clause_id,
            )
            for local_index, clause in enumerate(batch)
            if clause.clause_id
        ]

        if not expected_occurrences:
            return analyses

        normalized: List[ClauseAnalysis] = []
        pending: List[ClauseAnalysis] = []

        # ----------------------------------------------------
        # First pass:
        # Match returned IDs to an unused occurrence in the
        # current batch. Search in input order so the result is
        # deterministic.
        # ----------------------------------------------------
        used_local_positions = set()

        for analysis in analyses:
            returned_id = str(
                analysis.clause_id or ""
            ).strip()

            matching_occurrence = None

            for global_position, expected_id in expected_occurrences:
                if global_position in assigned_clause_positions:
                    continue

                if global_position in used_local_positions:
                    continue

                if returned_id == expected_id:
                    matching_occurrence = (
                        global_position,
                        expected_id,
                    )
                    break

            if matching_occurrence is None:
                pending.append(analysis)
                continue

            global_position, matched_id = (
                matching_occurrence
            )

            used_local_positions.add(
                global_position
            )
            assigned_clause_positions.add(
                global_position
            )

            normalized.append(
                analysis
            )

        # ----------------------------------------------------
        # Remaining input occurrences.
        # ----------------------------------------------------
        unused_occurrences = [
            (
                global_position,
                expected_id,
            )
            for global_position, expected_id
            in expected_occurrences
            if (
                global_position
                not in assigned_clause_positions
            )
            and (
                global_position
                not in used_local_positions
            )
        ]

        # ----------------------------------------------------
        # Rebind duplicate, cross-batch, unknown, or missing IDs.
        #
        # Response order is preserved for pending analyses and
        # input order is preserved for replacement occurrences.
        # ----------------------------------------------------
        for analysis, (
            replacement_position,
            replacement_id,
        ) in zip(
            pending,
            unused_occurrences,
        ):
            old_id = str(
                analysis.clause_id or ""
            ).strip()

            logger.warning(
                "Agent 3 repaired clause ID in batch %d: "
                "%s -> %s "
                "(input_position=%d)",
                batch_number,
                old_id or "<missing>",
                replacement_id,
                replacement_position,
            )

            repaired = replace(
                analysis,
                clause_id=replacement_id,
            )

            normalized.append(
                repaired
            )

            assigned_clause_positions.add(
                replacement_position
            )
            used_local_positions.add(
                replacement_position
            )

        # ----------------------------------------------------
        # If Gemini returned more analyses than the number of
        # input occurrences still available, the extras cannot
        # be safely associated with a clause and are dropped.
        # ----------------------------------------------------
        if len(pending) > len(unused_occurrences):
            logger.warning(
                "Agent 3 returned %d extra analyses in batch %d "
                "that could not be associated with input clauses.",
                len(pending) - len(unused_occurrences),
                batch_number,
            )

        # ----------------------------------------------------
        # Safety invariant:
        # Never return more analyses than the input batch size.
        # ----------------------------------------------------
        if len(normalized) > len(expected_occurrences):
            logger.warning(
                "Agent 3 batch %d produced %d analyses for "
                "%d input clause occurrences. Truncating extras.",
                batch_number,
                len(normalized),
                len(expected_occurrences),
            )
            normalized = normalized[
                :len(expected_occurrences)
            ]

        return normalized


    # ========================================================
    # SERIALIZATION
    # ========================================================

    def _serialize_clauses(
        self,
        clauses: List[ClauseInput],
    ) -> str:
        """
        Serialize clauses into JSON.
        """

        data = [
            clause.to_dict()
            for clause in clauses
        ]

        return json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )

    # ========================================================
    # LLM CALL
    # ========================================================

    def _call_llm(
        self,
        user_prompt: str,
        batch_number: int = 1,
        total_batches: int = 1,
        temperature_override: Optional[float] = None,
        max_tokens_override: Optional[int] = None,
    ) -> str:
        """
        Call the configured LLM.
        """

        try:
            generate_method = (
                self.llm_client.generate
            )

            try:
                signature = inspect.signature(
                    generate_method
                )

                accepts_model = (
                    "model"
                    in signature.parameters
                    or any(
                        parameter.kind
                        == inspect.Parameter.VAR_KEYWORD
                        for parameter
                        in signature.parameters.values()
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                accepts_model = True

            kwargs: dict[str, Any] = {
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": user_prompt,
                "temperature": (
                    temperature_override
                    if temperature_override is not None
                    else self.config.temperature
                ),
                "max_tokens": (
                    max_tokens_override
                    if max_tokens_override is not None
                    else self.config.max_tokens
                ),
            }

            if accepts_model:
                kwargs["model"] = (
                    self.config.model_name
                )

            response = generate_method(
                **kwargs
            )

        except Exception as exc:
            logger.exception(
                "Agent 3 LLM request failed."
            )

            raise RuntimeError(
                "Agent 3 failed to communicate "
                "with the LLM."
            ) from exc

        if response is None:
            raise RuntimeError(
                "Agent 3 LLM returned no response."
            )

        response_text = str(
            response
        ).strip()

        if not response_text:
            raise RuntimeError(
                "Agent 3 LLM returned an empty response."
            )

        return response_text

    # ========================================================
    # PARSING
    # ========================================================

    def _parse_analyses(
        self,
        raw_response: str,
    ) -> List[ClauseAnalysis]:
        """
        Parse an LLM JSON response.
        """

        parsed = parse_json_response(
            raw_response
        )

        if isinstance(
            parsed,
            dict,
        ):
            return convert_analyses(
                parsed
            )

        if isinstance(
            parsed,
            list,
        ):
            return convert_analyses(
                {
                    "analyses": parsed
                }
            )

        raise ValueError(
            "Agent 3 JSON response must be "
            "an object or an array."
        )

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    def _deduplicate_analyses(
        self,
        analyses: List[ClauseAnalysis],
    ) -> List[ClauseAnalysis]:
        """
        Remove duplicate clause IDs.
        """

        seen = set()

        result: List[
            ClauseAnalysis
        ] = []

        for analysis in analyses:
            clause_id = (
                analysis.clause_id
            )

            if clause_id in seen:
                logger.warning(
                    "Duplicate Agent 3 analysis "
                    "ignored: %s",
                    clause_id,
                )
                continue

            seen.add(
                clause_id
            )

            result.append(
                analysis
            )

        return result

    # ========================================================
    # AGENT 2 RISK PRESERVATION
    # ========================================================

    def _preserve_agent2_risk(
        self,
        analyses: List[ClauseAnalysis],
        clauses: List[ClauseInput],
    ) -> List[ClauseAnalysis]:
        """
        Replace any LLM-generated risk values with Agent 2's
        authoritative values.

        This is the final safety barrier preventing Agent 3
        from changing Agent 2's risk.
        """

        clause_map = {
            clause.clause_id: clause
            for clause in clauses
        }

        preserved: List[
            ClauseAnalysis
        ] = []

        for analysis in analyses:

            source_clause = (
                clause_map.get(
                    analysis.clause_id
                )
            )

            if source_clause is None:
                preserved.append(
                    analysis
                )
                continue

            # ------------------------------------------------
            # If Agent 2 supplied risk, ALWAYS use it.
            # ------------------------------------------------

            if (
                source_clause.risk_score
                is not None
                or source_clause.risk_level
                is not None
            ):

                score = (
                    normalize_agent2_risk_score(
                        source_clause.risk_score
                    )
                )

                level = (
                    normalize_agent2_risk_level(
                        source_clause.risk_level,
                        score,
                    )
                )

                if source_clause.category:
                    category = (
                        normalize_category(
                            source_clause.category
                        )
                    )
                else:
                    category = (
                        analysis.category
                    )

                preserved.append(
                    ClauseAnalysis(
                        clause_id=analysis.clause_id,
                        category=category,
                        risk_level=level,
                        risk_score=score,
                        summary=analysis.summary,
                        explanation=analysis.explanation,
                        user_impact=analysis.user_impact,
                        recommendation=analysis.recommendation,
                        evidence=analysis.evidence,
                    )
                )

            else:
                # Standalone Agent 3 behavior.
                preserved.append(
                    analysis
                )

        return preserved


__all__ = [
    "Agent3",
    "LLMClient",
]
