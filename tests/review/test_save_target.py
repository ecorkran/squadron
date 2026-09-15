"""The four questions each save target answers (slice 383, D1).

Separate assertions per implementation rather than one combined test: these
three targets exist precisely because they answer the same questions
differently, and a table-driven test would obscure which one regressed.

The stems here duplicate the literals pinned in
``test_persistence_migration.py``. That is deliberate — those pin what the
*pre-migration code* produced, these pin what the *new implementations*
produce, and the migration's whole claim is that the two agree. Deriving one
from the other would make them agree by construction and prove nothing.
"""

from __future__ import annotations

from unittest.mock import patch

from squadron.review.persistence import SaveTargetProtocol, SliceInfo
from squadron.review.save_target import ArchTarget, SaveTarget, SliceTarget, StepTarget

_SHA = "0f1e2d3c4b5a69788796a5b4c3d2e1f00f1e2d3c"


def _slice_info() -> SliceInfo:
    return SliceInfo(
        index=146,
        name="review-and-checkpoint-actions",
        slice_name="review-and-checkpoint-actions",
        design_file="project-documents/user/slices/146-slice.md",
        task_files=["146-tasks.review-and-checkpoint-actions.md"],
        arch_file="project-documents/user/architecture/140-arch.md",
        project="squadron",
    )


class TestSliceTarget:
    def test_stem_reproduces_todays_slice_naming(self) -> None:
        target = SliceTarget(_slice_info())

        assert target.filename_stem("code") == "146-review.code.review-and-checkpoint-actions"

    def test_frontmatter_carries_the_slice_name(self) -> None:
        assert SliceTarget(_slice_info()).frontmatter_fields() == {
            "slice": "review-and-checkpoint-actions"
        }

    def test_source_document_is_the_design_file(self) -> None:
        assert (
            SliceTarget(_slice_info()).source_document() == "project-documents/user/slices/146-slice.md"
        )

    def test_source_document_is_none_when_the_slice_has_no_design_file(self) -> None:
        """A slice with no design file names no source document rather than "" ."""
        info = _slice_info()
        info["design_file"] = None

        assert SliceTarget(info).source_document() is None

    def test_wrapped_record_stays_reachable(self) -> None:
        """``SliceInfo`` keeps its other consumers; the target wraps, never replaces."""
        info = _slice_info()

        assert SliceTarget(info).slice_info is info

    def test_reviewed_sha_comes_from_git(self) -> None:
        with patch("squadron.review.save_target.resolve_reviewed_sha", return_value=_SHA) as m:
            assert SliceTarget(_slice_info(), cwd="/repo").reviewed_sha() == _SHA
        m.assert_called_once_with("/repo")


class TestArchTarget:
    _ARCH = "project-documents/user/architecture/380-arch.pull-request-workflow.md"

    def test_stem_reproduces_todays_arch_naming(self) -> None:
        target = ArchTarget(380, self._ARCH)

        assert target.filename_stem("arch") == "380-review.arch.pull-request-workflow"

    def test_name_falls_back_to_the_whole_stem_without_a_dotted_segment(self) -> None:
        """``_arch_slice_info`` split on the first dot and kept the remainder.

        ``Path.stem`` has already removed ``.md``, so ``380-arch.md`` arrives
        here as ``380-arch`` — no dot left, and the whole stem is the name. The
        numeric prefix survives into ``slice:`` for such a document; faithful to
        the pre-migration fabrication, which did exactly this.
        """
        target = ArchTarget(380, "project-documents/user/architecture/380-arch.md")

        assert target.arch_name == "380-arch"

    def test_frontmatter_carries_the_arch_name_as_slice(self) -> None:
        """Faithful to the pre-migration fabrication, not to what is true.

        An arch review is not about a slice, but the fabricated ``SliceInfo``
        put the document name in ``slice:`` and byte-identity requires
        reproducing that. ``targetKind`` is what eventually makes the
        distinction readable (D4, Task 8).
        """
        assert ArchTarget(380, self._ARCH).frontmatter_fields() == {"slice": "pull-request-workflow"}

    def test_source_document_is_the_arch_file(self) -> None:
        assert ArchTarget(380, self._ARCH).source_document() == self._ARCH

    def test_reviewed_sha_comes_from_git(self) -> None:
        with patch("squadron.review.save_target.resolve_reviewed_sha", return_value=_SHA) as m:
            assert ArchTarget(380, self._ARCH, cwd="/repo").reviewed_sha() == _SHA
        m.assert_called_once_with("/repo")


class TestStepTarget:
    def test_stem_reproduces_todays_step_keyed_naming(self) -> None:
        target = StepTarget("review-code", 3)

        assert target.filename_stem("code") == "3-review.code.review-code"

    def test_frontmatter_carries_the_unknown_fallback(self) -> None:
        """The step path rendered with no ``SliceInfo``, so ``slice`` read ``unknown``."""
        assert StepTarget("review-code", 3).frontmatter_fields() == {"slice": "unknown"}

    def test_names_no_source_document(self) -> None:
        """The step path passes its input explicitly; the target claims none."""
        assert StepTarget("review-code", 3).source_document() is None

    def test_reviewed_sha_comes_from_git(self) -> None:
        with patch("squadron.review.save_target.resolve_reviewed_sha", return_value=_SHA) as m:
            assert StepTarget("review-code", 3, cwd="/repo").reviewed_sha() == _SHA
        m.assert_called_once_with("/repo")


class TestProtocolConformance:
    """Structural conformance, so a drifting implementation fails here first."""

    def test_every_implementation_satisfies_the_protocol(self) -> None:
        targets: list[SaveTarget] = [
            SliceTarget(_slice_info()),
            ArchTarget(380, "project-documents/user/architecture/380-arch.x.md"),
            StepTarget("review-code", 3),
        ]

        for target in targets:
            assert isinstance(target, SaveTarget)

    def test_every_implementation_satisfies_the_persistence_side_protocol(self) -> None:
        """The protocol is declared twice; this is what keeps the copies honest.

        ``persistence.py`` cannot import ``save_target`` — that module already
        imports ``SliceInfo`` and ``resolve_reviewed_sha`` from it, so the type
        import would close a cycle. It therefore declares its own structural
        copy. Duplication is only safe while both copies describe the same
        shape, so a method added to one and not the other fails here rather
        than surfacing as an unexplained type error at a call site.
        """
        targets: list[SaveTargetProtocol] = [
            SliceTarget(_slice_info()),
            ArchTarget(380, "project-documents/user/architecture/380-arch.x.md"),
            StepTarget("review-code", 3),
        ]

        for target in targets:
            assert isinstance(target, SaveTargetProtocol)

    def test_the_two_declarations_name_the_same_methods(self) -> None:
        """Shape equality, not just per-implementation conformance.

        ``isinstance`` against a runtime-checkable Protocol only checks method
        *presence* on the instance, so both assertions above would still pass
        if one declaration grew a method no implementation has yet. Comparing
        the declared members catches that.
        """
        declared = {name for name in SaveTarget.__protocol_attrs__}
        persistence_side = {name for name in SaveTargetProtocol.__protocol_attrs__}

        assert declared == persistence_side

    def test_the_protocol_does_not_ask_for_a_reviews_directory(self) -> None:
        """D1's deliberate omission, pinned.

        The directory depends on the invocation rather than the target, so it
        stays a ``save_review_result`` parameter. A fourth method here would
        make every implementation carry a value it cannot answer for.
        """
        assert not hasattr(SliceTarget(_slice_info()), "reviews_dir")
