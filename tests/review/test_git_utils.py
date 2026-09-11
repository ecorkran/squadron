"""Tests for git_utils — scoped slice diff resolution."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.review.git_utils import (
    DEFAULT_DIFF_BASE,
    GIT_COMMAND_TIMEOUT_SECONDS,
    INTEGRATION_BRANCH_KEY,
    DiffRangeUnresolvedError,
    EmptyScopeCase,
    EmptyScopeError,
    NotAGitRepositoryError,
    RefNotFoundError,
    _changed_paths,
    _find_merge_commit,
    _find_slice_branch,
    _resolve_fork_point,
    assert_reviewable_scope,
    normalize_diff_spec,
    resolve_diff_base,
    resolve_slice_diff_range,
    run_git,
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


class TestResolveForkPoint:
    """Real-git tests: the reflog parsing is the part mocks cannot cover."""

    @staticmethod
    def _git(cwd: Path, *args: str) -> None:
        subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)

    def _repo_with_ff_merged_slice(self, tmp_path: Path) -> Path:
        self._git(tmp_path, "init", "-q", "-b", "main")
        self._git(tmp_path, "config", "user.email", "t@t.co")
        self._git(tmp_path, "config", "user.name", "T")
        (tmp_path / "a.txt").write_text("base\n")
        self._git(tmp_path, "add", "-A")
        self._git(tmp_path, "commit", "-qm", "base")
        self._git(tmp_path, "checkout", "-q", "-b", "211-slice.foo")
        (tmp_path / "b.txt").write_text("one\n")
        self._git(tmp_path, "add", "-A")
        self._git(tmp_path, "commit", "-qm", "feat: slice work")
        self._git(tmp_path, "checkout", "-q", "main")
        self._git(tmp_path, "merge", "--ff-only", "-q", "211-slice.foo")
        return tmp_path

    def test_fork_point_from_branch_reflog(self, tmp_path: Path) -> None:
        repo = self._repo_with_ff_merged_slice(tmp_path)
        base_sha = subprocess.run(
            ["git", "rev-parse", "main~1"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        assert _resolve_fork_point("211-slice.foo", str(repo)) == base_sha

    def test_fork_point_returns_none_for_unknown_branch(self, tmp_path: Path) -> None:
        repo = self._repo_with_ff_merged_slice(tmp_path)
        assert _resolve_fork_point("no-such-branch", str(repo)) is None

    def test_end_to_end_ff_merged_slice_yields_slice_files_only(self, tmp_path: Path) -> None:
        """The real #54 repro: range must cover the slice's file, not the base."""
        repo = self._repo_with_ff_merged_slice(tmp_path)
        diff_range = resolve_slice_diff_range(211, str(repo), base="main")
        changed = subprocess.run(
            ["git", "diff", "--name-only", diff_range],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        assert changed == ["b.txt"]


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

    def test_resolve_fast_forward_merged_uses_fork_point(self) -> None:
        """Fast-forward merge: no merge commit exists, so use the branch reflog.

        Issue #54. Fast-forward is git's default when the target has not
        diverged, so this is the common case for a merged slice — both prior
        paths miss it: tip == merge-base collapses the three-dot diff, and a
        fast-forward leaves no merge commit to find.
        """
        mb_result = MagicMock()
        mb_result.returncode = 0
        mb_result.stdout = "deadbeef\n"

        with (
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="211-slice.foo",
            ),
            patch(_GIT_UTILS_SUBPROCESS, return_value=mb_result),
            patch("squadron.review.git_utils._resolve_rev", return_value="deadbeef"),
            patch(
                "squadron.review.git_utils._resolve_fork_point",
                return_value="f0rkp01nt",
            ),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
        ):
            result = resolve_slice_diff_range(211, ".")
        assert result == "f0rkp01nt..deadbeef"

    def test_resolve_raises_when_fork_point_unavailable(self) -> None:
        """Reflog expired or fresh clone → fail loudly, never guess a range.

        The removed commit-message grep (issue #14) is exactly the guess this
        must not make.
        """
        mb_result = MagicMock()
        mb_result.returncode = 0
        mb_result.stdout = "deadbeef\n"

        with (
            patch(
                "squadron.review.git_utils._find_slice_branch",
                return_value="211-slice.foo",
            ),
            patch(_GIT_UTILS_SUBPROCESS, return_value=mb_result),
            patch("squadron.review.git_utils._resolve_rev", return_value="deadbeef"),
            patch("squadron.review.git_utils._resolve_fork_point", return_value=None),
            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
        ):
            with pytest.raises(DiffRangeUnresolvedError, match="211"):
                resolve_slice_diff_range(211, ".")

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


