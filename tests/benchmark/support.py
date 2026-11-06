"""Shared test support for the benchmark suite."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from squadron.core.process_runner import ProcessResult


@dataclass(frozen=True)
class RunnerCall:
    argv: tuple[str, ...]
    cwd: str | None
    timeout: float
    env: Mapping[str, str] | None
    replace_env: bool


Handler = Callable[[RunnerCall], ProcessResult]


class ScriptedRunner:
    """A ``ProcessRunner`` whose results come from a handler; records every call.

    The handler may return a ``ProcessResult`` or raise a process error.
    """

    def __init__(self, handler: Handler) -> None:
        self._handler = handler
        self.calls: list[RunnerCall] = []

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: str | None,
        timeout: float,
        env: Mapping[str, str] | None = None,
        stdin: str | None = None,
        replace_env: bool = False,
    ) -> ProcessResult:
        call = RunnerCall(tuple(argv), cwd, timeout, env, replace_env)
        self.calls.append(call)
        return self._handler(call)


def ok(argv: Sequence[str], stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(tuple(argv), 0, stdout, stderr)


def failed(argv: Sequence[str], code: int = 1, stderr: str = "") -> ProcessResult:
    return ProcessResult(tuple(argv), code, "", stderr)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def git_tree(fixture: str, tmp_path: Path) -> Path:
    """Copy a fixture project into a one-commit git repository and return its path."""
    tree = tmp_path / fixture
    shutil.copytree(FIXTURES_DIR / fixture, tree)
    git = ["git", "-C", str(tree)]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run(
        [*git, "-c", "user.name=t", "-c", "user.email=t@t.invalid", "commit", "-q", "-m", "init"],
        check=True,
    )
    return tree
