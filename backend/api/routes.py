"""System endpoints: health, stats, provider status, stateless analysis, suggestions."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session as DBSession

from backend.agents.agent_harness import AgentHarness
from backend.agents.cost_analyzer import analyze_costs
from backend.agents.tools import tool_names
from backend.config import SUPPORTED_CLOUD_PROVIDERS, settings
from backend.database import get_db
from backend.schemas import (
    HealthResponse,
    ProviderStatus,
    ProvidersResponse,
    QueryRequest,
    QueryResponse,
    StatsResponse,
)
from backend.services.session_store import SessionNotFound, SessionStore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["system"])

_COUNTERS = {"stateless_queries": 0}

SUGGESTIONS: dict[str, list[str]] = {
    "general": [
        "What is my total cloud spend this month across all providers?",
        "Which services had the biggest cost increase recently?",
        "Give me a cost optimization report with concrete savings",
    ],
    "aws": [
        "Show my AWS cost breakdown by service for the last 3 months",
        "Show the daily AWS cost trend for the last 30 days",
        "Which AWS region is costing me the most?",
        "What is my AWS cost forecast for the next 30 days?",
        "Show AWS costs grouped by the Environment tag",
        "List my active EC2 instances, RDS databases and S3 buckets",
    ],
    "azure": [
        "Show my Azure spend by service for the last 30 days",
        "Show the daily Azure cost trend for this month",
        "List my Azure resources grouped by type",
    ],
    "gcp": [
        "Show my GCP costs by service for the last 30 days",
        "Show the daily GCP cost trend for this month",
        "Which billing account is my GCP project linked to?",
    ],
    "digitalocean": [
        "What is my DigitalOcean month-to-date usage?",
        "Estimate my monthly DigitalOcean run-rate from current resources",
        "Show my DigitalOcean invoice trend for the last 6 months",
    ],
}


def _aws_ambient_credentials() -> bool:
    """Cheap check for AWS credentials that boto3 would pick up without settings."""
    if os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_PROFILE"):
        return True
    home = Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE", "~/.aws/credentials")).expanduser()
    return home.exists()


def provider_statuses() -> list[ProviderStatus]:
    """Configuration status of each supported cloud provider."""
    statuses = []
    for name in SUPPORTED_CLOUD_PROVIDERS:
        info = dict(settings.provider_status().get(name, {}))
        configured = bool(info.pop("configured", False))
        if name == "aws" and not configured and _aws_ambient_credentials():
            configured = True
            info["source"] = "ambient credentials"
        statuses.append(ProviderStatus(name=name, configured=configured, details=info, tools=tool_names([name])))
    return statuses


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model_name(),
    )


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: DBSession = Depends(get_db)):
    """System statistics."""
    store = SessionStore(db)
    return StatsResponse(
        total_queries=_COUNTERS["stateless_queries"] + store.count_messages(role="user"),
        active_sessions=store.count_sessions(),
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model_name(),
        providers={status.name: status.configured for status in provider_statuses()},
    )


@router.get("/providers", response_model=ProvidersResponse)
def get_providers():
    """Which cloud providers are configured and which tools they expose."""
    return ProvidersResponse(
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model_name(),
        providers=provider_statuses(),
    )


def _analyze_in_session(session_id: str, query: str) -> QueryResponse:
    with SessionStore() as store:
        harness = AgentHarness(store=store)
        try:
            harness.load_session(session_id)
        except SessionNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        turn = harness.analyze(query)
        return QueryResponse(
            success=turn.success,
            data=turn.analysis,
            error=turn.error,
            session_id=harness.session_id,
        )


def _analyze_stateless(request: QueryRequest) -> QueryResponse:
    _COUNTERS["stateless_queries"] += 1
    providers = None
    if request.connection_context:
        providers = [name for name in request.connection_context if name in SUPPORTED_CLOUD_PROVIDERS] or None
    result = analyze_costs(request.query, providers=providers, connection_context=request.connection_context)
    if not result.get("success"):
        return QueryResponse(success=False, data=None, error=result.get("error", "Analysis failed"))
    return QueryResponse(success=True, data=result["data"])


@router.post("/analyze", response_model=QueryResponse)
async def analyze(request: QueryRequest):
    """Analyze a natural-language cost question.

    With ``session_id`` the query runs inside that session (memory + history). Without it a
    fresh, stateless agent is used and nothing is persisted.
    """
    logger.info("Processing query (session=%s): %s", request.session_id, request.query[:100])
    if request.session_id:
        return await run_in_threadpool(_analyze_in_session, request.session_id, request.query)
    return await run_in_threadpool(_analyze_stateless, request)


@router.get("/suggestions")
def get_suggestions(provider: str | None = None):
    """Suggested queries, configured providers first."""
    if provider:
        return {"suggestions": SUGGESTIONS.get(provider.lower(), SUGGESTIONS["general"])}
    configured = [status.name for status in provider_statuses() if status.configured]
    ordered = list(SUGGESTIONS["general"])
    for name in configured + [p for p in SUPPORTED_CLOUD_PROVIDERS if p not in configured]:
        ordered.extend(SUGGESTIONS[name][:3])
    return {"suggestions": ordered}
