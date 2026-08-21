const API_URL =
    "http://127.0.0.1:8000/api/agent1/analyze";


// ============================================================
// DOM
// ============================================================

const analyzeButton =
    document.getElementById("analyze");

const reanalyzeButton =
    document.getElementById("reanalyze");

const connectionStatus =
    document.getElementById("connectionStatus");

const pageTitle =
    document.getElementById("pageTitle");

const pageUrl =
    document.getElementById("pageUrl");

const agentBadge =
    document.getElementById("agentBadge");

const agentMessage =
    document.getElementById("agentMessage");

const policyCount =
    document.getElementById("policyCount");

const progressBar =
    document.getElementById("progressBar");

const discoveryStatus =
    document.getElementById("discoveryStatus");

const resultCount =
    document.getElementById("resultCount");

const results =
    document.getElementById("results");

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


// ============================================================
// GET CURRENT TAB
// ============================================================

async function getCurrentTab() {

    const tabs =
        await chrome.tabs.query({
            active: true,
            currentWindow: true
        });

    if (
        !tabs ||
        tabs.length === 0
    ) {
        throw new Error(
            "Could not determine the current tab."
        );
    }

    return tabs[0];
}


// ============================================================
// CONNECTION CHECK
// ============================================================

async function checkBackend() {

    try {

        const response =
            await fetch(
                "http://127.0.0.1:8000/",
                {
                    method: "GET"
                }
            );

        if (!response.ok) {
            throw new Error();
        }

        connectionStatus.className =
            "connection-status connected";

        connectionStatus.innerHTML =
            '<span class="status-dot"></span> Connected';

        return true;

    } catch (error) {

        connectionStatus.className =
            "connection-status error";

        connectionStatus.innerHTML =
            '<span class="status-dot"></span> Backend offline';

        return false;
    }
}


// ============================================================
// SET LOADING
// ============================================================

function setLoading(loading) {

    analyzeButton.disabled =
        loading;

    reanalyzeButton.disabled =
        loading;

    if (loading) {

        analyzeButton.textContent =
            "Running Agent 1...";

        reanalyzeButton.textContent =
            "Please wait...";

        agentBadge.className =
            "agent-badge running";

        agentBadge.textContent =
            "RUNNING";

        progressBar.className =
            "progress-bar running";

        agentMessage.textContent =
            "Discovering and extracting policy pages...";

        discoveryStatus.textContent =
            "Scanning";

    } else {

        analyzeButton.textContent =
            "Run Agent 1";

        reanalyzeButton.textContent =
            "Re-analyze";
    }
}


// ============================================================
// SET SUCCESS
// ============================================================

function setSuccess() {

    agentBadge.className =
        "agent-badge success";

    agentBadge.textContent =
        "SUCCESS";

    progressBar.className =
        "progress-bar success";

    discoveryStatus.textContent =
        "Complete";
}


// ============================================================
// SET ERROR
// ============================================================

function setError() {

    agentBadge.className =
        "agent-badge error";

    agentBadge.textContent =
        "ERROR";

    progressBar.className =
        "progress-bar";

    discoveryStatus.textContent =
        "Failed";
}


// ============================================================
// POLICY NAME
// ============================================================

function formatPolicyType(type) {

    switch (type) {

        case "terms":
            return "Terms & Conditions";

        case "privacy":
            return "Privacy Policy";

        case "cookies":
            return "Cookie Policy";

        default:
            return "Policy";
    }
}


// ============================================================
// TRUNCATE
// ============================================================

function truncate(text, maxLength) {

    if (!text) {
        return "";
    }

    if (
        text.length <= maxLength
    ) {
        return text;
    }

    return (
        text.substring(
            0,
            maxLength
        ) + "..."
    );
}


// ============================================================
// DISPLAY CURRENT PAGE
// ============================================================

function displayCurrentPage(tab) {

    const url =
        tab.url || "";

    pageUrl.textContent =
        url;


    let title =
        tab.title || "";


    if (!title) {

        try {

            title =
                new URL(url).hostname;

        } catch (error) {

            title =
                "Current website";
        }
    }


    pageTitle.textContent =
        truncate(
            title,
            42
        );
}


// ============================================================
// DISPLAY POLICY COUNTS
// ============================================================

