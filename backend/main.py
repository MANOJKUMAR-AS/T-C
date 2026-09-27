from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing the agents.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

for _env_file in (
    PROJECT_ROOT / ".env",
    Path(__file__).resolve().parent / ".env",
):
    if _env_file.exists():
        load_dotenv(_env_file, override=False)

from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agents.agent1.policy_extraction import (
    PolicyExtractionAgent,
)

from agents.agent2.agent import Agent2

from agents.agent3.agent import Agent3
from agents.agent3.config import Agent3Config
from agents.agent3.llm_client import GeminiLLMClient
from agents.agent3.models import (
    Agent3Request,
    ClauseInput,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="T&C Analyzer Backend",
    version="12.0.0",
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


# Agent 3 is initialized lazily.
#
# Agent 3 uses Gemini and is created only when Agent 3
# is actually requested.
agent3 = None


def get_agent3() -> Agent3:
    """
    Lazily initialize Agent 3.

    Agent 3 uses the Gemini client and therefore requires
    GEMINI_API_KEY when this endpoint is used.
    """

    global agent3

    if agent3 is not None:
        return agent3

    try:
        # Agent3Config reads defaults at module-import time.
        # Pass the Gemini model explicitly so Agent 3 cannot
        # accidentally inherit the old OpenAI model name.
        agent3_model = (
            os.getenv(
                "AGENT3_MODEL",
                "",
            ).strip()
            or os.getenv(
                "GEMINI_MODEL",
                "gemini-3.5-flash-lite",
            ).strip()
        )

        config = Agent3Config(
            model_name=agent3_model
        )

        llm_client = GeminiLLMClient()

        agent3 = Agent3(
            llm_client=llm_client,
            config=config,
        )

        return agent3

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Agent 3 could not be initialized. "
                f"{exc}"
            ),
        )


# ============================================================
# RUN STORAGE (BOUNDED + TTL)
# ============================================================

import time
from collections import OrderedDict


class BoundedRunStorage:
    """
    Thread-safe bounded in-memory run cache with TTL eviction.
    Prevents unbounded memory growth in production.
    """

    def __init__(self, max_items: int = 100, ttl_seconds: int = 3600):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self._store: OrderedDict[str, tuple[float, Dict[str, Any]]] = OrderedDict()

    def _evict_expired(self) -> None:
        now = time.time()
        expired_keys = [
            k for k, (ts, _) in self._store.items()
            if now - ts > self.ttl_seconds
        ]
        for k in expired_keys:
            self._store.pop(k, None)

    def __setitem__(self, key: str, value: Dict[str, Any]) -> None:
        self._evict_expired()
        if key in self._store:
            self._store.pop(key)
        elif len(self._store) >= self.max_items:
            self._store.popitem(last=False)
        self._store[key] = (time.time(), value)

    def __getitem__(self, key: str) -> Dict[str, Any]:
        self._evict_expired()
        if key not in self._store:
            raise KeyError(key)
        return self._store[key][1]

    def get(self, key: str, default: Any = None) -> Any:
        self._evict_expired()
        if key in self._store:
            return self._store[key][1]
        return default

    def __contains__(self, key: str) -> bool:
        self._evict_expired()
        return key in self._store

    def __len__(self) -> int:
        self._evict_expired()
        return len(self._store)


runs = BoundedRunStorage(max_items=100, ttl_seconds=3600)


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


class Agent3RunRequest(BaseModel):
    run_id: str


class FullAnalysisRequest(BaseModel):
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
            "12.0.0",

        "architecture":
            (
                "browser-first policy discovery "
                "+ Agent 1 "
                "+ Agent 2 "
                "+ Agent 3"
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

        "agent2_gemini_configured":
            bool(
                agent2.api_key
            ),

        "agent2_model":
            agent2.MODEL,

        "agent3":
            "available",

        "agent3_provider":
            "gemini",

        "agent3_model":
            os.getenv(
                "AGENT3_MODEL",
                os.getenv(
                    "GEMINI_MODEL",
                    "gemini-3.5-flash-lite",
                ),
            ),

        "active_runs":
            len(runs),
    }


# ============================================================
# INTERNAL HELPERS
# ============================================================

def get_run_or_404(
    run_id: str,
) -> Dict[str, Any]:
    """
    Retrieve an analysis run or raise 404.
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

    return run


def get_agent1_documents(
    run: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract Agent 1 policy documents while supporting
    all historical field names.
    """

    agent1_result = (
        run.get(
            "agent1"
        )
        or {}
    )

    documents = (
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
        documents,
        list,
    ):
        return []

    return documents


