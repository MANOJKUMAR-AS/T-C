// ============================================================
// T&C ANALYZER - POPUP
// Agent 1 + Agent 2 Frontend
// ============================================================


// ============================================================
// CONFIGURATION
// ============================================================

const BACKEND_URL = "http://127.0.0.1:8000";

const ANALYZE_ENDPOINT =
    `${BACKEND_URL}/api/analyze`;


// ============================================================
// DOM ELEMENTS
// ============================================================

// ------------------------------------------------------------
// Connection
// ------------------------------------------------------------

const connectionStatus =
    document.getElementById("connectionStatus");


// ------------------------------------------------------------
// Current page
// ------------------------------------------------------------

const pageTitle =
    document.getElementById("pageTitle");

const pageUrl =
    document.getElementById("pageUrl");


// ------------------------------------------------------------
// Agent 1
// ------------------------------------------------------------

const agentBadge =
    document.getElementById("agentBadge");

const policyCount =
    document.getElementById("policyCount");

const agentMessage =
    document.getElementById("agentMessage");

const progressBar =
    document.getElementById("progressBar");


// ------------------------------------------------------------
// Policy discovery
// ------------------------------------------------------------

const discoveryStatus =
    document.getElementById("discoveryStatus");

const termsCount =
    document.getElementById("termsCount");

const privacyCount =
    document.getElementById("privacyCount");

const cookiesCount =
    document.getElementById("cookiesCount");

const termsCard =
    document.getElementById("termsCard");

const privacyCard =
    document.getElementById("privacyCard");

const cookiesCard =
    document.getElementById("cookiesCard");


// ------------------------------------------------------------
// Agent 1 results
// ------------------------------------------------------------

const resultCount =
    document.getElementById("resultCount");

const results =
    document.getElementById("results");


// ------------------------------------------------------------
// Agent 2
// ------------------------------------------------------------

const agent2Status =
    document.getElementById("agent2Status");

const overallRisk =
    document.getElementById("overallRisk");

const overallRiskValue =
    document.getElementById("overallRiskValue");

const keyFindings =
    document.getElementById("keyFindings");

const clauses =
    document.getElementById("clauses");

const clauseCount =
    document.getElementById("clauseCount");


// ------------------------------------------------------------
// Actions
// ------------------------------------------------------------

const analyzeButton =
    document.getElementById("analyze");

const reanalyzeButton =
    document.getElementById("reanalyze");


// ============================================================
// STATE
// ============================================================

let currentTab = null;

let analysisRunning = false;


// ============================================================
// UTILITY
// ============================================================

function sleep(milliseconds) {

    return new Promise(
        resolve => setTimeout(resolve, milliseconds)
    );

}


// ============================================================
// HTML ESCAPING
// ============================================================
//
// Important because Agent 2 text comes from an LLM.
// Never directly inject model-generated text into HTML
// without escaping it first.
// ============================================================

function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");

}


// ============================================================
// NORMALIZE VALUE
// ============================================================

function safeText(value, fallback = "") {

    if (
        value === null ||
        value === undefined
    ) {

        return fallback;

    }

    return String(value);

}


// ============================================================
// CURRENT TAB
// ============================================================

async function getCurrentTab() {

    const tabs =
        await chrome.tabs.query({
            active: true,
            currentWindow: true
        });

    if (!tabs || tabs.length === 0) {

        throw new Error(
            "Unable to determine the current browser tab."
        );

    }

    return tabs[0];

}


// ============================================================
// DISPLAY CURRENT PAGE
// ============================================================

function displayCurrentPage(tab) {

    currentTab = tab;

    const title =
        tab?.title ||
        "Current page";

    const url =
        tab?.url ||
        "";

    pageTitle.textContent = title;

    pageUrl.textContent = url;

}


// ============================================================
// CONNECTION STATUS
// ============================================================

