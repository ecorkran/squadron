"""What persistence needs to know about the thing being reviewed.

Persistence was generic at the top — ``_resolve_save_outcome`` is already
parametrized over a target type — and hardwired to ``SliceInfo`` everywhere
beneath. The two callers that are not about a slice worked around that in
different ways: the arch review fabricated a ``SliceInfo`` from an initiative
index, and the pipeline action bypassed ``save_review_result`` entirely for a
lower-level call keyed by step name and index. Both are the same unmet need,
solved twice (design D1).

``SaveTarget`` is that need stated once: three questions persistence actually
asks of whatever is being reviewed.

The reviews *directory* is deliberately not a fourth question. It depends on
the invocation — ``--reviews-dir``, whether the repository has a
``project-documents/`` — rather than on the target, so it is resolved by the
caller and passed to ``save_review_result``, which already accepts it. Putting
it here would make every implementation carry a directory it does not choose
and cannot answer for.

A ``Protocol`` rather than a base class or a union: the implementations live in
three different packages, and a union would have to name ``PrTarget`` inside
``review/`` — the import the architecture forbids and
``tests/codehost/test_import_boundaries.py`` enforces. Structural typing lets
the CLI layer build a PR target this module never learns about.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Protocol, runtime_checkable

from squadron.review.persistence import SliceInfo, resolve_reviewed_sha
from squadron.review.rules import RulesSource


@runtime_checkable
class SaveTarget(Protocol):
    """The three target-specific questions a review artifact's shape depends on."""

    def filename_stem(self, review_type: str) -> str:
        """The artifact's name, without the ``.md``/``.json`` extension.

        A caller may append a further dotted segment (``save_review_result``'s
        ``name_suffix``, used when one slice produces several task reviews).
        That is the caller's concern, not the target's: the target answers what
        it is called, not which part of a split it happens to be.
        """
        ...

    def frontmatter_fields(self) -> dict[str, object]:
        """Keys this target contributes, beyond the ones every review carries.

        A slice contributes ``slice``; a PR contributes a nested ``pr`` mapping
        and no slice key. Rendering stays line-based in ``persistence.py`` —
        nested values render as indented lines the way ``criteria:`` already
        does (D2).
        """
        ...

    def source_document(self) -> str | None:
        """What was reviewed, for the ``sourceDocument`` key.

        ``None`` when the target cannot name one; the caller's explicit
        ``input_file`` takes precedence where it has one.
        """
        ...

    def reviewed_sha(self) -> str | None:
        """The commit the review describes.

        On the target rather than resolved inside ``save_review_result``,
        which stamps ``resolve_reviewed_sha(".")`` — the *operator's* HEAD.
        For a slice or arch review that is the right tree; for a PR review it
        is a different tree entirely, and the resulting sha is wrong in a way
        that still looks plausible (D3).
        """
        ...


class TargetKind(StrEnum):
    """What a review is *about*, written to frontmatter as ``targetKind`` (D4).

    Consumers that enumerate every review file classify by reading this, never
    by parsing the filename — the rule ``capture._read_review_type`` already
    follows, and the reason it is reliable where filename parsing is not.

    Absence means :attr:`SLICE`. Every artifact written before this key existed
    is a slice, arch, or step review, and the first two already carry a
    ``slice`` key; treating absence as anything else would strand them.
    """

    SLICE = "slice"
    ARCH = "arch"
    STEP = "step"
    PR = "pr"


