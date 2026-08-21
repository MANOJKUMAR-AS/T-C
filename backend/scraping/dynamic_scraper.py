from playwright.sync_api import sync_playwright


def scrape_dynamic_page(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        page.goto(
            url,
            wait_until="networkidle",
            timeout=30000
        )

        for selector in [
            "script",
            "style",
            "nav",
            "header",
            "footer",
            "aside",
            "form"
        ]:
            page.locator(selector).evaluate_all(
                "(elements) => elements.forEach(e => e.remove())"
            )

        text = page.locator("body").inner_text()

        browser.close()

        return text.strip()