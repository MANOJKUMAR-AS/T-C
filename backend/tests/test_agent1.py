"""
Authoritative unit and regression tests for Agent 1 (PolicyExtractionAgent).
"""

import pytest
from agents.agent1.policy_extraction import PolicyExtractionAgent


@pytest.fixture
def agent():
    return PolicyExtractionAgent()


def test_agent1_initialization(agent):
    assert agent is not None
    assert agent.name == "Policy Extraction Agent"
    assert agent.MIN_POLICY_CHARS == 500


def test_normalize_candidate_relative_url(agent):
    item = {
        "url": "/terms-and-conditions",
        "type": "terms",
        "content": "A" * 600,
    }
    normalized = agent._normalize_candidate(item, "https://example.com/page")
    assert normalized is not None
    assert normalized["url"] == "https://example.com/terms-and-conditions"
    assert normalized["type"] == "terms"


def test_browser_documents_fast_path_valid(agent):
    browser_docs = [
        {
            "url": "https://example.com/terms",
            "type": "terms",
            "content": (
                "These Terms and Conditions govern your use of our service. "
                "By using this site you agree to these terms of use. "
                "Limitation of liability and governing law shall apply to all accounts. "
                + "User agrees to abide by all applicable rules and conditions. " * 20
            ),
        }
    ]

    result = agent.run(
        url="https://example.com",
        browser_documents=browser_docs,
    )

    assert result["status"] == "complete"
    assert result["policy_count"] >= 1
    assert len(result["documents"]) >= 1
    doc = result["documents"][0]
    assert doc["url"] == "https://example.com/terms"
    assert doc["type"] == "terms"
    assert doc["extraction_method"] == "browser"


def test_browser_documents_rejection_of_shell_page(agent):
    browser_docs = [
        {
            "url": "https://example.com/terms",
            "type": "terms",
            "content": (
                "By continuing past this page, you agree to our terms of service, "
                "cookie policy, privacy policy and content policies."
            ),
        }
    ]

    # Shell text should be rejected by _is_generic_policy_shell
    normalized = agent._normalize_candidate(browser_docs[0], "https://example.com")
    assert not agent._is_real_policy_document(normalized)


def test_pdf_url_detection(agent):
    assert agent._is_pdf_url("https://example.com/legal/policy.pdf")
    assert agent._is_pdf_url("https://example.com/docs/terms.pdf/")
    assert not agent._is_pdf_url("https://example.com/terms")


def test_is_obvious_non_policy_route(agent):
    assert agent._is_obvious_non_policy_route("https://example.com/discussions/post/123")
    assert agent._is_obvious_non_policy_route("https://example.com/profile/johndoe")
    assert agent._is_obvious_non_policy_route("https://example.com/cart")
    assert not agent._is_obvious_non_policy_route("https://example.com/terms-and-conditions")
    assert not agent._is_obvious_non_policy_route("https://example.com/privacy-policy")


def test_deduplicate_candidates(agent):
    candidates = [
        {"url": "https://example.com/terms", "type": "terms"},
        {"url": "https://example.com/terms/", "type": "terms"},
        {"url": "https://example.com/privacy", "type": "privacy"},
    ]
    deduped = agent._deduplicate_candidates(candidates)
    assert len(deduped) == 2
    urls = [c["url"] for c in deduped]
    assert "https://example.com/terms" in urls
    assert "https://example.com/privacy" in urls