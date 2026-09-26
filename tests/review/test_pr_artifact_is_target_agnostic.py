"""Archiving, the run digest, and 917's integrity rendering on a PR artifact.

These paths operate on a ``ReviewResult`` and on filesystem paths, never on
slice identity — so 383's claim is that they need a *test*, not changes (D4).
A test that merely passed would not distinguish "target-agnostic" from "not
reached", so each case here drives the real function against a PR-shaped input
and asserts the outcome it produces for any other review.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from squadron.codehost.models import PullRequestRecord
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.persistence import (
    archive_existing_review,
    format_review_markdown,
    save_review_result,
)
from squadron.review.rules import RulesSource

_PR_HEAD = "1111111111111111111111111111111111111111"


def _record(number: int = 42) -> PullRequestRecord:
    return PullRequestRecord(
        host="github.com",
        owner="ecorkran",
        repository="squadron",
        number=number,
        base_ref="main",
        head_ref="feature",
        head_sha=_PR_HEAD,
        url=f"https://github.com/ecorkran/squadron/pull/{number}",
    )


def _pr_target(number: int = 42):
    # Imported here rather than at module scope: PrTarget lives in the CLI
    # layer by design (review/ must never import codehost), so a review-package
    # test reaches for it deliberately rather than by habit.
    from squadron.cli.commands.review_pr import PrTarget

    return PrTarget(_record(number), RulesSource.PROJECT, qualify=False)


def _result(verdict: Verdict = Verdict.CONCERNS) -> ReviewResult:
    return ReviewResult(
        verdict=verdict,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing error handling",
                description="No try/except around the write.",
                file_ref="src/foo.py:10",
                category="error-handling",
                location="src/foo.py:10",
            ),
        ],
        raw_output="## Summary\nCONCERNS\n",
        template_name="code",
        input_files={"input": "pr"},
        timestamp=datetime(2026, 4, 1, 12, 0, 0),
        model="claude-opus-4-5",
    )


class TestArchivingAPrArtifact:
    """The refuse-to-overwrite guard keys on paths, not on what was reviewed."""

    def test_a_prior_pr_review_is_archived_before_being_overwritten(self, tmp_path: Path) -> None:
        target = _pr_target()
        first = save_review_result(
            _result(Verdict.PASS),
            "code",
            reviews_dir=tmp_path,
            target=target,
            project_name="squadron",
            heading_label="PR #42",
        )
        original = first.read_bytes()

        second = save_review_result(
            _result(Verdict.FAIL),
            "code",
            reviews_dir=tmp_path,
            target=target,
            project_name="squadron",
            heading_label="PR #42",
        )

        assert second == first
        archived = tmp_path / "archive" / first.name
        assert archived.read_bytes() == original
        # The live slot holds the new run, not the archived one.
        assert first.read_bytes() != original

    def test_archive_guard_refuses_when_the_copy_cannot_be_made(self, tmp_path: Path) -> None:
        """A PR artifact gets the same refusal any other review would.

        ``archive/`` is occupied by a *file*, so the guard cannot create the
        directory it needs. It must report failure rather than proceeding —
        proceeding is what destroys the content the guard exists to protect.
        """
        artifact = tmp_path / "github.com-ecorkran-squadron-42-review.code.md"
        artifact.write_text("prior content")
        (tmp_path / "archive").write_text("not a directory")

        assert archive_existing_review(artifact) is False
        # Untouched: the caller aborts rather than overwriting.
        assert artifact.read_text() == "prior content"

    def test_archiving_is_a_noop_when_nothing_is_there(self, tmp_path: Path) -> None:
        absent = tmp_path / "github.com-ecorkran-squadron-42-review.code.md"

        assert archive_existing_review(absent) is True


class TestRunDigestOnAPrArtifact:
    """917's always-on record of what the parse saw, rendered for a PR review."""

    def test_the_digest_section_is_present_and_populated(self) -> None:
        rendered = format_review_markdown(
            _result(),
            "code",
            target=_pr_target(),
            project_name="squadron",
            heading_label="PR #42",
            reviewed_sha=_PR_HEAD,
        )

        assert "### Run Digest" in rendered
        assert f"- Response length: {len(_result().raw_output)} chars" in rendered
        assert "- Tool calls made: not offered" in rendered

    def test_a_degraded_pr_review_carries_its_raw_response(self) -> None:
        """The artifact is often the only surviving record of what the model said.

        A PR review that degrades must not read as a clean review finding
        nothing — the same claim 917 made for slice reviews, asserted here on
        the path that did not exist when it was made.
        """
        degraded = ReviewResult(
            verdict=Verdict.UNKNOWN,
            findings=[],
            raw_output="the model rambled without structure",
            template_name="code",
            input_files={"input": "pr"},
            timestamp=datetime(2026, 4, 1, 12, 0, 0),
            model="claude-opus-4-5",
        )

        rendered = format_review_markdown(
            degraded,
            "code",
            target=_pr_target(),
            project_name="squadron",
            heading_label="PR #42",
        )

        assert "## Findings Not Parsed" in rendered
        assert "No specific findings." not in rendered
        assert "the model rambled without structure" in rendered


class TestThePrArtifactIsWellFormed:
    """What a PR review's frontmatter actually says, end to end."""

    def test_frontmatter_names_the_pr_and_carries_no_slice_key(self, tmp_path: Path) -> None:
        path = save_review_result(
            _result(),
            "code",
            reviews_dir=tmp_path,
            target=_pr_target(),
            project_name="squadron",
            heading_label="PR #42",
        )
        text = path.read_text()

        assert "\nslice:" not in text
        assert "targetKind: pr" in text
        assert "rulesSource: project" in text
        assert "  number: 42" in text
        assert f"reviewedSha: {_PR_HEAD}" in text

    def test_the_heading_names_the_pr_rather_than_a_fabricated_slice(self, tmp_path: Path) -> None:
        """``slice 0`` would read as real. The provider-failure path already
        refused to emit it for a run with no slice; this is the same refusal on
        the success path."""
        path = save_review_result(
            _result(),
            "code",
            reviews_dir=tmp_path,
            target=_pr_target(),
            project_name="squadron",
            heading_label="PR #42",
        )

        assert "# Review: code — PR #42" in path.read_text()
        assert "slice 0" not in path.read_text()
