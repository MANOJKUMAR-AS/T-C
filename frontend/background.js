// ============================================================
// T&C ANALYZER
// BACKGROUND SERVICE WORKER
//
// Browser-first policy discovery
// + rendered policy extraction
// + direct route probing
//
// IMPORTANT:
// Policy classification uses URL PATH ONLY.
// Query parameters are NEVER used to classify policies.
// ============================================================

"use strict";


// ============================================================
// CONFIGURATION
// ============================================================

const CONFIG = {
    MAX_POLICY_TABS: 20,

    WEB_SEARCH_ENABLED: true,

    WEB_SEARCH_TIMEOUT: 12000,

    WEB_SEARCH_RESULTS_PER_QUERY: 10,

    WEB_SEARCH_MAX_QUERIES: 12,

    LOAD_TIMEOUT: 10000,

    ROUTE_PROBE_TIMEOUT: 10000,

    PROBE_CONCURRENCY: 3,

    TARGET_POLICY_DOCUMENTS: 6,

    MAX_PAGE_TEXT: 30000,

    MAX_DOCUMENT_TEXT: 150000,

    MIN_DOCUMENT_CHARS: 500
};


// ============================================================
// POLICY CLASSIFICATION
// ============================================================

function classifyPolicyUrl(url) {
    if (!url || typeof url !== "string") {
        return null;
    }

    try {
        const parsed = new URL(url);

        // IMPORTANT:
        // Only inspect pathname.
        // Query parameters must never determine policy type.
        const path = parsed.pathname
            .toLowerCase()
            .replace(/\/+/g, "/");

        // ----------------------------------------------------
        // Obvious non-policy paths
        // ----------------------------------------------------

        const blockedPathPatterns = [
            /^\/s(?:\/|$)/,
            /^\/product(?:\/|$)/,
            /^\/products(?:\/|$)/,
            /^\/p(?:\/|$)/,
            /^\/shop(?:\/|$)/,
            /^\/search(?:\/|$)/,
            /^\/category(?:\/|$)/,
            /^\/categories(?:\/|$)/,
            /^\/collection(?:\/|$)/,
            /^\/collections(?:\/|$)/,
            /^\/brand(?:\/|$)/,
            /^\/brands(?:\/|$)/,
            /^\/sale(?:\/|$)/,
            /^\/offer(?:\/|$)/,
            /^\/offers(?:\/|$)/,
            /^\/campaign(?:\/|$)/,
            /^\/campaigns(?:\/|$)/,
            /^\/catalog(?:\/|$)/,
            /^\/catalogue(?:\/|$)/,
            /^\/beauty(?:\/|$)/,
            /^\/skin(?:\/|$)/,
            /^\/makeup(?:\/|$)/,
            /^\/hair(?:\/|$)/,
            /^\/bath(?:\/|$)/,
            /^\/body(?:\/|$)/
        ];

        if (
            blockedPathPatterns.some(
                pattern => pattern.test(path)
            )
        ) {
            return null;
        }

        // ----------------------------------------------------
        // Privacy
        // ----------------------------------------------------

        if (/privacy/.test(path)) {
            return "privacy";
        }

        // ----------------------------------------------------
        // Terms
        // ----------------------------------------------------

        if (
            /terms?/.test(path) ||
            /termsofuse/.test(path) ||
            /terms[-_]?of[-_]?use/.test(path) ||
            /terms[-_]?and[-_]?conditions/.test(path) ||
            /terms[-_]?conditions/.test(path) ||
            /conditions[-_]?of[-_]?use/.test(path)
        ) {
            return "terms";
        }

        // ----------------------------------------------------
        // Cookies
        // ----------------------------------------------------

        if (/cookies?/.test(path)) {
            return "cookies";
        }

        // ----------------------------------------------------
        // Returns / refunds / cancellation
        // ----------------------------------------------------

        if (
            /return/.test(path) ||
            /refund/.test(path) ||
            /cancellation/.test(path) ||
            /exchange/.test(path)
        ) {
            return "returns";
        }

        // ----------------------------------------------------
        // Payments / fees / billing
        // ----------------------------------------------------

        if (
            /payment/.test(path) ||
            /payments/.test(path) ||
            /fees?/.test(path) ||
            /billing/.test(path)
        ) {
            return "payments";
        }

        // ----------------------------------------------------
        // Promotions
        // ----------------------------------------------------

        if (
            /promotion[-_]?policy/.test(path) ||
            /promotions[-_]?policy/.test(path) ||
            /sale[-_]?policy/.test(path) ||
            /offer[-_]?policy/.test(path)
        ) {
            return "promotions";
        }

        // ----------------------------------------------------
        // Legal
        // ----------------------------------------------------

        if (
            /\/legal(?:\/|$)/.test(path) ||
            /notice/.test(path) ||
            /notices/.test(path) ||
            /disclaimer/.test(path) ||
            /agreement/.test(path) ||
            /corporate/.test(path)
        ) {
            return "legal";
        }

        return null;

    } catch (error) {
        return null;
    }
}


// ============================================================
// URL HELPERS
// ============================================================

function normalizeUrl(url, baseUrl = null) {
    if (!url || typeof url !== "string") {
        return null;
    }

    try {
        const absolute = new URL(
            url,
            baseUrl || undefined
        );

        if (
            absolute.protocol !== "http:" &&
            absolute.protocol !== "https:"
        ) {
            return null;
        }

        absolute.hash = "";

        return absolute.href;

    } catch (error) {
        return null;
    }
}


function sameSite(urlA, urlB) {
    if (!urlA || !urlB) {
        return false;
    }

    try {
        const a = new URL(urlA);
        const b = new URL(urlB);

        return (
            a.hostname.toLowerCase() ===
            b.hostname.toLowerCase()
        );

    } catch (error) {
        return false;
    }
}


