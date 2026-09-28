"use strict";

// ============================================================
// T&C ANALYZER – POPUP CONTROLLER
//
// State machine: IDLE → EXTRACTING → EXTRACTED → ANALYZING → RESULT | ERROR
//
// Message contracts (must not change):
//   chrome.runtime.sendMessage({ action: "collectPolicyData", tabId })
//   POST /api/agent1/analyze
//   POST /api/agent2/analyze  { run_id }
//   POST /api/agent3/analyze  { run_id }
//
// Only Agent 3 final output is displayed to the user.
// Agent 1 policy-type counts are shown as compact context.
// Agent 2 output is never exposed.
// ============================================================

const API = "http://127.0.0.1:8001";

// How long the extraction summary stays visible before transitioning
// to the Agent 2 analyzing state.  Change this value to adjust the delay.
const EXTRACTION_SUMMARY_DISPLAY_MS = 5000;

// ============================================================
// STATE
// ============================================================

let analysisRunning = false;
let currentTabId    = null;
let currentTabUrl   = "";
let currentRunId    = null;
let activeRisk      = "high";   // default selected tab

// Agent 3 clause data grouped by risk level (populated after analysis)
let clausesByRisk = { high: [], medium: [], low: [] };

// ============================================================
// DOM ELEMENTS
// ============================================================

const states = {
    idle:       document.getElementById("state-idle"),
    extracting: document.getElementById("state-extracting"),
    extracted:  document.getElementById("state-extracted"),
    analyzing:  document.getElementById("state-analyzing"),
    result:     document.getElementById("state-result"),
    error:      document.getElementById("state-error"),
};

const btnAnalyze   = document.getElementById("btn-analyze");
const btnReanalyze = document.getElementById("btn-reanalyze");
const btnRetry     = document.getElementById("btn-retry");

// Extraction steps
const stepScrape  = document.getElementById("step-scrape");
const stepDetect  = document.getElementById("step-detect");
const stepExtract = document.getElementById("step-extract");

// Extraction summary
const docSummary = document.getElementById("doc-summary");

// Analysis steps
const stepClauses = document.getElementById("step-clauses");
const stepRisk    = document.getElementById("step-risk");
const stepExplain = document.getElementById("step-explain");

// Result elements
const resultRiskLevel    = document.getElementById("result-risk-level");
const resultRiskScore    = document.getElementById("result-risk-score");
const countHigh          = document.getElementById("count-high");
const countMedium        = document.getElementById("count-medium");
const countLow           = document.getElementById("count-low");
const tabHigh            = document.getElementById("tab-high");
const tabMedium          = document.getElementById("tab-medium");
const tabLow             = document.getElementById("tab-low");
const tabCountHigh       = document.getElementById("tab-count-high");
const tabCountMedium     = document.getElementById("tab-count-medium");
const tabCountLow        = document.getElementById("tab-count-low");
const clauseCategoryHeading = document.getElementById("clause-category-heading");
const clausePanel        = document.getElementById("clause-panel");
const resultDocContext   = document.getElementById("result-doc-context");

// Idle page info / error
const idlePageInfo = document.getElementById("idle-page-info");
const idleError    = document.getElementById("idle-error");

// Error state
const errorTitle = document.getElementById("error-title");
const errorDesc  = document.getElementById("error-desc");

// ============================================================
// STATE MACHINE
// ============================================================

function showState(name) {
    for (const [key, el] of Object.entries(states)) {
        if (el) el.hidden = (key !== name);
    }
}

// ============================================================
// STEP HELPERS
// ============================================================

function setStep(el, status) {
    // status: "pending" | "active" | "done"
    if (!el) return;
    el.className = `step step-${status}`;

    const indicator = el.querySelector(".step-indicator");
    if (!indicator) return;

    // Clear previous text/content set by previous states
    indicator.textContent = "";

    if (status === "done") {
        // The CSS ::after puts in the checkmark, but we need
        // to ensure the class triggers it.
        // No extra JS needed – handled by CSS.
    }
}

// ============================================================
// HTML ESCAPE
// ============================================================

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

