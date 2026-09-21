"""Byte-identity fixtures guarding the slice 383 persistence migration.

The migration replaces three divergent save shapes — slice, arch, and pipeline
step — with one ``SaveTarget`` contract. Its acceptance test is not "tests still
pass" but "the bytes are unchanged": every artifact these three paths write must
be identical before and after (design D2).

Two fixture sets, kept side by side on purpose:

- ``fixtures/383-premigration-*.md`` were captured at commit 1e6548b8, against
  unmodified persistence code, *before* Task 3 touched ``persistence.py``. A
  fixture captured afterwards would prove nothing.
- ``fixtures/383-postkeys-*.md`` are the same three artifacts after Task 8
  added ``targetKind`` and ``rulesSource``. That was the one sanctioned
  regeneration, and ``TestTheTwoNewKeysAreTheOnlyChange`` asserts the
  difference between the sets is exactly those two keys — a third difference
  would be drift arriving inside a regeneration everyone had already agreed to
  accept.

**These tests drive the targets, not a raw ``SliceInfo``.** Until Task 8 they
passed a bare ``SliceInfo`` (or ``None``) and rendered through
``format_review_markdown``'s fallback branch — the path the production save no
longer takes. They passed after the migration, and after the two keys were
added, because they were never exercising ``frontmatter_fields()`` at all. The
hole was invisible precisely because a green byte-identity check is what the
migration wanted to see. Any future assertion here must construct a target.

``reviewed_sha`` is pinned rather than resolved. The live save resolves it from
git, which would invalidate a byte-identity fixture on every commit; what these
pin is the rendered output *given* a sha.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict
from squadron.review.persistence import SliceInfo, format_review_markdown
from squadron.review.rules import RulesSource
from squadron.review.save_target import ArchTarget, SliceTarget, StepTarget

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
            target=SliceTarget(_slice_info(), rules_source=RulesSource.PROJECT),
            project_name="squadron",
            heading_label="slice 146",
            reviewed_sha=_PINNED_SHA,
        )

        fixture = _FIXTURES / "383-postkeys-slice.md"
        assert rendered == fixture.read_text()

    def test_arch_path(self) -> None:
        """The arch review's source document is its input file, not a design file."""
        arch_info = _arch_slice_info()
        rendered = format_review_markdown(
            _migration_result(),
            "arch",
            target=ArchTarget(
                arch_info["index"],
                arch_info["arch_file"],
                rules_source=RulesSource.PROJECT,
            ),
            project_name="squadron",
            heading_label="slice 380",
            reviewed_sha=_PINNED_SHA,
        )

        fixture = _FIXTURES / "383-postkeys-arch.md"
        assert rendered == fixture.read_text()

    def test_step_path(self) -> None:
        """The step path's target supplies the ``unknown`` fallbacks explicitly."""
        rendered = format_review_markdown(
            _migration_result(),
            "code",
            target=StepTarget("review-step", 0, rules_source=RulesSource.PROJECT),
            project_name="unknown",
            heading_label="slice 0",
            source_document="project-documents/user/slices/383-slice.md",
            reviewed_sha=_PINNED_SHA,
        )

        fixture = _FIXTURES / "383-postkeys-step.md"
        assert rendered == fixture.read_text()


class TestTheTwoNewKeysAreTheOnlyChange:
    """Task 8.2's actual requirement, and the reason the fixtures were captured.

    The pre-migration fixtures are kept alongside the regenerated ones so the
    diff can be asserted rather than eyeballed. A third difference is drift the
    migration check would otherwise have hidden — it would arrive inside a
    regeneration everyone had already agreed to accept.
    """

    @pytest.mark.parametrize("path_name", ["slice", "arch", "step"])
    def test_diff_against_premigration_is_exactly_two_keys(self, path_name: str) -> None:
        before = (_FIXTURES / f"383-premigration-{path_name}.md").read_text().splitlines()
        after = (_FIXTURES / f"383-postkeys-{path_name}.md").read_text().splitlines()

        added = [line for line in after if line not in before]
        removed = [line for line in before if line not in after]

        assert removed == [], f"the two keys are additive; nothing should disappear: {removed}"
        assert sorted(added) == ["rulesSource: project", "targetKind: " + path_name], (
            f"expected exactly targetKind and rulesSource to appear, got: {added}"
        )


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


class TestHeadingComesFromTheTarget:
    """The production call shape: a target, and no ``heading_label``.

    The byte-identity tests above pass ``heading_label`` by hand, which no CLI
    save path does — so they stayed green while every targeted save rendered
    ``slice 0``.
    """

    def _heading(self, rendered: str) -> str:
        return next(line for line in rendered.splitlines() if line.startswith("# Review:"))

    def test_slice_target_names_its_slice(self) -> None:
        rendered = format_review_markdown(
            _migration_result(), "code", target=SliceTarget(_slice_info())
        )
        assert self._heading(rendered) == "# Review: code — slice 146"

    def test_arch_target_is_not_a_slice(self) -> None:
        arch_info = _arch_slice_info()
        rendered = format_review_markdown(
            _migration_result(),
            "arch",
            target=ArchTarget(arch_info["index"], arch_info["arch_file"]),
        )
        assert self._heading(rendered) == "# Review: arch — initiative 380"

    def test_step_target_prints_no_fabricated_index(self) -> None:
        rendered = format_review_markdown(
            _migration_result(), "code", target=StepTarget("review-step", 0)
        )
        assert self._heading(rendered) == "# Review: code"
