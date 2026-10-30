"""The slice-landing resolver against throwaway repos (slice 403, criteria 1-3)."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.metrology.slice_range import resolve_slice_landings
from squadron.metrology.slice_range_models import (
    LandingMethod,
    RangeUnresolvedReason,
    SliceLanding,
)
from squadron.review.git_utils import run_git
from tests.conftest import run_test_git
from tests.metrology import slice_range_repos as repos
from tests.metrology.slice_range_repos import LandingShas


def resolve(repo: Path, index: int) -> list[SliceLanding] | RangeUnresolvedReason:
    return resolve_slice_landings(index, str(repo), "main")


def landings(repo: Path, index: int) -> list[SliceLanding]:
    outcome = resolve(repo, index)
    assert isinstance(outcome, list), outcome
    return outcome


def assert_landing(landing: SliceLanding, expected: LandingShas, method: LandingMethod) -> None:
    assert landing.method is method
    assert landing.target_ref == "main"
    assert landing.before_sha == expected.before
    assert landing.after_sha == expected.after
    assert landing.tip_sha == expected.tip
    assert landing.fork_sha == expected.fork
    assert landing.merge_sha == expected.merge


def fail_git_on(monkeypatch: pytest.MonkeyPatch, subcommand: str) -> None:
    """Make every ``run_git`` whose first argument is *subcommand* return None (a hang)."""

    def fake(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        return None if args[0] == subcommand else run_git(args, cwd=cwd)

    monkeypatch.setattr("squadron.metrology.slice_range.run_git", fake)


class TestMergePath:
    def test_no_ff_landing_resolves_one_landing(self, tmp_path: Path) -> None:
        repo, expected = repos.no_ff_landing(tmp_path)

        [landing] = landings(repo, 401)

        assert_landing(landing, expected, LandingMethod.MERGE_COMMIT)

    def test_same_landing_resolves_in_a_fresh_clone(self, tmp_path: Path) -> None:
        source, expected = repos.no_ff_landing(tmp_path / "source")
        clone = repos.clone_repo(source, tmp_path)

        [landing] = landings(clone, 401)

        assert_landing(landing, expected, LandingMethod.MERGE_COMMIT)

    def test_sync_merge_is_never_taken_as_a_landing(self, tmp_path: Path) -> None:
        repo, expected = repos.sync_merge(tmp_path)

        [landing] = landings(repo, 403)

        assert_landing(landing, expected, LandingMethod.MERGE_COMMIT)

    def test_two_landings_come_back_oldest_first(self, tmp_path: Path) -> None:
        repo, expected = repos.two_landings(tmp_path)

        first, second = landings(repo, 404)

        assert_landing(first, expected.first, LandingMethod.MERGE_COMMIT)
        assert_landing(second, expected.second, LandingMethod.MERGE_COMMIT)

    def test_failed_merge_search_is_git_error_with_a_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        repo, _ = repos.no_ff_landing(tmp_path)
        fail_git_on(monkeypatch, "log")

        with caplog.at_level(logging.WARNING):
            outcome = resolve(repo, 401)

        assert outcome is RangeUnresolvedReason.GIT_ERROR
        warning = next(r for r in caplog.records if r.levelno == logging.WARNING)
        assert "401" in warning.getMessage()
        assert "merge search" in warning.getMessage()


class TestFastForwardPath:
    def test_fast_forward_landing_resolves_one_landing(self, tmp_path: Path) -> None:
        repo, expected = repos.fast_forward_landing(tmp_path)

        [landing] = landings(repo, 402)

        assert_landing(landing, expected, LandingMethod.FAST_FORWARD)

    @pytest.mark.parametrize(
        ("build", "index", "reason"),
        [
            (lambda path: repos.rebased_branch(path)[0], 405, RangeUnresolvedReason.FORK_NOT_ANCESTOR),
            (repos.empty_branch, 406, RangeUnresolvedReason.EMPTY_BRANCH),
            (repos.landed_elsewhere, 407, RangeUnresolvedReason.LANDED_ELSEWHERE),
            (repos.not_landed, 408, RangeUnresolvedReason.NOT_LANDED),
            (repos.no_landing, 409, RangeUnresolvedReason.NO_LANDING),
        ],
    )
    def test_each_reason_is_returned_and_logged_at_info(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        build: Callable[[Path], Path],
        index: int,
        reason: RangeUnresolvedReason,
    ) -> None:
        repo = build(tmp_path)

        with caplog.at_level(logging.INFO):
            outcome = resolve(repo, index)

        assert outcome is reason
        info = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        assert any(str(index) in line and reason.value in line for line in info)

    def test_expired_reflog_is_reflog_unavailable(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        repo, _ = repos.fast_forward_landing(tmp_path)
        run_test_git(repo, "reflog", "expire", "--expire=now", "--all")

        with caplog.at_level(logging.INFO):
            outcome = resolve(repo, 402)

        assert outcome is RangeUnresolvedReason.REFLOG_UNAVAILABLE
        assert any(
            "402" in r.getMessage() and "reflog_unavailable" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.INFO
        )

    def test_failed_reflog_read_is_git_error_with_a_warning(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        repo, _ = repos.fast_forward_landing(tmp_path)
        fail_git_on(monkeypatch, "reflog")

        with caplog.at_level(logging.INFO):
            outcome = resolve(repo, 402)

        assert outcome is RangeUnresolvedReason.GIT_ERROR
        warning = next(r for r in caplog.records if r.levelno == logging.WARNING)
        assert "402" in warning.getMessage()
        assert "reflog" in warning.getMessage()
        assert not any(r.levelno == logging.INFO for r in caplog.records)
