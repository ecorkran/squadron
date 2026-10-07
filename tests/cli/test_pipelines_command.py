"""sq pipelines list (slice 199)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.run_views import render_pipeline_listing
from squadron.pipeline import loader
from squadron.pipeline.loader import PipelineInfo, PipelineSource
from tests.cli.test_run_views import write_pipeline


def test_lists_project_and_user_pipelines(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # HOME is a per-test temp dir (tests/conftest.py), so the user dir is hermetic.
    monkeypatch.chdir(tmp_path)
    write_pipeline(tmp_path / "project-documents/user/pipelines", "my-loop")
    write_pipeline(Path.home() / ".config/squadron/pipelines", "mine")

    result = CliRunner().invoke(app, ["pipelines", "list"])

    assert result.exit_code == 0, result.output
    assert "Built-in (" in result.output
    assert "Project (1)" in result.output
    assert "User (1)" in result.output


def test_no_pipelines_exits_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(loader, "_BUILTIN_DIR", tmp_path / "no-builtins")

    result = CliRunner().invoke(app, ["pipelines", "list"])

    assert result.exit_code == 0, result.output
    assert "No pipelines found." in result.output


def test_bare_group_prints_help() -> None:
    result = CliRunner().invoke(app, ["pipelines"])

    assert "list" in result.output


# ---------------------------------------------------------------------------
# Plain aligned listing (slice 174)
# ---------------------------------------------------------------------------

_BOX_DRAWING = set("─│┃━┏┓┗┛┌┐└┘├┤┬┴┼╭╮╯╰")


def _info(name: str, source: PipelineSource, params: dict[str, str] | None = None) -> PipelineInfo:
    return PipelineInfo(name, f"{name} description", source, Path(f"/x/{name}.yaml"), params or {})


def _render(pipelines: list[PipelineInfo], *, verbose: bool = False) -> list[str]:
    buffer = io.StringIO()
    render_pipeline_listing(pipelines, verbose=verbose, console=Console(file=buffer, width=200))
    return buffer.getvalue().splitlines()


class TestPlainListing:
    PIPELINES = [
        _info("p4", PipelineSource.BUILT_IN),
        _info("design-batch", PipelineSource.BUILT_IN),
        _info("a-very-long-user-pipeline", PipelineSource.USER),
    ]

    def test_group_labels_with_counts_in_listing_order(self) -> None:
        lines = _render(self.PIPELINES)

        assert lines[0] == "Built-in (2)"
        assert lines[3] == "User (1)"
        assert "Project (" not in "\n".join(lines)

    def test_name_width_is_shared_across_groups(self) -> None:
        lines = _render(self.PIPELINES)
        rows = [line for line in lines if line.startswith("  ")]

        # Every description starts in the same column, whichever group it is in.
        assert len({line.index(line.split()[1]) for line in rows}) == 1, rows

    def test_no_box_drawing(self) -> None:
        assert not _BOX_DRAWING & set("\n".join(_render(self.PIPELINES, verbose=True)))

    def test_verbose_shows_three_params_and_counts_the_rest(self) -> None:
        params = {"slice": "required", "model": "sonnet", "review-model": "minimax", "x": "1", "y": "2"}
        lines = _render([_info("loop", PipelineSource.PROJECT, params)], verbose=True)

        assert lines[1].endswith("slice=required model=sonnet review-model=minimax +2")

    def test_verbose_with_few_params_has_no_suffix(self) -> None:
        lines = _render([_info("loop", PipelineSource.PROJECT, {"slice": "required"})], verbose=True)

        assert lines[1].endswith("slice=required")

    def test_cli_verbose_flag(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(app, ["pipelines", "list", "-v"])

        assert result.exit_code == 0, result.output
        assert "slice=required" in result.output
