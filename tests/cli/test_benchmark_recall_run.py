"""``sq benchmark recall run`` (slice 430 D6, D9, D11) with fake services."""

from __future__ import annotations

import dataclasses
import logging
import os
from pathlib import Path

import pytest

from squadron.benchmark.auth_check import AuthAnswer, AuthCheckResult
from squadron.benchmark.bench_lock import BenchmarkLock
from squadron.benchmark.recall.live_services import LiveRunServices
from squadron.benchmark.recall.recall_services import RECALL_LOCK_ID, RecallServices
from squadron.benchmark.recall.recipe_dirs import RECIPES_DIR as BENCH_RECIPES_DIR
from squadron.benchmark.recall.stage_identity import live_stage_config
from squadron.cli.commands import benchmark_recall_run
from squadron.config.keys import BENCHMARK_REVIEW_TIMEOUT_KEY
from squadron.core.process_lock import ProcessLock
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.providers.base import ProfileName
from squadron.recipes.recipe_search import shipped_recipes_dir
from tests.benchmark.recall.committed import REPO_ROOT, add_committed_sets, proof_runner
from tests.benchmark.recall.fixtures.bug_repo.build import BuiltBugRepo, build
from tests.benchmark.recall.stage_support import (
    FakeSandboxes,
    StubLeakChecker,
    harness_env,
    live_config_for,
    output_arg,
    review_document,
    sq_finding,
    write_json,
)
from tests.benchmark.recall.support import fake_services, invoke_recall
from tests.benchmark.support import RunnerCall, ScriptedRunner, ok

SQ = "/opt/sq"


@pytest.fixture
def bug_repo(tmp_path: Path) -> BuiltBugRepo:
    return build(tmp_path / "bug_repo")


def _auth(aliases, runner, root, env, sq, timeout):  # type: ignore[no-untyped-def]
    return [AuthCheckResult(ProfileName.OPENROUTER, aliases[0], AuthAnswer.YES, 0, "")]


def _runner(events: list[str]) -> ScriptedRunner:
    """``sq`` calls write a review output; anything else (the lock's ``ps``) runs for real."""

    def handler(call: RunnerCall) -> ProcessResult:
        if call.argv[0] != SQ:
            return SubprocessRunner().run(call.argv, cwd=call.cwd, timeout=call.timeout)
        events.append("call")
        write_json(output_arg(call.argv), review_document([sq_finding(1)], cost=0.01))
        return ok(call.argv)

    return ScriptedRunner(handler)


def _services(
    tmp_path: Path, events: list[str], sandboxes: FakeSandboxes | None = None, **live: object
) -> RecallServices:
    runner = _runner(events)
    base = fake_services(tmp_path, runner)
    fields = {
        "harness_env": harness_env(tmp_path),
        "sq_path": lambda: SQ,
        "auth_check": _auth,
        "auth_timeout": lambda: 5.0,
        "leak_checker": lambda runner: StubLeakChecker(),
        "leak_judgeable": lambda profile: True,
        "config_for": live_config_for,
        "sandboxes": lambda context, root: sandboxes or FakeSandboxes(tmp_path / "tree"),
        **live,
    }
    timeout = {BENCHMARK_REVIEW_TIMEOUT_KEY: 600}
    return dataclasses.replace(
        base, live=LiveRunServices(**fields), read_config=lambda key: timeout.get(key)
    )  # type: ignore[arg-type]


def _add_fixture(services: RecallServices, bug_repo: BuiltBugRepo) -> None:
    result = invoke_recall(services, "cases", "add", str(bug_repo.case_file), "--set", "fixture")
    assert result.exit_code == 0, result.output


def _recipe(tmp_path: Path) -> Path:
    path = tmp_path / "rev.yaml"
    path.write_text("name: rev\nreviewers: [rev]\n", encoding="utf-8")
    return path


def _run(services: RecallServices, recipe: Path, *extra: str):  # type: ignore[no-untyped-def]
    return invoke_recall(services, "run", "--set", "fixture", "--recipe", str(recipe), *extra)


