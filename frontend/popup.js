"use strict";

const API = "http://127.0.0.1:8001";

const $ = id => document.getElementById(id);

const els = {
    pageTitle: $("pageTitle"),
    connectionStatus: $("connectionStatus"),
    agent1Status: $("agent1Status"),
    agent2Status: $("agent2Status"),

    termsCount: $("termsCount"),
    privacyCount: $("privacyCount"),
    cookiesCount: $("cookiesCount"),
    legalCount: $("legalCount"),

    policyCount: $("policyCount"),
    policies: $("policies"),

    overallRisk: $("overallRisk"),
    keyFindings: $("keyFindings"),
    clauseCount: $("clauseCount"),
    clauses: $("clauses"),

    analyze: $("analyze"),
    reanalyze: $("reanalyze"),
};



/* ============================================================
 * AGENT 3 UI
 * ========================================================== */

function ensureAgent3UI() {

    let status =
        document.getElementById("agent3Status");

    if (status) {

        els.agent3Status =
            status;

        els.agent3OverallRisk =
            document.getElementById("agent3OverallRisk");

        els.agent3OverallScore =
            document.getElementById("agent3OverallScore");

        els.agent3ClauseCount =
            document.getElementById("agent3ClauseCount");

        els.agent3Warnings =
            document.getElementById("agent3Warnings");

        els.agent3Analyses =
            document.getElementById("agent3Analyses");

        return;

    }


    const actions =
        document.querySelector(".actions");


    if (!actions) {

        console.warn(
            "[T&C] Could not create Agent 3 UI."
        );

        return;

    }


    const section =
        document.createElement("section");


    section.className =
        "panel agent3-panel";


    section.innerHTML = `

        <div class="hero">

            <div>

                <span class="eyebrow">
                    AGENT 3
                </span>

                <h2>
                    Plain-Language Explanation
                </h2>

            </div>

            <span
                id="agent3Status"
                class="status"
            >
                Waiting
            </span>

        </div>


        <div class="risk-box">

            <span>
                AGENT 3 RISK
            </span>

            <strong id="agent3OverallRisk">
                UNAVAILABLE
            </strong>

        </div>


        <div class="meta">

            Overall score:
            <strong id="agent3OverallScore">
                0/100
            </strong>

            &nbsp;·&nbsp;

            Clauses analyzed:
            <strong id="agent3ClauseCount">
                0
            </strong>

        </div>


        <h2>
            Warnings
        </h2>


        <ul id="agent3Warnings">

            <li>
                Agent 3 will explain clauses after Agent 2 completes.
            </li>

        </ul>


        <div class="section-head">

            <h2>
                Explanations
            </h2>

        </div>


        <div id="agent3Analyses"></div>

    `;


    actions.parentNode.insertBefore(
        section,
        actions
    );


    els.agent3Status =
        document.getElementById(
            "agent3Status"
        );

    els.agent3OverallRisk =
        document.getElementById(
            "agent3OverallRisk"
        );

    els.agent3OverallScore =
        document.getElementById(
            "agent3OverallScore"
        );

    els.agent3ClauseCount =
        document.getElementById(
            "agent3ClauseCount"
        );

    els.agent3Warnings =
        document.getElementById(
            "agent3Warnings"
        );

    els.agent3Analyses =
        document.getElementById(
            "agent3Analyses"
        );

}

/* ============================================================
 * FINAL COMPACT SUMMARY
 * ========================================================== */

function ensureFinalSummaryUI() {

    let summary =
        document.getElementById("finalSummary");

    if (summary) {
        return summary;
    }

    const actions =
        document.querySelector(".actions");

    if (!actions) {
        return null;
    }

    summary =
        document.createElement("section");

    summary.id =
        "finalSummary";

    summary.className =
        "panel final-summary-panel";

    summary.innerHTML = `

        <div class="hero">

            <div>

                <span class="eyebrow">
                    FINAL RESULT
                </span>

                <h2>
                    Terms & Conditions Risk
                </h2>

            </div>

        </div>

        <div class="meta">
            Policies scraped:
            <strong id="finalPolicyCount">
                0
            </strong>
        </div>

        <div class="risk-box">

            <span>
                OVERALL RISK
            </span>

            <strong id="finalRiskLevel">
                ANALYZING
            </strong>

        </div>

        <div class="meta">
            Overall score:
            <strong id="finalRiskScore">
                0/100
            </strong>
        </div>

    `;

    actions.parentNode.insertBefore(
        summary,
        actions
    );

    return summary;
}


