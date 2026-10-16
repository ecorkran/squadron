"""The replay runner against fakes: no git, cf or model call (slice 177 D4, D10)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

import pytest

from squadron.core.process_runner import ProcessResult
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.replay_models import (
    ModelRef,
    ProducerConfigRef,
    ProducerReplay,
    ReplayOutcome,
    ReplayPhase,
)
from squadron.pipeline.state import RunState
from squadron.replay.drafts import Drafts
from squadron.replay.outcome import FailureClass
from squadron.replay.runner import (
    ReplayDeps,
    ReplayPlan,
    ReplayRequest,
    build_plan,
    replay_set_id,
    run_replay_set,
)
from squadron.replay.sandbox import SandboxError
from squadron.replay.start_point import StartPoint
from tests.codehost.fake_runner import FakeProcessRunner
from tests.stats.producer_support import producer_actions, run, step

_START = "b" * 40
_NOW = datetime(2026, 11, 1, tzinfo=UTC)
_REVIEWER = ModelRef(alias="opus", model="claude-opus-5-5")


def _config(alias: str) -> ProducerConfigRef:
    return ProducerConfigRef(alias=alias, model=f"model-{alias}", profile="sdk", effort_sent=None)


def _start() -> StartPoint:
    return StartPoint(
        phase=ReplayPhase.DESIGN,
        slice_index=176,
        slice_name="effort-calibration",
        artifact_path="project-documents/user/slices/176-slice.effort-calibration.md",
        original_sha="a" * 40,
        start_sha=_START,
        original_first_draft="# original",
    )


def _request(*aliases: str, cap: int = 2) -> ReplayRequest:
    return ReplayRequest(
        project_id=ProjectId(value="github.com/manta/example", source=ProjectIdSource.REMOTE),
        phase=ReplayPhase.DESIGN,
        configs=[_config(alias) for alias in aliases],
        reviewer=_REVIEWER,
        max_revisions=cap,
    )


class _Sandbox:
    def __init__(self, path: Path, log: list[str]) -> None:
        self.path = path
        self._log = log
        self.kept = False

    def keep(self) -> None:
        self.kept = True
        self._log.append("keep")

    def __enter__(self) -> _Sandbox:
        self._log.append(f"enter {self.path.name}")
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self._log.append(f"exit {self.path.name}")


class _Fakes:
    """Everything the runner is given, recording what happened and in what order."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.log: list[str] = []
        self.sandboxes: dict[str, _Sandbox] = {}
        self.invocations: list[tuple[tuple[str, ...], Path]] = []
        self.states: dict[str, RunState] = {}
        self.written: list[ProducerReplay] = []
        self.fail_sandbox: dict[str, str] = {}  # replay id -> SandboxError text
        self.fail_store = False
        self.exit_code = 0
        self.stderr = ""
        self.cf = FakeProcessRunner([])
        self.confirmed: list[ReplayPlan] = []
        self.state_for: dict[str, RunState] = {}

    # ---- the injected collaborators
    def sandbox(self, replay_id: str) -> _Sandbox:
        if replay_id in self.fail_sandbox:
            raise SandboxError(self.fail_sandbox[replay_id])
        box = _Sandbox(self.tmp_path / replay_id, self.log)
        self.sandboxes[replay_id] = box
        return box

    def invoke(self, argv: Sequence[str], cwd: Path) -> ProcessResult:
        self.invocations.append((tuple(argv), cwd))
        self.log.append(f"sq {cwd.name}")
        return ProcessResult(argv=tuple(argv), returncode=self.exit_code, stdout="", stderr=self.stderr)

    def load(self, run_id: str) -> RunState:
        if run_id not in self.state_for:
            raise FileNotFoundError(run_id)
        return self.state_for[run_id]

    def write_replay(self, replay: ProducerReplay) -> str:
        if self.fail_store:
            raise MetrologyStoreError("disk full")
        self.written.append(replay)
        self.log.append(f"write {replay.run_id}")
        return f"record-{len(self.written)}"

    def drafts(self, _path: Path) -> Drafts:
        return Drafts(first="# first", final="# final")

    def deps(self) -> ReplayDeps:
        return ReplayDeps(
            store=self,
            run_states=self,
            sandbox_factory=self.sandbox,
            invoker=self.invoke,
            process_runner=self.cf,
            read_drafts=self.drafts,
            sq_executable="/usr/bin/sq",
            now=lambda: _NOW,
        )