function setConnectionStatus(
    state,
    message
) {

    connectionStatus.classList.remove(
        "checking",
        "connected",
        "disconnected",
        "error"
    );

    connectionStatus.classList.add(state);

    const dot =
        connectionStatus.querySelector(
            ".status-dot"
        );

    if (dot) {

        dot.className =
            `status-dot ${state}`;

    }

    connectionStatus.childNodes[
        connectionStatus.childNodes.length - 1
    ].textContent =
        ` ${message}`;

}


// ============================================================
// CHECK BACKEND
// ============================================================

async function checkBackend() {

    setConnectionStatus(
        "checking",
        "Connecting"
    );

    try {

        const response =
            await fetch(
                `${BACKEND_URL}/`,
                {
                    method: "GET"
                }
            );

        if (!response.ok) {

            throw new Error(
                `Backend returned HTTP ${response.status}`
            );

        }

        const data =
            await response.json();

        if (
            data &&
            data.status === "running"
        ) {

            setConnectionStatus(
                "connected",
                "Connected"
            );

            return true;

        }

        throw new Error(
            "Backend returned an unexpected response."
        );

    } catch (error) {

        console.error(
            "Backend connection failed:",
            error
        );

        setConnectionStatus(
            "disconnected",
            "Backend offline"
        );

        return false;

    }

}


// ============================================================
// RESET AGENT 1 UI
// ============================================================

function resetAgent1UI() {

    agentBadge.textContent =
        "WAITING";

    agentBadge.className =
        "agent-badge waiting";

    policyCount.textContent =
        "-";

    agentMessage.textContent =
        "Agent 1 is waiting to analyze the current page.";

    progressBar.style.width =
        "0%";

    discoveryStatus.textContent =
        "Waiting";

    resultCount.textContent =
        "0 results";

    termsCount.textContent =
        "0";

    privacyCount.textContent =
        "0";

    cookiesCount.textContent =
        "0";

    termsCard.classList.remove(
        "active"
    );

    privacyCard.classList.remove(
        "active"
    );

    cookiesCard.classList.remove(
        "active"
    );

    results.innerHTML = `
        <div class="empty-state">

            <div class="empty-icon">
                ◌
            </div>

            <h3>
                No analysis yet
            </h3>

            <p>
                Run the analysis to discover
                policy pages on this website.
            </p>

        </div>
    `;

}


// ============================================================
// RESET AGENT 2 UI
// ============================================================

function resetAgent2UI() {

    agent2Status.textContent =
        "Waiting";

    overallRisk.className =
        "risk-card";

    overallRiskValue.textContent =
        "-";

    keyFindings.innerHTML = `
        <li>
            Waiting for Agent 2 analysis...
        </li>
    `;

    clauseCount.textContent =
        "0";

    clauses.innerHTML = `
        <div class="empty-state">

            <div class="empty-icon">
                ◌
            </div>

            <h3>
                No clause analysis yet
            </h3>

            <p>
                Agent 2 results will appear
                here after policy extraction.
            </p>

        </div>
    `;

}


// ============================================================
// RESET ALL UI
// ============================================================

function resetUI() {

    resetAgent1UI();

    resetAgent2UI();

}


// ============================================================
// AGENT 1: START STATE
// ============================================================

function setAgent1Running() {

    agentBadge.textContent =
        "RUNNING";

    agentBadge.className =
        "agent-badge running";

    policyCount.textContent =
        "...";

    agentMessage.textContent =
        "Discovering policy pages...";

    discoveryStatus.textContent =
        "Searching";

    progressBar.style.width =
        "25%";

}


// ============================================================
// AGENT 1: SUCCESS STATE
// ============================================================

function setAgent1Complete(count) {

    agentBadge.textContent =
        "COMPLETE";

    agentBadge.className =
        "agent-badge complete";

    policyCount.textContent =
        String(count);

    agentMessage.textContent =
        count > 0
            ? "Policy pages discovered successfully."
            : "No policy pages were found.";

    discoveryStatus.textContent =
        count > 0
            ? "Complete"
            : "None found";

    progressBar.style.width =
        "100%";

}


// ============================================================
// AGENT 1: ERROR STATE
// ============================================================

