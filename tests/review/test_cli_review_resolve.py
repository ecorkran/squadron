"""CLI-level tests for ``sq review resolve``."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.documents.frontmatter import read_frontmatter
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.resolution_evidence import DiffBaseSource

_JUDGE_TRANSPORT = "squadron.review.addressed.judge.run_review_with_profile"

_REVIEW = """\
---
docType: review
reviewType: {review_type}
slice: findings-addressed
project: squadron
verdict: CONCERNS
reviewedSha: {sha}
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "Unhandled OSError on write"
    location: src/foo.py:10
---

# Review: {review_type} — slice 305
"""


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def _commit(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, capture_output=True, check=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _repo_with_review(repo: Path, *, review_types: tuple[str, ...] = ("code",)) -> str:
    source = repo / "src" / "foo.py"
    source.parent.mkdir(exist_ok=True)
    source.write_text("def save(): ...\n")
    base_sha = _commit(repo, "work under review")

    reviews_dir = repo / REVIEWS_DIR
    reviews_dir.mkdir(parents=True, exist_ok=True)
    for review_type in review_types:
        (reviews_dir / f"305-review.{review_type}.findings-addressed.md").write_text(
            _REVIEW.format(review_type=review_type, sha=base_sha)
        )
    _commit(repo, "add review")
    return base_sha


def _commit_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def _artifact_frontmatter(repo: Path, revision: int) -> dict[str, object]:
    path = repo / REVIEWS_DIR / f"305-resolution.code.findings-addressed-r{revision}.md"
    frontmatter = read_frontmatter(path)
    assert frontmatter is not None
    return frontmatter


def _flat(output: str) -> str:
    """CLI output with rich's soft wraps removed.

    Rich wraps the artifact path to the terminal width, so a filename can land
    split across two lines. Asserting on the unwrapped text keeps the test
    about content rather than about terminal geometry.
    """
    return output.replace("\n", "")


def _judge_output(raw_output: str) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.UNKNOWN,
        findings=[],
        template_name="judge.findings-addressed",
        input_files={},
        raw_output=raw_output,
    )


class TestReviewResolveCommand:
    def test_addressed_exits_zero_and_names_the_artifact(
        self, cli_runner: CliRunner, git_repo: Path
    ) -> None:
        _repo_with_review(git_repo)
        (git_repo / "src" / "foo.py").write_text("def save():\n    try:\n        ...\n")
        _commit(git_repo, "guard the write")

        transport = AsyncMock(return_value=_judge_output("F001: addressed"))
        with patch(_JUDGE_TRANSPORT, transport):
            result = cli_runner.invoke(app, ["review", "resolve", "305", "--cwd", str(git_repo)])

        assert result.exit_code == 0, result.output
        assert "ADDRESSED" in result.output
        assert "305-resolution.code.findings-addressed-r1.md" in _flat(result.output)

    def test_unaddressed_exits_one(self, cli_runner: CliRunner, git_repo: Path) -> None:
        """Nothing changed since the review — a shell can gate on the exit code."""
        _repo_with_review(git_repo)

        with patch(_JUDGE_TRANSPORT, AsyncMock()):
            result = cli_runner.invoke(app, ["review", "resolve", "305", "--cwd", str(git_repo)])

        assert result.exit_code == 1, result.output
        assert "UNADDRESSED" in result.output

    def test_no_judge_reports_unknown_and_exits_one(
        self, cli_runner: CliRunner, git_repo: Path
    ) -> None:
        _repo_with_review(git_repo)
        (git_repo / "src" / "foo.py").write_text("changed\n")
        _commit(git_repo, "change")

        transport = AsyncMock()
        with patch(_JUDGE_TRANSPORT, transport):
            result = cli_runner.invoke(
                app, ["review", "resolve", "305", "--cwd", str(git_repo), "--no-judge"]
            )

        assert result.exit_code == 1, result.output
        assert "UNKNOWN" in result.output
        transport.assert_not_called()

    def test_ambiguous_type_lists_both_files_and_exits_nonzero(
        self, cli_runner: CliRunner, git_repo: Path
    ) -> None:
        _repo_with_review(git_repo, review_types=("code", "tasks"))

        with patch(_JUDGE_TRANSPORT, AsyncMock()):
            result = cli_runner.invoke(app, ["review", "resolve", "305", "--cwd", str(git_repo)])

        assert result.exit_code == 1, result.output
        assert "305-review.code.findings-addressed.md" in _flat(result.output)
        assert "305-review.tasks.findings-addressed.md" in _flat(result.output)

    def test_explicit_type_disambiguates(self, cli_runner: CliRunner, git_repo: Path) -> None:
        _repo_with_review(git_repo, review_types=("code", "tasks"))

        with patch(_JUDGE_TRANSPORT, AsyncMock()):
            result = cli_runner.invoke(
                app, ["review", "resolve", "305", "tasks", "--cwd", str(git_repo)]
            )

        assert result.exit_code == 1, result.output
        assert "305-resolution.tasks.findings-addressed-r1.md" in _flat(result.output)

    def test_missing_review_reports_the_index_and_exits_nonzero(
        self, cli_runner: CliRunner, git_repo: Path
    ) -> None:
        _repo_with_review(git_repo)

        result = cli_runner.invoke(app, ["review", "resolve", "999", "--cwd", str(git_repo)])

        assert result.exit_code == 1, result.output
        assert "999-review" in _flat(result.output)


class TestReviewResolveFlagPassthrough:
    """Flags with non-trivial behavior, asserted at the CLI layer.

    The unit tests prove each behavior in isolation; these prove the command
    actually wires the flag through to it, which is the regression a refactor
    of the option list would introduce.
    """

    def test_since_overrides_the_stamp(self, cli_runner: CliRunner, git_repo: Path) -> None:
        base_sha = _repo_with_review(git_repo)
        (git_repo / "src" / "foo.py").write_text("changed\n")
        _commit(git_repo, "change")
        head = _commit_head(git_repo)

        with patch(_JUDGE_TRANSPORT, AsyncMock()):
            result = cli_runner.invoke(
                app,
                ["review", "resolve", "305", "--cwd", str(git_repo), "--since", "HEAD", "-v"],
            )

        # Measuring from HEAD means nothing changed since the base, so the
        # empty-diff screen fires instead of the judge — which it would not
        # have, had the flag been dropped and the stamp used.
        assert "UNADDRESSED" in result.output
        assert head != base_sha
        frontmatter = _artifact_frontmatter(git_repo, 1)
        assert frontmatter["shaSource"] == DiffBaseSource.SINCE.value
        assert frontmatter["resolvedSha"] == "HEAD"

    def test_a_bad_since_ref_is_a_named_git_failure_not_a_crash(
        self, cli_runner: CliRunner, git_repo: Path
    ) -> None:
        _repo_with_review(git_repo)

        with patch(_JUDGE_TRANSPORT, AsyncMock()):
            result = cli_runner.invoke(
                app,
                ["review", "resolve", "305", "--cwd", str(git_repo), "--since", "no-such-ref"],
            )

        assert result.exit_code == 1, result.output
        assert "UNKNOWN" in result.output
        assert _artifact_frontmatter(git_repo, 1)["resolution"] == "UNKNOWN"

    def test_model_flag_reaches_the_judge_and_is_recorded(
        self, cli_runner: CliRunner, git_repo: Path
    ) -> None:
        """``--model`` goes through the same alias cascade as every review command."""
        _repo_with_review(git_repo)
        (git_repo / "src" / "foo.py").write_text("changed\n")
        _commit(git_repo, "change")

        transport = AsyncMock(return_value=_judge_output("F001: addressed"))
        with patch(_JUDGE_TRANSPORT, transport):
            result = cli_runner.invoke(
                app,
                [
                    "review",
                    "resolve",
                    "305",
                    "--cwd",
                    str(git_repo),
                    "--model",
                    "claude-sonnet-5",
                    "--profile",
                    "sdk",
                ],
            )

        assert result.exit_code == 0, result.output
        assert transport.call_args.kwargs["model"] == "claude-sonnet-5"
        assert transport.call_args.kwargs["profile"] == "sdk"
        assert _artifact_frontmatter(git_repo, 1)["judgeModel"] == "claude-sonnet-5"

    def test_verbose_adds_the_note_column(self, cli_runner: CliRunner, git_repo: Path) -> None:
        _repo_with_review(git_repo)

        with patch(_JUDGE_TRANSPORT, AsyncMock()):
            quiet = cli_runner.invoke(app, ["review", "resolve", "305", "--cwd", str(git_repo)])
            loud = cli_runner.invoke(app, ["review", "resolve", "305", "--cwd", str(git_repo), "-v"])

        assert "Note" not in quiet.output
        assert "Note" in loud.output
        assert "nothing changed since the review" in _flat(loud.output)
