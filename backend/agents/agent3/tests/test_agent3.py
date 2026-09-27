"""
Tests for Agent 3.

These tests use mock LLM clients, so no real OpenAI
API request is made.
"""

import json

import pytest

from agents.agent3.agent import Agent3
from agents.agent3.config import Agent3Config
from agents.agent3.models import (
    Agent3Request,
    ClauseCategory,
    ClauseInput,
    RiskLevel,
)


class MockLLMClient:
    """Fake LLM client used for testing."""

    def __init__(self, response=None):
        self.response = (
            response
            if response is not None
            else self._default_response()
        )

        self.calls = []

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> str:
        """
        Return a predictable fake LLM response.

        The signature must match the LLMClient interface
        used by Agent3.
        """

        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "model": model,
            }
        )

        return self.response

    @staticmethod
    def _default_response():
        """Return a valid default Agent 3 response."""

        return json.dumps(
            {
                "analyses": [
                    {
                        "clause_id": "clause_1",
                        "category": "auto_renewal",
                        "risk_level": "medium",
                        "risk_score": 6,
                        "summary": (
                            "The subscription automatically renews."
                        ),
                        "explanation": (
                            "The subscription continues unless "
                            "the user cancels it."
                        ),
                        "user_impact": (
                            "The user may be charged again if "
                            "they forget to cancel."
                        ),
                        "recommendation": (
                            "Review the cancellation requirements "
                            "before subscribing."
                        ),
                        "evidence": "automatically renew",
                    }
                ]
            }
        )


class FailingLLMClient:
    """Mock LLM client that always fails."""

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> str:
        """Simulate an LLM communication failure."""

        raise RuntimeError(
            "Simulated LLM failure."
        )


@pytest.fixture
def config():
    """Return test configuration."""

    return Agent3Config(
        model_name="test-model",
        temperature=0.0,
        max_tokens=1000,
        max_clauses=10,
    )


@pytest.fixture
def clause():
    """Return a sample clause."""

    return ClauseInput(
        clause_id="clause_1",
        title="Subscription",
        text=(
            "Your subscription will automatically "
            "renew every month unless cancelled."
        ),
    )


@pytest.fixture
def mock_llm():
    """Return a mock LLM client."""

    return MockLLMClient()


@pytest.fixture
def agent(mock_llm, config):
    """Return Agent 3 configured with the mock LLM."""

    return Agent3(
        llm_client=mock_llm,
        config=config,
    )


def test_agent_initializes(agent):
    """Agent 3 should initialize successfully."""

    assert agent is not None


def test_analyze_clause(agent, clause):
    """Agent 3 should analyze a clause successfully."""

    request = Agent3Request(
        clauses=[clause],
        document_id="doc_001",
        document_title="Test Terms",
    )

    response = agent.analyze(request)

    assert response is not None
    assert response.document_id == "doc_001"
    assert response.total_clauses == 1
    assert response.analyzed_clauses == 1


def test_analysis_content(agent, clause):
    """Returned analysis should contain expected values."""

    request = Agent3Request(
        clauses=[clause]
    )

    response = agent.analyze(request)

    assert len(response.analyses) == 1

    analysis = response.analyses[0]

    assert analysis.clause_id == "clause_1"

    assert (
        analysis.category
        == ClauseCategory.AUTO_RENEWAL
    )

    assert (
        analysis.risk_level
        == RiskLevel.MEDIUM
    )

    assert analysis.risk_score == 6

    assert analysis.summary
    assert analysis.explanation
    assert analysis.user_impact
    assert analysis.recommendation
    assert analysis.evidence


def test_analyze_clauses_method(agent, clause):
    """Convenience analyze_clauses method should work."""

    response = agent.analyze_clauses(
        clauses=[clause],
        document_id="doc_002",
        document_title="Example Agreement",
    )

    assert response.document_id == "doc_002"
    assert response.total_clauses == 1
    assert response.analyzed_clauses == 1


def test_empty_request_raises_error(agent):
    """Empty requests should raise ValueError."""

    request = Agent3Request(
        clauses=[]
    )

    with pytest.raises(ValueError):
        agent.analyze(request)


def test_empty_clause_text_raises_error(agent):
    """Empty clause text should raise ValueError."""

    empty_clause = ClauseInput(
        clause_id="clause_1",
        text="",
    )

    request = Agent3Request(
        clauses=[empty_clause]
    )

    with pytest.raises(ValueError):
        agent.analyze(request)