// ============================================================
// DOCUMENT TYPE NORMALIZATION
// ============================================================

const DOC_TYPE_LABELS = {
    terms:       "Terms & Conditions",
    privacy:     "Privacy Policy",
    cookies:     "Cookie Policy",
    returns:     "Returns / Refunds",
    refund:      "Returns / Refunds",
    payments:    "Payments",
    billing:     "Payments",
    promotions:  "Promotions",
    subscription:"Subscription",
    legal:       "Legal / Other",
    other:       "Other",
};

function normalizeDocType(raw) {
    if (!raw) return "other";
    const key = String(raw).toLowerCase().trim();
    return DOC_TYPE_LABELS[key] || DOC_TYPE_LABELS["other"];
}

// Count policy documents by display type
function countDocTypes(policies) {
    const counts = {};
    for (const policy of policies) {
        const raw  = String(policy?.type || "other").toLowerCase();
        const label = normalizeDocType(raw);
        counts[label] = (counts[label] || 0) + 1;
    }
    return counts;
}

// ============================================================
// RISK LEVEL NORMALIZATION
// ============================================================

function normalizeRiskLevel(raw) {
    if (!raw) return "LOW";
    const upper = String(raw).toUpperCase().trim();
    if (upper === "CRITICAL") return "HIGH";
    if (["HIGH", "MEDIUM", "LOW"].includes(upper)) return upper;
    return "LOW";
}

// ============================================================
// COUNT RISK LEVELS FROM ANALYSES
// ============================================================

function countRiskLevels(analyses) {
    const counts = { high: 0, medium: 0, low: 0 };
    for (const a of analyses) {
        const level = normalizeRiskLevel(
            a?.risk_level || a?.risk || ""
        ).toLowerCase();
        if (level in counts) counts[level]++;
    }
    return counts;
}

// ============================================================
// GROUP CLAUSES BY RISK
// ============================================================

function groupByRisk(analyses) {
    const groups = { high: [], medium: [], low: [] };
    for (const a of analyses) {
        const level = normalizeRiskLevel(
            a?.risk_level || a?.risk || ""
        ).toLowerCase();
        if (level in groups) groups[level].push(a);
    }
    return groups;
}

// ============================================================
// BACKEND HELPERS
// ============================================================

async function post(path, body) {
    const response = await fetch(API + path, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(body),
    });

    const text = await response.text();
    let data;
    try { data = JSON.parse(text); }
    catch { throw new Error(text || `HTTP ${response.status}`); }

    if (!response.ok) {
        throw new Error(data?.detail || data?.error || `HTTP ${response.status}`);
    }
    return data;
}

async function checkBackendHealth() {
    try {
        const res  = await fetch(API + "/health", { cache: "no-store" });
        if (!res.ok) return false;
        const data = await res.json();
        return data?.status === "ok";
    } catch {
        return false;
    }
}

// ============================================================
// BROWSER DATA COLLECTION (collectPolicyData contract)
// ============================================================

async function browserData(tabId) {
    if (typeof tabId !== "number") {
        throw new Error("Invalid source tab.");
    }

    return new Promise((resolve, reject) => {
        let settled = false;

        const done = (ok, val) => {
            if (settled) return;
            settled = true;
            ok ? resolve(val) : reject(val);
        };

        chrome.runtime.sendMessage(
            { action: "collectPolicyData", tabId },
            response => {
                const err = chrome.runtime.lastError;
                if (err) {
                    done(false, new Error(err.message));
                    return;
                }
                if (!response) {
                    done(false, new Error("Browser collector returned no response."));
                    return;
                }
                if (response.success === false) {
                    done(false, new Error(response.error || "Browser collection failed."));
                    return;
                }
                done(true, response);
            }
        );
    });
}

// ============================================================
// ACTIVE TAB
// ============================================================

async function getActiveTab() {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab  = tabs[0];

    if (!tab || typeof tab.id !== "number") {
        throw new Error("No active webpage.");
    }
    if (!tab.url || !/^https?:\/\//i.test(tab.url)) {
        throw new Error("T&C Analyzer only works on HTTP/HTTPS pages.");
    }
    return tab;
}

