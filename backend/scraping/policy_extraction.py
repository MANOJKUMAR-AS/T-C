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
            "policy_pages": [],
        }

        try:

            # ------------------------------------------------
            # Discover policy pages
            # ------------------------------------------------

            links = find_policy_links(url)

            print(
                f"\nFound "
                f"{len(links)} "
                f"possible policy links."
            )

            # ------------------------------------------------
            # Scrape each policy
            # ------------------------------------------------

            for link in links:

                # IMPORTANT:
                # link is a dictionary.
                #
                # The scraper expects a string URL.
                policy_url = link["url"]

                print(
                    f"\n[{link['type']}] "
                    f"{policy_url}"
                )

                try:

                    # ----------------------------------------
                    # Try static scraper first
                    # ----------------------------------------

                    content = scrape_static_page(
                        policy_url
                    )

                    print(
                        f"Static scraper extracted "
                        f"{len(content)} "
                        f"characters."
                    )

                    # ----------------------------------------
                    # Dynamic fallback
                    # ----------------------------------------

                    if len(
                        content.strip()
                    ) < 500:

                        print(
                            "Static content is too small."
                        )

                        print(
                            "Trying dynamic scraper..."
                        )

                        content = scrape_dynamic_page(
                            policy_url
                        )

                        print(
                            f"Dynamic scraper extracted "
                            f"{len(content)} "
                            f"characters."
                        )

                    # ----------------------------------------
                    # Save successful extraction
                    # ----------------------------------------

                    if len(
                        content.strip()
                    ) >= 500:

                        result[
                            "policy_pages"
                        ].append({

                            "url": policy_url,

                            "type": link["type"],

                            "content": content,
                        })

                        print(
                            "Policy extraction successful."
                        )

                    else:

                        print(
                            "Policy page did not contain "
                            "enough text."
                        )

                except Exception as error:

                    print(
                        f"Failed to scrape "
                        f"{policy_url}: "
                        f"{error}"
                    )

            return result

        except Exception as error:

            return {
                "agent": self.name,
                "source_url": url,
                "policy_pages": [],
                "error": str(error),
            }