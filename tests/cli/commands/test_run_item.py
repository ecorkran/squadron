"""`sq run --resume <id> --item N --decision retry|accept` flags (slice 197 D8, Task 30)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.batch_report import BatchItemRecord, ItemOutcome
from squadron.pipeline.item_resume import ResumeExit, ResumeOutcome

runner = CliRunner()


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--resume", "r1", "--item", "401"], "--item requires --decision retry|accept"),
        (["P6", "--item", "401", "--decision", "retry"], "--item requires --resume"),
        (["--resume", "r1", "--decision", "accept"], "--decision and --instructions require --item"),
        (["--resume", "r1", "--instructions", "x"], "--decision and --instructions require --item"),
    ],
)
def test_a_meaningless_flag_combination_exits_2(args: list[str], message: str) -> None:
    with patch("squadron.cli.commands.run_item.resume_item") as resume:
        result = runner.invoke(app, ["run", *args])

    assert result.exit_code == 2
    assert message in " ".join(result.output.split())
    resume.assert_not_called()


def test_an_unknown_decision_is_a_usage_error() -> None:
    result = runner.invoke(app, ["run", "--resume", "r1", "--item", "401", "--decision", "merge"])

    assert result.exit_code == 2


@pytest.mark.parametrize("code", list(ResumeExit))
def test_the_exit_code_is_the_resume_exit(code: ResumeExit, tmp_path: Path) -> None:
    record = BatchItemRecord("401", "S401", ItemOutcome.PASSED)
    report = tmp_path / "r1.slices.report.json"
    outcome = ResumeOutcome(code, "401 S401 — done", record, report)

    with patch("squadron.cli.commands.run_item.resume_item", AsyncMock(return_value=outcome)) as resume:
        result = runner.invoke(
            app,
            [
                "run",
                "--resume",
                "r1",
                "--item",
                "401",
                "--decision",
                "retry",
                "--instructions",
                "keep the flags",
                "-p",
                "max-revisions=3",
            ],
        )

    assert result.exit_code == int(code)
    output = " ".join(result.output.split())
    assert f"{code.name} 401 S401 — done" in output
    assert str(report) in result.output.replace("\n", "")
    request = resume.await_args.args[0]  # type: ignore[union-attr]
    assert (request.run_id, request.index, request.decision, request.instructions) == (
        "r1",
        "401",
        "retry",
        "keep the flags",
    )
    assert request.param_overrides == {"max-revisions": "3"}


def test_a_reserved_p_key_on_an_item_resume_exits_2() -> None:
    with patch("squadron.cli.commands.run_item.resume_item") as resume:
        result = runner.invoke(
            app,
            [
                "run",
                "--resume",
                "r1",
                "--item",
                "401",
                "--decision",
                "retry",
                "-p",
                "accept_decision=1",
            ],
        )

    assert result.exit_code == 2
    resume.assert_not_called()


def test_a_plain_resume_never_reaches_item_resume() -> None:
    with patch("squadron.cli.commands.run_item.resume_item") as resume:
        result = runner.invoke(app, ["run", "--resume", "no-such-run"])

    assert result.exit_code == 1
    assert "Run 'no-such-run' not found" in result.output
    resume.assert_not_called()
