"""Re-qualification routing and the slice runner's place on the case-kind seam
(slice 426, Task 25)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from squadron.benchmark import case_runners, slice_runner
from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.case_runners import case_runner_for, register_case_runner
from squadron.benchmark.leak_rule_source import LeakRuleSource, installed_package_location
from squadron.benchmark.slice_discovery import SliceCandidate
from squadron.benchmark.slice_qualify import qualify_slice_candidate
from squadron.benchmark.slice_runner import SliceCaseRunner
from squadron.benchmark.slice_runner_wiring import register_slice_runner
from squadron.core.process_runner import ProcessResult, SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind, QualificationOutcome
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.slice_case_models import SliceQualification
from squadron.metrology.snapshot_models import SourceLanguage
from tests.benchmark.slice_case_support import PROJECT, environment
from tests.benchmark.slice_qualify_support import Setup, typical_setup
from tests.benchmark.slice_repos import two_parent_landing
from tests.benchmark.slice_runner_support import (
    CfRecorder,
    Events,
    Invoker,
    SandboxDouble,
    registration_factory,
    slice_case,
)
from tests.benchmark.support import ScriptedRunner
from tests.benchmark.test_production_deps import FakeHost, handler


def _qualified_case(setup: Setup) -> BenchmarkCase:
    result = qualify_slice_candidate(setup.candidate, setup.deps)
    assert result.case is not None
    return result.case


def _slice_runner(setup: Setup, events: Events) -> SliceCaseRunner:
    return SliceCaseRunner(
        sq_path="/installed/sq",
        invoker=Invoker(events),
        runner=SubprocessRunner(),
        registration_for=registration_factory(CfRecorder(events)),
        qualify_deps=setup.deps,
        candidate_for=lambda case: setup.candidate,
    )


def test_a_matching_stored_result_is_returned_without_qualifying_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))
    case = _qualified_case(setup)
    stored = setup.qualifications.list_slice_qualifications(PROJECT)[0]
    assert stored.start_environment is not None
    calls: list[SliceCandidate] = []
    monkeypatch.setattr(
        slice_runner, "qualify_slice_candidate", lambda candidate, deps: calls.append(candidate)
    )

    verdict = _slice_runner(setup, Events()).requalify(case, stored.start_environment)

    assert verdict == stored
    assert calls == []


def test_a_mismatched_digest_qualifies_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))
    case = _qualified_case(setup)
    seen: list[SliceCandidate] = []

    def fresh(candidate: SliceCandidate, deps: object) -> object:
        seen.append(candidate)
        return qualify_slice_candidate(candidate, setup.deps)

    monkeypatch.setattr(slice_runner, "qualify_slice_candidate", fresh)

    verdict = _slice_runner(setup, Events()).requalify(case, environment("7" * 64))

    assert seen == [setup.candidate]
    assert isinstance(verdict, SliceQualification)
    assert verdict.outcome is QualificationOutcome.QUALIFIED


def test_production_registration_puts_a_slice_runner_on_the_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(case_runners, "_RUNNERS", {})
    built = two_parent_landing(tmp_path / "repo")
    store = typical_setup(tmp_path / "s", built).cases
    assert isinstance(store, BenchmarkRecordStore)
    monkeypatch.setattr("squadron.benchmark.slice_runner_wiring.derive_project_id", lambda cwd: PROJECT)

    registered = register_slice_runner(
        sq_path="/installed/sq",
        repo_root=built.repo,
        runner=SubprocessRunner(),
        store=store,
        sandbox_at=lambda sha: (_ for _ in ()).throw(AssertionError("no sandbox is built here")),
        language=SourceLanguage.PYTHON,
        repeats=3,
        git_timeout_s=30.0,
    )

    assert case_runner_for(CaseKind.SLICE) is registered
    assert isinstance(registered, SliceCaseRunner)
    assert case_runner_for(CaseKind.FIX) is None


def test_the_seam_routes_each_kind_to_its_own_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(case_runners, "_RUNNERS", {})
    setup = typical_setup(tmp_path / "s", two_parent_landing(tmp_path / "repo"))
    mine = _slice_runner(setup, Events())
    other = _slice_runner(setup, Events())
    register_case_runner(CaseKind.SLICE, mine)
    register_case_runner(CaseKind.FIX, other)

    assert case_runner_for(CaseKind.SLICE) is mine
    assert case_runner_for(CaseKind.FIX) is other


def test_a_slice_replay_gets_leak_rules_from_the_checkouts_own_remote(tmp_path: Path) -> None:
    runner = ScriptedRunner(handler())
    source = LeakRuleSource(
        runner=runner,
        repo_root=tmp_path / "checkout",
        host=FakeHost(),  # type: ignore[arg-type]
        real_home=tmp_path / "home",
        install_location=installed_package_location(),
        uv_cache=Path("/cache/uv"),
        timeout_s=5,
    )
    sandbox = SandboxDouble.__new__(SandboxDouble)
    sandbox.tree, sandbox.home, sandbox.output_dir = (
        tmp_path / "sbx",
        tmp_path / "sbx.home",
        tmp_path / "sbx.out",
    )

    rules = source.rules_for(sandbox, slice_case())  # type: ignore[arg-type]

    assert (rules.host_owner, rules.host_repo) == ("acme", "widgets")
    assert rules.distribution_name == "widget-pkg"


def test_a_checkout_with_no_served_remote_refuses_a_slice_replay(tmp_path: Path) -> None:
    def handle(call: object) -> ProcessResult:
        argv: Sequence[str] = call.argv  # type: ignore[attr-defined]
        return ProcessResult(argv=tuple(argv), returncode=0, stdout="", stderr="")

    source = LeakRuleSource(
        runner=ScriptedRunner(handle),
        repo_root=tmp_path / "checkout",
        host=FakeHost(),  # type: ignore[arg-type]
        real_home=tmp_path / "home",
        install_location=installed_package_location(),
        uv_cache=Path("/cache/uv"),
        timeout_s=5,
    )
    sandbox = SandboxDouble.__new__(SandboxDouble)
    sandbox.tree = sandbox.home = sandbox.output_dir = tmp_path / "x"

    with pytest.raises(BenchmarkRefusal, match="no code host repository"):
        source.rules_for(sandbox, slice_case())  # type: ignore[arg-type]
