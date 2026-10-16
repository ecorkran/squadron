"""``sq replay judge`` with the judging core faked (slice 177 D5, D10)."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.replay.judging import JudgeInputError, JudgeJob, JudgeSummary

runner = CliRunner()
_ALIASES = {"opus": {"model": "claude-opus-5-5", "profile": "sdk"}}
_ARGS = ["replay", "judge", "--phase", "design", "--slice", "176", "--judge", "opus"]
_MODULE = "squadron.cli.commands.replay_judge"


class _Fakes:
    def __init__(self) -> None:
        self.jobs: list[JudgeJob] = [MagicMock(spec=JudgeJob)]
        self.pairs_calls = (3, 6)
        self.summary = JudgeSummary(judged=3, calls=6)
        self.judged_with: list[object] = []
        self.error: Exception | None = None

    async def judge(self, jobs: object, **kwargs: object) -> JudgeSummary:
        self.judged_with.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.summary


@pytest.fixture
def fakes() -> Iterator[_Fakes]:
    box = _Fakes()
    with (
        patch("squadron.cli.commands.replay_common.get_all_aliases", return_value=_ALIASES),
        patch(
            "squadron.cli.commands.replay_common.derive_project_id",
            return_value=ProjectId(value="p", source=ProjectIdSource.REMOTE),
        ),
        patch(f"{_MODULE}.MetrologyStore"),
        patch(f"{_MODULE}.resolve_store_dir"),
        patch(f"{_MODULE}.build_jobs", side_effect=lambda *a, **k: box.jobs),
        patch(f"{_MODULE}.total_calls", side_effect=lambda jobs: box.pairs_calls),
        patch(f"{_MODULE}.judge_jobs", side_effect=box.judge),
        patch(f"{_MODULE}.one_shot_judge_dispatcher", return_value=MagicMock()),
        patch(f"{_MODULE}.get_typed_config", return_value=600),
    ):
        yield box


def test_a_missing_judge_is_a_usage_error(fakes: _Fakes) -> None:
    result = runner.invoke(app, ["replay", "judge", "--phase", "design", "--slice", "176"])

    assert result.exit_code == 2
    assert fakes.judged_with == []


def test_non_interactive_without_yes_exits_1_and_judges_nothing(fakes: _Fakes) -> None:
    result = runner.invoke(app, _ARGS)

    assert result.exit_code == 1 and "--yes" in result.output
    assert fakes.judged_with == []


def test_no_replays_prints_a_message_and_exits_0(fakes: _Fakes) -> None:
    fakes.jobs = []

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 0 and "No replays for this slice" in result.output
    assert fakes.judged_with == []


def test_zero_pairs_to_judge_prints_a_message_and_exits_0(fakes: _Fakes) -> None:
    fakes.pairs_calls = (0, 0)

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 0 and "already been judged" in result.output
    assert fakes.judged_with == []


def test_the_plan_names_the_pairs_calls_and_prompt_hash_then_judges(fakes: _Fakes) -> None:
    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 0, result.output
    assert "3 pair(s) to judge: 6 judge calls with opus (prompt " in result.output
    assert "3 pair(s) judged" in result.output
    assert fakes.judged_with[0]["timeout_s"] == 600  # type: ignore[index]


def test_a_failed_pair_exits_1_with_the_count(fakes: _Fakes) -> None:
    fakes.summary = JudgeSummary(judged=2, failed=1, calls=5)

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 1
    assert "2 pair(s) judged, 1 failed" in result.output


def test_pairs_with_no_verdict_are_reported(fakes: _Fakes) -> None:
    fakes.summary = JudgeSummary(judged=3, invalid=1, calls=6)

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 0 and "1 with no verdict" in result.output


def test_an_input_error_exits_1_with_its_message(fakes: _Fakes) -> None:
    fakes.error = JudgeInputError("no replay in the set recorded the task prompt")

    result = runner.invoke(app, [*_ARGS, "--yes"])

    assert result.exit_code == 1 and "recorded the task prompt" in result.output


def test_declining_the_prompt_judges_nothing(fakes: _Fakes) -> None:
    with (
        patch("squadron.cli.commands.replay_common.is_interactive", return_value=True),
        patch(f"{_MODULE}.typer.confirm", return_value=False),
    ):
        result = runner.invoke(app, _ARGS)

    assert result.exit_code == 1 and "nothing was run" in result.output
    assert fakes.judged_with == []


def test_an_unknown_judge_alias_fails_before_any_work(fakes: _Fakes) -> None:
    args = list(_ARGS)
    args[args.index("opus")] = "nosuch"

    result = runner.invoke(app, [*args, "--yes"])

    assert result.exit_code == 1 and "nosuch" in result.output
