from __future__ import annotations

import re
from typing import Any, Dict, Iterable


# ============================================================
# COMPREHENSIVE TERMS & CONDITIONS RISK TAXONOMY
# ============================================================
#
# IMPORTANT:
# A clause existing does NOT automatically mean it is risky.
#
# Example:
#   "This agreement is governed by the laws of X."
#
# is a legal clause, but not necessarily a high-risk clause.
#
# The weights below represent potential USER IMPACT.
# They are intentionally conservative.
#
# Final score:
#   0-29   LOW
#   30-59  MEDIUM
#   60-79  HIGH
#   80-100 CRITICAL
# ============================================================


WEIGHTS = {

    # ========================================================
    # PRIVACY / PERSONAL DATA
    # ========================================================

    "personal_data_collection": 10,
    "extensive_data_collection": 15,
    "sensitive_personal_data": 20,
    "financial_data_collection": 20,
    "health_data_collection": 25,
    "biometric_data_collection": 25,
    "precise_location_collection": 20,
    "contact_data_collection": 10,
    "identity_data_collection": 10,
    "device_information_collection": 10,
    "browsing_history_collection": 15,
    "online_activity_collection": 10,
    "inferred_data_collection": 15,
    "children_data_collection": 20,
    "employee_data_collection": 10,

    # ========================================================
    # TRACKING
    # ========================================================

    "cookie_tracking": 10,
    "analytics_tracking": 10,
    "behavioral_tracking": 20,
    "cross_site_tracking": 20,
    "cross_service_tracking": 15,
    "device_fingerprinting": 20,
    "advertising_identifier_tracking": 15,
    "location_tracking": 20,
    "session_recording": 15,
    "interaction_tracking": 15,

    # ========================================================
    # ADVERTISING
    # ========================================================

    "advertising_targeting": 15,
    "personalized_advertising": 15,
    "interest_based_advertising": 15,
    "behavioral_advertising": 20,
    "third_party_advertising": 15,
    "advertising_partner_sharing": 15,

    # ========================================================
    # DATA SHARING / DISCLOSURE
    # ========================================================

    "third_party_data_sharing": 15,
    "service_provider_data_sharing": 10,
    "business_partner_sharing": 15,
    "affiliate_data_sharing": 10,
    "advertising_partner_data_sharing": 15,
    "data_sale": 25,
    "government_disclosure": 10,
    "law_enforcement_disclosure": 10,
    "legal_process_disclosure": 10,

    # ========================================================
    # DATA RETENTION / DELETION
    # ========================================================

    "data_retention": 10,
    "long_term_data_retention": 15,
    "indefinite_data_retention": 20,
    "deletion_limitations": 15,
    "account_deletion_limitations": 15,
    "post_account_retention": 15,
    "backup_retention": 10,

    # ========================================================
    # CONSENT / USER CONTROL
    # ========================================================

    "unfriendly_consent_or_opt_out": 15,
    "forced_consent": 20,
    "limited_opt_out": 15,
    "withdrawal_of_consent_limitations": 15,
    "continued_use_consent": 15,
    "cookie_control_limitations": 10,
    "consent_for_data_processing": 5,
    "consent_for_marketing": 10,

    # ========================================================
    # AUTOMATED PROCESSING
    # ========================================================

    "automated_decision_making": 15,
    "profiling": 15,
    "automated_profiling": 20,
    "algorithmic_personalization": 10,
    "recommendation_profiling": 10,

    # ========================================================
    # COMMUNICATION MONITORING
    # ========================================================

    "communication_monitoring": 20,
    "message_monitoring": 20,
    "call_monitoring": 20,
    "content_monitoring": 15,

    # ========================================================
    # SECURITY
    # ========================================================

    "security_disclaimer": 10,
    "no_guarantee_of_security": 10,
    "breach_disclaimer": 15,
    "security_incident_disclosure": 10,
    "user_security_obligation": 5,
    "account_security_obligation": 5,

    # ========================================================
    # ACCOUNT / ACCESS
    # ========================================================

    "account_termination": 10,
    "account_suspension": 10,
    "unilateral_termination": 15,
    "unilateral_suspension": 15,
    "access_restriction": 10,
    "account_lockout": 10,
    "account_deletion_by_provider": 15,
    "termination_without_notice": 15,

    # ========================================================
    # ELIGIBILITY / AGE
    # ========================================================

    "age_restriction": 5,
    "eligibility_restriction": 5,
    "parental_responsibility": 5,

    # ========================================================
    # ACCEPTABLE USE / USER CONDUCT
    # ========================================================

    "prohibited_use": 5,
    "unauthorized_access_restriction": 5,
    "reverse_engineering_restriction": 10,
    "scraping_restriction": 10,
    "automated_access_restriction": 10,
    "circumvention_restriction": 10,
    "commercial_use_restriction": 10,
    "redistribution_restriction": 10,
    "impersonation_restriction": 5,
    "illegal_activity_restriction": 5,
    "abuse_restriction": 5,

    # ========================================================
    # PAYMENTS
    # ========================================================

    "payment_obligation": 10,
    "payment_authorization": 10,
    "automatic_billing": 15,
    "recurring_billing": 15,
    "renewal_without_clear_notice": 20,
    "free_trial_conversion": 20,
    "price_change": 15,
    "fee_change": 15,
    "late_payment_consequences": 10,
    "payment_failure_consequences": 10,
    "currency_conversion_cost": 10,
    "tax_obligation": 5,

    # ========================================================
    # CANCELLATION / REFUND
    # ========================================================

    "cancellation_restriction": 15,
    "refund_limitation": 15,
    "non_refundable_payment": 15,
    "restocking_fee": 10,
    "return_shipping_cost": 10,
    "refund_delay": 10,
    "store_credit_instead_of_refund": 10,
    "cancellation_fee": 15,
    "return_condition_restriction": 10,

    # ========================================================
    # E-COMMERCE / DELIVERY
    # ========================================================

    "delivery_disclaimer": 10,
    "shipping_delay": 10,
    "risk_of_loss": 15,
    "delivery_estimate_disclaimer": 10,
    "order_cancellation_by_seller": 15,
    "order_rejection_right": 10,
    "inventory_availability_disclaimer": 10,
    "pricing_error_cancellation": 10,
    "product_description_disclaimer": 10,
    "warranty_limitation": 10,
    "guarantee_limitation": 10,

    # ========================================================
    # LIABILITY / WARRANTIES
    # ========================================================

    "liability_limitation": 15,
    "consequential_damage_exclusion": 15,
    "damage_cap": 20,
    "loss_exclusion": 15,
    "warranty_disclaimer": 10,
    "service_availability_disclaimer": 10,
    "content_disclaimer": 10,
    "third_party_content_disclaimer": 10,
    "accuracy_disclaimer": 10,
    "professional_advice_disclaimer": 10,
    "no_guarantee_clause": 10,

    # ========================================================
    # INDEMNIFICATION
    # ========================================================

    "indemnification": 20,
    "broad_indemnification": 25,
    "defense_obligation": 20,

    # ========================================================
    # DISPUTES / LEGAL RIGHTS
    # ========================================================

    "mandatory_arbitration": 20,
    "class_action_waiver": 20,
    "collective_action_waiver": 20,
    "jury_trial_waiver": 20,
    "dispute_resolution_restriction": 15,
    "exclusive_jurisdiction": 10,
    "exclusive_venue": 10,
    "governing_law": 5,

    # ========================================================
    # USER CONTENT / LICENSE
    # ========================================================

    "broad_user_content_license": 15,
    "irrevocable_content_license": 20,
    "worldwide_content_license": 15,
    "royalty_free_content_license": 15,
    "perpetual_content_license": 20,
    "sublicensable_content_license": 20,
    "transferable_content_license": 15,
    "user_content_ownership_restriction": 15,
    "content_removal_right": 10,
    "content_monitoring_right": 15,

    # ========================================================
    # INTELLECTUAL PROPERTY
    # ========================================================

    "intellectual_property_restriction": 10,
    "copyright_restriction": 10,
    "trademark_restriction": 5,
    "software_license_restriction": 10,
    "license_termination": 10,

    # ========================================================
    # POLICY / CONTRACT CHANGES
    # ========================================================

    "unilateral_policy_changes": 10,
    "unilateral_contract_changes": 15,
    "notice_limitation": 10,
    "continued_use_acceptance": 15,
    "retroactive_changes": 20,

    # ========================================================
    # INTERNATIONAL / EXPORT
    # ========================================================

    "international_data_transfer": 15,
    "cross_border_processing": 15,
    "export_control": 10,
    "sanctions_compliance": 10,

    # ========================================================
    # CONFIDENTIALITY
    # ========================================================

    "confidentiality_obligation": 5,
    "broad_confidentiality_obligation": 15,
    "confidentiality_survival": 10,

    # ========================================================
    # AUDIT / VERIFICATION
    # ========================================================

    "audit_right": 15,
    "inspection_right": 10,
    "verification_right": 10,

    # ========================================================
    # THIRD-PARTY SERVICES
    # ========================================================

    "third_party_service_dependency": 10,
    "third_party_terms_acceptance": 10,
    "third_party_content_risk": 10,
    "external_link_disclaimer": 5,

    # ========================================================
    # FORCE MAJEURE / BUSINESS INTERRUPTION
    # ========================================================

    "force_majeure": 5,
    "service_interruption": 10,
    "business_continuity_disclaimer": 10,

    # ========================================================
    # MISC LEGAL
    # ========================================================

    "survival_of_obligations": 10,
    "assignment_right": 10,
    "waiver_of_rights": 10,

    # These are deliberately neutral.
    "acceptance_of_terms": 0,
    "definitions": 0,
    "entire_agreement": 0,
    "severability": 0,
    "contact_information": 0,
}