/* ============================================================
 * HIDE INTERMEDIATE AGENT OUTPUT
 * ========================================================== */

function hideIntermediateAgentOutput() {

    const hide =
        id => {

            const element =
                document.getElementById(id);

            if (element) {
                element.style.display =
                    "none";
            }

        };

    // Agent 1 intermediate output
    hide("agent1Status");
    hide("policies");

    // Agent 2 intermediate output
    hide("agent2Status");
    hide("overallRisk");
    hide("keyFindings");
    hide("clauseCount");
    hide("clauses");

}

/* ============================================================
 * PROFESSIONAL RISK VIEW
 * ========================================================== */

(function injectProfessionalRiskStyles() {

    if (
        document.getElementById(
            "professionalRiskStyles"
        )
    ) {
        return;
    }


    const style =
        document.createElement(
            "style"
        );


    style.id =
        "professionalRiskStyles";


    style.textContent = `

        #professionalRiskView {
            display: block;
            width: 100%;
            box-sizing: border-box;
            padding: 18px 14px 24px;
            font-family: inherit;
        }


        .professional-page-header {
            margin-bottom: 18px;
        }


        .professional-eyebrow {
            display: block;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 1.4px;
            opacity: 0.62;
            margin-bottom: 5px;
        }


        .professional-page-header h2 {
            margin: 0;
            font-size: 22px;
            line-height: 1.2;
        }


        .professional-page-header p {
            margin: 7px 0 0;
            font-size: 12px;
            opacity: 0.62;
        }


        .professional-overall-card {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 18px;
            border-radius: 14px;
            border: 1px solid rgba(0,0,0,0.10);
            background: #ffffff;
            margin-bottom: 24px;
            box-sizing: border-box;
        }


        .professional-overall-card > div:first-child {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }


        .professional-overall-card > div:first-child span {
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            opacity: 0.58;
        }


        .professional-overall-card > div:first-child strong {
            font-size: 25px;
            line-height: 1;
        }


        .professional-overall-score {
            display: flex;
            align-items: baseline;
            gap: 2px;
        }


        .professional-overall-score strong {
            font-size: 28px;
        }


        .professional-overall-score span {
            font-size: 12px;
            opacity: 0.55;
        }


        .professional-section-title {
            font-size: 16px;
            font-weight: 700;
            margin-bottom: 10px;
        }


        .professional-risk-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }


        .professional-risk-card {
            background: #ffffff;
            border: 1px solid rgba(0,0,0,0.10);
            border-radius: 13px;
            padding: 14px;
            box-sizing: border-box;
        }


        .professional-risk-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 8px;
        }


        .professional-risk-badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 8px;
            border-radius: 999px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.5px;
            background: #eef1f5;
        }


        .professional-risk-badge.low {
            background: #eef5ef;
        }


        .professional-risk-badge.medium {
            background: #f6f1e5;
        }


        .professional-risk-badge.high {
            background: #f7eaea;
        }


        .professional-risk-badge.critical {
            background: #f4e6e6;
        }


        .professional-risk-score {
            font-size: 12px;
            font-weight: 700;
            opacity: 0.68;
        }


        .professional-risk-card h3 {
            margin: 0 0 5px;
            font-size: 16px;
            line-height: 1.25;
        }


        .professional-risk-type {
            font-size: 11px;
            opacity: 0.65;
            margin-bottom: 9px;
        }


        .professional-risk-type strong {
            opacity: 1;
        }


        .professional-risk-summary {
            margin: 0;
            font-size: 13px;
            line-height: 1.45;
        }


        .professional-risk-details {
            margin-top: 11px;
            border-top: 1px solid rgba(0,0,0,0.08);
            padding-top: 9px;
        }


        .professional-risk-details summary {
            cursor: pointer;
            font-size: 12px;
            font-weight: 700;
            list-style-position: inside;
        }


        .professional-detail-block {
            margin-top: 12px;
        }


        .professional-detail-block span {
            display: block;
            font-size: 9px;
            font-weight: 700;
            letter-spacing: 0.8px;
            opacity: 0.55;
            margin-bottom: 4px;
        }


        .professional-detail-block p {
            margin: 0;
            font-size: 12px;
            line-height: 1.5;
        }


        .professional-empty {
            padding: 20px;
            text-align: center;
            opacity: 0.6;
            font-size: 13px;
        }

    `;


    document.head.appendChild(
        style
    );

})();

