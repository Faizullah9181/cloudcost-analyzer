"""Strands Agent for AWS Cloud Cost Analysis."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from strands import Agent

from a2ui import build_cost_analysis_a2ui_messages
from agents.tools.aws_cost_tools import cost_tools
from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Cloud Analytics Agent — an expert AWS cloud cost analyst.

Your job is to help users understand their AWS spending by answering natural language
questions about costs, resources, and optimization opportunities.

CAPABILITIES:
- Retrieve monthly/daily cost breakdowns by service, region, account, or tag
- Show cost trends over time
- Forecast future costs
- List active AWS resources (EC2, S3, RDS, Lambda)
- Provide cost optimization recommendations

RESPONSE FORMAT — you MUST return valid JSON with this structure:
{
  "summary": "Human-readable analysis summary in 2-4 sentences",
  "total_cost": 123.45,
  "currency": "USD",
  "period": "2025-01-01 to 2025-03-31",
  "service_breakdown": [
    {"service": "Amazon EC2", "cost": 80.00, "percentage": 65.0, "change": 5.2}
  ],
  "time_series": [
    {"date": "2025-01", "cost": 40.00, "service": "Total"}
  ],
  "top_costs": [
    {"label": "EC2 On-Demand", "value": 60.00, "unit": "USD"}
  ],
  "recommendations": [
    "Consider Reserved Instances for stable EC2 workloads to save ~30%"
  ],
  "chart_type": "bar"
}

RULES:
- Always call the appropriate tool(s) first to get real data
- If a tool returns an error, report it clearly in the summary
- Use "bar" for service comparisons, "line" for time trends, "pie" for proportional breakdowns, "area" for cumulative trends
- Always include actionable recommendations
- Round all monetary values to 2 decimal places
- When showing percentage changes, compare to the previous period
- Respond ONLY with the JSON object, no markdown formatting or extra text
"""


def _build_agent() -> Agent:
    """Build and return the Strands cost analysis agent."""
    model_kwargs: dict[str, Any] = {}

    if settings.llm_provider == "bedrock":
        from strands.models import BedrockModel

        model = BedrockModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.bedrock_region,
            streaming=True,
        )
        model_kwargs["model"] = model

    elif settings.llm_provider == "openai":
        from strands.models.openai import OpenAIModel

        model = OpenAIModel(
            model="gpt-4o",
            client_args={"api_key": settings.openai_api_key},
        )
        model_kwargs["model"] = model

    elif settings.llm_provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        model = AnthropicModel(
            model_id="claude-sonnet-4-20250514",
            client_args={"api_key": settings.anthropic_api_key},
        )
        model_kwargs["model"] = model

    elif settings.llm_provider == "ollama":
        from strands.models.ollama import OllamaModel

        model = OllamaModel(
            host=settings.ollama_host,
            model_id=settings.ollama_model,
        )
        model_kwargs["model"] = model

    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=cost_tools,
        **model_kwargs,
    )
    return agent


# Module-level agent instance (lazy init)
_agent: Agent | None = None


def get_agent() -> Agent:
    """Get or create the singleton agent instance."""
    global _agent  # noqa: PLW0603
    if _agent is None:
        _agent = _build_agent()
    return _agent


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract JSON object from agent response text."""
    # Try direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Try to find JSON block in markdown
    patterns = [
        r"```json\s*([\s\S]*?)```",
        r"```\s*([\s\S]*?)```",
        r"\{[\s\S]*\}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1) if match.lastindex else match.group(0)
            try:
                return json.loads(candidate.strip())
            except (json.JSONDecodeError, TypeError):
                continue
    return None


def analyze_costs(query: str) -> dict[str, Any]:
    """Run a natural language cost analysis query through the agent.

    Args:
        query: Natural language question about AWS costs.

    Returns:
        Dictionary with analysis results.
    """
    agent = get_agent()

    try:
        result = agent(query)
        raw_text = str(result)

        parsed = _extract_json(raw_text)
        if parsed:
            analysis_data = {
                "summary": parsed.get("summary", ""),
                "total_cost": parsed.get("total_cost", 0),
                "currency": parsed.get("currency", "USD"),
                "period": parsed.get("period", ""),
                "service_breakdown": parsed.get("service_breakdown", []),
                "time_series": parsed.get("time_series", []),
                "top_costs": parsed.get("top_costs", []),
                "recommendations": parsed.get("recommendations", []),
                "raw_response": raw_text,
                "chart_type": parsed.get("chart_type", "bar"),
            }
            analysis_data["a2ui_messages"] = build_cost_analysis_a2ui_messages(analysis_data)
            return {
                "success": True,
                "data": analysis_data,
            }

        # Fallback: return raw text as summary
        fallback_data = {
            "summary": raw_text,
            "total_cost": 0,
            "currency": "USD",
            "period": "",
            "service_breakdown": [],
            "time_series": [],
            "top_costs": [],
            "recommendations": [],
            "raw_response": raw_text,
            "chart_type": "bar",
        }
        fallback_data["a2ui_messages"] = build_cost_analysis_a2ui_messages(fallback_data)
        return {
            "success": True,
            "data": fallback_data,
        }

    except Exception as exc:
        logger.exception("Agent analysis failed")
        return {"success": False, "error": str(exc)}
