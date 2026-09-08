
"use strict";

console.log("[T&C] Universal browser collector loaded:", location.href);

function cleanText(value) {
    return String(value || "")
        .replace(/\u00a0/g, " ")
        .replace(/\r\n?/g, "\n")
        .replace(/[ \t]+/g, " ")
        .split("\n")
        .map(x => x.trim())
        .filter(Boolean)
        .join("\n")
        .trim();
}

function absoluteUrl(value) {
    try {
        return new URL(value, location.href).href;
    } catch {
        return "";
    }
}

function classifyPolicy(url, label) {
    const s = `${url} ${label}`.toLowerCase();

    if (/privacy|privacypolicy|data-protection|data-privacy/.test(s)) return "privacy";
    if (/cookie|tracking-technolog/.test(s)) return "cookies";
    if (/terms?[-_ ]?(of[-_ ]?(use|service)|and[-_ ]?conditions?)|termsofuse|termsandcondition|user[-_ ]?agreement/.test(s)) return "terms";
    if (/return|refund|payment|fee|promotion|grievance|legal/.test(s)) return "legal";

    return "";
}

function collect() {
    const anchors = Array.from(document.querySelectorAll("a[href]"));
    const all = [];
    const policies = [];
    const seen = new Set();

    for (const a of anchors) {
        const url = absoluteUrl(a.getAttribute("href"));
        if (!url || !/^https?:/i.test(url)) continue;

        const text = cleanText(a.innerText || a.textContent || "");
        const title = cleanText(a.getAttribute("title") || "");
        const aria = cleanText(a.getAttribute("aria-label") || "");
        const key = url.split("#")[0];

        if (!seen.has(key)) {
            seen.add(key);
            all.push({ url, text, title, aria });
        }

        const type = classifyPolicy(url, `${text} ${title} ${aria}`);
        if (type) {
            policies.push({
                url,
                text,
                title,
                aria,
                type,
                source: "browser_dom_link"
            });
        }
    }

    const pageText = cleanText(document.body?.innerText || "");

    // If the current page itself is a policy document, preserve it.
    const currentType = classifyPolicy(
        location.href,
        `${document.title} ${pageText.slice(0, 8000)}`
    );

    const documents = [];
    if (
        currentType &&
        pageText.length >= 500 &&
        /privacy|terms|conditions|cookies|refund|return|payment|legal|grievance/i.test(
            `${document.title} ${pageText.slice(0, 12000)}`
        )
    ) {
        documents.push({
            url: location.href,
            title: document.title || "",
            type: currentType,
            content: pageText,
            text_content: pageText,
            source: "current_browser_document"
        });
    }

    return {
        success: true,
        url: location.href,
        title: document.title || "",
        browser_links: policies,
        browser_all_links: all,
        browser_documents: documents,
        browser_page_text: pageText.slice(0, 100000),
    };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.action !== "collectPolicyData") return;

    try {
        sendResponse(collect());
    } catch (error) {
        sendResponse({
            success: false,
            error: error?.message || String(error),
            browser_links: [],
            browser_all_links: [],
            browser_documents: [],
            browser_page_text: "",
        });
    }
    return true;
});