/* ============================================================
 * STATE
 * ========================================================== */

let analysisRunning = false;

let currentTabId = null;

let currentTabUrl = "";

let currentRunId = null;


/* ============================================================
 * GET ACTIVE TAB
 * ========================================================== */

async function getTab() {

    const tabs =
        await chrome.tabs.query({
            active: true,
            currentWindow: true
        });


    const tab = tabs[0];


    if (
        !tab ||
        typeof tab.id !== "number"
    ) {

        throw new Error(
            "No active webpage."
        );

    }


    if (
        !tab.url ||
        !/^https?:\/\//i.test(tab.url)
    ) {

        throw new Error(
            "T&C Analyzer can only analyze HTTP/HTTPS webpages."
        );

    }


    return tab;

}


/* ============================================================
 * BROWSER DATA
 * ========================================================== */

async function browserData(tabId) {

    if (
        typeof tabId !== "number"
    ) {

        throw new Error(
            "Invalid source tab."
        );

    }


    return new Promise(
        (
            resolve,
            reject
        ) => {

            let settled = false;


            const finishError =
                error => {

                    if (settled) {
                        return;
                    }

                    settled = true;

                    reject(error);

                };


            const finishSuccess =
                response => {

                    if (settled) {
                        return;
                    }

                    settled = true;

                    resolve(response);

                };


            chrome.runtime.sendMessage(

                {
                    action:
                        "collectPolicyData",

                    tabId:
                        tabId
                },

                response => {

                    const runtimeError =
                        chrome.runtime.lastError;


                    if (
                        runtimeError
                    ) {

                        finishError(
                            new Error(
                                runtimeError.message
                            )
                        );

                        return;

                    }


                    if (
                        !response
                    ) {

                        finishError(
                            new Error(
                                "Browser collector returned no response."
                            )
                        );

                        return;

                    }


                    if (
                        response.success === false
                    ) {

                        finishError(
                            new Error(
                                response.error ||
                                "Browser collection failed."
                            )
                        );

                        return;

                    }


                    finishSuccess(
                        response
                    );

                }

            );

        }
    );

}


/* ============================================================
 * BACKEND POST
 * ========================================================== */

async function post(
    path,
    body
) {

    const response =
        await fetch(
            API + path,
            {
                method:
                    "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body:
                    JSON.stringify(body)
            }
        );


    const text =
        await response.text();


    let data;


    try {

        data =
            JSON.parse(text);

    } catch {

        throw new Error(
            text ||
            `HTTP ${response.status}`
        );

    }


    if (
        !response.ok
    ) {

        throw new Error(
            data.detail ||
            data.error ||
            `HTTP ${response.status}`
        );

    }


    return data;

}


/* ============================================================
 * HEALTH CHECK
 * ========================================================== */

async function health() {

    try {

        const response =
            await fetch(
                API + "/health",
                {
                    cache:
                        "no-store"
                }
            );


        if (
            !response.ok
        ) {

            throw new Error(
                `HTTP ${response.status}`
            );

        }


        const data =
            await response.json();


        if (
            !data ||
            data.status !== "ok"
        ) {

            throw new Error(
                "Backend health check failed."
            );

        }


        els.connectionStatus.textContent =
            "Backend online";


        return true;

    } catch {

        els.connectionStatus.textContent =
            "Backend offline";


        return false;

    }

}


/* ============================================================
 * RESET UI
 * ========================================================== */

function resetUI() {

    els.policies.innerHTML =
        "";


    els.clauses.innerHTML =
        "";


    els.keyFindings.innerHTML =
        "<li>Agent 1 is collecting policy documents.</li>";


    els.overallRisk.textContent =
        "ANALYZING";


    els.clauseCount.textContent =
        "0";


    els.agent1Status.textContent =
        "Starting";


    els.agent2Status.textContent =
        "Waiting";


    els.termsCount.textContent =
        "0";

    els.privacyCount.textContent =
        "0";

    els.cookiesCount.textContent =
        "0";

    els.legalCount.textContent =
        "0";


    els.policyCount.textContent =
        "0 results";

}


