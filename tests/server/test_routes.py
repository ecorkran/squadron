"""Tests for daemon API routes via httpx AsyncClient + ASGITransport."""

from __future__ import annotations

from typing import Any

import httpx


def _spawn_body(name: str, provider: str = "mock", model: str = "m") -> dict[str, Any]:
    """Build a spawn request body."""
    return {
        "name": name,
        "agent_type": "api",
        "provider": provider,
        "model": model,
    }


async def _spawn(client: httpx.AsyncClient, name: str) -> httpx.Response:
    """Spawn a mock agent via the API."""
    return await client.post("/agents/", json=_spawn_body(name))


async def test_health(async_client: httpx.AsyncClient):
    """GET /health returns 200 with status ok and agent count."""
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["agents"] == 0


async def test_spawn_agent(async_client: httpx.AsyncClient):
    """POST /agents with valid body returns 200 with agent info."""
    resp = await _spawn(async_client, "test-agent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-agent"
    assert data["provider"] == "mock"


async def test_list_agents(async_client: httpx.AsyncClient):
    """Spawn two, GET /agents returns both."""
    await _spawn(async_client, "a")
    await _spawn(async_client, "b")
    resp = await async_client.get("/agents/")
    assert resp.status_code == 200
    names = [a["name"] for a in resp.json()]
    assert "a" in names
    assert "b" in names


async def test_get_agent(async_client: httpx.AsyncClient):
    """Spawn one, GET /agents/{name} returns info."""
    await _spawn(async_client, "x")
    resp = await async_client.get("/agents/x")
    assert resp.status_code == 200
    assert resp.json()["name"] == "x"


async def test_get_agent_not_found(async_client: httpx.AsyncClient):
    """GET /agents/nonexistent returns 404."""
    resp = await async_client.get("/agents/nonexistent")
    assert resp.status_code == 404


async def test_send_message(async_client: httpx.AsyncClient):
    """Spawn then POST message returns response messages."""
    await _spawn(async_client, "agent1")
    resp = await async_client.post("/agents/agent1/message", json={"content": "hello"})
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) >= 1
    assert messages[0]["content"] == "mock response"


async def test_get_history(async_client: httpx.AsyncClient):
    """Spawn, message, GET history returns conversation."""
    await _spawn(async_client, "agent1")
    await async_client.post("/agents/agent1/message", json={"content": "hello"})
    resp = await async_client.get("/agents/agent1/history")
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) >= 2
    assert messages[0]["sender"] == "human"
    assert messages[1]["sender"] == "agent1"


async def test_shutdown_agent(async_client: httpx.AsyncClient):
    """Spawn then DELETE /agents/{name} returns 204."""
    await _spawn(async_client, "agent1")
    resp = await async_client.delete("/agents/agent1")
    assert resp.status_code == 204


async def test_shutdown_all(async_client: httpx.AsyncClient):
    """Spawn two, DELETE /agents returns shutdown report."""
    await _spawn(async_client, "a")
    await _spawn(async_client, "b")
    resp = await async_client.delete("/agents/")
    assert resp.status_code == 200
    data = resp.json()
    assert "a" in data["succeeded"]
    assert "b" in data["succeeded"]


async def test_spawn_credentials_forwarded(async_client: httpx.AsyncClient, mock_provider: Any) -> None:
    """Credentials in SpawnRequest reach AgentConfig (regression: profile bug)."""
    last_config: list = []
    original_create = mock_provider.create_agent

    async def capturing_create(config):  # type: ignore[no-untyped-def]
        last_config.append(config)
        return await original_create(config)

    mock_provider.create_agent = capturing_create  # type: ignore[method-assign]

    resp = await async_client.post(
        "/agents/",
        json={
            "name": "cred-test",
            "agent_type": "api",
            "provider": "mock",
            "model": "m",
            "credentials": {"api_key_env": "OPENROUTER_API_KEY", "x": "y"},
        },
    )
    assert resp.status_code == 200
    assert last_config, "create_agent was never called"
    config = last_config[0]
    assert config.credentials == {"api_key_env": "OPENROUTER_API_KEY", "x": "y"}
