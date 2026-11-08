"""Shared test support for the benchmark suite."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    # Module-scoped fixtures call this before the per-test hermetic fixture has
    # replaced the host's git config, so ignore the host's config explicitly.
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True, env=env)
    subprocess.run([*git, "add", "-A"], check=True, env=env)
    subprocess.run(
        [*git, "-c", "user.name=t", "-c", "user.email=t@t.invalid", "commit", "-q", "-m", "init"],
        check=True,
        env=env,
    )
    return tree


@dataclass(frozen=True)
class ClosingCommitRepo:
    """A repository whose commits cover every discovery outcome; ``shas`` maps name to sha."""

    path: Path
    shas: dict[str, str]


#: (name, commit message) in history order. Messages without a closing keyword are
#: here too: they must not become candidates or rejections.
CLOSING_COMMIT_MESSAGES: tuple[tuple[str, str], ...] = (
    ("init", "init"),
    ("suffix_only", "fix: handle empty input (#283)"),
    ("body_line", "feat: add thing\n\nSome text.\nFixes #10"),
    ("two_issues", "fix: two at once\n\nCloses #11 and resolves #12"),
    ("split_one", "fix: part one\n\nFixes #13"),
    ("split_two", "fix: part two\n\nFixes #13"),
    ("same_twice", "fix: same twice\n\nFixes #14\nfixed #14"),
    ("cross_repo", "fix: cross\n\nCloses other/repo#15"),
    ("colon_form", "fix: colon form\n\nFixes: #17"),
    ("tidy", "chore: tidy"),
)


def hermetic_git(path: Path, *args: str) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    result = subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=t", "-c", "user.email=t@t.invalid", *args],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def closing_commit_repo(tmp_path: Path) -> ClosingCommitRepo:
    """Build the discovery repository: linear history, then a side branch merged with a keyword."""
    path = tmp_path / "closing_commit_repo"
    path.mkdir()
    hermetic_git(path, "init", "-q", "-b", "main")
    shas: dict[str, str] = {}
    for name, message in CLOSING_COMMIT_MESSAGES:
        hermetic_git(path, "commit", "-q", "--allow-empty", "-m", message)
        shas[name] = hermetic_git(path, "rev-parse", "HEAD")
    hermetic_git(path, "checkout", "-q", "-b", "side")
    hermetic_git(path, "commit", "-q", "--allow-empty", "-m", "side work")
    hermetic_git(path, "checkout", "-q", "main")
    hermetic_git(path, "merge", "-q", "--no-ff", "-m", "Merge side\n\nFixes #16", "side")
    shas["merge"] = hermetic_git(path, "rev-parse", "HEAD")
    return ClosingCommitRepo(path=path, shas=shas)


CHANGES_DIR = FIXTURES_DIR / "fixfair_changes"
DELETED_LIST = "deleted.txt"
FIX_COMMIT_BODY = "Fixes #1"


@dataclass(frozen=True)
class FixHistory:
    """A repository with a base commit and the commit a scenario applies on top of it."""

    repo: Path
    parent_sha: str
    fix_sha: str


def fix_history(fixture: str, scenario: str, tmp_path: Path) -> FixHistory:
    """Commit 1 is the fixture project; commit 2 applies ``fixfair_changes/<scenario>/``.

    Each file under the scenario directory is written at its relative path; paths listed
    in ``deleted.txt`` are removed. Commit 2's message carries a closing keyword.
    """
    repo = tmp_path / f"{fixture}-{scenario}"
    shutil.copytree(FIXTURES_DIR / fixture, repo)
    hermetic_git(repo, "init", "-q", "-b", "main")
    hermetic_git(repo, "add", "-A")
    hermetic_git(repo, "commit", "-q", "-m", "base")
    parent_sha = hermetic_git(repo, "rev-parse", "HEAD")

    scenario_dir = CHANGES_DIR / scenario
    for source in sorted(scenario_dir.rglob("*")):
        if not source.is_file() or source.name == DELETED_LIST:
            continue
        destination = repo / source.relative_to(scenario_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    deleted = scenario_dir / DELETED_LIST
    if deleted.exists():
        for line in deleted.read_text(encoding="utf-8").splitlines():
            if line.strip():
                (repo / line.strip()).unlink()
    hermetic_git(repo, "add", "-A")
    hermetic_git(repo, "commit", "-q", "-m", f"fix: apply {scenario}", "-m", FIX_COMMIT_BODY)
    return FixHistory(repo=repo, parent_sha=parent_sha, fix_sha=hermetic_git(repo, "rev-parse", "HEAD"))


TRACE_CONFIG_ENV = "SQUADRON_FIXCASE_TRACE_CONFIG"


@dataclass(frozen=True)
class TracePluginRun:
    """One pytest run with the trace plugin loaded."""

    output: dict[str, Any]
    returncode: int
    stderr: str


def trace_plugin_dir() -> Path:
    import squadron.benchmark as benchmark_package

    return Path(benchmark_package.__file__).parent / "pytest_trace"


def run_trace_plugin(
    tree: Path,
    work_dir: Path,
    mode: str,
    pytest_args: Sequence[str] = (),
    test_side_files: Sequence[str] | None = None,
) -> TracePluginRun:
    """Run the harness's pytest over ``tree`` (no venv) with the trace plugin and read its output.

    ``test_side_files`` defaults to every tracked ``.py`` file under ``tests/``.
    """
    if test_side_files is None:
        listing = hermetic_git(tree, "ls-files", "tests")
        test_side_files = [line for line in listing.splitlines() if line.endswith(".py")]
    work_dir.mkdir(parents=True, exist_ok=True)
    output = work_dir / "trace_output.json"
    config = work_dir / "trace_config.json"
    config.write_text(
        json.dumps(
            {
                "mode": mode,
                "tree": str(tree),
                "test_side_files": list(test_side_files),
                "output": str(output),
            }
        ),
        encoding="utf-8",
    )
    env = {**os.environ, "PYTHONPATH": str(trace_plugin_dir()), TRACE_CONFIG_ENV: str(config)}
    argv = [sys.executable, "-m", "pytest", "-p", "squadron_fixcase_trace", "-p", "no:cacheprovider"]
    if mode == "collect":
        argv += ["--collect-only", "-q"]
    result = subprocess.run(
        [*argv, *pytest_args], cwd=tree, env=env, capture_output=True, text=True, check=False
    )
    parsed: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    return TracePluginRun(output=parsed, returncode=result.returncode, stderr=result.stderr)