function isBadUrl(url) {
    if (!url || typeof url !== "string") {
        return true;
    }

    try {
        const parsed = new URL(url);

        if (
            parsed.protocol !== "http:" &&
            parsed.protocol !== "https:"
        ) {
            return true;
        }

        const path =
            parsed.pathname.toLowerCase();

        const badPathPatterns = [
            /\.jpg$/,
            /\.jpeg$/,
            /\.png$/,
            /\.gif$/,
            /\.webp$/,
            /\.svg$/,
            /\.ico$/,
            /\.mp4$/,
            /\.mp3$/,
            /\.zip$/,
            /\.css$/,
            /\.js$/,
            /^\/login(?:\/|$)/,
            /^\/signin(?:\/|$)/,
            /^\/signup(?:\/|$)/,
            /^\/register(?:\/|$)/,
            /^\/cart(?:\/|$)/,
            /^\/checkout(?:\/|$)/,
            /^\/account(?:\/|$)/,
            /^\/profile(?:\/|$)/,
            /^\/wishlist(?:\/|$)/
        ];

        return badPathPatterns.some(
            pattern => pattern.test(path)
        );

    } catch (error) {
        return true;
    }
}


// ============================================================
// TEXT CLEANING
// ============================================================

function cleanText(text) {
    if (!text || typeof text !== "string") {
        return "";
    }

    return text
        .replace(/\u00a0/g, " ")
        .replace(/\r/g, "")
        .replace(/[ \t]+/g, " ")
        .replace(/\n\s*\n\s*\n+/g, "\n\n")
        .trim();
}


// ============================================================
// DOCUMENT VALIDATION
// ============================================================

function isSubstantiveDocument(
    text,
    url = null,
    expectedType = null
) {
    const cleaned = cleanText(text);

    if (
        cleaned.length <
        CONFIG.MIN_DOCUMENT_CHARS
    ) {
        return false;
    }

    if (url) {
        const detectedType =
            classifyPolicyUrl(url);

        if (!detectedType) {
            return false;
        }

        if (
            expectedType &&
            detectedType !== expectedType
        ) {
            return false;
        }
    }

    const lower =
        cleaned.toLowerCase();

    // --------------------------------------------------------
    // Shopping shell detection
    // --------------------------------------------------------

    const shoppingSignals = [
        "shop now",
        "add to cart",
        "add to bag",
        "buy now",
        "new arrivals",
        "best sellers",
        "shopping bag",
        "my account",
        "sort by popularity",
        "all products",
        "regular price"
    ];

    let shoppingSignalCount = 0;

    for (
        const signal of shoppingSignals
    ) {
        if (
            lower.includes(signal)
        ) {
            shoppingSignalCount++;
        }
    }

    // A short page containing several storefront signals
    // is not treated as a policy document.
    if (
        cleaned.length < 5000 &&
        shoppingSignalCount >= 3
    ) {
        return false;
    }

    return true;
}


// ============================================================
// DOCUMENT NORMALIZATION
// ============================================================

function normalizeDocument(
    document,
    fallbackUrl = null,
    expectedType = null
) {
    if (
        !document ||
        typeof document !== "object"
    ) {
        return null;
    }

    const rawUrl =
        document.url ||
        document.source_url ||
        document.href ||
        fallbackUrl;

    const url =
        normalizeUrl(
            rawUrl,
            fallbackUrl
        );

    if (!url) {
        return null;
    }

    const urlType =
        classifyPolicyUrl(url);

    if (!urlType) {
        return null;
    }

    const type =
        expectedType &&
        expectedType === urlType
            ? expectedType
            : urlType;

    const content =
        cleanText(
            document.content ||
            document.text ||
            document.page_text ||
            document.markdown ||
            document.body_text ||
            ""
        );

    if (
        !isSubstantiveDocument(
            content,
            url,
            type
        )
    ) {
        return null;
    }

    return {
        type,

        url,

        title:
            document.title ||
            type,

        content:
            content.slice(
                0,
                CONFIG.MAX_DOCUMENT_TEXT
            ),

        source:
            document.source ||
            "browser"
    };
}


// ============================================================
// DOCUMENT DEDUPLICATION
// ============================================================

function deduplicateDocuments(
    documents
) {
    const result = [];

    const seenUrls = new Set();
    const seenContent = new Set();

    for (
        const document of documents || []
    ) {
        if (!document) {
            continue;
        }

        const normalized =
            normalizeDocument(
                document,
                null,
                document.type || null
            );

        if (!normalized) {
            continue;
        }

        const normalizedUrl =
            normalized.url
                .toLowerCase()
                .replace(/\/+$/, "");

        const contentKey =
            normalized.content
                .toLowerCase()
                .replace(/\s+/g, " ")
                .slice(0, 5000);

        if (
            seenUrls.has(
                normalizedUrl
            )
        ) {
            continue;
        }

        if (
            contentKey &&
            seenContent.has(
                contentKey
            )
        ) {
            continue;
        }

        seenUrls.add(
            normalizedUrl
        );

        if (contentKey) {
            seenContent.add(
                contentKey
            );
        }

        result.push(
            normalized
        );

        if (
            result.length >=
            CONFIG.MAX_POLICY_TABS
        ) {
            break;
        }
    }

    return result;
}


// ============================================================
// CONTENT SCRIPT COLLECTION
// ============================================================

async function collectFromContentScript(
    tabId
) {
    if (!tabId) {
        return null;
    }

    try {
        const response =
            await chrome.tabs.sendMessage(
                tabId,
                {
                    // IMPORTANT:
                    // Must match the action name in content.js
                    // onMessage listener ("collectPolicyData").
                    action:
                        "collectPolicyData"
                }
            );

        if (
            response &&
            typeof response === "object"
        ) {
            return response;
        }

        return null;

    } catch (error) {
        console.warn(
            "[T&C Background] Content script collection failed:",
            error?.message || error
        );

        return null;
    }
}


// ============================================================
// DIRECT PAGE COLLECTOR
// ============================================================

