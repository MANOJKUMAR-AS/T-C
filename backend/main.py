from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.agents1.policy_extraction import (
    PolicyExtractionAgent,
)

from agents.agent2.agent import Agent2


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="T&C Analyzer Backend",
    version="10.0.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AGENTS
# ============================================================

agent1 = PolicyExtractionAgent()
agent2 = Agent2()


# ============================================================
# RUN STORAGE
# ============================================================

runs: Dict[
    str,
    Dict[str, Any],
] = {}


# ============================================================
# REQUEST MODELS
# ============================================================

class Agent1Request(BaseModel):
    url: str

    browser_links: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    browser_documents: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    browser_all_links: List[
        Dict[str, Any]
    ] = Field(
        default_factory=list
    )

    browser_page_text: str = ""

    browser_title: str = ""


class Agent2Request(BaseModel):
    run_id: str


# ============================================================
# URL VALIDATION
# ============================================================

def validate_url(
    url: str,
) -> None:
    """
    Validate that the supplied URL is HTTP/HTTPS.
    """

    parsed = urlparse(
        url
    )

    if (
        parsed.scheme
        not in (
            "http",
            "https",
        )
        or not parsed.netloc
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only valid HTTP/HTTPS "
                "URLs are supported."
            ),
        )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "status": "running",

        "service":
            "T&C Analyzer",

        "version":
            "10.0.0",

        "architecture":
            (
                "browser-first policy discovery "
                "+ backend fallback "
                "+ Agent 2 clause analysis"
            ),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "status":
            "ok",

        "agent1":
            agent1.name,

        "agent2":
            agent2.name,

        "gemini_configured":
            bool(
                agent2.api_key
            ),

        "model":
            agent2.MODEL,

        "active_runs":
            len(runs),
    }


# ============================================================
# AGENT 1
# ============================================================

