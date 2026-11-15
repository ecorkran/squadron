"""A slice case replayed through the real ``SliceCaseRunner`` on the fixture project
(slice 426, Task 26; Task 41 extends this file with grading, judging and the report).

Sandboxes, git, cf registration under the scrubbed home, uv and pytest are real; the
runner's ``sq run P6 --producer-only`` call is scripted (``slice_pipeline_support``). The
world is built once per module: it installs the fixture project several times.
"""

from __future__ import annotations

import os
import re
import subprocess

import pytest

from squadron.benchmark.bench_report_render import render_text
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.benchmark_replay_models import ImplementationReplay
from squadron.metrology.grade_records import ImplementationGrade
from squadron.metrology.grade_store import GradeRecordStore
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from tests.benchmark.slice_pipeline_grading import (
    GradedRun,
    Judged,
    grade_all,
    judge_all,
    report_of,
)
from tests.benchmark.slice_pipeline_support import (
    BENCHMARK_ID,
    BREAKING_LINE,
    CONFIG_BREAKING,
    CONFIG_REFERENCE,
    CONFIG_SILENT,
    SliceWorld,
    replay_world,
)

pytestmark = [pytest.mark.network, pytest.mark.host_cf]


def cf_project_names() -> list[str]:
    """The project names ``cf project list`` prints under the real home (the registry the
    replays must not touch). Only the name column: other sessions move a project's slice and
    phase columns while this test runs, but they do not add this test's sandboxes."""
    result = subprocess.run(
        ["cf", "project", "list"], capture_output=True, text=True, check=True, env=dict(os.environ)
    )
    # Two header lines; each row is a two-character current-project marker, then the name.
    # A long value wraps onto a continuation line that starts with spaces.
    bodies = [row[2:] for row in result.stdout.splitlines()[2:]]
    return sorted(body.split()[0] for body in bodies if body and not body[0].isspace())


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> SliceWorld:
    before = cf_project_names()
    built = replay_world(tmp_path_factory.mktemp("slice-pipeline"))
    assert cf_project_names() == before, "the replays changed the real cf registry"
    return built


def diff_of(world: SliceWorld, replay: ImplementationReplay) -> str:
    assert replay.diff is not None
    return world.setup.records.diffs.get(replay.diff.sha256).decode()


def test_the_reference_config_commits_the_reference_change(world: SliceWorld) -> None:
    replay = world.replays[CONFIG_REFERENCE.alias]
    assert replay.outcome is ProducerOutcome.COMMITTED
    assert replay.absence is None
    text = diff_of(world, replay)
    assert "+def mul(left: int, right: int)" in text
    assert "tests/test_mul.py" in text


def test_the_breaking_config_commits_a_diff_against_the_fork(world: SliceWorld) -> None:
    replay = world.replays[CONFIG_BREAKING.alias]
    assert replay.outcome is ProducerOutcome.COMMITTED
    text = diff_of(world, replay)
    assert BREAKING_LINE.strip() in text
    assert "mul" not in text


def test_the_silent_config_is_the_no_commit_absence(world: SliceWorld) -> None:
    replay = world.replays[CONFIG_SILENT.alias]
    assert replay.outcome is ProducerOutcome.NO_COMMIT
    assert replay.absence is AbsenceClass.CONFIG
    assert replay.diff is None and replay.commit_sha is None


def test_each_replay_ran_the_producer_in_its_own_tree_with_the_run_id(world: SliceWorld) -> None:
    assert len(world.producer.calls) == 3
    trees = {cwd for _, cwd in world.producer.calls}
    assert len(trees) == 3
    for argv, _ in world.producer.calls:
        assert argv[1:4] == ["run", "P6", "511"]
        assert "--producer-only" in argv


def test_the_replays_are_stored_under_the_benchmark(world: SliceWorld) -> None:
    stored = world.setup.records.replays_for("bench-0123456789abcdef")
    assert len(stored) == 3
    assert {replay.outcome for _, replay in stored} == {
        ProducerOutcome.COMMITTED,
        ProducerOutcome.NO_COMMIT,
    }


