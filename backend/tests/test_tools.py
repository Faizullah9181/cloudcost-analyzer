"""Tests for provider tool helpers that do not touch the network."""

import pytest

from backend.a2ui import build_cost_analysis_a2ui_messages
from backend.agents.tools import TOOLS_BY_PROVIDER, get_tools, tool_names
from backend.agents.tools._common import day_range, month_range, parse_date_range
from backend.agents.tools.azure_cost_tools import _rows_as_dicts, _usage_date
from backend.agents.tools.digitalocean_tools import digitalocean_billing_summary
from backend.agents.tools.gcp_billing_tools import _billing_table, gcp_billing_by_service
from backend.config import settings


def test_registry_filters_by_provider():
    assert set(TOOLS_BY_PROVIDER) == {"aws", "azure", "gcp", "digitalocean"}
    assert len(get_tools()) == sum(len(v) for v in TOOLS_BY_PROVIDER.values())
    names = tool_names(["aws"])
    assert "aws_monthly_cost_breakdown" in names and not any(n.startswith("azure") for n in names)
    assert tool_names(["AZURE", "gcp"]) == tool_names(["azure"]) + tool_names(["gcp"])


def test_date_helpers():
    start, end = month_range(3)
    assert start < end and start.endswith("-01")
    start, end = day_range(7)
    assert start < end
    assert parse_date_range(None, None) == day_range(30)
    assert parse_date_range("2025-01-01", "2025-01-31") == ("2025-01-01", "2025-01-31")
    with pytest.raises(ValueError):
        parse_date_range("2025/01/01", None)
    with pytest.raises(ValueError):
        parse_date_range("2025-02-01", "2025-01-01")


def test_azure_row_mapping():
    class Column:  # pylint: disable=too-few-public-methods
        def __init__(self, name):
            self.name = name

    class Result:  # pylint: disable=too-few-public-methods
        columns = [Column("Cost"), Column("UsageDate"), Column("ServiceName"), Column("Currency")]
        rows = [[12.5, 20250131, "Virtual Machines", "USD"]]

    rows = _rows_as_dicts(Result())
    assert rows == [{"Cost": 12.5, "UsageDate": 20250131, "ServiceName": "Virtual Machines", "Currency": "USD"}]
    assert _usage_date(20250131) == "2025-01-31"


def test_digitalocean_requires_token():
    result = digitalocean_billing_summary()
    assert result["provider"] == "digitalocean" and "not configured" in result["error"]


def test_gcp_billing_table_validation(monkeypatch):
    monkeypatch.setattr(settings, "gcp_project_id", "my-project")
    monkeypatch.setattr(settings, "gcp_billing_dataset", "billing_export")
    assert _billing_table() == "`my-project.billing_export.gcp_billing_export_v1_*`"
    monkeypatch.setattr(settings, "gcp_billing_dataset", "bad; DROP TABLE")
    with pytest.raises(ValueError):
        _billing_table()
    monkeypatch.setattr(settings, "gcp_project_id", "")
    assert "No GCP project" in gcp_billing_by_service()["error"]


def test_a2ui_generator_shape():
    messages = build_cost_analysis_a2ui_messages(
        {"summary": "s", "total_cost": 12.3, "providers": {"aws": {}, "gcp": {}}, "service_breakdown": [{"service": "EC2", "cost": 12.3}]}
    )
    assert messages[0]["beginRendering"]["surfaceId"] == "cost-analysis"
    components = {c["id"]: c for c in messages[1]["surfaceUpdate"]["components"]}
    assert components["title"]["component"]["Text"]["text"]["literalString"] == "AWS + GCP Cost Analysis"
    assert "EC2" in components["service-0"]["component"]["Text"]["text"]["literalString"]
    assert "No optimization" in components["rec-0"]["component"]["Text"]["text"]["literalString"]
