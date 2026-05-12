"""Azure Cost Management tools."""

from strands import tool


@tool(description="Get Azure cost analysis by service for a time period")
def azure_cost_by_service(
    subscription_id: str, start_date: str, end_date: str, granularity: str = "Daily"
) -> dict:
    """
    Get Azure costs broken down by service/meter.

    Args:
        subscription_id: Azure subscription ID
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        granularity: Daily or Monthly

    Returns:
        Dictionary with service breakdown and costs
    """
    try:
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.identity import ClientSecretCredential
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        # Authenticate
        if not all(
            [
                settings.azure_tenant_id,
                settings.azure_client_id,
                settings.azure_client_secret,
            ]
        ):
            return {"error": "Azure credentials not configured"}

        credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )

        client = CostManagementClient(credential, subscription_id)

        # Query costs by meter
        scope = f"/subscriptions/{subscription_id}"
        query = {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {
                "from": f"{start_date}T00:00:00Z",
                "to": f"{end_date}T23:59:59Z",
            },
            "dataset": {
                "granularity": granularity,
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
                "grouping": [{"type": "Dimension", "name": "MeterCategory"}],
            },
        }

        result = client.query.usage(scope, query)

        # Format result
        services = {}
        total_cost = 0.0

        if hasattr(result, "rows"):
            for row in result.rows:
                service = row[0] if len(row) > 0 else "Unknown"
                cost = float(row[1]) if len(row) > 1 else 0.0
                services[service] = cost
                total_cost += cost

        return {
            "provider": "azure",
            "period": f"{start_date} to {end_date}",
            "total_cost": round(total_cost, 2),
            "services": services,
            "currency": "USD",
        }

    except Exception as e:
        return {"error": f"Failed to fetch Azure costs: {str(e)}"}


@tool(description="Get Azure cost trend over time")
def azure_cost_daily_trend(
    subscription_id: str, start_date: str, end_date: str
) -> dict:
    """Get daily cost trend for Azure subscription."""
    try:
        from azure.mgmt.costmanagement import CostManagementClient
        from azure.identity import ClientSecretCredential
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        if not all(
            [
                settings.azure_tenant_id,
                settings.azure_client_id,
                settings.azure_client_secret,
            ]
        ):
            return {"error": "Azure credentials not configured"}

        credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )

        client = CostManagementClient(credential, subscription_id)
        scope = f"/subscriptions/{subscription_id}"

        query = {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {
                "from": f"{start_date}T00:00:00Z",
                "to": f"{end_date}T23:59:59Z",
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"totalCost": {"name": "PreTaxCost", "function": "Sum"}},
            },
        }

        result = client.query.usage(scope, query)

        daily_costs = []
        if hasattr(result, "rows"):
            for row in result.rows:
                date = row[0] if len(row) > 0 else "Unknown"
                cost = float(row[1]) if len(row) > 1 else 0.0
                daily_costs.append({"date": date, "cost": round(cost, 2)})

        return {"provider": "azure", "daily_costs": daily_costs, "currency": "USD"}

    except Exception as e:
        return {"error": f"Failed to fetch Azure daily trend: {str(e)}"}


@tool(description="Get Azure resource inventory and their costs")
def azure_resource_inventory(subscription_id: str) -> dict:
    """Get inventory of Azure resources with cost information."""
    try:
        from azure.mgmt.resource import ResourceManagementClient
        from azure.identity import ClientSecretCredential
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        if not all(
            [
                settings.azure_tenant_id,
                settings.azure_client_id,
                settings.azure_client_secret,
            ]
        ):
            return {"error": "Azure credentials not configured"}

        credential = ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )

        client = ResourceManagementClient(credential, subscription_id)

        resources = []
        for resource in client.resources.list():
            resources.append(
                {
                    "id": resource.id,
                    "name": resource.name,
                    "type": resource.type,
                    "location": resource.location,
                }
            )

        return {
            "provider": "azure",
            "resource_count": len(resources),
            "resources": resources[:50],  # Limit to 50 for performance
        }

    except Exception as e:
        return {"error": f"Failed to fetch Azure resource inventory: {str(e)}"}