// ============================================================
// RENDER: EXTRACTION SUMMARY (State EXTRACTED)
// ============================================================

function renderExtractionSummary(policies) {
    const safe = Array.isArray(policies) ? policies : [];
    const counts = countDocTypes(safe);
    const total  = safe.length;

    if (!docSummary) return;

    if (total === 0) {
        docSummary.innerHTML = `
            <div class="doc-summary-row">
                <span class="doc-summary-type">No policy documents found</span>
            </div>
        `;
        return;
    }

    const rows = Object.entries(counts)
        .filter(([, n]) => n > 0)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([label, n]) => `
            <div class="doc-summary-row">
                <span class="doc-summary-type">${escapeHtml(label)}</span>
                <span class="doc-summary-count">${escapeHtml(n)}</span>
            </div>
        `)
        .join("");

    const totalLabel = total === 1 ? "1 document extracted" : `${total} documents extracted`;

    docSummary.innerHTML = `
        ${rows}
        <div class="doc-summary-total">${escapeHtml(totalLabel)}</div>
    `;
}

// ============================================================
// RENDER: OVERALL RISK CARD
// ============================================================

function renderRiskCard(overallRisk, overallScore) {
    if (!resultRiskLevel || !resultRiskScore) return;

    const level = normalizeRiskLevel(overallRisk);

    resultRiskLevel.textContent = level;
    resultRiskLevel.setAttribute("data-level", level);

    const score = Number.isFinite(Number(overallScore))
        ? Math.max(0, Math.min(100, Math.round(Number(overallScore))))
        : 0;
    resultRiskScore.textContent = String(score);
}

// ============================================================
// RENDER: CLAUSE COUNTS & TAB COUNTS
// ============================================================

function renderClauseCounts(counts) {
    if (countHigh)    countHigh.textContent   = String(counts.high);
    if (countMedium)  countMedium.textContent = String(counts.medium);
    if (countLow)     countLow.textContent    = String(counts.low);
    if (tabCountHigh)   tabCountHigh.textContent   = String(counts.high);
    if (tabCountMedium) tabCountMedium.textContent = String(counts.medium);
    if (tabCountLow)    tabCountLow.textContent    = String(counts.low);
}

// ============================================================
// RENDER: RISK TABS (active state)
// ============================================================

function renderRiskTabs(selectedRisk) {
    const tabs = { high: tabHigh, medium: tabMedium, low: tabLow };

    for (const [level, el] of Object.entries(tabs)) {
        if (!el) continue;
        const isActive = level === selectedRisk;
        el.classList.toggle("risk-tab-active", isActive);
        el.setAttribute("aria-selected", isActive ? "true" : "false");
    }
}

// ============================================================
// RENDER: CATEGORY HEADING
// ============================================================

function renderCategoryHeading(risk, count) {
    if (!clauseCategoryHeading) return;
    const label = risk.toUpperCase();
    const noun  = count === 1 ? "clause" : "clauses";
    clauseCategoryHeading.innerHTML = `
        <span class="cat-label cat-label-${escapeHtml(risk)}">${escapeHtml(label)} RISK</span>
        <span class="cat-count">${escapeHtml(count)} ${escapeHtml(noun)}</span>
    `;
}

// ============================================================
// CLAUSE DISPLAY TITLE
// ============================================================