async function executeDirectCollector(
    tabId
) {
    if (!tabId) {
        return null;
    }

    try {
        const results =
            await chrome.scripting.executeScript(
                {
                    target: {
                        tabId
                    },

                    func: () => {

                        function clean(value) {
                            if (
                                !value ||
                                typeof value !== "string"
                            ) {
                                return "";
                            }

                            return value
                                .replace(/\u00a0/g, " ")
                                .replace(/\r/g, "")
                                .replace(/[ \t]+/g, " ")
                                .replace(
                                    /\n\s*\n\s*\n+/g,
                                    "\n\n"
                                )
                                .trim();
                        }


                        function classify(url) {
                            if (
                                !url ||
                                typeof url !== "string"
                            ) {
                                return null;
                            }

                            try {
                                const parsed =
                                    new URL(url);

                                const path =
                                    parsed.pathname
                                        .toLowerCase()
                                        .replace(
                                            /\/+/g,
                                            "/"
                                        );

                                const blocked = [
                                    /^\/s(?:\/|$)/,
                                    /^\/product(?:\/|$)/,
                                    /^\/products(?:\/|$)/,
                                    /^\/p(?:\/|$)/,
                                    /^\/shop(?:\/|$)/,
                                    /^\/search(?:\/|$)/,
                                    /^\/category(?:\/|$)/,
                                    /^\/categories(?:\/|$)/,
                                    /^\/collection(?:\/|$)/,
                                    /^\/collections(?:\/|$)/,
                                    /^\/brand(?:\/|$)/,
                                    /^\/brands(?:\/|$)/,
                                    /^\/sale(?:\/|$)/,
                                    /^\/offer(?:\/|$)/,
                                    /^\/offers(?:\/|$)/,
                                    /^\/campaign(?:\/|$)/,
                                    /^\/campaigns(?:\/|$)/,
                                    /^\/catalog(?:\/|$)/,
                                    /^\/catalogue(?:\/|$)/,
                                    /^\/beauty(?:\/|$)/,
                                    /^\/skin(?:\/|$)/,
                                    /^\/makeup(?:\/|$)/,
                                    /^\/hair(?:\/|$)/,
                                    /^\/bath(?:\/|$)/,
                                    /^\/body(?:\/|$)/
                                ];

                                if (
                                    blocked.some(
                                        pattern =>
                                            pattern.test(
                                                path
                                            )
                                    )
                                ) {
                                    return null;
                                }

                                if (
                                    /privacy/.test(path)
                                ) {
                                    return "privacy";
                                }

                                if (
                                    /terms?/.test(path) ||
                                    /termsofuse/.test(path) ||
                                    /terms[-_]?of[-_]?use/.test(path) ||
                                    /terms[-_]?and[-_]?conditions/.test(path) ||
                                    /terms[-_]?conditions/.test(path) ||
                                    /conditions[-_]?of[-_]?use/.test(path)
                                ) {
                                    return "terms";
                                }

                                if (
                                    /cookies?/.test(path)
                                ) {
                                    return "cookies";
                                }

                                if (
                                    /return/.test(path) ||
                                    /refund/.test(path) ||
                                    /cancellation/.test(path) ||
                                    /exchange/.test(path)
                                ) {
                                    return "returns";
                                }

                                if (
                                    /payment/.test(path) ||
                                    /payments/.test(path) ||
                                    /fees?/.test(path) ||
                                    /billing/.test(path)
                                ) {
                                    return "payments";
                                }

                                if (
                                    /promotion[-_]?policy/.test(path) ||
                                    /promotions[-_]?policy/.test(path) ||
                                    /sale[-_]?policy/.test(path) ||
                                    /offer[-_]?policy/.test(path)
                                ) {
                                    return "promotions";
                                }

                                if (
                                    /\/legal(?:\/|$)/.test(path) ||
                                    /notice/.test(path) ||
                                    /notices/.test(path) ||
                                    /disclaimer/.test(path) ||
                                    /agreement/.test(path) ||
                                    /corporate/.test(path)
                                ) {
                                    return "legal";
                                }

                                return null;

                            } catch (error) {
                                return null;
                            }
                        }


                        function normalizeHref(href) {
                            try {
                                const absolute =
                                    new URL(
                                        href,
                                        window.location.href
                                    );

                                if (
                                    absolute.protocol !== "http:" &&
                                    absolute.protocol !== "https:"
                                ) {
                                    return null;
                                }

                                absolute.hash = "";

                                return absolute.href;

                            } catch (error) {
                                return null;
                            }
                        }


                        const links = [];

                        const anchors =
                            Array.from(
                                document.querySelectorAll(
                                    "a[href]"
                                )
                            );

                        for (
                            const anchor of anchors
                        ) {
                            const href =
                                normalizeHref(
                                    anchor.getAttribute(
                                        "href"
                                    )
                                );

                            if (!href) {
                                continue;
                            }

                            const type =
                                classify(href);

                            links.push({
                                url: href,

                                text: clean(
                                    anchor.innerText ||
                                    anchor.textContent ||
                                    ""
                                ),

                                type
                            });
                        }


                        const uniqueLinks = [];

                        const seen = new Set();

                        for (
                            const link of links
                        ) {
                            if (
                                seen.has(link.url)
                            ) {
                                continue;
                            }

                            seen.add(link.url);

                            uniqueLinks.push(
                                link
                            );
                        }


                        const pageText =
                            clean(
                                document.body
                                    ? (
                                        document.body.innerText ||
                                        ""
                                    )
                                    : ""
                            );


                        const currentType =
                            classify(
                                window.location.href
                            );


                        const browserDocument =
                            currentType &&
                            pageText.length >= 500
                                ? {
                                    type:
                                        currentType,

                                    url:
                                        window.location.href,

                                    title:
                                        document.title ||
                                        currentType,

                                    content:
                                        pageText,

                                    source:
                                        "browser"
                                }
                                : null;


                        return {
                            browser_links:
                                uniqueLinks,

                            browser_all_links:
                                uniqueLinks,

                            browser_documents:
                                browserDocument
                                    ? [
                                        browserDocument
                                    ]
                                    : [],

                            browser_page_text:
                                pageText.slice(
                                    0,
                                    30000
                                ),

                            url:
                                window.location.href,

                            title:
                                document.title ||
                                ""
                        };
                    }
                }
            );

        if (
            Array.isArray(results) &&
            results.length > 0 &&
            results[0]?.result
        ) {
            return results[0].result;
        }

        return null;

    } catch (error) {
        console.warn(
            "[T&C Background] Direct collector failed:",
            error?.message || error
        );

        return null;
    }
}


// ============================================================
// COLLECT TAB
// ============================================================

async function collectTab(tabId) {
    let data =
        await collectFromContentScript(
            tabId
        );

    if (!data) {
        data =
            await executeDirectCollector(
                tabId
            );
    }

    if (!data) {
        return {
            browser_links: [],
            browser_all_links: [],
            browser_documents: [],
            browser_page_text: ""
        };
    }

    return {
        browser_links:
            Array.isArray(
                data.browser_links
            )
                ? data.browser_links
                : [],

        browser_all_links:
            Array.isArray(
                data.browser_all_links
            )
                ? data.browser_all_links
                : (
                    Array.isArray(
                        data.browser_links
                    )
                        ? data.browser_links
                        : []
                ),

        browser_documents:
            Array.isArray(
                data.browser_documents
            )
                ? data.browser_documents
                : [],

        browser_page_text:
            typeof data.browser_page_text === "string"
                ? data.browser_page_text.slice(
                    0,
                    CONFIG.MAX_PAGE_TEXT
                )
                : "",

        url:
            data.url || "",

        title:
            data.title || ""
    };
}