function setAgent1Error(message) {

    agentBadge.textContent =
        "ERROR";

    agentBadge.className =
        "agent-badge error";

    policyCount.textContent =
        "0";

    agentMessage.textContent =
        message;

    discoveryStatus.textContent =
        "Failed";

    progressBar.style.width =
        "0%";

}


// ============================================================
// UPDATE POLICY COUNTS
// ============================================================

function updatePolicyCounts(
    policyPages
) {

    let terms = 0;
    let privacy = 0;
    let cookies = 0;

    for (
        const policy of policyPages
    ) {

        const type =
            safeText(
                policy?.type
            ).toLowerCase();

        if (type === "terms") {

            terms++;

        } else if (
            type === "privacy"
        ) {

            privacy++;

        } else if (
            type === "cookies"
        ) {

            cookies++;

        }

    }

    termsCount.textContent =
        String(terms);

    privacyCount.textContent =
        String(privacy);

    cookiesCount.textContent =
        String(cookies);


    termsCard.classList.toggle(
        "active",
        terms > 0
    );

    privacyCard.classList.toggle(
        "active",
        privacy > 0
    );

    cookiesCard.classList.toggle(
        "active",
        cookies > 0
    );

}


// ============================================================
// RENDER AGENT 1 RESULTS
// ============================================================

function renderAgent1Results(
    policyPages
) {

    if (
        !Array.isArray(policyPages) ||
        policyPages.length === 0
    ) {

        resultCount.textContent =
            "0 results";

        results.innerHTML = `
            <div class="empty-state">

                <div class="empty-icon">
                    ◌
                </div>

                <h3>
                    No policy pages found
                </h3>

                <p>
                    Agent 1 could not find
                    usable policy pages.
                </p>

            </div>
        `;

        return;

    }


    resultCount.textContent =
        `${policyPages.length} result${
            policyPages.length === 1
                ? ""
                : "s"
        }`;


    results.innerHTML =
        policyPages
            .map(
                (
                    policy,
                    index
                ) => {

                    const type =
                        safeText(
                            policy?.type,
                            "unknown"
                        );

                    const url =
                        safeText(
                            policy?.url,
                            ""
                        );

                    const content =
                        safeText(
                            policy?.content,
                            ""
                        );

                    const source =
                        safeText(
                            policy?.source,
                            ""
                        );

                    const preview =
                        content.length > 220
                            ? `${content.substring(0, 220)}...`
                            : content;


                    return `
                        <div class="result-card">

                            <div class="result-header">

                                <span class="result-index">
                                    ${index + 1}
                                </span>

                                <span class="result-type">
                                    ${escapeHtml(
                                        type.toUpperCase()
                                    )}
                                </span>

                            </div>


                            <h3>
                                ${escapeHtml(
                                    type
                                )}
                            </h3>


                            <p class="result-url">
                                ${escapeHtml(
                                    url
                                )}
                            </p>


                            ${
                                source
                                    ? `
                                        <span class="result-source">
                                            ${escapeHtml(
                                                source
                                            )}
                                        </span>
                                      `
                                    : ""
                            }


                            ${
                                preview
                                    ? `
                                        <p class="result-preview">
                                            ${escapeHtml(
                                                preview
                                            )}
                                        </p>
                                      `
                                    : `
                                        <p class="result-preview muted">
                                            Policy content extracted.
                                        </p>
                                      `
                            }

                        </div>
                    `;

                }
            )
            .join("");

}


// ============================================================
// AGENT 2: RUNNING STATE
// ============================================================

function setAgent2Running() {

    agent2Status.textContent =
        "Analyzing";

    overallRisk.className =
        "risk-card";

    overallRiskValue.textContent =
        "...";

    keyFindings.innerHTML = `
        <li>
            Agent 2 is analyzing the extracted policy.
        </li>
    `;

    clauseCount.textContent =
        "Analyzing";

    clauses.innerHTML = `
        <div class="empty-state">

            <div class="empty-icon">
                ◌
            </div>

            <h3>
                Analyzing clauses...
            </h3>

            <p>
                Agent 2 is processing the
                extracted policy text.
            </p>

        </div>
    `;

}