// Maps Agent 2 / Agent 3 machine-readable category values to
// short human-readable labels shown on clause card headers.
// Covers the full Agent 2 category vocabulary (schemas.py /
// ClauseCategory enum in agent3/models.py).
const CATEGORY_LABELS = {
    // Agent 2 primary categories
    subscription:          "Subscription",
    auto_renewal:          "Automatic Renewal",
    cancellation:          "Cancellation",
    payments:              "Payments",
    payment:               "Payments",
    privacy:               "Privacy",
    data_collection:       "Data Collection",
    data_sharing:          "Data Sharing",
    refund:                "Refund",
    intellectual_property: "Intellectual Property",
    license:               "License",
    liability:             "Liability",
    limitation_of_liability: "Limitation of Liability",
    indemnification:       "Indemnification",
    arbitration:           "Arbitration",
    termination:           "Termination",
    tracking:              "Tracking",
    security:              "Security",
    prohibited_use:        "Prohibited Use",
    // Agent 3 additional categories
    data_privacy:          "Data Privacy",
    data_retention:        "Data Retention",
    user_content:          "User Content",
    governing_law:         "Governing Law",
    account_termination:   "Account Termination",
    cookies:               "Cookies",
    third_party:           "Third-Party Services",
    third_party_services:  "Third-Party Services",
    marketing:             "Marketing",
    age_requirement:       "Age Requirement",
    other:                 "General Terms",
};

// Keyword patterns used as a last-resort text fallback.
// Each entry: [regex, display label].
// Tested against the first ~300 chars of the clause's source text.
const TEXT_KEYWORD_PATTERNS = [
    [/auto\w*\s+renew|renew\w*\s+auto/i,         "Automatic Renewal"],
    [/arbitrat/i,                                  "Arbitration"],
    [/class\s+action/i,                            "Class Action Waiver"],
    [/limitation\s+of\s+liabilit/i,               "Limitation of Liability"],
    [/indemnif/i,                                  "Indemnification"],
    [/intellectual\s+propert|copyright|trademark/i,"Intellectual Property"],
    [/data\s+shar|share.*personal|personal.*shar/i,"Data Sharing"],
    [/data\s+collect|collect.*personal|personal.*collect/i, "Data Collection"],
    [/data\s+retent|retain.*data|data.*retain/i,   "Data Retention"],
    [/governing\s+law|jurisdiction|applicable\s+law/i, "Governing Law"],
    [/terminat/i,                                  "Termination"],
    [/cancell/i,                                   "Cancellation"],
    [/refund/i,                                    "Refund"],
    [/subscript/i,                                 "Subscription"],
    [/payment|billing|charge/i,                    "Payments"],
    [/track|cookie|beacon/i,                       "Tracking"],
    [/third.party|third\s+part/i,                  "Third-Party Services"],
    [/privacy\s+polic|personal\s+info/i,           "Privacy"],
    [/prohibit|restrict|not\s+allow/i,             "Prohibited Use"],
    [/security|protect.*account|account.*protect/i,"Security"],
    [/user\s+content|your\s+content|submit.*content/i, "User Content"],
    [/licen[sc]e/i,                                "License"],
    [/liabilit/i,                                  "Liability"],
    [/market|promotional\s+email|opt.out/i,        "Marketing"],
    [/cookie/i,                                    "Cookies"],
    [/age\s+require|must\s+be\s+\d+|under\s+\d+/i,"Age Requirement"],
];

/**
 * Derive a short human-readable display title for a clause card.
 *
 * Priority:
 *   1. Explicit title field (if it looks meaningful — not a generic fallback)
 *   2. Category mapped via CATEGORY_LABELS
 *   3. Text keyword matched against clause content
 *   4. Neutral fallback "Clause"
 *
 * @param {object} analysis  – one element from Agent 3 analyses[]
 * @returns {string}
 */
