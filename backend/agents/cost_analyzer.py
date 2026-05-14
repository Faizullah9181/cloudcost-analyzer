"""Strands Agent for Cloud Cost Analysis (Multi-Cloud Support)."""

from __future__ import annotations

import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any

from strands import Agent

try:
    from backend.a2ui import build_cost_analysis_a2ui_messages
    from backend.agents.tools.aws_cost_tools import cost_tools as aws_tools
    from backend.agents.tools.azure_cost_tools import (
        azure_cost_by_service,
        azure_cost_daily_trend,
        azure_resource_inventory,
    )
    from backend.agents.tools.gcp_billing_tools import (
        gcp_billing_by_service,
        gcp_cost_daily_trend,
        gcp_resource_inventory,
    )
    from backend.agents.tools.digitalocean_tools import (
        digitalocean_billing_summary,
        digitalocean_resource_costs,
        digitalocean_monthly_trend,
    )
    from backend.config import settings
except ImportError:
    from a2ui import build_cost_analysis_a2ui_messages
    from agents.tools.aws_cost_tools import cost_tools as aws_tools
    from agents.tools.azure_cost_tools import (
        azure_cost_by_service,
        azure_cost_daily_trend,
        azure_resource_inventory,
    )
    from agents.tools.gcp_billing_tools import (
        gcp_billing_by_service,
        gcp_cost_daily_trend,
        gcp_resource_inventory,
    )
    from agents.tools.digitalocean_tools import (
        digitalocean_billing_summary,
        digitalocean_resource_costs,
        digitalocean_monthly_trend,
    )
    from config import settings

logger = logging.getLogger(__name__)

_unsloth_token: str | None = None
_unsloth_active_model: str | None = None

# Combine all cloud provider tools
_all_tools = [
    *aws_tools,  # AWS tools
    azure_cost_by_service,
    azure_cost_daily_trend,
    azure_resource_inventory,
    gcp_billing_by_service,
    gcp_cost_daily_trend,
    gcp_resource_inventory,
    digitalocean_billing_summary,
    digitalocean_resource_costs,
    digitalocean_monthly_trend,
]

SYSTEM_PROMPT = """You are Shimo Agent — an expert multi-cloud cost analyst.

Your job is to help users understand their cloud spending across AWS, Azure, GCP, and DigitalOcean
by answering natural language questions about costs, resources, and optimization opportunities.

CAPABILITIES:
- Retrieve cost breakdowns by service, region, account, or tag (per cloud)
- Compare costs across multiple cloud providers
- Show cost trends over time
- List active resources across all configured clouds
- Provide cloud-specific and multi-cloud optimization recommendations

RESPONSE FORMAT — you MUST return valid JSON with this structure:
{
  "summary": "Human-readable analysis summary in 2-4 sentences",
  "total_cost": 123.45,
  "currency": "USD",
  "period": "2025-01-01 to 2025-03-31",
  "providers": {
    "aws": {"total": 100, "services": {}},
    "azure": {"total": 50, "services": {}},
    "gcp": {"total": 30, "services": {}},
    "digitalocean": {"total": 20, "services": {}}
  },
  "service_breakdown": [
    {"service": "Compute", "cost": 80.00, "percentage": 65.0, "change": 5.2}
  ],
  "time_series": [
    {"date": "2025-01", "cost": 40.00, "service": "Total"}
  ],
  "recommendations": [
    "Consider Reserved Instances for stable EC2 workloads to save ~30%"
  ],
  "chart_type": "bar"
}

RULES:
- Always call the appropriate tool(s) first to get real data
- Support AWS, Azure, GCP, and DigitalOcean queries
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
            model=settings.openai_model,
            client_args={"api_key": settings.openai_api_key},
        )
        model_kwargs["model"] = model

    elif settings.llm_provider == "gemini":
        from strands.models.openai import OpenAIModel

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")

        # Gemini exposes an OpenAI-compatible endpoint.
        model = OpenAIModel(
            model=settings.gemini_model,
            client_args={
                "api_key": settings.gemini_api_key,
                "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            },
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

    elif settings.llm_provider == "unsloth":
        from strands.models.openai import OpenAIModel

        try:
            unsloth_token = _unsloth_login()
            model_name = settings.unsloth_model or _unsloth_get_active_model(
                unsloth_token
            )
            model = OpenAIModel(
                model=model_name,
                client_args={
                    "api_key": unsloth_token,
                    "base_url": f"{settings.unsloth_base_url.rstrip('/')}/v1",
                },
            )
        except RuntimeError as exc:
            if not settings.gemini_api_key:
                raise RuntimeError(
                    "Unsloth is unavailable and GEMINI_API_KEY is not configured for fallback"
                ) from exc
            logger.warning(
                "Unsloth unavailable, falling back to Gemini model '%s'",
                settings.gemini_model,
            )
            model = OpenAIModel(
                model=settings.gemini_model,
                client_args={
                    "api_key": settings.gemini_api_key,
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
                },
            )
        model_kwargs["model"] = model

    agent = Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=_all_tools,
        **model_kwargs,
    )
    return agent


def _unsloth_login() -> str:
    """Authenticate with Unsloth Studio and return bearer token."""
    global _unsloth_token  # noqa: PLW0603
    if _unsloth_token:
        return _unsloth_token

    login_url = f"{settings.unsloth_base_url.rstrip('/')}/api/auth/login"
    payload = json.dumps(
        {
            "username": settings.unsloth_username,
            "password": settings.unsloth_password,
        }
    ).encode("utf-8")

    request = Request(
        login_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            token = str(parsed.get("access_token", "")).strip()
            if not token:
                raise RuntimeError("Unsloth login response missing access_token")
            _unsloth_token = token
            return token
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        raise RuntimeError("Unable to authenticate to Unsloth Studio") from exc


def _unsloth_get_active_model(token: str) -> str:
    """Get active model from Unsloth status endpoint."""
    global _unsloth_active_model  # noqa: PLW0603
    if _unsloth_active_model:
        return _unsloth_active_model

    status_url = f"{settings.unsloth_base_url.rstrip('/')}/v1/status"
    request = Request(
        status_url,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )

    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            model = str(parsed.get("active_model", "")).strip()
            if model:
                _unsloth_active_model = model
                return model
    except (HTTPError, URLError, TimeoutError, ValueError):
        logger.warning(
            "Unable to auto-detect Unsloth active model; using fallback model name"
        )

    return "default"


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
            analysis_data["a2ui_messages"] = build_cost_analysis_a2ui_messages(
                analysis_data
            )
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
        fallback_data["a2ui_messages"] = build_cost_analysis_a2ui_messages(
            fallback_data
        )
        return {
            "success": True,
            "data": fallback_data,
        }

    except Exception as exc:
        logger.exception("Agent analysis failed")
        return {"success": False, "error": str(exc)}