// ============================================================
// NORMALIZE RISK
// ============================================================

function normalizeRisk(
    risk
) {

    const value =
        safeText(
            risk,
            "unknown"
        )
        .trim()
        .toLowerCase();

    if (
        [
            "low",
            "medium",
            "high",
            "critical"
        ].includes(value)
    ) {

        return value;

    }

    return "unknown";

}


// ============================================================
// RENDER OVERALL RISK
// ============================================================

function renderOverallRisk(
    risk
) {

    const normalized =
        normalizeRisk(risk);

    overallRisk.className =
        "risk-card";


    if (
        [
            "low",
            "medium",
            "high",
            "critical"
        ].includes(normalized)
    ) {

        overallRisk.classList.add(
            `risk-${normalized}`
        );

    }


    overallRiskValue.textContent =
        normalized === "unknown"
            ? "Unknown"
            : normalized.toUpperCase();

}


// ============================================================
// RENDER KEY FINDINGS
// ============================================================

function renderKeyFindings(
    findings
) {

    if (
        !Array.isArray(findings) ||
        findings.length === 0
    ) {

        keyFindings.innerHTML = `
            <li>
                No key findings were returned.
            </li>
        `;

        return;

    }


    keyFindings.innerHTML =
        findings
            .map(
                finding => `
                    <li>
                        ${escapeHtml(
                            safeText(finding)
                        )}
                    </li>
                `
            )
            .join("");

}


// ============================================================
// RENDER ARRAY FIELD
// ============================================================

function renderClauseList(
    title,
    items
) {

    if (
        !Array.isArray(items) ||
        items.length === 0
    ) {

        return "";

    }


    return `
        <div class="clause-list">

            <strong>
                ${escapeHtml(title)}
            </strong>

            <ul>

                ${items
                    .map(
                        item => `
                            <li>
                                ${escapeHtml(
                                    safeText(item)
                                )}
                            </li>
                        `
                    )
                    .join("")
                }

            </ul>

        </div>
    `;

}


// ============================================================
// RENDER SINGLE CLAUSE
// ============================================================

function renderClause(
    clause,
    index
) {

    const clauseId =
        safeText(
            clause?.clause_id,
            `C${index + 1}`
        );

    const title =
        safeText(
            clause?.title,
            "Untitled Clause"
        );

    const category =
        safeText(
            clause?.category,
            "other"
        );

    const summary =
        safeText(
            clause?.summary,
            "No summary provided."
        );

    const explanation =
        safeText(
            clause?.explanation,
            ""
        );

    const risk =
        normalizeRisk(
            clause?.risk_level
        );

    const riskReason =
        safeText(
            clause?.risk_reason,
            ""
        );

    const sourceText =
        safeText(
            clause?.source_text,
            ""
        );


    const obligations =
        Array.isArray(
            clause?.obligations
        )
            ? clause.obligations
            : [];

    const permissions =
        Array.isArray(
            clause?.permissions
        )
            ? clause.permissions
            : [];

    const restrictions =
        Array.isArray(
            clause?.restrictions
        )
            ? clause.restrictions
            : [];

    const consequences =
        Array.isArray(
            clause?.consequences
        )
            ? clause.consequences
            : [];


    return `
        <article class="clause-card">


            <!-- CLAUSE HEADER -->

            <div class="clause-header">

                <div>

                    <span class="clause-id">
                        ${escapeHtml(
                            clauseId
                        )}
                    </span>


                    <h4>
                        ${escapeHtml(
                            title
                        )}
                    </h4>

                </div>


                <span
                    class="risk-badge risk-${escapeHtml(
                        risk
                    )}"
                >
                    ${escapeHtml(
                        risk.toUpperCase()
                    )}
                </span>

            </div>



            <!-- CATEGORY -->

            <span class="clause-category">
                ${escapeHtml(
                    category
                )}
            </span>



            <!-- SUMMARY -->

            <p class="clause-summary">
                ${escapeHtml(
                    summary
                )}
            </p>



            <!-- EXPLANATION -->

            ${
                explanation
                    ? `
                        <div class="clause-explanation">

                            <strong>
                                Explanation
                            </strong>

                            <p>
                                ${escapeHtml(
                                    explanation
                                )}
                            </p>

                        </div>
                      `
                    : ""
            }



            <!-- RISK REASON -->

            ${
                riskReason
                    ? `
                        <div class="clause-risk-reason">

                            <strong>
                                Why this risk?
                            </strong>

                            <p>
                                ${escapeHtml(
                                    riskReason
                                )}
                            </p>

                        </div>
                      `
                    : ""
            }



            <!-- STRUCTURED DETAILS -->

            ${
                obligations.length > 0 ||
                permissions.length > 0 ||
                restrictions.length > 0 ||
                consequences.length > 0
                    ? `
                        <div class="clause-details">

                            ${renderClauseList(
                                "Obligations",
                                obligations
                            )}

                            ${renderClauseList(
                                "Permissions",
                                permissions
                            )}

                            ${renderClauseList(
                                "Restrictions",
                                restrictions
                            )}

                            ${renderClauseList(
                                "Consequences",
                                consequences
                            )}

                        </div>
                      `
                    : ""
            }



            <!-- SOURCE TEXT -->

            ${
                sourceText
                    ? `
                        <details>

                            <summary>
                                View source text
                            </summary>

                            <p class="source-text">
                                ${escapeHtml(
                                    sourceText
                                )}
                            </p>

                        </details>
                      `
                    : ""
            }


        </article>
    `;

}


