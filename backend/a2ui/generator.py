"""A2UI message generator for cloud cost analysis results."""

from __future__ import annotations

from typing import Any

SURFACE_ID = "cost-analysis"


def _safe_text(value: Any, fallback: str = "") -> str:
    """Return safe string output for UI text literals."""
    if value is None or value == "":
        return fallback
    return str(value)


def _text_component(component_id: str, text: str, usage_hint: str = "body") -> dict[str, Any]:
    """Build a basic A2UI Text component."""
    return {
        "id": component_id,
        "component": {"Text": {"usageHint": usage_hint, "text": {"literalString": text}}},
    }


def _column(component_id: str, children: list[str]) -> dict[str, Any]:
    return {"id": component_id, "component": {"Column": {"children": {"explicitList": children}}}}


def build_cost_analysis_a2ui_messages(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build A2UI messages (beginRendering + surfaceUpdate) for a cost analysis response."""
    summary = _safe_text(data.get("summary"), "Cost analysis completed.")
    total_cost = float(data.get("total_cost", 0) or 0)
    currency = _safe_text(data.get("currency"), "USD")
    period = _safe_text(data.get("period"), "Current period")

    providers = data.get("providers") or {}
    service_breakdown = data.get("service_breakdown") or []
    recommendations = data.get("recommendations") or []

    provider_names = [name.upper() for name in providers] if isinstance(providers, dict) else []
    title = " + ".join(provider_names) + " Cost Analysis" if provider_names else "Cloud Cost Analysis"

    service_lines = [
        f"{item.get('service', 'Unknown Service')}: {currency} {float(item.get('cost', 0) or 0):,.2f}"
        for item in service_breakdown[:8]
    ]
    rec_lines = [f"- {_safe_text(rec)}" for rec in recommendations[:5]]

    components: list[dict[str, Any]] = [
        {"id": "root-card", "component": {"Card": {"child": "root-column"}}},
        _column(
            "root-column",
            [
                "title",
                "summary",
                "total",
                "period",
                "services-title",
                "services-column",
                "recs-title",
                "recs-column",
            ],
        ),
        _text_component("title", title, "h2"),
        _text_component("summary", summary, "body"),
        _text_component("total", f"Total Cost: {currency} {total_cost:,.2f}", "h4"),
        _text_component("period", f"Period: {period}", "caption"),
        _text_component("services-title", "Top Services", "h4"),
        _column("services-column", [f"service-{index}" for index in range(max(len(service_lines), 1))]),
        _text_component("recs-title", "Recommendations", "h4"),
        _column("recs-column", [f"rec-{index}" for index in range(max(len(rec_lines), 1))]),
    ]

    if service_lines:
        components.extend(
            _text_component(f"service-{index}", line, "body") for index, line in enumerate(service_lines)
        )
    else:
        components.append(_text_component("service-0", "No service-level cost data available.", "caption"))

    if rec_lines:
        components.extend(_text_component(f"rec-{index}", line, "body") for index, line in enumerate(rec_lines))
    else:
        components.append(_text_component("rec-0", "No optimization recommendations available.", "caption"))

    return [
        {
            "beginRendering": {
                "surfaceId": SURFACE_ID,
                "root": "root-card",
                "styles": {"primaryColor": "#1D4ED8", "font": "Roboto"},
            }
        },
        {"surfaceUpdate": {"surfaceId": SURFACE_ID, "components": components}},
    ]