function getClauseDisplayTitle(analysis) {
    // --- 1. Explicit title ---
    const rawTitle = String(
        analysis?.title || analysis?.clause_title || ""
    ).trim();

    // Accept the title only if it isn't one of the known generic placeholders
    // that we're trying to replace.
    const GENERIC_TITLES = new Set([
        "", "policy", "policy clause", "clause",
        "policy 1", "policy 2", "policy 3", "policy 4", "policy 5",
        "clause 1", "clause 2", "clause 3", "clause 4", "clause 5",
        "untitled clause", "untitled",
    ]);

    if (rawTitle && !GENERIC_TITLES.has(rawTitle.toLowerCase())) {
        // Truncate very long titles to keep cards scannable
        return rawTitle.length > 60 ? rawTitle.slice(0, 57).trimEnd() + "…" : rawTitle;
    }

    // --- 2. Category mapping ---
    const rawCategory = String(
        analysis?.category || analysis?.clause_category || ""
    ).trim().toLowerCase();

    if (rawCategory && CATEGORY_LABELS[rawCategory]) {
        return CATEGORY_LABELS[rawCategory];
    }

    // Also try partial key matching for compound categories
    // (e.g. "auto_renewal_policy" should still map to "Automatic Renewal")
    for (const [key, label] of Object.entries(CATEGORY_LABELS)) {
        if (key !== "other" && rawCategory.includes(key)) {
            return label;
        }
    }

    // --- 3. Text keyword fallback ---
    const searchText = String(
        analysis?.summary     ||
        analysis?.explanation ||
        analysis?.evidence    ||
        analysis?.text        ||
        ""
    ).slice(0, 300);

    if (searchText) {
        for (const [pattern, label] of TEXT_KEYWORD_PATTERNS) {
            if (pattern.test(searchText)) {
                return label;
            }
        }
    }

    // --- 4. Neutral fallback ---
    return "Clause";
}

// ============================================================
// RENDER: SINGLE CLAUSE CARD
// ============================================================

function renderClauseCard(analysis, index, expandFirst) {
    const isExpanded = expandFirst && index === 0;

    const riskLevel = normalizeRiskLevel(
        analysis?.risk_level || analysis?.risk || ""
    ).toLowerCase();

    // Derive a meaningful display title using the priority helper.
    const title = getClauseDisplayTitle(analysis);
    const summary     = String(analysis?.summary     || analysis?.explanation  || "").trim();
    const explanation = String(analysis?.explanation || analysis?.summary      || "").trim();
    const userImpact  = String(analysis?.user_impact || analysis?.impact       || "").trim();
    const whyMatters  = String(analysis?.why_it_matters || "").trim();
    const recommendation = String(analysis?.recommendation || "").trim();
    const evidence    = String(analysis?.evidence || analysis?.risk_reason || "").trim();

    // Build body fields — only include non-empty ones
    const fields = [];

    if (summary) {
        fields.push({ label: "Summary", text: summary });
    }

    if (explanation && explanation !== summary) {
        fields.push({ label: "Explanation", text: explanation });
    }

    if (whyMatters) {
        fields.push({ label: "Why it matters", text: whyMatters });
    }

    if (userImpact) {
        fields.push({ label: "User impact", text: userImpact });
    }

    if (recommendation) {
        fields.push({ label: "What to consider", text: recommendation });
    }

    const bodyFieldsHtml = fields
        .map(f => `
            <div class="clause-field">
                <div class="clause-field-label">${escapeHtml(f.label)}</div>
                <div class="clause-field-text">${escapeHtml(f.text)}</div>
            </div>
        `)
        .join("");

    // Source shown last, in a visually secondary block
    const sourceHtml = evidence ? `
        <div class="clause-source-block">
            <div class="clause-field-label">Risk reason</div>
            <div class="clause-field-text">${escapeHtml(evidence)}</div>
        </div>
    ` : "";

    const cardId = `clause-card-${index}`;
    const bodyId = `clause-body-${index}`;

    const chevron = `<svg class="clause-chevron" width="8" height="13" viewBox="0 0 8 13" fill="none" aria-hidden="true">
        <path d="M1.5 1.5l5 5-5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>`;

    return `
        <article
            class="clause-card"
            id="${escapeHtml(cardId)}"
            aria-expanded="${isExpanded ? "true" : "false"}"
        >
            <button
                class="clause-card-header"
                type="button"
                aria-expanded="${isExpanded ? "true" : "false"}"
                aria-controls="${escapeHtml(bodyId)}"
                data-card="${escapeHtml(cardId)}"
            >
                <span class="clause-header-left">
                    <span class="clause-risk-pip clause-risk-pip-${escapeHtml(riskLevel)}" aria-hidden="true"></span>
                    <span class="clause-title-text">${escapeHtml(title)}</span>
                </span>
                ${chevron}
            </button>
            <div
                class="clause-body"
                id="${escapeHtml(bodyId)}"
                role="region"
                aria-label="${escapeHtml(title)}"
            >
                ${bodyFieldsHtml}
                ${sourceHtml}
            </div>
        </article>
    `;
}