// ============================================================
// RENDER CLAUSES
// ============================================================

function renderClauses(
    clauseList
) {

    if (
        !Array.isArray(clauseList) ||
        clauseList.length === 0
    ) {

        clauseCount.textContent =
            "0";

        clauses.innerHTML = `
            <div class="empty-state">

                <div class="empty-icon">
                    ◌
                </div>

                <h3>
                    No clauses found
                </h3>

                <p>
                    Agent 2 did not return
                    any clause-level analysis.
                </p>

            </div>
        `;

        return;

    }


    clauseCount.textContent =
        `${clauseList.length} clause${
            clauseList.length === 1
                ? ""
                : "s"
        }`;


    clauses.innerHTML =
        clauseList
            .map(
                (
                    clause,
                    index
                ) =>
                    renderClause(
                        clause,
                        index
                    )
            )
            .join("");

}


// ============================================================
// RENDER AGENT 2 ANALYSIS
// ============================================================

function renderAgent2Analysis(
    analysis
) {

    if (
        !analysis ||
        typeof analysis !== "object"
    ) {

        throw new Error(
            "Agent 2 returned no valid analysis."
        );

    }


    const documentType =
        safeText(
            analysis.document_type,
            "Document"
        );

    const risk =
        safeText(
            analysis.overall_risk,
            "unknown"
        );

    const findings =
        Array.isArray(
            analysis.key_findings
        )
            ? analysis.key_findings
            : [];

    const clauseList =
        Array.isArray(
            analysis.clauses
        )
            ? analysis.clauses
            : [];


    agent2Status.textContent =
        `${documentType}`;


    renderOverallRisk(
        risk
    );


    renderKeyFindings(
        findings
    );


    renderClauses(
        clauseList
    );

}


// ============================================================
// AGENT 2 COMPLETE
// ============================================================

function setAgent2Complete(
    analysisCount
) {

    agent2Status.textContent =
        analysisCount > 0
            ? "Complete"
            : "No analysis";


    if (analysisCount === 0) {

        overallRiskValue.textContent =
            "-";

    }

}


// ============================================================
// AGENT 2 ERROR
// ============================================================

