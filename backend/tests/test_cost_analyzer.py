"""Tests for JSON extraction and analysis normalisation."""

import json

from backend.agents.cost_analyzer import extract_json, normalize_analysis


def test_extract_json_variants():
    payload = {"summary": "ok {braces} inside", "total_cost": 1}
    text = json.dumps(payload)
    assert extract_json(text) == payload
    assert extract_json(f"Here you go:\n```json\n{text}\n```") == payload
    assert extract_json(f"Sure! {text} Let me know.") == payload
    assert extract_json("no json here") is None
    assert extract_json("[1, 2, 3]") is None


def test_normalize_fills_percentages_and_totals():
    parsed = {
        "summary": "s",
        "service_breakdown": [{"service": "A", "cost": "75"}, {"service": "B", "cost": 25}],
        "recommendations": "single string",
        "chart_type": "donut",
    }
    result = normalize_analysis(parsed, "raw", "what did I spend")
    assert result["total_cost"] == 100.0
    assert [item["percentage"] for item in result["service_breakdown"]] == [75.0, 25.0]
    assert result["recommendations"] == ["single string"]
    assert result["chart_type"] == "bar"
    assert result["query_type"] == "costs"
    assert result["a2ui_messages"][0]["beginRendering"]["root"] == "root-card"


def test_normalize_handles_missing_json_and_dict_breakdown():
    result = normalize_analysis(None, "The model said something unstructured.", "forecast")
    assert result["summary"] == "The model said something unstructured."
    assert result["total_cost"] == 0 and result["service_breakdown"] == []
    assert result["query_type"] == "forecast"

    result = normalize_analysis(
        {"service_breakdown": {"EC2": 10, "S3": 5}, "time_series": [{"date": "2025-01", "cost": 15}]},
        "",
    )
    assert result["service_breakdown"][0] == {"service": "EC2", "cost": 10.0, "percentage": 66.67, "change": 0.0}
    assert result["time_series"] == [{"date": "2025-01", "cost": 15.0, "service": "Total"}]
    assert result["providers"] == {}
