"""``sq run`` starts the on-pause command only for a paused run (#302)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import typer

from squadron.cli.commands.run import _finish_run
from squadron.pipeline.executor import ExecutionStatus, PipelineResult

_START = "squadron.cli.commands.run.start_pause_command"


def _result(status: ExecutionStatus, run_id: str | None = "run-7") -> PipelineResult:
    return PipelineResult(pipeline_name="p", status=status, step_results=[], run_id=run_id)


@pytest.mark.parametrize(
    ("status", "pause_hook", "run_id", "starts", "exit_code"),
    [
        (ExecutionStatus.PAUSED, True, "run-7", True, 0),
        (ExecutionStatus.PAUSED, False, "run-7", False, 0),
        (ExecutionStatus.COMPLETED, True, "run-7", False, 0),
        (ExecutionStatus.FAILED, True, "run-7", False, 1),
        (ExecutionStatus.PAUSED, True, None, False, 0),
    ],
)
def test_hook_fires_only_for_paused_runs(
    status: ExecutionStatus, pause_hook: bool, run_id: str | None, starts: bool, exit_code: int
) -> None:
    with patch(_START) as start, pytest.raises(typer.Exit) as exit_info:
        _finish_run(_result(status, run_id), pause_hook)

    assert start.called is starts
    assert exit_info.value.exit_code == exit_code