// ============================================================
// RENDER: CLAUSE LIST FOR ACTIVE RISK LEVEL
// ============================================================

function renderRiskClauses(risk) {
    if (!clausePanel) return;

    const clauses = clausesByRisk[risk] || [];

    if (clauses.length === 0) {
        const label = risk.toUpperCase();
        clausePanel.innerHTML = `
            <div class="clause-empty">
                No ${escapeHtml(label)} risk clauses found.
            </div>
        `;
        return;
    }

    clausePanel.innerHTML = clauses
        .map((a, i) => renderClauseCard(a, i, true))
        .join("");
}

// ============================================================
// TOGGLE CLAUSE CARD
// ============================================================

function toggleClause(cardId) {
    const card = document.getElementById(cardId);
    if (!card) return;

    const isExpanded = card.getAttribute("aria-expanded") === "true";
    const next = !isExpanded;

    card.setAttribute("aria-expanded", next ? "true" : "false");

    const btn = card.querySelector(".clause-card-header");
    if (btn) btn.setAttribute("aria-expanded", next ? "true" : "false");
}

// ============================================================
// SWITCH RISK TAB
// ============================================================

function switchRiskTab(risk) {
    if (!["high", "medium", "low"].includes(risk)) return;
    activeRisk = risk;
    renderRiskTabs(risk);
    renderCategoryHeading(risk, (clausesByRisk[risk] || []).length);
    renderRiskClauses(risk);
}

// ============================================================
// DOCUMENT CONTEXT FOOTER
// ============================================================

function renderDocContext(policies) {
    if (!resultDocContext) return;
    const safe  = Array.isArray(policies) ? policies : [];
    const total = safe.length;
    if (total === 0) {
        resultDocContext.textContent = "";
        return;
    }
    const counts  = countDocTypes(safe);
    const entries = Object.entries(counts)
        .filter(([, n]) => n > 0)
        .map(([label, n]) => `${label}: ${n}`)
        .join(" · ");
    const noun = total === 1 ? "document" : "documents";
    resultDocContext.textContent = `${total} policy ${noun} analyzed · ${entries}`;
}

// ============================================================
// RENDER: FINAL ANALYSIS (Agent 3 result)
// ============================================================

function renderFinalAnalysis(agent3Result, policies) {
    const analyses = Array.isArray(agent3Result?.analyses)
        ? agent3Result.analyses
        : [];

    const overallRisk  = agent3Result?.overall_risk_level
        || agent3Result?.overall_risk
        || "LOW";

    const overallScore = agent3Result?.overall_risk_score
        ?? agent3Result?.risk_score
        ?? 0;

    // Group clauses
    clausesByRisk = groupByRisk(analyses);
    const counts  = countRiskLevels(analyses);

    // Render risk card
    renderRiskCard(overallRisk, overallScore);

    // Render summary counts
    renderClauseCounts(counts);

    // Render doc context footer
    renderDocContext(policies);

    // Determine default active tab:
    // Prefer HIGH if it has clauses, then MEDIUM, then LOW
    let defaultTab = "high";
    if (counts.high > 0)        defaultTab = "high";
    else if (counts.medium > 0) defaultTab = "medium";
    else                        defaultTab = "low";

    activeRisk = defaultTab;
    renderRiskTabs(defaultTab);
    renderCategoryHeading(defaultTab, counts[defaultTab]);
    renderRiskClauses(defaultTab);

    showState("result");
}

// ============================================================
// RENDER: IDLE
// ============================================================

function renderIdleState(tab) {
    if (idlePageInfo && tab) {
        const display = tab.title || tab.url || "";
        idlePageInfo.textContent = display;
    }
    if (idleError) {
        idleError.textContent = "";
        idleError.hidden = true;
    }
    showState("idle");
}

// ============================================================
// RENDER: EXTRACTION PROGRESS
// ============================================================

