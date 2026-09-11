"""CLI-level tests for review scope resolution (slice 916).

Covers the ``--diff`` spec normalization (issue #89) at the command edge: a
spec that cannot be turned into a reviewable range must exit non-zero before
any provider work is done, since a model call spent to be told what git
already knew is pure cost.
"""

from __future__ import annotations

import json
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


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A git work tree on a feature branch with a real code change vs. main.

    The branch must actually contain reviewable changes: the empty-scope guard
    refuses a range with nothing in it, so a single-commit fixture would be
    refused before any of these assertions could run.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 1\n")
    _commit(repo, "init")
    subprocess.run(["git", "checkout", "-qb", "feature"], cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 2\n")
    _commit(repo, "feature work")
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


class TestDocumentedInvocations:
    """The shipped docs' ``--diff``-only forms must keep working (issue #70, C3).

    All ten documented examples in README.md and docs/COMMANDS.md pass --diff
    without a slice number, which is the not-persistable case. Exiting non-zero
    for that condition would break every one of them, so C3's revision has them
    exit on verdict instead. These tests are the guard on that decision.
    """

    def _invoke(self, cli_runner: CliRunner, git_repo: Path, argv: list[str]):
        with patch(
            "squadron.cli.commands.review.get_config",
            side_effect=_config_reader(str(git_repo)),
        ):
            return cli_runner.invoke(app, argv)

    def test_diff_with_json_output_is_parseable_on_stdout(
        self, cli_runner: CliRunner, mock_run_review: AsyncMock, git_repo: Path
    ) -> None:
        """README:344 — and COMMANDS.md:96 redirects stdout to a file.

        The not-persistable warning must therefore go to stderr, or the
        redirected JSON is corrupted.
        """
        result = self._invoke(
            cli_runner,
            git_repo,
            ["review", "code", "--diff", "main", "--output", "json"],
        )
        assert result.exit_code == 0, result.output
        payload = json.loads(result.stdout)
        assert payload["verdict"] == "PASS"

    def test_diff_with_files_glob(
        self, cli_runner: CliRunner, mock_run_review: AsyncMock, git_repo: Path
    ) -> None:
        """README:292."""
        result = self._invoke(
            cli_runner,
            git_repo,
            ["review", "code", "--diff", "main", "--files", "src/**/*.py"],
        )
        assert result.exit_code == 0, result.output

    def test_plain_diff_form(
        self, cli_runner: CliRunner, mock_run_review: AsyncMock, git_repo: Path
    ) -> None:
        """README:154, 286, 341 and COMMANDS.md:90."""
        result = self._invoke(cli_runner, git_repo, ["review", "code", "--diff", "main", "-v"])
        assert result.exit_code == 0, result.output

    def test_diff_to_output_file(
        self, cli_runner: CliRunner, mock_run_review: AsyncMock, git_repo: Path, tmp_path: Path
    ) -> None:
        """README:347 — --output file is the documented remedy for no slice number."""
        out = tmp_path / "result.json"
        result = self._invoke(
            cli_runner,
            git_repo,
            [
                "review",
                "code",
                "--diff",
                "main",
                "--output",
                "file",
                "--output-path",
                str(out),
            ],
        )
        assert result.exit_code == 0, result.output
        assert out.exists()

    @pytest.mark.parametrize("subcommand", ["slice", "arch", "tasks"])
    def test_bare_forms_for_other_subcommands(
        self,
        subcommand: str,
        cli_runner: CliRunner,
        mock_run_review: AsyncMock,
        git_repo: Path,
        tmp_path: Path,
    ) -> None:
        doc = tmp_path / "doc.md"
        doc.write_text("# doc\n")
        argv = ["review", subcommand, str(doc)]
        if subcommand in ("slice", "tasks"):
            argv += ["--against", str(doc)]
        result = self._invoke(cli_runner, git_repo, argv)
        assert result.exit_code == 0, result.output
