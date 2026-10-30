"""``record_slice_ranges``: persistence, durability and the concurrent-write guard (403 D1, D4)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.metrology.models import ProjectId
from squadron.metrology.slice_range import (
    SliceRangeResult,
    record_slice_ranges,
    resolve_slice_landings,
)
from squadron.metrology.slice_range_models import RangeUnresolvedReason, SliceLanding, SliceRanges
from squadron.metrology.store import MetrologyStore, slice_ranges_record_id
from tests.conftest import run_test_git
from tests.metrology import slice_range_repos as repos
from tests.metrology.snapshot.builders import make_project_id
from tests.metrology.test_slice_range_models import make_landing


class SpyStore(MetrologyStore):
    """A real store that counts writes."""

    def __init__(self, store_dir: Path) -> None:
        super().__init__(store_dir=store_dir)
        self.writes = 0

    def write_slice_ranges(self, ranges: SliceRanges) -> str:
        self.writes += 1
        return super().write_slice_ranges(ranges)


class RacedStore(SpyStore):
    """A store whose record changes between the start read and the re-read before the write."""

    def __init__(self, store_dir: Path, rival: SliceRanges) -> None:
        super().__init__(store_dir)
        self._rival = rival
        self._reads = 0

    def get_slice_ranges(self, project_id: ProjectId) -> SliceRanges | None:
        self._reads += 1
        return self._rival if self._reads > 1 else super().get_slice_ranges(project_id)


@pytest.fixture
def project() -> ProjectId:
    return make_project_id()


@pytest.fixture
def store(tmp_path: Path) -> SpyStore:
    return SpyStore(tmp_path / "store")


def record(
    repo: Path, store: MetrologyStore, project: ProjectId, *indices: int
) -> list[SliceRangeResult]:
    return record_slice_ranges(list(indices), str(repo), "main", store, project)


def seeded(project: ProjectId, slices: dict[int, list[SliceLanding]]) -> SliceRanges:
    return SliceRanges(record_id=slice_ranges_record_id(project), project_id=project, slices=slices)


def test_stored_fast_forward_range_survives_a_deleted_branch_and_expired_reflog(
    tmp_path: Path, store: SpyStore, project: ProjectId
) -> None:
    repo, expected = repos.fast_forward_landing(tmp_path)
    [first] = record(repo, store, project, 402)
    assert [entry.is_new for entry in first.landings] == [True]
    run_test_git(repo, "branch", "-D", "402-slice.y")
    run_test_git(repo, "reflog", "expire", "--expire=now", "--all")

    [again] = record(repo, store, project, 402)

    assert again.reason is RangeUnresolvedReason.NO_LANDING
    assert [entry.landing.after_sha for entry in again.landings] == [expected.after]
    assert [entry.is_new for entry in again.landings] == [False]
    assert store.writes == 1


def test_second_run_with_nothing_new_does_not_write(
    tmp_path: Path, store: SpyStore, project: ProjectId
) -> None:
    repo, _ = repos.no_ff_landing(tmp_path)

    record(repo, store, project, 401)
    [again] = record(repo, store, project, 401)

    assert not any(entry.is_new for entry in again.landings)
    assert store.writes == 1


def test_a_new_merge_adds_exactly_that_landing_and_keeps_the_stored_one_unchanged(
    tmp_path: Path, store: SpyStore, project: ProjectId
) -> None:
    repo, _ = repos.two_landings(tmp_path)
    first, second = _landings(repo, 404)
    store.write_slice_ranges(seeded(project, {404: [first]}))
    stored_json = first.model_dump_json()

    [result] = record(repo, store, project, 404)

    assert [entry.is_new for entry in result.landings] == [False, True]
    stored = store.get_slice_ranges(project)
    assert stored is not None
    assert [x.after_sha for x in stored.slices[404]] == [first.after_sha, second.after_sha]
    assert stored.slices[404][0].model_dump_json() == stored_json


def _landings(repo: Path, index: int) -> list[SliceLanding]:
    outcome = resolve_slice_landings(index, str(repo), "main")
    assert isinstance(outcome, list)
    return outcome


def test_concurrent_write_keeps_both_runs_landings_and_warns(
    tmp_path: Path, project: ProjectId, caplog: pytest.LogCaptureFixture
) -> None:
    repo, _ = repos.no_ff_landing(tmp_path)
    rival_landing = make_landing("9" * 40)
    raced = RacedStore(tmp_path / "raced", seeded(project, {777: [rival_landing]}))

    with caplog.at_level(logging.WARNING):
        record(repo, raced, project, 401)

    written = MetrologyStore.get_slice_ranges(raced, project)
    assert written is not None
    assert set(written.slices) == {401, 777}
    assert written.slices[777] == [rival_landing]
    warning = next(r for r in caplog.records if r.levelno == logging.WARNING)
    assert slice_ranges_record_id(project) in warning.getMessage()


def test_git_error_for_one_slice_persists_the_other_only(
    tmp_path: Path, store: SpyStore, project: ProjectId, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, _ = repos.no_ff_landing(tmp_path)

    def fail_slice_999(
        index: int, repo_root: str, target: str
    ) -> list[SliceLanding] | RangeUnresolvedReason:
        if index == 999:
            return RangeUnresolvedReason.GIT_ERROR
        return resolve_slice_landings(index, repo_root, target)

    monkeypatch.setattr("squadron.metrology.slice_range.resolve_slice_landings", fail_slice_999)

    good, bad = record(repo, store, project, 401, 999)

    assert good.reason is None
    assert bad.reason is RangeUnresolvedReason.GIT_ERROR
    stored = store.get_slice_ranges(project)
    assert stored is not None
    assert set(stored.slices) == {401}