# --- Task 41: grade, judge and report the same replays --------------------------------------


@pytest.fixture(scope="module")
def graded(world: SliceWorld, tmp_path_factory: pytest.TempPathFactory) -> GradedRun:
    locks = tmp_path_factory.mktemp("locks")
    plan, summary, lines = grade_all(world, locks)
    return GradedRun(plan, summary, lines)


@pytest.fixture(scope="module")
def judged(world: SliceWorld, graded: GradedRun, tmp_path_factory: pytest.TempPathFactory) -> Judged:
    return judge_all(world, tmp_path_factory.mktemp("judge-locks"))


def grades_by_alias(world: SliceWorld) -> dict[str, ImplementationGrade]:
    """Each stored replay grade, keyed by the alias of the replay it graded."""
    aliases = {record_id: replay.config.alias for record_id, replay in world.replays_with_ids()}
    stored = GradeRecordStore(world.setup.records).grades_for(BENCHMARK_ID)
    return {aliases[grade.replay_id]: grade for _, grade in stored}


def test_grading_passes_the_reference_and_the_good_replay_and_fails_the_breaking_one(
    world: SliceWorld, graded: GradedRun
) -> None:
    records = world.setup.records
    reference = GradeRecordStore(records).get_reference_grade(
        world.case.case_id, graded.plan.grader.digest, graded.plan.references[0].environment_digest
    )
    assert reference is not None and reference.result is not None
    assert reference.result.passed
    by_alias = grades_by_alias(world)
    assert set(by_alias) == {CONFIG_REFERENCE.alias, CONFIG_BREAKING.alias}, (
        "the no-commit replay is not graded"
    )
    good, broken = by_alias[CONFIG_REFERENCE.alias], by_alias[CONFIG_BREAKING.alias]
    assert good.result is not None and good.result.passed
    assert broken.result is not None and not broken.result.passed
    assert broken.result.regression_failure_count == 1
    assert broken.result.regression_failures == ("tests/test_calc.py::test_sub",)
    assert (graded.summary.references_graded, graded.summary.replays_graded) == (1, 2)


def test_every_pair_with_the_silent_replay_is_a_forfeit_and_the_rest_are_judged(
    world: SliceWorld, judged: Judged
) -> None:
    silent_id = next(
        record_id
        for record_id, replay in world.replays_with_ids()
        if replay.config.alias == CONFIG_SILENT.alias
    )
    judgments = SliceCaseRecordStore(world.setup.records).diff_judgments_for(BENCHMARK_ID)
    assert len(judgments) == 6
    with_silent = [j for j in judgments if silent_id in (j.a, j.b)]
    others = [j for j in judgments if silent_id not in (j.a, j.b)]
    assert len(with_silent) == 3 and all(j.forfeit for j in with_silent)
    assert len(others) == 3 and not any(j.forfeit for j in others)
    assert len(judged.dispatcher.prompts) == 6, (
        "three judged pairs, two orders each, no call for a forfeit"
    )
    assert (judged.result.summary.judged, judged.result.summary.forfeits) == (3, 3)
    bound, *pair_lines = judged.lines
    assert "pairs 6 (3 forfeits)" in bound, "the bound is the first thing printed"
    assert len(pair_lines) == 6


def test_the_report_has_the_slice_table_and_the_pairwise_section(
    world: SliceWorld, graded: GradedRun, judged: Judged
) -> None:
    text = render_text(report_of(world))

    assert "slice cases" in text and "no regressions" in text
    pairwise = text[text.index("pairwise (judge") :]
    assert "strength" in pairwise
    assert re.search(r"reference\s+1\.00\s+\(reference line, not ranked\)", pairwise)
    assert re.search(r"opus vs sol\s+d \+1\.00\s+too few cases \(1\)", pairwise)
    assert "judged 1 · over size 0 · harness-absent 0 · pending 0" in pairwise
    forfeits = sorted(row.forfeits for row in report_of(world).pairwise.configs)  # type: ignore[union-attr]
    assert forfeits == [1, 1, 3], (
        "each judged config forfeits once to the silent one; it forfeits three"
    )
