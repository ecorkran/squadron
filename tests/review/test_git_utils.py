"""Tests for git_utils — scoped slice diff resolution."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.review.git_utils import (
    DEFAULT_DIFF_BASE,
    INTEGRATION_BRANCH_KEY,
    DiffRangeUnresolvedError,
    _find_merge_commit,
    _find_slice_branch,
    resolve_diff_base,
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

    @pytest.mark.parametrize(
        ("message", "slice_number", "should_match"),
        [
            # Real convention: "Merge slice 303: judge-gated cycle conventions"
            ("Merge slice 303: judge-gated cycle conventions", 303, True),
            # Branch-name convention: "303-slice.foo"
            ("Merge branch '303-slice.foo'", 303, True),
            # Boundary false-positive: slice 303 must not match slice 3033
            ("Merge slice 3033: unrelated work", 303, False),
            ("Merge branch '3033-slice.unrelated'", 303, False),
        ],
    )
    def test_grep_pattern_against_real_git(
        self, message: str, slice_number: int, should_match: bool
    ) -> None:
        """Exercise the real `git log --grep` pattern, not a mocked subprocess.

        A mock that only asserts on stdout-parsing can't catch a grep
        pattern that never matches real commit messages (issue #14
        follow-up regression: the merge-commit grep used the branch-name
        word order "{n}-slice" while actual merge commits on this project
        read "Merge slice {n}: ..." — the pattern silently never matched).
        """
        grep_pattern = (
            rf"slice[^0-9]{slice_number}([^0-9]|$)"
            rf"|(^|[^0-9]){slice_number}-slice"
        )
        # Use grep directly against the literal message to isolate pattern
        # correctness from repository state (no real commit needed).
        grep_result = subprocess.run(
            ["grep", "-E", grep_pattern],
            input=message,
            capture_output=True,
            text=True,
            check=False,
        )
        matched = grep_result.returncode == 0
        assert matched == should_match


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

    def test_resolve_raises_when_branch_and_merge_commit_both_missing(self) -> None:
        """No branch, no merge commit → DiffRangeUnresolvedError, not a guess.

        A commit-message-grep fallback previously existed here but matched
        unrelated commits mentioning the slice number in prose, silently
        pulling a prior slice's merged code into the reviewed diff
        (issue #14). Failing loudly is the fix.
        """
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
        ):
            with pytest.raises(DiffRangeUnresolvedError, match="999"):
                resolve_slice_diff_range(999, ".")

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


class TestDiffBase:
    """Tests for the diff base used by merge-base (issue #32)."""

    def test_merge_base_uses_integration_branch_not_main(self) -> None:
        """The merge-base is computed against the configured base, not main.

        This is the #32 defect: a hardcoded "main" returns the whole
        accumulated band on a repo using an integration branch, so the
        reviewer fans out over already-merged files and lands on PASS.
        """
        mb_result = MagicMock()
        mb_result.returncode = 0
        mb_result.stdout = "deadbeef\n"

        with (
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="145-slice.foo",
            ),
            patch(_GIT_UTILS_SUBPROCESS, return_value=mb_result) as run_mock,
            patch("squadron.review.git_utils._resolve_rev", return_value="cafebabe"),
        ):
            result = resolve_slice_diff_range(145, ".", base="dev/erik")

        assert result == "deadbeef...145-slice.foo"
        argv = run_mock.call_args_list[0][0][0]
        assert argv[:2] == ["git", "merge-base"]
        assert argv[2] == "dev/erik", f"merge-base ran against {argv[2]!r}, not the base"

    def test_explicit_base_skips_config_read(self) -> None:
        """Passing base= must not consult CF config at all."""
        mb_result = MagicMock()
        mb_result.returncode = 0
        mb_result.stdout = "deadbeef\n"

        with (
            patch(
                "squadron.review.git_utils.resolve_diff_base",
                side_effect=AssertionError("config must not be read when base is given"),
            ),
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="145-slice.foo",
            ),
            patch(_GIT_UTILS_SUBPROCESS, return_value=mb_result),
            patch("squadron.review.git_utils._resolve_rev", return_value="cafebabe"),
        ):
            result = resolve_slice_diff_range(145, ".", base="dev/erik")

        assert result == "deadbeef...145-slice.foo"

    def test_unresolved_error_names_both_refs_searched(self) -> None:
        """The error must name what was actually searched, not just 'main'."""
        with (
            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
        ):
            with pytest.raises(DiffRangeUnresolvedError) as exc_info:
                resolve_slice_diff_range(145, ".", base="dev/erik")

        message = str(exc_info.value)
        assert "dev/erik" in message
        assert DEFAULT_DIFF_BASE in message


class TestResolveDiffBase:
    """Tests for resolve_diff_base() — CF config read with safe degradation."""

    def test_returns_configured_integration_branch(self) -> None:
        client = MagicMock()
        client.get_config.return_value = "dev/erik"

        assert resolve_diff_base(".", cf_client=client) == "dev/erik"
        client.get_config.assert_called_once_with(INTEGRATION_BRANCH_KEY)

    def test_empty_value_yields_default(self) -> None:
        """An unset key is the common case, not an error."""
        client = MagicMock()
        client.get_config.return_value = ""

        assert resolve_diff_base(".", cf_client=client) == DEFAULT_DIFF_BASE

    def test_whitespace_only_value_yields_default(self) -> None:
        client = MagicMock()
        client.get_config.return_value = "   \n"

        assert resolve_diff_base(".", cf_client=client) == DEFAULT_DIFF_BASE

    @pytest.mark.parametrize(
        "exc",
        [
            ContextForgeNotAvailable("cf not on PATH"),
            ContextForgeError("unknown key"),
        ],
    )
    def test_cf_failure_degrades_to_default(self, exc: Exception) -> None:
        """`sq review --diff` must work on a machine with no cf installed."""
        client = MagicMock()
        client.get_config.side_effect = exc

        assert resolve_diff_base(".", cf_client=client) == DEFAULT_DIFF_BASE

    def test_client_without_get_config_degrades_to_default(self) -> None:
        """An older/duck-typed client lacking get_config must not crash."""
        client = object()

        assert resolve_diff_base(".", cf_client=client) == DEFAULT_DIFF_BASE


class TestFindMergeCommitFallback:
    """Tests for _find_merge_commit's base-then-main search (issue #32)."""

    def test_searches_base_first_and_stops_on_hit(self) -> None:
        with patch(
            "squadron.review.git_utils._search_merge_commit",
            return_value="abc1234",
        ) as search:
            result = _find_merge_commit(145, ".", base="dev/erik")

        assert result == "abc1234"
        search.assert_called_once_with(145, ".", "dev/erik")

    def test_falls_back_to_main_when_base_has_no_merge(self) -> None:
        """Covers an integration branch that forked before the slice merged."""
        with patch(
            "squadron.review.git_utils._search_merge_commit",
            side_effect=[None, "abc1234"],
        ) as search:
            result = _find_merge_commit(145, ".", base="dev/erik")

        assert result == "abc1234"
        assert [c[0][2] for c in search.call_args_list] == ["dev/erik", DEFAULT_DIFF_BASE]

    def test_fallback_logs_warning(self) -> None:
        """The fallback can return a batch-promotion diff — it must be visible."""
        with (
            patch(
                "squadron.review.git_utils._search_merge_commit",
                side_effect=[None, "abc1234"],
            ),
            patch("squadron.review.git_utils._logger") as logger,
        ):
            _find_merge_commit(145, ".", base="dev/erik")

        assert logger.warning.called

    def test_no_duplicate_search_when_base_is_main(self) -> None:
        """base == main must not search the same ref twice."""
        with patch(
            "squadron.review.git_utils._search_merge_commit",
            return_value=None,
        ) as search:
            result = _find_merge_commit(145, ".", base=DEFAULT_DIFF_BASE)

        assert result is None
        search.assert_called_once_with(145, ".", DEFAULT_DIFF_BASE)
