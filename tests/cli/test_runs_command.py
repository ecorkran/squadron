"""sq runs list and sq runs wait (slice 199).

HOME is a per-test temp dir (tests/conftest.py), so ``StateManager()`` writes under it;
project pipelines are read from the temp cwd.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands import runs
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.run_prune import parse_duration
from squadron.pipeline.run_wait import WAIT_EXIT_CODES, WaitOutcome, WaitResult, orphaned_message
from squadron.pipeline.state import StateManager
from tests.pipeline.liveness_support import exited_pid
from tests.pipeline.run_listing_support import (
    STEP_NAMES,
    begin,
    begin_owned,
    completed_batch_run,
    end,
    mixed_records,
    pause_at,
    write_batch_pipeline,
    write_report,
    write_step_pipeline,
)


@pytest.fixture
def sm(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StateManager:
    monkeypatch.chdir(tmp_path)
    pipelines = tmp_path / "project-documents/user/pipelines"
    write_step_pipeline(pipelines, "steps")
    write_batch_pipeline(pipelines, "batch")
    return StateManager()


def _invoke(*args: str) -> str:
    result = CliRunner().invoke(app, ["runs", *args])
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())


class TestRunsList:
    def test_shows_resumable_runs(self, sm: StateManager) -> None:
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[1], done=[STEP_NAMES[0]])
        batch = completed_batch_run(sm, "batch")

        out = _invoke("list")

        assert paused in out and STEP_NAMES[1] in out
        assert batch in out and "3 items in slices (1 accept)" in out
        assert "Resume a step:" in out

    def test_empty_result_exits_zero(self, sm: StateManager) -> None:
        assert "No running or resumable runs. Use --all to include completed runs." in _invoke("list")

    def test_running_is_default_and_all_adds_completed(self, sm: StateManager) -> None:
        running = begin(sm, "steps")
        done = begin(sm, "steps")
        end(sm, done, ExecutionStatus.COMPLETED)

        out = _invoke("list")
        assert running in out and done not in out
        out = _invoke("list", "--all")
        assert running in out and done in out

    def test_unavailable_pipelines_summarised_once_and_detailed_under_v(self, sm: StateManager) -> None:
        for name in ("gone-a", "gone-a", "gone-b"):
            pause_at(sm, begin(sm, name), "design-0")

        quiet = CliRunner().invoke(app, ["runs", "list"])
        verbose = CliRunner().invoke(app, ["runs", "list", "-v"])

        summary = (
            "3 runs reference 2 unavailable pipelines "
            "(-v for details; sq runs prune --status unavailable removes them)."
        )
        assert quiet.exit_code == 0
        assert quiet.stderr.splitlines() == [summary]
        assert "unavailable:" not in quiet.output
        details = verbose.stderr.splitlines()
        assert details[0] == summary
        assert [line.split(":")[0] for line in details[1:]] == ["  gone-a", "  gone-b"]

    def test_no_summary_line_when_every_pipeline_loads(self, sm: StateManager) -> None:
        pause_at(sm, begin(sm, "steps"), STEP_NAMES[0])

        result = CliRunner().invoke(app, ["runs", "list"])

        assert result.stderr == ""

    def test_pipeline_filter(self, sm: StateManager) -> None:
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[0])
        batch = completed_batch_run(sm, "batch")

        out = _invoke("list", "--pipeline", "BATCH")

        assert batch in out
        assert paused not in out

    def test_bare_group_prints_help(self) -> None:
        result = CliRunner().invoke(app, ["runs"])
        assert "list" in result.output


class TestRunsWait:
    @pytest.mark.parametrize("outcome", list(WaitOutcome))
    def test_every_outcome_maps_to_its_exit_code(
        self, sm: StateManager, monkeypatch: pytest.MonkeyPatch, outcome: WaitOutcome
    ) -> None:
        run_id = begin(sm, "steps")
        end(sm, run_id, ExecutionStatus.COMPLETED)
        state = sm.load(run_id)

        def fake_wait(*_args: object, **_kwargs: object) -> WaitResult:
            return WaitResult(outcome, state)

        monkeypatch.setattr(runs, "wait_for_run", fake_wait)

        result = CliRunner().invoke(app, ["runs", "wait", run_id])

        assert result.exit_code == WAIT_EXIT_CODES[outcome]
        stderr_line = f"sq runs wait: run {run_id} {outcome}"
        if outcome is WaitOutcome.ORPHANED:
            stderr_line = orphaned_message(run_id, state)
        assert (stderr_line in result.stderr) is (outcome is not WaitOutcome.COMPLETED)

    def test_orphaned_run_exits_8_naming_the_process(self, sm: StateManager) -> None:
        pid = exited_pid()
        run_id = begin_owned(sm, "steps", pid)

        result = CliRunner().invoke(app, ["runs", "wait", run_id])

        assert result.exit_code == 8
        assert f"sq runs wait: run {run_id} orphaned (process {pid} gone)" in result.stderr

    def test_completed_run_prints_status_and_exits_zero(self, sm: StateManager) -> None:
        run_id = begin(sm, "steps")
        end(sm, run_id, ExecutionStatus.COMPLETED)

        result = CliRunner().invoke(app, ["runs", "wait", run_id])

        assert result.exit_code == 0, result.output
        assert "Run Status" in result.stdout
        assert run_id in result.stdout

    def test_missing_run_exits_not_found(self, sm: StateManager) -> None:
        result = CliRunner().invoke(app, ["runs", "wait", "no-such-run"])

        assert result.exit_code == WAIT_EXIT_CODES[WaitOutcome.NOT_FOUND]
        assert "sq runs wait: run no-such-run not_found" in result.stderr


# ---------------------------------------------------------------------------
# sq runs prune (slice 174 D9)
# ---------------------------------------------------------------------------


def _prune(*args: str) -> Result:
    return CliRunner().invoke(app, ["runs", "prune", *args])


def _files(sm: StateManager) -> set[str]:
    return {p.name for p in sm.runs_dir.iterdir()}


class TestRunsPrune:
    def test_preview_deletes_nothing(self, sm: StateManager) -> None:
        failed = begin(sm, "steps")
        end(sm, failed, ExecutionStatus.FAILED)
        before = _files(sm)

        result = _prune()

        assert result.exit_code == 0, result.output
        assert failed in result.stdout
        assert "1 run(s) would be removed. Re-run with --yes to delete." in result.stdout
        assert _files(sm) == before

    def test_yes_deletes_exactly_the_previewed_runs_and_reports(self, sm: StateManager) -> None:
        failed = begin(sm, "batch", {"plan": "180"})
        write_report(sm, "batch", failed, mixed_records())
        end(sm, failed, ExecutionStatus.FAILED)
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[0])
        preview = _prune()

        result = _prune("--yes")

        assert result.exit_code == 0, result.output
        assert "Removed 1 run(s)." in result.stdout
        assert failed in preview.stdout and paused not in preview.stdout
        assert not any(name.startswith(failed) for name in _files(sm))
        assert f"{paused}.json" in _files(sm)

    def test_preview_labels_stale_and_unowned(self, sm: StateManager) -> None:
        stale = begin_owned(sm, "steps", os.getpid())
        state = sm.load(stale)
        state.heartbeat_at = datetime(2020, 1, 1, tzinfo=UTC)
        sm._save(state)  # pyright: ignore[reportPrivateUsage]
        unowned = begin(sm, "steps")

        stale_out = " ".join(_prune("--status", "stale").stdout.split())
        unowned_out = " ".join(_prune("--status", "unowned").stdout.split())

        assert f"{stale} steps running stale" in stale_out
        assert f"{unowned} steps running unowned" in unowned_out
        assert unowned not in stale_out and stale not in unowned_out

    def test_paused_only_by_name_or_status(self, sm: StateManager) -> None:
        paused = begin(sm, "steps")
        pause_at(sm, paused, STEP_NAMES[0])

        assert paused not in _prune().stdout
        assert paused in _prune(paused).stdout
        assert paused in _prune("--status", "paused").stdout

    def test_named_live_run_is_refused_with_exit_1(self, sm: StateManager) -> None:
        live = begin_owned(sm, "steps", os.getpid())

        result = _prune(live, "--yes")

        assert result.exit_code == 1
        assert f"sq runs prune: run {live}: run is live; not pruned" in result.stderr
        assert f"{live}.json" in _files(sm)

    @pytest.mark.parametrize(
        "args",
        [
            ("run-x", "--status", "failed"),
            ("--status", "running"),
            ("--older-than", "3 fortnights"),
            ("--older-than", "7"),
        ],
        ids=["run-id-with-status", "not-a-category", "bad-unit", "no-unit"],
    )
    def test_usage_errors_exit_2(self, sm: StateManager, args: tuple[str, ...]) -> None:
        assert _prune(*args).exit_code == 2

    def test_older_than_filters(self, sm: StateManager) -> None:
        failed = begin(sm, "steps")
        end(sm, failed, ExecutionStatus.FAILED)

        assert "No runs to prune." in _prune("--older-than", " 2D ").stdout
        assert failed in _prune("--older-than", "0s").stdout


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("30s", timedelta(seconds=30)),
        ("5m", timedelta(minutes=5)),
        (" 2H ", timedelta(hours=2)),
        ("7d", timedelta(days=7)),
        ("1 w", timedelta(weeks=1)),
    ],
)
def test_parse_duration(text: str, expected: timedelta) -> None:
    assert parse_duration(text) == expected


@pytest.mark.parametrize("text", ["", "7", "d", "7y", "-1d", "1.5h"])
def test_parse_duration_rejects(text: str) -> None:
    with pytest.raises(ValueError, match="expected <int><unit>"):
        parse_duration(text)
