"""Tests for the branch-and-range git helpers added for slice 385.

Kept separate from ``test_git_utils.py`` (already near the project's
~450-line file-size guideline) per the task's own instruction.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from squadron.review.git_utils import (
    DetachedHeadError,
    GitRangeUnavailableError,
    commits_in_range,
    current_branch,
)

_GIT_UTILS_SUBPROCESS = "squadron.review.git_utils.subprocess.run"


class TestCurrentBranch:
    def test_normal_checkout(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "385-slice.create-a-pr-with-a-good-message\n"

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            result = current_branch(".")
        assert result == "385-slice.create-a-pr-with-a-good-message"

    def test_detached_head_raises(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "HEAD\n"

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            try:
                current_branch(".")
                raise AssertionError("expected DetachedHeadError")
            except DetachedHeadError:
                pass

    def test_git_unavailable_raises(self) -> None:
        with patch(_GIT_UTILS_SUBPROCESS, side_effect=FileNotFoundError("git not found")):
            try:
                current_branch(".")
                raise AssertionError("expected DetachedHeadError")
            except DetachedHeadError:
                pass


class TestCommitsInRange:
    def test_several_commits(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "sha2 second commit\nsha1 first commit\n"

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            records = commits_in_range("main", "head", cwd=".")

        assert [r.sha for r in records] == ["sha2", "sha1"]
        assert [r.subject for r in records] == ["second commit", "first commit"]

    def test_empty_range_returns_empty_list_not_none(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            records = commits_in_range("main", "head", cwd=".")

        assert records == []

    def test_git_unavailable_is_distinguished_from_empty_range(self) -> None:
        with patch(_GIT_UTILS_SUBPROCESS, side_effect=OSError("git not found")):
            try:
                commits_in_range("main", "head", cwd=".")
                raise AssertionError("expected GitRangeUnavailableError")
            except GitRangeUnavailableError:
                pass

    def test_git_refusal_is_distinguished_from_empty_range(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        mock_result.stderr = "fatal: bad revision 'main..head'"

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            try:
                commits_in_range("main", "head", cwd=".")
                raise AssertionError("expected GitRangeUnavailableError")
            except GitRangeUnavailableError:
                pass
