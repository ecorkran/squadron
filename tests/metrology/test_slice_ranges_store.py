"""Store methods for the ``slice_ranges`` record (slice 403, D1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.slice_range_models import SliceRanges
from squadron.metrology.store import MetrologyStore, slice_ranges_record_id
from tests.metrology.snapshot.builders import make_project_id
from tests.metrology.test_slice_range_models import make_landing


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "ranges-store")


def ranges_for(project_value: str, slices: dict[int, list[str]]) -> SliceRanges:
    """Ranges for a project; *slices* maps a slice to the after_shas of its landings."""
    project = make_project_id(project_value)
    return SliceRanges(
        record_id=slice_ranges_record_id(project),
        project_id=project,
        slices={
            index: [make_landing(after_sha) for after_sha in after_shas]
            for index, after_shas in slices.items()
        },
    )


PROJECT = "github.com/manta/example-repo"


def test_id_is_stable_per_project_and_differs_across_projects() -> None:
    project = make_project_id(PROJECT)

    assert slice_ranges_record_id(project) == slice_ranges_record_id(make_project_id(PROJECT))
    assert slice_ranges_record_id(project) != slice_ranges_record_id(
        make_project_id("github.com/manta/other")
    )
    assert slice_ranges_record_id(project).startswith("sliceranges-")


def test_write_then_get_round_trips(store: MetrologyStore) -> None:
    ranges = ranges_for(PROJECT, {403: ["a" * 40], 940: ["1" * 40, "2" * 40]})

    record_id = store.write_slice_ranges(ranges)

    assert record_id == ranges.record_id
    assert store.get_slice_ranges(make_project_id(PROJECT)) == ranges


def test_second_write_replaces_the_first(store: MetrologyStore) -> None:
    store.write_slice_ranges(ranges_for(PROJECT, {403: ["a" * 40]}))
    second = ranges_for(PROJECT, {403: ["a" * 40], 404: ["b" * 40]})

    store.write_slice_ranges(second)

    assert store.get_slice_ranges(make_project_id(PROJECT)) == second
    assert len(list(store.store_dir.glob("*.json"))) == 1


def test_missing_record_is_none(store: MetrologyStore) -> None:
    assert store.get_slice_ranges(make_project_id(PROJECT)) is None


def test_another_projects_record_is_not_returned(store: MetrologyStore) -> None:
    store.write_slice_ranges(ranges_for("github.com/manta/other", {403: ["a" * 40]}))

    assert store.get_slice_ranges(make_project_id(PROJECT)) is None


def test_corrupt_record_raises_naming_the_path(store: MetrologyStore) -> None:
    ranges = ranges_for(PROJECT, {403: ["a" * 40]})
    store.write_slice_ranges(ranges)
    path = store.record_location(ranges.record_id)
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(MetrologyStoreError, match=path.name):
        store.get_slice_ranges(make_project_id(PROJECT))


def test_mismatched_record_id_is_rejected(store: MetrologyStore) -> None:
    ranges = ranges_for(PROJECT, {403: ["a" * 40]}).model_copy(update={"record_id": "wrong"})

    with pytest.raises(MetrologyStoreError, match="does not match"):
        store.write_slice_ranges(ranges)
