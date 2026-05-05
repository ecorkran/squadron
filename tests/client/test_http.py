"""Tests for DaemonClient — verifies HTTP calls and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from squadron.client.http import DaemonClient, DaemonNotRunningError


@pytest.fixture
def client() -> DaemonClient:
    """DaemonClient with no real socket (will use HTTP base_url)."""
    return DaemonClient(
        socket_path="/nonexistent/daemon.sock",
        base_url="http://127.0.0.1:7862",
    )


def _mock_response(status_code: int = 200, json_data: dict | list | None = None) -> httpx.Response:
    """Build a mock httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://test"),
    )


async def test_spawn_sends_post(client: DaemonClient):
    """Verify POST to /agents/ with correct body."""
    body = {"name": "a", "agent_type": "api", "provider": "mock"}
    mock_resp = _mock_response(
        200, {"name": "a", "agent_type": "api", "provider": "mock", "state": "idle"}
    )
    with patch.object(
        httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_req:
        result = await client.spawn(body)
        mock_req.assert_called_once()
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert call_args[0][1] == "/agents/"
        assert result["name"] == "a"


async def test_list_agents(client: DaemonClient):
    """Verify GET to /agents."""
    mock_resp = _mock_response(200, [])
    with patch.object(
        httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_req:
        result = await client.list_agents()
        call_args = mock_req.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/agents/"
        assert result == []


async def test_send_message(client: DaemonClient):
    """Verify POST to /agents/{name}/message."""
    mock_resp = _mock_response(200, {"messages": [{"content": "hi", "sender": "a"}]})
    with patch.object(
        httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_req:
        result = await client.send_message("agent1", "hello")
        call_args = mock_req.call_args
        assert call_args[0][0] == "POST"
        assert "/agent1/message" in call_args[0][1]
        assert result[0]["content"] == "hi"


async def test_get_history(client: DaemonClient):
    """Verify GET to /agents/{name}/history."""
    mock_resp = _mock_response(200, {"messages": []})
    with patch.object(
        httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_req:
        result = await client.get_history("agent1")
        call_args = mock_req.call_args
        assert call_args[0][0] == "GET"
        assert "/agent1/history" in call_args[0][1]
        assert result == []


async def test_shutdown_agent(client: DaemonClient):
    """Verify DELETE to /agents/{name}."""
    mock_resp = _mock_response(204)
    with patch.object(
        httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_req:
        await client.shutdown_agent("agent1")
        call_args = mock_req.call_args
        assert call_args[0][0] == "DELETE"
        assert "/agent1" in call_args[0][1]


async def test_connection_error_raises_daemon_not_running(
    client: DaemonClient,
):
    """ConnectError → DaemonNotRunningError."""
    with patch.object(
        httpx.AsyncClient,
        "request",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("refused"),
    ):
        with pytest.raises(DaemonNotRunningError):
            await client.health()


async def test_health(client: DaemonClient):
    """Verify GET to /health."""
    mock_resp = _mock_response(200, {"status": "ok", "agents": 0})
    with patch.object(
        httpx.AsyncClient, "request", new_callable=AsyncMock, return_value=mock_resp
    ) as mock_req:
        result = await client.health()
        call_args = mock_req.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1] == "/health"
        assert result["status"] == "ok"
