from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from urllib.parse import urlparse

from agents.policy_extraction import PolicyExtractionAgent


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
# AGENT 1
# ============================================================

agent1 = PolicyExtractionAgent()


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
        "agent": "Policy Extraction Agent"
    }


# ============================================================
# AGENT 1 ENDPOINT
# ============================================================

@app.post("/api/agent1/analyze")
def analyze_with_agent1(request: AnalyzeRequest):

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
    # Run Agent 1
    # --------------------------------------------------------

    try:

        result = agent1.run(url)

        return result

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )