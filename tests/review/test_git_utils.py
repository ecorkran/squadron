"""Tests for git_utils — scoped slice diff resolution."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from squadron.review.git_utils import (
    _find_commit_range,
    _find_merge_commit,
    _find_slice_branch,
    resolve_slice_diff_range,
)

_GIT_UTILS_SUBPROCESS = "squadron.review.git_utils.subprocess.run"


class TestFindSliceBranch:
    """Tests for _find_slice_branch()."""

    def test_find_branch_exists(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "  122-slice.review-context-enrichment\n"

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            result = _find_slice_branch(122, ".")
        assert result == "122-slice.review-context-enrichment"

    def test_find_branch_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            result = _find_slice_branch(999, ".")
        assert result is None

    def test_find_branch_subprocess_error(self) -> None:
        with patch(
            _GIT_UTILS_SUBPROCESS,
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

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            result = _find_merge_commit(122, ".")
        assert result == "abc1234"

    def test_find_merge_commit_not_found(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch(_GIT_UTILS_SUBPROCESS, return_value=mock_result):
            result = _find_merge_commit(999, ".")
        assert result is None

    def test_find_merge_commit_subprocess_error(self) -> None:
        with patch(
            _GIT_UTILS_SUBPROCESS,
            side_effect=OSError("git error"),
        ):
            result = _find_merge_commit(122, ".")
        assert result is None


class TestResolveSliceDiffRange:
    """Tests for resolve_slice_diff_range()."""

    def test_resolve_branch_exists_unmerged(self) -> None:
        """Branch exists and tip differs from merge-base → three-dot."""
        mb_result = MagicMock()
        mb_result.returncode = 0
        mb_result.stdout = "deadbeef\n"

        with (
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="122-slice.foo",
            ),
            patch(
                _GIT_UTILS_SUBPROCESS,
                return_value=mb_result,
            ),
            patch(
                "squadron.review.git_utils._resolve_rev",
                return_value="cafebabe",
            ),
        ):
            result = resolve_slice_diff_range(122, ".")
        assert result == "deadbeef...122-slice.foo"

    def test_resolve_branch_exists_already_merged(self) -> None:
        """Branch exists but tip == merge-base → fall through to merge commit."""
        mb_result = MagicMock()
        mb_result.returncode = 0
        mb_result.stdout = "deadbeef\n"

        with (
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="122-slice.foo",
            ),
            patch(
                _GIT_UTILS_SUBPROCESS,
                return_value=mb_result,
            ),
            patch(
                "squadron.review.git_utils._resolve_rev",
                return_value="deadbeef",
            ),
            patch(
                "squadron.review.git_utils._find_merge_commit",
                return_value="merge123",
            ),
        ):
            result = resolve_slice_diff_range(122, ".")
        assert result == "merge123^1..merge123^2"

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


class TestFindCommitRange:
    """Tests for _find_commit_range()."""

    def test_multiple_commits(self) -> None:
        """Multiple commits matched — return oldest^..newest."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        # git log outputs newest-first
        mock_result.stdout = (
            "aaa1111 feat: slice 181 thing\n"
            "bbb2222 fix: resolve slice 181 edge case\n"
            "ccc3333 docs: add slice 181 task file\n"
        )
        with patch(
            "squadron.review.git_utils.subprocess.run", return_value=mock_result
        ):
            result = _find_commit_range(181, ".")
        assert result == "ccc3333^..aaa1111"

    def test_single_commit(self) -> None:
        """Exactly one commit matched — return {sha}^! syntax."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc1234 feat: implement slice 181\n"
        with patch(
            "squadron.review.git_utils.subprocess.run", return_value=mock_result
        ):
            result = _find_commit_range(181, ".")
        assert result == "abc1234^!"

    def test_no_commits(self) -> None:
        """No commits matched — return None."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch(
            "squadron.review.git_utils.subprocess.run", return_value=mock_result
        ):
            result = _find_commit_range(999, ".")
        assert result is None

    def test_subprocess_error(self) -> None:
        """Git failure — return None."""
        with patch(
            "squadron.review.git_utils.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            result = _find_commit_range(181, ".")
        assert result is None

    def test_nonzero_returncode(self) -> None:
        """Non-zero exit — return None."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        mock_result.stdout = ""
        with patch(
            "squadron.review.git_utils.subprocess.run", return_value=mock_result
        ):
            result = _find_commit_range(181, ".")
        assert result is None


class TestResolveSliceDiffRangeWithCommitGrep:
    """Tests for resolve_slice_diff_range() step-3 commit-grep path."""

    def test_commit_grep_used_when_branch_and_merge_missing(self) -> None:
        """No branch, no merge commit → commit grep resolves range."""
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
            patch(
                "squadron.review.git_utils._find_commit_range",
                return_value="ccc3333^..aaa1111",
            ),
        ):
            result = resolve_slice_diff_range(181, ".")
        assert result == "ccc3333^..aaa1111"

    def test_commit_grep_single_commit(self) -> None:
        """Single matched commit → {sha}^! range returned."""
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
            patch(
                "squadron.review.git_utils._find_commit_range",
                return_value="abc1234^!",
            ),
        ):
            result = resolve_slice_diff_range(181, ".")
        assert result == "abc1234^!"

    def test_commit_grep_not_tried_when_merge_commit_found(self) -> None:
        """Merge commit found → commit grep is never called."""
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch(
                "squadron.review.git_utils._find_merge_commit",
                return_value="merge999",
            ),
            patch("squadron.review.git_utils._find_commit_range") as mock_grep,
        ):
            result = resolve_slice_diff_range(181, ".")
        assert result == "merge999^1..merge999^2"
        mock_grep.assert_not_called()

    def test_fallback_fires_when_all_three_fail(self) -> None:
        """All three resolution paths fail → warning + 'main'."""
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
            patch("squadron.review.git_utils._find_commit_range", return_value=None),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            result = resolve_slice_diff_range(999, ".")
        assert result == "main"
        assert "WARNING" in mock_stderr.getvalue()
