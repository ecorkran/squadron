"""Tests for ``sq review resolve``'s review location and loading."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from squadron.review.addressed.models import FindingStatus, SettlingScreen
from squadron.review.models import ReviewResult, Verdict
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.resolution import (
    DiffBaseSource,
    Resolution,
    ResolutionError,
    load_review,
    locate_review,
    resolve_review_diff_base,
    review_type_of,
    settle_findings,
)

_JUDGE_TRANSPORT = "squadron.review.addressed.judge.run_review_with_profile"


def _judge_output(raw_output: str) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.UNKNOWN,
        findings=[],
        template_name="judge.findings-addressed",
        input_files={},
        raw_output=raw_output,
    )


_REVIEW_WITH_FINDINGS = """\
---
docType: review
reviewType: code
slice: findings-addressed
verdict: CONCERNS
reviewedSha: abc1234
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "Unhandled OSError on write"
    location: src/foo.py:10
  - id: F002
    severity: note
    category: naming
    summary: "Variable name unclear"
    location: src/bar.py:3
---

# Review: code — slice 305
"""


def _write_review(cwd: Path, filename: str, content: str = _REVIEW_WITH_FINDINGS) -> Path:
    reviews_dir = cwd / REVIEWS_DIR
    reviews_dir.mkdir(parents=True, exist_ok=True)
    path = reviews_dir / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestLocateReview:
    def test_single_review_resolves_without_a_type(self, tmp_path: Path) -> None:
        expected = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        assert locate_review(305, None, str(tmp_path)) == expected
        assert review_type_of(expected) == "code"

    def test_explicit_type_selects_among_several(self, tmp_path: Path) -> None:
        _write_review(tmp_path, "305-review.code.findings-addressed.md")
        expected = _write_review(tmp_path, "305-review.tasks.findings-addressed.md")
        assert locate_review(305, "tasks", str(tmp_path)) == expected

    def test_ambiguous_index_lists_every_match(self, tmp_path: Path) -> None:
        """305's real on-disk state: a code review and a tasks review."""
        _write_review(tmp_path, "305-review.code.findings-addressed.md")
        _write_review(tmp_path, "305-review.tasks.findings-addressed.md")

        with pytest.raises(ResolutionError) as excinfo:
            locate_review(305, None, str(tmp_path))

        message = str(excinfo.value)
        assert "305-review.code.findings-addressed.md" in message
        assert "305-review.tasks.findings-addressed.md" in message

    def test_missing_explicit_type_names_the_expected_path(self, tmp_path: Path) -> None:
        _write_review(tmp_path, "305-review.code.findings-addressed.md")

        with pytest.raises(ResolutionError) as excinfo:
            locate_review(305, "arch", str(tmp_path))

        message = str(excinfo.value)
        assert "305-review.arch.*.md" in message
        assert str(tmp_path / REVIEWS_DIR) in message

    def test_no_review_for_the_index(self, tmp_path: Path) -> None:
        _write_review(tmp_path, "305-review.code.findings-addressed.md")

        with pytest.raises(ResolutionError, match="306-review"):
            locate_review(306, None, str(tmp_path))


class TestLoadReview:
    def test_reads_verdict_sha_and_findings(self, tmp_path: Path) -> None:
        path = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        loaded = load_review(path)

        assert loaded.verdict == Verdict.CONCERNS
        assert loaded.frontmatter["reviewedSha"] == "abc1234"
        assert [record.finding_id for record in loaded.findings] == ["F001", "F002"]
        assert loaded.findings[0].severity == "FAIL"
        assert loaded.findings[0].location == "src/foo.py:10"

    def test_review_without_findings_block(self, tmp_path: Path) -> None:
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            "---\ndocType: review\nverdict: PASS\n---\n\n# Review\n",
        )
        loaded = load_review(path)

        assert loaded.verdict == Verdict.PASS
        assert loaded.findings == []

    def test_missing_verdict_warns_and_reads_unknown(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            "---\ndocType: review\n---\n\n# Review\n",
        )
        with caplog.at_level(logging.WARNING):
            loaded = load_review(path)

        assert loaded.verdict == Verdict.UNKNOWN
        assert "verdict" in caplog.text

    def test_no_frontmatter_is_an_error_not_an_empty_result(self, tmp_path: Path) -> None:
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            "# Review with no frontmatter at all\n",
        )
        with pytest.raises(ResolutionError, match="frontmatter"):
            load_review(path)