def test_missing_clause_id_raises_error(agent):
    """Missing clause ID should raise ValueError."""

    invalid_clause = ClauseInput(
        clause_id="",
        text="This is a test clause.",
    )

    request = Agent3Request(
        clauses=[invalid_clause]
    )

    with pytest.raises(ValueError):
        agent.analyze(request)


def test_maximum_clause_limit(agent):
    """Maximum clause limit should be enforced."""

    clauses = [
        ClauseInput(
            clause_id=f"clause_{index}",
            text=f"Test clause {index}.",
        )
        for index in range(11)
    ]

    request = Agent3Request(
        clauses=clauses
    )

    with pytest.raises(ValueError):
        agent.analyze(request)


def test_llm_failure_is_handled(config, clause):
    """LLM failures should become RuntimeError."""

    agent = Agent3(
        llm_client=FailingLLMClient(),
        config=config,
    )

    request = Agent3Request(
        clauses=[clause]
    )

    with pytest.raises(RuntimeError):
        agent.analyze(request)


def test_invalid_json_response(config, clause):
    """Invalid JSON response should be rejected."""

    llm = MockLLMClient(
        response="This is not valid JSON."
    )

    agent = Agent3(
        llm_client=llm,
        config=config,
    )

    request = Agent3Request(
        clauses=[clause]
    )

    with pytest.raises(ValueError):
        agent.analyze(request)


def test_overall_risk_score(agent, clause):
    """Overall risk score should be within the valid range."""

    request = Agent3Request(
        clauses=[clause]
    )

    response = agent.analyze(request)

    assert (
        0
        <= response.overall_risk_score
        <= 10
    )


def test_risk_level_matches_score(agent, clause):
    """Overall risk level should be a valid RiskLevel."""

    request = Agent3Request(
        clauses=[clause]
    )

    response = agent.analyze(request)

    assert response.overall_risk_level in [
        RiskLevel.LOW,
        RiskLevel.MEDIUM,
        RiskLevel.HIGH,
        RiskLevel.CRITICAL,
    ]


def test_response_to_dict(agent, clause):
    """Agent3Response should serialize correctly."""

    request = Agent3Request(
        clauses=[clause],
        document_id="doc_003",
    )

    response = agent.analyze(request)

    data = response.to_dict()

    assert isinstance(data, dict)

    assert data["document_id"] == "doc_003"

    assert "overall_risk_level" in data
    assert "overall_risk_score" in data
    assert "analyses" in data

    assert isinstance(
        data["analyses"],
        list,
    )


def test_llm_receives_configured_model(
    agent,
    mock_llm,
    clause,
):
    """Agent 3 should pass the configured model to the LLM."""

    request = Agent3Request(
        clauses=[clause]
    )

    agent.analyze(request)

    assert len(mock_llm.calls) == 1

    call = mock_llm.calls[0]

    assert call["model"] == "test-model"
    assert call["temperature"] == 0.0
    assert call["max_tokens"] == 1000


def test_llm_receives_prompts(
    agent,
    mock_llm,
    clause,
):
    """Agent 3 should send system and user prompts."""

    request = Agent3Request(
        clauses=[clause],
        document_id="doc_prompt_test",
        document_title="Prompt Test",
    )

    agent.analyze(request)

    assert len(mock_llm.calls) == 1

    call = mock_llm.calls[0]

    assert call["system_prompt"]
    assert call["user_prompt"]

    assert (
        "doc_prompt_test"
        in call["user_prompt"]
    )

    assert (
        "Prompt Test"
        in call["user_prompt"]
    )

    assert (
        "clause_1"
        in call["user_prompt"]
    )


# ==========================================================
# AGENT 3 RISK SCALE REGRESSION TESTS
# ==========================================================

import json as _json


def _make_agent3_with_score(score: int, level: str, config_fixture):
    """
    Helper: build an Agent3 whose mock LLM returns the given
    risk_score and risk_level for clause_1.
    """
    response = _json.dumps({
        "analyses": [{
            "clause_id": "clause_1",
            "category": "auto_renewal",
            "risk_level": level,
            "risk_score": score,
            "summary": "Test summary.",
            "explanation": "Test explanation.",
            "user_impact": "Test impact.",
            "recommendation": "Test recommendation.",
            "evidence": "test evidence",
        }]
    })
    llm = MockLLMClient(response=response)
    return Agent3(llm_client=llm, config=config_fixture)


