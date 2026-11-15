"""Judge refusals name what is missing, and the per-call figure rule (slice 426, Task 31)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark.diff_judge_plan import (
    JUDGE_COST_FLAG,
    JUDGE_MODEL_FLAG,
    REPO_FLAG,
    RUN_CAP_FLAG,
    FigureSource,
    JudgeRefusal,
    largest_call_cost,
)
from squadron.benchmark.diff_judge_reference import ReferenceDiffReader
from squadron.config.keys import BENCHMARK_JUDGE_MODEL_KEY
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from tests.benchmark.diff_judge_run_support import World, make_world, plan_of
from tests.benchmark.slice_case_support import BENCHMARK_ID, PROJECT, judge_ref, judgment
from tests.benchmark.slice_repos import two_parent_landing
from tests.benchmark.slice_runner_support import slice_case


def _case_between(start_sha: str, reference_sha: str) -> BenchmarkCase:
    """A slice case spanning the given commits, otherwise like the fixture case."""
    base = slice_case()
    return BenchmarkCase.build(
        project_id=base.project_id,
        kind=base.kind,
        start_sha=start_sha,
        reference_sha=reference_sha,
        task_text=base.task_text,
        hidden_tests=base.hidden_tests,
        hidden_fixtures=base.hidden_fixtures,
        superseded_tests=base.superseded_tests,
        excluded_tests=base.excluded_tests,
        grader_commands=base.grader_commands,
        provenance=base.provenance,
    )


def _world(tmp_path: Path) -> World:
    return make_world(tmp_path, cases={"a": {"opus": 1, "sol": 1}})


def test_no_run_cap_names_the_flag(tmp_path: Path) -> None:
    with pytest.raises(JudgeRefusal, match=RUN_CAP_FLAG):
        plan_of(_world(tmp_path), max_cost=None)


def test_no_judge_names_the_flag_and_the_config_key(tmp_path: Path) -> None:
    with pytest.raises(JudgeRefusal) as refused:
        plan_of(_world(tmp_path), judge=None)

    assert JUDGE_MODEL_FLAG in str(refused.value)
    assert BENCHMARK_JUDGE_MODEL_KEY in str(refused.value)


def test_no_per_call_figure_names_the_flag(tmp_path: Path) -> None:
    with pytest.raises(JudgeRefusal, match=JUDGE_COST_FLAG):
        plan_of(_world(tmp_path), judge_cost=None, observed_cost=None)


def test_a_case_whose_project_has_no_repo_names_the_case_and_the_flag(tmp_path: Path) -> None:
    world = _world(tmp_path)
    case = next(iter(world.cases.values()))

    with pytest.raises(JudgeRefusal) as refused:
        plan_of(world, repo_projects=set())

    assert case.case_id in str(refused.value)
    assert REPO_FLAG in str(refused.value)


def test_a_non_positive_figure_or_cap_is_refused(tmp_path: Path) -> None:
    world = _world(tmp_path)
    with pytest.raises(JudgeRefusal, match="positive"):
        plan_of(world, max_cost=0)
    with pytest.raises(JudgeRefusal, match="positive"):
        plan_of(world, judge_cost=-1.0)


def test_a_tip_sha_missing_from_the_repo_refuses_naming_the_case_and_the_sha(
    tmp_path: Path,
) -> None:
    built = two_parent_landing(tmp_path / "repo")
    missing = "d" * 40
    case = _case_between(built.landing.fork, missing)
    reader = ReferenceDiffReader(SubprocessRunner(), {PROJECT.value: built.repo}, 30.0)

    with pytest.raises(JudgeRefusal) as refused:
        reader(case)

    assert case.case_id in str(refused.value)
    assert missing in str(refused.value)


def test_the_reference_diff_is_start_to_tip_from_the_checkout(tmp_path: Path) -> None:
    built = two_parent_landing(tmp_path / "repo")
    case = _case_between(built.landing.fork, built.landing.tip)
    reader = ReferenceDiffReader(SubprocessRunner(), {PROJECT.value: built.repo}, 30.0)

    diff = reader(case).decode()

    assert "diff --git a/src/app.py b/src/app.py" in diff
    assert "DEVLOG.md" in diff  # the reader returns the full diff; normalization is later


def test_the_per_call_figure_is_the_largest_observed_cost_for_the_same_alias(
    tmp_path: Path,
) -> None:
    world = _world(tmp_path)
    mine = judgment(a="implreplay-a", cost=0.04)
    pricier = judgment(a="implreplay-b", cost=0.09)
    other_alias = judgment(a="implreplay-c", judge=judge_ref(alias="other"), cost=5.0)
    for item in (mine, pricier, other_alias):
        world.store.write_diff_judgment(item)

    observed = largest_call_cost(world.store.diff_judgments_for(BENCHMARK_ID, "gpt-judge"))

    assert observed == pytest.approx(0.09)
    assert (
        plan_of(world, observed_cost=observed, judge_cost=None).figure_source
        is FigureSource.MAX_OBSERVED
    )
    assert plan_of(world, observed_cost=observed, judge_cost=None).per_call_usd == pytest.approx(0.09)


def test_the_judge_cost_flag_is_used_when_no_judgment_has_a_figure(tmp_path: Path) -> None:
    plan = plan_of(_world(tmp_path), observed_cost=largest_call_cost([]), judge_cost=0.07)

    assert plan.figure_source is FigureSource.FLAG
    assert plan.per_call_usd == pytest.approx(0.07)


def test_planning_dispatches_and_writes_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    world = _world(tmp_path)

    with caplog.at_level(logging.WARNING):
        plan_of(world)

    assert world.store.diff_judgments_for(BENCHMARK_ID) == []
    assert world.sidecars.files == {}