@pytest.fixture
def committed_review(git_repo: Path) -> Iterator[tuple[Path, Path, str]]:
    """A review file committed to a real repo: ``(repo, review path, SHA)``."""
    path = _write_review(git_repo, "305-review.code.findings-addressed.md")
    subprocess.run(["git", "add", "-A"], cwd=git_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "add review"], cwd=git_repo, capture_output=True, check=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=git_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    yield git_repo, path, sha


class TestResolveReviewDiffBase:
    def test_since_overrides_a_present_stamp(self, tmp_path: Path) -> None:
        path = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        base, source = resolve_review_diff_base(
            {"reviewedSha": "abc1234"}, path, since="v1.2.0", cwd=str(tmp_path)
        )
        assert (base, source) == ("v1.2.0", DiffBaseSource.SINCE)

    def test_stamp_is_used_when_present(self, tmp_path: Path) -> None:
        path = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        base, source = resolve_review_diff_base(
            {"reviewedSha": "abc1234"}, path, since=None, cwd=str(tmp_path)
        )
        assert (base, source) == ("abc1234", DiffBaseSource.FRONTMATTER)

    def test_falls_back_to_file_history_and_warns(
        self, committed_review: tuple[Path, Path, str], caplog: pytest.LogCaptureFixture
    ) -> None:
        repo, path, sha = committed_review
        with caplog.at_level(logging.WARNING):
            base, source = resolve_review_diff_base({}, path, since=None, cwd=str(repo))

        assert (base, source) == (sha, DiffBaseSource.FILE_HISTORY)
        assert "reviewedSha" in caplog.text

    def test_since_wins_with_nothing_to_fall_back_to(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``--since`` short-circuits before the fallback, not merely over it.

        Distinct from the first case, where a stamp existed to override: here
        there is none, so a precedence bug would show up as a file-history
        WARNING rather than as a wrong return value.
        """
        path = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        with (
            caplog.at_level(logging.WARNING),
            patch("squadron.review.resolution.run_git") as mock_run_git,
        ):
            base, source = resolve_review_diff_base({}, path, since="HEAD~3", cwd=str(tmp_path))

        assert (base, source) == ("HEAD~3", DiffBaseSource.SINCE)
        mock_run_git.assert_not_called()
        assert "reviewedSha" not in caplog.text

    def test_file_history_failure_returns_no_base(self, tmp_path: Path) -> None:
        """An unmanaged path leaves the base unresolved for the caller to classify."""
        path = _write_review(tmp_path, "305-review.code.findings-addressed.md")
        base, source = resolve_review_diff_base({}, path, since=None, cwd=str(tmp_path))
        assert base is None
        assert source == DiffBaseSource.FILE_HISTORY


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


def _commit_work(repo: Path, body: str = "def save(): ...\n") -> str:
    """Commit a source file, so there is something for the review to be about."""
    source = repo / "src" / "foo.py"
    source.parent.mkdir(exist_ok=True)
    source.write_text(body)
    return _commit(repo, "work under review")


def _stamped_review(repo: Path, sha: str) -> Path:
    """Write a review stamped with *sha*, then commit it."""
    path = _write_review(
        repo,
        "305-review.code.findings-addressed.md",
        _REVIEW_WITH_FINDINGS.replace("reviewedSha: abc1234", f"reviewedSha: {sha}"),
    )
    _commit(repo, "add review")
    return path


class TestScreensNeverReachTheJudge:
    @pytest.mark.asyncio
    async def test_nothing_changed_since_the_review_is_unaddressed(
        self, git_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The review file is committed after its own base — and must not count."""
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)

        transport = AsyncMock()
        with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.WARNING):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(git_repo)
            )

        assert settled.resolution == Resolution.UNADDRESSED
        assert settled.base == base_sha
        assert settled.base_source == DiffBaseSource.FRONTMATTER
        assert [outcome.finding_id for outcome in settled.outcomes] == ["F001"]
        assert settled.outcomes[0].status == FindingStatus.UNADDRESSED
        assert settled.outcomes[0].screen == SettlingScreen.BYTE_IDENTICAL
        transport.assert_not_called()

    @pytest.mark.asyncio
    async def test_git_failure_is_unknown_and_names_the_command(
        self, git_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)

        transport = AsyncMock()
        with (
            patch("squadron.review.addressed.screens.run_git", return_value=None),
            patch(_JUDGE_TRANSPORT, transport),
            caplog.at_level(logging.WARNING),
        ):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(git_repo)
            )

        assert settled.resolution == Resolution.UNKNOWN
        assert settled.diff.failed_command == f"git diff {base_sha} --name-only"
        assert settled.diff.failed_command in caplog.text
        assert settled.outcomes == []
        transport.assert_not_called()

    @pytest.mark.asyncio
    async def test_unresolvable_base_is_a_named_git_failure(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """No stamp and no file history — reported as the command that failed."""
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            _REVIEW_WITH_FINDINGS.replace("reviewedSha: abc1234\n", ""),
        )

        transport = AsyncMock()
        with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.WARNING):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(tmp_path)
            )

        assert settled.resolution == Resolution.UNKNOWN
        assert settled.diff.failed_command is not None
        assert "git log -1" in settled.diff.failed_command
        transport.assert_not_called()

    @pytest.mark.asyncio
    async def test_real_work_since_the_review_reaches_the_judge(self, git_repo: Path) -> None:
        """The complement: a real change is not screened out before the judge."""
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)
        (git_repo / "src" / "foo.py").write_text("def save():\n    try:\n        ...\n")
        _commit(git_repo, "guard the write")

        transport = AsyncMock(return_value=_judge_output("F001: addressed — guarded"))
        with patch(_JUDGE_TRANSPORT, transport):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(git_repo)
            )

        transport.assert_called_once()
        assert settled.diff.changed_paths == frozenset({"src/foo.py"})
        assert settled.resolution == Resolution.ADDRESSED


