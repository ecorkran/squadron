"""``grade_one``: the sandbox, the digest check and the diff (slice 425 Task 24, D1, D16)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from squadron.benchmark.grade_one import grade_one
from squadron.benchmark.grade_prepare import prepare_tree
from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.grade_models import GradeAbsence
from squadron.metrology.grade_records import ImplementationGrade, ReferenceGrade
from tests.benchmark.grade_support import (
    OTHER_ENVIRONMENT,
    failing_environment,
    make_world,
    quiet_review,
    seed_reference,
)
from tests.benchmark.grading_fixtures import GradingRepo, build_variant, make_grading_case

START_IDS = ("t.py::a",)


def assert_error_logged(caplog: pytest.LogCaptureFixture, fragment: str) -> None:
    assert any(r.levelno == logging.ERROR and fragment in r.getMessage() for r in caplog.records), [
        r.getMessage() for r in caplog.records
    ]


def test_an_unresolvable_environment_is_environment_failed(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    world = make_world(tmp_path, grading_repo, fail=failing_environment("uv sync failed"))
    target = world.replay_target(b"irrelevant")
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, target, world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.ENVIRONMENT_FAILED
    assert record.absence_class is AbsenceClass.HARNESS
    assert record.environment_digest is None
    assert record.result is None
    assert_error_logged(caplog, "uv sync failed")


def test_a_digest_that_differs_from_the_replays_is_environment_changed(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    world = make_world(tmp_path, grading_repo, identity=OTHER_ENVIRONMENT)
    target = world.replay_target(b"irrelevant")
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, target, world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.ENVIRONMENT_CHANGED
    assert record.absence_class is AbsenceClass.HARNESS
    assert record.environment_digest == OTHER_ENVIRONMENT.identity_digest
    assert_error_logged(caplog, "differs from the expected")


def test_a_diff_that_does_not_apply_is_diff_apply_failed(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    world = make_world(tmp_path, grading_repo)
    bad = (
        b"diff --git a/missing.py b/missing.py\n--- a/missing.py\n+++ b/missing.py\n"
        b"@@ -1 +1 @@\n-nothing like this\n+at all\n"
    )
    with caplog.at_level(logging.ERROR):
        record = grade_one(world.case, world.replay_target(bad), world.deps)
    assert isinstance(record, ImplementationGrade)
    assert record.absence is GradeAbsence.DIFF_APPLY_FAILED
    assert record.absence_class is AbsenceClass.HARNESS
    assert_error_logged(caplog, "git apply")


def test_an_unreadable_reference_is_reference_unreadable(
    tmp_path: Path, grading_repo: GradingRepo, caplog: pytest.LogCaptureFixture
) -> None:
    case = make_grading_case(grading_repo)
    missing = case.model_copy(update={"reference_sha": "0" * 40})
    world = make_world(tmp_path, grading_repo, case=missing, collect=lambda s, c: START_IDS)
    with caplog.at_level(logging.ERROR):
        record = grade_one(missing, world.reference_target(), world.deps)
    assert isinstance(record, ReferenceGrade)
    assert record.absence is GradeAbsence.REFERENCE_UNREADABLE
    assert record.baseline_nodes is not None  # the baseline precedes the diff and is kept
    assert_error_logged(caplog, "git diff")


def test_an_absent_grade_is_written_to_the_store(tmp_path: Path, grading_repo: GradingRepo) -> None:
    world = make_world(tmp_path, grading_repo, identity=OTHER_ENVIRONMENT)
    grade_one(world.case, world.replay_target(b"x"), world.deps)
    stored = world.store.grades_for("bench-1")
    assert [grade.absence for _, grade in stored] == [GradeAbsence.ENVIRONMENT_CHANGED]


def test_a_clean_apply_commits_on_top_of_the_start_commit(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    producer = build_variant(grading_repo, "producer_a", tmp_path / "producer")
    world = make_world(tmp_path, grading_repo, reviewer=quiet_review)
    seed_reference(world, ())
    with world.factory(world.case) as sandbox:
        run = world.run(world.replay_target(producer.diff()), sandbox)
        prepare_tree(run)
        tree = sandbox.tree
        parent = subprocess.run(
            ["git", "rev-parse", "HEAD~1"], cwd=tree, capture_output=True, text=True, check=True
        ).stdout.strip()
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tree, capture_output=True, text=True, check=True
        ).stdout.strip()
        assert parent == grading_repo.start_sha
        assert run.head_sha == head
        author = subprocess.run(
            ["git", "log", "-1", "--format=%an"], cwd=tree, capture_output=True, text=True, check=True
        ).stdout.strip()
        assert author


def test_the_reference_diff_applies_and_commits(tmp_path: Path, grading_repo: GradingRepo) -> None:
    world = make_world(tmp_path, grading_repo, collect=lambda s, c: START_IDS, reviewer=quiet_review)
    with world.factory(world.case) as sandbox:
        run = world.run(world.reference_target(), sandbox)
        prepare_tree(run)
        names = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            cwd=sandbox.tree,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert "tests/review/test_parts.py" in names


def test_the_sandbox_is_removed_afterwards_unless_keep_is_set(
    tmp_path: Path, grading_repo: GradingRepo
) -> None:
    world = make_world(tmp_path, grading_repo, identity=OTHER_ENVIRONMENT)
    grade_one(world.case, world.replay_target(b"x"), world.deps)
    assert len(world.factory.removed) == 1
    assert not world.factory.removed[0].exists()

    kept_world = make_world(tmp_path / "kept", grading_repo, identity=OTHER_ENVIRONMENT, keep=True)
    grade_one(kept_world.case, kept_world.replay_target(b"x"), kept_world.deps)
    assert kept_world.factory.removed == []
    assert kept_world.factory.opened[0].tree.exists()