/* ============================================================
 * BUTTON STATE
 * ========================================================== */

function setRunningState(
    running
) {

    analysisRunning =
        running;


    els.analyze.disabled =
        running;


    els.reanalyze.disabled =
        running;


    if (
        running
    ) {

        els.analyze.textContent =
            "Analyzing...";

        els.reanalyze.textContent =
            "Please wait...";

    } else {

        els.analyze.textContent =
            "Run Analysis";

        els.reanalyze.textContent =
            "Run Again";

    }

}


/* ============================================================
 * RENDER AGENT 1
 * ========================================================== */

function renderPolicies(
    policies
) {

    const safePolicies =
        Array.isArray(policies)
            ? policies
            : [];


    els.policyCount.textContent =
        `${safePolicies.length} result${
            safePolicies.length === 1
                ? ""
                : "s"
        }`;


    const counts = {

        terms:
            0,

        privacy:
            0,

        cookies:
            0,

        legal:
            0

    };

    // Map policy types not shown in their own counter to "legal".
    // background.js classifyPolicyUrl() can also produce:
    // "returns", "payments", "promotions" — all displayed under Legal.
    const TYPE_DISPLAY_MAP = {
        returns:    "legal",
        payments:   "legal",
        promotions: "legal",
    };


    els.policies.innerHTML =
        "";


    for (
        const policy of safePolicies
    ) {

        const type =
            String(
                policy?.type ||
                "legal"
            )
                .toLowerCase();

        // Resolve display category: "returns"/"payments"/"promotions"
        // are shown under the "legal" counter.
        const displayType =
            TYPE_DISPLAY_MAP[type] ||
            type;

        if (
            counts[displayType] !== undefined
        ) {

            counts[displayType]++;

        }


        const card =
            document.createElement(
                "article"
            );


        card.className =
            "card";


        const title =

            type === "privacy"
                ? "Privacy Policy"

            : type === "terms"
                ? "Terms & Conditions"

            : type === "cookies"
                ? "Cookie Policy"

            : "Legal / Other Policy";


        const content =
            String(
                policy?.content ||
                policy?.text ||
                ""
            );


        card.innerHTML = `

            <div class="card-title">
                ${escapeHtml(title)}
            </div>

            <div class="meta">
                ${content.length.toLocaleString()}
                characters extracted
            </div>

            <div class="url">
                ${escapeHtml(
                    policy?.url ||
                    ""
                )}
            </div>

            <div class="preview">
                ${escapeHtml(
                    content.slice(
                        0,
                        1200
                    )
                )}
            </div>

            <div class="source">
                Source:
                ${escapeHtml(
                    policy?.source ||
                    "browser"
                )}
            </div>

        `;


        els.policies.appendChild(
            card
        );

    }


    els.termsCount.textContent =
        counts.terms;


    els.privacyCount.textContent =
        counts.privacy;


    els.cookiesCount.textContent =
        counts.cookies;


    els.legalCount.textContent =
        counts.legal;


    return safePolicies;

}


/* ============================================================
 * RENDER AGENT 2
 * ========================================================== */