function updatePolicyCounts(policies) {

    const terms =
        policies.filter(
            policy =>
                policy.type === "terms"
        ).length;

    const privacy =
        policies.filter(
            policy =>
                policy.type === "privacy"
        ).length;

    const cookies =
        policies.filter(
            policy =>
                policy.type === "cookies"
        ).length;


    termsCount.textContent =
        terms;

    privacyCount.textContent =
        privacy;

    cookiesCount.textContent =
        cookies;


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
// DISPLAY RESULTS
// ============================================================

function displayResults(policies) {

    results.innerHTML = "";

    resultCount.textContent =
        `${policies.length} ${
            policies.length === 1
                ? "result"
                : "results"
        }`;


    if (
        policies.length === 0
    ) {

        results.innerHTML = `
            <div class="empty-state">

                <div class="empty-icon">
                    ?
                </div>

                <h3>
                    No policy found
                </h3>

                <p>
                    Agent 1 could not find a
                    Terms, Privacy, or Cookie
                    policy on this website.
                </p>

            </div>
        `;

        return;
    }


    policies.forEach(
        policy => {

            const content =
                policy.content || "";


            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "result-card";


            card.innerHTML = `

                <div class="result-header">

                    <div class="result-type">

                        <div class="result-icon">
                            ✓
                        </div>

                        <div>

                            <h3>
                                ${formatPolicyType(
                                    policy.type
                                )}
                            </h3>

                            <p>
                                ${content.length.toLocaleString()}
                                characters extracted
                            </p>

                        </div>

                    </div>

                    <span class="found-badge">
                        FOUND
                    </span>

                </div>


                <div class="result-url">
                    ${policy.url}
                </div>


                <div class="result-preview">

                    <span class="preview-label">
                        CONTENT PREVIEW
                    </span>

                    ${truncate(
                        content,
                        450
                    )}

                </div>
            `;


            results.appendChild(
                card
            );
        }
    );
}


// ============================================================
// SHOW ERROR
// ============================================================

function showError(message) {

    setError();

    policyCount.textContent =
        "0";

    agentMessage.textContent =
        message;

    results.innerHTML = `
        <div class="error-card">
            <strong>Agent 1 error</strong>
            <br>
            ${message}
        </div>
    `;

    resultCount.textContent =
        "Error";
}


// ============================================================
// RUN AGENT 1
// ============================================================

async function runAgent1() {

    setLoading(true);

    try {

        const backendAvailable =
            await checkBackend();


        if (!backendAvailable) {

            throw new Error(
                "Backend is offline. Start FastAPI with: " +
                "python -m uvicorn main:app " +
                "--reload --host 127.0.0.1 --port 8000"
            );
        }


        const tab =
            await getCurrentTab();


        displayCurrentPage(
            tab
        );


        const url =
            tab.url || "";


        // ----------------------------------------------------
        // Browser internal pages
        // ----------------------------------------------------

        if (
            url.startsWith("chrome://") ||
            url.startsWith("chrome-extension://") ||
            url.startsWith("edge://") ||
            url.startsWith("about:")
        ) {

            throw new Error(
                "Chrome internal pages cannot be analyzed."
            );
        }


        // ----------------------------------------------------
        // Send URL to Agent 1
        // ----------------------------------------------------

        const response =
            await fetch(
                API_URL,
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


        if (!response.ok) {

            let message =
                "Backend request failed.";

            try {

                const errorData =
                    await response.json();

                message =
                    errorData.detail ||
                    message;

            } catch (error) {
                // Ignore parsing error.
            }

            throw new Error(
                message
            );
        }


        // ----------------------------------------------------
        // Receive Agent 1 result
        // ----------------------------------------------------

        const data =
            await response.json();


        const policies =
            data.policy_pages || [];


        // ----------------------------------------------------
        // Update UI
        // ----------------------------------------------------

        policyCount.textContent =
            policies.length;


        if (
            policies.length > 0
        ) {

            agentMessage.textContent =
                `Agent 1 found ${
                    policies.length
                } policy page${
                    policies.length === 1
                        ? ""
                        : "s"
                } and extracted ${
                    policies.reduce(
                        (total, policy) =>
                            total +
                            (
                                policy.content || ""
                            ).length,
                        0
                    ).toLocaleString()
                } characters.`;

        } else {

            agentMessage.textContent =
                "No supported policy page was discovered.";
        }


        updatePolicyCounts(
            policies
        );


        displayResults(
            policies
        );


        setSuccess();


    } catch (error) {

        console.error(
            "Agent 1 error:",
            error
        );

        showError(
            error.message ||
            "Unknown error."
        );

    } finally {

        setLoading(false);
    }
}


// ============================================================
// BUTTONS
// ============================================================

analyzeButton.addEventListener(
    "click",
    runAgent1
);

reanalyzeButton.addEventListener(
    "click",
    runAgent1
);


// ============================================================
// INITIALIZATION
// ============================================================

async function initialize() {

    try {

        const tab =
            await getCurrentTab();

        displayCurrentPage(
            tab
        );

    } catch (error) {

        pageTitle.textContent =
            "Current page unavailable";

        pageUrl.textContent =
            "";
    }


    await checkBackend();

    await runAgent1();
}


initialize();