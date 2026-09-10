"""Shared fixtures: in-memory DB, isolated settings, and a scripted fake Strands model."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Environment must be fixed before backend.config is imported anywhere.
os.environ.update(
    {
        "DATABASE_URL": "sqlite:///:memory:",
        "LLM_PROVIDER": "bedrock",
        "MEMORY_LLM_SUMMARIES": "false",
        "MEMORY_COMPRESSION_THRESHOLD": "6",
        "MEMORY_RECENT_WINDOW": "2",
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_PROFILE": "",
        "AZURE_TENANT_ID": "",
        "AZURE_CLIENT_ID": "",
        "AZURE_CLIENT_SECRET": "",
        "AZURE_SUBSCRIPTION_ID": "",
        "GCP_SERVICE_ACCOUNT_JSON": "",
        "GCP_PROJECT_ID": "",
        "DIGITALOCEAN_API_TOKEN": "",
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
        "GEMINI_API_KEY": "",
    }
)

import pytest  # noqa: E402
from strands.models.model import Model  # noqa: E402

from backend.database import Base, engine, init_db  # noqa: E402

SAMPLE_ANALYSIS = {
    "summary": "Your AWS spend for January was USD 150.00, driven by EC2 and S3.",
    "query_type": "costs",
    "total_cost": 150.0,
    "currency": "USD",
    "period": "2025-01-01 to 2025-01-31",
    "providers": {"aws": {"total": 150.0, "services": {"Amazon EC2": 100.0, "Amazon S3": 50.0}}},
    "service_breakdown": [
        {"service": "Amazon EC2", "cost": 100.0, "percentage": 0, "change": 0},
        {"service": "Amazon S3", "cost": 50.0},
    ],
    "time_series": [],
    "recommendations": ["Buy Reserved Instances for steady EC2 workloads"],
    "chart_type": "bar",
}
SAMPLE_JSON = json.dumps(SAMPLE_ANALYSIS)


class FakeModel(Model):
    """Scripted Strands model.

    ``script`` is a list of steps consumed one per model call. A step is either
    ``{"text": "..."}`` (final answer) or ``{"tool": name, "input": {...}}`` (tool call).
    When the script is exhausted the model returns ``default_text``.
    """

    def __init__(self, script: list[dict[str, Any]] | None = None, default_text: str = SAMPLE_JSON, fail: bool = False):
        self.script = list(script or [])
        self.default_text = default_text
        self.fail = fail
        self.calls: list[dict[str, Any]] = []
        self._config: dict[str, Any] = {"model_id": "fake"}

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        return dict(self._config)

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # pragma: no cover
        raise NotImplementedError("FakeModel does not support structured output")
        yield  # pylint: disable=unreachable

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls.append(
            {
                "messages": [dict(m) for m in messages],
                "system_prompt": system_prompt,
                "tool_specs": [spec["name"] for spec in (tool_specs or [])],
            }
        )
        if self.fail:
            raise RuntimeError("simulated model outage")
        step = self.script.pop(0) if self.script else {"text": self.default_text}
        yield {"messageStart": {"role": "assistant"}}
        if "tool" in step:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"tool-{len(self.calls)}", "name": step["tool"]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(step.get("input", {}))}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockDelta": {"delta": {"text": step["text"]}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}, "metrics": {"latencyMs": 1}}}


@pytest.fixture(autouse=True)
def fresh_db():
    """Recreate all tables for every test."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def fake_model(monkeypatch):
    """Install a FakeModel as the model factory; returns a function to configure it."""
    holder: dict[str, FakeModel] = {"model": FakeModel()}

    def _build_model(provider=None, config=None):  # pylint: disable=unused-argument
        return holder["model"]

    monkeypatch.setattr("backend.agents.agent_harness.build_model", _build_model)
    monkeypatch.setattr("backend.agents.cost_analyzer.build_model", _build_model)

    def configure(script=None, default_text=SAMPLE_JSON, fail=False) -> FakeModel:
        holder["model"] = FakeModel(script=script, default_text=default_text, fail=fail)
        return holder["model"]

    configure.current = lambda: holder["model"]  # type: ignore[attr-defined]
    return configure


@pytest.fixture
def store():
    from backend.services.session_store import SessionStore  # pylint: disable=import-outside-toplevel

    with SessionStore() as session_store:
        yield session_store


@pytest.fixture
def client():
    from fastapi.testclient import TestClient  # pylint: disable=import-outside-toplevel

    from backend.main import app  # pylint: disable=import-outside-toplevel

    with TestClient(app) as test_client:
        yield test_client
