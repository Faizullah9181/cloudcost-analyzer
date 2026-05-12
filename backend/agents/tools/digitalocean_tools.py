"""DigitalOcean Billing tools."""

from strands import tool
import requests


@tool(description="Get DigitalOcean billing summary")
def digitalocean_billing_summary(api_token: str = None) -> dict:
    """
    Get DigitalOcean billing information and invoices.

    Args:
        api_token: DigitalOcean API token (uses config if not provided)

    Returns:
        Dictionary with billing summary
    """
    try:
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        token = api_token or settings.digitalocean_api_token
        if not token:
            return {"error": "DigitalOcean API token not configured"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # Get balance
        balance_resp = requests.get(
            "https://api.digitalocean.com/v2/customers/my/balance",
            headers=headers,
            timeout=10,
        )

        # Get invoices
        invoices_resp = requests.get(
            "https://api.digitalocean.com/v2/customers/my/invoices",
            headers=headers,
            timeout=10,
        )

        balance_data = balance_resp.json() if balance_resp.status_code == 200 else {}
        invoices_data = invoices_resp.json() if invoices_resp.status_code == 200 else {}

        # Process recent invoices
        invoices = []
        if "invoices" in invoices_data:
            for invoice in invoices_data["invoices"][:5]:  # Last 5 invoices
                invoices.append(
                    {
                        "date": invoice.get("date"),
                        "total": float(invoice.get("total", 0)),
                        "status": invoice.get("status"),
                        "uuid": invoice.get("uuid"),
                    }
                )

        return {
            "provider": "digitalocean",
            "account_balance": float(balance_data.get("month_to_date_balance", 0)),
            "account_balance_previous_month": float(
                balance_data.get("account_balance", 0)
            ),
            "recent_invoices": invoices,
            "currency": "USD",
        }

    except Exception as e:
        return {"error": f"Failed to fetch DigitalOcean billing: {str(e)}"}


@tool(description="Get DigitalOcean resources usage and costs")
def digitalocean_resource_costs(api_token: str = None) -> dict:
    """Get breakdown of DigitalOcean resources and their costs."""
    try:
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        token = api_token or settings.digitalocean_api_token
        if not token:
            return {"error": "DigitalOcean API token not configured"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        resources = {
            "droplets": {"count": 0, "cost": 0.0},
            "volumes": {"count": 0, "cost": 0.0},
            "load_balancers": {"count": 0, "cost": 0.0},
            "databases": {"count": 0, "cost": 0.0},
            "app_platform": {"count": 0, "cost": 0.0},
        }

        # Get droplets
        droplets_resp = requests.get(
            "https://api.digitalocean.com/v2/droplets?per_page=200",
            headers=headers,
            timeout=10,
        )
        if droplets_resp.status_code == 200:
            droplets = droplets_resp.json().get("droplets", [])
            resources["droplets"]["count"] = len(droplets)
            resources["droplets"]["cost"] = sum(
                d.get("size", {}).get("price_monthly", 0) for d in droplets
            )

        # Get volumes
        volumes_resp = requests.get(
            "https://api.digitalocean.com/v2/volumes?per_page=200",
            headers=headers,
            timeout=10,
        )
        if volumes_resp.status_code == 200:
            volumes = volumes_resp.json().get("volumes", [])
            resources["volumes"]["count"] = len(volumes)
            resources["volumes"]["cost"] = sum(
                v.get("size_gigabytes", 0) * 0.10 for v in volumes
            )  # $0.10/GB/month

        # Get load balancers
        lb_resp = requests.get(
            "https://api.digitalocean.com/v2/load_balancers?per_page=200",
            headers=headers,
            timeout=10,
        )
        if lb_resp.status_code == 200:
            lbs = lb_resp.json().get("load_balancers", [])
            resources["load_balancers"]["count"] = len(lbs)
            resources["load_balancers"]["cost"] = len(lbs) * 10.0  # $10/month per LB

        # Get databases
        db_resp = requests.get(
            "https://api.digitalocean.com/v2/databases?per_page=200",
            headers=headers,
            timeout=10,
        )
        if db_resp.status_code == 200:
            dbs = db_resp.json().get("databases", [])
            resources["databases"]["count"] = len(dbs)
            # Estimate based on node count and size
            for db in dbs:
                resources["databases"]["cost"] += db.get("num_nodes", 1) * 15.0

        total_cost = sum(r["cost"] for r in resources.values())

        return {
            "provider": "digitalocean",
            "resources": resources,
            "total_monthly_cost": round(total_cost, 2),
            "currency": "USD",
        }

    except Exception as e:
        return {"error": f"Failed to fetch DigitalOcean resource costs: {str(e)}"}


@tool(description="Get DigitalOcean billing metrics by month")
def digitalocean_monthly_trend(api_token: str = None, months: int = 6) -> dict:
    """Get DigitalOcean billing trend over past months."""
    try:
        try:
            from backend.config import settings
        except ImportError:
            from config import settings

        token = api_token or settings.digitalocean_api_token
        if not token:
            return {"error": "DigitalOcean API token not configured"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        invoices_resp = requests.get(
            "https://api.digitalocean.com/v2/customers/my/invoices?per_page=100",
            headers=headers,
            timeout=10,
        )

        monthly_costs = []
        if invoices_resp.status_code == 200:
            invoices = invoices_resp.json().get("invoices", [])

            # Group by month
            monthly_dict = {}
            for invoice in invoices:
                date = invoice.get("date", "")[:7]  # YYYY-MM
                total = float(invoice.get("total", 0))
                if date in monthly_dict:
                    monthly_dict[date] += total
                else:
                    monthly_dict[date] = total

            # Sort and limit
            for date in sorted(monthly_dict.keys(), reverse=True)[:months]:
                monthly_costs.append(
                    {"month": date, "cost": round(monthly_dict[date], 2)}
                )

        return {
            "provider": "digitalocean",
            "monthly_costs": monthly_costs,
            "currency": "USD",
        }

    except Exception as e:
        return {"error": f"Failed to fetch DigitalOcean monthly trend: {str(e)}"}
