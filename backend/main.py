from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from urllib.parse import urlparse

from agents.agents1.policy_extraction import PolicyExtractionAgent
from agents.agent2 import Agent2


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="T&C Analyzer Backend",
    version="1.0.0"
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
# REQUEST MODEL
# ============================================================

class AnalyzeRequest(BaseModel):
    url: str


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():

    return {
        "status": "running",
        "service": "T&C Analyzer Backend",
        "agents": [
            "Policy Extraction Agent",
            "Clause Analysis Agent"
        ]
    }


# ============================================================
# AGENT 1 ONLY
# ============================================================

@app.post("/api/agent1/analyze")
def analyze_with_agent1(request: AnalyzeRequest):

    url = request.url.strip()

    parsed = urlparse(url)

    if parsed.scheme not in ["http", "https"]:
        raise HTTPException(
            status_code=400,
            detail="Only HTTP and HTTPS URLs are supported."
        )

    if not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL."
        )

    try:

        result = agent1.run(url)

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# ============================================================
# AGENT 1 → AGENT 2 PIPELINE
# ============================================================

@app.post("/api/analyze")
def analyze_full(request: AnalyzeRequest):

    url = request.url.strip()

    # --------------------------------------------------------
    # Validate URL
    # --------------------------------------------------------

    parsed = urlparse(url)

    if parsed.scheme not in ["http", "https"]:
        raise HTTPException(
            status_code=400,
            detail="Only HTTP and HTTPS URLs are supported."
        )

    if not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="Invalid URL."
        )

    # --------------------------------------------------------
    # AGENT 1
    # --------------------------------------------------------

    try:

        agent1_result = agent1.run(url)

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=f"Agent 1 failed: {error}"
        )

    policy_pages = agent1_result.get(
        "policy_pages",
        []
    )

    # --------------------------------------------------------
    # No policies found
    # --------------------------------------------------------

    if not policy_pages:

        return {
            "source_url": url,
            "agent1": agent1_result,
            "agent2": {
                "status": "skipped",
                "reason": "No policy pages were extracted.",
                "analyses": []
            }
        }

    # --------------------------------------------------------
    # AGENT 2
    # --------------------------------------------------------

    analyses = []

    for policy in policy_pages:

        content = policy.get(
            "content",
            ""
        )

        if not content.strip():
            continue

        try:

            analysis = agent2.analyze(
                content
            )

            analyses.append({
                "url": policy.get("url"),
                "type": policy.get("type"),
                "analysis": analysis.model_dump()
            })

        except Exception as error:

            analyses.append({
                "url": policy.get("url"),
                "type": policy.get("type"),
                "error": str(error)
            })

    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {
        "source_url": url,

        "agent1": {
            "policy_count": len(policy_pages),
            "policy_pages": policy_pages
        },

        "agent2": {
            "status": "completed",
            "analysis_count": len(analyses),
            "analyses": analyses
        }
    }