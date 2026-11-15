"""Load test: grading many replays in sequence, as ``sq benchmark grade`` does (slice 425).

Required by the load-test tier: grading is an environment-layer path (a clone, a diff apply,
tool-config restoration and a record write per subject) and a benchmark holds many subjects.
Twenty-four replays are graded through the real ``grade_one`` over a real git fixture, and the
run must keep each subject inside a wall-clock bound, leave no sandbox behind, write exactly
one record per subject and stay within the review budget.
"""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.grade_one import grade_one
from squadron.metrology.grade_records import ImplementationGrade
from tests.benchmark.grade_support import BENCHMARK_ID, replay_world
from tests.benchmark.grading_fixtures import GradingRepo, build_grading_repo

REPLAY_COUNT = 24
PER_REVIEW_USD = 0.2
#: Generous: a clone of the small fixture, a diff apply and a store write take well under this.
SECONDS_PER_SUBJECT = 10.0


def test_many_replays_grade_within_bounds_and_leave_nothing(tmp_path: Path) -> None:
    repo: GradingRepo = build_grading_repo(tmp_path / "repo")
    budget = ReviewBudget(cap_usd=REPLAY_COUNT * PER_REVIEW_USD, per_review_usd=PER_REVIEW_USD)
    world, diff = replay_world(tmp_path, repo, budget=budget)
    template = world.replay_target(diff)

    started = time.monotonic()
    records: list[ImplementationGrade] = []
    for index in range(REPLAY_COUNT):
        target = replace(template, replay_id=f"implreplay-load-{index:04d}")
        record = grade_one(world.case, target, world.deps)
        assert isinstance(record, ImplementationGrade)
        records.append(record)
    elapsed = time.monotonic() - started

    assert elapsed < REPLAY_COUNT * SECONDS_PER_SUBJECT, f"{elapsed:.1f}s for {REPLAY_COUNT}"
    assert all(record.result is not None for record in records), [r.detail for r in records]
    assert len(world.store.grades_for(BENCHMARK_ID)) == REPLAY_COUNT
    assert len(world.factory.opened) == REPLAY_COUNT
    assert len(world.factory.removed) == REPLAY_COUNT
    assert all(not sandbox.tree.exists() for sandbox in world.factory.opened)
