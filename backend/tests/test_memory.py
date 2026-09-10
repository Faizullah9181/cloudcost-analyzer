"""Tests for the four memory layers and the manager."""

from datetime import datetime, timedelta

from backend.memory import CloudProvider, DeepMemory, HotMemory, MemoryManager, ProceduralMemory, detect_query_type
from backend.memory.cold_memory import ColdMemory, MessageRole


def test_hot_memory_metadata_and_detection():
    hot = HotMemory("sess_1", session_name="Q2 review")
    hot.add_provider("aws", account_id="123456789012", region="us-east-1")
    hot.add_provider(CloudProvider.AZURE, account_id="sub-1")
    assert hot.current_provider == CloudProvider.AWS
    assert hot.detect_provider("compare with azure costs") == CloudProvider.AZURE
    assert hot.detect_provider("what about gcp") is None  # not active
    hot.add_interaction("user", "x" * 500)
    text = hot.assemble_context()
    assert "Q2 review" in text and "123456789012" in text and "AZURE" in text
    assert "..." in hot.get_recent_interactions_text()


def test_cold_memory_search_and_compression():
    cold = ColdMemory("sess_1")
    for index in range(6):
        cold.add_message(None, MessageRole.USER, f"What are my EC2 costs in month {index}?", provider="aws", tags=["costs"])
        cold.add_message(None, MessageRole.ASSISTANT, f"EC2 costs were {index * 100} USD.", provider="aws")
    results = cold.search_by_content("EC2 costs")
    assert results and results[0].relevance_score > 0.5
    assert cold.messages_since_summary() == 12

    compressed, summary = cold.compress(keep_recent=4)
    assert compressed == 8
    assert "User asked" in summary and "Key findings" in summary
    assert cold.messages[0].is_summary and len(cold.messages) == 5
    assert cold.messages_since_summary() == 4

    # a second compression folds the previous summary in
    compressed_again, summary_again = cold.compress(keep_recent=2)
    assert compressed_again == 2
    assert "Earlier summary" in summary_again
    assert sum(1 for m in cold.messages if m.is_summary) == 1


def test_cold_memory_hydrate_and_retention():
    cold = ColdMemory("sess_1", retention_days=1)
    old = (datetime.now() - timedelta(days=3)).isoformat()
    cold.load_from_records(
        [
            {"id": "a", "role": "user", "content": "old question", "timestamp": old},
            {"id": "b", "role": "assistant", "content": "old answer", "timestamp": old},
            {"id": "c", "role": "system", "content": "summary", "timestamp": old, "is_summary": True},
            {"id": "d", "role": "user", "content": "new question", "timestamp": datetime.now().isoformat()},
        ]
    )
    assert len(cold.messages) == 4
    assert cold.prune_retention_window() == 2  # summaries survive
    assert [m.id for m in cold.messages] == ["c", "d"]


def test_procedural_memory_matches_relevant_skills():
    proc = ProceduralMemory()
    skills = proc.get_relevant_skills("How can I optimize my EC2 costs?", limit=2)
    assert skills and skills[0].id == "aws/ec2_analysis"
    assert proc.assemble_skills_injection().startswith("### Available Skills")
    do_skills = proc.search_skills("digitalocean droplet costs")
    assert any(s.id == "digitalocean/droplet_costs" for s in do_skills)
    forecast = proc.search_skills("forecast Azure spend next month")
    assert any(s.id == "analysis/cost_forecasting" for s in forecast)


def test_deep_memory_roundtrip_and_topics():
    deep = DeepMemory("user_1")
    deep.record_session_start()
    deep.observe_query("Compare my AWS and Azure costs")
    deep.observe_query("Forecast AWS spend next month")
    deep.set_timezone("Europe/London")
    assert "aws" in deep.get_preferred_providers()
    assert "comparison" in deep.get_common_topics() or "forecasting" in deep.get_common_topics()

    restored = DeepMemory.from_dict("user_1", deep.to_dict())
    assert restored.total_queries == 2
    assert restored.get_trait("timezone").value == "Europe/London"
    assert restored.get_preferred_providers() == deep.get_preferred_providers()
    assert "User Profile" in restored.get_user_context_injection()


def test_memory_manager_flow_and_auto_compression():
    mgr = MemoryManager("sess_1", user_id="u1", enable_deep_memory=True, compression_threshold=4, recent_window=2)
    mgr.initialize_session("Test", ["aws", "azure"], "bedrock", {"aws": {"account_id": "111122223333"}})
    prompt, ctx = mgr.process_query("What are my Azure costs?")
    assert "111122223333" in prompt and "Connected" not in prompt  # base prompt is generic here
    assert ctx["provider"] == "azure" and ctx["query_type"] == "costs"
    assert mgr.record_response("Azure costs are 10 USD.", tokens_used=20, analysis_data={"query_type": "costs"}) is None
    mgr.process_query("And AWS?")
    compression = mgr.record_response("AWS costs are 20 USD.", tokens_used=20)
    assert compression and compression["compressed_messages"] == 2
    status = mgr.get_memory_status()
    assert status["cold_memory"]["summaries"] == 1
    assert status["metrics"]["compression_count"] == 1
    assert mgr.deep_memory_state()["total_queries"] == 2


def test_memory_manager_hydrate():
    mgr = MemoryManager("sess_1")
    mgr.initialize_session("Test", ["aws"], "bedrock")
    loaded = mgr.hydrate(
        [
            {"role": "user", "content": "hello", "timestamp": datetime.now().isoformat()},
            {"role": "assistant", "content": "hi", "timestamp": datetime.now().isoformat()},
        ]
    )
    assert loaded == 2
    assert mgr.hot_memory.total_messages == 2
    assert len(mgr.hot_memory.recent_interactions) == 2


def test_detect_query_type():
    assert detect_query_type("forecast next month") == "forecast"
    assert detect_query_type("compare aws vs azure") == "comparison"
    assert detect_query_type("list all my instances") == "inventory"
    assert detect_query_type("how do I save money") == "optimization"
    assert detect_query_type("show the daily trend") == "trend"
    assert detect_query_type("what did I spend") == "costs"
    assert detect_query_type("hello") == "analysis"
