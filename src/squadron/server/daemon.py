"""Daemon lifecycle: signal handling and server startup."""

from __future__ import annotations

import asyncio
import os
import signal
from pathlib import Path

import uvicorn

from squadron.logging import get_logger
from squadron.server.app import create_app
from squadron.server.engine import SquadronEngine
from squadron.server.pid import (
    DaemonConfig,
    is_daemon_running,
    read_pid_file,
    remove_pid_file,
    write_pid_file,
)

logger = get_logger(__name__)

__all__ = [
    "DaemonConfig",
    "is_daemon_running",
    "read_pid_file",
    "remove_pid_file",
    "start_server",
    "write_pid_file",
]


def remove_socket_file(path: str) -> None:
    """Remove Unix socket file if it exists."""
    sock_path = Path(path)
    if sock_path.exists():
        sock_path.unlink()


async def start_server(engine: SquadronEngine, config: DaemonConfig) -> None:
    """Start dual-transport daemon: Unix socket + HTTP on localhost.

    Runs both uvicorn servers in a TaskGroup. If either fails to bind,
    the other is cancelled automatically. Handles SIGTERM/SIGINT for
    graceful shutdown.
    """
    app = create_app(engine)

    # Clean up stale socket file before binding
    remove_socket_file(config.socket_path)
    # Ensure socket directory exists
    Path(config.socket_path).parent.mkdir(parents=True, exist_ok=True)

    uds_config = uvicorn.Config(app, uds=config.socket_path, log_level="info")
    http_config = uvicorn.Config(app, host="127.0.0.1", port=config.port, log_level="info")

    uds_server = uvicorn.Server(uds_config)
    http_server = uvicorn.Server(http_config)

    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("daemon.signal: initiating graceful shutdown")
        shutdown_event.set()
        uds_server.should_exit = True
        http_server.should_exit = True

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    write_pid_file(config.pid_path)
    logger.info(
        "daemon.start: socket=%s http=127.0.0.1:%d pid=%d",
        config.socket_path,
        config.port,
        os.getpid(),
    )

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(uds_server.serve())
            tg.create_task(http_server.serve())
    finally:
        await engine.shutdown_all()
        remove_pid_file(config.pid_path)
        remove_socket_file(config.socket_path)
        logger.info("daemon.stop: cleanup complete")