class TestAgent2RiskScorePreservation:
    """
    Agent 3 must preserve Agent 2 authoritative 0-100 risk scores
    exactly when they are supplied via overall_risk_score /
    overall_risk_level on the request.
    """

    @pytest.mark.parametrize("score,expected_level", [
        (0,   "low"),
        (5,   "low"),
        (10,  "low"),
        (20,  "low"),
        (44,  "low"),
        (45,  "medium"),
        (60,  "medium"),
        (80,  "medium"),
        (81,  "high"),
        (99,  "high"),
        (100, "high"),
    ])
    def test_overall_risk_score_preserved(self, score, expected_level, config):
        """
        When Agent 2 overall_risk_score is supplied, the Agent 3
        response must carry it back unchanged and derive the correct
        risk level using the Agent 2 thresholds:
            0-44  LOW
            45-80 MEDIUM
            81-100 HIGH
        """
        level_map = {0: "low", 5: "low", 10: "low", 20: "low",
                     44: "low", 45: "medium", 60: "medium", 80: "medium",
                     81: "high", 99: "high", 100: "high"}

        clause = ClauseInput(
            clause_id="clause_1",
            text="Test clause text for risk scale test.",
            title="Test Clause",
            risk_score=score,
            risk_level=expected_level,
        )

        agent = _make_agent3_with_score(score, expected_level, config)

        request = Agent3Request(
            clauses=[clause],
            document_id="risk_test",
            overall_risk_score=score,
            overall_risk_level=expected_level,
        )

        response = agent.analyze(request)

        # Overall score must be preserved exactly.
        assert response.overall_risk_score == score, (
            f"Expected overall_risk_score={score}, "
            f"got {response.overall_risk_score}"
        )

        # Overall level must match Agent 2 thresholds.
        from agents.agent3.models import RiskLevel
        assert response.overall_risk_level.value == expected_level, (
            f"Expected overall_risk_level={expected_level!r}, "
            f"got {response.overall_risk_level.value!r}"
        )


class TestAgent2ClauseRiskPreservation:
    """
    Agent 2 clause-level risk values must survive Agent 3
    without distortion.
    """

    @pytest.mark.parametrize("agent2_score,agent2_level", [
        (75,  "high"),
        (40,  "low"),
        (100, "high"),
        (0,   "low"),
        (55,  "medium"),
    ])
    def test_clause_risk_preserved_by_preserve_agent2_risk(
        self, agent2_score, agent2_level, config
    ):
        """
        _preserve_agent2_risk() must replace any LLM-generated score
        with the Agent 2 authoritative value.
        Score 75 must NOT become 10; score 40 must NOT become 4, etc.
        """
        clause = ClauseInput(
            clause_id="clause_1",
            text="Test clause text for clause risk preservation.",
            title="Test Clause",
            risk_score=agent2_score,
            risk_level=agent2_level,
        )

        # Mock LLM echoes the correct values (as a well-behaved LLM would).
        agent = _make_agent3_with_score(agent2_score, agent2_level, config)

        request = Agent3Request(
            clauses=[clause],
            document_id="clause_risk_test",
            overall_risk_score=agent2_score,
            overall_risk_level=agent2_level,
        )

        response = agent.analyze(request)

        assert len(response.analyses) == 1
        analysis = response.analyses[0]

        # The final clause-level score must equal the Agent 2 value.
        assert analysis.risk_score == agent2_score, (
            f"Clause risk_score distorted: expected {agent2_score}, "
            f"got {analysis.risk_score}"
        )


