"""``sq review code --commit SHA`` reviews exactly the changes one commit introduced."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.review.models import ReviewResult, Verdict


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Three commits, each adding one file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    for name in ("first.py", "second.py", "third.py"):
        (repo / name).write_text("x = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-m", f"add {name}")
    return repo


@pytest.fixture
def mock_run_review():
    result = ReviewResult(
        verdict=Verdict.PASS,
        findings=[],
        raw_output="PASS",
        template_name="code",
        input_files={"cwd": "."},
    )
    with patch(
        "squadron.cli.commands.review.run_review_with_profile",
        new_callable=AsyncMock,
        return_value=result,
    ) as mock:
        yield mock


def _invoke(repo: Path, *args: str):
    def get_config(key: str, cwd: str = ".") -> object:
        if key == "cwd":
            return str(repo)
        if key == "verbosity":
            return 0
        return None

    with patch("squadron.cli.commands.review.get_config", side_effect=get_config):
        return CliRunner().invoke(app, ["review", "code", *args, "--no-save"])


def test_short_sha_reviews_that_commit_only(repo: Path, mock_run_review: AsyncMock) -> None:
    middle = _git(repo, "rev-parse", "HEAD~1")
    result = _invoke(repo, "--commit", middle[:7])

    assert result.exit_code == 0, result.output
    inputs = mock_run_review.call_args.args[1]
    assert inputs["diff"] == f"{_git(repo, 'rev-parse', 'HEAD~2')}..{middle}"


def test_commit_with_diff_is_refused(repo: Path, mock_run_review: AsyncMock) -> None:
    result = _invoke(repo, "--commit", "HEAD", "--diff", "main")

    assert result.exit_code == 1
    mock_run_review.assert_not_called()


def test_unknown_commit_is_refused_before_model_call(repo: Path, mock_run_review: AsyncMock) -> None:
    result = _invoke(repo, "--commit", "deadbee")

    assert result.exit_code == 1
    assert "deadbee" in result.output
    mock_run_review.assert_not_called()
