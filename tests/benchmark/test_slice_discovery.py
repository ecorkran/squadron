"""Slice discovery and the no-code check on the fixture repositories (slice 426, Task 13)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import pytest

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.slice_discovery import (
    SLICE_RANGES_COMMAND,
    discover,
    has_code_change,
)
from squadron.benchmark.slice_git import SliceHarnessError
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError, SubprocessRunner
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.slice_case_models import SliceCandidateRejection
from squadron.metrology.slice_range_models import LandingMethod, SliceLanding, SliceRanges
from tests.benchmark.slice_repos import (
    SLICE_NAME,
    SliceRepo,
    all_tests_rewritten,
    branch_with_target_merge,
    docs_only_slice,
    fast_forward_landing,
    landing_to_record,
    load_real_landings,
    two_landings_of_one_slice,
    two_parent_landing,
)
from tests.conftest import run_test_git

PROJECT = ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE)
TIMEOUT_S = 30.0


def _ranges(*built: SliceRepo) -> SliceRanges:
    slices: dict[int, list[SliceLanding]] = {}
    for item in built:
        landings = [landing_to_record(item.landing)]
        if item.second is not None:
            landings.append(landing_to_record(item.second))
        slices[item.index] = landings
    return SliceRanges(record_id="sliceranges-test", project_id=PROJECT, slices=slices)


class _Store:
    def __init__(self, ranges: SliceRanges | None) -> None:
        self._ranges = ranges

    def get_slice_ranges(self, project_id: ProjectId) -> SliceRanges | None:
        assert project_id == PROJECT
        return self._ranges


class _FailingGit:
    """A runner whose git never answers: it times out, or exits non-zero."""

    def __init__(self, *, timeout: bool) -> None:
        self._timeout = timeout

    def run(self, argv: Sequence[str], **kwargs: object) -> ProcessResult:
        if self._timeout:
            raise ProcessTimedOutError(argv, 1.0)
        return ProcessResult(argv=tuple(argv), returncode=128, stdout="", stderr="fatal: bad object")


class _NoMerges:
    """A runner answering every ``rev-list --merges`` with nothing."""

    def run(self, argv: Sequence[str], **kwargs: object) -> ProcessResult:
        return ProcessResult(argv=tuple(argv), returncode=0, stdout="", stderr="")


def test_a_two_parent_and_a_fast_forward_landing_yield_candidates(tmp_path: Path) -> None:
    merged = two_parent_landing(tmp_path / "a")
    forwarded = fast_forward_landing(tmp_path / "b")

    for built in (merged, forwarded):
        result = discover(_Store(_ranges(built)), PROJECT, SubprocessRunner(), built.repo, TIMEOUT_S)

        assert [c.slice_index for c in result.candidates] == [built.index]
        assert result.candidates[0].landing.tip_sha == built.landing.tip
        assert (result.rejections, result.harness_failures) == ((), ())


def test_two_landings_are_rejected_as_multiple_landings(tmp_path: Path) -> None:
    built = two_landings_of_one_slice(tmp_path)

    result = discover(_Store(_ranges(built)), PROJECT, SubprocessRunner(), built.repo, TIMEOUT_S)

    assert result.candidates == ()
    rejection = result.rejections[0]
    assert rejection.rejection is SliceCandidateRejection.MULTIPLE_LANDINGS
    assert "2 landings" in rejection.detail
    assert built.second is not None
    assert rejection.landing.after_sha == built.second.after


def test_a_target_merge_on_the_branch_is_rejected(tmp_path: Path) -> None:
    built = branch_with_target_merge(tmp_path)

    result = discover(_Store(_ranges(built)), PROJECT, SubprocessRunner(), built.repo, TIMEOUT_S)

    assert result.candidates == ()
    assert result.rejections[0].rejection is SliceCandidateRejection.BRANCH_CONTAINS_MERGES


def test_no_record_refuses_naming_the_command() -> None:
    with pytest.raises(BuildHalted, match=SLICE_RANGES_COMMAND):
        discover(_Store(None), PROJECT, _NoMerges(), Path("."), TIMEOUT_S)


@pytest.mark.parametrize("timeout", [True, False], ids=["timeout", "non-zero exit"])
def test_a_git_that_does_not_answer_is_a_harness_failure_not_a_rejection(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, timeout: bool
) -> None:
    built = two_parent_landing(tmp_path)

    with caplog.at_level(logging.ERROR):
        result = discover(
            _Store(_ranges(built)), PROJECT, _FailingGit(timeout=timeout), built.repo, TIMEOUT_S
        )

    assert (result.candidates, result.rejections) == ((), ())
    assert result.harness_failures[0].slice_index == built.index
    assert "git rev-list --merges" in result.harness_failures[0].detail
    assert any(r.levelno == logging.ERROR and "rev-list" in r.getMessage() for r in caplog.records)


def test_every_index_in_the_record_is_accounted_for_once(tmp_path: Path) -> None:
    merged = two_parent_landing(tmp_path)
    ranges = _ranges(merged)
    landing = ranges.slices[merged.index][0]
    ranges.slices[599] = [landing]  # a second index over the same history
    ranges.slices[598] = [landing, landing.model_copy(update={"after_sha": "e" * 40})]

    result = discover(_Store(ranges), PROJECT, SubprocessRunner(), merged.repo, TIMEOUT_S)

    accounted = [
        item.slice_index
        for found in (result.candidates, result.rejections, result.harness_failures)
        for item in found
    ]
    assert sorted(accounted) == sorted(ranges.slices)


def test_real_landings_give_one_candidate_per_landing_method() -> None:
    ranges = load_real_landings()

    result = discover(_Store(ranges), PROJECT, _NoMerges(), Path("."), TIMEOUT_S)

    methods = {c.slice_index: c.landing.method for c in result.candidates}
    assert methods == {402: LandingMethod.MERGE_COMMIT, 420: LandingMethod.FAST_FORWARD}


def test_has_code_change_is_false_for_a_docs_only_slice(tmp_path: Path) -> None:
    built = docs_only_slice(tmp_path)

    assert not has_code_change(
        built.landing.fork, built.landing.tip, built.repo, SubprocessRunner(), TIMEOUT_S
    )


def test_has_code_change_is_true_with_one_code_file_among_dropped_files(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path)

    assert has_code_change(
        built.landing.fork, built.landing.tip, built.repo, SubprocessRunner(), TIMEOUT_S
    )


def test_has_code_change_is_true_for_a_rename_from_a_dropped_path_to_a_code_path(
    tmp_path: Path,
) -> None:
    built = all_tests_rewritten(tmp_path)
    repo = built.repo
    run_test_git(repo, "checkout", "-q", "-b", "rename-work", built.landing.fork)
    dropped = f"project-documents/user/tasks/{built.index}-tasks.{SLICE_NAME}.md"
    run_test_git(repo, "mv", dropped, "src/notes.md")
    run_test_git(repo, "commit", "-q", "-m", "move a task file into src")
    tip = run_test_git(repo, "rev-parse", "HEAD").strip()

    assert has_code_change(built.landing.fork, tip, repo, SubprocessRunner(), TIMEOUT_S)


def test_has_code_change_raises_and_logs_when_git_fails(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR), pytest.raises(SliceHarnessError, match="diff --name-status"):
        has_code_change("a" * 40, "b" * 40, tmp_path, _FailingGit(timeout=False), TIMEOUT_S)

    assert any(r.levelno == logging.ERROR for r in caplog.records)
