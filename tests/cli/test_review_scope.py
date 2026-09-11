"""CLI-level tests for review scope resolution (slice 916).

Covers the ``--diff`` spec normalization (issue #89) at the command edge: a
spec that cannot be turned into a reviewable range must exit non-zero before
any provider work is done, since a model call spent to be told what git
already knew is pure cost.
"""

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
def git_repo(tmp_path: Path) -> Path:
    """A real git work tree with one commit on a known branch."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


@pytest.fixture
def mock_run_review():
    """Stand in for the provider call, so 'was the model invoked' is assertable."""
    result = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="## Summary\nPASS\n",
        template_name="code",
        input_files={"cwd": "."},
    )
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock:
        yield mock


def _config_reader(cwd_value: str):
    def mock_get_config(key: str, cwd: str = ".") -> object:
        if key == "cwd":
            return cwd_value
        if key == "verbosity":
            return 0
        return None

    return mock_get_config


class TestDiffSpecNormalizationAtCLI:
    def test_unresolvable_ref_exits_nonzero_without_model_call(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        git_repo: Path,
    ) -> None:
        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=_config_reader(str(git_repo)),
        ):
            result = cli_runner.invoke(
                app, ["review", "code", "--diff", "no-such-ref-xyz", "--no-save"]
            )

        assert result.exit_code != 0
        mock_run_review.assert_not_called()

    def test_bare_ref_reaches_both_consumers_normalized(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        git_repo: Path,
    ) -> None:
        """The prompt input and the path extraction get the same normalized range."""
        with (
            patch(
                "squadron.cli.commands.review.get_config",
                side_effect=_config_reader(str(git_repo)),
            ),
            patch(
                "squadron.cli.commands.review.extract_diff_paths",
                return_value=["app.py"],
            ) as mock_extract,
        ):
            result = cli_runner.invoke(app, ["review", "code", "--diff", "main", "--no-save"])

        assert result.exit_code == 0, result.output
        _, inputs = mock_run_review.call_args.args
        assert inputs["diff"] == "main...HEAD"
        if mock_extract.call_args is not None:
            assert mock_extract.call_args.args[0] == "main...HEAD"

    def test_explicit_range_is_not_rewritten(
        self,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        git_repo: Path,
    ) -> None:
        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=_config_reader(str(git_repo)),
        ):
            result = cli_runner.invoke(app, ["review", "code", "--diff", "main..HEAD", "--no-save"])

        assert result.exit_code == 0, result.output
        _, inputs = mock_run_review.call_args.args
        assert inputs["diff"] == "main..HEAD"
