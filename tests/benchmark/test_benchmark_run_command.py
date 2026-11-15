"""``sq benchmark run``: options, refusals, output and exit codes (slice 424 Tasks 32-33).

The command runs against doubles through its one seam (``make_run_command``), so no model,
sandbox or network is involved. Aliases are the real built-in ones.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from squadron.benchmark.auth_check import AuthAnswer
from squadron.benchmark.bench_plan import (
    BenchConfig,
    PlannedReplay,
    config_key,
    replay_record_id,
)
from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.replay_deps import ReplayStoreError
from squadron.benchmark.run_services import KeptSandbox, ReplayContext, RunServices
from squadron.benchmark.scrubbed_env import MissingCredentialError, MissingHarnessHomeError
from squadron.cli.commands import benchmark_run as run_module
from squadron.cli.commands.benchmark_run import make_run_command
from squadron.cli.commands.benchmark_run_report import ReplayReporter
from squadron.config.keys import BENCHMARK_PLANNED_SAMPLES_KEY, COST_CAP_KEY
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import CandidateRejection
from squadron.metrology.benchmark_replay_enums import AbsenceClass, LeakVerdict, ProducerOutcome
from squadron.metrology.benchmark_replay_models import CaseDrop, ImplementationReplay, LeakScanResult
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.store import MetrologyStore
from squadron.providers.base import ProfileName
from tests.benchmark.test_fix_case_runner import fix_case
from tests.metrology.test_benchmark_replay_models import _replay as make_replay

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
TRANSCRIPT_PROFILES = {ProfileName.SDK, ProfileName.OPENAI_OAUTH}
CLEAN_LEAK = LeakScanResult(
    verdict=LeakVerdict.NO_LEAK_DETECTED, rules_version=1, tool_calls_seen=3, hits=(), detail=""
)


class Harness:
    """Fake services over a real record store, with an ordered event log."""

    def __init__(self, tmp_path: Path) -> None:
        self.events: list[str] = []
        self.store = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store"))
        cases = [fix_case(task=f"issue {n}") for n in range(2)]
        for case in cases:
            self.store.write_case(case)
        self.case_ids = [case.case_id for case in cases]
        self.store.write_case_set("fixes", self.case_ids)
        self.config: dict[str, object] = {COST_CAP_KEY: 2.0, BENCHMARK_PLANNED_SAMPLES_KEY: 1}
        self.unpriced: set[str] = set()
        self.cost: float | None = 0.5
        self.outcome = ProducerOutcome.COMMITTED
        self.absence = AbsenceClass.CONFIG
        self.drop: set[str] = set()
        self.store_failure = False
        self.replay_failure: Exception | None = None
        self.kept: list[KeptSandbox] = []
        self.contexts: list[ReplayContext] = []
        self.auth_requests: list[list[str]] = []
        self.lock_root = tmp_path / "locks"
        self.repo = tmp_path / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

    def replay_function(self, context: ReplayContext) -> Callable[[Any, BenchConfig, int], Any]:
        self.contexts.append(context)

        def replay(case: Any, config: BenchConfig, sample: int) -> ImplementationReplay | CaseDrop:
            self.events.append(f"replay:{config.alias}:{sample}")
            if self.store_failure:
                raise ReplayStoreError("cannot store the diff")
            if self.replay_failure is not None:
                raise self.replay_failure
            if case.case_id in self.drop:
                return CaseDrop(
                    case_id=case.case_id,
                    reason=CandidateRejection.NO_TEST_CHANGE,
                    environment_digest="digest",
                )
            record_id = replay_record_id(context.benchmark_id, case.case_id, config_key(config), sample)
            committed = self.outcome is ProducerOutcome.COMMITTED
            record = make_replay().model_copy(
                update={
                    "benchmark_id": context.benchmark_id,
                    "case_id": case.case_id,
                    "sample": sample,
                    "run_id": record_id,
                    "outcome": self.outcome,
                    "absence": None if committed else self.absence,
                    "leak": CLEAN_LEAK,
                    "cost_usd": self.cost,
                }
            )
            self.store.write_replay(record_id, record)
            return record

        return replay

    def auth_check(self, aliases: Sequence[str]) -> dict[ProfileName, AuthAnswer]:
        self.auth_requests.append(list(aliases))
        return {profile: AuthAnswer.YES for profile in TRANSCRIPT_PROFILES}

    def services(self, repo_root: Path) -> RunServices:
        return RunServices(
            repo_root=repo_root,
            store=self.store,
            process_runner=SubprocessRunner(),
            lock_root=self.lock_root,
            sweep=lambda runner, root: None,
            clock=lambda: NOW,
            runners=lambda kind: object(),  # type: ignore[arg-type,return-value]
            transcript_sources=lambda profile: object() if profile in TRANSCRIPT_PROFILES else None,  # type: ignore[arg-type,return-value]
            read_config=self.config.get,
            auth_check=self.auth_check,
            unpriced_aliases=lambda aliases: frozenset(a for a in aliases if a in self.unpriced),
            replay_function=self.replay_function,
            kept_sandboxes=lambda: list(self.kept),
        )

    def invoke(self, *args: str) -> Any:
        app = typer.Typer()
        app.command("run")(make_run_command(self.services))
        app.callback()(lambda: None)
        return CliRunner().invoke(app, ["run", "--set", "fixes", "--repo", str(self.repo), *args])


@pytest.fixture
def harness(tmp_path: Path) -> Harness:
    return Harness(tmp_path)


CAPS = ["--max-cost", "10", "--max-cost-per-replay", "2"]


class TestRefusals:
    def test_missing_run_cap_exits_1_naming_the_flag(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus", "--max-cost-per-replay", "2")
        assert result.exit_code == 1
        assert "Error:" in result.output and "--max-cost" in result.output

    def test_no_per_replay_cap_names_both_sources(self, harness: Harness) -> None:
        harness.config.pop(COST_CAP_KEY)
        result = harness.invoke("--model", "opus", "--max-cost", "10")
        assert result.exit_code == 1
        assert "--max-cost-per-replay" in result.output and COST_CAP_KEY in result.output

    def test_an_alias_with_no_transcript_source_is_refused_before_any_auth_probe(
        self, harness: Harness
    ) -> None:
        result = harness.invoke("--model", "gpt54", *CAPS)
        assert result.exit_code == 1
        assert "no transcript source" in result.output
        assert harness.auth_requests == []
        assert harness.events == []

    def test_an_unknown_alias_is_refused_naming_it(self, harness: Harness) -> None:
        result = harness.invoke("--model", "no-such-alias", *CAPS)
        assert result.exit_code == 1
        assert "no-such-alias" in result.output

    def test_an_unknown_case_set_is_refused(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus", "--set-version", "9", *CAPS)
        assert result.exit_code == 1
        assert "fixes v9" in result.output

    def test_a_repeated_model_is_refused(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus", "--model", "opus", *CAPS)
        assert result.exit_code == 1
        assert "more than once" in result.output

    def test_a_refusal_prints_no_stack_trace(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus")
        assert "Traceback" not in result.output


class TestSamples:
    def pending(self, result: Any) -> str:
        return next(line for line in result.output.splitlines() if line.startswith("pending"))

    def test_absent_flag_uses_the_config_key(self, harness: Harness) -> None:
        harness.config[BENCHMARK_PLANNED_SAMPLES_KEY] = 3
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.exit_code == 0, result.output
        assert self.pending(result).startswith("pending 6 of 6")

    def test_the_flag_wins_over_the_key(self, harness: Harness) -> None:
        harness.config[BENCHMARK_PLANNED_SAMPLES_KEY] = 3
        result = harness.invoke("--model", "opus", "--samples", "1", *CAPS)
        assert self.pending(result).startswith("pending 2 of 2")

    def test_neither_refuses_naming_both(self, harness: Harness) -> None:
        harness.config.pop(BENCHMARK_PLANNED_SAMPLES_KEY)
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.exit_code == 1
        assert "--samples" in result.output and BENCHMARK_PLANNED_SAMPLES_KEY in result.output

    @pytest.mark.parametrize("value", ["0", "-2"])
    def test_a_non_positive_flag_refuses(self, harness: Harness, value: str) -> None:
        result = harness.invoke("--model", "opus", "--samples", value, *CAPS)
        assert result.exit_code == 1
        assert "--samples must be a positive integer" in result.output

    def test_a_non_positive_config_value_refuses_naming_the_key(self, harness: Harness) -> None:
        harness.config[BENCHMARK_PLANNED_SAMPLES_KEY] = 0
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.exit_code == 1
        assert f"{BENCHMARK_PLANNED_SAMPLES_KEY} must be a positive integer" in result.output

    def test_a_second_model_doubles_the_plan(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus", "--model", "sol", *CAPS)
        assert self.pending(result).startswith("pending 4 of 4")


def test_help_lists_every_option() -> None:
    app = typer.Typer()
    app.command("run")(make_run_command(lambda root: pytest.fail("no services for --help")))
    app.callback()(lambda: None)
    # Read the options off the command: CI forces colour, which splits option names in
    # the rendered --help text.
    command = typer.main.get_command(app).commands["run"]  # type: ignore[attr-defined]
    options = {opt for param in command.params for opt in param.opts}
    assert options >= {
        "--set", "--set-version", "--model", "--samples", "--max-cost",
        "--max-cost-per-replay", "--case", "--retry-harness", "--keep",
    }  # fmt: skip


class TestOutput:
    def test_the_bound_is_printed_before_the_first_replay(
        self, harness: Harness, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        real_format_bound = run_module.format_bound

        def logged(*args: Any, **kwargs: Any) -> str:
            harness.events.append("bound")
            return real_format_bound(*args, **kwargs)

        monkeypatch.setattr(run_module, "format_bound", logged)
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.exit_code == 0
        assert harness.events == ["bound", "replay:opus:0", "replay:opus:0"]

    def test_a_full_run_exits_0_and_prints_lines_and_summary(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.exit_code == 0, result.output
        lines = [line for line in result.output.splitlines() if line.startswith("implreplay-")]
        assert len(lines) == 2
        assert all(
            "committed" in line and "no_leak_detected" in line and "$0.5000" in line for line in lines
        )
        assert "benchmark bench-" in result.output and ": complete" in result.output
        assert "outcomes: committed 2" in result.output
        assert "leak: no_leak_detected 2" in result.output
        assert "spent: $1.0000 of run cap $10.00" in result.output

    def test_a_capped_run_exits_2(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus", "--max-cost", "0.4", "--max-cost-per-replay", "2")
        assert result.exit_code == 2
        assert ": partial" in result.output
        assert len(harness.events) == 1

    def test_a_store_failure_exits_1_and_leaves_the_run_running(self, harness: Harness) -> None:
        harness.store_failure = True
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.exit_code == 1
        assert "Error: cannot store the diff" in result.output
        assert [run.status.value for run in harness.store.list_runs()] == ["running"]
        assert not list(harness.lock_root.glob("*.lock"))

    @pytest.mark.parametrize(
        "failure",
        [
            BuildHalted("git log could not run"),
            MissingCredentialError("OPENAI_API_KEY"),
            MissingHarnessHomeError(),
        ],
        ids=["build_halted", "missing_credential", "missing_harness_home"],
    )
    def test_a_replay_environment_failure_is_a_refusal_not_a_traceback(
        self, harness: Harness, failure: Exception
    ) -> None:
        harness.replay_failure = failure
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.exit_code == 1
        assert f"Error: {failure}" in result.output
        assert "Traceback" not in result.output
        assert not list(harness.lock_root.glob("*.lock"))

    def test_keep_prints_the_paths_and_the_auth_copy_warning(
        self, harness: Harness, tmp_path: Path
    ) -> None:
        harness.kept = [KeptSandbox(tmp_path / "t", tmp_path / "t.home", tmp_path / "t.out")]
        result = harness.invoke("--model", "opus", "--keep", *CAPS)
        assert harness.contexts[0].keep is True
        assert f"tree: {tmp_path / 't'}" in result.output
        assert f"home: {tmp_path / 't.home'}" in result.output
        assert "copies of your auth files" in result.output

    def test_without_kept_sandboxes_no_warning_is_printed(self, harness: Harness) -> None:
        result = harness.invoke("--model", "opus", *CAPS)
        assert "auth files" not in result.output

    def test_no_run_state_prints_the_auth_check_reminder_once_per_profile(
        self, harness: Harness
    ) -> None:
        harness.outcome = ProducerOutcome.NO_RUN_STATE
        result = harness.invoke("--model", "opus", "--model", "sol", *CAPS)
        reminders = [line for line in result.output.splitlines() if "sq benchmark auth-check" in line]
        assert len(reminders) == 2
        assert {"sdk" in line or "openai-oauth" in line for line in reminders} == {True}

    def test_a_later_no_run_state_in_a_seen_profile_is_not_reminded_again(
        self, harness: Harness
    ) -> None:
        harness.outcome = ProducerOutcome.NO_RUN_STATE
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.output.count("sq benchmark auth-check") == 1

    def test_a_no_run_state_after_a_committed_first_replay_still_gets_the_reminder(self) -> None:
        printed: list[str] = []
        reporter = ReplayReporter(printed.append)
        config = BenchConfig("opus", "claude-opus-5-5", "sdk", None)

        def planned(sample: int) -> PlannedReplay:
            return PlannedReplay("case-x", sample, config, f"implreplay-{sample}")

        committed = make_replay()
        silent = committed.model_copy(update={"outcome": ProducerOutcome.NO_RUN_STATE})
        for sample, result in enumerate([committed, silent, silent]):
            reporter(planned(sample), result)
        reminders = [line for line in printed if "sq benchmark auth-check" in line]
        assert len(reminders) == 1
        assert printed.index(reminders[0]) == 2  # right after the first no_run_state line

    def test_unpriced_replays_are_counted_and_their_config_is_not_bounded(
        self, harness: Harness
    ) -> None:
        harness.unpriced = {"sol"}
        harness.cost = None
        result = harness.invoke("--model", "sol", *CAPS)
        assert "not bounded: sol (openai-oauth) — reports no cost" in result.output
        assert "(2 replays reported no cost)" in result.output
        assert "unpriced" in result.output

    def test_a_dropped_case_is_listed_with_its_reason(self, harness: Harness) -> None:
        harness.drop = {harness.case_ids[0]}
        result = harness.invoke("--model", "opus", *CAPS)
        assert result.output.count(f"dropped case {harness.case_ids[0]}: no_test_change") == 2
        assert len(harness.events) == 2  # the drop's attempt, then the other case

    def test_case_filter_limits_the_plan_without_changing_the_benchmark(self, harness: Harness) -> None:
        full = harness.invoke("--model", "opus", *CAPS)
        full_id = next(w for w in full.output.split() if w.startswith("bench-"))
        harness.events.clear()
        filtered = harness.invoke("--model", "opus", "--case", harness.case_ids[0], *CAPS)
        assert full_id in filtered.output
        assert "pending 0 of 1" in filtered.output
        assert harness.events == []

    def test_retry_harness_deletes_only_harness_records_and_runs_them_again(
        self, harness: Harness
    ) -> None:
        harness.outcome = ProducerOutcome.NO_RUN_STATE
        harness.absence = AbsenceClass.HARNESS
        harness.invoke("--model", "opus", *CAPS)
        harness.events.clear()
        plain = harness.invoke("--model", "opus", *CAPS)
        assert "pending 0 of 2" in plain.output and harness.events == []
        retried = harness.invoke("--model", "opus", "--retry-harness", *CAPS)
        assert "deleted 2 harness-absent replay records" in retried.output
        assert "pending 2 of 2" in retried.output
        assert harness.events == ["replay:opus:0", "replay:opus:0"]

    def test_retry_harness_leaves_config_absences_alone(self, harness: Harness) -> None:
        harness.outcome = ProducerOutcome.NO_COMMIT
        harness.invoke("--model", "opus", *CAPS)
        harness.events.clear()
        retried = harness.invoke("--model", "opus", "--retry-harness", *CAPS)
        assert "deleted 0 harness-absent replay records" in retried.output
        assert harness.events == []