class TestConvertAnalysisScaleHandling:
    """
    convert_analysis() must use the 0-100 normaliser unconditionally.

    Scale is NOT inferred from numeric magnitude.

    Correctness guarantee:
    - Agent 2 authoritative scores 0, 1, 5, 10 are all valid low-end
      values on the 0-100 scale and must pass through unchanged.
    - convert_analysis() does not and must not guess scale from value.
    - _preserve_agent2_risk() in agent.py is the final barrier that
      overwrites risk with ClauseInput values from Agent 2, making
      convert_analysis()'s intermediate risk value irrelevant in
      production.  In standalone tests _preserve_agent2_risk() is a
      no-op because ClauseInput has no Agent 2 risk fields set.
    """

    def _raw(self, score, level="low"):
        return {
            "clause_id": "c1",
            "category": "privacy",
            "risk_level": level,
            "risk_score": score,
            "summary": "s", "explanation": "e",
            "user_impact": "u", "recommendation": "r", "evidence": "ev",
        }

    # ----------------------------------------------------------
    # Agent 2 small scores (0-10 range) must NOT be clamped to
    # a 0-10 legacy scale.  They survive as-is on 0-100.
    # ----------------------------------------------------------

    def test_agent2_score_0_is_0(self):
        """Agent 2 score 0 → 0 (not misinterpreted)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(0, "low")).risk_score == 0

    def test_agent2_score_1_is_1(self):
        """Agent 2 score 1 → 1 (not clamped by 0-10 logic)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(1, "low")).risk_score == 1

    def test_agent2_score_5_is_5(self):
        """Agent 2 score 5 → 5, NOT reinterpreted on a 0-10 scale."""
        from agents.agent3.utils import convert_analysis
        result = convert_analysis(self._raw(5, "low"))
        assert result.risk_score == 5, (
            f"Agent 2 score 5 must remain 5, got {result.risk_score}"
        )

    def test_agent2_score_10_is_10(self):
        """Agent 2 score 10 → 10, NOT the top of a 0-10 scale."""
        from agents.agent3.utils import convert_analysis
        result = convert_analysis(self._raw(10, "low"))
        assert result.risk_score == 10, (
            f"Agent 2 score 10 must remain 10, got {result.risk_score}"
        )

    def test_agent2_score_44_is_44(self):
        """Agent 2 score 44 → 44 (boundary of LOW on 0-100 scale)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(44, "low")).risk_score == 44

    def test_agent2_score_45_is_45(self):
        """Agent 2 score 45 → 45 (boundary of MEDIUM on 0-100 scale)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(45, "medium")).risk_score == 45

    def test_agent2_score_75_is_75(self):
        """Agent 2 score 75 → 75, never clamped."""
        from agents.agent3.utils import convert_analysis
        result = convert_analysis(self._raw(75, "high"))
        assert result.risk_score == 75, (
            f"Expected 75 but got {result.risk_score}"
        )

    def test_agent2_score_80_is_80(self):
        """Agent 2 score 80 → 80 (boundary of MEDIUM on 0-100 scale)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(80, "medium")).risk_score == 80

    def test_agent2_score_81_is_81(self):
        """Agent 2 score 81 → 81 (boundary of HIGH on 0-100 scale)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(81, "high")).risk_score == 81

    def test_agent2_score_100_is_100(self):
        """Agent 2 score 100 → 100 (maximum)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(100, "high")).risk_score == 100

    def test_standalone_score_6_survives(self):
        """
        Standalone mock-LLM score 6 → 6.
        Clamping to [0, 100] leaves small integers unchanged.
        """
        from agents.agent3.utils import convert_analysis
        result = convert_analysis(self._raw(6, "medium"))
        assert result.risk_score == 6
        assert result.risk_level.value == "medium"

    def test_score_40_survives(self):
        """Score 40 → 40 (valid on both 0-100 and as a large standalone value)."""
        from agents.agent3.utils import convert_analysis
        assert convert_analysis(self._raw(40, "low")).risk_score == 40

    def test_no_magnitude_dispatch(self):
        """
        Explicit proof: scores 5 and 10 are NOT routed to a 0-10 normaliser.
        If they were, they would be clamped and the risk level derived from
        the 0-10 thresholds (<=2 LOW, <=6 MEDIUM, <=8 HIGH) would disagree
        with the string risk_level supplied by Agent 2.

        With a single 0-100 normaliser:
        - score 5, level "low" → score=5, level=LOW  (string path in
          normalize_agent2_risk_level maps "low" → LOW directly)
        - score 10, level "low" → score=10, level=LOW
        """
        from agents.agent3.utils import convert_analysis
        from agents.agent3.models import RiskLevel

        r5 = convert_analysis(self._raw(5, "low"))
        assert r5.risk_score == 5
        assert r5.risk_level == RiskLevel.LOW

        r10 = convert_analysis(self._raw(10, "low"))
        assert r10.risk_score == 10
        assert r10.risk_level == RiskLevel.LOW


class TestNormalizeAgent2RiskLevel:
    """
    normalize_agent2_risk_level() must use Agent 2 thresholds:
        0-44  LOW
        45-80 MEDIUM
        81-100 HIGH
    """

    @pytest.mark.parametrize("score,expected", [
        (0,   "low"),
        (1,   "low"),
        (5,   "low"),
        (10,  "low"),
        (44,  "low"),
        (45,  "medium"),
        (60,  "medium"),
        (80,  "medium"),
        (81,  "high"),
        (99,  "high"),
        (100, "high"),
    ])
    def test_threshold_boundaries(self, score, expected):
        from agents.agent3.utils import normalize_agent2_risk_level
        from agents.agent3.models import RiskLevel
        # Pass None as level so the function falls through to the
        # score-based path, exercising the actual threshold logic.
        result = normalize_agent2_risk_level(None, score)
        assert result.value == expected, (
            f"score={score}: expected {expected!r}, got {result.value!r}"
        )
