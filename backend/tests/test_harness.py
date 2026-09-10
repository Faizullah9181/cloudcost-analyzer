"""End-to-end tests for the AgentHarness with a scripted model."""

import json

from backend.agents.agent_harness import AgentHarness
from backend.config import settings
from backend.services.session_store import SessionStore
from backend.tests.conftest import SAMPLE_ANALYSIS, SAMPLE_JSON


def test_create_session_and_analyze(fake_model, store):
    model = fake_model()
    harness = AgentHarness(store=store)
    session = harness.create_session("Test", ["aws"], "bedrock", user_id="u1", connection_context={"aws": {"account_id": "111122223333"}})

    turn = harness.analyze("What are my AWS costs this month?")

    assert turn.success and turn.error is None
    assert turn.analysis["total_cost"] == 150.0
    assert [i["percentage"] for i in turn.analysis["service_breakdown"]] == [66.67, 33.33]
    assert turn.usage["total_tokens"] == 15
    assert turn.response == SAMPLE_ANALYSIS["summary"]

    call = model.calls[0]
    assert "Connected Cloud Accounts" in call["system_prompt"] and "111122223333" in call["system_prompt"]
    assert "### Session Information" in call["system_prompt"]
    assert "aws_monthly_cost_breakdown" in call["tool_specs"]
    assert not any(name.startswith("azure") for name in call["tool_specs"])

    with SessionStore() as fresh:
        reloaded = fresh.require_session(session.id)
        assert reloaded.message_count == 2
        assert reloaded.messages[0].role == "user" and reloaded.messages[1].analysis["total_cost"] == 150.0
        assert reloaded.analysis_results["total_cost"] == 150.0
        assert fresh.get_user_profile("u1")["total_queries"] == 1


def test_resume_replays_history(fake_model, store):
    model = fake_model()
    harness = AgentHarness(store=store)
    session = harness.create_session("Resume", ["aws"], "bedrock")
    harness.analyze("What are my AWS costs?")

    resumed = AgentHarness(store=store)
    resumed.load_session(session.id)
    assert resumed.memory_manager.hot_memory.total_messages == 2
    assert [m["role"] for m in resumed._messages] == ["user", "assistant"]  # pylint: disable=protected-access

    resumed.analyze("And by region?")
    replayed = model.calls[-1]["messages"]
    assert [m["role"] for m in replayed] == ["user", "assistant", "user"]
    assert "Recent Context" in model.calls[-1]["system_prompt"]


def test_tool_call_loop_with_real_tool(fake_model, store):
    model = fake_model(script=[{"tool": "digitalocean_billing_summary", "input": {}}, {"text": SAMPLE_JSON}])
    harness = AgentHarness(store=store)
    harness.create_session("DO", ["digitalocean"], "bedrock")

    turn = harness.analyze("What is my DigitalOcean usage?")

    assert turn.success
    assert turn.tool_calls == [{"tool": "digitalocean_billing_summary", "calls": 1, "successes": 1, "errors": 0, "seconds": turn.tool_calls[0]["seconds"]}]
    tool_result_turn = model.calls[1]["messages"][-1]
    assert tool_result_turn["role"] == "user"
    text = json.dumps(tool_result_turn["content"])
    assert "not configured" in text  # the real tool ran and reported the missing token


def test_model_failure_is_recorded(fake_model, store):
    fake_model(fail=True)
    harness = AgentHarness(store=store)
    harness.create_session("Fail", ["aws"], "bedrock")
    turn = harness.analyze("What are my costs?")
    assert not turn.success and "simulated model outage" in turn.error
    assert turn.analysis["summary"].startswith("Analysis failed")
    messages = store.get_messages(harness.session_id)
    assert messages[-1].role == "assistant" and "error" in messages[-1].tags and messages[-1].analysis is None


def test_auto_compression_persists_summary(fake_model, store):
    fake_model()
    harness = AgentHarness(store=store)
    harness.create_session("Long", ["aws"], "bedrock")
    turns = [harness.analyze(f"Question {i} about costs") for i in range(3)]  # 6 messages = threshold
    assert turns[-1].compression and turns[-1].compression["compressed_messages"] > 0
    assert harness.session.compression_count == 1
    messages = store.get_messages(harness.session_id)
    assert messages[-1].is_summary and messages[-1].role == "system"
    assert harness.get_memory_status()["cold_memory"]["summaries"] == 1
    assert harness.check_compression_needed() is False

    result = harness.compress_context()
    assert result["compression_count"] == 1 or result["compressed_messages"] >= 0


def test_runtime_credentials_are_not_persisted(fake_model, store, monkeypatch):
    fake_model()
    monkeypatch.setattr(settings, "digitalocean_api_token", "")
    harness = AgentHarness(store=store)
    session = harness.create_session(
        "Creds", ["digitalocean"], "bedrock", credentials={"digitalocean": {"api_token": "s3cret", "team": "acme"}}
    )
    assert settings.digitalocean_api_token == "s3cret"
    assert session.connection_context == {"digitalocean": {"team": "acme"}}
    assert "s3cret" not in json.dumps(session.to_export())

    harness.set_provider_credentials("aws", {"account_id": "999988887777", "access_key_id": "AKIA", "secret_access_key": "x"})
    monkeypatch.setattr(settings, "aws_access_key_id", "")
    monkeypatch.setattr(settings, "aws_secret_access_key", "")
    assert "aws" in harness.providers and harness.connection_context["aws"] == {"account_id": "999988887777"}


def test_export_and_health(fake_model, store):
    fake_model()
    harness = AgentHarness(store=store)
    harness.create_session("Export", ["aws", "gcp"], "bedrock")
    harness.analyze("costs?")
    export = harness.export_session()
    assert export["messages"][0]["role"] == "user" and export["memory"]["message_count"] == 2
    health = harness.get_health_status()
    assert health["session_active"] and health["tools"] == 12 and health["memory_layers"]["deep"] == "disabled"
    summary = harness.end_session()
    assert summary["query_count"] == 1 and summary["message_count"] == 2