// ============================================================
// WAIT FOR TAB LOAD
// ============================================================

function waitForTabLoad(
    tabId,
    timeout = CONFIG.LOAD_TIMEOUT
) {
    return new Promise(resolve => {

        let finished = false;
        let timer = null;

        function cleanup() {
            try {
                chrome.tabs.onUpdated.removeListener(
                    listener
                );
            } catch (error) {
                // Ignore cleanup errors.
            }

            if (timer) {
                clearTimeout(timer);
            }
        }


        function finish(result) {
            if (finished) {
                return;
            }

            finished = true;

            cleanup();

            resolve(result);
        }


        function listener(
            updatedTabId,
            changeInfo
        ) {
            if (
                updatedTabId !== tabId
            ) {
                return;
            }

            if (
                changeInfo.status ===
                "complete"
            ) {
                finish(true);
            }
        }


        timer =
            setTimeout(
                () => finish(false),
                timeout
            );


        chrome.tabs.onUpdated.addListener(
            listener
        );


        chrome.tabs.get(tabId)
            .then(tab => {
                if (
                    tab &&
                    tab.status === "complete"
                ) {
                    finish(true);
                }
            })
            .catch(() => {
                finish(false);
            });
    });
}


// ============================================================
// SAFE TAB CLOSE
// ============================================================

async function closeTab(tabId) {
    if (!tabId) {
        return;
    }

    try {
        await chrome.tabs.remove(
            tabId
        );
    } catch (error) {
        // Ignore already-closed tabs.
    }
}


// ============================================================
// HYDRATE POLICY URL
// ============================================================

async function hydratePolicyUrl(
    url,
    expectedType = null
) {
    let tabId = null;

    try {
        const normalizedTarget =
            normalizeUrl(url);

        if (!normalizedTarget) {
            return null;
        }

        const detectedType =
            classifyPolicyUrl(
                normalizedTarget
            );

        if (!detectedType) {
            console.log(
                `[T&C Background] Rejected non-policy route: ${normalizedTarget}`
            );

            return null;
        }

        if (
            expectedType &&
            detectedType !== expectedType
        ) {
            console.log(
                `[T&C Background] Rejected type mismatch: ${normalizedTarget}`
            );

            return null;
        }

        console.log(
            `[T&C Background] Opening policy: ${normalizedTarget}`
        );

        const tab =
            await chrome.tabs.create({
                url:
                    normalizedTarget,

                active:
                    false
            });

        tabId =
            tab.id;

        if (!tabId) {
            return null;
        }

        await waitForTabLoad(
            tabId,
            CONFIG.ROUTE_PROBE_TIMEOUT
        );

        let currentTab = null;

        try {
            currentTab =
                await chrome.tabs.get(
                    tabId
                );
        } catch (error) {
            return null;
        }

        const finalUrl =
            currentTab?.url ||
            normalizedTarget;

        const finalType =
            classifyPolicyUrl(
                finalUrl
            );

        if (!finalType) {
            console.log(
                `[T&C Background] Rejected redirect: ${normalizedTarget} -> ${finalUrl}`
            );

            return null;
        }

        if (
            expectedType &&
            finalType !== expectedType
        ) {
            console.log(
                `[T&C Background] Rejected redirected type: ${finalUrl}`
            );

            return null;
        }

        const data =
            await collectTab(
                tabId
            );

        const documents =
            Array.isArray(
                data.browser_documents
            )
                ? data.browser_documents
                : [];


        for (
            const document of documents
        ) {
            const normalized =
                normalizeDocument(
                    {
                        ...document,

                        url:
                            document.url ||
                            finalUrl,

                        type:
                            finalType
                    },

                    finalUrl,

                    finalType
                );

            if (normalized) {
                normalized.source =
                    "browser";

                console.log(
                    `[T&C Background] Policy collected: ${normalized.type} ${normalized.content.length} chars`
                );

                return normalized;
            }
        }


        if (
            data.browser_page_text &&
            data.browser_page_text.length >=
                CONFIG.MIN_DOCUMENT_CHARS
        ) {
            const fallback =
                normalizeDocument(
                    {
                        type:
                            finalType,

                        url:
                            finalUrl,

                        title:
                            data.title ||
                            finalType,

                        content:
                            data.browser_page_text,

                        source:
                            "browser"
                    },

                    finalUrl,

                    finalType
                );

            if (fallback) {
                console.log(
                    `[T&C Background] Policy text fallback collected: ${finalType} ${fallback.content.length} chars`
                );

                return fallback;
            }
        }

        console.log(
            `[T&C Background] Policy page had insufficient content: ${finalUrl}`
        );

        return null;

    } catch (error) {

        console.warn(
            `[T&C Background] Failed to hydrate ${url}:`,
            error?.message || error
        );

        return null;

    } finally {

        await closeTab(
            tabId
        );
    }
}


// ============================================================
// HYDRATE DISCOVERED POLICY LINKS
// ============================================================

async function hydrateDiscoveredLinks(
    links,
    sourceUrl
) {
    if (!Array.isArray(links)) {
        return [];
    }

    const candidates = [];

    const seen = new Set();

    for (
        const link of links
    ) {
        if (!link) {
            continue;
        }

        const rawUrl =
            link.url ||
            link.href;

        const url =
            normalizeUrl(
                rawUrl,
                sourceUrl
            );

        if (!url) {
            continue;
        }

        if (
            !sameSite(
                url,
                sourceUrl
            )
        ) {
            continue;
        }

        if (
            isBadUrl(url)
        ) {
            continue;
        }

        const type =
            classifyPolicyUrl(
                url
            );

        if (!type) {
            continue;
        }

        const key =
            url.toLowerCase();

        if (
            seen.has(key)
        ) {
            continue;
        }

        seen.add(key);

        candidates.push({
            url,
            type
        });

        if (
            candidates.length >=
            CONFIG.MAX_POLICY_TABS
        ) {
            break;
        }
    }


    if (
        candidates.length === 0
    ) {
        return [];
    }


    console.log(
        `[T&C Background] Browser policy candidates: ${candidates.length}`
    );


    const documents = [];

    for (
        let i = 0;
        i < candidates.length;
        i += CONFIG.PROBE_CONCURRENCY
    ) {
        const batch =
            candidates.slice(
                i,
                i +
                    CONFIG.PROBE_CONCURRENCY
            );

        const results =
            await Promise.all(
                batch.map(
                    candidate =>
                        hydratePolicyUrl(
                            candidate.url,
                            candidate.type
                        )
                )
            );

        for (
            const document of results
        ) {
            if (document) {
                documents.push(
                    document
                );
            }
        }

        if (
            documents.length >=
            CONFIG.TARGET_POLICY_DOCUMENTS
        ) {
            break;
        }
    }

    return deduplicateDocuments(
        documents
    );
}


