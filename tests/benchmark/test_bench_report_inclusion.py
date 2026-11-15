"""Report rows and case inclusion (slice 425 Task 37, D13)."""

from __future__ import annotations

import typing
from pathlib import Path

import pytest

from squadron.benchmark import report_models
from squadron.benchmark.report_models import BenchmarkReport
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.grade_models import GradeAbsence
from squadron.metrology.replay_models import ProducerConfigRef, PromptIdentity
from tests.benchmark.report_support import ReportWorld, config, make_world

SAMPLES = 2


def six_cases(world: ReportWorld) -> list[BenchmarkCase]:
    return [world.add_case(f"case-{i}") for i in range(6)]


def fill(world: ReportWorld, cases: list[BenchmarkCase], *configs: ProducerConfigRef) -> None:
    for case in cases:
        for cfg in configs:
            for sample in range(SAMPLES):
                world.add_sample(case, cfg, sample)


def objective_labels(report: BenchmarkReport) -> list[str]:
    data = report.tables[0].data["objective"]
    return [row["config"]["label"] for row in data]


def test_two_replays_differing_only_in_tool_use_give_two_rows(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases, config("opus", tool_use=True), config("opus", tool_use=False))
    assert len(world.build().tables[0].data["objective"]) == 2


def test_two_replays_differing_only_in_max_output_tokens_give_two_rows(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases, config("opus"), config("opus", max_output_tokens=4096))
    assert len(world.build().tables[0].data["objective"]) == 2


def test_two_aliases_with_one_identity_give_one_row(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    same_identity = {"model": "shared-model"}
    # Samples 0 and 1 of every case come from two different aliases of one identity.
    for case in cases:
        world.add_sample(case, config("first-alias", **same_identity), 0)
        world.add_sample(case, config("second-alias", **same_identity), 1)
    report = world.build()
    assert len(report.tables[0].data["objective"]) == 1
    assert report.cases_compared == 6
    assert objective_labels(report) == ["first-alias"]  # the label is the first alias seen


def test_one_sample_recorded_twice_for_one_identity_is_an_error(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    case = world.add_case("case-0")
    world.add_sample(case, config("first-alias", model="shared-model"), 0)
    world.add_sample(case, config("second-alias", model="shared-model"), 0)
    with pytest.raises(ValueError, match="recorded twice"):
        world.build()


def prompt(sha: str) -> PromptIdentity:
    return PromptIdentity(
        sha256=sha * 64, source="builtin", squadron_version="1", cf_version=None, guide_version=None
    )


def test_a_split_prompt_identity_gives_two_rows_and_a_warning(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    for case in cases:
        world.add_sample(case, config("opus"), 0, replay={"prompt": prompt("a")})
        world.add_sample(case, config("opus"), 1, replay={"prompt": prompt("b")})
    report = world.build()
    assert len(report.tables[0].data["objective"]) == 2
    assert any("prompt identity" in warning for warning in report.warnings)
    assert report.tables[0].data["paired"] == []  # a split config is shown, never compared


def test_a_missing_sample_excludes_the_case_as_incomplete(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases, config("opus"), config("sol"))
    lost = {
        record_id
        for record_id, replay in world.replays
        if replay.config.alias == "sol" and replay.sample == 1 and replay.case_id == cases[0].case_id
    }
    assert len(lost) == 1
    world.replays = [item for item in world.replays if item[0] not in lost]
    world.grades = [g for g in world.grades if g.replay_id not in lost]
    report = world.build()
    assert report.exclusions == {"incomplete": 1}
    assert report.cases_compared == 5


def test_a_replay_not_yet_graded_makes_its_case_incomplete(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases[1:], config("opus"))
    world.add_sample(cases[0], config("opus"), 0)
    world.add_sample(cases[0], config("opus"), 1, graded=False)
    report = world.build()
    assert report.exclusions == {"incomplete": 1}


def test_a_harness_replay_absence_excludes_the_case_under_its_reason(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases[1:], config("opus"))
    world.add_sample(cases[0], config("opus"), 0)
    world.add_sample(
        cases[0],
        config("opus"),
        1,
        replay={"outcome": ProducerOutcome.NO_RUN_STATE, "absence": AbsenceClass.HARNESS},
    )
    assert world.build().exclusions == {"harness_replay": 1}


def test_a_harness_grade_absence_excludes_the_case_under_its_reason(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases[1:], config("opus"))
    world.add_sample(cases[0], config("opus"), 0)
    world.add_sample(
        cases[0],
        config("opus"),
        1,
        grade_absence=(GradeAbsence.REVIEW_FAILED, AbsenceClass.HARNESS),
    )
    assert world.build().exclusions == {"harness_grade": 1}


def test_a_config_absence_keeps_the_case_and_counts_as_a_fail(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases[1:], config("opus"))
    world.add_sample(cases[0], config("opus"), 0)
    world.add_sample(
        cases[0],
        config("opus"),
        1,
        replay={"outcome": ProducerOutcome.COST_CAP, "absence": AbsenceClass.CONFIG},
    )
    report = world.build()
    assert report.exclusions == {}
    row = report.tables[0].data["objective"][0]
    assert row["config_absences"] == {"cost_cap": 1}
    assert row["n_cases"] == 6


def test_grades_under_an_older_identity_appear_only_in_the_count(tmp_path: Path) -> None:
    from tests.benchmark.test_grade_identity import make_identity
    from tests.benchmark.test_grade_records import make_implementation

    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases, config("opus"))
    older = make_identity(grader_version=0)
    for record_id, replay in list(world.replays):
        world.grades.append(
            make_implementation(
                replay_id=record_id,
                benchmark_id=world.run.benchmark_id,
                case_id=replay.case_id,
                grader=older,
            )
        )
    report = world.build()
    assert report.older_identity_grades == 12
    assert len(report.tables[0].data["objective"]) == 1
    assert report.cases_compared == 6


def test_a_failed_replay_with_no_effort_stamp_is_counted_by_failure_class_not_a_row(
    tmp_path: Path,
) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases, config("opus"))
    world.add_sample(
        cases[0],
        config("opus", effort_sent=None),
        0,
        replay={"outcome": ProducerOutcome.PRODUCER_FAILED, "absence": AbsenceClass.CONFIG},
    )
    report = world.build()
    assert report.unstamped_replays == {"producer_failed": 1}
    assert [row["config"]["effort_sent"] for row in report.tables[0].data["objective"]] == ["high"]


def test_a_committed_replay_that_sent_no_effort_is_an_honest_not_sent_row(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cases = six_cases(world)
    fill(world, cases, config("quiet", effort_sent=None))
    row = world.build().tables[0].data["objective"][0]
    assert row["config"]["effort_sent"] is None


FORBIDDEN_WORDS = ("score", "composite", "overall", "rank", "combined", "aggregate")


def test_no_field_name_or_type_on_the_report_models_is_a_composite() -> None:
    models = [
        obj
        for obj in vars(report_models).values()
        if isinstance(obj, type) and issubclass(obj, report_models.BaseModel)
    ]
    assert BenchmarkReport in models
    for model in models:
        for name in model.model_fields:
            assert not any(word in name for word in FORBIDDEN_WORDS), f"{model.__name__}.{name}"
    hints = typing.get_type_hints(BenchmarkReport)
    assert not any("Score" in str(hint) for hint in hints.values())
