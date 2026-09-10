"""Strands tools for GCP billing (BigQuery billing export, Cloud Billing API, Cloud Asset inventory)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from strands import tool

from backend.agents.tools._common import error_result, parse_date_range
from backend.config import settings

logger = logging.getLogger(__name__)

_IDENT_RE = re.compile(r"^[A-Za-z0-9_.\-*]+$")
_DEFAULT_TABLE = "gcp_billing_export_v1_*"


def _credentials():
    """Service-account credentials from settings, otherwise Application Default Credentials."""
    from google.oauth2 import service_account  # pylint: disable=import-outside-toplevel

    raw = (settings.gcp_service_account_json or "").strip()
    if raw.startswith("{"):
        return service_account.Credentials.from_service_account_info(json.loads(raw))
    if raw:
        return service_account.Credentials.from_service_account_file(raw)

    import google.auth  # pylint: disable=import-outside-toplevel

    credentials, _ = google.auth.default()
    return credentials


def _project(project_id: str | None) -> str | None:
    return (project_id or "").strip() or settings.gcp_project_id or None


def _billing_table() -> str:
    billing_project = settings.gcp_billing_project_id or settings.gcp_project_id
    dataset = settings.gcp_billing_dataset or "billing_export"
    table = settings.gcp_billing_table or _DEFAULT_TABLE
    for part in (billing_project, dataset, table):
        if not part or not _IDENT_RE.match(part):
            raise ValueError(f"Invalid BigQuery identifier in billing export config: {part!r}")
    return f"`{billing_project}.{dataset}.{table}`"


def _run_billing_query(
    select_sql: str, project_id: str, start: str, end: str, tail_sql: str = ""
) -> list[dict[str, Any]]:
    from google.cloud import bigquery  # pylint: disable=import-outside-toplevel

    table = _billing_table()
    client = bigquery.Client(credentials=_credentials(), project=settings.gcp_billing_project_id or project_id)
    sql = f"""
        {select_sql}
        FROM {table}
        WHERE usage_start_time >= TIMESTAMP(@start_date)
          AND usage_start_time < TIMESTAMP(@end_date)
          AND (@project_id = '' OR project.id = @project_id)
        {tail_sql}
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "STRING", start),
            bigquery.ScalarQueryParameter("end_date", "STRING", end),
            bigquery.ScalarQueryParameter("project_id", "STRING", project_id),
        ]
    )
    return [dict(row) for row in client.query(sql, job_config=job_config).result()]


