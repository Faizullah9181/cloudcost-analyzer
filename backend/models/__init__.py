"""Pydantic schemas for API request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Natural language query from the user."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language query about AWS costs",
    )


class CostDataPoint(BaseModel):
    """Single cost data point for charts."""

    label: str
    value: float
    unit: str = "USD"


class CostBreakdown(BaseModel):
    """Service-level cost breakdown."""

    service: str
    cost: float
    percentage: float
    change: float = 0.0  # % change from previous period


class TimeSeriesPoint(BaseModel):
    """Time series data point."""

    date: str
    cost: float
    service: str = "Total"


class AnalysisResult(BaseModel):
    """Full analysis result returned to the frontend."""

    summary: str
    total_cost: float = 0.0
    currency: str = "USD"
    period: str = ""
    service_breakdown: list[CostBreakdown] = []
    time_series: list[TimeSeriesPoint] = []
    top_costs: list[CostDataPoint] = []
    recommendations: list[str] = []
    raw_response: str = ""
    chart_type: str = "bar"  # bar | line | pie | area
    a2ui_messages: list[dict[str, Any]] = []


class QueryResponse(BaseModel):
    """API response wrapping the analysis result."""

    success: bool
    data: AnalysisResult | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    service: str
    version: str


class StatsResponse(BaseModel):
    """System stats response."""

    total_queries: int
    aws_connected: bool
    llm_provider: str
    available_services: list[str]


class ServiceListResponse(BaseModel):
    """List of AWS services."""

    services: list[dict[str, Any]]
