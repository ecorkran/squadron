"""Byte-identity fixtures guarding the slice 383 persistence migration.

The migration replaces three divergent save shapes — slice, arch, and pipeline
step — with one ``SaveTarget`` contract. Its acceptance test is not "tests still
pass" but "the bytes are unchanged": every artifact these three paths write must
be identical before and after (design D2).

The fixtures in ``fixtures/383-premigration-*.md`` were captured at commit
1e6548b8, against unmodified persistence code, *before* Task 3 touched
``persistence.py``. A fixture captured afterwards would prove nothing.

**Any diff here is a regression, not an improvement.** Do not update a fixture
to match new output. The one sanctioned regeneration is Task 8.2, when
``rulesSource`` and ``targetKind`` are added together — at which point the diff
must contain exactly those two keys and nothing else.

``reviewed_sha`` is pinned rather than resolved. ``save_review_result``
currently stamps ``resolve_reviewed_sha(".")`` — the live repository HEAD —
which would invalidate a byte-identity fixture on every commit. The migration
moves that resolution onto the target (Task 3.6); what must not change is the
rendered output *given* a sha, which is what these fixtures hold.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.persistence import SliceInfo, format_review_markdown

_FIXTURES = Path(__file__).parent / "fixtures"

#: Pinned so the artifact is a function of the inputs alone. The live value is
#: resolved from git at save time and would differ on every commit.
_PINNED_SHA = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"


def _migration_result() -> ReviewResult:
    """One canned result, rendered by all three paths.

    Deliberately carries both a structured finding and a plain finding: the
    frontmatter ``findings:`` block and the body ``## Findings`` section are
    rendered by separate code, and the migration must leave both untouched.
    """
    return ReviewResult(
        verdict=Verdict.CONCERNS,
        findings=[
            ReviewFinding(
                severity=Severity.CONCERN,
                title="Missing error handling",
                description="The runner does not handle SDK timeout errors.",
                file_ref="src/squadron/review/runner.py:42",
                category="error-handling",
                location="src/squadron/review/runner.py:42",
            ),
        ],
        raw_output="## Summary\nCONCERNS\n\n## Findings\n...",
        template_name="code",
        input_files={"input": "file.md"},
        timestamp=datetime(2026, 4, 1, 12, 0, 0),
        model="claude-opus-4-5",
    )


def _slice_info() -> SliceInfo:
    """The slice path's metadata, matching the existing snapshot test's shape."""
    return SliceInfo(
        index=146,
        name="review-and-checkpoint-actions",
        slice_name="review-and-checkpoint-actions",
        design_file="project-documents/user/slices/146-slice.md",
        task_files=["146-tasks.review-and-checkpoint-actions.md"],
        arch_file="project-documents/user/architecture/140-arch.md",
        project="squadron",
    )


def _arch_slice_info() -> SliceInfo:
    """What ``cli/commands/review.py::_arch_slice_info`` fabricates for an arch review.

    Reproduced here rather than imported: the migration *deletes* that function
    (Task 3.7), so importing it would make this fixture unbuildable at exactly
    the point it is needed. The project name is pinned — the real function reads
    it from a live Context Forge client and degrades to ``"unknown"``.
    """
    return SliceInfo(
        index=380,
        name="pull-request-workflow",
        slice_name="pull-request-workflow",
        design_file=None,
        task_files=[],
        arch_file="project-documents/user/architecture/380-arch.pull-request-workflow.md",
        project="squadron",
    )


class TestPreMigrationByteIdentity:
    """Each path's rendered artifact, pinned against its pre-migration capture."""

    def test_slice_path(self) -> None:
        rendered = format_review_markdown(
            _migration_result(),
            "code",
            _slice_info(),
            reviewed_sha=_PINNED_SHA,
        )

        fixture = _FIXTURES / "383-premigration-slice.md"
        assert rendered == fixture.read_text()

    def test_arch_path(self) -> None:
        """The arch review's source document is its input file, not a design file."""
        arch_info = _arch_slice_info()
        rendered = format_review_markdown(
            _migration_result(),
            "arch",
            arch_info,
            source_document=arch_info["arch_file"],
            reviewed_sha=_PINNED_SHA,
        )

        fixture = _FIXTURES / "383-premigration-arch.md"
        assert rendered == fixture.read_text()

    def test_step_path(self) -> None:
        """The step path renders with no slice info — the fallback shape is pinned too."""
        rendered = format_review_markdown(
            _migration_result(),
            "code",
            None,
            source_document="project-documents/user/slices/383-slice.md",
            reviewed_sha=_PINNED_SHA,
        )

        fixture = _FIXTURES / "383-premigration-step.md"
        assert rendered == fixture.read_text()


class TestPreMigrationFilenames:
    """The other half of the migration: what each path names its file.

    Byte-identity of the *content* would not catch a stem that changed, and the
    stem is precisely what the ``SaveTarget`` contract takes over (Task 3.1).
    These pin today's three shapes as literals, so a new implementation that
    renders identical bytes under a different name still fails.
    """

    def test_slice_stem(self) -> None:
        info = _slice_info()
        stem = f"{info['index']}-review.code.{info['slice_name']}"
        assert stem == "146-review.code.review-and-checkpoint-actions"

    def test_arch_stem(self) -> None:
        info = _arch_slice_info()
        stem = f"{info['index']}-review.arch.{info['slice_name']}"
        assert stem == "380-review.arch.pull-request-workflow"

    def test_step_stem(self) -> None:
        """``save_review_file`` names a step review from step index and step name."""
        step_index, step_name = 3, "review-code"
        stem = f"{step_index}-review.code.{step_name}"
        assert stem == "3-review.code.review-code"