function renderAgent2(
    result
) {

    const clauses =
        Array.isArray(
            result?.clauses
        )
            ? result.clauses
            : [];


    const summary =
        result?.summary ||
        {};


    const overallRisk =
        result?.overall_risk ||
        summary.overall_risk ||
        "UNAVAILABLE";


    els.agent2Status.textContent =
        result?.status ||
        "Complete";


    els.overallRisk.textContent =
        overallRisk;


    els.clauseCount.textContent =
        String(
            clauses.length
        );


    const findings =
        Array.isArray(
            summary.key_findings
        )
            ? summary.key_findings

        : Array.isArray(
            result?.key_findings
        )
            ? result.key_findings

        : [];


    els.keyFindings.innerHTML =
        findings.length

            ? findings
                .map(
                    item =>
                        `<li>${
                            escapeHtml(
                                item
                            )
                        }</li>`
                )
                .join("")

            : "<li>No high-priority findings were returned.</li>";


    els.clauses.innerHTML =
        "";


    for (
        const clause of clauses
    ) {

        const card =
            document.createElement(
                "article"
            );


        card.className =
            "card";


        const riskLevel =
            clause?.risk_level ||
            "LOW";


        const riskScore =
            Number(
                clause?.risk_score ||
                0
            );


        card.innerHTML = `

            <div class="clause-title">
                ${escapeHtml(
                    clause?.title ||
                    "Clause"
                )}
            </div>

            <div class="meta">
                ${escapeHtml(
                    riskLevel
                )}
                &middot; score
                ${riskScore}/100
                &middot;
                ${escapeHtml(
                    clause?.document_type ||
                    ""
                )}
            </div>

            <div class="clause-label">
                SUMMARY
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.summary ||
                    ""
                )}
            </div>

            <div class="clause-label">
                WHY IT MATTERS
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.explanation ||
                    ""
                )}
            </div>

            <div class="clause-label">
                OBLIGATIONS
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.obligations ||
                    ""
                )}
            </div>

            <div class="clause-label">
                PERMISSIONS
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.permissions ||
                    ""
                )}
            </div>

            <div class="clause-label">
                RESTRICTIONS
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.restrictions ||
                    ""
                )}
            </div>

            <div class="clause-label">
                CONSEQUENCES
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.consequences ||
                    ""
                )}
            </div>

            <div class="clause-label">
                RISK REASON
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.risk_reason ||
                    ""
                )}
            </div>

            <div class="clause-label">
                SOURCE
            </div>

            <div class="clause-text">
                ${escapeHtml(
                    clause?.source_text ||
                    ""
                )}
            </div>

        `;


        els.clauses.appendChild(
            card
        );

    }


    if (
        !clauses.length
    ) {

        els.clauses.innerHTML =
            '<div class="card">No clauses were returned.</div>';

    }

}



/* ============================================================
 * RENDER AGENT 3
 * ========================================================== */

