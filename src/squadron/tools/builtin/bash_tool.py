"""The ``bash`` tool.

Split out of the former single-module ``builtin.py`` (slice 266, T23). Pure move — no
logic changed."""

from __future__ import annotations

import asyncio
import logging
import os
import signal

from squadron.tools import limits
from squadron.tools.builtin._shared import BASH_NAME, error, guarded, require_str, truncate
from squadron.tools.models import JailSpec, ToolDescriptor, ToolExecutor, ToolResult
from squadron.tools.registry import register

_logger = logging.getLogger(__name__)


BASH_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Shell command to run, anchored to the working directory.",
        }
    },
    "required": ["command"],
}


async def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    """Kill *proc*'s whole process group and reap it, so no zombie or orphan is left."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        # The process exited on its own between the timeout firing and this kill. Nothing to
        # signal; the wait below still reaps it.
        pass
    await proc.wait()


def _bash_factory(spec: JailSpec) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            command = require_str(args, "command")

            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=spec.root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Required so the timeout path can kill the whole group, not just the shell.
                start_new_session=True,
            )

            # Read the limit at call time (module attribute), never captured at import, so a
            # lowered limit takes effect for the very next call.
            timeout = limits.BASH_TIMEOUT_S
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                await _kill_process_group(proc)
                _logger.warning(
                    "%s: command timed out after %ss and was killed: %s",
                    BASH_NAME,
                    timeout,
                    command,
                )
                return ToolResult(
                    content=(f"Error: command timed out after {timeout}s and was killed: {command}"),
                    is_error=True,
                )

            limit = limits.MAX_OUTPUT_BYTES
            stdout = truncate(stdout_bytes, limit, "stdout")
            stderr = truncate(stderr_bytes, limit, "stderr")
            body = f"stdout:\n{stdout}\nstderr:\n{stderr}"
            exit_code = proc.returncode

            if exit_code != 0:
                # The model needs the captured output to react, so it travels with the error.
                return error(BASH_NAME, f"command exited with code {exit_code}.\n{body}")
            return ToolResult(content=body)

        return await guarded(BASH_NAME, run)

    return execute


BASH = ToolDescriptor(
    name=BASH_NAME,
    description=(
        "Run a shell command in the working directory. Returns labeled stdout and stderr; "
        "long output is truncated with a visible marker and long-running commands are killed."
    ),
    parameters=BASH_PARAMETERS,
    factory=_bash_factory,
)

register(BASH)
