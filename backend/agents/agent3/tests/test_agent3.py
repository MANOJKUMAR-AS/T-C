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
