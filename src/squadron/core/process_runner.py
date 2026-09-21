"""An injected seam for running child processes.

Every code-host call in the 380 initiative goes through ``ProcessRunner`` so
tests can script a host's behavior without an external binary. The protocol is
deliberately narrow: one ``run`` method, a bounded timeout on every call, and
two distinct error types for the two ways a process fails to answer at all.

``run_git`` (``squadron.review.git_utils``) returns ``None`` for both a missing
binary and a timeout. The architecture names "host call exceeded its timeout"
as its own failure mode, so this module keeps them apart.
"""

from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from squadron.core.subprocess_text import TEXT_DECODING

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessResult:
    """The complete outcome of a child process that ran to completion.

    A non-zero ``returncode`` is a result, not an error: the process answered.
    """

    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class ProcessNotFoundError(Exception):
    """The executable could not be invoked at all."""

    def __init__(self, executable: str) -> None:
        super().__init__(f"executable not found: {executable}")
        self.executable = executable


class ProcessCwdNotFoundError(Exception):
    """The requested working directory does not exist.

    Deliberately does not subclass ``ProcessNotFoundError`` — a missing
    working directory is a configuration error, not a code-host condition,
    and callers that catch ``ProcessNotFoundError`` (e.g. ``github_cli.py``)
    must not silently swallow this one too (D3, squadron#112).
    """

    def __init__(self, cwd: str) -> None:
        super().__init__(f"working directory not found: {cwd}")
        self.cwd = cwd


class ProcessTimedOutError(Exception):
    """The process was invoked but did not finish within its bound."""

    def __init__(self, argv: Sequence[str], timeout: float) -> None:
        super().__init__(f"{' '.join(argv)} exceeded {timeout}s")
        self.argv = tuple(argv)
        self.timeout = timeout


class ProcessRunner(Protocol):
    """Runs a child process to completion under a wall-clock bound."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        """Run ``argv``, returning its result even when it exits non-zero.

        Raises ``ProcessNotFoundError`` if the executable is missing,
        ``ProcessCwdNotFoundError`` if ``cwd`` is given and does not exist,
        and ``ProcessTimedOutError`` if it outlives ``timeout``.
        ``ProcessCwdNotFoundError`` signals a configuration error and is
        meant to surface — no caller is obliged to handle it.
        """
        ...


class SubprocessRunner:
    """The production ``ProcessRunner``, backed by :mod:`subprocess`."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        # A replaced environment loses PATH and HOME, which `gh` needs to find
        # its own config and credentials. Merge over os.environ, never replace.
        merged_env = {**os.environ, **env} if env is not None else None
        try:
            completed = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
                **TEXT_DECODING,
                cwd=cwd,
                env=merged_env,
                input=stdin,
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            # Popen raises FileNotFoundError for both a missing executable and a
            # missing cwd (D3, squadron#112) — classify here rather than pre-checking
            # cwd before Popen, which would add a stat to the success path and a
            # check-then-use gap.
            if cwd is not None and not Path(cwd).is_dir():
                _logger.warning("process cwd not found: %s", cwd)
                raise ProcessCwdNotFoundError(cwd) from exc
            _logger.warning("process not found: %s", " ".join(argv))
            raise ProcessNotFoundError(argv[0]) from exc
        except subprocess.TimeoutExpired as exc:
            _logger.warning("process timed out after %ss: %s", timeout, " ".join(argv))
            raise ProcessTimedOutError(argv, timeout) from exc
        return ProcessResult(
            argv=tuple(argv),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
