"""Start a configured command when a run ends paused (#302).

Called by ``sq run`` after the run's state is saved and the run lock is released, so the
command can take the lock at once. The command is detached in its own session: it
outlives the terminal, ``sq run`` never waits for it, and a failure to start it is one
logged warning that leaves the run's status and exit code alone.
"""

from __future__ import annotations

import logging
import shlex
import subprocess

from squadron.config.keys import ON_PAUSE_COMMAND_KEY
from squadron.config.manager import get_config

_logger = logging.getLogger(__name__)


def start_pause_command(run_id: str, cwd: str) -> bool:
    """Start ``pipeline.on_pause_command`` with *run_id* as its last argument.

    The command runs in *cwd*. Returns ``True`` when it started; ``False`` when the key is
    unset or the command could not be started (logged at WARNING).
    """
    configured = get_config(ON_PAUSE_COMMAND_KEY, cwd=cwd)
    if configured is None:
        return False
    try:
        argv = [*shlex.split(str(configured)), run_id]
        subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        # The run already paused cleanly; a hook that cannot start must not change that.
        _logger.warning(
            "%s %r did not start for run %s: %s", ON_PAUSE_COMMAND_KEY, configured, run_id, exc
        )
        return False
    return True
