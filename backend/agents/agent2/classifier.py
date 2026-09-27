import re
from typing import Dict, List


CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "subscription": [
        "subscription",
        "subscriptions",
        "membership",
        "memberships",
        "recurring service",
        "recurring services",
        "recurring plan",
        "recurring plans",
    ],
    "auto_renewal": [
        "automatically renew",
        "automatically renewed",
        "auto-renew",
        "auto renew",
        "automatic renewal",
        "automatic renewals",
        "renew automatically",
        "renewed automatically",
    ],
    "cancellation": [
        "cancel",
        "cancellation",
        "cancellations",
        "cancelling",
        "cancelled",
        "canceled",
        "cancellation request",
        "cancellation requests",
    ],
    "payments": [
        "payment",
        "payments",
        "billing",
        "billings",
        "charge",
        "charges",
        "fee",
        "fees",
        "pay",
        "paid",
        "transaction",
        "transactions",
    ],
    "privacy": [
        "privacy",
        "privacy policy",
        "personal information",
        "personal data",
        "private information",
    ],
    "data_collection": [
        "collect",
        "collects",
        "collected",
        "collecting",
        "collection",
        "collections",
        "usage data",
        "device information",
        "information collected",
        "data collected",
        "gather information",
        "gather data",
        "obtain information",
        "obtain data",
    ],
    "data_sharing": [
        "share",
        "shares",
        "shared",
        "sharing",
        "third party",
        "third parties",
        "service provider",
        "service providers",
        "disclose",
        "discloses",
        "disclosed",
        "disclosure",
        "disclosures",
        "transfer to",
        "transferred to",
        "provide to third parties",
    ],
    "refund": [
        "refund",
        "refunds",
        "refunded",
        "refunding",
        "reimbursement",
        "reimbursements",
        "reimburse",
        "reimbursed",
        "reimbursement amount",
        "money back",
        "return of payment",
        "return the payment",
        "return payments",
    ],
    "intellectual_property": [
        "intellectual property",
        "copyright",
        "copyrights",
        "trademark",
        "trademarks",
        "trade mark",
        "trade marks",
    ],
    "license": [
        "license",
        "licenses",
        "licence",
        "licences",
        "licensed",
        "licensing",
    ],
    "liability": [
        "liability",
        "liabilities",
        "liable",
        "limitation of liability",
        "limit our liability",
        "limits our liability",
    ],
    "indemnification": [
        "indemnify",
        "indemnification",
        "indemnity",
        "indemnities",
    ],
    "arbitration": [
        "arbitration",
        "arbitrate",
        "arbitrator",
        "arbitrators",
    ],
    "termination": [
        "terminate",
        "terminated",
        "terminates",
        "termination",
        "terminations",
        "suspend",
        "suspended",
        "suspension",
        "suspensions",
    ],
    "tracking": [
        "cookies",
        "cookie",
        "tracking",
        "track users",
        "tracking technologies",
        "analytics",
        "web analytics",
    ],
    "security": [
        "security",
        "security measures",
        "security safeguards",
        "safeguards",
        "protect personal information",
        "protect personal data",
        "data security",
        "information security",
    ],
    "governing_law": [
        "governed by",
        "governed by the laws",
        "governing law",
        "laws of",
        "exclusive jurisdiction",
        "jurisdiction",
        "venue",
    ],
    "age_requirement": [
        "minors",
        "minor",
        "18 years of age",
        "under 18",
        "at least 18",
        "age of 18",
        "children under",
        "under the age of",
    ],
    "prohibited_use": [
        "prohibited",
        "restrictions",
        "expressly restricted",
        "prohibited use",
        "prohibited activities",
        "you must not",
        "you agree not to",
        "not permitted",
    ],
    "warranty": [
        "warranty",
        "warranties",
        "without warranty",
        "as is",
        "disclaim all warranties",
        "disclaims all warranties",
        "disclaimer of warranties",
    ],
}


def _normalize(text: str) -> str:
    if not text:
        return ""

    normalized = text.lower()
    normalized = normalized.replace("–", "-")
    normalized = normalized.replace("—", "-")
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    if not text or not phrase:
        return False

    phrase_normalized = _normalize(phrase)

    pattern = (
        r"(?<![a-z0-9])"
        + re.escape(phrase_normalized)
        + r"(?![a-z0-9])"
    )

    return re.search(pattern, text) is not None


def _has_any(text: str, phrases: List[str]) -> bool:
    return any(_contains_phrase(text, phrase) for phrase in phrases)