# ============================================================
# TEXT RULES
# ============================================================

TEXT_RULES = {

    # ========================================================
    # PRIVACY
    # ========================================================

    "personal_data_collection": [
        r"\bwe collect\b",
        r"\bcollect(?:s|ed|ing)?\b.{0,180}\b(?:personal|user|customer)\b.{0,120}\b(?:data|information)\b",
        r"\bpersonal information\b.{0,180}\bcollect",
        r"\binformation we collect\b",
    ],

    "extensive_data_collection": [
        r"\bdevice information\b",
        r"\bbrowsing history\b",
        r"\busage information\b",
        r"\binteraction data\b",
        r"\bonline activity\b",
        r"\bidentifiers\b",
    ],

    "sensitive_personal_data": [
        r"\bsensitive personal information\b",
        r"\bsensitive personal data\b",
        r"\brace\b.{0,80}\bdata\b",
        r"\bracial\b.{0,80}\binformation\b",
        r"\breligious\b.{0,80}\binformation\b",
        r"\bsexual orientation\b",
    ],

    "financial_data_collection": [
        r"\bfinancial information\b",
        r"\bpayment information\b",
        r"\bcredit card\b",
        r"\bdebit card\b",
        r"\bbank account\b",
        r"\bbilling information\b",
    ],

    "health_data_collection": [
        r"\bhealth information\b",
        r"\bmedical information\b",
        r"\bhealth data\b",
        r"\bmedical data\b",
    ],

    "biometric_data_collection": [
        r"\bbiometric\b",
        r"\bfacial recognition\b",
        r"\bfingerprint\b",
        r"\bvoiceprint\b",
        r"\bface scan\b",
    ],

    "precise_location_collection": [
        r"\bprecise location\b",
        r"\bgps location\b",
        r"\bprecise geolocation\b",
    ],

    "contact_data_collection": [
        r"\bemail address\b",
        r"\bphone number\b",
        r"\btelephone number\b",
        r"\bpostal address\b",
        r"\bcontact information\b",
    ],

    "identity_data_collection": [
        r"\bidentity information\b",
        r"\bidentity data\b",
        r"\baccount details\b",
    ],

    "device_information_collection": [
        r"\bdevice information\b",
        r"\bdevice data\b",
        r"\bdevice identifier\b",
        r"\bdevice identifiers\b",
    ],

    "browsing_history_collection": [
        r"\bbrowsing history\b",
        r"\bbrowser history\b",
        r"\bweb history\b",
    ],

    "online_activity_collection": [
        r"\bonline activity\b",
        r"\bonline behavior\b",
        r"\bactivity on (?:our|the) (?:website|site|app)\b",
    ],

    "inferred_data_collection": [
        r"\binfer(?:red|ence)?\b.{0,120}\b(?:information|data|interests|preferences)\b",
        r"\binferences about\b",
        r"\bderive\b.{0,100}\b(?:information|preferences|interests)\b",
    ],

    "children_data_collection": [
        r"\bchildren'?s data\b",
        r"\bchildren under\b",
        r"\bminors\b.{0,100}\bpersonal information\b",
        r"\bunder the age of\b",
    ],

    "employee_data_collection": [
        r"\bemployee information\b",
        r"\bemployment information\b",
    ],

    # ========================================================
    # TRACKING
    # ========================================================

    "cookie_tracking": [
        r"\bcookies?\b",
        r"\bcookie identifiers?\b",
        r"\bcookie technologies\b",
    ],

    "analytics_tracking": [
        r"\banalytics\b",
        r"\busage analytics\b",
        r"\bperformance analytics\b",
        r"\banalytics services\b",
    ],

    "behavioral_tracking": [
        r"\bbehavioral tracking\b",
        r"\bbehavioural tracking\b",
        r"\btrack your activity\b",
        r"\btrack(?:ing)?\b.{0,100}\b(?:behavior|activity|interests)\b",
    ],

    "cross_site_tracking": [
        r"\bacross websites\b",
        r"\bacross sites\b",
        r"\bacross the web\b",
        r"\bacross different websites\b",
    ],

    "cross_service_tracking": [
        r"\bacross our services\b",
        r"\bacross services\b",
        r"\bacross apps\b",
        r"\bcombine\b.{0,100}\b(?:information|data)\b",
    ],

    "device_fingerprinting": [
        r"\bdevice fingerprint(?:ing)?\b",
        r"\bbrowser fingerprint(?:ing)?\b",
        r"\bfingerprinting\b",
    ],

    "advertising_identifier_tracking": [
        r"\badvertising identifier\b",
        r"\badvertising id\b",
        r"\bmobile advertising id\b",
    ],

    "location_tracking": [
        r"\blocation tracking\b",
        r"\btrack your location\b",
        r"\btrack\b.{0,80}\blocation\b",
    ],

    "session_recording": [
        r"\bsession recording\b",
        r"\bsession replay\b",
        r"\brecord your session\b",
    ],

    "interaction_tracking": [
        r"\btrack\b.{0,80}\bclicks\b",
        r"\btrack\b.{0,80}\binteractions\b",
        r"\binteraction tracking\b",
    ],

    # ========================================================
    # ADVERTISING
    # ========================================================

    "advertising_targeting": [
        r"\btargeted advertising\b",
        r"\btargeted ads?\b",
        r"\btarget advertisements?\b",
    ],

    "personalized_advertising": [
        r"\bpersonalized advertising\b",
        r"\bpersonalised advertising\b",
        r"\bpersonalized ads?\b",
        r"\bpersonalised ads?\b",
    ],

    "interest_based_advertising": [
        r"\binterest[- ]based advertising\b",
        r"\binterest[- ]based ads?\b",
        r"\bbased on your interests\b.{0,100}\badvertis",
    ],

    "behavioral_advertising": [
        r"\bbehavioral advertising\b",
        r"\bbehavioural advertising\b",
        r"\bbehavioral ads?\b",
    ],

    "third_party_advertising": [
        r"\bthird[- ]party advertising\b",
        r"\badvertising networks?\b",
        r"\badvertising services\b",
    ],

    "advertising_partner_sharing": [
        r"\badvertising partners?\b",
        r"\badvertising partner\b.{0,150}\bdata\b",
    ],

    # ========================================================
    # SHARING
    # ========================================================

    "third_party_data_sharing": [
        r"\bshare(?:s|d|ing)?\b.{0,180}\bthird[- ]part(?:y|ies)\b",
        r"\bdisclose\b.{0,180}\bthird[- ]part(?:y|ies)\b",
        r"\bprovide\b.{0,180}\bthird[- ]part(?:y|ies)\b",
    ],

    "service_provider_data_sharing": [
        r"\bservice providers?\b.{0,150}\b(?:data|information)\b",
        r"\bservice provider\b",
    ],

    "business_partner_sharing": [
        r"\bbusiness partners?\b",
        r"\bstrategic partners?\b",
    ],

    "affiliate_data_sharing": [
        r"\baffiliate companies\b",
        r"\baffiliates\b.{0,150}\b(?:data|information)\b",
        r"\bgroup companies\b.{0,150}\b(?:data|information)\b",
    ],

    "data_sale": [
        r"\bsell\b.{0,120}\b(?:personal|user|customer)\b.{0,120}\b(?:data|information)\b",
        r"\bsale of personal information\b",
        r"\bsell your information\b",
    ],

    "government_disclosure": [
        r"\bgovernment authorities\b",
        r"\bgovernment request\b",
        r"\bgovernment agencies\b",
    ],

    "law_enforcement_disclosure": [
        r"\blaw enforcement\b",
        r"\blaw enforcement agencies\b",
    ],

    "legal_process_disclosure": [
        r"\blegal process\b",
        r"\bcourt order\b",
        r"\bsubpoena\b",
        r"\blegal request\b",
    ],

    # ========================================================
    # RETENTION
    # ========================================================

    "data_retention": [
        r"\bretain(?:s|ed|ing)?\b.{0,150}\b(?:data|information)\b",
        r"\bdata retention\b",
        r"\bretention period\b",
    ],

    "long_term_data_retention": [
        r"\blong[- ]term retention\b",
        r"\bretain\b.{0,100}\b(?:for years|extended period)\b",
    ],

    "indefinite_data_retention": [
        r"\bretain\b.{0,100}\bindefinitely\b",
        r"\bretain indefinitely\b",
        r"\bindefinite retention\b",
    ],

    "deletion_limitations": [
        r"\bmay not be able to delete\b",
        r"\bcannot delete\b",
        r"\bunable to delete\b",
        r"\bdeletion may not\b",
    ],

    "account_deletion_limitations": [
        r"\bdelete your account\b",
        r"\baccount deletion\b",
        r"\bdeleting your account\b",
    ],

    "post_account_retention": [
        r"\bafter you delete your account\b",
        r"\bafter account deletion\b",
        r"\bretain\b.{0,120}\bafter termination\b",
    ],

    "backup_retention": [
        r"\bbackup copies\b",
        r"\bbackups?\b.{0,100}\bretain\b",
        r"\bretained in backup\b",
    ],

    # ========================================================
    # CONSENT
    # ========================================================

    "unfriendly_consent_or_opt_out": [
        r"\bopt[- ]out\b",
        r"\bwithdraw consent\b",
        r"\bmanage cookies\b",
    ],

    "forced_consent": [
        r"\bmust consent\b",
        r"\brequired to consent\b",
        r"\bcondition of use\b.{0,100}\bconsent\b",
    ],

    "limited_opt_out": [
        r"\blimited opt[- ]out\b",
        r"\bmay not opt out\b",
        r"\bcannot opt out\b",
        r"\bno opt[- ]out\b",
    ],

    "withdrawal_of_consent_limitations": [
        r"\bwithdraw\b.{0,100}\bconsent\b",
        r"\bwithdrawal of consent\b",
    ],

    "continued_use_consent": [
        r"\bcontinued use\b.{0,150}\b(?:accept|agree|consent)\b",
        r"\bcontinued use\b.{0,100}\bconstitutes acceptance\b",
    ],

    "cookie_control_limitations": [
        r"\bdisable cookies\b",
        r"\bblocking cookies\b",
        r"\bcookie settings\b",
    ],

    "consent_for_data_processing": [
        r"\bconsent\b.{0,100}\b(?:process|processing)\b.{0,100}\bdata\b",
    ],

    "consent_for_marketing": [
        r"\bconsent\b.{0,100}\bmarketing\b",
        r"\bmarketing consent\b",
    ],

    # ========================================================
    # AUTOMATION
    # ========================================================

    "automated_decision_making": [
        r"\bautomated decision\b",
        r"\bautomated decisions\b",
        r"\bautomated decision[- ]making\b",
    ],

    "profiling": [
        r"\bprofiling\b",
        r"\bprofile you\b",
        r"\bcreate a profile\b",
    ],

    "automated_profiling": [
        r"\bautomated profiling\b",
        r"\bautomatically profile\b",
    ],

    "algorithmic_personalization": [
        r"\balgorithmic\b",
        r"\bpersonalized recommendations?\b",
        r"\bpersonalised recommendations?\b",
    ],

    "recommendation_profiling": [
        r"\brecommendation systems?\b",
        r"\brecommendations based on\b",
    ],

    # ========================================================
    # COMMUNICATION MONITORING
    # ========================================================

    "communication_monitoring": [
        r"\bmonitor(?:s|ing)?\b.{0,100}\bcommunications?\b",
        r"\bmonitor(?:s|ing)?\b.{0,100}\bmessages?\b",
    ],

    "message_monitoring": [
        r"\bmonitor(?:s|ing)?\b.{0,100}\bchat\b",
        r"\breview\b.{0,100}\bmessages?\b",
    ],

    "call_monitoring": [
        r"\bmonitor(?:s|ing)?\b.{0,100}\bcalls?\b",
        r"\brecord\b.{0,100}\bcalls?\b",
    ],

    "content_monitoring": [
        r"\bmonitor(?:s|ing)?\b.{0,100}\bcontent\b",
        r"\breview\b.{0,100}\buser content\b",
    ],

    # ========================================================
    # SECURITY
    # ========================================================

    "security_disclaimer": [
        r"\bno method of transmission\b",
        r"\bsecurity cannot be guaranteed\b",
        r"\bsecurity cannot be guaranteed\b",
    ],

    "no_guarantee_of_security": [
        r"\bcannot guarantee\b.{0,100}\bsecurity\b",
        r"\bnot guarantee\b.{0,100}\bsecurity\b",
        r"\bno guarantee\b.{0,100}\bsecurity\b",
    ],

    "breach_disclaimer": [
        r"\bdata breach\b",
        r"\bsecurity breach\b",
        r"\bbreach notification\b",
    ],

    "security_incident_disclosure": [
        r"\bsecurity incident\b",
        r"\bsecurity event\b",
    ],

    "user_security_obligation": [
        r"\byou are responsible\b.{0,100}\bsecurity\b",
        r"\bkeep your credentials secure\b",
        r"\bprotect your password\b",
    ],

    "account_security_obligation": [
        r"\bmaintain the confidentiality\b.{0,100}\baccount\b",
        r"\baccount credentials\b",
        r"\baccount password\b",
    ],

    # ========================================================
    # ACCOUNT
    # ========================================================

    "account_termination": [
        r"\bterminate\b.{0,120}\b(?:account|access|service)\b",
        r"\bsuspend\b.{0,120}\b(?:account|access|service)\b",
        r"\btermination of\b.{0,120}\b(?:account|access|service)\b",
        r"\btermination\b.{0,120}\baccess\b",
    ],

    "account_suspension": [
        r"\bsuspend\b.{0,100}\b(?:account|access)\b",
        r"\bsuspension of\b.{0,100}\b(?:account|access)\b",
    ],

    "unilateral_termination": [
        r"\breserve the right to\b.{0,120}\b(?:terminate|suspend)\b",
        r"\bmay terminate\b.{0,120}\b(?:at any time|without notice)\b",
    ],

    "unilateral_suspension": [
        r"\bmay suspend\b.{0,120}\b(?:at any time|without notice)\b",
        r"\breserve the right to suspend\b",
    ],

    "access_restriction": [
        r"\brestrict\b.{0,100}\baccess\b",
        r"\blimit\b.{0,100}\baccess\b",
        r"\bdeny\b.{0,100}\baccess\b",
        r"\brevoke\b.{0,100}\baccess\b",
    ],

    "account_lockout": [
        r"\blocked account\b",
        r"\blockout\b",
        r"\block\b.{0,80}\baccount\b",
    ],

    "account_deletion_by_provider": [
        r"\bwe may delete your account\b",
        r"\bdelete your account\b.{0,150}\bwe may\b",
        r"\baccount may be deleted\b",
    ],

    "termination_without_notice": [
        r"\bterminate\b.{0,100}\bwithout notice\b",
        r"\bsuspend\b.{0,100}\bwithout notice\b",
    ],

    # ========================================================
    # ELIGIBILITY
    # ========================================================

    "age_restriction": [
        r"\bmust be at least\b.{0,50}\byears old\b",
        r"\bunder the age of\b",
        r"\bminimum age\b",
    ],

    "eligibility_restriction": [
        r"\beligible to use\b",
        r"\beligibility requirements?\b",
        r"\bnot eligible\b",
    ],

    "parental_responsibility": [
        r"\bparent or guardian\b",
        r"\bparental consent\b",
        r"\bguardian consent\b",
    ],

    # ========================================================
    # USER CONDUCT
    # ========================================================

    "prohibited_use": [
        r"\bprohibited uses?\b",
        r"\byou agree not to misuse\b",
        r"\byou may not use\b",
        r"\bprohibited activities\b",
    ],

    "unauthorized_access_restriction": [
        r"\bunauthorized access\b",
        r"\battempt unauthorized access\b",
    ],

    "reverse_engineering_restriction": [
        r"\breverse engineer\b",
        r"\bdecompile\b",
        r"\bdisassemble\b",
    ],

    "scraping_restriction": [
        r"\bscrap(?:e|ing)\b",
        r"\bdata mining\b",
    ],

    "automated_access_restriction": [
        r"\bautomated access\b",
        r"\bautomated means\b",
        r"\bautomated systems\b",
    ],

    "circumvention_restriction": [
        r"\bcircumvent\b",
        r"\bbypass\b.{0,100}\bsecurity\b",
        r"\bcircumvent\b.{0,100}\bsecurity\b",
    ],

    "commercial_use_restriction": [
        r"\bcommercial use\b",
        r"\bcommercial purposes\b",
    ],

    "redistribution_restriction": [
        r"\bredistribut\b",
        r"\bresell\b",
        r"\breproduce\b",
    ],

    "impersonation_restriction": [
        r"\bimpersonat(?:e|ion)\b",
        r"\bpretend to be\b",
    ],

    "illegal_activity_restriction": [
        r"\billegal activities\b",
        r"\bunlawful activities\b",
        r"\bviolate applicable law\b",
    ],

    "abuse_restriction": [
        r"\bharass\b",
        r"\babuse\b.{0,100}\bservice\b",
        r"\bthreaten\b.{0,100}\busers?\b",
    ],

    # ========================================================
    # PAYMENT
    # ========================================================

    "payment_obligation": [
        r"\byou agree to pay\b",
        r"\bpayment is due\b",
        r"\bpayment obligation\b",
        r"\bfees? payable\b",
        r"\byou must pay\b",
    ],

    "payment_authorization": [
        r"\bauthorize\b.{0,100}\bcharge\b",
        r"\bauthorize\b.{0,100}\bpayment\b",
        r"\bauthorization to charge\b",
    ],

    "automatic_billing": [
        r"\bautomatically charge\b",
        r"\bautomatically billed\b",
        r"\bautomatic billing\b",
        r"\bautomatically debit\b",
    ],

    "recurring_billing": [
        r"\brecurring billing\b",
        r"\brecurring payment\b",
        r"\brecurring charge\b",
        r"\bsubscription fee\b",
    ],

    "renewal_without_clear_notice": [
        r"\bautomatically renew\b",
        r"\bauto[- ]renew\b",
        r"\brenewal\b.{0,120}\bautomatically\b",
    ],

    "free_trial_conversion": [
        r"\bfree trial\b.{0,180}\bcharged\b",
        r"\bfree trial\b.{0,180}\bsubscription\b",
        r"\btrial period\b.{0,180}\bautomatically\b",
    ],

    "price_change": [
        r"\bprices? may change\b",
        r"\bprice may change\b",
        r"\bchange\b.{0,80}\bprice\b",
    ],

    "fee_change": [
        r"\bfees? may change\b",
        r"\bchange\b.{0,80}\bfees?\b",
    ],

    "late_payment_consequences": [
        r"\blate payment\b",
        r"\boverdue payment\b",
        r"\bfailure to pay\b",
        r"\bnonpayment\b",
    ],

    "payment_failure_consequences": [
        r"\bpayment fails?\b",
        r"\bfailed payment\b",
        r"\bpayment failure\b",
        r"\bdeclined payment\b",
    ],

    "currency_conversion_cost": [
        r"\bcurrency conversion\b",
        r"\bforeign exchange\b",
        r"\bexchange rate\b",
    ],

    "tax_obligation": [
        r"\byou are responsible for\b.{0,100}\btaxes?\b",
        r"\btaxes? are your responsibility\b",
        r"\bapplicable taxes\b",
    ],

    # ========================================================
    # REFUNDS / RETURNS
    # ========================================================

    "cancellation_restriction": [
        r"\bcancell?ation\b.{0,120}\b(?:not permitted|restriction|fee)\b",
        r"\bcannot cancel\b",
        r"\bno cancellation\b",
    ],

    "refund_limitation": [
        r"\brefunds?\b.{0,120}\b(?:not available|not permitted|limited)\b",
        r"\bno refunds?\b",
        r"\brefund policy\b",
        r"\brefund limitation\b",
    ],

    "non_refundable_payment": [
        r"\bnon[- ]refundable\b",
        r"\bnonrefundable\b",
    ],

    "restocking_fee": [
        r"\brestocking fee\b",
        r"\bre-stocking fee\b",
    ],

    "return_shipping_cost": [
        r"\breturn shipping\b",
        r"\bcost of return shipping\b",
        r"\breturn shipping costs?\b",
    ],

    "refund_delay": [
        r"\brefund\b.{0,150}\b(?:days?|business days)\b",
        r"\brefund may take\b",
    ],

    "store_credit_instead_of_refund": [
        r"\bstore credit\b",
        r"\bcredit instead of refund\b",
    ],

    "cancellation_fee": [
        r"\bcancellation fee\b",
        r"\bcancel(?:lation)? fee\b",
    ],

    "return_condition_restriction": [
        r"\breturn\b.{0,150}\bunused\b",
        r"\breturn\b.{0,150}\boriginal packaging\b",
        r"\breturn\b.{0,150}\bwithin\b.{0,50}\bdays\b",
    ],

    # ========================================================
    # E-COMMERCE
    # ========================================================

    "delivery_disclaimer": [
        r"\bdelivery\b.{0,150}\bnot guaranteed\b",
        r"\bdelivery dates?\b.{0,100}\bestimate\b",
    ],

    "shipping_delay": [
        r"\bshipping delays?\b",
        r"\bdelivery delays?\b",
        r"\bdelays? in delivery\b",
    ],

    "risk_of_loss": [
        r"\brisk of loss\b",
        r"\brisk of damage\b",
        r"\btitle and risk\b",
    ],

    "delivery_estimate_disclaimer": [
        r"\bestimated delivery\b",
        r"\bdelivery estimate\b",
        r"\bestimated shipping\b",
    ],

    "order_cancellation_by_seller": [
        r"\bwe may cancel\b.{0,150}\border\b",
        r"\bmay cancel your order\b",
        r"\border may be cancelled\b",
    ],

    "order_rejection_right": [
        r"\brefuse or cancel\b.{0,100}\border\b",
        r"\breserve the right\b.{0,100}\breject\b.{0,100}\border\b",
    ],

    "inventory_availability_disclaimer": [
        r"\bsubject to availability\b",
        r"\bwhile supplies last\b",
        r"\bout of stock\b.{0,100}\bcancel\b",
    ],

    "pricing_error_cancellation": [
        r"\bpricing error\b",
        r"\bincorrect price\b",
        r"\bprice error\b",
    ],

    "product_description_disclaimer": [
        r"\bproduct descriptions?\b.{0,150}\bmay not\b",
        r"\bproduct information\b.{0,150}\bnot guaranteed\b",
    ],

    "warranty_limitation": [
        r"\blimited warranty\b",
        r"\bwarranty limitations?\b",
    ],

    "guarantee_limitation": [
        r"\bguarantee\b.{0,100}\bexcluded\b",
        r"\bguarantee limitations?\b",
    ],

    # ========================================================
    # LIABILITY
    # ========================================================

    "liability_limitation": [
        r"\blimitation of liability\b",
        r"\bnot liable\b",
        r"\bshall not be liable\b",
        r"\bmaximum liability\b",
    ],

    "consequential_damage_exclusion": [
        r"\bindirect or consequential damages\b",
        r"\bconsequential damages\b",
        r"\bincidental damages\b",
    ],

    "damage_cap": [
        r"\bliability\b.{0,100}\blimited to\b",
        r"\bmaximum liability\b.{0,100}\b(?:amount|fee|paid)\b",
        r"\bdamages\b.{0,100}\bshall not exceed\b",
    ],

    "loss_exclusion": [
        r"\bexclude\b.{0,100}\blosses\b",
        r"\bexclude\b.{0,100}\bdamages\b",
        r"\bnot responsible for\b.{0,100}\bloss\b",
    ],

    "warranty_disclaimer": [
        r"\bdisclaimer of warranties\b",
        r"\bprovided as is\b",
        r"\bas[- ]is\b",
        r"\bwithout warranties\b",
        r"\bno warranties\b",
    ],

    "service_availability_disclaimer": [
        r"\bservice may be unavailable\b",
        r"\bavailability is not guaranteed\b",
        r"\bcontinuous availability\b",
        r"\bservice availability\b",
    ],

    "content_disclaimer": [
        r"\bcontent disclaimer\b",
        r"\bdoes not guarantee the accuracy\b",
        r"\bcontent may be inaccurate\b",
    ],

    "third_party_content_disclaimer": [
        r"\bthird[- ]party content\b",
        r"\bcontent provided by third parties\b",
        r"\ball content is provided by third[- ]party\b",
        r"\bdoes not host\b.{0,100}\bthird[- ]party\b",
    ],

    "accuracy_disclaimer": [
        r"\baccuracy is not guaranteed\b",
        r"\bno guarantee of accuracy\b",
        r"\bwe do not warrant the accuracy\b",
    ],

    "professional_advice_disclaimer": [
        r"\bnot legal advice\b",
        r"\bnot medical advice\b",
        r"\bnot financial advice\b",
        r"\bnot professional advice\b",
    ],

    "no_guarantee_clause": [
        r"\bno guarantee\b",
        r"\bwithout guarantee\b",
        r"\bmake no guarantees?\b",
    ],

    # ========================================================
    # INDEMNIFICATION
    # ========================================================

    "indemnification": [
        r"\bindemnif(?:y|ies|ied|ication)\b",
        r"\bhold harmless\b",
    ],

    "broad_indemnification": [
        r"\bindemnify\b.{0,180}\b(?:claims|losses|damages|expenses)\b",
        r"\bdefend and indemnify\b",
    ],

    "defense_obligation": [
        r"\bduty to defend\b",
        r"\bobligation to defend\b",
        r"\bdefend\b.{0,100}\bclaims\b",
    ],

    # ========================================================
    # DISPUTES
    # ========================================================

    "mandatory_arbitration": [
        r"\bbinding arbitration\b",
        r"\bmandatory arbitration\b",
        r"\barbitrat(?:e|ion)\b",
    ],

    "class_action_waiver": [
        r"\bclass action\b",
        r"\bclass[- ]action waiver\b",
        r"\bwaive\b.{0,100}\bclass action\b",
    ],

    "collective_action_waiver": [
        r"\bcollective action\b",
        r"\bcollective proceedings\b",
        r"\bwaive\b.{0,100}\bcollective\b",
    ],

    "jury_trial_waiver": [
        r"\bwaive\b.{0,80}\bjury trial\b",
        r"\bjury trial\b.{0,80}\bwaiver\b",
    ],

    "dispute_resolution_restriction": [
        r"\bdispute resolution\b",
        r"\bresolve disputes\b",
        r"\bdisputes shall be resolved\b",
    ],

    "exclusive_jurisdiction": [
        r"\bexclusive jurisdiction\b",
        r"\bexclusive jurisdiction of\b",
    ],

    "exclusive_venue": [
        r"\bexclusive venue\b",
        r"\bvenue shall be\b",
    ],

    "governing_law": [
        r"\bgoverned by the laws\b",
        r"\bgoverning law\b",
        r"\blaws of the state\b",
    ],

    # ========================================================
    # USER CONTENT
    # ========================================================

    "broad_user_content_license": [
        r"\blicense\b.{0,150}\buser content\b",
        r"\buser content\b.{0,150}\blicense\b",
    ],

    "irrevocable_content_license": [
        r"\birrevocable\b.{0,100}\blicense\b",
    ],

    "worldwide_content_license": [
        r"\bworldwide\b.{0,100}\blicense\b",
    ],

    "royalty_free_content_license": [
        r"\broyalty[- ]free\b",
    ],

    "perpetual_content_license": [
        r"\bperpetual\b.{0,100}\blicense\b",
        r"\bperpetual license\b",
    ],

    "sublicensable_content_license": [
        r"\bsublicens(?:e|able)\b",
        r"\bright to sublicense\b",
    ],

    "transferable_content_license": [
        r"\btransferable\b.{0,100}\blicense\b",
    ],

    "user_content_ownership_restriction": [
        r"\byou retain ownership\b.{0,120}\bcontent\b",
        r"\bownership of your content\b",
        r"\bcontent ownership\b",
    ],

    "content_removal_right": [
        r"\bremove\b.{0,100}\buser content\b",
        r"\bremove your content\b",
        r"\bdelete user content\b",
    ],

    "content_monitoring_right": [
        r"\bmonitor\b.{0,100}\buser content\b",
        r"\breview\b.{0,100}\buser content\b",
    ],

    # ========================================================
    # IP
    # ========================================================

    "intellectual_property_restriction": [
        r"\bintellectual property rights\b",
        r"\bintellectual property\b.{0,100}\brestriction\b",
    ],

    "copyright_restriction": [
        r"\bcopyright infringement\b",
        r"\bcopyrighted material\b",
        r"\bcopyright restrictions?\b",
    ],

    "trademark_restriction": [
        r"\btrademark infringement\b",
        r"\btrademark restrictions?\b",
    ],

    "software_license_restriction": [
        r"\bsoftware license\b",
        r"\blicense restrictions?\b",
    ],

    "license_termination": [
        r"\blicense\b.{0,100}\bterminate\b",
        r"\blicense terminates?\b",
    ],

    # ========================================================
    # POLICY CHANGES
    # ========================================================

    "unilateral_policy_changes": [
        r"\bmay change these terms\b",
        r"\bmodify these terms\b",
        r"\bterms may be updated\b",
        r"\bpolicy may be updated\b",
    ],

    "unilateral_contract_changes": [
        r"\bchange\b.{0,100}\bagreement\b.{0,100}\bwithout notice\b",
        r"\bmodify\b.{0,100}\bterms\b.{0,100}\bwithout notice\b",
    ],

    "notice_limitation": [
        r"\bwithout notice\b",
        r"\bwithout prior notice\b",
        r"\bno notice\b",
    ],

    "continued_use_acceptance": [
        r"\bcontinued use means\b",
        r"\bcontinued use\b.{0,100}\b(?:accept|agree)\b",
        r"\bcontinued use\b.{0,100}\bconstitutes acceptance\b",
    ],

    "retroactive_changes": [
        r"\bretroactive\b.{0,100}\b(?:change|changes|terms|policy)\b",
        r"\bchanges apply retroactively\b",
    ],

    # ========================================================
    # INTERNATIONAL / EXPORT
    # ========================================================

    "international_data_transfer": [
        r"\binternational transfer\b",
        r"\bdata transferred internationally\b",
        r"\btransfer\b.{0,100}\boutside\b.{0,100}\bcountry\b",
    ],

    "cross_border_processing": [
        r"\bcross[- ]border\b",
        r"\bprocessed in other countries\b",
        r"\bprocessed outside\b",
    ],

    "export_control": [
        r"\bexport control\b",
        r"\bexport laws\b",
        r"\bexport regulations\b",
    ],

    "sanctions_compliance": [
        r"\bsanctions\b.{0,100}\b(?:law|laws|regulations?)\b",
        r"\btrade sanctions\b",
    ],

    # ========================================================
    # CONFIDENTIALITY
    # ========================================================

    "confidentiality_obligation": [
        r"\bconfidential information\b",
        r"\bconfidentiality\b",
    ],

    "broad_confidentiality_obligation": [
        r"\bkeep\b.{0,100}\bconfidential information\b",
        r"\bstrictly confidential\b",
    ],

    "confidentiality_survival": [
        r"\bconfidentiality\b.{0,100}\bsurvive\b",
        r"\bconfidential obligations\b.{0,100}\btermination\b",
    ],

    # ========================================================
    # AUDIT
    # ========================================================

    "audit_right": [
        r"\bright to audit\b",
        r"\baudit rights?\b",
        r"\baudit your\b",
    ],

    "inspection_right": [
        r"\bright to inspect\b",
        r"\binspection rights?\b",
    ],

    "verification_right": [
        r"\bright to verify\b",
        r"\bverification rights?\b",
    ],

    # ========================================================
    # THIRD PARTY SERVICES
    # ========================================================

    "third_party_service_dependency": [
        r"\bthird[- ]party services?\b",
        r"\bdependent on third parties\b",
    ],

    "third_party_terms_acceptance": [
        r"\bthird[- ]party terms\b",
        r"\bsubject to third[- ]party terms\b",
    ],

    "third_party_content_risk": [
        r"\bthird[- ]party content\b",
        r"\bthird[- ]party providers?\b",
    ],

    "external_link_disclaimer": [
        r"\bexternal links?\b",
        r"\blinks to third[- ]party websites\b",
    ],

    # ========================================================
    # FORCE MAJEURE
    # ========================================================

    "force_majeure": [
        r"\bforce majeure\b",
        r"\bevents beyond our control\b",
        r"\bcircumstances beyond our control\b",
    ],

    "service_interruption": [
        r"\bservice interruption\b",
        r"\bservice disruptions?\b",
        r"\bmaintenance\b.{0,100}\bservice\b",
    ],

    "business_continuity_disclaimer": [
        r"\bbusiness continuity\b",
        r"\bwe are not responsible\b.{0,100}\binterruption\b",
    ],

    # ========================================================
    # MISC
    # ========================================================

    "survival_of_obligations": [
        r"\bsurvive termination\b",
        r"\bsurvival of\b",
    ],

    "assignment_right": [
        r"\bassign\b.{0,100}\bright\b",
        r"\bassignment of this agreement\b",
    ],

    "waiver_of_rights": [
        r"\bwaiver of rights\b",
        r"\bwaive any rights\b",
    ],

    # Neutral classifications
    "acceptance_of_terms": [
        r"\bby accessing or using\b.{0,120}\bagree\b",
        r"\bby using\b.{0,120}\bagree to\b",
        r"\bagree to be bound by\b",
    ],

    "definitions": [
        r"\bdefinitions?\b",
        r"\bmeans the following\b",
    ],

    "entire_agreement": [
        r"\bentire agreement\b",
        r"\bwhole agreement\b",
    ],

    "severability": [
        r"\bseverability\b",
        r"\bseverable\b",
    ],

    "contact_information": [
        r"\bcontact us\b",
        r"\bcontact information\b",
    ],
}


