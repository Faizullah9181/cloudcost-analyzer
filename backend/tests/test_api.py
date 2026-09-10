"""HTTP API tests."""

from backend.tests.conftest import SAMPLE_JSON


def test_health_and_providers(client):
    health = client.get("/api/health").json()
    assert health["status"] == "healthy" and health["llm_provider"] == "bedrock"
    providers = client.get("/api/providers").json()
    assert [p["name"] for p in providers["providers"]] == ["aws", "azure", "gcp", "digitalocean"]
    assert "aws_cost_forecast" in providers["providers"][0]["tools"]
    assert client.get("/").json()["sessions"] == "/api/sessions"
    assert len(client.get("/api/suggestions").json()["suggestions"]) > 5


def test_session_crud(client):
    created = client.post(
        "/api/sessions",
        json={"name": "Web", "cloud_providers": ["aws", "gcp"], "connection_context": {"aws": {"account_id": "1"}}},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["cloud_providers"] == {"aws": True, "gcp": True}
    assert body["llm_provider"] == "bedrock" and body["created_at"]

    session_id = body["id"]
    assert client.get(f"/api/sessions/{session_id}").json()["name"] == "Web"
    assert client.get("/api/sessions").json()[0]["id"] == session_id

    patched = client.patch(f"/api/sessions/{session_id}", json={"name": "Renamed", "tags": ["x"]})
    assert patched.json()["name"] == "Renamed" and patched.json()["tags"] == ["x"]

    added = client.post(f"/api/sessions/{session_id}/messages", json={"role": "user", "content": "note"})
    assert added.status_code == 201 and added.json()["message_count"] == 1
    assert client.get(f"/api/sessions/{session_id}/messages").json()["messages"][0]["content"] == "note"

    assert client.post(f"/api/sessions/{session_id}/analysis", json={"analysis": {"total_cost": 5}}).status_code == 200
    assert client.get(f"/api/sessions/{session_id}/analysis").json()["analysis"] == {"total_cost": 5}
    assert client.get(f"/api/sessions/{session_id}/export").json()["messages"][0]["content"] == "note"

    assert client.delete(f"/api/sessions/{session_id}").status_code == 204
    assert client.get("/api/sessions").json() == []
    assert client.get("/api/sessions?include_archived=true").json()[0]["is_active"] is False
    assert client.delete(f"/api/sessions/{session_id}?hard=true").status_code == 204
    assert client.get(f"/api/sessions/{session_id}").status_code == 404


def test_session_validation(client):
    assert client.post("/api/sessions", json={"name": "x", "cloud_providers": ["mars"]}).status_code == 422
    assert client.post("/api/sessions", json={"name": "x", "cloud_providers": {"aws": False}}).status_code == 422
    assert client.post("/api/sessions", json={"cloud_providers": ["aws"]}).status_code == 422


def test_chat_endpoint_runs_agent(client, fake_model):
    fake_model()
    session_id = client.post("/api/sessions", json={"name": "Chat", "cloud_providers": ["aws"]}).json()["id"]

    response = client.post(f"/api/sessions/{session_id}/chat", json={"query": "What are my AWS costs?"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] and body["data"]["total_cost"] == 150.0
    assert body["memory"]["query_type"] == "costs" and body["memory"]["usage"]["total_tokens"] == 15

    messages = client.get(f"/api/sessions/{session_id}/messages").json()
    assert messages["message_count"] == 2 and messages["messages"][1]["analysis"]["total_cost"] == 150.0
    assert client.get(f"/api/sessions/{session_id}/analysis").json()["analysis"]["total_cost"] == 150.0

    memory = client.get(f"/api/sessions/{session_id}/memory").json()
    assert memory["memory"]["cold_memory"]["total_messages"] == 2

    compressed = client.post(f"/api/sessions/{session_id}/compress").json()
    assert compressed["session_id"] == session_id
    assert client.post("/api/sessions/nope/chat", json={"query": "hi"}).status_code == 404


def test_analyze_endpoint_stateless_and_session(client, fake_model):
    fake_model(default_text=SAMPLE_JSON)
    stateless = client.post("/api/analyze", json={"query": "costs?", "connection_context": {"gcp": {"project_id": "p"}}})
    assert stateless.status_code == 200 and stateless.json()["success"]
    assert stateless.json()["data"]["providers"]["aws"]["total"] == 150.0
    assert stateless.json()["session_id"] is None

    session_id = client.post("/api/sessions", json={"name": "S", "cloud_providers": ["aws"]}).json()["id"]
    in_session = client.post("/api/analyze", json={"query": "costs?", "session_id": session_id})
    assert in_session.json()["session_id"] == session_id
    assert client.get(f"/api/sessions/{session_id}").json()["message_count"] == 2
    assert client.get("/api/stats").json()["total_queries"] >= 2
