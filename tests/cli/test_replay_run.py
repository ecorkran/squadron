"""``sq replay run`` with the runner core faked (slice 177 D4, D10)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.replay_models import (
    ModelRef,
    ProducerConfigRef,
    ProducerReplay,
    ReplayOutcome,
    ReplayPhase,
)
from squadron.replay.runner import ReplayPlan, ReplayRequest, ReplaySetSummary
from squadron.replay.start_point import StartPoint, StartPointError

runner = CliRunner()
_ALIASES = {
    "sonnet": {"model": "claude-sonnet-5-5", "profile": "sdk"},
    "haiku": {"model": "claude-haiku-5-5", "profile": "sdk"},
    "opus": {"model": "claude-opus-5-5", "profile": "sdk"},
}
_ARGS = [
    "replay", "run", "--phase", "design", "--slice", "176",
    "--config", "sonnet", "--config", "haiku",
    "--reviewer", "opus", "--max-revisions", "1",
]  # fmt: skip


def _start() -> StartPoint:
    return StartPoint(
        phase=ReplayPhase.DESIGN,
        slice_index=176,
        slice_name="effort-calibration",
        artifact_path="x.md",
        original_sha="a" * 40,
        start_sha="b" * 40,
        original_first_draft="# original",
    )


def _record(alias: str, outcome: ReplayOutcome = ReplayOutcome.ACCEPTED) -> ProducerReplay:
    return ProducerReplay(
        replay_set="s",
        project_id=ProjectId(value="p", source=ProjectIdSource.REMOTE),
        phase=ReplayPhase.DESIGN,
        slice_index=176,
        slice_name="effort-calibration",
        original_sha="a" * 40,
        start_sha="b" * 40,
        config=ProducerConfigRef(alias=alias, model="m", profile="sdk", effort_sent=None),
        reviewer=ModelRef(alias="opus", model="claude-opus-5-5"),
        max_revisions=1,
        run_id="r",
        outcome=outcome,
        failure_class=None if outcome is not ReplayOutcome.FAILED else "stall",
        rounds=1,
        first_verdict="PASS",
        cost_usd=0.5,
        priced=(2, 2),
        wall_seconds=12.0,
        prompt=None,
        task_prompt=None,
        first_draft=None,
        final_text=None,
        squadron_version="0.0.0",
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
    )


class _Core:
    """Stands in for ``run_replay_set``: drives the callbacks, returns a chosen summary."""

    def __init__(self) -> None:
        self.summary = ReplaySetSummary()
        self.plans: list[ReplayPlan] = []
        self.requests: list[ReplayRequest] = []
        self.confirmed: bool | None = None

    def __call__(
        self,
        request: ReplayRequest,
        start: StartPoint,
        deps: object,
        *,
        confirm: Callable[[ReplayPlan], bool],
        new_replay_id: Callable[[], str],
        on_record: Callable[[str, ProducerReplay], None] | None = None,
        on_skip: Callable[[str, str], None] | None = None,
    ) -> ReplaySetSummary:
        self.requests.append(request)
        plan = ReplayPlan(
            phase=request.phase,
            slice_index=start.slice_index,
            slice_name=start.slice_name,
            start_sha=start.start_sha,
            configs=tuple(request.configs),
            reviewer=request.reviewer,
            max_revisions=request.max_revisions,
            llm_call_bound=len(request.configs) * 2 * (1 + request.max_revisions),
        )
        self.plans.append(plan)
        self.confirmed = confirm(plan)
        if not self.confirmed:
            return ReplaySetSummary(declined=True)
        for record_id, record in self.summary.records:
            if on_record is not None:
                on_record(record_id, record)
        for alias, why in self.summary.skipped:
            if on_skip is not None:
                on_skip(alias, why)
        return self.summary


@pytest.fixture
def core() -> Iterator[_Core]:
    fake = _Core()
    with (
        patch("squadron.cli.commands.replay.run_replay_set", fake),
        patch("squadron.cli.commands.replay.get_all_aliases", return_value=_ALIASES),
        patch(
            "squadron.cli.commands.replay.derive_project_id",
            return_value=ProjectId(value="p", source=ProjectIdSource.REMOTE),
        ),
        patch("squadron.cli.commands.replay._start_point", return_value=_start()),
        patch("squadron.cli.commands.replay._deps", return_value=MagicMock()),
    ):
        yield fake


@pytest.mark.parametrize("missing", ["--reviewer", "--max-revisions"])
def test_a_missing_required_option_is_a_usage_error(core: _Core, missing: str) -> None:
    args = list(_ARGS)
    index = args.index(missing)
    del args[index : index + 2]

    result = runner.invoke(app, args)

    assert result.exit_code == 2
    assert core.requests == []


def test_non_interactive_without_yes_exits_1_and_runs_nothing(core: _Core) -> None:
    result = runner.invoke(app, _ARGS)  # CliRunner's stdin is not a tty

    assert result.exit_code == 1
    assert "--yes" in result.output
    assert core.requests == []


def test_an_unknown_alias_fails_before_any_work(core: _Core) -> None:
    args = [*_ARGS, "--yes"]
    args[args.index("haiku")] = "nosuchalias"

    result = runner.invoke(app, args)

    assert result.exit_code == 1
    assert "nosuchalias" in result.output
    assert core.requests == []


def test_a_start_point_error_becomes_a_clean_exit_1() -> None:
    from pathlib import Path

    import typer

    from squadron.cli.commands import replay

    with (
        patch.object(replay, "GitHistory", MagicMock()),
        patch.object(replay, "resolve_start_point", side_effect=StartPointError("no commit added x")),
    ):
        with pytest.raises(typer.Exit) as caught:
            replay._start_point(ReplayPhase.DESIGN, 176, Path("."))  # pyright: ignore[reportPrivateUsage]

    assert caught.value.exit_code == 1


def test_every_config_recorded_exits_0_including_failed_outcomes(core: _Core) -> None:
    core.summary = ReplaySetSummary(
        records=[("rec-1", _record("sonnet")), ("rec-2", _record("haiku", ReplayOutcome.FAILED))]
    )

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 0, result.output
    assert "sonnet: accepted" in result.output
    assert "haiku: failed [stall]" in result.output
    assert "2 replay record(s) written" in result.output


def test_the_plan_is_printed_with_the_llm_call_bound(core: _Core) -> None:
    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert core.confirmed is True
    assert "start commit   " + "b" * 40 in result.output
    assert "8 LLM calls at most" in result.output  # 2 configs x 2 x (1 + 1)


def test_a_skipped_config_exits_1_and_is_reported(core: _Core) -> None:
    core.summary = ReplaySetSummary(
        records=[("rec-1", _record("sonnet"))], skipped=[("haiku", "git fetch failed")]
    )

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 1
    assert "haiku: skipped - git fetch failed" in result.output
    assert "1 config(s) skipped" in result.output


def test_a_stopped_set_exits_1_with_the_reason(core: _Core) -> None:
    core.summary = ReplaySetSummary(stopped="could not write the replay record: disk full")

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 1
    assert "Stopped: could not write the replay record: disk full" in result.output


def test_answering_no_at_the_prompt_runs_nothing_and_exits_1(core: _Core) -> None:
    with (
        patch("squadron.cli.commands.replay._is_interactive", return_value=True),
        patch("squadron.cli.commands.replay.typer.confirm", return_value=False),
    ):
        result = runner.invoke(app, _ARGS)

    assert core.confirmed is False
    assert result.exit_code == 1
    assert "nothing was run" in result.output
