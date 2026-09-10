"""Pydantic schemas for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.config import SUPPORTED_CLOUD_PROVIDERS, settings


# ----- analysis ------------------------------------------------------------


class CostDataPoint(BaseModel):
    """Single cost data point for charts."""

    label: str
    value: float
    unit: str = "USD"


class CostBreakdown(BaseModel):
    """Service-level cost breakdown."""

    service: str
    cost: float = 0.0
    percentage: float = 0.0
    change: float = 0.0  # % change from previous period


class TimeSeriesPoint(BaseModel):
    """Time series data point."""

    date: str
    cost: float = 0.0
    service: str = "Total"


class AnalysisResult(BaseModel):
    """Structured analysis returned to the frontend and CLI."""

    summary: str
    total_cost: float = 0.0
    currency: str = "USD"
    period: str = ""
    providers: dict[str, Any] = Field(default_factory=dict)
    service_breakdown: list[CostBreakdown] = Field(default_factory=list)
    time_series: list[TimeSeriesPoint] = Field(default_factory=list)
    top_costs: list[CostDataPoint] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    raw_response: str = ""
    chart_type: str = "bar"  # bar | line | pie | area
    query_type: str = "analysis"
    a2ui_messages: list[dict[str, Any]] = Field(default_factory=list)


class QueryRequest(BaseModel):
    """Natural language query. ``session_id`` is optional for one-off (stateless) analysis."""

    query: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None
    connection_context: dict[str, Any] | None = None


class QueryResponse(BaseModel):
    """API response wrapping the analysis result."""

    success: bool
    data: AnalysisResult | None = None
    error: str | None = None
    session_id: str | None = None


# ----- system ----------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_provider: str
    llm_model: str


class StatsResponse(BaseModel):
    total_queries: int
    active_sessions: int
    llm_provider: str
    llm_model: str
    providers: dict[str, Any]


class ProviderStatus(BaseModel):
    name: str
    configured: bool
    details: dict[str, Any] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)


class ProvidersResponse(BaseModel):
    llm_provider: str
    llm_model: str
    providers: list[ProviderStatus]


# ----- sessions --------------------------------------------------------------


def _normalise_providers(value: Any) -> dict[str, bool]:
    if value is None:
        return {}
    if isinstance(value, dict):
        items = [(str(name).lower(), bool(enabled)) for name, enabled in value.items()]
    elif isinstance(value, (list, tuple, set)):
        items = [(str(name).lower(), True) for name in value]
    else:
        raise ValueError("cloud_providers must be a mapping or a list of provider names")
    unknown = [name for name, _ in items if name not in SUPPORTED_CLOUD_PROVIDERS]
    if unknown:
        raise ValueError(f"Unsupported cloud provider(s): {', '.join(sorted(unknown))}")
    return dict(items)


class SessionCreate(BaseModel):
    """Create session request. ``cloud_providers`` may be a list or a name -> enabled map."""

    name: str = Field(..., min_length=1, max_length=255)
    cloud_providers: dict[str, bool] = Field(default_factory=lambda: {"aws": True})
    llm_provider: str | None = None
    connection_context: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("cloud_providers", mode="before")
    @classmethod
    def _providers(cls, value: Any) -> dict[str, bool]:
        providers = _normalise_providers(value)
        if not any(providers.values()):
            raise ValueError("At least one cloud provider must be enabled")
        return providers

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _llm(cls, value: Any) -> str:
        return str(value or settings.llm_provider).strip().lower()


class SessionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    connection_context: dict[str, Any] | None = None
    tags: list[str] | None = None


class SessionResponse(BaseModel):
    """Session summary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    user_id: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    context_tokens: int = 0
    compression_count: int = 0
    cloud_providers: dict[str, bool]
    connection_context: dict[str, Any] = Field(default_factory=dict)
    llm_provider: str
    llm_model: str = ""
    is_active: bool
    tags: list[str] = Field(default_factory=list)


class MessageAdd(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    id: str
    seq: int
    role: str
    content: str
    timestamp: datetime | None = None
    tokens_used: int = 0
    provider: str | None = None
    tags: list[str] = Field(default_factory=list)
    analysis: dict[str, Any] | None = None
    is_summary: bool = False


class MessagesResponse(BaseModel):
    session_id: str
    message_count: int
    messages: list[MessageResponse]


class ChatRequest(BaseModel):
    """Run the agent for one turn inside a session."""

    query: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    success: bool
    session_id: str
    message: str
    data: AnalysisResult | None = None
    error: str | None = None
    memory: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class SessionAnalysisUpdate(BaseModel):
    analysis: dict[str, Any]


class CompressResponse(BaseModel):
    session_id: str
    compressed_messages: int
    pruned_messages: int
    summary: str
    compression_count: int
