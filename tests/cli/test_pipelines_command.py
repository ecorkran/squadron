"""sq pipelines list (slice 199)."""

from __future__ import annotations

import io
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import Result
from rich.console import Console
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.run_views import render_pipeline_listing
from squadron.data import data_dir
from squadron.pipeline import loader
from squadron.pipeline.loader import (
    PipelineInfo,
    PipelineLocation,
    PipelineSource,
    load_pipeline,
    resolve_pipeline,
)
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
        assert lines[3] == ""  # blank line between groups
        assert lines[4] == "User (1)"
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


# ---------------------------------------------------------------------------
# sq pipelines show (slice 174)
# ---------------------------------------------------------------------------


class TestPipelinesShow:
    @pytest.fixture
    def project(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.chdir(tmp_path)
        directory = tmp_path / "project-documents/user/pipelines"
        directory.mkdir(parents=True)
        return directory

    def test_built_in(self, project: Path) -> None:
        result = CliRunner().invoke(app, ["pipelines", "show", "p4"])
        builtin = data_dir() / "pipelines" / "P4.yaml"

        assert result.exit_code == 0, result.output
        assert result.stdout_bytes == (
            f"# source: built-in\n# path: {builtin}\n".encode() + builtin.read_bytes()
        )

    def test_project_shadow_shows_the_shadow(self, project: Path) -> None:
        write_pipeline(project, "p4", "project copy of p4")

        result = CliRunner().invoke(app, ["pipelines", "show", "P4"])

        lines = result.stdout.splitlines()
        assert lines[0] == "# source: project"
        assert lines[1] == f"# path: {project / 'p4.yaml'}"
        assert "project copy of p4" in result.stdout

    def test_path_only(self, project: Path) -> None:
        result = CliRunner().invoke(app, ["pipelines", "show", "p4", "--path"])

        assert result.exit_code == 0
        assert result.stdout.strip() == str(data_dir() / "pipelines" / "P4.yaml")

    @pytest.mark.parametrize("name", ["nope", "data/pipelines/P4.yaml"])
    def test_not_found_exits_1_with_loader_message(self, project: Path, name: str) -> None:
        result = CliRunner().invoke(app, ["pipelines", "show", name])

        assert result.exit_code == 1
        assert "not found in any pipeline directory" in result.stderr
        assert result.stdout == ""

    def test_unreadable_file(self, project: Path, caplog: pytest.LogCaptureFixture) -> None:
        write_pipeline(project, "locked")
        path = project / "locked.yaml"
        path.chmod(0o000)
        try:
            with caplog.at_level(logging.ERROR):
                result = CliRunner().invoke(app, ["pipelines", "show", "locked"])
        finally:
            path.chmod(0o644)

        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr.startswith(f"Error: cannot read {path}:")
        assert any(r.levelno == logging.ERROR and str(path) in r.getMessage() for r in caplog.records)

    def test_non_utf8_bytes_pass_through(self, project: Path) -> None:
        raw = b"name: odd\ndescription: caf\xe9\nsteps: []\n"
        (project / "odd.yaml").write_bytes(raw)

        result = CliRunner().invoke(app, ["pipelines", "show", "odd"])

        assert result.exit_code == 0
        assert result.stdout_bytes.endswith(raw)


class TestResolvePipeline:
    def test_project_wins_and_names_its_source(self, tmp_path: Path) -> None:
        write_pipeline(tmp_path / "proj", "p4")

        location = resolve_pipeline("P4", project_dir=tmp_path / "proj", user_dir=tmp_path / "u")

        assert location == PipelineLocation("p4", PipelineSource.PROJECT, tmp_path / "proj" / "p4.yaml")

    def test_user_then_built_in(self, tmp_path: Path) -> None:
        write_pipeline(tmp_path / "user", "mine")

        mine = resolve_pipeline("mine", project_dir=tmp_path / "p", user_dir=tmp_path / "user")
        builtin = resolve_pipeline("p4", project_dir=tmp_path / "p", user_dir=tmp_path / "user")

        assert mine.source is PipelineSource.USER
        assert builtin.source is PipelineSource.BUILT_IN

    def test_invalid_pipeline_file_still_resolves(self, tmp_path: Path) -> None:
        (tmp_path / "proj").mkdir()
        (tmp_path / "proj" / "broken.yaml").write_text("steps: [unclosed\n")

        location = resolve_pipeline("broken", project_dir=tmp_path / "proj", user_dir=tmp_path / "u")

        assert location.path.name == "broken.yaml"

    def test_not_found_names_searched_directories(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Searched:"):
            resolve_pipeline("nope", project_dir=tmp_path / "p", user_dir=tmp_path / "u")


class TestListingShadowMarker:
    def test_shadowing_row_carries_the_marker_and_others_do_not(self) -> None:
        shadowing = PipelineInfo(
            "p4", "p4 description", PipelineSource.USER, Path("/u/p4.yaml"), {}, PipelineSource.BUILT_IN
        )
        plain = _info("other", PipelineSource.BUILT_IN)

        lines = _render([shadowing, plain])

        assert [line for line in lines if "shadows built-in" in line] == [
            next(line for line in lines if line.lstrip().startswith("p4"))
        ]
        assert not any("shadows" in line for line in lines if "other" in line)

    def test_listing_without_shadows_has_no_extra_column(self) -> None:
        lines = _render([_info("alpha", PipelineSource.BUILT_IN)])

        assert not any("shadows" in line for line in lines)

    def test_cli_marks_a_user_copy_of_a_builtin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.chdir(tmp_path)
        CliRunner().invoke(app, ["pipelines", "copy", "p4"])

        result = CliRunner().invoke(app, ["pipelines", "list"])

        assert any("shadows built-in" in line and "p4" in line for line in result.stdout.splitlines())


class TestPipelinesCopy:
    @pytest.fixture
    def homes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
        """(user pipelines dir, project pipelines dir) under a temporary home and cwd."""
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        project = tmp_path / "proj"
        project.mkdir()
        monkeypatch.chdir(project)
        return (
            tmp_path / "home/.config/squadron/pipelines",
            project / "project-documents/user/pipelines",
        )

    @staticmethod
    def _copy(*args: str) -> Result:
        return CliRunner().invoke(app, ["pipelines", "copy", *args])

    def test_built_in_copy_is_byte_identical_with_shadow_notice(self, homes: tuple[Path, Path]) -> None:
        user_dir, _ = homes
        builtin = data_dir() / "pipelines" / "P4.yaml"

        result = self._copy("p4")

        target = user_dir / "p4.yaml"
        assert result.exit_code == 0, result.output
        assert result.stdout == f"{target}\n"
        assert "shadows the built-in pipeline 'p4'" in result.stderr
        assert target.read_bytes() == builtin.read_bytes()
        assert "# source:" not in target.read_text()

    def test_new_name_copy_has_no_shadow_notice(self, homes: tuple[Path, Path]) -> None:
        user_dir, _ = homes

        result = self._copy("p4", "my-p4")

        assert result.exit_code == 0, result.output
        assert (user_dir / "my-p4.yaml").is_file()
        assert result.stderr == ""

    def test_project_scope_writes_under_project_documents_and_builtin_still_resolves(
        self, homes: tuple[Path, Path]
    ) -> None:
        _, project_dir = homes

        result = self._copy("p4", "--project")

        assert result.exit_code == 0, result.output
        assert (project_dir / "p4.yaml").is_file()
        assert resolve_pipeline("p4").source is PipelineSource.PROJECT
        assert resolve_pipeline(
            "p4", project_dir=Path("/nonexistent"), user_dir=Path("/nonexistent")
        ).source is (PipelineSource.BUILT_IN)

    def test_second_copy_needs_force_and_refusal_leaves_the_file_unchanged(
        self, homes: tuple[Path, Path]
    ) -> None:
        # A named copy: once an unnamed copy shadows the original, the name resolves to the
        # copy itself, so a repeat copy of that name is the own-file refusal (next test).
        user_dir, _ = homes
        self._copy("p4", "my-p4")
        target = user_dir / "my-p4.yaml"
        target.write_text("edited\n")

        refused = self._copy("p4", "my-p4")
        assert refused.exit_code == 1
        assert str(target) in refused.stderr.replace("\n", "")
        assert target.read_text() == "edited\n"

        forced = self._copy("p4", "my-p4", "--force")
        assert forced.exit_code == 0
        assert target.read_bytes() == (data_dir() / "pipelines" / "P4.yaml").read_bytes()

    def test_copying_onto_its_own_file_is_refused(self, homes: tuple[Path, Path]) -> None:
        user_dir, _ = homes
        write_pipeline(user_dir, "mine")

        result = self._copy("mine")

        assert result.exit_code == 1
        assert "nothing to copy" in result.stderr

    def test_unknown_name_surfaces_the_resolver_message(self, homes: tuple[Path, Path]) -> None:
        with pytest.raises(FileNotFoundError) as expected:
            resolve_pipeline("no-such-pipeline")

        result = self._copy("no-such-pipeline")

        assert result.exit_code == 1
        assert str(expected.value).split("\n")[0] in result.stderr

    def test_new_name_with_a_path_separator_is_refused(self, homes: tuple[Path, Path]) -> None:
        result = self._copy("p4", "../escape")

        assert result.exit_code == 1
        assert not (homes[0].parent / "escape.yaml").exists()

    @pytest.mark.parametrize(
        "error", [PermissionError(13, "Permission denied"), FileNotFoundError(2, "gone")]
    )
    def test_unreadable_or_vanished_source_logs_and_exits_1(
        self, homes: tuple[Path, Path], caplog: pytest.LogCaptureFixture, error: OSError
    ) -> None:
        builtin = data_dir() / "pipelines" / "P4.yaml"
        with (
            patch.object(Path, "read_bytes", side_effect=error),
            caplog.at_level(logging.ERROR),
        ):
            result = self._copy("p4")

        assert result.exit_code == 1
        assert any(str(builtin) in record.getMessage() for record in caplog.records)
        assert not (homes[0] / "p4.yaml").exists()

    def test_write_error_logs_and_exits_1_without_a_partial_file(
        self, homes: tuple[Path, Path], caplog: pytest.LogCaptureFixture
    ) -> None:
        user_dir, _ = homes
        with (
            patch(
                "squadron.cli.commands.pipelines.write_new_file", side_effect=OSError(28, "No space")
            ),
            caplog.at_level(logging.ERROR),
        ):
            result = self._copy("p4")

        assert result.exit_code == 1
        assert any(str(user_dir / "p4.yaml") in record.getMessage() for record in caplog.records)
        assert not (user_dir / "p4.yaml").exists()

    def test_run_loads_the_copy_after_a_same_name_copy(self, homes: tuple[Path, Path]) -> None:
        user_dir, _ = homes
        self._copy("p4")
        (user_dir / "p4.yaml").write_text(
            (user_dir / "p4.yaml").read_text().replace("description:", "description: COPY ", 1)
        )

        assert "COPY" in load_pipeline("p4").description
