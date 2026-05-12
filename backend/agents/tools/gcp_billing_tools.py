"""GCP Cloud Billing tools."""

from strands import tool


@tool(description="Get GCP billing data by service")
def gcp_billing_by_service(project_id: str, start_date: str, end_date: str) -> dict:
    """
    Get GCP costs broken down by service.

    Args:
        project_id: GCP project ID
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Dictionary with service breakdown and costs
    """
    try:
        from google.oauth2 import service_account
        import json
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        if not settings.gcp_service_account_json:
            return {"error": "GCP service account not configured"}

        # Load credentials
        if settings.gcp_service_account_json.startswith("{"):
            creds_dict = json.loads(settings.gcp_service_account_json)
        else:
            with open(settings.gcp_service_account_json) as f:
                creds_dict = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(creds_dict)

        # Query BigQuery for billing data (GCP uses BigQuery export)
        from google.cloud import bigquery

        bq_client = bigquery.Client(credentials=credentials, project=project_id)

        query = f"""
        SELECT
            service.description as service,
            SUM(cost) as total_cost,
            SUM(usage.amount) as usage_amount,
            usage.unit
        FROM `{project_id}.billing_export.gcp_billing_export_v1_*`
        WHERE _TABLE_SUFFIX BETWEEN 
            REPLACE('{start_date}', '-', '') AND REPLACE('{end_date}', '-', '')
        GROUP BY service, usage.unit
        ORDER BY total_cost DESC
        """

        query_job = bq_client.query(query)
        results = query_job.result()

        services = {}
        total_cost = 0.0

        for row in results:
            service = row["service"] or "Unknown"
            cost = float(row["total_cost"] or 0)
            services[service] = {
                "cost": round(cost, 2),
                "usage": float(row["usage_amount"] or 0),
                "unit": row["unit"] or "",
            }
            total_cost += cost

        return {
            "provider": "gcp",
            "project_id": project_id,
            "period": f"{start_date} to {end_date}",
            "total_cost": round(total_cost, 2),
            "services": services,
            "currency": "USD",
        }

    except Exception as e:
        return {"error": f"Failed to fetch GCP costs: {str(e)}"}


@tool(description="Get GCP daily cost trend")
def gcp_cost_daily_trend(project_id: str, start_date: str, end_date: str) -> dict:
    """Get daily cost trend for GCP project."""
    try:
        from google.oauth2 import service_account
        from google.cloud import bigquery
        import json
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        if not settings.gcp_service_account_json:
            return {"error": "GCP service account not configured"}

        # Load credentials
        if settings.gcp_service_account_json.startswith("{"):
            creds_dict = json.loads(settings.gcp_service_account_json)
        else:
            with open(settings.gcp_service_account_json) as f:
                creds_dict = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        bq_client = bigquery.Client(credentials=credentials, project=project_id)

        query = f"""
        SELECT
            DATE(TIMESTAMP_MICROS(CAST(invoice_month || '01' AS INT64) * 1000000)) as date,
            SUM(cost) as daily_cost
        FROM `{project_id}.billing_export.gcp_billing_export_v1_*`
        WHERE _TABLE_SUFFIX BETWEEN 
            REPLACE('{start_date}', '-', '') AND REPLACE('{end_date}', '-', '')
        GROUP BY date
        ORDER BY date
        """

        query_job = bq_client.query(query)
        results = query_job.result()

        daily_costs = []
        for row in results:
            daily_costs.append(
                {
                    "date": str(row["date"]),
                    "cost": round(float(row["daily_cost"] or 0), 2),
                }
            )

        return {
            "provider": "gcp",
            "project_id": project_id,
            "daily_costs": daily_costs,
            "currency": "USD",
        }

    except Exception as e:
        return {"error": f"Failed to fetch GCP daily trend: {str(e)}"}


@tool(description="Get GCP resource inventory")
def gcp_resource_inventory(project_id: str) -> dict:
    """Get inventory of GCP resources."""
    try:
        from google.cloud import asset_v1
        from google.oauth2 import service_account
        import json
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        if not settings.gcp_service_account_json:
            return {"error": "GCP service account not configured"}

        # Load credentials
        if settings.gcp_service_account_json.startswith("{"):
            creds_dict = json.loads(settings.gcp_service_account_json)
        else:
            with open(settings.gcp_service_account_json) as f:
                creds_dict = json.load(f)

        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = asset_v1.AssetServiceClient(credentials=credentials)

        parent = f"projects/{project_id}"
        response = client.list_assets(request={"parent": parent})

        resources = []
        count = 0
        for asset in response:
            if count >= 50:  # Limit to 50
                break
            resources.append(
                {
                    "name": asset.name,
                    "type": asset.asset_type,
                    "resource_name": asset.resource.get("name", ""),
                }
            )
            count += 1

        return {
            "provider": "gcp",
            "project_id": project_id,
            "resource_count": count,
            "resources": resources,
        }

    except Exception as e:
        return {"error": f"Failed to fetch GCP resource inventory: {str(e)}"}
