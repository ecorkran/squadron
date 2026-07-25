"""Artifact-level vocabulary for metrology reporting.

320 left ``SampleVerdict.artifact_level`` a reserved, always-``None`` hook —
no enum or constant for the vocabulary exists anywhere. This module is the
single definition (CLAUDE.md: comparison values defined once); 321 derives
the level at report time from each sample's recorded review type.
"""

from __future__ import annotations

from enum import StrEnum


class ArtifactLevel(StrEnum):
    """The artifact grain reports group on.

    ``UNCLASSIFIED`` is an explicit bucket for a review type the vocabulary
    doesn't know — never a silent drop.
    """

    TASKS_VS_SLICE = "tasks_vs_slice"
    SLICE_DESIGN_VS_ARCH = "slice_design_vs_arch"
    ARCH_VS_CONCEPT = "arch_vs_concept"
    UNCLASSIFIED = "unclassified"


#: Maps a persisted review's recorded type (``reviewType`` frontmatter) to
#: its ``ArtifactLevel``. Centralized here so the vocabulary is defined once
#: and referenced everywhere, never scattered as conditionals.
_REVIEW_TYPE_TO_LEVEL: dict[str, ArtifactLevel] = {
    "judge.tasks-vs-slice": ArtifactLevel.TASKS_VS_SLICE,
    "tasks": ArtifactLevel.TASKS_VS_SLICE,
    "judge.slice-vs-arch": ArtifactLevel.SLICE_DESIGN_VS_ARCH,
    "slice": ArtifactLevel.SLICE_DESIGN_VS_ARCH,
    "arch": ArtifactLevel.ARCH_VS_CONCEPT,
}


def derive_artifact_level(review_type: str) -> ArtifactLevel:
    """Map a recorded review type to its ``ArtifactLevel``.

    An unknown or empty review type returns ``UNCLASSIFIED`` — reported with
    its n, never dropped.
    """
    return _REVIEW_TYPE_TO_LEVEL.get(review_type, ArtifactLevel.UNCLASSIFIED)