class SliceTarget:
    """A review of a slice, named and keyed by its ``SliceInfo``.

    Wraps ``SliceInfo`` rather than replacing it: the type carries design, task,
    and arch file paths that template inputs and the resolve path read for
    reasons unrelated to saving. This slice is not a ``SliceInfo`` refactor.
    """

    def __init__(
        self,
        slice_info: SliceInfo,
        cwd: str = ".",
        rules_source: RulesSource = RulesSource.NONE,
    ) -> None:
        self._info = slice_info
        self._cwd = cwd
        self._rules_source = rules_source

    @property
    def slice_info(self) -> SliceInfo:
        """The wrapped record, for callers that still need its other fields."""
        return self._info

    def filename_stem(self, review_type: str) -> str:
        return f"{self._info['index']}-review.{review_type}.{self._info['slice_name']}"

    def frontmatter_fields(self) -> dict[str, object]:
        return {
            "slice": self._info["slice_name"],
            "targetKind": TargetKind.SLICE.value,
            "rulesSource": self._rules_source.value,
        }

    def source_document(self) -> str | None:
        return self._info.get("design_file")

    def reviewed_sha(self) -> str | None:
        return resolve_reviewed_sha(self._cwd)


class ArchTarget:
    """A review of an initiative's architecture document.

    Replaces ``_arch_slice_info``'s fabrication of a ``SliceInfo`` from an
    initiative index. The name derives from the document's own filename, as the
    fabrication did — an arch review has no slice name to borrow.
    """

    def __init__(
        self,
        index: int,
        arch_file: str,
        cwd: str = ".",
        rules_source: RulesSource = RulesSource.NONE,
    ) -> None:
        self._index = index
        self._arch_file = arch_file
        self._cwd = cwd
        self._rules_source = rules_source

    @property
    def arch_name(self) -> str:
        """The document stem past its numeric prefix, e.g. ``pull-request-workflow``."""
        stem = Path(self._arch_file).stem
        return stem.split(".", 1)[1] if "." in stem else stem

    def filename_stem(self, review_type: str) -> str:
        return f"{self._index}-review.{review_type}.{self.arch_name}"

    def frontmatter_fields(self) -> dict[str, object]:
        # The pre-migration arch path fabricated a SliceInfo whose slice_name
        # was the arch document's name, so `slice:` carried that value. Byte
        # identity required reproducing it, not correcting it. `targetKind` is
        # what finally says this is not a slice review, without moving the key
        # a reader may already depend on.
        return {
            "slice": self.arch_name,
            "targetKind": TargetKind.ARCH.value,
            "rulesSource": self._rules_source.value,
        }

    def source_document(self) -> str | None:
        return self._arch_file

    def reviewed_sha(self) -> str | None:
        return resolve_reviewed_sha(self._cwd)


class StepTarget:
    """A review produced by a pipeline step that resolved no slice.

    The step path named files from the step's name and index and rendered with
    no ``SliceInfo`` at all, which is why its artifacts carry ``slice: unknown``
    and ``project: unknown``. Reproduced rather than repaired: this is a
    migration, and changing those values would change bytes it must not (D2).
    """

    _UNKNOWN = "unknown"

    def __init__(
        self,
        step_name: str,
        step_index: int,
        cwd: str = ".",
        rules_source: RulesSource = RulesSource.NONE,
    ) -> None:
        self._step_name = step_name
        self._step_index = step_index
        self._cwd = cwd
        self._rules_source = rules_source

    def filename_stem(self, review_type: str) -> str:
        return f"{self._step_index}-review.{review_type}.{self._step_name}"

    def frontmatter_fields(self) -> dict[str, object]:
        # `slice: unknown` is the pre-migration fallback, reproduced rather
        # than repaired (D2). `targetKind` is what makes the distinction
        # readable: a step review is not a slice review whose name went
        # missing, which is the only thing `unknown` could previously convey.
        return {
            "slice": self._UNKNOWN,
            "targetKind": TargetKind.STEP.value,
            "rulesSource": self._rules_source.value,
        }

    def source_document(self) -> str | None:
        # The step path passes its input explicitly; the target names none.
        return None

    def reviewed_sha(self) -> str | None:
        return resolve_reviewed_sha(self._cwd)


__all__ = ["ArchTarget", "SaveTarget", "SliceTarget", "StepTarget"]