@app.post(
    "/api/agent1/analyze"
)
def analyze_agent1(
    request: Agent1Request,
):
    """
    Run Agent 1 using browser-collected data.

    Browser extraction is the primary source.

    Firecrawl is handled inside Agent 1 as a fallback.
    """

    url = request.url.strip()

    validate_url(
        url
    )

    try:

        # ----------------------------------------------------
        # Run Agent 1
        # ----------------------------------------------------

        result = agent1.run(
            url=url,

            browser_links=
                request.browser_links,

            browser_documents=
                request.browser_documents,

            browser_all_links=
                request.browser_all_links,

            browser_page_text=
                request.browser_page_text,

            browser_title=
                request.browser_title,
        )


        # ----------------------------------------------------
        # Ensure result is a dictionary
        # ----------------------------------------------------

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Agent 1 returned an invalid result."
            )


        # ----------------------------------------------------
        # Normalize Agent 1 document field
        #
        # Agent 1 currently uses "documents".
        #
        # The rest of the application historically uses
        # "policy_pages".
        #
        # We expose BOTH so the frontend and Agent 2 stay
        # compatible.
        # ----------------------------------------------------

        documents = (
            result.get(
                "documents"
            )
            or result.get(
                "policy_documents"
            )
            or result.get(
                "browser_documents"
            )
            or result.get(
                "policy_pages"
            )
            or []
        )


        if not isinstance(
            documents,
            list,
        ):
            documents = []


        # ----------------------------------------------------
        # Normalize document aliases
        # ----------------------------------------------------

        result[
            "documents"
        ] = documents

        result[
            "policy_documents"
        ] = documents

        result[
            "policy_pages"
        ] = documents

        result[
            "browser_documents"
        ] = documents

        result[
            "document_count"
        ] = len(
            documents
        )


        # ----------------------------------------------------
        # Run ID
        # ----------------------------------------------------

        run_id = uuid4().hex


        # ----------------------------------------------------
        # Store complete analysis state
        # ----------------------------------------------------

        runs[
            run_id
        ] = {
            "run_id":
                run_id,

            "created_at":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "url":
                url,

            "agent1":
                result,

            "agent2":
                None,
        }


        # ----------------------------------------------------
        # Logging
        # ----------------------------------------------------

        print(
            ""
        )

        print(
            "=" * 70
        )

        print(
            "AGENT 1 API COMPLETE"
        )

        print(
            f"Run ID: {run_id}"
        )

        print(
            f"Policy documents: {len(documents)}"
        )

        print(
            "=" * 70
        )

        print(
            ""
        )


        # ----------------------------------------------------
        # API RESPONSE
        # ----------------------------------------------------

        return {
            "success":
                True,

            "run_id":
                run_id,

            "agent1":
                result,

            # Top-level aliases for frontend
            # compatibility.
            "documents":
                documents,

            "policy_documents":
                documents,

            "policy_pages":
                documents,

            "document_count":
                len(documents),
        }


    except HTTPException:
        raise


    except Exception as exc:

        print(
            "Agent 1 API ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# AGENT 2
# ============================================================

@app.post(
    "/api/agent2/analyze"
)
def analyze_agent2(
    request: Agent2Request,
):
    """
    Run Agent 2 against the policy documents produced by
    Agent 1.
    """

    run = runs.get(
        request.run_id
    )


    # --------------------------------------------------------
    # Validate run
    # --------------------------------------------------------

    if not run:

        raise HTTPException(
            status_code=404,
            detail=(
                "Analysis run not found."
            ),
        )


    # --------------------------------------------------------
    # Return cached Agent 2 result
    # --------------------------------------------------------

    if run.get(
        "agent2"
    ) is not None:

        return {
            "success":
                True,

            "run_id":
                request.run_id,

            "agent2":
                run["agent2"],
        }


    # --------------------------------------------------------
    # Get Agent 1 documents
    #
    # Support all known field names.
    # --------------------------------------------------------

    agent1_result = (
        run.get(
            "agent1"
        )
        or {}
    )


    policies = (
        agent1_result.get(
            "policy_pages"
        )
        or agent1_result.get(
            "documents"
        )
        or agent1_result.get(
            "policy_documents"
        )
        or agent1_result.get(
            "browser_documents"
        )
        or []
    )


    if not isinstance(
        policies,
        list,
    ):
        policies = []


    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    print(
        ""
    )

    print(
        "=" * 70
    )

    print(
        "AGENT 2 REQUEST"
    )

    print(
        f"Run ID: {request.run_id}"
    )

    print(
        f"Policy documents received: {len(policies)}"
    )

    print(
        "=" * 70
    )

    print(
        ""
    )


    # --------------------------------------------------------
    # No policies
    # --------------------------------------------------------

    if not policies:

        result = {
            "agent":
                agent2.name,

            "status":
                "unavailable",

            "error":
                (
                    "Agent 1 found no policy "
                    "documents."
                ),

            "clauses":
                [],

            "clause_count":
                0,

            "summary": {
                "overall_score":
                    0,

                "overall_risk":
                    "UNAVAILABLE",

                "critical":
                    0,

                "high":
                    0,

                "medium":
                    0,

                "low":
                    0,

                "key_findings":
                    [],
            },

            "overall_risk":
                "UNAVAILABLE",
        }

    else:

        # ----------------------------------------------------
        # Agent 2 analysis
        # ----------------------------------------------------

        try:

            result = agent2.run(
                policies
            )

        except Exception as exc:

            print(
                "Agent 2 ERROR:",
                exc,
            )

            raise HTTPException(
                status_code=500,
                detail=str(exc),
            )


    # --------------------------------------------------------
    # Store Agent 2 result
    # --------------------------------------------------------

    run[
        "agent2"
    ] = result


    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return {
        "success":
            True,

        "run_id":
            request.run_id,

        "agent2":
            result,
    }


# ============================================================
# OPTIONAL RUN STATUS ENDPOINT
# ============================================================

@app.get(
    "/api/runs/{run_id}"
)
def get_run(
    run_id: str,
):
    """
    Return the complete stored analysis state.

    Useful for debugging and frontend recovery.
    """

    run = runs.get(
        run_id
    )

    if not run:

        raise HTTPException(
            status_code=404,
            detail=(
                "Analysis run not found."
            ),
        )

    return {
        "success":
            True,

        **run,
    }