"""Agent construction and response parsing for multi-cloud cost analysis.

This module is stateless. ``AgentHarness`` adds memory and persistence on top;
``analyze_costs`` is the one-shot path used by the legacy ``/api/analyze`` endpoint.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.agent.agent_result import AgentResult
from strands.models.model import Model

from backend.a2ui import build_cost_analysis_a2ui_messages
from backend.agents.llm import build_model
from backend.agents.prompts import build_base_system_prompt
from backend.agents.tools import get_tools
from backend.config import settings
from backend.memory.memory_manager import detect_query_type

logger = logging.getLogger(__name__)

CHART_TYPES = {"bar", "line", "pie", "area"}
QUERY_TYPES = {"costs", "trend", "forecast", "comparison", "inventory", "optimization", "analysis"}
MAX_BREAKDOWN_ITEMS = 20


# ----- JSON extraction ------------------------------------------------------------------


def _balanced_json_objects(text: str) -> list[str]:
    """Yield candidate top-level ``{...}`` substrings using brace matching (string-aware)."""
    candidates: list[str] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                candidates.append(text[start : index + 1])
                start = -1
    return candidates


def extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from model output (plain, fenced, or embedded in prose)."""
    if not text:
        return None
    stripped = text.strip()
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        pass

    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", stripped):
        try:
            parsed = json.loads(match.group(1).strip())
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            continue

    best: dict[str, Any] | None = None
    for candidate in _balanced_json_objects(stripped):
        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict) and (best is None or len(candidate) > len(json.dumps(best))):
            best = parsed
    return best


# Backwards-compatible alias
_extract_json = extract_json


# ----- normalisation ------------------------------------------------------------------------


def _to_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^0-9.\-eE]", "", value.replace(",", ""))
        try:
            return float(cleaned) if cleaned not in ("", "-", ".", "-.") else default
        except ValueError:
            return default
    return default


