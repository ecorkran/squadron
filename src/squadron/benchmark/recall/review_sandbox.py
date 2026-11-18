"""The recall review sandbox: head plus its ancestry back to base, nothing later (D7).

Wraps ``HistoryFreeSandbox``, with submodules left unfilled since a review only reads. It
builds the one-commit tree at ``head`` under its own fixed bound, then this module deepens
it through the injected ``ProcessRunner`` so ``sq review code --diff <base>`` finds a merge
base. Fetching a commit brings only its ancestors, so no commit later than ``head`` (and so
no fix) can be present. No ref is made.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from squadron.core.process_runner import ProcessRunner
from squadron.replay.history_free_sandbox import PROCESS_FAILURES, HistoryFreeSandbox, SandboxError

_logger = logging.getLogger(__name__)


@contextmanager
def review_sandbox(
    *,
    repo: Path,
    base: str,
    head: str,
    runner: ProcessRunner,
    root: Path,
    sandbox_id: str,
    fetch_timeout: float,
) -> Iterator[Path]:
    """Yield the sandbox tree; any build failure raises ``SandboxError`` with its reason."""
    if not repo.is_dir():
        raise SandboxError(f"source repo missing: {repo}")
    with HistoryFreeSandbox(
        start_sha=head,
        sandbox_id=sandbox_id,
        repo_root=repo,
        runner=runner,
        root=root,
        allow_unfilled_submodules=True,
    ) as sandbox:
        tree = sandbox.path
        count = _rev_count(runner, repo, base, head, fetch_timeout)
        _run(
            runner,
            [
                "git",
                "-C",
                str(tree),
                "fetch",
                "-q",
                "--depth",
                str(count + 1),
                str(repo.resolve()),
                head,
            ],
            fetch_timeout,
            "fetch",
        )
        _run(
            runner,
            ["git", "-C", str(tree), "rev-parse", "-q", "--verify", f"{base}^{{commit}}"],
            fetch_timeout,
            "base unreachable",
        )
        yield tree


def _rev_count(runner: ProcessRunner, repo: Path, base: str, head: str, timeout: float) -> int:
    stdout = _run(
        runner, ["git", "-C", str(repo), "rev-list", "--count", f"{base}..{head}"], timeout, "rev-list"
    )
    try:
        return int(stdout.strip())
    except ValueError as exc:
        raise SandboxError(f"rev-list gave no count: {stdout.strip()!r}") from exc


def _run(runner: ProcessRunner, argv: Sequence[str], timeout: float, label: str) -> str:
    """Run one D7 command; a timeout, a missing binary or a non-zero exit raises."""
    try:
        result = runner.run(argv, cwd=None, timeout=timeout)
    except PROCESS_FAILURES as exc:
        raise SandboxError(f"{label}: {exc}") from exc
    if result.returncode != 0:
        raise SandboxError(f"{label}: {' '.join(argv)} failed: {result.stderr.strip()[-300:]}")
    return result.stdout
