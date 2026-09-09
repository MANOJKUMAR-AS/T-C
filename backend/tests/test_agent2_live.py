import os
import sys
from pathlib import Path

from dotenv import load_dotenv


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

# test_agent2_live.py
#   ↓
# tests
#   ↓
# backend
#   ↓
# t&c
#
# Therefore:
#   parents[1] = backend
#   parents[2] = t&c

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------
# Python import path
# ---------------------------------------------------------

# Allows:
# from agents.agent2 import Agent2

sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv(PROJECT_ROOT / ".env")


# Import Agent 2 after configuring the environment
from agents.agent2 import Agent2


# ---------------------------------------------------------
# Main test
# ---------------------------------------------------------

def main():

    print("========================================")
    print("       AGENT 2 GROQ LIVE TEST")
    print("========================================")

    print(
        "Groq API key:",
        "FOUND" if os.getenv("GROQ_API_KEY") else "MISSING"
    )

    print(
        "Model:",
        os.getenv("AGENT2_MODEL")
    )

    print("\nCreating Agent 2...")

    try:
        agent2 = Agent2()

    except Exception as error:
        print("\nERROR CREATING AGENT 2:")
        print(type(error).__name__)
        print(error)
        return

    print("Agent 2 created successfully.")

    # -----------------------------------------------------
    # Sample Terms & Conditions
    # -----------------------------------------------------

    sample_text = """
    Subscription Terms

    Your subscription automatically renews at the end
    of each billing period unless you cancel before
    the renewal date.

    We may charge your payment method for the applicable
    subscription fee.

    You may cancel your subscription through your account
    settings.

    We may collect information about your use of the
    service, including device information and usage data.

    We may share this information with service providers
    that help us operate the service.
    """

    print("\nSending document to Agent 2...")
    print("Please wait...\n")

    # -----------------------------------------------------
    # Run Agent 2
    # -----------------------------------------------------

    try:
        result = agent2.analyze(sample_text)

    except Exception as error:
        print("========================================")
        print("       AGENT 2 ERROR")
        print("========================================")

        print("\nError type:")
        print(type(error).__name__)

        print("\nError message:")
        print(error)

        return

    # -----------------------------------------------------
    # Display result
    # -----------------------------------------------------

    print("========================================")
    print("       AGENT 2 RESULT")
    print("========================================\n")

    print(result.model_dump_json(indent=2))

    print("\n========================================")
    print("       TEST SUCCESSFUL")
    print("========================================")


# ---------------------------------------------------------
# Entry point
# ---------------------------------------------------------

if __name__ == "__main__":
    main()