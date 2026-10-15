"""Tests for the ``sq stats reviews`` report core (slice 175 D8)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.core.usage import CostBasis, TokenUsage
from squadron.stats.reviews_report import reviews_usage_report


def _artifact(directory: Path, name: str, **front: object) -> Path:
    lines = ["---", "docType: review", "verdict: PASS", "reviewType: slice"]
    lines += [f"{key}: {value}" for key, value in front.items()]
    path = directory / name
    path.write_text("\n".join([*lines, "---", "", "# Review body that must not be read", ""]))
    return path


@pytest.fixture
def reviews(tmp_path: Path) -> Path:
    directory = tmp_path / "reviews"
    directory.mkdir()
    _artifact(
        directory,
        "175-review.slice.usage.md",
        slice="usage-and-cost-tracking",
        aiModel="claude-opus",
        promptTokens=500,
        cachedTokens=300,
        cacheWriteTokens=100,
        completionTokens=20,
        turns=3,
        costUsd=0.41,
        costBasis="provider",
        dateCreated=20261014,
    )
    _artifact(directory, "175-review.tasks.usage.md", slice="usage-and-cost-tracking", runId="run-abc")
    _artifact(directory, "174-review.slice.other.md", slice="other", promptTokens=7, completionTokens=1)
    (directory / "175-broken.md").write_text("no frontmatter here\n")
    return directory


def test_rows_exclusions_and_skips(reviews: Path, caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="squadron.stats.reviews_report"):
        report = reviews_usage_report(reviews, None)

    assert [row.path.name for row in report.rows] == [
        "174-review.slice.other.md",
        "175-review.slice.usage.md",
    ]
    assert report.excluded_run_ids == ["run-abc"]
    assert report.skipped == 1
    assert any("175-broken.md" in r.getMessage() for r in caplog.records)
    assert report.totals.usage == TokenUsage(prompt=507, cached=300, cache_write=100, completion=21)
    assert (report.totals.cost_usd, report.totals.priced) == (0.41, 1)


def test_slice_filter_matches_index_and_name(reviews: Path) -> None:
    by_index = reviews_usage_report(reviews, "175")
    by_name = reviews_usage_report(reviews, "usage-and-cost-tracking")

    for report in (by_index, by_name):
        assert [row.path.name for row in report.rows] == ["175-review.slice.usage.md"]
        assert report.excluded_run_ids == ["run-abc"]
    row = by_index.rows[0]
    assert (row.model, row.verdict, row.date) == ("claude-opus", "PASS", "20261014")
    assert row.record.cost_basis is CostBasis.PROVIDER


def test_malformed_fields_become_none_and_row_is_kept(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _artifact(tmp_path, "1-review.md", promptTokens='"abc"', costBasis="guess", completionTokens=4)

    with caplog.at_level(logging.WARNING, logger="squadron.stats.reviews_report"):
        report = reviews_usage_report(tmp_path, None)

    record = report.rows[0].record
    assert record.usage.prompt is None and record.cost_basis is None
    assert report.totals.usage.prompt is None
    messages = [r.getMessage() for r in caplog.records]
    assert any("1-review.md" in m and "promptTokens" in m for m in messages)
    assert any("costBasis" in m for m in messages)


def test_requested_model_maps_to_alias_only_when_known(tmp_path: Path) -> None:
    _artifact(tmp_path, "1-review.md", requestedModel="opus")
    _artifact(tmp_path, "2-review.md", requestedModel="claude-opus-4-1-20250805")

    with patch("squadron.stats.reviews_report.get_all_aliases", return_value={"opus": {}}):
        report = reviews_usage_report(tmp_path, None)

    assert [row.record.alias for row in report.rows] == ["opus", None]


def test_missing_directory_is_flagged_not_raised(tmp_path: Path) -> None:
    report = reviews_usage_report(tmp_path / "absent", None)

    assert report.missing_dir and report.rows == []


def test_reads_frontmatter_only(reviews: Path) -> None:
    with patch.object(Path, "read_text", autospec=True, side_effect=Path.read_text) as read_text:
        reviews_usage_report(reviews, None)

    # One read per artifact, each through read_frontmatter: no second body read. Reads
    # outside the directory (the alias tables) are not artifact reads.
    artifact_reads = [c for c in read_text.call_args_list if c.args[0].parent == reviews]
    assert len(artifact_reads) == len(list(reviews.glob("*.md")))