function renderExtractionProgress() {
    setStep(stepScrape,  "active");
    setStep(stepDetect,  "pending");
    setStep(stepExtract, "pending");
    showState("extracting");
}

// ============================================================
// RENDER: ANALYSIS PROGRESS
// ============================================================

function renderAnalysisProgress() {
    setStep(stepClauses, "active");
    setStep(stepRisk,    "pending");
    setStep(stepExplain, "pending");
    showState("analyzing");
}

// ============================================================
// SHOW ERROR
// ============================================================

function showErrorState(title, desc) {
    if (errorTitle) errorTitle.textContent = title || "Something went wrong";
    if (errorDesc)  errorDesc.textContent  = desc  || "An unexpected error occurred.";
    showState("error");
}

// ============================================================
// MAIN ANALYSIS PIPELINE
// ============================================================

async function runAnalysis() {
    if (analysisRunning) return;
    analysisRunning = true;

    // Disable buttons
    if (btnAnalyze)   btnAnalyze.disabled   = true;
    if (btnReanalyze) btnReanalyze.disabled = true;

    let collectedPolicies = [];

    try {
        // --------------------------------------------------
        // STEP 1: Get active tab
        // --------------------------------------------------
        let tab;
        try {
            tab = await getActiveTab();
        } catch (err) {
            showErrorState(
                "Unable to analyze this page",
                err?.message || "Could not access the current page."
            );
            return;
        }

        currentTabId  = tab.id;
        currentTabUrl = tab.url;

        // --------------------------------------------------
        // STEP 2: Backend health
        // --------------------------------------------------
        const healthy = await checkBackendHealth();
        if (!healthy) {
            showErrorState(
                "Backend is not running",
                "Please start the FastAPI backend on port 8001 and try again."
            );
            return;
        }

        // --------------------------------------------------
        // STEP 3: Extracting UI + browser collection
        // --------------------------------------------------
        renderExtractionProgress();
        setStep(stepScrape, "active");

        let browser;
        try {
            browser = await browserData(currentTabId);
        } catch (err) {
            // Non-fatal — proceed with empty browser data
            browser = {
                browser_links:     [],
                browser_documents: [],
                browser_all_links: [],
                browser_page_text: "",
            };
        }

        setStep(stepScrape,  "done");
        setStep(stepDetect,  "active");

        // --------------------------------------------------
        // STEP 4: Agent 1
        // --------------------------------------------------
        setStep(stepDetect,  "done");
        setStep(stepExtract, "active");

        let a1;
        try {
            a1 = await post("/api/agent1/analyze", {
                url:               currentTabUrl,
                browser_links:     browser?.browser_links     || [],
                browser_documents: browser?.browser_documents || [],
                browser_all_links: browser?.browser_all_links || [],
                browser_page_text: browser?.browser_page_text || "",
                browser_title:     browser?.title || tab.title || "",
            });
        } catch (err) {
            showErrorState(
                "Unable to analyze this page",
                "We couldn't extract usable policy information from this page."
            );
            return;
        }

        currentRunId = a1?.run_id || null;

        const agent1Result = a1?.agent1 || a1 || {};
        collectedPolicies  = Array.isArray(agent1Result?.policy_pages)
            ? agent1Result.policy_pages
            : (Array.isArray(agent1Result?.documents)
                ? agent1Result.documents
                : []);

        setStep(stepExtract, "done");

        // --------------------------------------------------
        // STEP 5: Show extraction summary briefly
        // --------------------------------------------------
        renderExtractionSummary(collectedPolicies);
        showState("extracted");

        if (collectedPolicies.length === 0) {
            showErrorState(
                "No policy documents found",
                "This page does not appear to contain usable Terms, Privacy, Cookie, or related policy information."
            );
            return;
        }

        if (!currentRunId) {
            showErrorState(
                "Unable to analyze this page",
                "Policy extraction did not return a valid session. Please try again."
            );
            return;
        }

        // Keep extraction summary visible long enough for the user to read it.
        // Duration is controlled by EXTRACTION_SUMMARY_DISPLAY_MS (top of file).
        await new Promise(r => setTimeout(r, EXTRACTION_SUMMARY_DISPLAY_MS));

        // --------------------------------------------------
        // STEP 6: Analyzing UI
        // --------------------------------------------------
        renderAnalysisProgress();
        setStep(stepClauses, "active");

        // --------------------------------------------------
        // STEP 7: Agent 2
        // --------------------------------------------------
        let a2;
        try {
            a2 = await post("/api/agent2/analyze", { run_id: currentRunId });
        } catch (err) {
            showErrorState(
                "Analysis couldn't be completed",
                "The page was extracted, but the risk analysis could not be completed."
            );
            return;
        }

        setStep(stepClauses, "done");
        setStep(stepRisk,    "done");
        setStep(stepExplain, "active");

        // --------------------------------------------------
        // STEP 8: Agent 3
        // --------------------------------------------------
        let a3;
        try {
            a3 = await post("/api/agent3/analyze", { run_id: currentRunId });
        } catch (err) {
            showErrorState(
                "Analysis couldn't be completed",
                "The page was extracted, but the plain-language explanation could not be completed."
            );
            return;
        }

        setStep(stepExplain, "done");

        const agent3Result = a3?.agent3 || a3 || {};

        // --------------------------------------------------
        // STEP 9: Render final result
        // --------------------------------------------------
        const analyses = Array.isArray(agent3Result?.analyses)
            ? agent3Result.analyses
            : [];

        if (analyses.length === 0) {
            showErrorState(
                "No analyzable clauses found",
                "The available policy content could not be broken into analyzable clauses."
            );
            return;
        }

        renderFinalAnalysis(agent3Result, collectedPolicies);

    } catch (err) {
        showErrorState(
            "Something went wrong",
            "An unexpected error occurred. Please try again."
        );
    } finally {
        analysisRunning = false;
        if (btnAnalyze)   btnAnalyze.disabled   = false;
        if (btnReanalyze) btnReanalyze.disabled = false;
    }
}