function renderAgent3(result) {

    ensureAgent3UI();

    if (!els.agent3Status) {
        return;
    }


    const analyses =
        Array.isArray(result?.analyses)
            ? result.analyses
            : [];


    const overallRisk =
        String(
            result?.overall_risk_level ||
            result?.overall_risk ||
            "UNAVAILABLE"
        ).toUpperCase();


    const overallScore =
        Number(
            result?.overall_risk_score ??
            result?.risk_score ??
            0
        );


    const analyzedClauses =
        Number(
            result?.analyzed_clauses ??
            analyses.length
        );


    /*
     * --------------------------------------------------------
     * CREATE CLEAN USER-FACING RESULT VIEW
     * --------------------------------------------------------
     */

    let resultView =
        document.getElementById(
            "professionalRiskView"
        );


    if (!resultView) {

        resultView =
            document.createElement(
                "section"
            );

        resultView.id =
            "professionalRiskView";

        resultView.className =
            "professional-risk-view";


        /*
         * Insert before the action buttons.
         */

        const actions =
            document.querySelector(
                ".actions"
            );


        if (actions) {

            actions.parentNode.insertBefore(
                resultView,
                actions
            );

        } else {

            document.body.prepend(
                resultView
            );

        }

    }


    /*
     * --------------------------------------------------------
     * RISK LEVEL CLASS
     * --------------------------------------------------------
     */

    const riskClass =
        overallRisk
            .toLowerCase()
            .replace(
                /[^a-z]/g,
                ""
            );


    /*
     * --------------------------------------------------------
     * FINDINGS
     * --------------------------------------------------------
     */

    const findingsHtml =
        analyses.map(
            (analysis, index) => {

                const riskLevel =
                    String(
                        analysis?.risk_level ||
                        analysis?.risk ||
                        "LOW"
                    ).toUpperCase();


                const riskScore =
                    Number(
                        analysis?.risk_score ??
                        analysis?.score ??
                        0
                    );


                const riskType =
                    analysis?.category ||
                    analysis?.clause_category ||
                    analysis?.type ||
                    "General";


                const title =
                    analysis?.title ||
                    analysis?.clause_title ||
                    analysis?.name ||
                    "Policy clause";


                const summary =
                    analysis?.summary ||
                    analysis?.plain_language ||
                    analysis?.what_it_means ||
                    analysis?.explanation ||
                    "No summary available.";


                const explanation =
                    analysis?.explanation ||
                    analysis?.plain_language ||
                    analysis?.what_it_means ||
                    "";


                const whyItMatters =
                    analysis?.why_it_matters ||
                    analysis?.reason ||
                    "";


                const userImpact =
                    analysis?.user_impact ||
                    analysis?.impact ||
                    "";


                const recommendation =
                    analysis?.recommendation ||
                    "";


                const evidence =
                    analysis?.evidence ||
                    analysis?.risk_reason ||
                    "";


                const safeId =
                    `risk-detail-${index}`;


                return `

                    <article
                        class="professional-risk-card"
                    >

                        <div
                            class="professional-risk-header"
                        >

                            <span
                                class="professional-risk-badge ${escapeHtml(riskLevel.toLowerCase())}"
                            >
                                ${escapeHtml(riskLevel)} RISK
                            </span>

                            <span
                                class="professional-risk-score"
                            >
                                ${escapeHtml(riskScore)}/100
                            </span>

                        </div>


                        <h3>
                            ${escapeHtml(title)}
                        </h3>


                        <div
                            class="professional-risk-type"
                        >
                            Risk type:
                            <strong>
                                ${escapeHtml(riskType)}
                            </strong>
                        </div>


                        <p
                            class="professional-risk-summary"
                        >
                            ${escapeHtml(summary)}
                        </p>


                        <details
                            class="professional-risk-details"
                            id="${safeId}"
                        >

                            <summary>
                                View explanation
                            </summary>


                            ${
                                explanation
                                    ? `
                                        <div class="professional-detail-block">

                                            <span>
                                                EXPLANATION
                                            </span>

                                            <p>
                                                ${escapeHtml(
                                                    explanation
                                                )}
                                            </p>

                                        </div>
                                    `
                                    : ""
                            }


                            ${
                                whyItMatters
                                    ? `
                                        <div class="professional-detail-block">

                                            <span>
                                                WHY IT MATTERS
                                            </span>

                                            <p>
                                                ${escapeHtml(
                                                    whyItMatters
                                                )}
                                            </p>

                                        </div>
                                    `
                                    : ""
                            }


                            ${
                                userImpact
                                    ? `
                                        <div class="professional-detail-block">

                                            <span>
                                                USER IMPACT
                                            </span>

                                            <p>
                                                ${escapeHtml(
                                                    userImpact
                                                )}
                                            </p>

                                        </div>
                                    `
                                    : ""
                            }


                            ${
                                recommendation
                                    ? `
                                        <div class="professional-detail-block">

                                            <span>
                                                WHAT TO CONSIDER
                                            </span>

                                            <p>
                                                ${escapeHtml(
                                                    recommendation
                                                )}
                                            </p>

                                        </div>
                                    `
                                    : ""
                            }


                            ${
                                evidence
                                    ? `
                                        <div class="professional-detail-block">

                                            <span>
                                                RISK REASON
                                            </span>

                                            <p>
                                                ${escapeHtml(
                                                    evidence
                                                )}
                                            </p>

                                        </div>
                                    `
                                    : ""
                            }

                        </details>

                    </article>

                `;

            }
        ).join("");


    /*
     * --------------------------------------------------------
     * POLICY COUNT
     * --------------------------------------------------------
     */

    const policyCountElement =
        document.getElementById(
            "finalPolicyCount"
        );


    const policyCount =
        policyCountElement
            ? policyCountElement.textContent
            : (
                document.getElementById(
                    "policyCount"
                )?.textContent ||
                "0"
            );


    /*
     * --------------------------------------------------------
     * FINAL VIEW
     * --------------------------------------------------------
     */

    resultView.innerHTML = `

        <div
            class="professional-page-header"
        >

            <div>

                <span
                    class="professional-eyebrow"
                >
                    T&C ANALYZER
                </span>

                <h2>
                    Terms & Conditions Risk
                </h2>

                <p>
                    ${escapeHtml(
                        policyCount
                    )}
                    policies analyzed
                    ·
                    ${escapeHtml(
                        analyzedClauses
                    )}
                    risk findings
                </p>

            </div>

        </div>


        <div
            class="professional-overall-card ${escapeHtml(riskClass)}"
        >

            <div>

                <span>
                    OVERALL RISK
                </span>

                <strong>
                    ${escapeHtml(
                        overallRisk
                    )}
                </strong>

            </div>


            <div
                class="professional-overall-score"
            >

                <strong>
                    ${escapeHtml(
                        overallScore
                    )}
                </strong>

                <span>
                    /100
                </span>

            </div>

        </div>


        <div
            class="professional-section-title"
        >
            Risk Findings
        </div>


        <div
            class="professional-risk-list"
        >

            ${
                findingsHtml ||
                `
                    <div
                        class="professional-empty"
                    >
                        No risk findings were returned.
                    </div>
                `
            }

        </div>

    `;


    /*
     * --------------------------------------------------------
     * HIDE ALL OLD AGENT OUTPUT
     * --------------------------------------------------------
     *
     * Agent 1 and Agent 2 continue running, but their
     * intermediate results are not presented to users.
     */

    const hideIds = [

        "agent1Status",
        "agent2Status",

        "termsCount",
        "privacyCount",
        "cookiesCount",
        "legalCount",

        "policyCount",
        "policies",

        "overallRisk",
        "keyFindings",
        "clauseCount",
        "clauses",

        "agent3Status",
        "agent3OverallRisk",
        "agent3OverallScore",
        "agent3ClauseCount",
        "agent3Warnings",
        "agent3Analyses"

    ];


    for (
        const id of hideIds
    ) {

        const element =
            document.getElementById(id);

        if (element) {

            element.style.display =
                "none";

        }

    }


    /*
     * Hide the old panels completely.
     */

    const panels =
        document.querySelectorAll(
            ".panel"
        );


    for (
        const panel of panels
    ) {

        if (
            panel !== resultView &&
            !panel.contains(resultView)
        ) {

            panel.style.display =
                "none";

        }

    }

}

