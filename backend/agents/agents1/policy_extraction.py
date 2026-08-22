from scraping.policy_detector import find_policy_links
from scraping.static_scraper import scrape_static_page
from scraping.dynamic_scraper import scrape_dynamic_page


class PolicyExtractionAgent:

    def __init__(self):
        self.name = "Policy Extraction Agent"

    def run(self, url):

        result = {
            "agent": self.name,
            "source_url": url,
            "policy_pages": []
        }

        try:

            # ================================================
            # STEP 1: DISCOVER POLICY LINKS
            # ================================================

            links = find_policy_links(url)

            print(
                f"\nFound {len(links)} "
                f"possible policy links."
            )

            # ================================================
            # STEP 2: PROCESS EACH POLICY
            # ================================================

            for link in links:

                print("\n" + "-" * 60)

                print(
                    f"Policy type: {link['type']}"
                )

                print(
                    f"Policy URL: {link['url']}"
                )

                # IMPORTANT:
                # `link` is a dictionary.
                #
                # We MUST extract the URL string.
                policy_url = link["url"]

                try:

                    # ========================================
                    # STEP 3: STATIC SCRAPING
                    # ========================================

                    print(
                        "Trying static scraper..."
                    )

                    content = scrape_static_page(
                        policy_url
                    )

                    print(
                        f"Static scraper extracted "
                        f"{len(content)} characters."
                    )

                    # ========================================
                    # STEP 4: DYNAMIC FALLBACK
                    # ========================================

                    if len(content.strip()) < 500:

                        print(
                            "Static extraction produced "
                            "less than 500 characters."
                        )

                        print(
                            "Trying dynamic scraper..."
                        )

                        content = scrape_dynamic_page(
                            policy_url
                        )

                        print(
                            f"Dynamic scraper extracted "
                            f"{len(content)} characters."
                        )

                    # ========================================
                    # STEP 5: SAVE RESULT
                    # ========================================

                    if len(content.strip()) >= 500:

                        result["policy_pages"].append({
                            "url": policy_url,
                            "type": link["type"],
                            "content": content
                        })

                        print(
                            "Policy extraction successful."
                        )

                    else:

                        print(
                            "Policy extraction failed: "
                            "not enough text."
                        )

                except Exception as error:

                    print(
                        f"Failed to scrape "
                        f"{policy_url}: "
                        f"{error}"
                    )

            return result

        except Exception as error:

            result["error"] = str(error)

            return result