function setAgent2Error(
    message
) {

    agent2Status.textContent =
        "Error";

    overallRisk.className =
        "risk-card";

    overallRiskValue.textContent =
        "ERROR";

    keyFindings.innerHTML = `
        <li>
            ${escapeHtml(
                message
            )}
        </li>
    `;

    clauseCount.textContent =
        "0";

    clauses.innerHTML = `
        <div class="empty-state">

            <div class="empty-icon">
                !
            </div>

            <h3>
                Agent 2 analysis failed
            </h3>

            <p>
                ${escapeHtml(
                    message
                )}
            </p>

        </div>
    `;

}


// ============================================================
// FIND FIRST SUCCESSFUL ANALYSIS
// ============================================================
//
// Agent 1 can discover multiple policies.
// Agent 2 can therefore return multiple analyses.
// The UI displays the first successful analysis while
// preserving all Agent 1 results.
// ============================================================

function findSuccessfulAnalysis(
    analyses
) {

    if (
        !Array.isArray(analyses)
    ) {

        return null;

    }


    for (
        const item of analyses
    ) {

        if (
            item &&
            item.analysis &&
            typeof item.analysis === "object"
        ) {

            return item;

        }

    }


    return null;

}


// ============================================================
// GET ANALYSIS ERROR
// ============================================================

function getAnalysisError(
    analyses
) {

    if (
        !Array.isArray(analyses)
    ) {

        return null;

    }


    for (
        const item of analyses
    ) {

        if (
            item &&
            item.error
        ) {

            return safeText(
                item.error
            );

        }

    }


    return null;

}


// ============================================================
// RUN FULL ANALYSIS
// ============================================================

