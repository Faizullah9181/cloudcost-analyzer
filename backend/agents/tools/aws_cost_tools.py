"""Strands tools for AWS cost analysis (Cost Explorer, Organizations, resource inventory)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from strands import tool

from backend.agents.tools._common import (
    clamp,
    day_range,
    error_result,
    month_range,
    round_money,
    today_utc,
)
from backend.config import settings

logger = logging.getLogger(__name__)

# Cost Explorer and Organizations are global services served from us-east-1.
GLOBAL_REGION = "us-east-1"


def _session() -> boto3.session.Session:
    """Build a boto3 session from explicit settings, falling back to ambient credentials."""
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_profile:
        kwargs["profile_name"] = settings.aws_profile
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.session.Session(**kwargs)


def _client(service: str, region: str | None = None):
    return _session().client(service, region_name=region or settings.aws_region)


def _ce():
    return _client("ce", GLOBAL_REGION)


def _aws_error(exc: Exception, **extra: Any) -> dict[str, Any]:
    logger.warning("AWS call failed: %s", exc)
    return error_result("aws", str(exc), **extra)


def _grouped_costs(response: dict, key_name: str) -> list[dict[str, Any]]:
    """Flatten a grouped Cost Explorer response into ``[{key, cost, date}]`` rows."""
    rows: list[dict[str, Any]] = []
    for period in response.get("ResultsByTime", []):
        period_start = period["TimePeriod"]["Start"]
        for group in period.get("Groups", []):
            cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
            if cost > 0.01:
                rows.append({key_name: group["Keys"][0] or "n/a", "cost": round(cost, 2), "date": period_start})
    return sorted(rows, key=lambda row: row["cost"], reverse=True)


@tool
def aws_monthly_cost_breakdown(months: int = 3) -> dict:
    """Get monthly AWS cost broken down by service for the current month and prior months.

    Args:
        months: Number of months to include (1-12), counting the current month. Defaults to 3.

    Returns:
        Period, per-service cost rows (with the month each row belongs to), and the total.
    """
    start, end = month_range(months)
    try:
        response = _ce().get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )
    except (ClientError, BotoCoreError) as exc:
        return _aws_error(exc)

    rows = _grouped_costs(response, "service")
    by_service: dict[str, float] = {}
    for row in rows:
        by_service[row["service"]] = round(by_service.get(row["service"], 0.0) + row["cost"], 2)
    return {
        "provider": "aws",
        "period": f"{start} to {end}",
        "currency": "USD",
        "total": round(sum(by_service.values()), 2),
        "services": dict(sorted(by_service.items(), key=lambda item: item[1], reverse=True)),
        "monthly_rows": rows,
    }


@tool
def aws_daily_cost_trend(days: int = 30) -> dict:
    """Get the daily AWS cost trend for the last N days.

    Args:
        days: Number of days to look back (1-90). Defaults to 30.

    Returns:
        Daily total cost points, the total for the period and the daily average.
    """
    start, end = day_range(days, max_days=90)
    try:
        response = _ce().get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )
    except (ClientError, BotoCoreError) as exc:
        return _aws_error(exc)

    points = [
        {"date": period["TimePeriod"]["Start"], "cost": round(float(period["Total"]["UnblendedCost"]["Amount"]), 2)}
        for period in response.get("ResultsByTime", [])
    ]
    total = round(sum(point["cost"] for point in points), 2)
    return {
        "provider": "aws",
        "period": f"{start} to {end}",
        "currency": "USD",
        "daily_costs": points,
        "total": total,
        "average_daily": round(total / max(len(points), 1), 2),
    }


@tool
def aws_service_cost_details(service_name: str, months: int = 1) -> dict:
    """Get a usage-type level cost breakdown for one AWS service.

    Args:
        service_name: Exact Cost Explorer service name, e.g. 'Amazon Elastic Compute Cloud - Compute',
            'Amazon Simple Storage Service', 'AWS Lambda', 'Amazon Relational Database Service'.
        months: Number of months to include (1-12). Defaults to 1.

    Returns:
        Cost per usage type for the service and the service total.
    """
    start, end = month_range(months)
    try:
        response = _ce().get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            Filter={"Dimensions": {"Key": "SERVICE", "Values": [service_name]}},
            GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        )
    except (ClientError, BotoCoreError) as exc:
        return _aws_error(exc, service=service_name)

    rows = _grouped_costs(response, "usage_type")
    return {
        "provider": "aws",
        "service": service_name,
        "period": f"{start} to {end}",
        "currency": "USD",
        "usage_types": rows,
        "total": round(sum(row["cost"] for row in rows), 2),
    }


@tool
def aws_cost_by_region(months: int = 1) -> dict:
    """Get AWS cost broken down by region.

    Args:
        months: Number of months to include (1-12). Defaults to 1.

    Returns:
        Cost per region and the total.
    """
    start, end = month_range(months)
    try:
        response = _ce().get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "REGION"}],
        )
    except (ClientError, BotoCoreError) as exc:
        return _aws_error(exc)

    rows = _grouped_costs(response, "region")
    for row in rows:
        if row["region"] in ("", "n/a", "NoRegion"):
            row["region"] = "global"
    return {
        "provider": "aws",
        "period": f"{start} to {end}",
        "currency": "USD",
        "regions": rows,
        "total": round(sum(row["cost"] for row in rows), 2),
    }


@tool
def aws_cost_by_account(months: int = 1) -> dict:
    """Get AWS cost broken down by linked account (AWS Organizations).

    Args:
        months: Number of months to include (1-12). Defaults to 1.

    Returns:
        Cost per account with account names when Organizations access is available.
    """
    start, end = month_range(months)
    try:
        response = _ce().get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        )
    except (ClientError, BotoCoreError) as exc:
        return _aws_error(exc)

    account_names: dict[str, str] = {}
    try:
        paginator = _client("organizations", GLOBAL_REGION).get_paginator("list_accounts")
        for page in paginator.paginate():
            for account in page.get("Accounts", []):
                account_names[account["Id"]] = account["Name"]
    except (ClientError, BotoCoreError) as exc:
        logger.debug("Organizations lookup skipped: %s", exc)

    rows = _grouped_costs(response, "account_id")
    for row in rows:
        row["account_name"] = account_names.get(row["account_id"], row["account_id"])
    return {
        "provider": "aws",
        "period": f"{start} to {end}",
        "currency": "USD",
        "accounts": rows,
        "total": round(sum(row["cost"] for row in rows), 2),
    }


@tool
def aws_cost_forecast(forecast_days: int = 30) -> dict:
    """Get the AWS cost forecast for the next N days.

    Args:
        forecast_days: Days to forecast (1-90). Defaults to 30.

    Returns:
        Daily mean forecast values and the forecast total.
    """
    forecast_days = clamp(forecast_days, 1, 90)
    start = today_utc()
    end = start + timedelta(days=forecast_days)
    try:
        response = _ce().get_cost_forecast(
            TimePeriod={"Start": start.isoformat(), "End": end.isoformat()},
            Granularity="DAILY",
            Metric="UNBLENDED_COST",
        )
    except (ClientError, BotoCoreError) as exc:
        return _aws_error(exc)

    points = [
        {"date": item["TimePeriod"]["Start"], "mean": round(float(item["MeanValue"]), 2)}
        for item in response.get("ForecastResultsByTime", [])
    ]
    return {
        "provider": "aws",
        "period": f"{start.isoformat()} to {end.isoformat()}",
        "currency": "USD",
        "forecast": points,
        "total_forecast": round_money(response.get("Total", {}).get("Amount", 0)),
    }


@tool
def aws_resource_inventory() -> dict:
    """Summarise active AWS resources in the configured region (EC2, RDS, S3, Lambda).

    Returns:
        Counts and a sample of resources per service. Individual services report an
        error field when access is denied instead of failing the whole inventory.
    """
    inventory: dict[str, Any] = {"provider": "aws", "region": settings.aws_region}
    session = _session()

    try:
        ec2 = session.client("ec2")
        instances = [
            {"id": inst["InstanceId"], "type": inst["InstanceType"], "state": inst["State"]["Name"]}
            for reservation in ec2.describe_instances().get("Reservations", [])
            for inst in reservation.get("Instances", [])
        ]
        inventory["ec2"] = {"count": len(instances), "instances": instances[:20]}
    except (ClientError, BotoCoreError) as exc:
        inventory["ec2"] = {"error": str(exc)}

    try:
        buckets = session.client("s3").list_buckets().get("Buckets", [])
        inventory["s3"] = {"count": len(buckets), "buckets": [bucket["Name"] for bucket in buckets][:20]}
    except (ClientError, BotoCoreError) as exc:
        inventory["s3"] = {"error": str(exc)}

    try:
        databases = [
            {
                "id": db["DBInstanceIdentifier"],
                "engine": db["Engine"],
                "class": db["DBInstanceClass"],
                "status": db["DBInstanceStatus"],
            }
            for db in session.client("rds").describe_db_instances().get("DBInstances", [])
        ]
        inventory["rds"] = {"count": len(databases), "instances": databases[:20]}
    except (ClientError, BotoCoreError) as exc:
        inventory["rds"] = {"error": str(exc)}

    try:
        functions = [
            {"name": fn["FunctionName"], "runtime": fn.get("Runtime", "n/a")}
            for fn in session.client("lambda").list_functions().get("Functions", [])
        ]
        inventory["lambda"] = {"count": len(functions), "functions": functions[:20]}
    except (ClientError, BotoCoreError) as exc:
        inventory["lambda"] = {"error": str(exc)}

    return inventory


@tool
def aws_cost_by_tag(tag_key: str, months: int = 1) -> dict:
    """Get AWS cost broken down by the values of a cost-allocation tag.

    Args:
        tag_key: Tag key to group by, e.g. 'Environment', 'Project', 'Team'.
        months: Number of months to include (1-12). Defaults to 1.

    Returns:
        Cost per tag value (untagged spend is reported as 'untagged') and the total.
    """
    start, end = month_range(months)
    try:
        response = _ce().get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "TAG", "Key": tag_key}],
        )
    except (ClientError, BotoCoreError) as exc:
        return _aws_error(exc, tag_key=tag_key)

    rows = _grouped_costs(response, "tag_value")
    for row in rows:
        # Cost Explorer returns "Key$Value"; "Key$" means untagged.
        value = row["tag_value"].split("$", 1)[-1] if "$" in row["tag_value"] else row["tag_value"]
        row["tag_value"] = value or "untagged"
    return {
        "provider": "aws",
        "tag_key": tag_key,
        "period": f"{start} to {end}",
        "currency": "USD",
        "tag_values": rows,
        "total": round(sum(row["cost"] for row in rows), 2),
    }


aws_tools = [
    aws_monthly_cost_breakdown,
    aws_daily_cost_trend,
    aws_service_cost_details,
    aws_cost_by_region,
    aws_cost_by_account,
    aws_cost_forecast,
    aws_resource_inventory,
    aws_cost_by_tag,
]