@tool
def gcp_billing_by_service(
    project_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Get GCP cost broken down by service from the BigQuery billing export.

    Args:
        project_id: GCP project to filter on. Defaults to the configured project.
        start_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        end_date: End date (YYYY-MM-DD). Defaults to today.

    Returns:
        Gross cost, credits and net cost per service, plus the totals.
    """
    project = _project(project_id)
    if not project:
        return error_result("gcp", "No GCP project configured (set GCP_PROJECT_ID)")
    try:
        start, end = parse_date_range(start_date, end_date)
        rows = _run_billing_query(
            """
            SELECT service.description AS service,
                   SUM(cost) AS gross_cost,
                   SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS credits,
                   ANY_VALUE(currency) AS currency
            """,
            project,
            start,
            end,
            tail_sql="GROUP BY service ORDER BY gross_cost DESC",
        )
    except ValueError as exc:
        return error_result("gcp", str(exc))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("GCP billing query failed: %s", exc)
        return error_result("gcp", f"Failed to fetch GCP costs: {exc}")

    services: dict[str, dict[str, float]] = {}
    currency = "USD"
    for row in rows:
        name = str(row.get("service") or "Unknown")
        gross = float(row.get("gross_cost") or 0)
        credit_total = float(row.get("credits") or 0)
        entry = services.setdefault(name, {"gross_cost": 0.0, "credits": 0.0, "net_cost": 0.0})
        entry["gross_cost"] = round(entry["gross_cost"] + gross, 2)
        entry["credits"] = round(entry["credits"] + credit_total, 2)
        entry["net_cost"] = round(entry["gross_cost"] + entry["credits"], 2)
        currency = str(row.get("currency") or currency)

    ordered = dict(sorted(services.items(), key=lambda item: item[1]["net_cost"], reverse=True))
    return {
        "provider": "gcp",
        "project_id": project,
        "period": f"{start} to {end}",
        "currency": currency,
        "total_cost": round(sum(item["net_cost"] for item in ordered.values()), 2),
        "total_gross_cost": round(sum(item["gross_cost"] for item in ordered.values()), 2),
        "services": ordered,
    }


@tool
def gcp_cost_daily_trend(
    project_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """Get the daily GCP cost trend from the BigQuery billing export.

    Args:
        project_id: GCP project to filter on. Defaults to the configured project.
        start_date: Start date (YYYY-MM-DD). Defaults to 30 days ago.
        end_date: End date (YYYY-MM-DD). Defaults to today.

    Returns:
        Daily net cost points and the total.
    """
    project = _project(project_id)
    if not project:
        return error_result("gcp", "No GCP project configured (set GCP_PROJECT_ID)")
    try:
        start, end = parse_date_range(start_date, end_date)
        rows = _run_billing_query(
            """
            SELECT DATE(usage_start_time) AS day,
                   SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net_cost
            """,
            project,
            start,
            end,
            tail_sql="GROUP BY day ORDER BY day",
        )
    except ValueError as exc:
        return error_result("gcp", str(exc))
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("GCP trend query failed: %s", exc)
        return error_result("gcp", f"Failed to fetch GCP daily trend: {exc}")

    daily: dict[str, float] = {}
    for row in rows:
        day = str(row.get("day"))
        daily[day] = round(daily.get(day, 0.0) + float(row.get("net_cost") or 0), 2)
    points = [{"date": day, "cost": cost} for day, cost in sorted(daily.items())]
    return {
        "provider": "gcp",
        "project_id": project,
        "period": f"{start} to {end}",
        "currency": "USD",
        "daily_costs": points,
        "total_cost": round(sum(daily.values()), 2),
    }


@tool
def gcp_project_billing_info(project_id: str | None = None) -> dict:
    """Check which billing account a GCP project is linked to and whether billing is enabled.

    Args:
        project_id: GCP project ID. Defaults to the configured project.

    Returns:
        Billing account name and enabled flag.
    """
    project = _project(project_id)
    if not project:
        return error_result("gcp", "No GCP project configured (set GCP_PROJECT_ID)")
    try:
        from google.cloud import billing_v1  # pylint: disable=import-outside-toplevel

        client = billing_v1.CloudBillingClient(credentials=_credentials())
        info = client.get_project_billing_info(name=f"projects/{project}")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("GCP billing info failed: %s", exc)
        return error_result("gcp", f"Failed to fetch GCP billing info: {exc}")

    return {
        "provider": "gcp",
        "project_id": project,
        "billing_account": info.billing_account_name,
        "billing_enabled": bool(info.billing_enabled),
    }


@tool
def gcp_resource_inventory(project_id: str | None = None) -> dict:
    """List GCP resources in a project via the Cloud Asset API, grouped by asset type.

    Args:
        project_id: GCP project ID. Defaults to the configured project.

    Returns:
        Total asset count, counts per asset type and a sample of assets.
    """
    project = _project(project_id)
    if not project:
        return error_result("gcp", "No GCP project configured (set GCP_PROJECT_ID)")
    try:
        from google.cloud import asset_v1  # pylint: disable=import-outside-toplevel

        client = asset_v1.AssetServiceClient(credentials=_credentials())
        request = asset_v1.ListAssetsRequest(
            parent=f"projects/{project}",
            content_type=asset_v1.ContentType.RESOURCE,
            page_size=200,
        )
        by_type: dict[str, int] = {}
        sample: list[dict[str, str]] = []
        for count, asset in enumerate(client.list_assets(request=request)):
            if count >= 2000:
                break
            by_type[asset.asset_type] = by_type.get(asset.asset_type, 0) + 1
            if len(sample) < 50:
                sample.append(
                    {
                        "name": asset.name.rsplit("/", 1)[-1],
                        "type": asset.asset_type,
                        "location": getattr(asset.resource, "location", "") or "",
                    }
                )
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.warning("GCP inventory failed: %s", exc)
        return error_result("gcp", f"Failed to fetch GCP resource inventory: {exc}")

    return {
        "provider": "gcp",
        "project_id": project,
        "resource_count": sum(by_type.values()),
        "by_type": dict(sorted(by_type.items(), key=lambda item: item[1], reverse=True)),
        "resources": sample,
    }


gcp_tools = [gcp_billing_by_service, gcp_cost_daily_trend, gcp_project_billing_info, gcp_resource_inventory]
