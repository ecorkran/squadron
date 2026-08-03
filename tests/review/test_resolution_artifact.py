"""Tests for the resolution artifact's rendering and versioned writes."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest
import yaml

from squadron.metrology.capture import resolve_target
from squadron.metrology.discovery import discover_judge_results
from squadron.metrology.errors import MetrologyTargetError
from squadron.review.addressed.models import FindingOutcome, FindingStatus, SettlingScreen
from squadron.review.models import Verdict
from squadron.review.persistence import REVIEWS_DIR
from squadron.review.resolution import Resolution
from squadron.review.resolution_artifact import (
    RESOLUTION_DOC_TYPE,
    ResolutionRecord,
    render_resolution,
    save_resolution,
)

#: A note that would corrupt hand-rendered frontmatter three separate ways.
#: The same hostile fixture 305's F005 test used.
_HOSTILE_NOTE = '# leading hash: colon-space too\nand an embedded newline: "quoted"'


def _record(**overrides: object) -> ResolutionRecord:
    defaults: dict[str, object] = {
        "index": 305,
        "review_file": "305-review.code.findings-addressed.md",
        "review_type": "code",
        "slice_name": "findings-addressed",
        "project": "squadron",
        "review_verdict": Verdict.CONCERNS,
        "resolution": Resolution.ADDRESSED,
        "date_created": "20260803",
        "reviewed_sha": "abc1234",
        "resolved_sha": "abc1234",
        "sha_source": "frontmatter",
        "judge_model": "claude-opus-4-5",
        "outcomes": [
            FindingOutcome(
                finding_id="F001",
                status=FindingStatus.ADDRESSED,
                screen=SettlingScreen.JUDGE,
                note="guarded the write",
            ),
        ],
    }
    defaults.update(overrides)
    return ResolutionRecord(**defaults)  # pyright: ignore[reportArgumentType]


def _frontmatter(markdown: str) -> dict[str, object]:
    block = markdown.split("---", 2)[1]
    return cast("dict[str, object]", yaml.safe_load(block))


class TestRenderResolution:
    def test_hostile_note_round_trips_exactly(self) -> None:
        """Notes embed arbitrary model text — 305 F005 applies unchanged here."""
        record = _record(
            outcomes=[
                FindingOutcome(
                    finding_id="F001",
                    status=FindingStatus.DISPUTED,
                    screen=SettlingScreen.JUDGE,
                    note=_HOSTILE_NOTE,
                ),
            ]
        )
        parsed = _frontmatter(render_resolution(record))
        statuses = cast("list[dict[str, object]]", parsed["findingStatuses"])
        assert statuses[0]["note"] == _HOSTILE_NOTE

    def test_full_schema_is_present_with_correct_types(self) -> None:
        parsed = _frontmatter(render_resolution(_record()))

        assert parsed["docType"] == RESOLUTION_DOC_TYPE
        assert parsed["reviewFile"] == "305-review.code.findings-addressed.md"
        assert parsed["reviewType"] == "code"
        assert parsed["slice"] == "findings-addressed"
        assert parsed["project"] == "squadron"
        assert parsed["reviewVerdict"] == "CONCERNS"
        assert parsed["resolution"] in {r.value for r in Resolution}
        assert parsed["reviewedSha"] == "abc1234"
        assert parsed["resolvedSha"] == "abc1234"
        assert parsed["shaSource"] == "frontmatter"
        assert parsed["judgeModel"] == "claude-opus-4-5"
        assert parsed["dateCreated"] == "20260803"

        statuses = cast("list[dict[str, object]]", parsed["findingStatuses"])
        assert isinstance(statuses, list)
        assert statuses[0]["id"] == "F001"
        assert statuses[0]["status"] in {s.value for s in FindingStatus}
        assert statuses[0]["screen"] in {s.value for s in SettlingScreen}

    def test_enum_members_serialize_rather_than_raising(self) -> None:
        """``Resolution`` and ``Verdict`` are str subclasses SafeDumper rejects raw."""
        markdown = render_resolution(_record(resolution=Resolution.UNKNOWN))
        assert "resolution: UNKNOWN" in markdown

    def test_absent_values_are_null_not_invented(self) -> None:
        parsed = _frontmatter(
            render_resolution(_record(reviewed_sha=None, judge_model=None, sha_source=None))
        )
        assert parsed["reviewedSha"] is None
        assert parsed["judgeModel"] is None
        assert parsed["shaSource"] is None

    def test_no_findings_renders_a_body_saying_so(self) -> None:
        markdown = render_resolution(_record(outcomes=[]))
        assert "findingStatuses" not in _frontmatter(markdown)
        assert "No CONCERN+ findings" in markdown

    def test_body_disclaims_amending_the_review_verdict(self) -> None:
        assert "does not change the review's `verdict:`" in render_resolution(_record())

    def test_filename_never_carries_the_review_substring(self) -> None:
        """Metrology's globs key on ``-review.``; this name must not match."""
        from squadron.review.resolution_artifact import RESOLUTION_FILENAME_FORMAT

        name = RESOLUTION_FILENAME_FORMAT.format(
            index=305, review_type="code", slice_name="findings-addressed", revision=1
        )
        assert "-review." not in name