// ============================================================
// EVENT DELEGATION: CLAUSE CARD TOGGLE
// ============================================================

if (clausePanel) {
    clausePanel.addEventListener("click", e => {
        const btn = e.target.closest(".clause-card-header");
        if (!btn) return;
        const cardId = btn.getAttribute("data-card");
        if (cardId) toggleClause(cardId);
    });

    clausePanel.addEventListener("keydown", e => {
        if (e.key !== "Enter" && e.key !== " ") return;
        const btn = e.target.closest(".clause-card-header");
        if (!btn) return;
        e.preventDefault();
        const cardId = btn.getAttribute("data-card");
        if (cardId) toggleClause(cardId);
    });
}

// ============================================================
// EVENT: RISK TABS
// ============================================================

if (tabHigh)   tabHigh.addEventListener("click",   () => switchRiskTab("high"));
if (tabMedium) tabMedium.addEventListener("click", () => switchRiskTab("medium"));
if (tabLow)    tabLow.addEventListener("click",    () => switchRiskTab("low"));

// ============================================================
// EVENT: BUTTONS
// ============================================================

if (btnAnalyze) {
    btnAnalyze.addEventListener("click", () => runAnalysis());
}

if (btnReanalyze) {
    btnReanalyze.addEventListener("click", () => {
        if (!analysisRunning) runAnalysis();
    });
}

if (btnRetry) {
    btnRetry.addEventListener("click", () => {
        if (!analysisRunning) runAnalysis();
    });
}

// ============================================================
// INITIALIZATION
// ============================================================

(async () => {
    try {
        const tab = await getActiveTab();
        currentTabId  = tab.id;
        currentTabUrl = tab.url;
        renderIdleState(tab);
    } catch (err) {
        // Tab not accessible (e.g., chrome:// page)
        if (idlePageInfo) idlePageInfo.textContent = "";
        if (idleError) {
            idleError.textContent = err?.message || "Unable to access this page.";
            idleError.hidden = false;
        }
        if (btnAnalyze) btnAnalyze.disabled = true;
        showState("idle");
    }
})();