// ============================================================
// SITE-SPECIFIC POLICY ROUTES
// ============================================================
//
// These are fallback routes used when a site does not expose
// usable policy links in the current page DOM.
//
// Browser tabs are used for extraction, so normal browser
// session behavior remains available.
//
// ============================================================

const SITE_SPECIFIC_ROUTES = {

    // --------------------------------------------------------
    // AJIO
    // --------------------------------------------------------

    "ajio.com": [

        {
            path:
                "/help/termsAndCondition",

            type:
                "terms"
        },

        {
            path:
                "/fee-payment-promotion-policy",

            type:
                "payments"
        },

        {
            path:
                "/return-refund-policy",

            type:
                "returns"
        },

        {
            path:
                "/privacypolicy",

            type:
                "privacy"
        },

        {
            path:
                "/policy/privacypolicy",

            type:
                "privacy"
        },

        {
            path:
                "/ajio-own-sale-policy",

            type:
                "promotions"
        }
    ],


    // --------------------------------------------------------
    // NYKAA
    // --------------------------------------------------------

    "nykaa.com": [

        {
            path:
                "/terms-conditions",

            type:
                "terms"
        },

        {
            path:
                "/app-terms-conditions",

            type:
                "terms"
        },

        {
            path:
                "/app-api/index.php/pages/terms",

            type:
                "terms"
        },

        {
            path:
                "/privacy-policy",

            type:
                "privacy"
        },

        {
            path:
                "/privacy-policy-app",

            type:
                "privacy"
        },

        {
            path:
                "/policy",

            type:
                "privacy"
        },

        {
            path:
                "/cancellation-policy",

            type:
                "returns"
        },

        {
            path:
                "/cancellation-policy/lp",

            type:
                "returns"
        },

        {
            path:
                "/policy-app",

            type:
                "terms"
        },

        {
            path:
                "/shipping-policy-app",

            type:
                "legal"
        }
    ]
};


// ============================================================
// GENERIC POLICY ROUTES
// ============================================================

const GENERIC_POLICY_ROUTES = [

    {
        path:
            "/privacy-policy",

        type:
            "privacy"
    },

    {
        path:
            "/privacy",

        type:
            "privacy"
    },

    {
        path:
            "/legal/privacy",

        type:
            "privacy"
    },

    {
        path:
            "/terms",

        type:
            "terms"
    },

    {
        path:
            "/terms-of-use",

        type:
            "terms"
    },

    {
        path:
            "/terms-and-conditions",

        type:
            "terms"
    },

    {
        path:
            "/legal/terms",

        type:
            "terms"
    },

    {
        path:
            "/cookies",

        type:
            "cookies"
    },

    {
        path:
            "/cookie-policy",

        type:
            "cookies"
    },

    {
        path:
            "/legal",

        type:
            "legal"
    },

    {
        path:
            "/returns",

        type:
            "returns"
    },

    {
        path:
            "/return-policy",

        type:
            "returns"
    },

    {
        path:
            "/refund-policy",

        type:
            "returns"
    },

    {
        path:
            "/payment-policy",

        type:
            "payments"
    },

    {
        path:
            "/fee-policy",

        type:
            "payments"
    }
];


// ============================================================
// GET ROUTE PROBES
// ============================================================

function getRouteProbes(sourceUrl) {
    try {
        const parsed =
            new URL(sourceUrl);

        const hostname =
            parsed.hostname
                .toLowerCase()
                .replace(
                    /^www\./,
                    ""
                );

        const routes = [];

        // ----------------------------------------------------
        // Site-specific routes first
        // ----------------------------------------------------

        const siteRoutes =
            SITE_SPECIFIC_ROUTES[
                hostname
            ] || [];

        routes.push(
            ...siteRoutes
        );

        // ----------------------------------------------------
        // Generic routes second
        // ----------------------------------------------------

        routes.push(
            ...GENERIC_POLICY_ROUTES
        );


        const unique = [];

        const seen =
            new Set();

        for (
            const route of routes
        ) {
            let fullUrl;

            try {
                fullUrl =
                    new URL(
                        route.path,
                        `${parsed.protocol}//${parsed.host}`
                    ).href;
            } catch (error) {
                continue;
            }

            const key =
                fullUrl.toLowerCase();

            if (
                seen.has(key)
            ) {
                continue;
            }

            seen.add(key);

            unique.push({
                url:
                    fullUrl,

                type:
                    route.type
            });
        }

        return unique;

    } catch (error) {
        return [];
    }
}


// ============================================================
// DIRECT ROUTE PROBING
// ============================================================

async function probePolicyRoutes(
    sourceUrl
) {
    const candidates =
        getRouteProbes(
            sourceUrl
        );

    if (
        candidates.length === 0
    ) {
        return [];
    }

    console.log(
        `[T&C Background] Direct route probes: ${candidates.length}`
    );

    const documents = [];

    let cursor = 0;


    async function worker() {

        while (true) {

            if (
                documents.length >=
                CONFIG.TARGET_POLICY_DOCUMENTS
            ) {
                return;
            }

            if (
                cursor >=
                candidates.length
            ) {
                return;
            }

            const index =
                cursor++;

            const candidate =
                candidates[index];

            console.log(
                `[T&C Background] Probing: ${candidate.url}`
            );

            const document =
                await hydratePolicyUrl(
                    candidate.url,
                    candidate.type
                );

            if (document) {

                documents.push(
                    document
                );

                console.log(
                    `[T&C Background] Probe SUCCESS: ${candidate.type} ${candidate.url}`
                );
            } else {

                console.log(
                    `[T&C Background] Probe FAILED: ${candidate.url}`
                );
            }
        }
    }


    const workers = [];

    const workerCount =
        Math.min(
            CONFIG.PROBE_CONCURRENCY,
            candidates.length
        );

    for (
        let i = 0;
        i < workerCount;
        i++
    ) {
        workers.push(
            worker()
        );
    }

    await Promise.all(
        workers
    );

    return deduplicateDocuments(
        documents
    );
}


