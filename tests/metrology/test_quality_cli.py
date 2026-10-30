"""``sq metrology slice-ranges`` CLI tests (slice 403, D4 and D10)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import patch

import click
import pytest
import typer
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.slice_range_models import RangeUnresolvedReason
from squadron.metrology.store import MetrologyStore
from tests.metrology import slice_range_repos as repos

runner = CliRunner()

ConfigWriter = Callable[[Path, dict[str, object]], Path]
PROJECT = "github.com/manta/example-repo"
CLI_MODULE = "squadron.cli.commands.metrology_quality"


@pytest.fixture
def store_dir(tmp_path: Path) -> Iterator[Path]:
    directory = tmp_path / "cli-store"
    with (
        patch(f"{CLI_MODULE}.resolve_store_dir", return_value=directory),
        patch(f"{CLI_MODULE}.resolve_diff_base", return_value="main"),
    ):
        yield directory


def with_identity(repo: Path, write_project_config: ConfigWriter) -> Path:
    """Record a project identity in the fixture repo (it has no git remote)."""
    write_project_config(repo, {"metrology.project_id": PROJECT})
    return repo


def invoke(repo: Path, *args: str) -> tuple[int, str]:
    result = runner.invoke(app, ["metrology", "slice-ranges", *args, "--cwd", str(repo)])
    return result.exit_code, result.output


def test_resolved_slice_prints_its_line_and_the_record_path(
    tmp_path: Path, store_dir: Path, write_project_config: ConfigWriter
) -> None:
    repo, _ = repos.no_ff_landing(tmp_path)
    with_identity(repo, write_project_config)

    code, output = invoke(repo, "401")

    assert code == 0
    assert "401  merge_commit  1 landing  (new)" in output
    assert f"Record: {store_dir}" in output


def test_unresolved_slice_prints_its_reason_and_exits_zero(
    tmp_path: Path, store_dir: Path, write_project_config: ConfigWriter
) -> None:
    repo = repos.not_landed(tmp_path)
    with_identity(repo, write_project_config)

    code, output = invoke(repo, "408")

    assert code == 0
    assert "408  unresolved: not_landed" in output
    assert list(store_dir.glob("*.json")) == []


def test_new_marker_appears_only_on_the_first_run(
    tmp_path: Path, store_dir: Path, write_project_config: ConfigWriter
) -> None:
    repo, _ = repos.no_ff_landing(tmp_path)
    with_identity(repo, write_project_config)

    _, first = invoke(repo, "401")
    _, second = invoke(repo, "401")

    assert "(new)" in first
    assert "401  merge_commit  1 landing" in second
    assert "(new)" not in second


def test_json_output_parses_and_carries_the_landings(
    tmp_path: Path, store_dir: Path, write_project_config: ConfigWriter
) -> None:
    repo, expected = repos.no_ff_landing(tmp_path)
    with_identity(repo, write_project_config)

    code, output = invoke(repo, "401", "--json")

    assert code == 0
    payload = json.loads(output)
    [entry] = payload["slices"]
    assert entry["slice"] == 401
    assert entry["reason"] is None
    [landing] = entry["landings"]
    assert landing["after_sha"] == expected.after
    assert landing["is_new"] is True
    assert payload["record_path"].startswith(str(store_dir))


def test_git_error_exits_one_with_the_message(
    tmp_path: Path, store_dir: Path, write_project_config: ConfigWriter
) -> None:
    repo, _ = repos.no_ff_landing(tmp_path)
    with_identity(repo, write_project_config)

    with patch(
        "squadron.metrology.slice_range.resolve_slice_landings",
        return_value=RangeUnresolvedReason.GIT_ERROR,
    ):
        code, output = invoke(repo, "401")

    assert code == 1
    assert "401  unresolved: git_error" in output
    assert "git failed while resolving slice(s) [401]" in output


def test_store_write_failure_exits_one_with_the_message(
    tmp_path: Path, store_dir: Path, write_project_config: ConfigWriter
) -> None:
    repo, _ = repos.no_ff_landing(tmp_path)
    with_identity(repo, write_project_config)

    with patch.object(
        MetrologyStore, "write_slice_ranges", side_effect=MetrologyStoreError("disk full")
    ):
        code, output = invoke(repo, "401")

    assert code == 1
    assert "Store error: disk full" in output


def test_command_exposes_the_documented_options() -> None:
    # Inspect the registered command, not --help text: forced colour in CI splits the text.
    root = typer.main.get_command(app)
    assert isinstance(root, click.Group)
    metrology = root.commands["metrology"]
    assert isinstance(metrology, click.Group)
    command = metrology.commands["slice-ranges"]

    options = {opt for param in command.params for opt in param.opts}
    assert {"--cwd", "--json"} <= options
    assert not any(param.hidden for param in command.params if isinstance(param, click.Option))