async function runAnalysis() {

    if (analysisRunning) {

        return;

    }


    analysisRunning = true;


    analyzeButton.disabled =
        true;

    reanalyzeButton.disabled =
        true;


    try {

        // ----------------------------------------------------
        // Get current tab
        // ----------------------------------------------------

        const tab =
            await getCurrentTab();

        displayCurrentPage(
            tab
        );


        const url =
            safeText(
                tab?.url
            ).trim();


        if (!url) {

            throw new Error(
                "The current tab does not contain a valid URL."
            );

        }


        // ----------------------------------------------------
        // Validate browser page
        // ----------------------------------------------------

        if (
            url.startsWith(
                "chrome://"
            ) ||
            url.startsWith(
                "chrome-extension://"
            ) ||
            url.startsWith(
                "edge://"
            ) ||
            url.startsWith(
                "about:"
            )
        ) {

            throw new Error(
                "This page cannot be analyzed. Open a normal HTTP or HTTPS website."
            );

        }


        // ----------------------------------------------------
        // Check backend
        // ----------------------------------------------------

        const backendAvailable =
            await checkBackend();


        if (!backendAvailable) {

            throw new Error(
                "Backend is not running. Start FastAPI on port 8000."
            );

        }


        // ----------------------------------------------------
        // Reset previous results
        // ----------------------------------------------------

        resetUI();


        // ----------------------------------------------------
        // Agent 1 running
        // ----------------------------------------------------

        setAgent1Running();

        setAgent2Running();


        // ----------------------------------------------------
        // Send request
        // ----------------------------------------------------

        console.log(
            "Sending analysis request:",
            url
        );


        const response =
            await fetch(
                ANALYZE_ENDPOINT,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        url: url
                    })
                }
            );


        // ----------------------------------------------------
        // Read response
        // ----------------------------------------------------

        let data = null;

        try {

            data =
                await response.json();

        } catch (error) {

            throw new Error(
                `Backend returned invalid JSON (HTTP ${response.status}).`
            );

        }


        // ----------------------------------------------------
        // HTTP error
        // ----------------------------------------------------

        if (!response.ok) {

            const detail =
                data?.detail ||
                `HTTP ${response.status}`;

            throw new Error(
                safeText(detail)
            );

        }


        console.log(
            "Backend response:",
            data
        );


        // ----------------------------------------------------
        // Agent 1 response
        // ----------------------------------------------------

        const agent1 =
            data?.agent1;


        const policyPages =
            Array.isArray(
                agent1?.policy_pages
            )
                ? agent1.policy_pages
                : [];


        updatePolicyCounts(
            policyPages
        );


        renderAgent1Results(
            policyPages
        );


        setAgent1Complete(
            policyPages.length
        );


        // ----------------------------------------------------
        // No Agent 1 policies
        // ----------------------------------------------------

        if (
            policyPages.length === 0
        ) {

            agent2Status.textContent =
                "Skipped";

            overallRisk.className =
                "risk-card";

            overallRiskValue.textContent =
                "-";

            keyFindings.innerHTML = `
                <li>
                    Agent 2 was skipped because
                    Agent 1 extracted no policy pages.
                </li>
            `;

            clauseCount.textContent =
                "0";

            clauses.innerHTML = `
                <div class="empty-state">

                    <div class="empty-icon">
                        ◌
                    </div>

                    <h3>
                        No policy content
                    </h3>

                    <p>
                        Agent 2 needs extracted
                        policy text before analysis.
                    </p>

                </div>
            `;

            return;

        }


        // ----------------------------------------------------
        // Agent 2 response
        // ----------------------------------------------------

        const agent2 =
            data?.agent2;


        const analyses =
            Array.isArray(
                agent2?.analyses
            )
                ? agent2.analyses
                : [];


        const successfulAnalysis =
            findSuccessfulAnalysis(
                analyses
            );


        // ----------------------------------------------------
        // Successful Agent 2 analysis
        // ----------------------------------------------------

        if (
            successfulAnalysis
        ) {

            renderAgent2Analysis(
                successfulAnalysis.analysis
            );


            setAgent2Complete(
                analyses.length
            );


            // If multiple analyses exist,
            // show that in the status.

            if (
                analyses.length > 1
            ) {

                agent2Status.textContent =
                    `${analyses.length} analyses`;

            }

            return;

        }


        // ----------------------------------------------------
        // Agent 2 failed
        // ----------------------------------------------------

        const agent2Error =
            getAnalysisError(
                analyses
            );


        if (
            agent2Error
        ) {

            setAgent2Error(
                agent2Error
            );

            return;

        }


        // ----------------------------------------------------
        // Agent 2 skipped
        // ----------------------------------------------------

        if (
            agent2?.status === "skipped"
        ) {

            const reason =
                safeText(
                    agent2?.reason,
                    "Agent 2 did not run."
                );

            setAgent2Error(
                reason
            );

            return;

        }


        // ----------------------------------------------------
        // Unexpected Agent 2 response
        // ----------------------------------------------------

        setAgent2Error(
            "Agent 2 returned no usable analysis."
        );

    } catch (error) {

        console.error(
            "Analysis failed:",
            error
        );


        // If Agent 1 has not completed,
        // show the error there.

        if (
            agentBadge.textContent !==
            "COMPLETE"
        ) {

            setAgent1Error(
                safeText(
                    error?.message,
                    "Analysis failed."
                )
            );

        }


        setAgent2Error(
            safeText(
                error?.message,
                "Analysis failed."
            )
        );

    } finally {

        analysisRunning =
            false;

        analyzeButton.disabled =
            false;

        reanalyzeButton.disabled =
            false;

    }

}


// ============================================================
// BUTTON EVENTS
// ============================================================

analyzeButton.addEventListener(
    "click",
    async () => {

        await runAnalysis();

    }
);


reanalyzeButton.addEventListener(
    "click",
    async () => {

        await runAnalysis();

    }
);


// ============================================================
// INITIALIZATION
// ============================================================
//
// IMPORTANT:
// Do NOT automatically run Agent 1 + Agent 2 here.
//
// Opening the popup only:
// 1. Gets the current tab.
// 2. Displays the page.
// 3. Checks backend connectivity.
//
// The user must click "Run Analysis".
// ============================================================

async function initialize() {

    try {

        const tab =
            await getCurrentTab();

        displayCurrentPage(
            tab
        );

    } catch (error) {

        console.error(
            "Could not get current tab:",
            error
        );

        pageTitle.textContent =
            "Current page unavailable";

        pageUrl.textContent =
            "";

    }


    await checkBackend();

}


// ============================================================
// START
// ============================================================

initialize();