// ============================================================
// BROWSER WEB SEARCH FALLBACK
// ============================================================
//
// FINAL FALLBACK:
//
// 1. Browser DOM discovery
// 2. Direct browser route probing
// 3. Browser-based web search
//
// IMPORTANT:
// The search engine is ONLY used to discover URLs.
// The actual policy page is opened in a Chrome tab and
// extracted using the same browser-session collector.
//
// This avoids backend HTTP 403 / bot-protection problems.
// ============================================================

const WEB_SEARCH_QUERIES = [

    {
        type: "terms",
        query:
            'site:{domain} "terms and conditions"'
    },

    {
        type: "terms",
        query:
            'site:{domain} "terms of use"'
    },

    {
        type: "terms",
        query:
            'site:{domain} "terms of service"'
    },

    {
        type: "privacy",
        query:
            'site:{domain} "privacy policy"'
    },

    {
        type: "privacy",
        query:
            'site:{domain} "privacy notice"'
    },

    {
        type: "cookies",
        query:
            'site:{domain} "cookie policy"'
    },

    {
        type: "cookies",
        query:
            'site:{domain} "cookie notice"'
    },

    {
        type: "returns",
        query:
            'site:{domain} "return policy"'
    },

    {
        type: "returns",
        query:
            'site:{domain} "refund policy"'
    },

    {
        type: "returns",
        query:
            'site:{domain} "cancellation policy"'
    },

    {
        type: "payments",
        query:
            'site:{domain} "payment policy"'
    },

    {
        type: "legal",
        query:
            'site:{domain} "legal notice"'
    }
];


// ------------------------------------------------------------
// Search URL helpers
// ------------------------------------------------------------

function getSearchDomain(sourceUrl) {

    try {

        const parsed =
            new URL(sourceUrl);

        return parsed.hostname
            .toLowerCase()
            .replace(/^www\./, "");

    } catch (error) {

        return "";

    }
}


function buildWebSearchUrl(query) {

    return (
        "https://www.google.com/search?q=" +
        encodeURIComponent(query)
    );

}


// ------------------------------------------------------------
// Extract links from rendered search results
// ------------------------------------------------------------

async function collectSearchResultLinks(
    tabId,
    sourceUrl,
    expectedType
) {

    if (!tabId) {
        return [];
    }

    try {

        const results =
            await chrome.scripting.executeScript({

                target: {
                    tabId
                },

                func: (
                    sourceUrlArg,
                    expectedTypeArg
                ) => {

                    function clean(value) {

                        if (
                            !value ||
                            typeof value !== "string"
                        ) {
                            return "";
                        }

                        return value
                            .replace(/\u00a0/g, " ")
                            .replace(/\s+/g, " ")
                            .trim();

                    }


                    function classify(url) {

                        if (
                            !url ||
                            typeof url !== "string"
                        ) {
                            return null;
                        }

                        try {

                            const parsed =
                                new URL(url);

                            const path =
                                parsed.pathname
                                    .toLowerCase()
                                    .replace(
                                        /\/+/g,
                                        "/"
                                    );


                            const blocked = [
                                /^\/s(?:\/|$)/,
                                /^\/product(?:\/|$)/,
                                /^\/products(?:\/|$)/,
                                /^\/p(?:\/|$)/,
                                /^\/shop(?:\/|$)/,
                                /^\/search(?:\/|$)/,
                                /^\/category(?:\/|$)/,
                                /^\/categories(?:\/|$)/,
                                /^\/collection(?:\/|$)/,
                                /^\/collections(?:\/|$)/,
                                /^\/brand(?:\/|$)/,
                                /^\/brands(?:\/|$)/,
                                /^\/sale(?:\/|$)/,
                                /^\/offer(?:\/|$)/,
                                /^\/offers(?:\/|$)/,
                                /^\/campaign(?:\/|$)/,
                                /^\/campaigns(?:\/|$)/,
                                /^\/catalog(?:\/|$)/,
                                /^\/catalogue(?:\/|$)/
                            ];


                            if (
                                blocked.some(
                                    pattern =>
                                        pattern.test(
                                            path
                                        )
                                )
                            ) {
                                return null;
                            }


                            if (
                                /privacy/.test(path)
                            ) {
                                return "privacy";
                            }


                            if (
                                /terms?/.test(path) ||
                                /termsofuse/.test(path) ||
                                /terms[-_]?of[-_]?use/.test(path) ||
                                /terms[-_]?and[-_]?conditions/.test(path) ||
                                /terms[-_]?conditions/.test(path)
                            ) {
                                return "terms";
                            }


                            if (
                                /cookies?/.test(path)
                            ) {
                                return "cookies";
                            }


                            if (
                                /return/.test(path) ||
                                /refund/.test(path) ||
                                /cancellation/.test(path) ||
                                /exchange/.test(path)
                            ) {
                                return "returns";
                            }


                            if (
                                /payment/.test(path) ||
                                /payments/.test(path) ||
                                /fees?/.test(path) ||
                                /billing/.test(path)
                            ) {
                                return "payments";
                            }


                            if (
                                /promotion[-_]?policy/.test(path) ||
                                /promotions[-_]?policy/.test(path)
                            ) {
                                return "promotions";
                            }


                            if (
                                /\/legal(?:\/|$)/.test(path) ||
                                /notice/.test(path) ||
                                /notices/.test(path) ||
                                /disclaimer/.test(path) ||
                                /agreement/.test(path) ||
                                /corporate/.test(path)
                            ) {
                                return "legal";
                            }


                            return null;

                        } catch (error) {

                            return null;

                        }

                    }


                    function sameSite(
                        urlA,
                        urlB
                    ) {

                        try {

                            const a =
                                new URL(urlA);

                            const b =
                                new URL(urlB);

                            const hostA =
                                a.hostname
                                    .toLowerCase()
                                    .replace(
                                        /^www\./,
                                        ""
                                    );

                            const hostB =
                                b.hostname
                                    .toLowerCase()
                                    .replace(
                                        /^www\./,
                                        ""
                                    );

                            return (
                                hostA ===
                                hostB
                            );

                        } catch (error) {

                            return false;

                        }

                    }


                    const links = [];

                    const anchors =
                        Array.from(
                            document.querySelectorAll(
                                "a[href]"
                            )
                        );


                    for (
                        const anchor of anchors
                    ) {

                        let href;

                        try {

                            href =
                                new URL(
                                    anchor.href,
                                    window.location.href
                                ).href;

                        } catch (error) {

                            continue;

                        }


                        const type =
                            classify(href);


                        if (!type) {
                            continue;
                        }


                        if (
                            expectedTypeArg &&
                            type !== expectedTypeArg
                        ) {
                            continue;
                        }


                        if (
                            !sameSite(
                                href,
                                sourceUrlArg
                            )
                        ) {
                            continue;
                        }


                        links.push({

                            url:
                                href,

                            type,

                            text:
                                clean(
                                    anchor.innerText ||
                                    anchor.textContent ||
                                    ""
                                )

                        });

                    }


                    const unique = [];

                    const seen =
                        new Set();


                    for (
                        const link of links
                    ) {

                        const key =
                            link.url
                                .toLowerCase();


                        if (
                            seen.has(key)
                        ) {
                            continue;
                        }


                        seen.add(key);

                        unique.push(
                            link
                        );

                    }


                    return unique;

                },

                args: [
                    sourceUrl,
                    expectedType
                ]

            });


        if (
            !Array.isArray(results) ||
            !results.length ||
            !Array.isArray(
                results[0]?.result
            )
        ) {
            return [];
        }


        return results[0].result;

    } catch (error) {

        console.warn(
            "[T&C Background] Search result extraction failed:",
            error?.message || error
        );

        return [];

    }
}


