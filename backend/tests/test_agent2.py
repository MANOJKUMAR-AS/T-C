from agents.agent2.classifier import suggest_category
from agents.agent2.schemas import ClauseAnalysis, DocumentAnalysis


def test_category_detection():
    text = """
    We may automatically renew your subscription
    unless you cancel before the renewal date.
    """

    category = suggest_category(text)

    assert category in {
        "subscription",
        "auto_renewal",
        "cancellation",
    }


def test_clause_schema():
    clause = ClauseAnalysis(
        clause_id="clause_001",
        title="Automatic Renewal",
        category="auto_renewal",
        summary="The subscription renews automatically.",
        explanation="Users may be charged again unless they cancel.",
        obligations=[],
        permissions=[],
        restrictions=["Cancellation may be required before renewal."],
        consequences=["Another subscription charge may occur."],
        risk_level="medium",
        risk_reason="Automatic charges may occur.",
        source_text="Your subscription automatically renews.",
    )

    assert clause.clause_id == "clause_001"
    assert clause.risk_level == "medium"


def test_document_schema():
    document = DocumentAnalysis(
        document_type="terms_and_conditions",
        overall_risk="medium",
        key_findings=[
            "The subscription automatically renews."
        ],
        clauses=[],
    )

    assert document.document_type == "terms_and_conditions"
    assert len(document.key_findings) == 1