"""First draft and final text, read from a sandbox repository (slice 177 D4)."""

from __future__ import annotations

import logging

import pytest

from squadron.metrology.replay_models import ReplayPhase
from squadron.replay.drafts import read_drafts
from tests.stats.repo_support import StatsRepo

_T1 = "2026-10-01T10:00:00+00:00"
_T2 = "2026-10-02T10:00:00+00:00"
_T3 = "2026-10-03T10:00:00+00:00"
_DESIGN = "project-documents/user/slices/176-slice.effort.md"


def test_first_draft_is_the_committed_first_version_and_final_is_the_working_file(
    stats_repo: StatsRepo,
) -> None:
    stats_repo.commit("start", {"README.md": "x\n"}, _T1)
    stats_repo.commit("draft", {_DESIGN: "# draft\n"}, _T2)
    stats_repo.commit("revise", {_DESIGN: "# revised\n"}, _T3)
    (stats_repo.root / _DESIGN).write_text("# uncommitted final\n", encoding="utf-8")

    drafts = read_drafts(stats_repo.root, ReplayPhase.DESIGN, 176)

    assert drafts.first == "# draft\n"
    assert drafts.final == "# uncommitted final\n"


def test_an_artifact_that_was_never_committed_has_no_first_draft_but_a_final_text(
    stats_repo: StatsRepo, caplog: pytest.LogCaptureFixture
) -> None:
    stats_repo.commit("start", {"README.md": "x\n"}, _T1)
    stats_repo.commit("other", {"b.txt": "b\n"}, _T2)
    (stats_repo.root / _DESIGN).parent.mkdir(parents=True)
    (stats_repo.root / _DESIGN).write_text("# only on disk\n", encoding="utf-8")

    with caplog.at_level(logging.WARNING):
        drafts = read_drafts(stats_repo.root, ReplayPhase.DESIGN, 176)

    assert drafts.first is None and drafts.final == "# only on disk\n"
    assert "no first draft for slice 176" in caplog.text


def test_an_undecodable_final_text_is_none_with_a_warning(
    stats_repo: StatsRepo, caplog: pytest.LogCaptureFixture
) -> None:
    stats_repo.commit("start", {"README.md": "x\n"}, _T1)
    stats_repo.commit("draft", {_DESIGN: "# draft\n"}, _T2)
    (stats_repo.root / _DESIGN).write_bytes(b"\xff\xfe\x00bad")

    with caplog.at_level(logging.WARNING):
        drafts = read_drafts(stats_repo.root, ReplayPhase.DESIGN, 176)

    assert drafts.first == "# draft\n" and drafts.final is None
    assert "final text unreadable for slice 176" in caplog.text


def test_no_artifact_at_all_is_none_for_both(stats_repo: StatsRepo) -> None:
    stats_repo.commit("start", {"README.md": "x\n"}, _T1)
    stats_repo.commit("other", {"b.txt": "b\n"}, _T2)

    drafts = read_drafts(stats_repo.root, ReplayPhase.DESIGN, 176)

    assert (drafts.first, drafts.final) == (None, None)


def test_split_task_files_are_concatenated_in_numeric_order(stats_repo: StatsRepo) -> None:
    base = "project-documents/user/tasks/176-tasks.effort"
    files = {f"{base}-{n}.md": f"part {n}\n" for n in (1, 2, 10)}
    stats_repo.commit("start", {"README.md": "x\n"}, _T1)
    stats_repo.commit("tasks", files, _T2)

    drafts = read_drafts(stats_repo.root, ReplayPhase.TASKS, 176)

    assert drafts.first == drafts.final == "part 1\n\npart 2\n\npart 10\n"