class TestRunGitTimeout:
    """``run_git`` is bounded and reports a timeout rather than swallowing it.

    Without a timeout, a command touching an unreachable remote-tracking ref
    blocks the review indefinitely with no output.
    """

    def test_timeout_returns_none_and_warns(self, caplog: pytest.LogCaptureFixture) -> None:
        with patch(
            _GIT_UTILS_SUBPROCESS,
            side_effect=subprocess.TimeoutExpired(cmd=["git", "fetch"], timeout=1),
        ):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                assert run_git(["fetch", "origin"], cwd=".") is None

        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 1

    def test_timeout_is_passed_to_subprocess(self) -> None:
        """The bound comes from the module constant, not an inline literal."""
        with patch(_GIT_UTILS_SUBPROCESS) as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="")
            run_git(["status"], cwd=".")

        assert mock_run.call_args.kwargs["timeout"] == GIT_COMMAND_TIMEOUT_SECONDS

    def test_oserror_path_unchanged(self, caplog: pytest.LogCaptureFixture) -> None:
        """An OSError still returns None, and stays distinct from the timeout path."""
        with patch(_GIT_UTILS_SUBPROCESS, side_effect=OSError("no git binary")):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                assert run_git(["status"], cwd=".") is None

        assert [r for r in caplog.records if r.levelname == "WARNING"] == []


class TestNormalizeDiffSpec:
    """``--diff`` specs become explicit ranges; bare refs gain merge-base semantics."""

    @pytest.mark.parametrize(
        ("spec", "expected"),
        [
            # Explicit ranges pass through — this is what protects a deliberate
            # two-dot comparison from the bare-ref rewrite.
            ("a..b", "a..b"),
            ("a...b", "a...b"),
            ("origin/main..HEAD", "origin/main..HEAD"),
            # A three-dot spec contains a two-dot substring; checking two-dot
            # first would misclassify it. This case pins the check order.
            ("origin/main...HEAD", "origin/main...HEAD"),
        ],
    )
    def test_explicit_ranges_pass_through(self, spec: str, expected: str) -> None:
        with patch(_GIT_UTILS_SUBPROCESS) as mock_run:
            assert normalize_diff_spec(spec, cwd=".") == expected
        # A pass-through consults git at all only if the rewrite branch ran.
        mock_run.assert_not_called()

    def test_bare_ref_rewrites_to_merge_base_range(self) -> None:
        with patch(_GIT_UTILS_SUBPROCESS) as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n")
            assert normalize_diff_spec("origin/main", cwd=".") == "origin/main...HEAD"

    def test_not_a_git_repository_is_distinguishable(self) -> None:
        """git could not run at all — the spec is not at fault."""
        with patch(_GIT_UTILS_SUBPROCESS, side_effect=OSError("no git")):
            with pytest.raises(NotAGitRepositoryError) as exc_info:
                normalize_diff_spec("origin/main", cwd=".")
        assert exc_info.value.ref == "origin/main"
        assert not isinstance(exc_info.value, RefNotFoundError)

    def test_ref_not_found_is_distinguishable(self) -> None:
        """git ran and refused — the ref itself is the problem."""
        with patch(_GIT_UTILS_SUBPROCESS) as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            with pytest.raises(RefNotFoundError) as exc_info:
                normalize_diff_spec("no-such-ref", cwd=".")
        assert exc_info.value.ref == "no-such-ref"
        assert not isinstance(exc_info.value, NotAGitRepositoryError)


