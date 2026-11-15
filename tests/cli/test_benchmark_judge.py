"""``sq benchmark judge`` (slice 426, Task 35): output, exits, refusals and production wiring.

The dispatcher is a double and the store a temporary one; the reference diffs come from a
fixture repository so ``--repo`` is real.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from squadron.benchmark.diff_judge_services import JudgeServices
from squadron.cli.app import app
from squadron.cli.commands import benchmark_common as common_module
from squadron.cli.commands import benchmark_judge as cli_module
from squadron.config.keys import (
    BENCHMARK_JUDGE_MAX_PROMPT_CHARS_KEY,
    BENCHMARK_JUDGE_MODEL_KEY,
    METROLOGY_JUDGE_TIMEOUT_KEY,
)
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind, CaseProvenance
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.content_sidecars import ContentSidecars, SidecarKind
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.store import MetrologyStore
from tests.benchmark.diff_judge_run_support import JUDGE, NOW, MemorySidecars, ScriptedDispatcher
from tests.benchmark.diff_judge_support import diff_text
from tests.benchmark.report_support import config
from tests.benchmark.slice_case_support import PROJECT
from tests.benchmark.slice_repos import SliceRepo, fast_forward_landing, two_parent_landing
from tests.benchmark.slice_runner_support import slice_case
from tests.benchmark.test_grade_plan import make_replay, make_run

runner = CliRunner()
BENCHMARK_ID = "bench-3f9c0a1b2c3d4e5f"


class Fixture:
    """A stored benchmark of one slice case with two configs at k = 1, over a real repo."""

    def __init__(self, tmp_path: Path) -> None:
        self.built: SliceRepo = two_parent_landing(tmp_path / "repo")
        records = BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store"))
        self.records = records
        self.slice_store = SliceCaseRecordStore(records)
        base = slice_case()
        self.case = BenchmarkCase.build(
            project_id=PROJECT,
            kind=CaseKind.SLICE,
            start_sha=self.built.landing.fork,
            reference_sha=self.built.landing.tip,
            task_text=base.task_text,
            hidden_tests=(),
            hidden_fixtures=(),
            superseded_tests=(),
            excluded_tests=(),
            grader_commands=(),
            provenance=CaseProvenance(
                source_ref=f"slice:{self.built.index}@{self.built.landing.after}",
                created_at=NOW,
                built_by="test",
            ),
        )
        records.write_case(self.case)
        records.write_case_set("slices", [self.case.case_id])
        run = make_run(BENCHMARK_ID).model_copy(update={"case_set": "slices", "case_set_version": 1})
        records.write_run(run)
        for alias in ("opus", "sol"):
            content = diff_text(alias)
            ref = records.diffs.put(content)
            record_id, replay = make_replay(
                self.case,
                1,
                config=config(alias),
                diff=ref,
                commit_sha="c" * 40,
                benchmark_id=BENCHMARK_ID,
            )
            records.write_replay(f"{record_id}-{alias}", replay)
        self.sidecars = MemorySidecars()

    def services(
        self,
        dispatcher: ScriptedDispatcher,
        tmp_path: Path,
        settings: dict[str, object] | None = None,
    ) -> JudgeServices:
        values: dict[str, object] = {
            BENCHMARK_JUDGE_MODEL_KEY: "gpt-judge",
            BENCHMARK_JUDGE_MAX_PROMPT_CHARS_KEY: 400000,
            METROLOGY_JUDGE_TIMEOUT_KEY: 5,
        } | (settings or {})
        return JudgeServices(
            repo_root=self.built.repo,
            store=self.records,
            slice_store=self.slice_store,
            process_runner=SubprocessRunner(),
            lock_root=tmp_path / "locks",
            clock=lambda: NOW,
            read_config=lambda key: values.get(key),
            resolve_judge=lambda alias: JUDGE,
            dispatcher_for=lambda alias: dispatcher,
            sidecars=self.sidecars,
            project_id_of=lambda path: PROJECT.value,
        )


def _invoke(
    fixture: Fixture, services: JudgeServices, *args: str, benchmark: str = BENCHMARK_ID
) -> Any:
    command = typer.Typer()
    command.command("judge")(cli_module.make_judge_command(lambda root: services))
    command.callback()(lambda: None)
    return runner.invoke(command, ["judge", benchmark, "--repo", str(fixture.built.repo), *args])


def test_output_for_a_stored_fixture_with_a_dispatcher_double(tmp_path: Path) -> None:
    fixture, dispatcher = Fixture(tmp_path), ScriptedDispatcher()

    result = _invoke(
        fixture, fixture.services(dispatcher, tmp_path), "--max-cost", "3", "--judge-cost", "0.05"
    )

    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert lines[0].startswith(f"judge {BENCHMARK_ID}  judge gpt-judge (openai-oauth)")
    assert "pairs 3 (0 forfeits) → 6 calls" in result.output  # 1 cross pair + 2 reference pairs
    pair_lines = [line for line in lines if line.startswith(fixture.case.case_id)]
    assert len(pair_lines) == 3
    assert any(" opus s1 vs sol s1: " in line for line in pair_lines)
    assert any(" vs reference: " in line for line in pair_lines)
    assert "judged 3 pairs, 0 forfeits, 0 failed" in result.output
    assert len(dispatcher.prompts) == 6


def test_the_cap_exits_2_and_keeps_the_records_written(tmp_path: Path) -> None:
    fixture, dispatcher = Fixture(tmp_path), ScriptedDispatcher(cost=0.04)

    result = _invoke(
        fixture, fixture.services(dispatcher, tmp_path), "--max-cost", "0.05", "--judge-cost", "0.04"
    )

    assert result.exit_code == 2
    assert "stopped at the run cap" in result.output
    assert len(fixture.slice_store.diff_judgments_for(BENCHMARK_ID)) == 1


@pytest.mark.parametrize(
    ("args", "settings", "named"),
    [
        (["--judge-cost", "0.05"], {}, "--max-cost"),
        (
            ["--max-cost", "3", "--judge-cost", "0.05"],
            {BENCHMARK_JUDGE_MODEL_KEY: None},
            BENCHMARK_JUDGE_MODEL_KEY,
        ),
        (
            ["--max-cost", "3", "--judge-cost", "0.05"],
            {BENCHMARK_JUDGE_MODEL_KEY: None},
            "--judge-model",
        ),
        (["--max-cost", "3"], {}, "--judge-cost"),
    ],
    ids=["no cap", "no judge (key)", "no judge (flag)", "no per-call figure"],
)
def test_each_refusal_exits_1_naming_what_is_missing(
    tmp_path: Path, args: list[str], settings: dict[str, object], named: str
) -> None:
    fixture, dispatcher = Fixture(tmp_path), ScriptedDispatcher()

    result = _invoke(fixture, fixture.services(dispatcher, tmp_path, settings), *args)

    assert result.exit_code == 1
    assert named in result.output
    assert dispatcher.prompts == []


def test_a_case_with_no_matching_repo_exits_1_naming_the_case_and_flag(tmp_path: Path) -> None:
    fixture, dispatcher = Fixture(tmp_path), ScriptedDispatcher()
    services = fixture.services(dispatcher, tmp_path)
    other = JudgeServices(**{**services.__dict__, "project_id_of": lambda path: "elsewhere"})

    result = _invoke(fixture, other, "--max-cost", "3", "--judge-cost", "0.05")

    assert result.exit_code == 1
    assert fixture.case.case_id in result.output and "--repo" in result.output


def test_a_tip_sha_missing_from_the_repo_exits_1_naming_case_and_sha(tmp_path: Path) -> None:
    fixture, dispatcher = Fixture(tmp_path), ScriptedDispatcher()
    other_repo = fast_forward_landing(tmp_path / "other")  # holds none of this case's commits
    services = fixture.services(dispatcher, tmp_path)
    command = typer.Typer()
    command.command("judge")(cli_module.make_judge_command(lambda root: services))
    command.callback()(lambda: None)

    result = runner.invoke(
        command,
        [
            "judge",
            BENCHMARK_ID,
            "--repo",
            str(other_repo.repo),
            "--max-cost",
            "3",
            "--judge-cost",
            "0.05",
        ],
    )

    assert result.exit_code == 1
    assert fixture.case.case_id in result.output
    assert dispatcher.prompts == []


def test_an_unknown_benchmark_id_exits_1_naming_it(tmp_path: Path) -> None:
    fixture, dispatcher = Fixture(tmp_path), ScriptedDispatcher()

    result = _invoke(
        fixture, fixture.services(dispatcher, tmp_path), "--max-cost", "3", benchmark="bench-nope"
    )

    assert result.exit_code == 1
    assert "bench-nope" in result.output


def test_judge_deps_returns_the_real_collaborators_without_dispatching(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(common_module, "resolve_store_dir", lambda cwd: tmp_path / "store")

    services = cli_module.judge_deps(tmp_path)

    assert isinstance(services.store, BenchmarkRecordStore)
    assert isinstance(services.slice_store, SliceCaseRecordStore)
    assert isinstance(services.process_runner, SubprocessRunner)
    assert isinstance(services.sidecars, ContentSidecars)
    assert callable(services.dispatcher_for("opus"))  # resolved, never called
    assert SidecarKind.DIFFS.value in str(services.sidecars._directory)  # pyright: ignore[reportPrivateUsage]


def test_help_lists_every_option() -> None:
    command = typer.Typer()
    command.command("judge")(cli_module.make_judge_command(lambda root: pytest.fail("no services")))  # type: ignore[arg-type,return-value]
    command.callback()(lambda: None)

    click_command = typer.main.get_command(command).commands["judge"]  # type: ignore[attr-defined]
    options = {opt for param in click_command.params for opt in param.opts}

    assert options >= {"--max-cost", "--judge-model", "--judge-cost", "--repo"}
    assert runner.invoke(app, ["benchmark", "judge", "--help"]).exit_code == 0
