"""A2UI message generator for cloud cost analysis results."""

from __future__ import annotations

from typing import Any


def _safe_text(value: Any, fallback: str = "") -> str:
    """Return safe string output for UI text literals."""
    if value is None:
        return fallback
    return str(value)


def _text_component(
    component_id: str, text: str, usage_hint: str = "body"
) -> dict[str, Any]:
    """Build a basic A2UI Text component."""
    return {
        "id": component_id,
        "component": {
            "Text": {
                "usageHint": usage_hint,
                "text": {"literalString": text},
            }
        },
    }


def build_cost_analysis_a2ui_messages(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build A2UI messages for a cost analysis response.

    The output follows the A2UI message pattern with beginRendering + surfaceUpdate.
    """
    surface_id = "cost-analysis"
    summary = _safe_text(data.get("summary"), "Cost analysis completed.")
    total_cost = float(data.get("total_cost", 0) or 0)
    currency = _safe_text(data.get("currency"), "USD")
    period = _safe_text(data.get("period"), "Current period")

    service_breakdown = data.get("service_breakdown", []) or []
    recommendations = data.get("recommendations", []) or []

    service_items = [
        f"{item.get('service', 'Unknown Service')}: {currency} {float(item.get('cost', 0) or 0):.2f}"
        for item in service_breakdown[:8]
    ]

    rec_items = [f"- {_safe_text(rec)}" for rec in recommendations[:5]]

    components: list[dict[str, Any]] = [
        {
            "id": "root-card",
            "component": {"Card": {"child": "root-column"}},
        },
        {
            "id": "root-column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": [
                            "title",
                            "summary",
                            "total",
                            "period",
                            "services-title",
                            "services-column",
                            "recs-title",
                            "recs-column",
                        ]
                    }
                }
            },
        },
        _text_component("title", "AWS Cost Analysis", "h2"),
        _text_component("summary", summary, "body"),
        _text_component("total", f"Total Cost: {currency} {total_cost:.2f}", "h4"),
        _text_component("period", f"Period: {period}", "caption"),
        _text_component("services-title", "Top Services", "h4"),
        {
            "id": "services-column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": [
                            f"service-{index}"
                            for index in range(
                                len(service_items) if service_items else 1
                            )
                        ]
                    }
                }
            },
        },
        _text_component("recs-title", "Recommendations", "h4"),
        {
            "id": "recs-column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": [
                            f"rec-{index}"
                            for index in range(len(rec_items) if rec_items else 1)
                        ]
                    }
                }
            },
        },
    ]

    if service_items:
        for index, service_line in enumerate(service_items):
            components.append(_text_component(f"service-{index}", service_line, "body"))
    else:
        components.append(
            _text_component(
                "service-0", "No service-level cost data available.", "caption"
            )
        )

    if rec_items:
        for index, rec_line in enumerate(rec_items):
            components.append(_text_component(f"rec-{index}", rec_line, "body"))
    else:
        components.append(
            _text_component(
                "rec-0", "No optimization recommendations available.", "caption"
            )
        )

    return [
        {
            "beginRendering": {
                "surfaceId": surface_id,
                "root": "root-card",
                "styles": {
                    "primaryColor": "#1D4ED8",
                    "font": "Roboto",
                },
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": surface_id,
                "components": components,
            }
        },
    ]
