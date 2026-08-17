"""HTTP client for CLI-to-daemon communication via Unix socket or HTTP."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

_DEFAULT_SOCKET = str(Path.home() / ".squadron" / "daemon.sock")
_DEFAULT_BASE_URL = "http://127.0.0.1:7862"
_TIMEOUT = 300.0


class DaemonNotRunningError(Exception):
    """Raised when the CLI cannot connect to the daemon."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or "Daemon is not running. Start it with: sq serve")


class DaemonClient:
    """Async HTTP client for the squadron daemon.

    Uses Unix domain socket by default, with HTTP fallback.
    """

    def __init__(
        self,
        socket_path: str = _DEFAULT_SOCKET,
        base_url: str = _DEFAULT_BASE_URL,
    ) -> None:
        self._socket_path = socket_path
        self._base_url = base_url
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily create the httpx client, preferring Unix socket."""
        if self._client is not None:
            return self._client

        if await asyncio.to_thread(Path(self._socket_path).exists):
            transport = httpx.AsyncHTTPTransport(uds=self._socket_path)
            self._client = httpx.AsyncClient(
                transport=transport,
                base_url="http://localhost",
                timeout=_TIMEOUT,
            )
        else:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=_TIMEOUT,
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request, translating connection errors."""
        client = await self._get_client()
        try:
            resp = await client.request(method, path, **kwargs)
        except httpx.ConnectError as exc:
            raise DaemonNotRunningError() from exc

        if resp.status_code >= 400:
            detail = "Unknown error"
            try:
                body = resp.json()
                detail = body.get("detail", str(body))
            except (json.JSONDecodeError, AttributeError):
                # Error body is either not JSON, or JSON that isn't a dict
                # (body.get raises AttributeError on e.g. a list/scalar).
                # Fall back to the raw text for the error message.
                detail = resp.text or f"HTTP {resp.status_code}"
            if resp.status_code == 404:
                from squadron.core.agent_registry import (
                    AgentNotFoundError,
                )

                raise AgentNotFoundError(detail)
            raise httpx.HTTPStatusError(
                detail,
                request=resp.request,
                response=resp,
            )
        return resp

    async def spawn(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """POST /agents — spawn a new agent."""
        resp = await self._request("POST", "/agents/", json=request_data)
        return resp.json()  # type: ignore[no-any-return]

    async def list_agents(
        self,
        state: str | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        """GET /agents — list active agents."""
        params: dict[str, str] = {}
        if state:
            params["state"] = state
        if provider:
            params["provider"] = provider
        resp = await self._request("GET", "/agents/", params=params)
        return resp.json()  # type: ignore[no-any-return]

    async def send_message(self, agent_name: str, content: str) -> list[dict[str, Any]]:
        """POST /agents/{name}/message — send a message."""
        resp = await self._request(
            "POST",
            f"/agents/{agent_name}/message",
            json={"content": content},
        )
        return resp.json()["messages"]  # type: ignore[no-any-return]

    async def get_history(self, agent_name: str, limit: int | None = None) -> list[dict[str, Any]]:
        """GET /agents/{name}/history — get conversation history."""
        params: dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        resp = await self._request("GET", f"/agents/{agent_name}/history", params=params)
        return resp.json()["messages"]  # type: ignore[no-any-return]

    async def shutdown_agent(self, name: str) -> None:
        """DELETE /agents/{name} — shut down a single agent."""
        await self._request("DELETE", f"/agents/{name}")

    async def shutdown_all(self) -> dict[str, Any]:
        """DELETE /agents — shut down all agents."""
        resp = await self._request("DELETE", "/agents/")
        return resp.json()  # type: ignore[no-any-return]

    async def health(self) -> dict[str, Any]:
        """GET /health — daemon health check."""
        resp = await self._request("GET", "/health")
        return resp.json()  # type: ignore[no-any-return]

    async def request_shutdown(self) -> None:
        """POST /shutdown — request daemon shutdown."""
        await self._request("POST", "/shutdown")

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
