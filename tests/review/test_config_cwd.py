"""Tests for config-based --cwd resolution in review commands."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.review.models import ReviewResult, Verdict


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def pass_result() -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="code",
        input_files={"cwd": "."},
    )


@pytest.fixture
def mock_run_review(pass_result: ReviewResult):
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=pass_result,
    ) as mock:
        yield mock


class TestConfigCwd:
    """Test config-based cwd resolution."""

    def test_config_cwd_used_when_no_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "cwd":
                return "/configured/path"
            if key == "verbosity":
                return 0
            return None

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=mock_get_config,
        ):
            result = cli_runner.invoke(app, ["review", "code", "--files", "**/*"])
            assert result.exit_code == 0
            # Verify run_review was called with the config cwd
            call_args = mock_run_review.call_args
            _, inputs = call_args.args
            assert inputs["cwd"] == "/configured/path"

    def test_flag_overrides_config_cwd(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "cwd":
                return "/configured/path"
            if key == "verbosity":
                return 0
            return None

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=mock_get_config,
        ):
            result = cli_runner.invoke(
                app, ["review", "code", "--cwd", "/explicit/path", "--files", "**/*"]
            )
            assert result.exit_code == 0
            call_args = mock_run_review.call_args
            _, inputs = call_args.args
            assert inputs["cwd"] == "/explicit/path"

    def test_default_dot_when_no_config_no_flag(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
    ) -> None:
        def mock_get_config(key: str, cwd: str = ".") -> object:
            if key == "cwd":
                return "."
            if key == "verbosity":
                return 0
            return None

        with (
            patch(
                "squadron.cli.commands.review.get_config",
                side_effect=mock_get_config,
            ),
            patch(
                "squadron.cli.commands.review.find_git_root",
                return_value=".",
            ),
        ):
            result = cli_runner.invoke(app, ["review", "code", "--files", "**/*"])
            assert result.exit_code == 0
            call_args = mock_run_review.call_args
            _, inputs = call_args.args
            assert inputs["cwd"] == "."


@pytest.fixture
def git_repo_with_subdir(tmp_path: Path) -> tuple[Path, Path]:
    """A real git work tree with a nested subdirectory.

    Returns ``(repo_root, subdir)``. A real repo is used rather than a mocked
    ``find_git_root`` so the test exercises the same rev-parse the CLI runs.
    """
    repo = tmp_path / "repo"
    subdir = repo / "project-documents" / "user"
    subdir.mkdir(parents=True)
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("# probe\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo, subdir


def _config_reader(cwd_value: str):
    """Build a ``get_config`` stub returning ``cwd_value`` for the cwd key."""

    def mock_get_config(key: str, cwd: str = ".") -> object:
        if key == "cwd":
            return cwd_value
        if key == "verbosity":
            return 0
        return None

    return mock_get_config


class TestJailRootIsGitRoot:
    """The reviewing agent's cwd is its tool jail root (issue #86).

    A configured cwd pointing at a subdirectory of the repo made every
    repo-relative path in the prompt unopenable. ``slice``, ``arch``, and
    ``tasks`` all resolved the raw cwd; only ``code`` anchored at the git root.
    """

    @pytest.mark.parametrize("subcommand", ["slice", "arch", "tasks"])
    def test_subdir_cwd_yields_git_root(
        self,
        subcommand: str,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        git_repo_with_subdir: tuple[Path, Path],
    ) -> None:
        repo, subdir = git_repo_with_subdir
        input_file = repo / "input.md"
        input_file.write_text("# input\n")

        argv = ["review", subcommand, str(input_file), "--no-save"]
        if subcommand in ("slice", "tasks"):
            argv += ["--against", str(input_file)]

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=_config_reader(str(subdir)),
        ):
            result = cli_runner.invoke(app, argv)

        assert result.exit_code == 0, result.output
        _, inputs = mock_run_review.call_args.args
        # The jail root is the repo root, not the configured subdirectory.
        assert Path(inputs["cwd"]).resolve() == repo.resolve()
        assert Path(inputs["cwd"]).resolve() != subdir.resolve()

    def test_cwd_outside_git_work_tree_falls_back(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """No git work tree: the helper falls back to the resolved cwd, not an error."""
        outside = tmp_path / "not-a-repo"
        outside.mkdir()
        input_file = outside / "input.md"
        input_file.write_text("# input\n")

        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=_config_reader(str(outside)),
        ):
            result = cli_runner.invoke(
                app,
                [
                    "review",
                    "slice",
                    str(input_file),
                    "--against",
                    str(input_file),
                    "--no-save",
                ],
            )

        assert result.exit_code == 0, result.output
        _, inputs = mock_run_review.call_args.args
        assert Path(inputs["cwd"]).resolve() == outside.resolve()
