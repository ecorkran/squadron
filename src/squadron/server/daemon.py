"""Daemon lifecycle: PID management, signal handling, and server startup."""

from __future__ import annotations

import asyncio
import errno
import os
import signal
from dataclasses import dataclass, field
from pathlib import Path

import uvicorn

from squadron.logging import get_logger
from squadron.server.app import create_app
from squadron.server.engine import SquadronEngine

logger = get_logger(__name__)

_DEFAULT_DIR = Path.home() / ".squadron"


@dataclass
class DaemonConfig:
    """Configuration for the daemon process."""

    socket_path: str = field(default_factory=lambda: str(_DEFAULT_DIR / "daemon.sock"))
    port: int = 7862
    pid_path: str = field(default_factory=lambda: str(_DEFAULT_DIR / "daemon.pid"))


def write_pid_file(path: str) -> None:
    """Write the current process PID to a file, creating parents if needed."""
    pid_path = Path(path)
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()))


def remove_pid_file(path: str) -> None:
    """Remove PID file if it exists."""
    pid_path = Path(path)
    if pid_path.exists():
        pid_path.unlink()


def read_pid_file(path: str) -> int | None:
    """Read PID from file. Returns None if file is missing or invalid."""
    pid_path = Path(path)
    if not pid_path.exists():
        return None
    try:
        return int(pid_path.read_text().strip())
    except (ValueError, OSError):
        return None


def is_daemon_running(pid_path: str) -> bool:
    """Check if a daemon process is alive based on its PID file.

    Handles stale PID files: if the process is gone, removes the
    stale file and returns False.
    """
    pid = read_pid_file(pid_path)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            # Stale PID file — process is gone
            remove_pid_file(pid_path)
            return False
        if exc.errno == errno.EPERM:
            # Process exists but we can't signal it (different user)
            return True
        raise


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