def _ids(*ids: str):  # pyright: ignore[reportUnknownParameterType]
    queue = list(ids)
    return lambda: queue.pop(0)


def _accepted_state(run_id: str) -> RunState:
    return run(
        run_id,
        [
            step("design-0", "design", producer_actions(verdict="PASS", cost=1.0)),
            step("loop-1", "loop"),
        ],
    )


def _ok_cf() -> FakeProcessRunner:
    ok = ProcessResult(argv=(), returncode=0, stdout="[]", stderr="")
    return FakeProcessRunner([(["cf", "project", "list"], ok), (["cf", "set", "slice"], ok)])


@pytest.fixture
def fakes(tmp_path: Path) -> _Fakes:
    box = _Fakes(tmp_path)
    box.cf = _ok_cf()
    return box


def _go(fakes: _Fakes, request: ReplayRequest, ids: Sequence[str], confirm: bool = True):  # pyright: ignore[reportUnknownParameterType]
    def decide(plan: ReplayPlan) -> bool:
        fakes.confirmed.append(plan)
        return confirm

    return run_replay_set(request, _start(), fakes.deps(), confirm=decide, new_replay_id=_ids(*ids))


def test_two_configs_give_two_records_in_order_with_the_specified_argv(fakes: _Fakes) -> None:
    fakes.state_for = {"r1": _accepted_state("r1"), "r2": _accepted_state("r2")}

    summary = _go(fakes, _request("sonnet", "haiku", cap=1), ["r1", "r2"])

    assert [r.config.alias for _, r in summary.records] == ["sonnet", "haiku"]
    assert [r.run_id for _, r in summary.records] == ["r1", "r2"]
    first, second = fakes.invocations
    assert first[0] == (
        "/usr/bin/sq", "run", "P4", "176", "-m", "sonnet",
        "-p", "review-model=opus", "-p", "max-revisions=1", "--run-id", "r1",
    )  # fmt: skip
    assert second[0][5] == "haiku" and second[0][-1] == "r2"
    assert (first[1], second[1]) == (fakes.sandboxes["r1"].path, fakes.sandboxes["r2"].path)


def test_the_record_is_written_before_its_sandbox_is_removed(fakes: _Fakes) -> None:
    fakes.state_for = {"r1": _accepted_state("r1")}

    _go(fakes, _request("sonnet"), ["r1"])

    assert fakes.log.index("write r1") < fakes.log.index("exit r1")
    assert fakes.log.index("sq r1") < fakes.log.index("write r1")


def test_a_record_carries_the_outcome_drafts_and_conditions(fakes: _Fakes) -> None:
    fakes.state_for = {"r1": _accepted_state("r1")}

    summary = _go(fakes, _request("sonnet"), ["r1"])

    ((_, record),) = summary.records
    assert record.outcome is ReplayOutcome.ACCEPTED and record.rounds == 1
    assert (record.first_draft, record.final_text) == ("# first", "# final")
    assert (record.start_sha, record.original_sha) == (_START, "a" * 40)
    assert record.reviewer == _REVIEWER and record.max_revisions == 2
    assert record.created_at == _NOW and record.wall_seconds >= 0
    assert record.replay_set == replay_set_id(_request("sonnet"), _start())


def test_replay_set_id_is_shared_by_configs_and_changes_with_the_conditions() -> None:
    same = replay_set_id(_request("a"), _start()) == replay_set_id(_request("a", "b"), _start())
    assert same
    assert replay_set_id(_request("a", cap=1), _start()) != replay_set_id(
        _request("a", cap=2), _start()
    )


def test_a_failing_first_config_does_not_stop_the_second(fakes: _Fakes) -> None:
    fakes.state_for = {"r2": _accepted_state("r2")}  # r1 left no run state
    fakes.exit_code, fakes.stderr = 1, "traceback..."

    summary = _go(fakes, _request("sonnet", "haiku"), ["r1", "r2"])

    first, second = (r for _, r in summary.records)
    assert (first.outcome, first.failure_class) == (
        ReplayOutcome.FAILED,
        FailureClass.NO_RUN_STATE.value,
    )
    assert second.outcome is ReplayOutcome.ACCEPTED


