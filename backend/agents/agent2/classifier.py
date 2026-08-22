from typing import Dict, List


CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "subscription": [
        "subscription",
        "recurring",
        "membership",
    ],
    "auto_renewal": [
        "automatically renew",
        "auto-renew",
        "auto renew",
        "automatic renewal",
    ],
    "cancellation": [
        "cancel",
        "cancellation",
    ],
    "payments": [
        "payment",
        "billing",
        "charge",
        "fee",
    ],
    "privacy": [
        "privacy",
        "personal information",
        "personal data",
    ],
    "data_collection": [
        "collect",
        "collection",
        "usage data",
        "device information",
    ],
    "data_sharing": [
        "share",
        "third party",
        "third parties",
        "service providers",
        "disclose",
    ],
    "refund": [
        "refund",
        "reimbursement",
    ],
    "intellectual_property": [
        "intellectual property",
        "copyright",
        "trademark",
    ],
    "license": [
        "license",
        "licence",
    ],
    "liability": [
        "liability",
        "liable",
    ],
    "indemnification": [
        "indemnify",
        "indemnification",
    ],
    "arbitration": [
        "arbitration",
        "arbitrate",
    ],
    "termination": [
        "terminate",
        "termination",
        "suspend",
        "suspension",
    ],
    "tracking": [
        "cookies",
        "tracking",
        "analytics",
    ],
    "security": [
        "security",
        "security measures",
    ],
}


def suggest_category(text: str) -> str:
    """
    Suggest a clause category using keyword matching.
    """

    if not text or not text.strip():
        return "other"

    normalized = text.lower()

    priority_categories = [
        "auto_renewal",
        "data_sharing",
        "data_collection",
        "subscription",
        "cancellation",
        "refund",
        "payments",
        "privacy",
        "arbitration",
        "indemnification",
        "termination",
        "tracking",
        "security",
        "intellectual_property",
        "license",
        "liability",
    ]

    for category in priority_categories:
        keywords = CATEGORY_KEYWORDS.get(category, [])

        if any(keyword in normalized for keyword in keywords):
            return category

    return "other"
