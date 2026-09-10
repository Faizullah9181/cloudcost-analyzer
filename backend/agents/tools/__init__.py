"""Cloud provider tool registry for the Shimo agent."""

from __future__ import annotations

from backend.agents.tools.aws_cost_tools import aws_tools
from backend.agents.tools.azure_cost_tools import azure_tools
from backend.agents.tools.digitalocean_tools import digitalocean_tools
from backend.agents.tools.gcp_billing_tools import gcp_tools

TOOLS_BY_PROVIDER: dict[str, list] = {
    "aws": list(aws_tools),
    "azure": list(azure_tools),
    "gcp": list(gcp_tools),
    "digitalocean": list(digitalocean_tools),
}


def get_tools(providers: list[str] | None = None) -> list:
    """Return the tools for the given providers (all providers when ``None`` or empty)."""
    if not providers:
        providers = list(TOOLS_BY_PROVIDER)
    tools: list = []
    for provider in providers:
        tools.extend(TOOLS_BY_PROVIDER.get(provider.lower(), []))
    return tools


def tool_names(providers: list[str] | None = None) -> list[str]:
    """Names of the tools that would be registered for ``providers``."""
    return [tool.tool_name for tool in get_tools(providers)]


__all__ = ["TOOLS_BY_PROVIDER", "get_tools", "tool_names"]