/* ============================================================
 * HTML ESCAPING
 * ========================================================== */

function escapeHtml(
    value
) {

    return String(
        value ?? ""
    )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );

}


/* ============================================================
 * RUN ANALYSIS
 * ========================================================== */

async function run() {

    /*
     * HARD SINGLE-FLIGHT LOCK
     *
     * This prevents two Agent 1 requests from being
     * created when the user clicks repeatedly.
     */

    if (
        analysisRunning
    ) {

        console.warn(
            "[T&C] Analysis already running. Ignoring duplicate request."
        );

        return;

    }


    setRunningState(
        true
    );


    resetUI();


    try {

        /* ----------------------------------------------------
         * STEP 1: SOURCE TAB
         * -------------------------------------------------- */

        const tab =
            await getTab();


        currentTabId =
            tab.id;


        currentTabUrl =
            tab.url;


        els.pageTitle.textContent =
            tab.title ||
            tab.url ||
            "Current webpage";


        console.log(
            "[T&C] Source tab:",
            {
                id:
                    tab.id,

                url:
                    tab.url,

                title:
                    tab.title
            }
        );


        /* ----------------------------------------------------
         * STEP 2: BACKEND
         * -------------------------------------------------- */

        if (
            !(await health())
        ) {

            throw new Error(
                "Start FastAPI on port 8001 first."
            );

        }


        /* ----------------------------------------------------
         * STEP 3: BROWSER COLLECTION
         * -------------------------------------------------- */

        els.agent1Status.textContent =
            "Collecting browser data";


        const browser =
            await browserData(
                currentTabId
            );


        console.log(
            "[T&C] DATA FROM CHROME:",
            {
                policyLinks:
                    Array.isArray(
                        browser?.browser_links
                    )
                        ? browser.browser_links.length
                        : 0,

                documents:
                    Array.isArray(
                        browser?.browser_documents
                    )
                        ? browser.browser_documents.length
                        : 0,

                allLinks:
                    Array.isArray(
                        browser?.browser_all_links
                    )
                        ? browser.browser_all_links.length
                        : 0,

                pageText:
                    String(
                        browser?.browser_page_text ||
                        ""
                    ).length
            }
        );


        /* ----------------------------------------------------
         * STEP 4: AGENT 1
         * -------------------------------------------------- */

        els.agent1Status.textContent =
            "Extracting policies";


        const a1 =
            await post(
                "/api/agent1/analyze",
                {

                    url:
                        currentTabUrl,

                    browser_links:
                        browser?.browser_links ||
                        [],

                    browser_documents:
                        browser?.browser_documents ||
                        [],

                    browser_all_links:
                        browser?.browser_all_links ||
                        [],

                    browser_page_text:
                        browser?.browser_page_text ||
                        "",

                    browser_title:
                        browser?.title ||
                        tab.title ||
                        ""

                }
            );


        /*
         * Ignore stale responses.
         */

        if (
            !analysisRunning
        ) {

            return;

        }


        currentRunId =
            a1?.run_id ||
            null;


        const agent1 =
            a1?.agent1 ||
            a1 ||
            {};


        const policies =
            Array.isArray(
                agent1.policy_pages
            )
                ? agent1.policy_pages
                : [];


        console.log(
            "[T&C] AGENT 1 RESULT:",
            {
                runId:
                    currentRunId,

                policies:
                    policies.length
            }
        );


        renderPolicies(
            policies
        );


        if (
            policies.length === 0
        ) {

            els.agent1Status.textContent =
                "No policies found";


            els.agent2Status.textContent =
                "Skipped";


            els.overallRisk.textContent =
                "UNAVAILABLE";


            els.keyFindings.innerHTML =
                "<li>No supported policy document could be extracted from this page.</li>";


            return;

        }


        els.agent1Status.textContent =
            "Complete";


        /* ----------------------------------------------------
         * STEP 5: AGENT 2
         * -------------------------------------------------- */

        if (
            !currentRunId
        ) {

            throw new Error(
                "Agent 1 completed without a run ID."
            );

        }


        els.agent2Status.textContent =
            "Analyzing";


        els.overallRisk.textContent =
            "ANALYZING";


        const a2 =
            await post(
                "/api/agent2/analyze",
                {
                    run_id:
                        currentRunId
                }
            );


        if (
            !analysisRunning
        ) {

            return;

        }


        renderAgent2(
            a2?.agent2 ||
            a2 ||
            {}
        );




        /* ----------------------------------------------------
         * STEP 6: AGENT 3
         * -------------------------------------------------- */

        ensureAgent3UI();


        if (els.agent3Status) {

            els.agent3Status.textContent =
                "Analyzing";

        }


        console.log(
            "[T&C] Starting Agent 3:",
            {
                runId:
                    currentRunId
            }
        );


        const a3 =
            await post(
                "/api/agent3/analyze",
                {
                    run_id:
                        currentRunId
                }
            );


        if (
            !analysisRunning
        ) {

            return;

        }


        console.log(
            "[T&C] AGENT 3 RESULT:",
            a3
        );


        renderAgent3(
            a3?.agent3 ||
            a3 ||
            {}
        );


    } catch (
        error
    ) {

        console.error(
            "[T&C] Analysis error:",
            error
        );


        els.agent1Status.textContent =
            "Error";


        els.agent2Status.textContent =
            "Stopped";


        els.overallRisk.textContent =
            "ERROR";


        els.keyFindings.innerHTML =
            `<li>${
                escapeHtml(
                    error?.message ||
                    String(error)
                )
            }</li>`;

    } finally {

        setRunningState(
            false
        );

    }

}


