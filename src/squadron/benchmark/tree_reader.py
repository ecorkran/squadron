"""Reading files of a git commit through ``ProcessRunner`` (slice 425 API Contracts).

``TreeReader`` is what a grading adapter needs of a commit: one file's bytes and the list
of tracked paths. ``GitTreeReader`` answers it with ``git show`` and ``git ls-tree`` in the
user's checkout, so the start and reference trees are read without being checked out.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NoReturn, Protocol

from squadron.benchmark.replay_outcome import STDERR_TAIL_CHARS
from squadron.codehost.git_refs import GIT_QUERY_TIMEOUT_SECONDS
from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessRunner,
    ProcessTimedOutError,
)

PROCESS_FAILURES = (ProcessNotFoundError, ProcessCwdNotFoundError, ProcessTimedOutError)

_logger = logging.getLogger(__name__)
#: What ``errors="replace"`` decoding leaves where a byte was not valid UTF-8.
_REPLACEMENT_CHARACTER = "\N{REPLACEMENT CHARACTER}"


class TreeReader(Protocol):
    """Reads one commit's tree."""

    def read(self, path: str) -> bytes:
        """The file's content at the commit; raises when there is no such file."""
        ...

    def list_paths(self) -> tuple[str, ...]:
        """Every tracked path at the commit."""
        ...


class TreeReadError(Exception):
    """A git read of a commit's tree failed; carries the command's stderr tail."""

    def __init__(self, action: str, detail: str) -> None:
        super().__init__(f"{action}: {detail}")
        self.action = action
        self.detail = detail


class GitTreeReader:
    """A ``TreeReader`` over one commit of a repository, read with git.

    ``ProcessRunner`` returns decoded text, so content is UTF-8 with universal newlines.
    A file that is not valid UTF-8 raises instead of being read with replaced bytes. A CRLF
    file therefore reads back with LF endings (#334).
    """

    def __init__(self, runner: ProcessRunner, repo_root: Path, sha: str) -> None:
        self._runner = runner
        self._repo_root = repo_root
        self._sha = sha

    def read(self, path: str) -> bytes:
        action = f"git show {self._sha}:{path}"
        stdout = self._git(action, ["show", f"{self._sha}:{path}"])
        if _REPLACEMENT_CHARACTER in stdout:
            self._fail(action, "content is not valid UTF-8 text")
        return stdout.encode("utf-8")

    def list_paths(self) -> tuple[str, ...]:
        action = f"git ls-tree {self._sha}"
        stdout = self._git(action, ["ls-tree", "-r", "-z", "--name-only", self._sha])
        return tuple(path for path in stdout.split("\0") if path)

    def _git(self, action: str, args: list[str]) -> str:
        try:
            result = self._runner.run(
                ["git", *args], cwd=str(self._repo_root), timeout=GIT_QUERY_TIMEOUT_SECONDS
            )
        except PROCESS_FAILURES as exc:
            # Logged by _fail; a hung read, a vanished checkout or a git that cannot
            # start all leave the commit unreadable, which grade_one records as an
            # absence like any other read failure.
            self._fail(action, str(exc))
        if result.returncode != 0:
            self._fail(action, result.stderr.strip()[-STDERR_TAIL_CHARS:])
        return result.stdout

    @staticmethod
    def _fail(action: str, detail: str) -> NoReturn:
        _logger.error("%s failed: %s", action, detail)
        raise TreeReadError(action, detail)
