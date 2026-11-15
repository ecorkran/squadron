"""``sq benchmark slice-cases build`` (slice 426, Task 21): output, exits and production wiring.

The qualification collaborators are doubles from the slice-case test support; the git history
is a fixture repository under ``tmp_path``.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from squadron.benchmark.python_adapter import PythonBenchmarkAdapter
from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.benchmark.registry import UnsupportedLanguageError
from squadron.benchmark.slice_case_build import SliceBuildDeps
from squadron.cli.app import app
from squadron.cli.commands import benchmark_common as common_module
from squadron.cli.commands import benchmark_slice as cli_module
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.project_id import ProjectId
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.slice_range_models import SliceRanges
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.metrology.store import MetrologyStore
from squadron.replay.history_free_sandbox import SandboxError
from tests.benchmark.slice_case_support import PROJECT
from tests.benchmark.slice_qualify_support import Setup, typical_setup
from tests.benchmark.slice_repos import SliceRepo, landing_of, two_parent_landing

runner = CliRunner()


class _Ranges:
    def __init__(self, ranges: SliceRanges | None) -> None:
        self._ranges = ranges

    def get_slice_ranges(self, project_id: ProjectId) -> SliceRanges | None:
        return self._ranges


def _ranges_for(built: SliceRepo) -> SliceRanges:
    return SliceRanges(
        record_id="sliceranges-t", project_id=PROJECT, slices={built.index: [landing_of(built)]}
    )


def _patch_deps(
    monkeypatch: pytest.MonkeyPatch, setup: Setup, ranges: SliceRanges | None
) -> list[bool]:
    """Make the command build its deps from ``setup``; returns the ``keep`` values it asked for."""
    asked: list[bool] = []

    def fake(repo_root: Path, *, keep: bool, runner: object = None) -> SliceBuildDeps:
        asked.append(keep)
        return SliceBuildDeps(
            qualify=replace(setup.deps, keep=keep), ranges=_Ranges(ranges), case_sets=setup.cases
        )

    monkeypatch.setattr(cli_module, "build_deps", fake)
    monkeypatch.setattr(cli_module, "sweep_benchmark_orphans", lambda runner: None)
    return asked


def invoke(built: SliceRepo, *extra: str) -> Any:
    return runner.invoke(
        app, ["benchmark", "slice-cases", "build", "--set", "slices", "--repo", str(built.repo), *extra]
    )


def test_a_stored_fixture_prints_lines_the_case_set_and_the_yield_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = two_parent_landing(tmp_path / "repo")
    _patch_deps(monkeypatch, typical_setup(tmp_path / "s", built), _ranges_for(built))

    result = invoke(built)

    assert result.exit_code == 0, result.output
    assert f"slice {built.index} qualified case-" in result.output
    assert "(2 regression nodes, 2 superseded, 2 excluded)" in result.output
    assert "case set slices v1" in result.output
    assert "slice cases" in result.output  # the yield rows' heading
    assert "candidates  qualified" in result.output


def test_no_slice_ranges_record_exits_1_naming_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = two_parent_landing(tmp_path / "repo")
    _patch_deps(monkeypatch, typical_setup(tmp_path / "s", built), None)

    result = invoke(built)

    assert result.exit_code == 1
    assert "sq metrology slice-ranges" in result.output


def test_a_harness_failure_exits_1_after_printing_its_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = two_parent_landing(tmp_path / "repo")
    failing = typical_setup(
        tmp_path / "s",
        built,
        fail=lambda sha: SandboxError("no space") if sha == built.landing.tip else None,
    )
    _patch_deps(monkeypatch, failing, _ranges_for(built))

    result = invoke(built)

    assert result.exit_code == 1
    assert f"slice {built.index} harness_error:" in result.output
    assert f"build stopped at slice {built.index}" in result.output


def test_keep_is_passed_on_and_the_kept_paths_print(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(tmp_path / "s", built)
    asked = _patch_deps(monkeypatch, setup, _ranges_for(built))

    result = invoke(built, "--keep")

    assert result.exit_code == 0, result.output
    assert asked == [True]
    assert all(sandbox.kept for sandbox in setup.factory.sandboxes.values())
    for sandbox in setup.factory.sandboxes.values():
        assert f"kept {sandbox.tree}" in result.output


def test_without_keep_nothing_is_kept_or_printed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    built = two_parent_landing(tmp_path / "repo")
    setup = typical_setup(tmp_path / "s", built)
    asked = _patch_deps(monkeypatch, setup, _ranges_for(built))

    result = invoke(built)

    assert asked == [False]
    assert "kept " not in result.output


@pytest.fixture
def real_store_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    directory = tmp_path / "store"
    monkeypatch.setattr(common_module, "resolve_store_dir", lambda cwd: directory)
    monkeypatch.setattr(cli_module, "derive_project_id", lambda cwd: PROJECT)
    return directory


def test_build_deps_returns_the_real_collaborators_without_running_a_process(
    tmp_path: Path, real_store_dir: Path
) -> None:
    deps = cli_module.build_deps(tmp_path, keep=True)

    qualify = deps.qualify
    assert isinstance(qualify.runner, SubprocessRunner)
    assert isinstance(qualify.qualifications, SliceCaseRecordStore)
    assert isinstance(qualify.cases, BenchmarkRecordStore)
    assert isinstance(deps.ranges, MetrologyStore)
    assert isinstance(qualify.adapter, PythonFixCaseAdapter)
    assert isinstance(qualify.suite_runner, PythonBenchmarkAdapter)
    assert qualify.keep is True
    assert qualify.project_id == PROJECT
    assert qualify.repeats >= 1
    assert not real_store_dir.exists() or list(real_store_dir.iterdir()) == []


def test_build_deps_takes_the_case_language_from_production_wiring(
    tmp_path: Path, real_store_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A language production does not support is refused here too, not silently Python."""
    monkeypatch.setattr(cli_module, "CASE_LANGUAGE", SourceLanguage.SHELL)

    with pytest.raises(UnsupportedLanguageError):
        cli_module.build_deps(tmp_path, keep=False)


def test_help_lists_every_option() -> None:
    command = (
        typer.main.get_command(app).commands["benchmark"].commands["slice-cases"].commands["build"]
    )  # type: ignore[attr-defined]
    options = {opt for param in command.params for opt in param.opts}

    assert options >= {"--set", "--repo", "--keep"}
    assert runner.invoke(app, ["benchmark", "slice-cases", "build", "--help"]).exit_code == 0
