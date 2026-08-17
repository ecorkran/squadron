"""spawn command — create an agent via the daemon."""

from __future__ import annotations

import asyncio
from typing import Any

import typer
from rich import print as rprint

from squadron.client.http import DaemonClient, DaemonNotRunningError
from squadron.config.manager import get_config
from squadron.providers.profiles import get_profile


def _resolve_spawn_model(flag: str | None) -> str | None:
    """Resolve model for spawn: CLI flag → config → None."""
    if flag is not None:
        return flag
    config_val = get_config("default_model")
    return config_val if isinstance(config_val, str) else None


def _resolve_profile(
    profile_name: str,
    cli_provider: str | None,
    cli_base_url: str | None,
) -> dict[str, Any]:
    """Load a profile and return fields to merge into request_data.

    CLI flags take precedence over profile fields when explicitly set.
    """
    profile = get_profile(profile_name)
    credentials: dict[str, Any] = {}
    if profile.api_key_env is not None:
        credentials["api_key_env"] = profile.api_key_env
    if profile.default_headers is not None:
        credentials["default_headers"] = profile.default_headers
    return {
        "agent_type": "api",
        "provider": cli_provider or profile.provider,
        "base_url": cli_base_url or profile.base_url,
        "credentials": credentials,
    }


def spawn(
    name: str = typer.Option(..., help="Unique agent name"),
    agent_type: str = typer.Option("sdk", "--type", help="Agent type (default: sdk)"),
    provider: str | None = typer.Option(None, "--provider", help="Provider name (defaults to --type)"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory (SDK agents)"),
    system_prompt: str | None = typer.Option(None, "--system-prompt", help="System prompt override"),
    permission_mode: str | None = typer.Option(None, "--permission-mode", help="SDK permission mode"),
    model: str | None = typer.Option(None, "--model", help="Model override (e.g. opus, sonnet)"),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="Base URL for OpenAI-compatible endpoints",
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Provider profile (e.g. openrouter, local, gemini)",
    ),
) -> None:
    """Spawn a new agent."""
    resolved_model = _resolve_spawn_model(model)
    request_data: dict[str, Any] = {
        "name": name,
        "agent_type": agent_type,
        "provider": provider or agent_type,
        "model": resolved_model,
        "instructions": system_prompt,
        "base_url": base_url,
        "cwd": cwd,
    }

    if profile is not None:
        try:
            profile_data = _resolve_profile(profile, provider, base_url)
        except KeyError as exc:
            rprint(f"[red]Error: {exc}[/red]")
            raise typer.Exit(code=1) from None
        request_data.update(profile_data)

    asyncio.run(_spawn(request_data))


async def _spawn(request_data: dict[str, Any]) -> None:
    client = DaemonClient()
    try:
        result = await client.spawn(request_data)
        rprint(
            f"[green]Agent '{result['name']}' spawned"
            f" (type: {result['agent_type']},"
            f" provider: {result['provider']})[/green]"
        )
    except DaemonNotRunningError:
        rprint("[red]Error: Daemon is not running. Start it with: sq serve[/red]")
        raise typer.Exit(code=1) from None
    except Exception as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from None
    finally:
        await client.close()
