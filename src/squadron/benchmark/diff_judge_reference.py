"""Reading a slice case's reference diff from the user's checkout (slice 426 D2, D16).

The reference is ``start..tip`` as the landed slice left it. A ``tip_sha`` the checkout does
not hold is a refusal naming the case and the sha, before any call is made; a git call that
does not answer halts the run.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path

from squadron.benchmark.diff_judge_plan import JudgeHalted, JudgeRefusal
from squadron.benchmark.slice_git import SliceHarnessError, git_result
from squadron.core.process_runner import ProcessResult, ProcessRunner
from squadron.metrology.benchmark_models import BenchmarkCase

_logger = logging.getLogger(__name__)


class ReferenceDiffReader:
    """``start..tip`` of a case, read with ``git diff --binary`` in the case project's checkout."""

    def __init__(self, runner: ProcessRunner, repos: Mapping[str, Path], timeout_s: float) -> None:
        self._runner = runner
        self._repos = repos
        self._timeout_s = timeout_s

    def __call__(self, case: BenchmarkCase) -> bytes:
        repo = self._repos[case.project_id.value]
        for sha in (case.start_sha, case.reference_sha):
            if self._git(repo, ["cat-file", "-e", f"{sha}^{{commit}}"]).returncode != 0:
                raise JudgeRefusal(
                    f"case {case.case_id}: commit {sha} is not in {repo}; the reference diff "
                    f"cannot be read there (is --repo the checkout the slice landed in?)"
                )
        diff = self._git(repo, ["diff", "--binary", case.start_sha, case.reference_sha])
        if diff.returncode != 0:
            message = (
                f"git diff for case {case.case_id} exited {diff.returncode}: {diff.stderr.strip()}"
            )
            _logger.error(message)
            raise JudgeHalted(message)
        return diff.stdout.encode("utf-8")

    def _git(self, repo: Path, args: list[str]) -> ProcessResult:
        try:
            return git_result(self._runner, repo, args, self._timeout_s)
        except SliceHarnessError as exc:
            # ``git_result`` logged it; the run stops.
            raise JudgeHalted(str(exc)) from exc