def _is_auto_renewal(text: str) -> bool:
    renewal_terms = [
        "renew",
        "renewal",
        "renewed",
        "renew automatically",
        "renewal date",
        "renewal period",
        "renewal term",
    ]

    automatic_terms = [
        "automatically",
        "automatic",
        "auto-renew",
        "auto renew",
        "recurring",
    ]

    return (
        _has_any(text, renewal_terms)
        and _has_any(text, automatic_terms)
    )


def _is_subscription(text: str) -> bool:
    """
    Subscription classification requires actual service/membership
    semantics.

    A bare occurrence of "subscription" is intentionally insufficient
    because financial/legal documents commonly use phrases such as
    "IPO subscription", "share subscription", or "investment subscription",
    which are payment/investment transactions rather than recurring
    service subscriptions.
    """

    # Strong service-subscription indicators.
    service_terms = [
        "service subscription",
        "service subscriptions",
        "subscription service",
        "subscription services",
        "subscription plan",
        "subscription plans",
        "subscription fee",
        "subscription fees",
        "subscription period",
        "subscription term",
        "subscription renewal",
        "subscription renewals",
        "subscription price",
        "subscription pricing",
        "monthly subscription",
        "annual subscription",
        "yearly subscription",
        "monthly membership",
        "annual membership",
        "membership plan",
        "membership plans",
        "membership fee",
        "membership fees",
    ]

    membership_terms = [
        "membership",
        "memberships",
    ]

    recurring_service_terms = [
        "recurring service",
        "recurring services",
        "recurring plan",
        "recurring plans",
        "recurring payment for service",
        "recurring payments for service",
    ]

    # A bare "subscription" can be accepted when the surrounding clause
    # clearly establishes service/customer-plan semantics.
    subscription_terms = [
        "subscription",
        "subscriptions",
    ]

    service_context_terms = [
        "service",
        "plan",
        "member",
        "membership",
        "customer",
        "monthly",
        "annual",
        "yearly",
        "recurring",
        "renewal",
        "renew",
        "fee",
        "price",
        "pricing",
        "billing",
    ]

    # Explicit financial/investment subscription contexts must not be
    # classified as a service subscription.
    investment_context_terms = [
        "ipo subscription",
        "ipo subscriptions",
        "share subscription",
        "share subscriptions",
        "shares subscription",
        "shares subscriptions",
        "investment subscription",
        "investment subscriptions",
        "securities subscription",
        "securities subscriptions",
        "public issue subscription",
        "public issue subscriptions",
        "issue subscription",
        "issue subscriptions",
        "asba subscription",
        "asba subscriptions",
    ]

    if _has_any(text, investment_context_terms):
        return False

    if _has_any(text, service_terms):
        return True

    if _has_any(text, membership_terms):
        return True

    if _has_any(text, recurring_service_terms):
        return True

    if _has_any(text, subscription_terms):
        return _has_any(text, service_context_terms)

    return False


def _is_cancellation(text: str) -> bool:
    cancellation_terms = [
        "cancel",
        "cancellation",
        "cancellations",
        "cancelling",
        "cancelled",
        "canceled",
        "cancellation request",
        "cancellation requests",
    ]

    return _has_any(text, cancellation_terms)


def _is_refund(text: str) -> bool:
    refund_terms = [
        "refund",
        "refunds",
        "refunded",
        "refunding",
        "reimbursement",
        "reimbursements",
        "reimburse",
        "reimbursed",
        "reimbursement amount",
        "money back",
        "return of payment",
        "return the payment",
        "return payments",
    ]

    return _has_any(text, refund_terms)


def _is_data_sharing(text: str) -> bool:
    sharing_action_terms = [
        "share",
        "shares",
        "shared",
        "sharing",
        "disclose",
        "discloses",
        "disclosed",
        "disclosure",
        "disclosures",
        "transfer to",
        "transferred to",
    ]

    recipient_terms = [
        "third party",
        "third parties",
        "service provider",
        "service providers",
        "partner",
        "partners",
        "affiliate",
        "affiliates",
        "vendor",
        "vendors",
        "authorities",
        "government",
    ]

    if not _has_any(text, sharing_action_terms):
        return False

    return _has_any(text, recipient_terms)


def _is_data_collection(text: str) -> bool:
    collection_action_terms = [
        "collect",
        "collects",
        "collected",
        "collecting",
        "collection",
        "collections",
        "gather information",
        "gather data",
        "obtain information",
        "obtain data",
    ]

    data_terms = [
        "information",
        "data",
        "personal information",
        "personal data",
        "device information",
        "usage data",
        "user information",
        "user data",
    ]

    return (
        _has_any(text, collection_action_terms)
        and _has_any(text, data_terms)
    )


def _is_payments(text: str) -> bool:
    payment_terms = [
        "payment",
        "payments",
        "billing",
        "charge",
        "charges",
        "fee",
        "fees",
        "pay",
        "paid",
        "transaction",
        "transactions",
    ]

    return _has_any(text, payment_terms)


