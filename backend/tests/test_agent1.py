from agents.agents1.policy_extraction import PolicyExtractionAgent

agent = PolicyExtractionAgent()

url = "https://www.swiggy.com/"

result = agent.run(url)


print("\n" + "=" * 60)
print("AGENT 1 RESULT")
print("=" * 60)

print(
    f"\nSource: "
    f"{result['source_url']}"
)

print(
    f"Policies found: "
    f"{len(result['policy_pages'])}"
)


if "error" in result:

    print(
        f"\nError: "
        f"{result['error']}"
    )


for policy in result["policy_pages"]:

    print(
        "\n" + "-" * 60
    )

    print(
        f"Type: "
        f"{policy['type']}"
    )

    print(
        f"URL: "
        f"{policy['url']}"
    )

    print(
        f"Characters extracted: "
        f"{len(policy['content'])}"
    )

    print("\nPreview:")

    print(
        policy["content"][:500]
    )