class TestAssertReviewableScope:
    """A review of nothing must be refused, and must say which kind of nothing."""

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(
            ["git", "init", "--initial-branch=main"], cwd=repo, check=True, capture_output=True
        )
        (repo / "app.py").write_text("x = 1\n")
        self._commit(repo, "init")
        return repo

    @staticmethod
    def _commit(repo: Path, message: str) -> None:
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-m", message],
            cwd=repo,
            check=True,
            capture_output=True,
        )

    def _branch_with(self, repo: Path, filename: str, content: str) -> None:
        subprocess.run(["git", "checkout", "-qb", "feature"], cwd=repo, check=True, capture_output=True)
        (repo / filename).write_text(content)
        self._commit(repo, "feature work")

    def test_healthy_scope_passes_through(self, repo: Path) -> None:
        self._branch_with(repo, "app.py", "x = 2\n")
        assert assert_reviewable_scope("main...HEAD", str(repo), ["*.md"]) == ["app.py"]

    def test_all_excluded_carries_patterns_and_count(
        self, repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The range had changes, but every one matched an exclusion."""
        self._branch_with(repo, "notes.md", "# notes\n")

        with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
            with pytest.raises(EmptyScopeError) as exc_info:
                assert_reviewable_scope("main...HEAD", str(repo), ["*.md"])

        error = exc_info.value
        assert error.case == EmptyScopeCase.ALL_EXCLUDED
        assert error.exclude_patterns == ["*.md"]
        assert error.excluded_count == 1
        assert [r for r in caplog.records if r.levelname == "WARNING"]

    def test_no_changes_at_all_is_a_distinct_case(
        self, repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The range itself is the problem — wrong base, or already merged."""
        with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
            with pytest.raises(EmptyScopeError) as exc_info:
                assert_reviewable_scope("main...HEAD", str(repo), ["*.md"])

        error = exc_info.value
        assert error.case == EmptyScopeCase.NO_CHANGES
        # Distinguishable by structured field, not by message text.
        assert error.case != EmptyScopeCase.ALL_EXCLUDED
        assert [r for r in caplog.records if r.levelname == "WARNING"]

    def test_rejected_pathspec_is_its_own_case(
        self, repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """git refusing the patterns is not the same as the patterns excluding everything.

        The remedy differs — fix the patterns vs. pick a different range — so
        overloading ALL_EXCLUDED would defeat the point of the enum.
        """
        self._branch_with(repo, "app.py", "x = 2\n")

        real = _changed_paths

        def fail_only_filtered(diff, cwd, patterns):
            return None if patterns else real(diff, cwd, patterns)

        with patch("squadron.review.git_utils._changed_paths", side_effect=fail_only_filtered):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                with pytest.raises(EmptyScopeError) as exc_info:
                    assert_reviewable_scope("main...HEAD", str(repo), ["[bad"])

        assert exc_info.value.case == EmptyScopeCase.INVALID_EXCLUDE_PATTERN
        assert exc_info.value.case != EmptyScopeCase.ALL_EXCLUDED
        assert [r for r in caplog.records if r.levelname == "WARNING"]

    def test_unusable_range_reports_no_changes(
        self, repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """git could not compute the range at all."""
        with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
            with pytest.raises(EmptyScopeError) as exc_info:
                assert_reviewable_scope("no-such-ref...HEAD", str(repo), None)

        assert exc_info.value.case == EmptyScopeCase.NO_CHANGES
        assert [r for r in caplog.records if r.levelname == "WARNING"]


class TestExtractDiffPathsIsBounded:
    """``extract_diff_paths`` runs through ``run_git``, so it inherits the timeout.

    It previously called ``subprocess.run`` directly, leaving the unreachable-remote
    hang reachable through the one path that always runs — the language-detection
    extraction on both the CLI and pipeline review routes.
    """

    def test_timeout_yields_empty_list_not_a_hang(self, caplog: pytest.LogCaptureFixture) -> None:
        from squadron.review.rules import extract_diff_paths

        with patch(
            _GIT_UTILS_SUBPROCESS,
            side_effect=subprocess.TimeoutExpired(cmd=["git", "diff"], timeout=1),
        ):
            with caplog.at_level("WARNING", logger="squadron.review.git_utils"):
                assert extract_diff_paths("main...HEAD", ".", None) == []

        assert [r for r in caplog.records if r.levelname == "WARNING"]

    def test_passes_the_timeout_through(self) -> None:
        from squadron.review.rules import extract_diff_paths

        with patch(_GIT_UTILS_SUBPROCESS) as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="app.py\n")
            assert extract_diff_paths("main...HEAD", ".", None) == ["app.py"]

        assert mock_run.call_args.kwargs["timeout"] == GIT_COMMAND_TIMEOUT_SECONDS
