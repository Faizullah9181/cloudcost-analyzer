"""Tests for the session store (persistence regressions)."""

import pytest

from backend.services.session_store import SessionNotFound, SessionStore


def test_messages_persist_across_sessions(store):
    session = store.create_session("Persist", ["aws", "azure"], llm_provider="bedrock", user_id="u1")
    store.add_message(session, "user", "hello", tags=["costs"])
    store.add_message(session, "assistant", "hi", tokens_used=12, analysis={"total_cost": 1})
    store.commit()

    with SessionStore() as other:
        reloaded = other.require_session(session.id)
        assert reloaded.message_count == 2
        assert reloaded.context_tokens == 12
        assert [m.role for m in reloaded.messages] == ["user", "assistant"]
        assert reloaded.messages[1].analysis == {"total_cost": 1}
        assert reloaded.enabled_providers() == ["aws", "azure"]
        assert other.get_session(session.id[:8]).id == session.id


def test_archive_list_and_delete(store):
    first = store.create_session("A", ["aws"])
    second = store.create_session("B", ["gcp"])
    assert [s.id for s in store.list_sessions()] == [second.id, first.id]
    store.archive_session(first.id)
    assert [s.id for s in store.list_sessions()] == [second.id]
    assert len(store.list_sessions(include_archived=True)) == 2
    store.delete_session(second.id)
    with pytest.raises(SessionNotFound):
        store.require_session(second.id)
    assert store.count_sessions(include_archived=True) == 1


def test_user_profile_roundtrip(store):
    assert store.get_user_profile("u1") is None
    store.save_user_profile("u1", {"total_queries": 3}, commit=True)
    store.save_user_profile("u1", {"total_queries": 4}, commit=True)
    assert store.get_user_profile("u1") == {"total_queries": 4}


def test_update_session_merges_context(store):
    session = store.create_session("C", {"aws": True}, connection_context={"aws": {"account_id": "1"}})
    store.update_session(session, name="Renamed", connection_context={"aws": {"region": "eu-west-1"}}, tags=["prod"])
    assert session.name == "Renamed"
    assert session.connection_context == {"aws": {"account_id": "1", "region": "eu-west-1"}}
    assert session.tags == ["prod"]