_NO_FINDINGS_REVIEW = """\
---
docType: review
reviewType: code
slice: findings-addressed
verdict: {verdict}
reviewedSha: abc1234
---

# Review: code — slice 305
"""


class TestVerdictConsistencyScreen:
    """Design review F001 — empty findings mean different things per verdict."""

    @pytest.mark.asyncio
    async def test_passing_review_with_no_findings_is_addressed(self, tmp_path: Path) -> None:
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            _NO_FINDINGS_REVIEW.format(verdict="PASS"),
        )

        transport = AsyncMock()
        with (
            patch(_JUDGE_TRANSPORT, transport),
            patch("squadron.review.resolution.run_git") as resolution_git,
            patch("squadron.review.addressed.screens.run_git") as screens_git,
        ):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(tmp_path)
            )

        assert settled.resolution == Resolution.ADDRESSED
        assert settled.outcomes == []
        transport.assert_not_called()
        resolution_git.assert_not_called()
        screens_git.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verdict", ["FAIL", "CONCERNS"])
    async def test_failing_review_with_no_findings_is_inconsistent_evidence(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture, verdict: str
    ) -> None:
        """The exact shape a parser-drop bug like issue #28 produces."""
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            _NO_FINDINGS_REVIEW.format(verdict=verdict),
        )

        transport = AsyncMock()
        with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.WARNING):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(tmp_path)
            )

        assert settled.resolution == Resolution.UNKNOWN
        assert verdict in caplog.text
        assert "inconsistent evidence" in caplog.text
        transport.assert_not_called()

    @pytest.mark.asyncio
    async def test_note_only_findings_do_not_count_as_concern_plus(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A NOTE is not something the work is held accountable for."""
        path = _write_review(
            tmp_path,
            "305-review.code.findings-addressed.md",
            _REVIEW_WITH_FINDINGS.replace("severity: fail", "severity: note"),
        )

        with patch(_JUDGE_TRANSPORT, AsyncMock()), caplog.at_level(logging.WARNING):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(tmp_path)
            )

        assert settled.resolution == Resolution.UNKNOWN
        assert "CONCERNS" in caplog.text


class TestJudgeLeg:
    @pytest.mark.asyncio
    async def test_judge_claiming_addressed_over_a_touched_path_resolves_addressed(
        self, git_repo: Path
    ) -> None:
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)
        (git_repo / "src" / "foo.py").write_text("def save():\n    try:\n        ...\n")
        _commit(git_repo, "guard the write")

        transport = AsyncMock(return_value=_judge_output("F001: addressed"))
        with patch(_JUDGE_TRANSPORT, transport):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(git_repo)
            )

        assert settled.resolution == Resolution.ADDRESSED
        assert settled.outcomes[0].status == FindingStatus.ADDRESSED

    @pytest.mark.asyncio
    async def test_no_judge_leaves_findings_unsettled(
        self, git_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)
        (git_repo / "src" / "foo.py").write_text("def save():\n    try:\n        ...\n")
        _commit(git_repo, "guard the write")

        transport = AsyncMock()
        with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.WARNING):
            settled = await settle_findings(
                load_review(path),
                model_id=None,
                profile="sdk",
                cwd=str(git_repo),
                no_judge=True,
            )

        assert settled.resolution == Resolution.UNKNOWN
        assert "--no-judge" in caplog.text
        transport.assert_not_called()

    @pytest.mark.asyncio
    async def test_transport_failure_is_unknown_not_a_pass(
        self, git_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)
        (git_repo / "src" / "foo.py").write_text("def save():\n    try:\n        ...\n")
        _commit(git_repo, "guard the write")

        transport = AsyncMock(side_effect=RuntimeError("provider unreachable"))
        with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.ERROR):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(git_repo)
            )

        assert settled.resolution == Resolution.UNKNOWN
        assert "judge transport failed" in caplog.text

    @pytest.mark.asyncio
    async def test_change_set_over_the_injection_cap_never_reaches_the_judge(
        self, git_repo: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``--since`` can reach arbitrarily far back; the cap is what bounds it."""
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)
        for index in range(40):
            (git_repo / f"file-with-a-long-name-{index:04d}.py").write_text("x = 1\n")
        _commit(git_repo, "many files")

        transport = AsyncMock()
        with (
            patch(_JUDGE_TRANSPORT, transport),
            patch("squadron.review.resolution.get_config", return_value=100),
            caplog.at_level(logging.WARNING),
        ):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(git_repo)
            )

        assert settled.resolution == Resolution.UNKNOWN
        assert "review.max_total_injection_bytes" in caplog.text
        assert "100 bytes" in caplog.text
        assert base_sha in caplog.text
        transport.assert_not_called()

    @pytest.mark.asyncio
    async def test_a_non_int_cap_is_an_error_not_an_unbounded_prompt(self, git_repo: Path) -> None:
        base_sha = _commit_work(git_repo)
        path = _stamped_review(git_repo, base_sha)
        (git_repo / "src" / "foo.py").write_text("changed\n")
        _commit(git_repo, "change")

        with (
            patch(_JUDGE_TRANSPORT, AsyncMock()),
            patch("squadron.review.resolution.get_config", return_value="lots"),
            pytest.raises(TypeError, match="max_total_injection_bytes"),
        ):
            await settle_findings(load_review(path), model_id=None, profile="sdk", cwd=str(git_repo))