def _normalise_breakdown(raw: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        raw = [{"service": name, "cost": cost} for name, cost in raw.items()]
    if not isinstance(raw, list):
        return items
    for entry in raw:
        if isinstance(entry, dict):
            name = str(entry.get("service") or entry.get("name") or entry.get("label") or "").strip()
            if not name:
                continue
            items.append(
                {
                    "service": name,
                    "cost": round(_to_float(entry.get("cost", entry.get("value"))), 2),
                    "percentage": round(_to_float(entry.get("percentage")), 2),
                    "change": round(_to_float(entry.get("change")), 2),
                }
            )
    items.sort(key=lambda item: item["cost"], reverse=True)
    return items[:MAX_BREAKDOWN_ITEMS]


def _normalise_time_series(raw: Any) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return points
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        date = str(entry.get("date") or entry.get("month") or entry.get("day") or "").strip()
        if not date:
            continue
        points.append(
            {
                "date": date,
                "cost": round(_to_float(entry.get("cost", entry.get("value"))), 2),
                "service": str(entry.get("service") or "Total"),
            }
        )
    return points


def _normalise_providers(raw: Any) -> dict[str, dict[str, Any]]:
    providers: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return providers
    for name, data in raw.items():
        entry: dict[str, Any] = {"total": 0.0, "services": {}}
        if isinstance(data, dict):
            entry["total"] = round(_to_float(data.get("total", data.get("total_cost"))), 2)
            services = data.get("services")
            if isinstance(services, dict):
                entry["services"] = {str(k): round(_to_float(v), 2) for k, v in services.items()}
            elif isinstance(services, list):
                entry["services"] = {
                    str(item.get("service", "")): round(_to_float(item.get("cost")), 2)
                    for item in services
                    if isinstance(item, dict) and item.get("service")
                }
            if not entry["total"] and entry["services"]:
                entry["total"] = round(sum(entry["services"].values()), 2)
        else:
            entry["total"] = round(_to_float(data), 2)
        providers[str(name).lower()] = entry
    return providers


def normalize_analysis(parsed: dict[str, Any] | None, raw_text: str, query: str = "") -> dict[str, Any]:
    """Turn (possibly partial) model JSON into the ``AnalysisResult`` shape with A2UI messages."""
    parsed = parsed if isinstance(parsed, dict) else {}
    raw_text = raw_text or ""

    summary = str(parsed.get("summary") or "").strip()
    if not summary:
        summary = raw_text.strip() or "Analysis completed."

    providers = _normalise_providers(parsed.get("providers"))
    breakdown = _normalise_breakdown(parsed.get("service_breakdown"))
    time_series = _normalise_time_series(parsed.get("time_series"))

    total_cost = round(_to_float(parsed.get("total_cost")), 2)
    if total_cost <= 0 and breakdown:
        total_cost = round(sum(item["cost"] for item in breakdown), 2)
    if total_cost <= 0 and providers:
        total_cost = round(sum(item["total"] for item in providers.values()), 2)
    if total_cost <= 0 and time_series:
        total_cost = round(sum(point["cost"] for point in time_series), 2)

    if total_cost > 0 and breakdown and all(item["percentage"] == 0 for item in breakdown):
        for item in breakdown:
            item["percentage"] = round(item["cost"] / total_cost * 100, 2)

    recommendations = parsed.get("recommendations")
    if isinstance(recommendations, str):
        recommendations = [recommendations]
    recommendations = [str(rec).strip() for rec in (recommendations or []) if str(rec).strip()]

    chart_type = str(parsed.get("chart_type") or "").lower()
    if chart_type not in CHART_TYPES:
        chart_type = "line" if time_series and not breakdown else "bar"

    query_type = str(parsed.get("query_type") or "").lower()
    if query_type not in QUERY_TYPES:
        query_type = detect_query_type(query or summary)

    top_costs = parsed.get("top_costs")
    top_costs = [
        {
            "label": str(item.get("label") or item.get("service") or ""),
            "value": round(_to_float(item.get("value", item.get("cost"))), 2),
            "unit": str(item.get("unit") or parsed.get("currency") or "USD"),
        }
        for item in (top_costs if isinstance(top_costs, list) else [])
        if isinstance(item, dict) and (item.get("label") or item.get("service"))
    ]

    analysis: dict[str, Any] = {
        "summary": summary,
        "total_cost": total_cost,
        "currency": str(parsed.get("currency") or "USD"),
        "period": str(parsed.get("period") or ""),
        "providers": providers,
        "service_breakdown": breakdown,
        "time_series": time_series,
        "top_costs": top_costs,
        "recommendations": recommendations,
        "raw_response": raw_text,
        "chart_type": chart_type,
        "query_type": query_type,
    }
    analysis["a2ui_messages"] = build_cost_analysis_a2ui_messages(analysis)
    return analysis


# ----- result helpers -------------------------------------------------------------------------


def result_text(result: AgentResult | Any) -> str:
    """Concatenated text blocks of an agent result."""
    message = getattr(result, "message", None)
    if isinstance(message, dict):
        parts = [block.get("text", "") for block in message.get("content", []) if isinstance(block, dict)]
        text = "".join(parts).strip()
        if text:
            return text
    return str(result)


def tool_calls_from_metrics(metrics: Any) -> list[dict[str, Any]]:
    """Summarise tool usage recorded by Strands during a run."""
    calls: list[dict[str, Any]] = []
    for name, metric in (getattr(metrics, "tool_metrics", None) or {}).items():
        calls.append(
            {
                "tool": name,
                "calls": int(getattr(metric, "call_count", 0) or 0),
                "successes": int(getattr(metric, "success_count", 0) or 0),
                "errors": int(getattr(metric, "error_count", 0) or 0),
                "seconds": round(float(getattr(metric, "total_time", 0.0) or 0.0), 3),
            }
        )
    return calls


def usage_from_metrics(metrics: Any) -> dict[str, int]:
    """Token usage accumulated over a run."""
    usage = dict(getattr(metrics, "accumulated_usage", None) or {})
    return {
        "input_tokens": int(usage.get("inputTokens", 0) or 0),
        "output_tokens": int(usage.get("outputTokens", 0) or 0),
        "total_tokens": int(usage.get("totalTokens", 0) or 0),
        "cycles": int(getattr(metrics, "cycle_count", 0) or 0),
    }


def estimate_tokens(text: str) -> int:
    """Rough token estimate when the provider reports no usage."""
    return max(1, int(len(text.split()) * 1.3))


# ----- agent construction ------------------------------------------------------------------------


def build_agent(
    *,
    system_prompt: str,
    providers: list[str] | None = None,
    model: Model | None = None,
    llm_provider: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    callback_handler: Callable[..., Any] | None = None,
    window_size: int = 40,
    tools: list | None = None,
) -> Agent:
    """Create a Strands agent with the tools for ``providers``.

    ``callback_handler`` defaults to silent; pass a callable to stream tokens / tool events.
    """
    return Agent(
        model=model or build_model(llm_provider),
        tools=tools if tools is not None else get_tools(providers),
        system_prompt=system_prompt,
        messages=list(messages or []),
        callback_handler=callback_handler,
        conversation_manager=SlidingWindowConversationManager(window_size=max(4, window_size)),
    )


def analyze_costs(
    query: str,
    providers: list[str] | None = None,
    connection_context: dict[str, dict[str, Any]] | None = None,
    llm_provider: str | None = None,
) -> dict[str, Any]:
    """One-shot analysis without session memory (fresh agent per call).

    Returns ``{"success": True, "data": analysis}`` or ``{"success": False, "error": ...}``.
    """
    providers = [p.lower() for p in (providers or [])] or None
    active = providers or [
        name for name, status in settings.provider_status().items() if status.get("configured")
    ] or ["aws"]
    system_prompt = build_base_system_prompt(active, connection_context)
    try:
        agent = build_agent(system_prompt=system_prompt, providers=active, llm_provider=llm_provider)
        result = agent(query)
        raw = result_text(result)
        analysis = normalize_analysis(extract_json(raw), raw, query)
        return {
            "success": True,
            "data": analysis,
            "tool_calls": tool_calls_from_metrics(result.metrics),
            "usage": usage_from_metrics(result.metrics),
        }
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception("Agent analysis failed")
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}
