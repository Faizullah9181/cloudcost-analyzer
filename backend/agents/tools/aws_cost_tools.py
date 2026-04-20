"""Custom Strands tools for AWS cost analysis."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from strands import tool

from config import settings

logger = logging.getLogger(__name__)


def _get_ce_client():
    """Get AWS Cost Explorer client."""
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.client("ce", **kwargs)


def _get_org_client():
    """Get AWS Organizations client."""
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.client("organizations", **kwargs)


@tool
def get_monthly_cost_breakdown(months: int = 3) -> str:
    """Get monthly AWS cost breakdown by service for the last N months.

    Args:
        months: Number of months to look back (1-12). Defaults to 3.

    Returns:
        JSON string with monthly cost data grouped by service.
    """
    months = max(1, min(months, 12))
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=30 * months)).strftime("%Y-%m-%d")

    try:
        client = _get_ce_client()
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost", "UsageQuantity"],
            GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
        )

        results = []
        for period in response.get("ResultsByTime", []):
            period_start = period["TimePeriod"]["Start"]
            for group in period.get("Groups", []):
                service = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if cost > 0.01:
                    results.append(
                        {"date": period_start, "service": service, "cost": round(cost, 2)}
                    )

        return json.dumps(
            {
                "period": f"{start_date} to {end_date}",
                "data": sorted(results, key=lambda x: x["cost"], reverse=True),
                "total": round(sum(r["cost"] for r in results), 2),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        return json.dumps({"error": str(e)})


@tool
def get_daily_cost_trend(days: int = 30) -> str:
    """Get daily AWS cost trend for the last N days.

    Args:
        days: Number of days to look back (1-90). Defaults to 30.

    Returns:
        JSON string with daily total cost data.
    """
    days = max(1, min(days, 90))
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        client = _get_ce_client()
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metrics=["UnblendedCost"],
        )

        results = []
        for period in response.get("ResultsByTime", []):
            cost = float(period["Total"]["UnblendedCost"]["Amount"])
            results.append({"date": period["TimePeriod"]["Start"], "cost": round(cost, 2)})

        return json.dumps(
            {
                "period": f"{start_date} to {end_date}",
                "data": results,
                "total": round(sum(r["cost"] for r in results), 2),
                "average_daily": round(sum(r["cost"] for r in results) / max(len(results), 1), 2),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        return json.dumps({"error": str(e)})


@tool
def get_service_cost_details(service_name: str, months: int = 1) -> str:
    """Get detailed cost breakdown for a specific AWS service.

    Args:
        service_name: AWS service name (e.g., 'Amazon EC2', 'Amazon S3', 'AWS Lambda').
        months: Number of months to look back. Defaults to 1.

    Returns:
        JSON string with detailed cost breakdown for the service.
    """
    months = max(1, min(months, 12))
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=30 * months)).strftime("%Y-%m-%d")

    try:
        client = _get_ce_client()
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost", "UsageQuantity"],
            Filter={"Dimensions": {"Key": "SERVICE", "Values": [service_name]}},
            GroupBy=[{"Type": "DIMENSION", "Key": "USAGE_TYPE"}],
        )

        results = []
        for period in response.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                usage_type = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if cost > 0.001:
                    results.append(
                        {
                            "usage_type": usage_type,
                            "cost": round(cost, 4),
                            "date": period["TimePeriod"]["Start"],
                        }
                    )

        return json.dumps(
            {
                "service": service_name,
                "period": f"{start_date} to {end_date}",
                "data": sorted(results, key=lambda x: x["cost"], reverse=True),
                "total": round(sum(r["cost"] for r in results), 2),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        return json.dumps({"error": str(e)})


@tool
def get_cost_by_region(months: int = 1) -> str:
    """Get AWS cost breakdown by region.

    Args:
        months: Number of months to look back. Defaults to 1.

    Returns:
        JSON string with cost data grouped by AWS region.
    """
    months = max(1, min(months, 12))
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=30 * months)).strftime("%Y-%m-%d")

    try:
        client = _get_ce_client()
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "REGION"}],
        )

        results = []
        for period in response.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                region = group["Keys"][0] or "global"
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if cost > 0.01:
                    results.append({"region": region, "cost": round(cost, 2)})

        return json.dumps(
            {
                "period": f"{start_date} to {end_date}",
                "data": sorted(results, key=lambda x: x["cost"], reverse=True),
                "total": round(sum(r["cost"] for r in results), 2),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        return json.dumps({"error": str(e)})


@tool
def get_cost_by_account(months: int = 1) -> str:
    """Get AWS cost breakdown by linked account (for AWS Organizations).

    Args:
        months: Number of months to look back. Defaults to 1.

    Returns:
        JSON string with cost data grouped by AWS account ID.
    """
    months = max(1, min(months, 12))
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=30 * months)).strftime("%Y-%m-%d")

    try:
        client = _get_ce_client()
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "DIMENSION", "Key": "LINKED_ACCOUNT"}],
        )

        # Try to get account names
        account_names = {}
        try:
            org_client = _get_org_client()
            accounts = org_client.list_accounts()
            for acct in accounts.get("Accounts", []):
                account_names[acct["Id"]] = acct["Name"]
        except (ClientError, NoCredentialsError):
            pass

        results = []
        for period in response.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                account_id = group["Keys"][0]
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if cost > 0.01:
                    results.append(
                        {
                            "account_id": account_id,
                            "account_name": account_names.get(account_id, account_id),
                            "cost": round(cost, 2),
                        }
                    )

        return json.dumps(
            {
                "period": f"{start_date} to {end_date}",
                "data": sorted(results, key=lambda x: x["cost"], reverse=True),
                "total": round(sum(r["cost"] for r in results), 2),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        return json.dumps({"error": str(e)})


@tool
def get_cost_forecast(forecast_days: int = 30) -> str:
    """Get AWS cost forecast for the next N days.

    Args:
        forecast_days: Number of days to forecast (1-90). Defaults to 30.

    Returns:
        JSON string with forecast data.
    """
    forecast_days = max(1, min(forecast_days, 90))
    start_date = datetime.utcnow().strftime("%Y-%m-%d")
    end_date = (datetime.utcnow() + timedelta(days=forecast_days)).strftime("%Y-%m-%d")

    try:
        client = _get_ce_client()
        response = client.get_cost_forecast(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="DAILY",
            Metric="UNBLENDED_COST",
        )

        forecasts = []
        for item in response.get("ForecastResultsByTime", []):
            forecasts.append(
                {
                    "date": item["TimePeriod"]["Start"],
                    "mean": round(float(item["MeanValue"]), 2),
                }
            )

        total_forecast = float(response.get("Total", {}).get("Amount", 0))
        return json.dumps(
            {
                "period": f"{start_date} to {end_date}",
                "data": forecasts,
                "total_forecast": round(total_forecast, 2),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        return json.dumps({"error": str(e)})


@tool
def get_resource_inventory() -> str:
    """Get a summary of active AWS resources across key services (EC2, RDS, S3, Lambda).

    Returns:
        JSON string with resource counts and details.
    """
    inventory = {}
    kwargs = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token

    # EC2 instances
    try:
        ec2 = boto3.client("ec2", **kwargs)
        instances = ec2.describe_instances()
        ec2_list = []
        for reservation in instances["Reservations"]:
            for inst in reservation["Instances"]:
                ec2_list.append(
                    {
                        "id": inst["InstanceId"],
                        "type": inst["InstanceType"],
                        "state": inst["State"]["Name"],
                    }
                )
        inventory["ec2"] = {"count": len(ec2_list), "instances": ec2_list[:20]}
    except (ClientError, NoCredentialsError) as e:
        inventory["ec2"] = {"error": str(e)}

    # S3 buckets
    try:
        s3 = boto3.client("s3", **kwargs)
        buckets = s3.list_buckets()
        inventory["s3"] = {
            "count": len(buckets.get("Buckets", [])),
            "buckets": [b["Name"] for b in buckets.get("Buckets", [])][:20],
        }
    except (ClientError, NoCredentialsError) as e:
        inventory["s3"] = {"error": str(e)}

    # RDS instances
    try:
        rds = boto3.client("rds", **kwargs)
        db_instances = rds.describe_db_instances()
        rds_list = []
        for db in db_instances["DBInstances"]:
            rds_list.append(
                {
                    "id": db["DBInstanceIdentifier"],
                    "engine": db["Engine"],
                    "class": db["DBInstanceClass"],
                    "status": db["DBInstanceStatus"],
                }
            )
        inventory["rds"] = {"count": len(rds_list), "instances": rds_list[:20]}
    except (ClientError, NoCredentialsError) as e:
        inventory["rds"] = {"error": str(e)}

    # Lambda functions
    try:
        lam = boto3.client("lambda", **kwargs)
        functions = lam.list_functions()
        lam_list = [
            {"name": f["FunctionName"], "runtime": f.get("Runtime", "N/A")}
            for f in functions.get("Functions", [])
        ]
        inventory["lambda"] = {"count": len(lam_list), "functions": lam_list[:20]}
    except (ClientError, NoCredentialsError) as e:
        inventory["lambda"] = {"error": str(e)}

    return json.dumps(inventory)


@tool
def get_cost_by_tag(tag_key: str, months: int = 1) -> str:
    """Get AWS cost breakdown by a specific cost allocation tag.

    Args:
        tag_key: The tag key to group costs by (e.g., 'Environment', 'Project', 'Team').
        months: Number of months to look back. Defaults to 1.

    Returns:
        JSON string with cost data grouped by tag values.
    """
    months = max(1, min(months, 12))
    end_date = datetime.utcnow().strftime("%Y-%m-%d")
    start_date = (datetime.utcnow() - timedelta(days=30 * months)).strftime("%Y-%m-%d")

    try:
        client = _get_ce_client()
        response = client.get_cost_and_usage(
            TimePeriod={"Start": start_date, "End": end_date},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"],
            GroupBy=[{"Type": "TAG", "Key": tag_key}],
        )

        results = []
        for period in response.get("ResultsByTime", []):
            for group in period.get("Groups", []):
                tag_value = group["Keys"][0] or "untagged"
                cost = float(group["Metrics"]["UnblendedCost"]["Amount"])
                if cost > 0.01:
                    results.append({"tag_value": tag_value, "cost": round(cost, 2)})

        return json.dumps(
            {
                "tag_key": tag_key,
                "period": f"{start_date} to {end_date}",
                "data": sorted(results, key=lambda x: x["cost"], reverse=True),
                "total": round(sum(r["cost"] for r in results), 2),
            }
        )
    except (ClientError, NoCredentialsError) as e:
        return json.dumps({"error": str(e)})


# Collect all tools for the agent
cost_tools = [
    get_monthly_cost_breakdown,
    get_daily_cost_trend,
    get_service_cost_details,
    get_cost_by_region,
    get_cost_by_account,
    get_cost_forecast,
    get_resource_inventory,
    get_cost_by_tag,
]
