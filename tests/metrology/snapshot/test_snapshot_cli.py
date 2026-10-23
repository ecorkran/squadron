"""``sq metrology snapshot`` CLI tests (slice 400)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.snapshot.contract import AdapterRegistry
from squadron.metrology.snapshot_models import CodeSnapshot, SnapshotMetric, SourceLanguage
from squadron.metrology.store import MetrologyStore
from tests.metrology.snapshot.builders import make_code_snapshot, make_project_id
from tests.metrology.snapshot.conftest import SnapshotRepoFactory
from tests.metrology.snapshot.test_take import FakeAdapter

runner = CliRunner()

ConfigWriter = Callable[[Path, dict[str, object]], Path]
REMOTE_PROJECT = "github.com/manta/example-repo"


def fake_registry() -> AdapterRegistry:
    return {
        SourceLanguage.PYTHON: FakeAdapter(
            SourceLanguage.PYTHON, frozenset({SnapshotMetric.FILE_LENGTH})
        )
    }


@pytest.fixture
def store_dir(tmp_path: Path) -> Iterator[Path]:
    """Point every metrology command at one isolated store."""
    directory = tmp_path / "cli-store"
    with (
        patch("squadron.cli.commands.metrology_snapshot.resolve_store_dir", return_value=directory),
        patch("squadron.cli.commands.metrology.resolve_store_dir", return_value=directory),
        patch("squadron.cli.commands.metrology_snapshot.default_registry", fake_registry),
    ):
        yield directory


@pytest.fixture
def repo(snapshot_git_repo: SnapshotRepoFactory) -> Path:
    return snapshot_git_repo({"a.py": "x = 1\n", "run.sh": "echo hi\n"})


def snapshot_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("snapshot-*.json"))


def test_clean_run_exits_zero_and_writes_one_record(repo: Path, store_dir: Path) -> None:
    result = runner.invoke(app, ["metrology", "snapshot", "--cwd", str(repo)])

    assert result.exit_code == 0, result.output
    assert len(snapshot_files(store_dir)) == 1
    assert "python (1 file(s))" in result.output
    assert "shell (1 file(s))" in result.output
    assert "absent: no_adapter" in result.output
    assert "limits: none declared" in result.output
    assert "exclusions: 0" in result.output
    assert f"record: {snapshot_files(store_dir)[0]}" in result.output


def test_json_output_parses_as_a_code_snapshot(repo: Path, store_dir: Path) -> None:
    result = runner.invoke(app, ["metrology", "snapshot", "--cwd", str(repo), "--json"])

    assert result.exit_code == 0, result.output
    parsed = CodeSnapshot.model_validate_json(result.stdout)
    assert parsed.project_id.value == REMOTE_PROJECT
    assert {entry.language for entry in parsed.languages} == {
        SourceLanguage.PYTHON,
        SourceLanguage.SHELL,
    }


def test_limits_and_exclusions_are_reported(
    repo: Path, store_dir: Path, write_project_config: ConfigWriter
) -> None:
    write_project_config(
        repo,
        {
            "metrology.max_file_lines": 300,
            "metrology.max_function_lines": 50,
            "metrology.snapshot_exclude": "vendor/**",
        },
    )

    result = runner.invoke(app, ["metrology", "snapshot", "--cwd", str(repo)])

    assert result.exit_code == 0, result.output
    assert "limits: file 300, function 50" in result.output
    assert "exclusions: 1" in result.output


def test_dirty_tree_exits_one_naming_the_path_and_writes_nothing(repo: Path, store_dir: Path) -> None:
    (repo / "scratch.txt").write_text("x\n", encoding="utf-8")

    result = runner.invoke(app, ["metrology", "snapshot", "--cwd", str(repo)])

    assert result.exit_code == 1
    assert "scratch.txt" in result.stderr
    assert snapshot_files(store_dir) == []


def test_missing_project_identity_exits_one(
    snapshot_git_repo: SnapshotRepoFactory, store_dir: Path
) -> None:
    repo = snapshot_git_repo({"a.py": "x = 1\n"}, remote=None)

    result = runner.invoke(app, ["metrology", "snapshot", "--cwd", str(repo)])

    assert result.exit_code == 1
    assert "metrology.project_id" in result.stderr
    assert snapshot_files(store_dir) == []


def test_cwd_flag_measures_the_given_repo_not_the_process_cwd(
    repo: Path, store_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = runner.invoke(app, ["metrology", "snapshot", "--cwd", str(repo), "--json"])

    assert result.exit_code == 0, result.output
    assert CodeSnapshot.model_validate_json(result.stdout).project_id.value == REMOTE_PROJECT


def test_unwritable_store_exits_one_names_the_path_and_logs_error(
    repo: Path, store_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store_dir.write_text("a regular file where the store directory should be", encoding="utf-8")

    with caplog.at_level(logging.ERROR):
        result = runner.invoke(app, ["metrology", "snapshot", "--cwd", str(repo)])

    assert result.exit_code == 1
    assert str(store_dir) in result.stderr
    assert any(r.levelno == logging.ERROR and str(store_dir) in r.getMessage() for r in caplog.records)
    assert store_dir.is_file()


class TestOtherCommandsUnchanged:
    """Success Criterion 10: a snapshot record in the store changes no other command."""

    def run_all(self, repo: Path, tmp_path: Path) -> dict[str, tuple[int, str]]:
        commands = {
            "list": ["metrology", "list", "--cwd", str(repo)],
            "baseline": ["metrology", "report", "baseline"],
            "delta": ["metrology", "audit", "delta", str(tmp_path / "no-such-project")],
        }
        outcomes: dict[str, tuple[int, str]] = {}
        for name, argv in commands.items():
            result = runner.invoke(app, argv)
            outcomes[name] = (result.exit_code, result.output)
        return outcomes

    def test_list_report_baseline_and_audit_delta_are_unchanged(
        self, repo: Path, store_dir: Path, tmp_path: Path
    ) -> None:
        before = self.run_all(repo, tmp_path)

        MetrologyStore(store_dir=store_dir).write_snapshot(make_code_snapshot())
        assert make_project_id().value == REMOTE_PROJECT
        assert len(snapshot_files(store_dir)) == 1
        after = self.run_all(repo, tmp_path)

        assert after == before
