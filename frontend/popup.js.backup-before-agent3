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


        if (
            counts[type] !== undefined
        ) {

            counts[type]++;

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
                · score
                ${riskScore}/100
                ·
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