"""FastAPI routes for Cloud Analytics."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from agents.cost_analyzer import analyze_costs
from config import settings
from models import (
    HealthResponse,
    QueryRequest,
    QueryResponse,
    StatsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Simple in-memory query counter
_query_count = 0


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy", service="cloud-analytics", version="1.0.0")


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Get system statistics."""
    return StatsResponse(
        total_queries=_query_count,
        aws_connected=bool(settings.aws_access_key_id or settings.aws_region),
        llm_provider=settings.llm_provider,
        available_services=[
            "AWS Cost Explorer",
            "AWS EC2",
            "AWS S3",
            "AWS RDS",
            "AWS Lambda",
            "AWS Organizations",
        ],
    )


@router.post("/analyze", response_model=QueryResponse)
async def analyze(request: QueryRequest):
    """Analyze AWS costs using natural language query."""
    global _query_count  # noqa: PLW0603
    _query_count += 1

    logger.info("Processing query: %s", request.query[:100])

    result = analyze_costs(request.query)

    if not result.get("success"):
        raise HTTPException(
            status_code=500, detail=result.get("error", "Analysis failed")
        )

    return QueryResponse(success=True, data=result.get("data"))


@router.get("/suggestions")
async def get_suggestions():
    """Get suggested queries for the user."""
    return {
        "suggestions": [
            "What is my total AWS spend this month?",
            "Show me cost breakdown by service for the last 3 months",
            "Which AWS region is costing me the most?",
            "Show daily cost trend for the last 30 days",
            "What's my cost forecast for the next month?",
            "List all my active EC2 instances and S3 buckets",
            "Show cost breakdown by linked account",
            "Which services had the biggest cost increase?",
            "Show me costs grouped by Environment tag",
            "Give me a full cost optimization report",
        ]
    }
