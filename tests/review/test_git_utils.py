"""Tests for git_utils — scoped slice diff resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from squadron.review.git_utils import (
    _find_merge_commit,
    _find_slice_branch,
    resolve_slice_diff_range,
)


class TestFindSliceBranch:
    """Tests for _find_slice_branch()."""

    def test_find_branch_exists(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  122-slice.review-context-enrichment\n"

        with patch("squadron.review.git_utils.subprocess.run", return_value=mock_result):
            result = _find_slice_branch(122, ".")
        assert result == "122-slice.review-context-enrichment"

    def test_find_branch_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("squadron.review.git_utils.subprocess.run", return_value=mock_result):
            result = _find_slice_branch(999, ".")
        assert result is None

    def test_find_branch_subprocess_error(self) -> None:
        with patch(
            "squadron.review.git_utils.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            result = _find_slice_branch(122, ".")
        assert result is None


class TestFindMergeCommit:
    """Tests for _find_merge_commit()."""

    def test_find_merge_commit_found(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc1234 Merge branch '122-slice.foo'\n"

        with patch("squadron.review.git_utils.subprocess.run", return_value=mock_result):
            result = _find_merge_commit(122, ".")
        assert result == "abc1234"

    def test_find_merge_commit_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("squadron.review.git_utils.subprocess.run", return_value=mock_result):
            result = _find_merge_commit(999, ".")
        assert result is None

    def test_find_merge_commit_subprocess_error(self) -> None:
        with patch(
            "squadron.review.git_utils.subprocess.run",
            side_effect=OSError("git error"),
        ):
            result = _find_merge_commit(122, ".")
        assert result is None


class TestResolveSliceDiffRange:
    """Tests for resolve_slice_diff_range()."""

    def test_resolve_branch_exists(self) -> None:
        mb_result = MagicMock()
        mb_result.returncode = 0
        mb_result.stdout = "deadbeef\n"

        with (
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="122-slice.foo",
            ),
            patch(
                "squadron.review.git_utils.subprocess.run",
                return_value=mb_result,
            ),
        ):
            result = resolve_slice_diff_range(122, ".")
        assert result == "deadbeef...122-slice.foo"

    def test_resolve_merged(self) -> None:
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch(
                "squadron.review.git_utils._find_merge_commit",
                return_value="abc1234",
            ),
        ):
            result = resolve_slice_diff_range(122, ".")
        assert result == "abc1234^1..abc1234^2"

    def test_resolve_fallback(self, capsys: object) -> None:
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
        ):
            result = resolve_slice_diff_range(999, ".")
        assert result == "main"
        import sys
        from io import StringIO

        # Re-run to capture stderr
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            resolve_slice_diff_range(999, ".")
        assert "WARNING" in mock_stderr.getvalue()

    def test_resolve_merge_base_fails(self) -> None:
        """Branch found but merge-base fails → falls back to merge commit or main."""
        mb_result = MagicMock()
        mb_result.returncode = 1
        mb_result.stdout = ""

        with (
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="122-slice.foo",
            ),
            patch(
                "squadron.review.git_utils.subprocess.run",
                return_value=mb_result,
            ),
            patch(
                "squadron.review.git_utils._find_merge_commit",
                return_value="def5678",
            ),
        ):
            result = resolve_slice_diff_range(122, ".")
        assert result == "def5678^1..def5678^2"