def get_agent2_clauses(
    run: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract normalized clauses from Agent 2.

    Agent 2 returns clauses directly under the result.
    """

    agent2_result = (
        run.get(
            "agent2"
        )
        or {}
    )

    clauses = agent2_result.get(
        "clauses"
    )

    if not isinstance(
        clauses,
        list,
    ):
        return []

    return clauses


def build_agent3_request(
    run: Dict[str, Any],
) -> Agent3Request:
    """
    Convert Agent 2 output into Agent 3 input.

    IMPORTANT:
    Agent 2 is the single source of truth for risk.

    Every Agent 2 clause passes its:
        - category
        - risk_score
        - risk_level
        - risk_reason

    Agent 2 document-level risk:
        - overall_risk
        - overall_risk_score

    is also passed directly to Agent 3.
    """

    agent2_clauses = get_agent2_clauses(
        run
    )

    if not agent2_clauses:
        raise ValueError(
            "Agent 2 produced no clauses for Agent 3."
        )

    # Agent 2's complete result.
    agent2_result = (
        run.get(
            "agent2"
        )
        or {}
    )

    clause_inputs: List[ClauseInput] = []

    for index, clause in enumerate(
        agent2_clauses,
        1,
    ):

        clause_id = str(
            clause.get(
                "clause_id"
            )
            or f"clause_{index}"
        ).strip()

        title = str(
            clause.get(
                "title"
            )
            or "Untitled Clause"
        ).strip()

        source_text = str(
            clause.get(
                "source_text"
            )
            or clause.get(
                "summary"
            )
            or clause.get(
                "explanation"
            )
            or ""
        ).strip()

        if not source_text:
            continue

        source = clause.get(
            "document_url"
        )

        # ----------------------------------------------------
        # Preserve Agent 2's authoritative clause-level risk.
        # ----------------------------------------------------

        category = clause.get(
            "category"
        )

        risk_score = clause.get(
            "risk_score"
        )

        risk_level = clause.get(
            "risk_level"
        )

        risk_reason = clause.get(
            "risk_reason"
        )

        # Safely normalize the score when Agent 2 supplied it.
        normalized_risk_score = None

        if risk_score is not None:
            try:
                normalized_risk_score = int(
                    risk_score
                )
            except (
                TypeError,
                ValueError,
            ):
                normalized_risk_score = None

        clause_inputs.append(
            ClauseInput(
                clause_id=clause_id,
                title=title,
                text=source_text,
                source=(
                    str(source)
                    if source
                    else None
                ),
                category=(
                    str(category)
                    if category
                    else None
                ),
                risk_score=(
                    normalized_risk_score
                ),
                risk_level=(
                    str(risk_level)
                    if risk_level
                    else None
                ),
                risk_reason=(
                    str(risk_reason)
                    if risk_reason
                    else None
                ),
            )
        )

    if not clause_inputs:
        raise ValueError(
            "Agent 2 clauses did not contain usable "
            "source text for Agent 3."
        )

    agent1_result = (
        run.get(
            "agent1"
        )
        or {}
    )

    document_id = str(
        run.get(
            "run_id"
        )
        or "unknown"
    )

    document_title = str(
        agent1_result.get(
            "title"
        )
        or agent1_result.get(
            "document_title"
        )
        or "Terms & Conditions"
    )

    # --------------------------------------------------------
    # Preserve Agent 2's authoritative document-level risk.
    # --------------------------------------------------------

    overall_risk_level = (
        agent2_result.get(
            "overall_risk"
        )
    )

    overall_risk_score = (
        agent2_result.get(
            "overall_risk_score"
        )
    )

    normalized_overall_score = None

    if overall_risk_score is not None:
        try:
            normalized_overall_score = int(
                overall_risk_score
            )
        except (
            TypeError,
            ValueError,
        ):
            normalized_overall_score = None

    return Agent3Request(
        clauses=clause_inputs,
        document_id=document_id,
        document_title=document_title,
        overall_risk_score=(
            normalized_overall_score
        ),
        overall_risk_level=(
            str(overall_risk_level)
            if overall_risk_level
            else None
        ),
    )


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

        if not isinstance(
            result,
            dict,
        ):
            raise RuntimeError(
                "Agent 1 returned an invalid result."
            )

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

        run_id = uuid4().hex

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

            "agent3":
                None,
        }

        print()
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
        print()

        return {
            "success":
                True,

            "run_id":
                run_id,

            "agent1":
                result,

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

    run = get_run_or_404(
        request.run_id
    )

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

    policies = get_agent1_documents(
        run
    )

    print()
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
    print()

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

    run[
        "agent2"
    ] = result

    return {
        "success":
            True,

        "run_id":
            request.run_id,

        "agent2":
            result,
    }


# ============================================================
# AGENT 3
# ============================================================

@app.post(
    "/api/agent3/analyze"
)
def analyze_agent3(
    request: Agent3RunRequest,
):
    """
    Run Agent 3 against the clauses produced by Agent 2.
    """

    run = get_run_or_404(
        request.run_id
    )

    if run.get(
        "agent2"
    ) is None:

        raise HTTPException(
            status_code=400,
            detail=(
                "Agent 2 must be run before Agent 3."
            ),
        )

    if run.get(
        "agent3"
    ) is not None:

        return {
            "success":
                True,

            "run_id":
                request.run_id,

            "agent3":
                run["agent3"],
        }

    try:

        request_data = build_agent3_request(
            run
        )

        current_agent3 = get_agent3()

        print()
        print(
            "=" * 70
        )
        print(
            "AGENT 3 REQUEST"
        )
        print(
            f"Run ID: {request.run_id}"
        )
        print(
            f"Clauses sent: {len(request_data.clauses)}"
        )
        print(
            "=" * 70
        )
        print()

        result = current_agent3.analyze(
            request_data
        )

        result_dict = result.to_dict()

        run[
            "agent3"
        ] = result_dict

        print()
        print(
            "=" * 70
        )
        print(
            "AGENT 3 COMPLETE"
        )
        print(
            f"Clauses analyzed: {len(result.analyses)}"
        )
        print(
            f"Overall risk: {result.overall_risk_level}"
        )
        print(
            f"Overall score: {result.overall_risk_score}"
        )
        print(
            "=" * 70
        )
        print()

        return {
            "success":
                True,

            "run_id":
                request.run_id,

            "agent3":
                result_dict,
        }

    except HTTPException:
        raise

    except ValueError as exc:

        print(
            "Agent 3 VALIDATION ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except RuntimeError as exc:

        print(
            "Agent 3 RUNTIME ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

    except Exception as exc:

        print(
            "Agent 3 ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


# ============================================================
# FULL PIPELINE
# ============================================================

@app.post(
    "/api/analyze"
)
def analyze_full_pipeline(
    request: FullAnalysisRequest,
):
    """
    Run the complete T&C analysis pipeline:

        Agent 1
           ↓
        Agent 2
           ↓
        Agent 3

    This is the endpoint intended for the Chrome extension.
    """

    url = request.url.strip()

    validate_url(
        url
    )

    # --------------------------------------------------------
    # STEP 1: Agent 1
    # --------------------------------------------------------

    try:

        agent1_result = agent1.run(
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

        if not isinstance(
            agent1_result,
            dict,
        ):
            raise RuntimeError(
                "Agent 1 returned an invalid result."
            )

    except Exception as exc:

        print(
            "FULL PIPELINE Agent 1 ERROR:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Agent 1 failed: "
                f"{exc}"
            ),
        )

    documents = (
        agent1_result.get(
            "documents"
        )
        or agent1_result.get(
            "policy_documents"
        )
        or agent1_result.get(
            "browser_documents"
        )
        or agent1_result.get(
            "policy_pages"
        )
        or []
    )

    if not isinstance(
        documents,
        list,
    ):
        documents = []

    agent1_result[
        "documents"
    ] = documents

    agent1_result[
        "policy_documents"
    ] = documents

    agent1_result[
        "policy_pages"
    ] = documents

    agent1_result[
        "document_count"
    ] = len(
        documents
    )

    run_id = uuid4().hex

    run = {
        "run_id":
            run_id,

        "created_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "url":
            url,

        "agent1":
            agent1_result,

        "agent2":
            None,

        "agent3":
            None,
    }

    runs[
        run_id
    ] = run

    # --------------------------------------------------------
    # STEP 2: Agent 2
    # --------------------------------------------------------

    if not documents:

        agent2_result = {
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

        try:

            agent2_result = agent2.run(
                documents
            )

        except Exception as exc:

            print(
                "FULL PIPELINE Agent 2 ERROR:",
                exc,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Agent 2 failed: "
                    f"{exc}"
                ),
            )

    run[
        "agent2"
    ] = agent2_result

    # --------------------------------------------------------
    # STEP 3: Agent 3
    # --------------------------------------------------------

    agent3_result = None

    agent2_clauses = (
        agent2_result.get(
            "clauses",
            []
        )
        if isinstance(
            agent2_result,
            dict,
        )
        else []
    )

    if agent2_clauses:

        try:

            agent3_request = build_agent3_request(
                run
            )

            current_agent3 = get_agent3()

            agent3_response = current_agent3.analyze(
                agent3_request
            )

            agent3_result = (
                agent3_response.to_dict()
            )

            run[
                "agent3"
            ] = agent3_result

        except HTTPException:
            raise

        except Exception as exc:

            print(
                "FULL PIPELINE Agent 3 ERROR:",
                exc,
            )

            raise HTTPException(
                status_code=500,
                detail=(
                    "Agent 3 failed: "
                    f"{exc}"
                ),
            )

    else:

        agent3_result = {
            "status":
                "unavailable",

            "error":
                (
                    "Agent 2 produced no clauses "
                    "for Agent 3."
                ),

            "analyses":
                [],

            "overall_risk_level":
                "UNAVAILABLE",

            "overall_risk_score":
                0,
        }

        run[
            "agent3"
        ] = agent3_result

    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    return {
        "success":
            True,

        "run_id":
            run_id,

        "url":
            url,

        "agent1":
            agent1_result,

        "agent2":
            agent2_result,

        "agent3":
            agent3_result,
    }


# ============================================================
# RUN STATUS
# ============================================================

@app.get(
    "/api/runs/{run_id}"
)
def get_run(
    run_id: str,
):
    """
    Return the complete stored analysis state.
    """

    run = get_run_or_404(
        run_id
    )

    return {
        "success":
            True,

        **run,
    }