// ------------------------------------------------------------
// Browser web-search query
// ------------------------------------------------------------

async function runBrowserWebSearch(
    sourceUrl,
    expectedType,
    query
) {

    let tabId = null;

    try {

        const searchUrl =
            buildWebSearchUrl(
                query
            );


        console.log(
            `[T&C Background] Web search: ${query}`
        );


        const tab =
            await chrome.tabs.create({

                url:
                    searchUrl,

                active:
                    false

            });


        tabId =
            tab.id;


        if (!tabId) {
            return [];
        }


        await waitForTabLoad(
            tabId,
            CONFIG.WEB_SEARCH_TIMEOUT
        );


        const links =
            await collectSearchResultLinks(
                tabId,
                sourceUrl,
                expectedType
            );


        console.log(
            `[T&C Background] Search discovered ${links.length} same-site ${expectedType} links`
        );


        return links;

    } catch (error) {

        console.warn(
            `[T&C Background] Browser web search failed:`,
            error?.message || error
        );

        return [];

    } finally {

        await closeTab(
            tabId
        );

    }
}


// ------------------------------------------------------------
// THIRD FALLBACK
// ------------------------------------------------------------

async function browserWebSearchFallback(
    sourceUrl
) {

    if (
        !CONFIG.WEB_SEARCH_ENABLED
    ) {
        return [];
    }


    const domain =
        getSearchDomain(
            sourceUrl
        );


    if (!domain) {
        return [];
    }


    console.log(
        "================================================"
    );

    console.log(
        "[T&C Background] THIRD FALLBACK: BROWSER WEB SEARCH"
    );

    console.log(
        `[T&C Background] Search domain: ${domain}`
    );

    console.log(
        "================================================"
    );


    const discovered = [];

    const seen =
        new Set();


    const queryLimit =
        Math.min(
            CONFIG.WEB_SEARCH_MAX_QUERIES,
            WEB_SEARCH_QUERIES.length
        );


    for (
        let i = 0;
        i < queryLimit;
        i++
    ) {

        if (
            discovered.length >=
            CONFIG.TARGET_POLICY_DOCUMENTS
        ) {
            break;
        }


        const definition =
            WEB_SEARCH_QUERIES[i];


        const query =
            definition.query.replace(
                "{domain}",
                domain
            );


        const links =
            await runBrowserWebSearch(
                sourceUrl,
                definition.type,
                query
            );


        for (
            const link of links
        ) {

            const url =
                normalizeUrl(
                    link.url,
                    sourceUrl
                );


            if (!url) {
                continue;
            }


            if (
                !sameSite(
                    url,
                    sourceUrl
                )
            ) {
                continue;
            }


            if (
                isBadUrl(url)
            ) {
                continue;
            }


            const detectedType =
                classifyPolicyUrl(
                    url
                );


            if (!detectedType) {
                continue;
            }


            if (
                detectedType !==
                definition.type
            ) {
                continue;
            }


            const key =
                url
                    .toLowerCase()
                    .replace(
                        /\/+$/,
                        ""
                    );


            if (
                seen.has(key)
            ) {
                continue;
            }


            seen.add(key);


            discovered.push({

                url,

                type:
                    detectedType

            });


            console.log(
                `[T&C Background] WEB SEARCH CANDIDATE: ${detectedType} ${url}`
            );


            if (
                discovered.length >=
                CONFIG.TARGET_POLICY_DOCUMENTS
            ) {
                break;
            }

        }

    }


    if (
        discovered.length === 0
    ) {

        console.log(
            "[T&C Background] Browser web search found no policy URLs."
        );

        return [];

    }


    console.log(
        `[T&C Background] Browser web search discovered ${discovered.length} policy URLs. Hydrating...`
    );


    const documents = [];


    for (
        let i = 0;
        i < discovered.length;
        i += CONFIG.PROBE_CONCURRENCY
    ) {

        const batch =
            discovered.slice(
                i,
                i +
                    CONFIG.PROBE_CONCURRENCY
            );


        const results =
            await Promise.all(
                batch.map(
                    candidate =>
                        hydratePolicyUrl(
                            candidate.url,
                            candidate.type
                        )
                )
            );


        for (
            const document of results
        ) {

            if (document) {

                document.source =
                    "browser_web_search";

                documents.push(
                    document
                );

            }

        }


        if (
            documents.length >=
            CONFIG.TARGET_POLICY_DOCUMENTS
        ) {
            break;
        }

    }


    const finalDocuments =
        deduplicateDocuments(
            documents
        );


    console.log(
        `[T&C Background] THIRD FALLBACK COMPLETE: ${finalDocuments.length} policy documents`
    );


    return finalDocuments;
}