_TWO_CONCERNS_REVIEW = _REVIEW_WITH_FINDINGS.replace("severity: note", "severity: concern")


class TestClaimVerification:
    """The judge is consulted, not obeyed — on this path as on the gate's."""

    @pytest.fixture
    def repo_with_review(self, git_repo: Path) -> tuple[Path, Path]:
        """A repo whose review cites ``src/foo.py`` and ``src/bar.py``."""
        base_sha = _commit_work(git_repo)
        path = _write_review(
            git_repo,
            "305-review.code.findings-addressed.md",
            _TWO_CONCERNS_REVIEW.replace("reviewedSha: abc1234", f"reviewedSha: {base_sha}"),
        )
        _commit(git_repo, "add review")
        return git_repo, path

    @staticmethod
    def _change(repo: Path, name: str) -> None:
        (repo / "src" / name).write_text("changed\n")
        _commit(repo, f"touch {name}")

    @pytest.mark.asyncio
    async def test_addressed_over_an_untouched_path_is_downgraded(
        self, repo_with_review: tuple[Path, Path], caplog: pytest.LogCaptureFixture
    ) -> None:
        repo, path = repo_with_review
        self._change(repo, "bar.py")

        transport = AsyncMock(return_value=_judge_output("F001: addressed\nF002: addressed"))
        with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.WARNING):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(repo)
            )

        statuses = {outcome.finding_id: outcome.status for outcome in settled.outcomes}
        assert statuses["F001"] == FindingStatus.DISPUTED
        assert statuses["F002"] == FindingStatus.ADDRESSED
        assert settled.resolution == Resolution.UNKNOWN
        assert "src/foo.py:10" in caplog.text

    @pytest.mark.asyncio
    async def test_moved_is_always_downgraded_with_no_fresh_findings(
        self, repo_with_review: tuple[Path, Path], caplog: pytest.LogCaptureFixture
    ) -> None:
        """Decision 3's stated consequence, confirmed rather than assumed."""
        repo, path = repo_with_review
        self._change(repo, "foo.py")
        self._change(repo, "bar.py")

        transport = AsyncMock(return_value=_judge_output("F001: moved successor=F009\nF002: addressed"))
        with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.WARNING):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(repo)
            )

        statuses = {outcome.finding_id: outcome.status for outcome in settled.outcomes}
        assert statuses["F001"] == FindingStatus.DISPUTED
        assert settled.resolution == Resolution.UNKNOWN
        assert "F009" in caplog.text

    @pytest.mark.asyncio
    async def test_one_disputed_outranks_the_rest_being_addressed(
        self, repo_with_review: tuple[Path, Path]
    ) -> None:
        """UNKNOWN is evaluated before a would-be pass — 305's ordering, here."""
        repo, path = repo_with_review
        self._change(repo, "foo.py")
        self._change(repo, "bar.py")

        transport = AsyncMock(return_value=_judge_output("F001: disputed\nF002: addressed"))
        with patch(_JUDGE_TRANSPORT, transport):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(repo)
            )

        statuses = {outcome.finding_id: outcome.status for outcome in settled.outcomes}
        assert statuses == {
            "F001": FindingStatus.DISPUTED,
            "F002": FindingStatus.ADDRESSED,
        }
        assert settled.resolution == Resolution.UNKNOWN

    @pytest.mark.asyncio
    async def test_one_unaddressed_among_addressed_is_unaddressed(
        self, repo_with_review: tuple[Path, Path]
    ) -> None:
        repo, path = repo_with_review
        self._change(repo, "foo.py")
        self._change(repo, "bar.py")

        transport = AsyncMock(return_value=_judge_output("F001: unaddressed\nF002: addressed"))
        with patch(_JUDGE_TRANSPORT, transport):
            settled = await settle_findings(
                load_review(path), model_id=None, profile="sdk", cwd=str(repo)
            )

        assert settled.resolution == Resolution.UNADDRESSED