class TestSaveResolution:
    def test_revisions_increment_and_never_overwrite(self, tmp_path: Path) -> None:
        first = save_resolution(
            render_resolution(_record(resolution=Resolution.UNADDRESSED)),
            index=305,
            review_type="code",
            slice_name="findings-addressed",
            cwd=str(tmp_path),
        )
        first_content = first.read_text()

        second = save_resolution(
            render_resolution(_record(resolution=Resolution.ADDRESSED)),
            index=305,
            review_type="code",
            slice_name="findings-addressed",
            cwd=str(tmp_path),
        )

        assert first.name.endswith("-r1.md")
        assert second.name.endswith("-r2.md")
        assert first.read_text() == first_content
        assert "resolution: ADDRESSED" in second.read_text()

    def test_a_collision_raises_rather_than_destroying_a_record(self, tmp_path: Path) -> None:
        reviews_dir = tmp_path / REVIEWS_DIR
        reviews_dir.mkdir(parents=True)
        # A file whose revision segment does not parse: it must not be counted,
        # and the -r1 it would otherwise mask must still be protected.
        (reviews_dir / "305-resolution.code.findings-addressed-rX.md").write_text("hand-made\n")
        colliding = reviews_dir / "305-resolution.code.findings-addressed-r1.md"
        colliding.write_text("existing record\n")

        with (
            patch("squadron.review.resolution_artifact.next_revision", return_value=1),
            pytest.raises(FileExistsError, match="append-only"),
        ):
            save_resolution(
                render_resolution(_record()),
                index=305,
                review_type="code",
                slice_name="findings-addressed",
                cwd=str(tmp_path),
            )

        assert colliding.read_text() == "existing record\n"


class TestMetrologyNeverSeesResolutions:
    """SC11 — both review-discovery globs must exclude resolution artifacts."""

    def _saved(self, tmp_path: Path) -> Path:
        return save_resolution(
            render_resolution(_record()),
            index=305,
            review_type="code",
            slice_name="findings-addressed",
            cwd=str(tmp_path),
        )

    def test_discover_judge_results_ignores_them(self, tmp_path: Path) -> None:
        assert self._saved(tmp_path).is_file()
        assert discover_judge_results(str(tmp_path)) == []

    def test_index_scoped_review_discovery_ignores_them(self, tmp_path: Path) -> None:
        """``resolve_target`` uses a different glob shape — assert it separately.

        One glob's exclusion does not imply the other's, so neither is inferred
        from the other here.
        """
        assert self._saved(tmp_path).is_file()
        with pytest.raises(MetrologyTargetError, match="No review result for index 305"):
            resolve_target("305", None, str(tmp_path))