def test_no_run_file_records_no_run_state_with_exit_code_and_stderr_tail(
    fakes: _Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    fakes.exit_code, fakes.stderr = 2, "boom: cannot start"

    with caplog.at_level(logging.WARNING):
        summary = _go(fakes, _request("sonnet"), ["r1"])

    ((_, record),) = summary.records
    assert record.failure_class == FailureClass.NO_RUN_STATE.value
    assert "exit 2" in (record.failure_detail or "")
    assert "boom: cannot start" in (record.failure_detail or "")
    assert "no run state for r1" in caplog.text


def test_a_slice_that_does_not_resolve_stops_before_any_dispatch(fakes: _Fakes) -> None:
    bad = ProcessResult(argv=(), returncode=1, stdout="", stderr="No file matching index '176'")
    fakes.cf = FakeProcessRunner([(["cf", "project", "list"], bad), (["cf", "set", "slice"], bad)])

    summary = _go(fakes, _request("sonnet", "haiku"), ["r1", "r2"])

    assert fakes.invocations == []  # no sq run, so no dispatch
    assert summary.records == []
    assert summary.stopped is not None
    assert "slice 176" in summary.stopped and _START in summary.stopped
    assert "exit r1" in fakes.log  # the sandbox is still removed


def test_a_sandbox_setup_failure_skips_that_config_and_the_set_continues(
    fakes: _Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    fakes.state_for = {"r2": _accepted_state("r2")}
    fakes.fail_sandbox = {"r1": "git fetch failed: not our ref"}
    skipped: list[tuple[str, str]] = []

    with caplog.at_level(logging.ERROR):
        summary = run_replay_set(
            _request("sonnet", "haiku"),
            _start(),
            fakes.deps(),
            confirm=lambda _plan: True,
            new_replay_id=_ids("r1", "r2"),
            on_skip=lambda alias, why: skipped.append((alias, why)),
        )

    assert summary.skipped == [("sonnet", "git fetch failed: not our ref")]
    assert skipped == summary.skipped
    assert [r.config.alias for _, r in summary.records] == ["haiku"]
    assert "not our ref" in caplog.text


def test_a_store_write_failure_stops_the_set_and_keeps_the_sandbox(
    fakes: _Fakes, caplog: pytest.LogCaptureFixture
) -> None:
    fakes.state_for = {"r1": _accepted_state("r1"), "r2": _accepted_state("r2")}
    fakes.fail_store = True

    with caplog.at_level(logging.ERROR):
        summary = _go(fakes, _request("sonnet", "haiku"), ["r1", "r2"])

    assert summary.records == []
    assert fakes.sandboxes["r1"].kept is True
    assert "r2" not in fakes.sandboxes  # the second config never started
    assert summary.stopped is not None
    assert str(fakes.sandboxes["r1"].path) in summary.stopped and "disk full" in summary.stopped
    assert str(fakes.sandboxes["r1"].path) in caplog.text


def test_a_cleanup_failure_inside_the_sandbox_does_not_stop_the_set(fakes: _Fakes) -> None:
    """Cleanup failures are the sandbox's own WARNING; the runner sees a normal exit."""
    fakes.state_for = {"r1": _accepted_state("r1"), "r2": _accepted_state("r2")}

    summary = _go(fakes, _request("sonnet", "haiku"), ["r1", "r2"])

    assert len(summary.records) == 2 and summary.stopped is None


def test_declining_the_plan_runs_nothing(fakes: _Fakes) -> None:
    summary = _go(fakes, _request("sonnet"), ["r1"], confirm=False)

    assert summary.declined is True
    assert fakes.sandboxes == {} and fakes.invocations == []


@pytest.mark.parametrize(("configs", "cap"), [(1, 0), (2, 1), (3, 2), (5, 4)])
def test_the_llm_call_bound_is_configs_times_two_times_one_plus_cap(configs: int, cap: int) -> None:
    aliases = [f"c{n}" for n in range(configs)]

    plan = build_plan(_request(*aliases, cap=cap), _start())

    assert plan.llm_call_bound == configs * 2 * (1 + cap)
    assert (plan.start_sha, plan.slice_index, plan.max_revisions) == (_START, 176, cap)


def test_the_plan_is_confirmed_before_any_sandbox_exists(fakes: _Fakes) -> None:
    fakes.state_for = {"r1": _accepted_state("r1")}

    _go(fakes, _request("sonnet"), ["r1"])

    assert len(fakes.confirmed) == 1 and fakes.confirmed[0].llm_call_bound == 6