# ============================================================
# FACTOR NORMALIZATION
# ============================================================

def _normalize_factors(
    factors: Iterable[Any],
) -> list[str]:

    valid = []

    for factor in factors or []:

        key = str(
            factor
        ).strip().lower()

        if key in WEIGHTS and key not in valid:
            if key not in valid:
                valid.append(key)

    return valid


# ============================================================
# TEXT FACTOR INFERENCE
# ============================================================

def infer_text_factors(
    text: str,
) -> list[str]:

    low = (
        text or ""
    ).lower()

    found = []

    for factor, patterns in TEXT_RULES.items():

        matched = False

        for pattern in patterns:

            try:
                if re.search(
                    pattern,
                    low,
                    re.I | re.S,
                ):
                    matched = True
                    break

            except re.error:
                continue

        if matched:
            found.append(factor)

    return found


# ============================================================
# SCORE ONE CLAUSE
# ============================================================

def score_clause(
    clause: Dict[str, Any],
) -> Dict[str, Any]:

    text = " ".join(
        str(
            clause.get(
                key,
                "",
            ) or ""
        )
        for key in (
            "title",
            "summary",
            "explanation",
            "risk_reason",
            "source_text",
            "clause_text",
            "text",
        )
    )

    factors = _normalize_factors(
        clause.get(
            "risk_factors",
            [],
        )
    )

    inferred = infer_text_factors(text)

    for factor in inferred:

        if factor not in factors:
            factors.append(factor)

    # --------------------------------------------------------
    # Avoid double-counting closely related factors.
    #
    # Example:
    # behavioral_advertising + advertising_targeting
    #
    # Both can be valid, but we don't want dozens of synonyms
    # to artificially create CRITICAL risk.
    # --------------------------------------------------------

    factor_groups = [
        {
            "advertising_targeting",
            "personalized_advertising",
            "interest_based_advertising",
            "behavioral_advertising",
        },
        {
            "cookie_tracking",
            "analytics_tracking",
            "behavioral_tracking",
            "interaction_tracking",
        },
        {
            "account_termination",
            "account_suspension",
            "unilateral_termination",
            "unilateral_suspension",
            "termination_without_notice",
        },
        {
            "liability_limitation",
            "consequential_damage_exclusion",
            "damage_cap",
            "loss_exclusion",
        },
        {
            "third_party_data_sharing",
            "service_provider_data_sharing",
            "business_partner_sharing",
            "affiliate_data_sharing",
            "advertising_partner_data_sharing",
        },
        {
            "data_retention",
            "long_term_data_retention",
            "indefinite_data_retention",
        },
    ]

    # --------------------------------------------------------
    # Score all matched factors.
    #
    # Within a related group, retain the strongest factor
    # plus one additional factor when it represents a
    # genuinely different user impact.
    # --------------------------------------------------------

    selected = list(factors)

    for group in factor_groups:

        matched = [
            factor
            for factor in selected
            if factor in group
        ]

        if len(matched) <= 1:
            continue

        strongest = max(
            matched,
            key=lambda factor: WEIGHTS.get(
                factor,
                0,
            ),
        )

        for factor in matched:
            if factor == strongest:
                continue

            # Keep a second factor only when it describes
            # a materially different consequence.
            if factor in {
                "consequential_damage_exclusion",
                "damage_cap",
                "indefinite_data_retention",
                "termination_without_notice",
                "advertising_partner_data_sharing",
                "behavioral_tracking",
            }:
                continue

            if factor in selected:
                selected.remove(factor)

    factors = selected

    score = min(
        100,
        sum(
            WEIGHTS.get(
                factor,
                0,
            )
            for factor in factors
        ),
    )

    if score >= 80:
        level = "CRITICAL"

    elif score >= 60:
        level = "HIGH"

    elif score >= 30:
        level = "MEDIUM"

    else:
        level = "LOW"

    return {
        **clause,
        "risk_factors": factors,
        "risk_score": score,
        "risk_level": level,
    }


# ============================================================
# SCORE ALL CLAUSES
# ============================================================

def score_clauses(
    clauses: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:

    return [
        score_clause(clause)
        for clause in clauses
    ]


# ============================================================
# OVERALL SCORE
# ============================================================

def overall_score(
    clauses: list[Dict[str, Any]],
) -> int:

    if not clauses:
        return 0

    scores = sorted(
        (
            int(
                clause.get(
                    "risk_score",
                    0,
                )
            )
            for clause in clauses
        ),
        reverse=True,
    )

    # Only the strongest five risk-bearing clauses
    # influence the overall score.
    #
    # This prevents a long policy with dozens of harmless
    # clauses from becoming artificially HIGH.
    top = [
        score
        for score in scores[:5]
        if score > 0
    ]

    if not top:
        return 0

    return min(
        100,
        round(
            sum(top)
            / len(top)
        ),
    )


# ============================================================
# RISK LEVEL
# ============================================================

def level_for_score(
    score: int,
) -> str:

    if score >= 80:
        return "CRITICAL"

    if score >= 60:
        return "HIGH"

    if score >= 30:
        return "MEDIUM"

    return "LOW"

    