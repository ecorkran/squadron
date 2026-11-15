"""``SliceCaseRunner.run``: registration under the scrubbed home, then producer-only ``P6``
(slice 426, Task 24)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark.case_runners import FixCaseRunner
from squadron.benchmark.slice_runner import (
    CF_TOOLS,
    SLICE_BRANCH_SUFFIX,
    SLICE_PIPELINE,
    SLICE_PRODUCER_STEP,
    SliceCaseRunner,
)
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind, CaseProvenance
from squadron.pr.branch import parse_slice_branch
from squadron.replay.history_free_sandbox import SandboxError
from tests.benchmark.slice_qualify_support import typical_setup
from tests.benchmark.slice_repos import two_parent_landing
from tests.benchmark.slice_runner_support import (
    CAPS,
    CONFIG,
    SLICE_INDEX,
    SQ_PATH,
    CfRecorder,
    Events,
    Invoker,
    SandboxDouble,
    make_tools_dir,
    registration_factory,
    slice_case,
)


def _runner(tmp_path: Path, recorder: CfRecorder, invoker: Invoker) -> SliceCaseRunner:
    setup = typical_setup(tmp_path / "setup", two_parent_landing(tmp_path / "repo"))
    return SliceCaseRunner(
        sq_path=SQ_PATH,
        invoker=invoker,
        runner=SubprocessRunner(),
        registration_for=registration_factory(recorder),
        qualify_deps=setup.deps,
        candidate_for=lambda case: setup.candidate,
    )


def _sandbox(
    tmp_path: Path, *, detached: bool, name: str = "sandbox-1", branch: str = "main"
) -> SandboxDouble:
    return SandboxDouble(
        tmp_path / "sandboxes", name, make_tools_dir(tmp_path), detached=detached, branch=branch
    )


@pytest.fixture
def events() -> Events:
    return Events()


def test_the_producer_runs_with_the_exact_argv_cwd_and_scrubbed_env(
    tmp_path: Path, events: Events
) -> None:
    recorder, invoker = CfRecorder(events), Invoker(events)
    sandbox = _sandbox(tmp_path, detached=True)

    _runner(tmp_path, recorder, invoker).run(slice_case(), CONFIG, sandbox, CAPS, "implreplay-r1")

    ((argv, cwd, env),) = invoker.calls
    assert argv == [
        SQ_PATH, "run", "P6", str(SLICE_INDEX), "-m", "opus", "--producer-only",
        "--max-cost", "8.0", "--run-id", "implreplay-r1",
    ]  # fmt: skip
    assert cwd == sandbox.tree
    assert env is not None
    assert env["HOME"] == str(sandbox.home)
    assert (sandbox.home / "bin" / "cf").is_symlink()
    assert (sandbox.home / "bin" / "node").is_symlink()
    assert sandbox.tool_requests == [CF_TOOLS]


def test_registration_happens_before_the_producer_and_under_the_same_env(
    tmp_path: Path, events: Events
) -> None:
    recorder, invoker = CfRecorder(events), Invoker(events)
    sandbox = _sandbox(tmp_path, detached=True)

    _runner(tmp_path, recorder, invoker).run(slice_case(), CONFIG, sandbox, CAPS, "implreplay-r1")

    assert events.items[-1] == "sq run"
    assert [event.split()[1] for event in events.items[:-1]] == ["init", "config", "set"]
    producer_env = invoker.calls[0][2]
    assert all(call.env == producer_env and call.replace_env for call in recorder.calls)
    assert {call.cwd for call in recorder.calls} == {str(sandbox.tree)}


def test_a_tree_on_a_branch_registers_that_branch_and_creates_none(
    tmp_path: Path, events: Events
) -> None:
    recorder, invoker = CfRecorder(events), Invoker(events)
    sandbox = _sandbox(tmp_path, detached=False, branch=f"{SLICE_INDEX}-slice.existing")

    _runner(tmp_path, recorder, invoker).run(slice_case(), CONFIG, sandbox, CAPS, "implreplay-r1")

    assert sandbox.created_branches == []
    set_branch = next(
        c for c in recorder.calls if c.argv[1:4] == ("config", "set", "git.integration_branch")
    )
    assert set_branch.argv[-1] == f"{SLICE_INDEX}-slice.existing"


def test_a_detached_tree_gets_a_slice_branch_and_registers_it(tmp_path: Path, events: Events) -> None:
    recorder, invoker = CfRecorder(events), Invoker(events)
    sandbox = _sandbox(tmp_path, detached=True, name="sandbox-9")

    _runner(tmp_path, recorder, invoker).run(slice_case(), CONFIG, sandbox, CAPS, "implreplay-r1")

    expected = f"{SLICE_INDEX}-slice.{SLICE_BRANCH_SUFFIX}sandbox-9"
    assert sandbox.created_branches == [expected]
    assert sandbox.branch() == expected
    assert parse_slice_branch(expected) == SLICE_INDEX  # what --producer-only checks
    set_branch = next(
        c for c in recorder.calls if c.argv[1:4] == ("config", "set", "git.integration_branch")
    )
    assert set_branch.argv[-1] == expected


def test_a_failing_registration_is_a_harness_absence_with_an_error_log_and_no_producer(
    tmp_path: Path, events: Events, caplog: pytest.LogCaptureFixture
) -> None:
    recorder, invoker = CfRecorder(events, fail_prefix=("set", "arch")), Invoker(events)
    sandbox = _sandbox(tmp_path, detached=True)

    with caplog.at_level(logging.ERROR), pytest.raises(SandboxError, match="cf exploded"):
        _runner(tmp_path, recorder, invoker).run(slice_case(), CONFIG, sandbox, CAPS, "implreplay-r1")

    assert invoker.calls == []
    assert any(
        r.levelno == logging.ERROR and "slice 403" in r.getMessage() and "cf exploded" in r.getMessage()
        for r in caplog.records
    )


def test_no_cf_project_rm_is_ever_issued(tmp_path: Path, events: Events) -> None:
    recorder, invoker = CfRecorder(events), Invoker(events)
    sandbox = _sandbox(tmp_path, detached=True)

    _runner(tmp_path, recorder, invoker).run(slice_case(), CONFIG, sandbox, CAPS, "implreplay-r1")

    assert not any(call.argv[1:3] == ("project", "rm") for call in recorder.calls)
    assert not any(call.argv[1:3] == ("project", "list") for call in recorder.calls)


def test_a_fix_case_runner_never_asks_for_extra_tools(tmp_path: Path, events: Events) -> None:
    sandbox = _sandbox(tmp_path, detached=True)
    sandbox.output_dir.mkdir()
    fix_case = BenchmarkCase.build(
        project_id=slice_case().project_id,
        kind=CaseKind.FIX,
        start_sha="f" * 40,
        reference_sha="a" * 40,
        task_text="issue",
        hidden_tests=("t::x",),
        hidden_fixtures=(),
        superseded_tests=(),
        excluded_tests=(),
        grader_commands=(),
        provenance=CaseProvenance(
            source_ref="owner/repo#12", created_at=slice_case().provenance.created_at, built_by="t"
        ),
    )
    runner = FixCaseRunner(
        sq_path=SQ_PATH,
        invoker=Invoker(events),
        qualify_deps=object(),  # type: ignore[arg-type]
        candidate_for=lambda case: None,  # type: ignore[arg-type,return-value]
    )

    runner.run(fix_case, CONFIG, sandbox, CAPS, "implreplay-f1")

    assert sandbox.tool_requests == [()]
    assert not (sandbox.home / "bin" / "cf").exists()


def test_the_replay_record_names_p6_and_implement(tmp_path: Path, events: Events) -> None:
    runner = _runner(tmp_path, CfRecorder(events), Invoker(events))

    assert (runner.pipeline, runner.producer_step) == (SLICE_PIPELINE, SLICE_PRODUCER_STEP)
    assert (SLICE_PIPELINE, SLICE_PRODUCER_STEP) == ("P6", "implement")


def test_a_config_without_a_profile_is_refused_before_anything_runs(
    tmp_path: Path, events: Events
) -> None:
    recorder, invoker = CfRecorder(events), Invoker(events)
    sandbox = _sandbox(tmp_path, detached=True)
    unresolved = CONFIG.__class__(alias="x", model="m", profile=None, effort_configured=None)

    with pytest.raises(ValueError, match="no provider profile"):
        _runner(tmp_path, recorder, invoker).run(slice_case(), unresolved, sandbox, CAPS, "r")

    assert recorder.calls == [] and invoker.calls == []