def _is_policy_change(text: str) -> bool:
    """
    Detect clauses whose primary subject is amendment/update/revision
    of a policy, terms, agreement, or notice.

    This must take precedence over broad keyword categories such as
    data_collection when the clause merely mentions data practices as
    a reason for changing the policy.
    """
    policy_change_patterns = [
        r"\b(?:may|can|will|reserve\s+the\s+right\s+to)\s+"
        r"(?:change|modify|update|amend|revise|replace)\b.{0,220}"
        r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
        r"terms\s+and\s+conditions|terms\s+of\s+service|agreement|notice)\b",
        r"\b(?:change|changes|modify|modification|update|updates|"
        r"amend|amendment|amendments|revise|revision|revisions)\b.{0,160}"
        r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
        r"agreement|notice)\b",
        r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
        r"agreement|notice)\b.{0,160}"
        r"\b(?:from\s+time\s+to\s+time|periodically|occasionally)\b",
        r"\b(?:privacy\s+policy|privacy\s+notice|policy|terms|"
        r"agreement|notice)\b.{0,180}"
        r"\b(?:reflect|reflecting)\s+(?:changes|updates|revisions)\b",
    ]

    return any(
        re.search(pattern, text, re.I)
        for pattern in policy_change_patterns
    )


def _is_age_requirement(text: str) -> bool:
    age_terms = [
        "minor",
        "minors",
        "18 years of age",
        "under 18",
        "at least 18",
        "age of 18",
        "children under",
        "under the age of",
        "age requirement",
        "minimum age",
    ]
    return _has_any(text, age_terms)


def _is_genuine_governing_law(text: str) -> bool:
    genuine_governing_law_patterns = [
        r"\bgoverned\s+by\b",
        r"\bgoverned\s+in\s+accordance\s+with\b",
        r"\bgoverning\s+law\b",
        r"\blaws\s+of\b",
        r"\blaw\s+of\b",
        r"\bjurisdiction\b",
        r"\bexclusive\s+jurisdiction\b",
        r"\bcourts?\s+(?:of|in|at)\b",
        r"\bvenue\b",
        r"\bdispute\s+resolution\b",
        r"\bproper\s+law\b",
    ]
    return any(re.search(p, text, re.I) for p in genuine_governing_law_patterns)


def suggest_category(text: str) -> str:
    """
    Suggest a category for a legal/policy clause.

    Specific semantic categories are evaluated before broad categories.
    """

    normalized = _normalize(text)

    if not normalized:
        return "other"

    # Policy-amendment clauses are about changing the policy/terms
    # themselves. They may mention data collection, payments, or other
    # subjects as reasons for the change, but those mentions do not make
    # the amendment clause a substantive clause about that subject.
    if _is_policy_change(normalized):
        return "other"

    # Highly specific categories first.
    if _is_auto_renewal(normalized):
        return "auto_renewal"

    if _is_refund(normalized):
        return "refund"

    if _is_age_requirement(normalized):
        return "age_requirement"

    if _is_data_sharing(normalized):
        return "data_sharing"

    if _is_data_collection(normalized):
        return "data_collection"

    if _is_subscription(normalized):
        return "subscription"

    if _is_cancellation(normalized):
        return "cancellation"

    # Other legal categories.
    if _has_any(normalized, CATEGORY_KEYWORDS["arbitration"]):
        return "arbitration"

    if _has_any(normalized, CATEGORY_KEYWORDS["indemnification"]):
        return "indemnification"

    if _is_genuine_governing_law(normalized):
        return "governing_law"

    if _has_any(normalized, CATEGORY_KEYWORDS["intellectual_property"]):
        return "intellectual_property"

    if _has_any(normalized, CATEGORY_KEYWORDS["prohibited_use"]):
        return "prohibited_use"

    if _has_any(normalized, CATEGORY_KEYWORDS["license"]):
        return "license"

    if _has_any(normalized, CATEGORY_KEYWORDS["liability"]):
        return "liability"

    if _has_any(normalized, CATEGORY_KEYWORDS["warranty"]):
        return "warranty"

    if _has_any(normalized, CATEGORY_KEYWORDS["termination"]):
        return "termination"

    if _has_any(normalized, CATEGORY_KEYWORDS["tracking"]):
        return "tracking"

    if _has_any(normalized, CATEGORY_KEYWORDS["security"]):
        return "security"

    if _has_any(normalized, CATEGORY_KEYWORDS["privacy"]):
        return "privacy"

    # Broad financial category last.
    if _is_payments(normalized):
        return "payments"

    return "other"