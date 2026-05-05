"""serve command — start, stop, or check status of the daemon."""

from __future__ import annotations

import asyncio
import os
import signal

import typer
from rich import print as rprint

from squadron.server.daemon import (
    DaemonConfig,
    is_daemon_running,
    read_pid_file,
    start_server,
)
from squadron.server.engine import SquadronEngine


def serve(
    stop: bool = typer.Option(False, "--stop", help="Stop a running daemon"),
    status: bool = typer.Option(False, "--status", help="Check daemon status"),
    port: int | None = typer.Option(None, "--port", help="Override HTTP port (default: 7862)"),
) -> None:
    """Start the squadron daemon, or manage a running one."""
    config = DaemonConfig()
    if port is not None:
        config.port = port

    if status:
        _show_status(config)
        return

    if stop:
        _stop_daemon(config)
        return

    _start_daemon(config)


def _show_status(config: DaemonConfig) -> None:
    """Print daemon status and exit."""
    if is_daemon_running(config.pid_path):
        pid = read_pid_file(config.pid_path)
        rprint(f"[green]Daemon is running (PID {pid})[/green]")
    else:
        rprint("[yellow]Daemon is not running.[/yellow]")


def _stop_daemon(config: DaemonConfig) -> None:
    """Send SIGTERM to a running daemon."""
    pid = read_pid_file(config.pid_path)
    if pid is None or not is_daemon_running(config.pid_path):
        rprint("[red]Error: Daemon is not running.[/red]")
        raise typer.Exit(code=1)

    os.kill(pid, signal.SIGTERM)
    rprint(f"[green]Sent shutdown signal to daemon (PID {pid}).[/green]")


def _start_daemon(config: DaemonConfig) -> None:
    """Start the daemon process."""
    if is_daemon_running(config.pid_path):
        pid = read_pid_file(config.pid_path)
        rprint(f"[red]Error: Daemon is already running (PID {pid}). Use --stop first.[/red]")
        raise typer.Exit(code=1)

    engine = SquadronEngine()
    rprint(f"[green]Starting daemon on 127.0.0.1:{config.port} and {config.socket_path}[/green]")
    asyncio.run(start_server(engine, config))
