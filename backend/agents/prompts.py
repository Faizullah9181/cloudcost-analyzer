"""System prompt and connection-context blocks for the Shimo agent."""

from __future__ import annotations

from typing import Any

from backend.config import Settings, settings as default_settings

SYSTEM_PROMPT = """You are Shimo Agent, an expert multi-cloud cost analyst covering AWS, Azure, GCP and DigitalOcean.

HOW TO WORK
- Always call the relevant tool(s) first and base every number on tool output. Never invent costs.
- Only use tools for providers connected to this session (listed under "Connected Cloud Accounts").
  If the user asks about a provider that is not connected, say so instead of guessing.
- Time ranges: "this month" means the current calendar month; trends default to the last 30 days;
  otherwise use the tool defaults. State the period you analysed.
- If a tool returns an error, report it plainly in the summary and continue with the data you do have.
- Round money to 2 decimals and keep the currency the tools return.
- For multi-cloud questions call the tools for each connected provider, then combine.

RESPONSE FORMAT
Return ONLY a JSON object - no markdown fences, no text before or after it:
{
  "summary": "2-4 plain-language sentences answering the question with the key numbers",
  "query_type": "costs | trend | forecast | comparison | inventory | optimization | analysis",
  "total_cost": 123.45,
  "currency": "USD",
  "period": "2025-01-01 to 2025-01-31",
  "providers": {"aws": {"total": 100.0, "services": {"Amazon EC2": 60.0}}},
  "service_breakdown": [{"service": "Amazon EC2", "cost": 60.0, "percentage": 60.0, "change": 0.0}],
  "time_series": [{"date": "2025-01-01", "cost": 3.2, "service": "Total"}],
  "recommendations": ["Concrete, data-grounded action"],
  "chart_type": "bar"
}
Rules for the fields:
- service_breakdown: top cost items across the connected providers (max 15). percentage is the share
  of total_cost. change is the % change versus the previous period when known, otherwise 0.
- time_series: include only when the data has a time dimension (daily or monthly points).
- chart_type: "bar" for service comparisons, "pie" for shares, "line" or "area" for trends.
- recommendations: 2-5 actionable items tied to the numbers you found.
- When no cost data is available, still return the JSON with total_cost 0 and an explanatory summary.
"""


def build_connection_block(
    providers: list[str],
    connection_context: dict[str, dict[str, Any]] | None = None,
    config: Settings | None = None,
) -> str:
    """Describe the connected accounts so the model passes the right identifiers to tools."""
    config = config or default_settings
    connection_context = connection_context or {}
    lines = ["### Connected Cloud Accounts:"]
    if not providers:
        lines.append("- No cloud providers are connected to this session.")

    for provider in providers:
        ctx = connection_context.get(provider, {}) or {}
        if provider == "aws":
            account = ctx.get("account_id") or config.aws_account_id or "default credentials"
            region = ctx.get("region") or config.aws_region
            lines.append(f"- AWS: account {account}, default region {region}")
        elif provider == "azure":
            subscription = ctx.get("subscription_id") or config.azure_subscription_id
            lines.append(
                f"- Azure: subscription {subscription}"
                if subscription
                else "- Azure: no subscription configured - ask the user for a subscription ID before calling tools"
            )
        elif provider == "gcp":
            project = ctx.get("project_id") or config.gcp_project_id
            lines.append(
                f"- GCP: project {project} (billing export in BigQuery dataset {config.gcp_billing_dataset})"
                if project
                else "- GCP: no project configured - ask the user for a project ID before calling tools"
            )
        elif provider == "digitalocean":
            lines.append(
                "- DigitalOcean: API token configured"
                if config.digitalocean_api_token
                else "- DigitalOcean: API token NOT configured - billing tools will return an error"
            )
        else:
            lines.append(f"- {provider}: unsupported provider")

        notes = ctx.get("notes") or ctx.get("auth_method")
        if notes:
            lines.append(f"  Notes: {notes}")

    return "\n".join(lines)


def build_base_system_prompt(
    providers: list[str],
    connection_context: dict[str, dict[str, Any]] | None = None,
    config: Settings | None = None,
) -> str:
    """System prompt plus the connected-account block."""
    return f"{SYSTEM_PROMPT}\n{build_connection_block(providers, connection_context, config)}"


SUMMARIZER_PROMPT = (
    "You summarise cloud cost analysis conversations. Produce a compact plain-text summary "
    "(max 200 words) that preserves: the questions asked, the key figures found (totals, top services, "
    "periods), and any recommendations given. No markdown, no JSON."
)
