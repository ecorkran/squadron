"""The recall review sandbox holds head and base, never the fix (slice 430 D7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.recall.review_sandbox import review_sandbox
from squadron.core.process_runner import (
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
    SubprocessRunner,
)
from squadron.replay.history_free_sandbox import SandboxError
from tests.benchmark.recall.fixtures.bug_repo.build import BuiltBugRepo
from tests.benchmark.support import RunnerCall, ScriptedRunner, failed
from tests.conftest import run_test_git


def _open(bug_repo: BuiltBugRepo, tmp_path: Path, runner: ProcessRunner, **override: object):  # noqa: ANN202
    args: dict[str, object] = {
        "repo": bug_repo.repo,
        "base": bug_repo.base,
        "head": bug_repo.head,
        "runner": runner,
        "root": tmp_path / "bench",
        "sandbox_id": "recall-test",
        "fetch_timeout": 30.0,
    }
    args.update(override)
    return review_sandbox(**args)  # pyright: ignore[reportArgumentType]


def test_tree_has_head_and_base_not_fix(bug_repo: BuiltBugRepo, tmp_path: Path) -> None:
    with _open(bug_repo, tmp_path, SubprocessRunner()) as tree:
        assert run_test_git(tree, "rev-parse", "HEAD").strip() == bug_repo.head
        run_test_git(tree, "cat-file", "-e", f"{bug_repo.base}^{{commit}}")
        with pytest.raises(Exception):  # noqa: B017 - git exits non-zero for a missing object
            run_test_git(tree, "cat-file", "-e", f"{bug_repo.fix}^{{commit}}")
        assert run_test_git(tree, "for-each-ref").strip() == ""
        merge_base = run_test_git(tree, "merge-base", bug_repo.base, "HEAD").strip()
        assert merge_base == bug_repo.base
    assert not tree.exists()


def test_missing_repo(bug_repo: BuiltBugRepo, tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="source repo missing"):
        with _open(bug_repo, tmp_path, SubprocessRunner(), repo=tmp_path / "gone"):
            pass


def _failing(step: str, outcome: str):  # noqa: ANN202
    real = SubprocessRunner()

    def handler(call: RunnerCall) -> ProcessResult:
        if step in call.argv:
            if outcome == "timeout":
                raise ProcessTimedOutError(call.argv, call.timeout)
            return failed(call.argv, stderr=f"{step} broke")
        return real.run(call.argv, cwd=call.cwd, timeout=call.timeout)

    return ScriptedRunner(handler)


@pytest.mark.parametrize(
    ("step", "outcome", "reason"),
    [
        ("init", "fail", "init -q"),
        ("fetch", "fail", "fetch"),
        ("fetch", "timeout", "exceeded"),
        ("rev-list", "fail", "rev-list"),
    ],
)
def test_failures_raise_with_reason(
    bug_repo: BuiltBugRepo, tmp_path: Path, step: str, outcome: str, reason: str
) -> None:
    with pytest.raises(SandboxError, match=reason):
        with _open(bug_repo, tmp_path, _failing(step, outcome)):
            pass
    assert not (tmp_path / "bench" / "recall-test").exists()


def test_base_unreachable(bug_repo: BuiltBugRepo, tmp_path: Path) -> None:
    with pytest.raises(SandboxError, match="base unreachable"):
        with _open(bug_repo, tmp_path, SubprocessRunner(), base=bug_repo.fix):
            pass