/* ============================================================
 * BUTTON EVENTS
 * ========================================================== */

els.analyze.addEventListener(
    "click",
    () => {

        run();

    }
);


els.reanalyze.addEventListener(
    "click",
    () => {

        if (
            analysisRunning
        ) {

            return;

        }

        run();

    }
);


/* ============================================================
 * INITIAL POPUP STATE
 *
 * IMPORTANT:
 * We DO NOT automatically run analysis here.
 *
 * The user must explicitly click Run Analysis.
 * This prevents duplicate Agent 1 requests.
 * ========================================================== */

(async () => {

    try {

        const tab =
            await getTab();


        currentTabId =
            tab.id;


        currentTabUrl =
            tab.url;


        els.pageTitle.textContent =
            tab.title ||
            tab.url ||
            "Current webpage";


        await health();


        els.agent1Status.textContent =
            "Ready";


        els.agent2Status.textContent =
            "Ready";


        els.overallRisk.textContent =
            "READY";


        els.keyFindings.innerHTML =
            "<li>Click Run Analysis to scan this webpage.</li>";


    } catch (
        error
    ) {

        console.error(
            "[T&C] Popup initialization error:",
            error
        );


        els.connectionStatus.textContent =
            "Unable to access page";


        els.agent1Status.textContent =
            "Unavailable";


        els.agent2Status.textContent =
            "Stopped";


        els.overallRisk.textContent =
            "UNAVAILABLE";


        els.keyFindings.innerHTML =
            `<li>${
                escapeHtml(
                    error?.message ||
                    String(error)
                )
            }</li>`;

    }

})();