// ============================================================
// MAIN COLLECTION HANDLER
// ============================================================

async function handleCollectPolicyData(
    message,
    sender
) {
    let sourceTab = null;

    try {

        // ----------------------------------------------------
        // 1. Explicit tab ID from popup
        // ----------------------------------------------------

        if (
            Number.isInteger(
                message?.tabId
            )
        ) {
            try {
                sourceTab =
                    await chrome.tabs.get(
                        message.tabId
                    );
            } catch (error) {
                sourceTab = null;
            }
        }


        // ----------------------------------------------------
        // 2. Sender tab
        // ----------------------------------------------------

        if (
            !sourceTab?.id &&
            sender?.tab?.id
        ) {
            sourceTab =
                sender.tab;
        }


        // ----------------------------------------------------
        // 3. Active tab fallback
        // ----------------------------------------------------

        if (
            !sourceTab?.id
        ) {
            const activeTabs =
                await chrome.tabs.query({
                    active:
                        true,

                    currentWindow:
                        true
                });

            sourceTab =
                activeTabs?.[0] ||
                null;
        }


        if (
            !sourceTab?.id
        ) {
            throw new Error(
                "No source tab."
            );
        }


        const sourceUrl =
            sourceTab.url ||
            "";


        console.log(
            "=============================================="
        );

        console.log(
            "[T&C Background] COLLECT START"
        );

        console.log(
            `[T&C Background] Source tab: ${sourceTab.id}`
        );

        console.log(
            `[T&C Background] URL: ${sourceUrl}`
        );


        // ----------------------------------------------------
        // Validate source page
        // ----------------------------------------------------

        if (
            !/^https?:\/\//i.test(
                sourceUrl
            )
        ) {
            throw new Error(
                "This page cannot be analyzed by the browser collector."
            );
        }


        // ----------------------------------------------------
        // STEP 1
        // Collect current page
        // ----------------------------------------------------

        const browserData =
            await collectTab(
                sourceTab.id
            );

        const browserLinks =
            Array.isArray(
                browserData.browser_links
            )
                ? browserData.browser_links
                : [];

        const browserAllLinks =
            Array.isArray(
                browserData.browser_all_links
            )
                ? browserData.browser_all_links
                : browserLinks;


        let documents =
            deduplicateDocuments(
                browserData.browser_documents ||
                []
            );


        console.log(
            `[T&C Background] Browser links: ${browserLinks.length}`
        );

        console.log(
            `[T&C Background] Browser documents: ${documents.length}`
        );

        console.log(
            `[T&C Background] Browser all links: ${browserAllLinks.length}`
        );

        console.log(
            `[T&C Background] Browser page text: ${
                browserData.browser_page_text?.length ||
                0
            }`
        );


        // ----------------------------------------------------
        // STEP 2
        // Hydrate genuine browser-discovered policy links
        // ----------------------------------------------------

        if (
            documents.length <
            CONFIG.TARGET_POLICY_DOCUMENTS
        ) {

            const discoveredDocuments =
                await hydrateDiscoveredLinks(
                    browserLinks,
                    sourceUrl
                );

            documents =
                deduplicateDocuments([
                    ...documents,
                    ...discoveredDocuments
                ]);
        }


        console.log(
            `[T&C Background] After link hydration: ${documents.length}`
        );


        // ----------------------------------------------------
        // STEP 3
        // Direct route probing
        // ----------------------------------------------------

        if (
            documents.length <
            CONFIG.TARGET_POLICY_DOCUMENTS
        ) {

            console.log(
                "[T&C Background] Starting direct policy route probes..."
            );

            const routeDocuments =
                await probePolicyRoutes(
                    sourceUrl
                );

            documents =
                deduplicateDocuments([
                    ...documents,
                    ...routeDocuments
                ]);
        }


        // ----------------------------------------------------
        // STEP 4
        // Browser web-search fallback
        // ----------------------------------------------------

        if (
            documents.length <
            CONFIG.TARGET_POLICY_DOCUMENTS
        ) {

            console.log(
                "[T&C Background] Starting browser web-search fallback..."
            );

            const searchDocuments =
                await browserWebSearchFallback(
                    sourceUrl
                );

            documents =
                deduplicateDocuments([
                    ...documents,
                    ...searchDocuments
                ]);
        }


        // ----------------------------------------------------
        // Final result
        // ----------------------------------------------------

        documents =
            documents.slice(
                0,
                CONFIG.MAX_POLICY_TABS
            );


        console.log(
            `[T&C Background] FINAL DOCUMENTS: ${documents.length}`
        );


        for (
            const document of documents
        ) {
            console.log(
                `[T&C Background] [${document.type}] ${document.url} -> ${document.content.length} chars`
            );
        }


        console.log(
            "[T&C Background] COLLECT COMPLETE"
        );

        console.log(
            "=============================================="
        );


        return {
            ok:
                true,

            source_url:
                sourceUrl,

            browser_links:
                browserLinks,

            browser_all_links:
                browserAllLinks,

            browser_documents:
                documents,

            browser_page_text:
                browserData.browser_page_text ||
                "",

            documents:
                documents
        };


    } catch (error) {

        console.error(
            "[T&C Background] COLLECTION ERROR:",
            error
        );

        return {
            ok:
                false,

            error:
                error?.message ||
                String(error),

            browser_links:
                [],

            browser_all_links:
                [],

            browser_documents:
                [],

            browser_page_text:
                "",

            documents:
                []
        };
    }
}


// ============================================================
// MESSAGE LISTENER
// ============================================================

chrome.runtime.onMessage.addListener(
    (
        message,
        sender,
        sendResponse
    ) => {

        if (
            !message ||
            message.action !==
                "collectPolicyData"
        ) {
            return false;
        }

        handleCollectPolicyData(
            message,
            sender
        )
            .then(
                result => {
                    sendResponse(
                        result
                    );
                }
            )
            .catch(
                error => {

                    sendResponse({
                        ok:
                            false,

                        error:
                            error?.message ||
                            String(error),

                        browser_links:
                            [],

                        browser_all_links:
                            [],

                        browser_documents:
                            [],

                        browser_page_text:
                            "",

                        documents:
                            []
                    });
                }
            );

        return true;
    }
);


// ============================================================
// SERVICE WORKER STARTUP
// ============================================================

console.log(
    "[T&C Background] Service worker loaded successfully."
);
