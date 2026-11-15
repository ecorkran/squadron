"""Harness failures are recorded as ``harness_error``, never as a rejection (slice 426, Task 19)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from squadron.benchmark.adapter import SuiteRunError
from squadron.benchmark.slice_qualify import qualify_slice_candidate
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.metrology.benchmark_models import QualificationOutcome
from squadron.metrology.slice_case_models import SliceCandidateRejection
from squadron.replay.history_free_sandbox import SandboxError
from tests.benchmark.slice_qualify_support import SUITE_RUNS, FakeSuite, Setup, typical_setup
from tests.benchmark.slice_repos import docs_only_slice, two_parent_landing


class _FailingGit:
    """Real git, except ``git ls-tree`` exits non-zero."""

    def __init__(self) -> None:
        self._real = SubprocessRunner()

    def run(self, argv: Sequence[str], **kwargs: object) -> ProcessResult:
        if argv[1] == "ls-tree":
            return ProcessResult(
                argv=tuple(argv), returncode=128, stdout="", stderr="fatal: bad object"
            )
        return self._real.run(argv, cwd=kwargs["cwd"], timeout=kwargs["timeout"])  # type: ignore[arg-type]


def _tip_sandbox_fails(tip_sha: str) -> Callable[[str], Exception | None]:
    return lambda sha: SandboxError("no space left") if sha == tip_sha else None


def _setups(tmp_path: Path) -> dict[str, Callable[[], Setup]]:
    built = two_parent_landing(tmp_path / "repo")
    tip = built.landing.tip
    return {
        "suite timeout": lambda: typical_setup(
            tmp_path / "t", built, suite=FakeSuite(SUITE_RUNS, timed_out=True)
        ),
        "SuiteRunError": lambda: typical_setup(
            tmp_path / "e", built, suite=FakeSuite(SUITE_RUNS, error=SuiteRunError("no report"))
        ),
        "sandbox error": lambda: typical_setup(tmp_path / "s", built, fail=_tip_sandbox_fails(tip)),
        "failed git": lambda: typical_setup(tmp_path / "g", built, runner=_FailingGit()),
    }


@pytest.mark.parametrize("failure", ["suite timeout", "SuiteRunError", "sandbox error", "failed git"])
def test_each_harness_failure_is_a_harness_error_with_an_error_log_and_no_case(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, failure: str
) -> None:
    setup = _setups(tmp_path)[failure]()

    with caplog.at_level(logging.ERROR):
        result = qualify_slice_candidate(setup.candidate, setup.deps)

    assert result.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert result.record.rejection is None
    assert result.record.detail
    assert result.case is None
    assert setup.cases.list_cases(setup.deps.project_id) == []
    assert any(
        record.levelno == logging.ERROR and str(setup.candidate.slice_index) in record.getMessage()
        for record in caplog.records
    )


def test_a_harness_error_is_never_reused(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    failing = typical_setup(tmp_path / "s", built, runner=_FailingGit())
    qualify_slice_candidate(failing.candidate, failing.deps)
    retry = typical_setup(tmp_path / "s", built)

    result = qualify_slice_candidate(retry.candidate, retry.deps)

    assert not result.reused
    assert result.record.outcome is QualificationOutcome.QUALIFIED


def test_a_later_result_under_the_same_key_overwrites_the_harness_error(tmp_path: Path) -> None:
    built = docs_only_slice(tmp_path / "repo")
    failing = typical_setup(tmp_path / "s", built, runner=_FailingGit())
    first = qualify_slice_candidate(failing.candidate, failing.deps)
    retry = typical_setup(tmp_path / "s", built)

    second = qualify_slice_candidate(retry.candidate, retry.deps)

    assert first.record.outcome is QualificationOutcome.HARNESS_ERROR
    assert second.record.rejection is SliceCandidateRejection.NO_CODE_CHANGE
    stored = retry.qualifications.get_slice_qualification(
        retry.deps.project_id, built.index, built.landing.after, None
    )
    assert stored == second.record
