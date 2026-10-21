import json
import logging
from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()


@pytest.fixture
def plain_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A directory outside any git repository, as the working directory."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_json_is_one_line_that_parses(plain_dir: Path) -> None:
    result = runner.invoke(app, ["probe", "--json"])

    assert result.exit_code == 0
    assert len(result.stdout.strip().splitlines()) == 1
    assert json.loads(result.stdout)["probe_version"] == 1


def test_default_output_is_multiline_and_equals_json_output(plain_dir: Path) -> None:
    compact = runner.invoke(app, ["probe", "--json"])
    pretty = runner.invoke(app, ["probe"])

    assert pretty.exit_code == 0
    assert len(pretty.stdout.strip().splitlines()) > 1
    assert json.loads(pretty.stdout) == json.loads(compact.stdout)


def test_probe_failure_exits_one_with_empty_stdout(
    plain_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(cwd: Path) -> None:
        raise RuntimeError("probe broke")

    monkeypatch.setattr("squadron.cli.commands.probe.build_probe", explode)

    result = runner.invoke(app, ["probe", "--json"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "probe broke" in result.stderr


def test_warning_run_keeps_stdout_pure_json(plain_dir: Path, caplog: pytest.LogCaptureFixture) -> None:
    graph_dir = plain_dir / ".understand-anything"
    graph_dir.mkdir()
    (graph_dir / "knowledge-graph.json").write_text("{}")
    (graph_dir / "meta.json").write_text("not json")

    with caplog.at_level(logging.WARNING):
        result = runner.invoke(app, ["probe", "--json"])

    assert result.exit_code == 0
    assert any(record.levelno == logging.WARNING for record in caplog.records)
    assert json.loads(result.stdout)["graph"]["commit"] is None


def test_outside_a_repository_exits_zero_with_unknown_commits_behind(plain_dir: Path) -> None:
    result = runner.invoke(app, ["probe", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["graph"]["commits_behind"] is None
