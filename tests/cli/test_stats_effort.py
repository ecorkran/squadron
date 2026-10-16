"""``sq stats slice`` and ``sq stats slices`` end to end (slice 176 D7, D9, criteria 4-5)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.pipeline.state import StateManager
from tests.stats.effort_project import build_project
from tests.stats.repo_support import StatsRepo, write_run_file

runner = CliRunner()


@pytest.fixture
def project(
    stats_repo: StatsRepo, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[StatsRepo]:
    """Slice 176 in a temp repo that is the working directory, with its own runs dir."""
    build_project(stats_repo)
    runs = tmp_path / "runs"
    runs.mkdir()
    write_run_file(runs, "run-176", 176, cost_usd=0.5)
    monkeypatch.chdir(stats_repo.root)
    with patch("squadron.cli.commands.stats.StateManager", lambda: StateManager(runs_dir=runs)):
        yield stats_repo


def _json(*args: str) -> dict[str, object]:
    result = runner.invoke(app, ["stats", *args, "--json"])
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_slice_table_and_json_show_the_same_values(project: StatsRepo) -> None:
    table = runner.invoke(app, ["stats", "slice", "176"])
    data = _json("slice", "176")

    assert table.exit_code == 0, table.output
    assert "Slice 176  Effort Example  planned effort 3/5  window: branch" in table.output
    assert f"impl commits {data['implementation_commits']}" in table.output
    assert f"fix-ups {data['fixups']}" in table.output
    groups = data["groups"]
    assert isinstance(groups, list)
    assert str(groups[0]["marker_sha"])[:8] in table.output
    assert "marker not found" in table.output  # the third group, in its marker cell
    assert "$0.75 (2 of 3 priced)" in table.output
    assert data["spend"]["totals"]["cost_usd"] == 0.75  # type: ignore[index]


def test_slices_table_and_json_show_the_same_values(project: StatsRepo) -> None:
    table = runner.invoke(app, ["stats", "slices"])
    data = _json("slices")

    assert table.exit_code == 0, table.output
    levels = data["levels"]
    assert isinstance(levels, list) and [level["level"] for level in levels] == [3]
    assert "Completed slices 1" in table.output
    row = next(line for line in table.output.splitlines() if line.strip().startswith("3/5"))
    assert f" {levels[0]['n']} " in row
    assert "6d" in row  # the one slice's span, 6 days, as the JSON's 518400 seconds
    assert levels[0]["measures"]["span"]["median"] == 518400.0


def test_outside_a_git_repo_exits_1_naming_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    monkeypatch.chdir(plain)

    result = runner.invoke(app, ["stats", "slice", "176"])

    assert result.exit_code == 1
    assert str(Path.cwd()) in result.output


def test_unknown_index_exits_1_naming_the_plan_files(project: StatsRepo) -> None:
    result = runner.invoke(app, ["stats", "slice", "4242"])

    assert result.exit_code == 1
    assert "4242" in result.output and "140-slices.x.md" in result.output


def test_malformed_since_exits_1_naming_the_value_and_format(project: StatsRepo) -> None:
    result = runner.invoke(app, ["stats", "slices", "--since", "2026-10"])

    assert result.exit_code == 1
    assert "'2026-10'" in result.output and "YYYYMMDD" in result.output


def test_an_empty_rollup_prints_its_reason_and_exits_0(project: StatsRepo) -> None:
    result = runner.invoke(app, ["stats", "slices", "--since", "20271231"])

    assert result.exit_code == 0
    assert "no completed slices since 20271231" in result.output


def _snapshot(repo: StatsRepo, runs: Path) -> tuple[str, str, list[str]]:
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo.root, capture_output=True, text=True, check=True
    ).stdout
    refs = repo.git("for-each-ref")
    return status, refs, sorted(path.name for path in runs.iterdir())


def test_the_commands_write_no_file_ref_or_run_state(project: StatsRepo, tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    before = _snapshot(project, runs)

    for args in (["slice", "176"], ["slice", "176", "--json"], ["slices"], ["slices", "--json"]):
        assert runner.invoke(app, ["stats", *args]).exit_code == 0

    assert _snapshot(project, runs) == before