def test_bound_printed_before_the_first_call_then_rerun_has_nothing(
    tmp_path: Path, bug_repo: BuiltBugRepo, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    services = _services(tmp_path, events)
    _add_fixture(services, bug_repo)
    real_render = benchmark_recall_run.render_bound

    def recording_render(bound):  # type: ignore[no-untyped-def]
        events.append("bound")
        return real_render(bound)

    monkeypatch.setattr(benchmark_recall_run, "render_bound", recording_render)
    result = _run(services, _recipe(tmp_path), "--runs", "2", "--max-cost", "1", "--call-cost", "0.01")
    assert result.exit_code == 0, result.output
    assert events == ["bound", "call", "call"]
    assert "auth openrouter (rev): yes" in result.output
    assert "→ at most $0.03 (from --call-cost), capped at $1.00" in result.output
    again = _run(services, _recipe(tmp_path), "--runs", "2", "--max-cost", "1")
    assert again.exit_code == 0 and "0 stages to run" in again.output
    assert events.count("call") == 2


def test_shipped_recipe_on_nonsquadron_prints_bound_and_makes_no_call(tmp_path: Path) -> None:
    events: list[str] = []
    missing = FakeSandboxes(tmp_path / "tree")
    services = _services(tmp_path, events, config_for=live_stage_config, sandboxes=missing)
    services = dataclasses.replace(services, process_runner=proof_runner())
    add_committed_sets(services)
    missing.failures.update({case.name: "source repo missing" for case in services.store.list_cases()})
    recipe = str(shipped_recipes_dir() / "haiku-sol-luna.yaml")
    result = invoke_recall(
        services, "run", "--set", "real-bugs-nonsquadron", "--recipe", recipe,
        "--max-cost", "25", "--max-plan-calls", "14", "--call-cost", "0.5",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    # 14 cases x 2 reviewers x (1 review + 1 luna-r comb) = 56; the 14 sol reviews are plan-billed.
    assert "56 stages to run" in result.output and "plan-billed calls: 14, cap 14" in result.output
    assert events == []


def test_recipe_by_name_runs_sol_r_variant_with_no_plan_calls(tmp_path: Path) -> None:
    events: list[str] = []
    missing = FakeSandboxes(tmp_path / "tree")
    services = _services(tmp_path, events, config_for=live_stage_config, sandboxes=missing)
    services = dataclasses.replace(services, process_runner=proof_runner(), repo_root=REPO_ROOT)
    add_committed_sets(services)
    missing.failures.update({case.name: "source repo missing" for case in services.store.list_cases()})
    result = invoke_recall(
        services, "run", "--set", "real-bugs-nonsquadron", "--recipe", "haiku-solr-luna",
        "--max-cost", "25", "--call-cost", "0.5",
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "56 stages to run" in result.output and "plan-billed" not in result.output
    assert events == []


def test_exit_1_when_refused(tmp_path: Path, bug_repo: BuiltBugRepo) -> None:
    services = _services(tmp_path, [])
    _add_fixture(services, bug_repo)
    no_cost = _run(services, _recipe(tmp_path), "--call-cost", "0.01")
    assert no_cost.exit_code == 1 and "--max-cost" in no_cost.output
    no_timeout = dataclasses.replace(services, read_config=lambda key: None)
    refused = _run(no_timeout, _recipe(tmp_path), "--max-cost", "1", "--call-cost", "0.01")
    assert refused.exit_code == 1 and BENCHMARK_REVIEW_TIMEOUT_KEY in refused.output


def test_exit_2_when_capped(tmp_path: Path, bug_repo: BuiltBugRepo) -> None:
    events: list[str] = []
    services = _services(tmp_path, events)
    _add_fixture(services, bug_repo)
    result = _run(
        services, _recipe(tmp_path), "--runs", "4", "--max-cost", "0.000001", "--call-cost", "0.01"
    )
    assert result.exit_code == 2, result.output
    assert events == ["call"]
    assert "3 stages left" in result.output


def test_lock_held_by_a_live_process_is_refused(
    tmp_path: Path, bug_repo: BuiltBugRepo, caplog: pytest.LogCaptureFixture
) -> None:
    services = _services(tmp_path, [])
    _add_fixture(services, bug_repo)
    with BenchmarkLock.acquire(services.bench_root, RECALL_LOCK_ID, SubprocessRunner()):
        with caplog.at_level(logging.ERROR):
            result = _run(services, _recipe(tmp_path), "--max-cost", "1", "--call-cost", "0.01")
    assert result.exit_code == 1
    assert f"pid {os.getpid()}" in result.output
    assert any(
        r.levelno == logging.ERROR and str(os.getpid()) in r.getMessage() for r in caplog.records
    )


def test_lock_of_a_dead_owner_is_taken_over(
    tmp_path: Path, bug_repo: BuiltBugRepo, caplog: pytest.LogCaptureFixture
) -> None:
    events: list[str] = []
    services = _services(tmp_path, events)
    _add_fixture(services, bug_repo)
    services.bench_root.mkdir(parents=True, exist_ok=True)
    dead = ProcessLock(pid=os.getpid(), started_at=1.0)  # this pid, but not this process's start
    (services.bench_root / f"{RECALL_LOCK_ID}.lock").write_text(dead.to_json())
    with caplog.at_level(logging.WARNING):
        result = _run(services, _recipe(tmp_path), "--max-cost", "1", "--call-cost", "0.01")
    assert result.exit_code == 0, result.output
    assert any(
        r.levelno == logging.WARNING and "taking over the lock" in r.getMessage()
        for r in caplog.records
    )
    assert events == ["call"]


def test_recipe_named_without_path_is_found_in_the_benchmark_dir(
    tmp_path: Path, bug_repo: BuiltBugRepo
) -> None:
    events: list[str] = []
    services = _services(tmp_path, events)
    _add_fixture(services, bug_repo)
    bench_dir = tmp_path / BENCH_RECIPES_DIR
    bench_dir.mkdir(parents=True)
    _recipe(bench_dir)
    result = invoke_recall(
        services, "run", "--set", "fixture", "--recipe", "rev", "--max-cost", "1", "--call-cost", "0.01"
    )
    assert result.exit_code == 0, result.output
    assert events == ["call"]
