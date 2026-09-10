"""Strands tools for Azure Cost Management and resource inventory."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from strands import tool

from backend.agents.tools._common import error_result, parse_date_range
from backend.config import settings

logger = logging.getLogger(__name__)


def _credential():
    """Service-principal credential when configured, otherwise Azure CLI / managed identity."""
    from azure.identity import ClientSecretCredential, DefaultAzureCredential  # pylint: disable=import-outside-toplevel

    if settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret:
        return ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def _subscription(subscription_id: str | None) -> str | None:
    return (subscription_id or "").strip() or settings.azure_subscription_id or None


def _rows_as_dicts(result: Any) -> list[dict[str, Any]]:
    """Zip Cost Management result rows with their column names."""
    columns = [column.name for column in (getattr(result, "columns", None) or [])]
    return [dict(zip(columns, row)) for row in (getattr(result, "rows", None) or [])]


def _usage_date(value: Any) -> str:
    """Cost Management returns UsageDate as an int like 20250131."""
    text = str(value or "")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def _query(subscription_id: str, start: str, end: str, granularity: str | None, group_by: str | None):
    from azure.mgmt.costmanagement import CostManagementClient  # pylint: disable=import-outside-toplevel
    from azure.mgmt.costmanagement.models import (  # pylint: disable=import-outside-toplevel
        QueryAggregation,
        QueryDataset,
        QueryDefinition,
        QueryGrouping,
        QueryTimePeriod,
    )

    dataset_kwargs: dict[str, Any] = {
        "aggregation": {"totalCost": QueryAggregation(name="Cost", function="Sum")},
    }
    if granularity:
        dataset_kwargs["granularity"] = granularity
    if group_by:
        dataset_kwargs["grouping"] = [QueryGrouping(type="Dimension", name=group_by)]

    definition = QueryDefinition(
        type="ActualCost",
        timeframe="Custom",
        time_period=QueryTimePeriod(
            from_property=datetime.fromisoformat(start).replace(tzinfo=timezone.utc),
            to=datetime.fromisoformat(end).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc),
        ),
        dataset=QueryDataset(**dataset_kwargs),
    )
    client = CostManagementClient(_credential())
    return client.query.usage(scope=f"/subscriptions/{subscription_id}", parameters=definition)


@tool
def azure_cost_by_service(
    subscription_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Get Azure actual cost broken down by service for a period.

    Args:
        subscription_id: Azure subscription ID. Defaults to the configured subscription.
        start_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        end_date: End date (YYYY-MM-DD). Defaults to today.

    Returns:
        Cost per service, the total and the currency.
    """
    sub = _subscription(subscription_id)
    if not sub:
        return error_result("azure", "No Azure subscription configured (set AZURE_SUBSCRIPTION_ID)")
    try:
        start, end = parse_date_range(start_date, end_date)
        result = _query(sub, start, end, None, "ServiceName")
    except ValueError as exc:
        return error_result("azure", str(exc))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Azure cost query failed: %s", exc)
        return error_result("azure", f"Failed to fetch Azure costs: {exc}")

    services: dict[str, float] = {}
    currency = "USD"
    for row in _rows_as_dicts(result):
        name = str(row.get("ServiceName") or "Unknown")
        services[name] = round(services.get(name, 0.0) + float(row.get("Cost") or 0), 2)
        currency = str(row.get("Currency") or currency)

    return {
        "provider": "azure",
        "subscription_id": sub,
        "period": f"{start} to {end}",
        "currency": currency,
        "total_cost": round(sum(services.values()), 2),
        "services": dict(sorted(services.items(), key=lambda item: item[1], reverse=True)),
    }


@tool
def azure_cost_daily_trend(
    subscription_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Get the daily Azure cost trend for a subscription.

    Args:
        subscription_id: Azure subscription ID. Defaults to the configured subscription.
        start_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        end_date: End date (YYYY-MM-DD). Defaults to today.

    Returns:
        Daily cost points, the total and the currency.
    """
    sub = _subscription(subscription_id)
    if not sub:
        return error_result("azure", "No Azure subscription configured (set AZURE_SUBSCRIPTION_ID)")
    try:
        start, end = parse_date_range(start_date, end_date)
        result = _query(sub, start, end, "Daily", None)
    except ValueError as exc:
        return error_result("azure", str(exc))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Azure trend query failed: %s", exc)
        return error_result("azure", f"Failed to fetch Azure daily trend: {exc}")

    daily: dict[str, float] = {}
    currency = "USD"
    for row in _rows_as_dicts(result):
        day = _usage_date(row.get("UsageDate"))
        daily[day] = round(daily.get(day, 0.0) + float(row.get("Cost") or 0), 2)
        currency = str(row.get("Currency") or currency)

    points = [{"date": day, "cost": cost} for day, cost in sorted(daily.items())]
    return {
        "provider": "azure",
        "subscription_id": sub,
        "period": f"{start} to {end}",
        "currency": currency,
        "daily_costs": points,
        "total_cost": round(sum(daily.values()), 2),
    }


@tool
def azure_resource_inventory(subscription_id: str | None = None) -> dict:
    """List Azure resources in a subscription grouped by resource type.

    Args:
        subscription_id: Azure subscription ID. Defaults to the configured subscription.

    Returns:
        Total resource count, counts per type, and a sample of resources.
    """
    sub = _subscription(subscription_id)
    if not sub:
        return error_result("azure", "No Azure subscription configured (set AZURE_SUBSCRIPTION_ID)")
    try:
        from azure.mgmt.resource.resources import ResourceManagementClient  # pylint: disable=import-outside-toplevel

        client = ResourceManagementClient(_credential(), sub)
        resources = []
        by_type: dict[str, int] = {}
        for resource in client.resources.list():
            by_type[resource.type] = by_type.get(resource.type, 0) + 1
            if len(resources) < 50:
                resources.append(
                    {"name": resource.name, "type": resource.type, "location": resource.location}
                )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("Azure inventory failed: %s", exc)
        return error_result("azure", f"Failed to fetch Azure resource inventory: {exc}")

    return {
        "provider": "azure",
        "subscription_id": sub,
        "resource_count": sum(by_type.values()),
        "by_type": dict(sorted(by_type.items(), key=lambda item: item[1], reverse=True)),
        "resources": resources,
    }


azure_tools = [azure_cost_by_service, azure_cost_daily_trend, azure_resource_inventory]
