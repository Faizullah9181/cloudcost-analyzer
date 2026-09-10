"""Strands tools for DigitalOcean billing and resource cost estimates."""

from __future__ import annotations

import logging
from typing import Any

import requests
from strands import tool

from backend.agents.tools._common import clamp, error_result, round_money
from backend.config import settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.digitalocean.com/v2"
_TIMEOUT = 15

# Public list prices used for estimates where the API does not expose costs.
_VOLUME_PRICE_PER_GB = 0.10
_LOAD_BALANCER_PRICE = 12.0
_DATABASE_NODE_PRICE = 15.0


class DigitalOceanError(RuntimeError):
    """Raised when the DigitalOcean API returns an error."""


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    token = settings.digitalocean_api_token
    if not token:
        raise DigitalOceanError("DigitalOcean API token not configured (set DIGITALOCEAN_API_TOKEN)")
    response = requests.get(
        f"{API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        params=params,
        timeout=_TIMEOUT,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.text)
        except ValueError:
            detail = response.text
        raise DigitalOceanError(f"DigitalOcean API {path} returned {response.status_code}: {detail}")
    return response.json()


def _invoice_rows(invoices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "period": invoice.get("invoice_period"),
            "amount": round_money(invoice.get("amount")),
            "uuid": invoice.get("invoice_uuid"),
            "updated_at": invoice.get("updated_at"),
        }
        for invoice in invoices
    ]


@tool
def digitalocean_billing_summary() -> dict:
    """Get the DigitalOcean account balance, month-to-date usage and recent invoices.

    Returns:
        Month-to-date usage and balance, the current invoice preview and the last 6 invoices.
    """
    try:
        balance = _get("/customers/my/balance")
        invoices = _get("/customers/my/invoices", params={"per_page": 6})
    except (DigitalOceanError, requests.RequestException) as exc:
        logger.warning("DigitalOcean billing failed: %s", exc)
        return error_result("digitalocean", str(exc))

    preview = invoices.get("invoice_preview") or {}
    return {
        "provider": "digitalocean",
        "currency": "USD",
        "month_to_date_usage": round_money(balance.get("month_to_date_usage")),
        "month_to_date_balance": round_money(balance.get("month_to_date_balance")),
        "account_balance": round_money(balance.get("account_balance")),
        "generated_at": balance.get("generated_at"),
        "current_invoice_preview": {
            "period": preview.get("invoice_period"),
            "amount": round_money(preview.get("amount")),
        },
        "recent_invoices": _invoice_rows(invoices.get("invoices", [])),
    }


@tool
def digitalocean_resource_costs() -> dict:
    """Estimate the monthly cost of DigitalOcean resources (droplets, volumes, load balancers, databases).

    Droplet prices come from the API; other resources use public list prices.

    Returns:
        Per-resource-type counts and estimated monthly cost, plus the estimated total.
    """
    resources: dict[str, dict[str, Any]] = {
        "droplets": {"count": 0, "monthly_cost": 0.0, "items": []},
        "volumes": {"count": 0, "monthly_cost": 0.0},
        "load_balancers": {"count": 0, "monthly_cost": 0.0},
        "databases": {"count": 0, "monthly_cost": 0.0},
    }
    errors: dict[str, str] = {}

    try:
        droplets = _get("/droplets", params={"per_page": 200}).get("droplets", [])
        resources["droplets"]["count"] = len(droplets)
        resources["droplets"]["monthly_cost"] = round(
            sum(float((d.get("size") or {}).get("price_monthly") or 0) for d in droplets), 2
        )
        resources["droplets"]["items"] = [
            {
                "name": d.get("name"),
                "size": d.get("size_slug"),
                "region": (d.get("region") or {}).get("slug"),
                "status": d.get("status"),
                "price_monthly": round_money((d.get("size") or {}).get("price_monthly")),
            }
            for d in droplets[:25]
        ]
    except (DigitalOceanError, requests.RequestException) as exc:
        errors["droplets"] = str(exc)

    try:
        volumes = _get("/volumes", params={"per_page": 200}).get("volumes", [])
        resources["volumes"]["count"] = len(volumes)
        resources["volumes"]["monthly_cost"] = round(
            sum(float(v.get("size_gigabytes") or 0) * _VOLUME_PRICE_PER_GB for v in volumes), 2
        )
    except (DigitalOceanError, requests.RequestException) as exc:
        errors["volumes"] = str(exc)

    try:
        lbs = _get("/load_balancers", params={"per_page": 200}).get("load_balancers", [])
        resources["load_balancers"]["count"] = len(lbs)
        resources["load_balancers"]["monthly_cost"] = round(
            sum(int(lb.get("size_unit") or 1) * _LOAD_BALANCER_PRICE for lb in lbs), 2
        )
    except (DigitalOceanError, requests.RequestException) as exc:
        errors["load_balancers"] = str(exc)

    try:
        dbs = _get("/databases", params={"per_page": 200}).get("databases", [])
        resources["databases"]["count"] = len(dbs)
        resources["databases"]["monthly_cost"] = round(
            sum(int(db.get("num_nodes") or 1) * _DATABASE_NODE_PRICE for db in dbs), 2
        )
    except (DigitalOceanError, requests.RequestException) as exc:
        errors["databases"] = str(exc)

    if len(errors) == 4:
        return error_result("digitalocean", next(iter(errors.values())))

    result: dict[str, Any] = {
        "provider": "digitalocean",
        "currency": "USD",
        "estimate": True,
        "resources": resources,
        "total_monthly_cost": round(sum(item["monthly_cost"] for item in resources.values()), 2),
    }
    if errors:
        result["errors"] = errors
    return result


@tool
def digitalocean_monthly_trend(months: int = 6) -> dict:
    """Get DigitalOcean invoiced spend per month.

    Args:
        months: Number of months to return (1-24). Defaults to 6.

    Returns:
        Monthly invoice totals, most recent first, and the current period preview.
    """
    months = clamp(months, 1, 24)
    try:
        payload = _get("/customers/my/invoices", params={"per_page": 100})
    except (DigitalOceanError, requests.RequestException) as exc:
        logger.warning("DigitalOcean invoices failed: %s", exc)
        return error_result("digitalocean", str(exc))

    totals: dict[str, float] = {}
    for invoice in payload.get("invoices", []):
        period = str(invoice.get("invoice_period") or "")[:7]
        if period:
            totals[period] = round(totals.get(period, 0.0) + round_money(invoice.get("amount")), 2)

    monthly = [{"month": month, "cost": totals[month]} for month in sorted(totals, reverse=True)[:months]]
    preview = payload.get("invoice_preview") or {}
    return {
        "provider": "digitalocean",
        "currency": "USD",
        "monthly_costs": monthly,
        "current_period": {"month": preview.get("invoice_period"), "cost": round_money(preview.get("amount"))},
        "total": round(sum(item["cost"] for item in monthly), 2),
    }


digitalocean_tools = [digitalocean_billing_summary, digitalocean_resource_costs, digitalocean_monthly_trend]
