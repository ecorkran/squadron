"""Tests for artifact-level derivation."""

from __future__ import annotations

import pytest

from squadron.metrology.levels import ArtifactLevel, derive_artifact_level


@pytest.mark.parametrize(
    ("review_type", "expected"),
    [
        ("judge.tasks-vs-slice", ArtifactLevel.TASKS_VS_SLICE),
        ("tasks", ArtifactLevel.TASKS_VS_SLICE),
        ("judge.slice-vs-arch", ArtifactLevel.SLICE_DESIGN_VS_ARCH),
        ("slice", ArtifactLevel.SLICE_DESIGN_VS_ARCH),
        ("arch", ArtifactLevel.ARCH_VS_CONCEPT),
    ],
)
def test_known_review_types_map_to_expected_level(review_type: str, expected: ArtifactLevel) -> None:
    assert derive_artifact_level(review_type) == expected


@pytest.mark.parametrize("review_type", ["", "unknown-type", "judge.code", "code"])
def test_unknown_or_empty_review_type_is_unclassified(review_type: str) -> None:
    assert derive_artifact_level(review_type) == ArtifactLevel.UNCLASSIFIED


def test_arch_vs_concept_has_no_template_but_vocabulary_is_complete() -> None:
    """arch-vs-concept has no judge template today, but the level exists so
    future arch-concept judging classifies correctly rather than landing in
    UNCLASSIFIED once such judging ships."""
    assert derive_artifact_level("arch") == ArtifactLevel.ARCH_VS_CONCEPT
