"""Replay start-point resolution (slice 177 D2) on real throwaway git repos."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.metrology.replay_models import ReplayPhase
from squadron.replay.start_point import (
    ArtifactNotFoundError,
    RootCommitError,
    resolve_start_point,
)
from squadron.review.git_utils import run_git
from squadron.stats.git_history import GitHistory
from tests.stats.repo_support import StatsRepo

_T1 = "2026-10-01T10:00:00+00:00"
_T2 = "2026-10-02T10:00:00+00:00"
_T3 = "2026-10-03T10:00:00+00:00"
_T4 = "2026-10-04T10:00:00+00:00"
_DESIGN = "project-documents/user/slices/176-slice.effort-calibration.md"
_ARCHIVED = "project-documents/user/slices/archive/176-slice.effort-calibration.md"
_PLAN = "project-documents/user/architecture/140-slices.pipeline-foundation.md"


def _loaded(repo: StatsRepo) -> GitHistory:
    history = GitHistory(repo.root, run=run_git)
    history.load()
    return history


def test_design_start_point_is_the_first_parent_of_the_adding_commit(stats_repo: StatsRepo) -> None:
    start = stats_repo.commit("init", {_PLAN: "plan\n"}, _T1)
    added = stats_repo.commit(
        "docs: add design", {_DESIGN: "# first draft\n", _PLAN: "plan 176\n"}, _T2
    )

    point = resolve_start_point(ReplayPhase.DESIGN, 176, _loaded(stats_repo))

    assert (point.original_sha, point.start_sha) == (added, start)
    assert point.slice_name == "effort-calibration"
    assert point.artifact_path == _DESIGN
    assert point.slice_index == 176 and point.phase is ReplayPhase.DESIGN


def test_first_draft_is_the_content_at_the_adding_commit_after_later_edits(
    stats_repo: StatsRepo,
) -> None:
    stats_repo.commit("init", {_PLAN: "plan\n"}, _T1)
    stats_repo.commit("docs: add design", {_DESIGN: "# first draft\n"}, _T2)
    stats_repo.commit("docs: revise design", {_DESIGN: "# revised\n"}, _T3)

    point = resolve_start_point(ReplayPhase.DESIGN, 176, _loaded(stats_repo))

    assert point.original_first_draft == "# first draft\n"


def test_a_later_file_in_archive_with_the_same_index_is_not_matched(stats_repo: StatsRepo) -> None:
    stats_repo.commit("init", {_PLAN: "plan\n"}, _T1)
    stats_repo.commit("docs: archive only", {_ARCHIVED: "# archived\n"}, _T2)

    with pytest.raises(ArtifactNotFoundError):
        resolve_start_point(ReplayPhase.DESIGN, 176, _loaded(stats_repo))


def test_the_live_file_wins_over_an_archived_copy_added_later(stats_repo: StatsRepo) -> None:
    stats_repo.commit("init", {_PLAN: "plan\n"}, _T1)
    added = stats_repo.commit("docs: add design", {_DESIGN: "# live\n"}, _T2)
    stats_repo.commit("docs: archive copy", {_ARCHIVED: "# copy\n"}, _T3)

    point = resolve_start_point(ReplayPhase.DESIGN, 176, _loaded(stats_repo))

    assert point.original_sha == added


def test_split_task_files_concatenate_in_numeric_suffix_order(stats_repo: StatsRepo) -> None:
    base = "project-documents/user/tasks/176-tasks.effort-calibration"
    files = {f"{base}-{n}.md": f"part {n}\n" for n in (1, 2, 10)}
    stats_repo.commit("init", {_PLAN: "plan\n"}, _T1)
    stats_repo.commit("docs: add tasks", files, _T2)

    point = resolve_start_point(ReplayPhase.TASKS, 176, _loaded(stats_repo))

    assert point.original_first_draft == "part 1\n\npart 2\n\npart 10\n"
    assert point.slice_name == "effort-calibration"
    assert point.artifact_path == f"{base}-1.md"


def test_a_single_tasks_file_keeps_its_whole_name(stats_repo: StatsRepo) -> None:
    stats_repo.commit("init", {_PLAN: "plan\n"}, _T1)
    stats_repo.commit(
        "docs: add tasks", {"project-documents/user/tasks/176-tasks.phase-2.md": "t\n"}, _T2
    )

    point = resolve_start_point(ReplayPhase.TASKS, 176, _loaded(stats_repo))

    assert point.slice_name == "phase-2"


def test_no_adding_commit_names_the_pattern(stats_repo: StatsRepo) -> None:
    stats_repo.commit("init", {_PLAN: "plan\n"}, _T1)

    with pytest.raises(ArtifactNotFoundError, match="176-slice") as caught:
        resolve_start_point(ReplayPhase.DESIGN, 176, _loaded(stats_repo))

    assert caught.value.pattern == "project-documents/user/slices/176-slice.*.md"


def test_a_root_commit_has_no_start_point(stats_repo: StatsRepo) -> None:
    root = stats_repo.commit("docs: add design", {_DESIGN: "# first\n"}, _T1)

    with pytest.raises(RootCommitError) as caught:
        resolve_start_point(ReplayPhase.DESIGN, 176, _loaded(stats_repo))

    assert caught.value.sha == root


def test_real_history_resolves_slice_176_to_the_spike_start_sha() -> None:
    """Task 1's spike recorded this start sha from the real squadron history."""
    repo_root = Path(__file__).resolve().parents[2]
    history = GitHistory(repo_root, run=run_git)
    history.load()

    point = resolve_start_point(ReplayPhase.DESIGN, 176, history)

    assert point.start_sha == "bca771926e89d9ac7c753d9c88a84aa4b1f83ac7"
    assert point.slice_name == "effort-calibration-and-producer-model-effectiveness"
    assert point.original_first_draft.startswith("---")
