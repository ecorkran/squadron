"""Tests for squadron.documents.validate.validate_document."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

from squadron.documents.frontmatter import read_frontmatter
from squadron.documents.validate import ViolationCode, validate_document
from squadron.pipeline.actions.devlog import DevlogAction
from squadron.pipeline.actions.devlog import (
    _read_or_create as devlog_read_or_create,  # pyright: ignore[reportPrivateUsage]
)
from squadron.pipeline.actions.findings_addressed.evidence import (
    GateEvidence,
    render_gate_evidence,
)
from squadron.pipeline.models import ActionContext
from squadron.review.addressed.models import FindingOutcome, FindingStatus, SettlingScreen
from squadron.review.resolution_artifact import ResolutionRecord, render_resolution

_VALID_SLICE_DESIGN = """---
docType: slice-design
project: squadron
dateCreated: 20260803
dateUpdated: 20260804
status: not_started
---

# probe
"""

_VALID_TASKS = """---
docType: tasks
project: squadron
dateCreated: 20260803
dateUpdated: 20260804
status: not_started
---

# probe
"""

_VALID_REVIEW = """---
docType: review
project: squadron
dateCreated: 20260803
dateUpdated: 20260804
status: complete
---

# probe
"""


def test_fm001_no_frontmatter_block(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("# just a heading\n\nno frontmatter here.\n", encoding="utf-8")

    violations = validate_document(doc)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM001
    assert violations[0].line == 1


def test_fm002_unparseable_location_colon_space(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "---\n"
        "docType: review\n"
        "project: squadron\n"
        "dateCreated: 20260803\n"
        "dateUpdated: 20260803\n"
        "status: complete\n"
        "findings:\n"
        "  - id: F001\n"
        '    summary: "probe"\n'
        "    location: Slice design: Implementation Details\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )

    violations = validate_document(doc)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM002
    assert violations[0].detail is not None
    assert violations[0].line > 1


def test_fm003_block_parses_to_non_mapping(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text("---\n- one\n- two\n---\n\nbody\n", encoding="utf-8")

    violations = validate_document(doc)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM003


def test_fm004_missing_universal_field(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "---\ndocType: slice-design\nproject: squadron\ndateCreated: 20260803\n---\n\nbody\n",
        encoding="utf-8",
    )

    violations = validate_document(doc)

    codes = {v.code for v in violations}
    keys = {v.key for v in violations if v.code == ViolationCode.FM004}
    assert ViolationCode.FM004 in codes
    assert "dateUpdated" in keys
    assert "status" in keys


def test_fm005_invalid_status(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "---\n"
        "docType: notes\n"
        "project: squadron\n"
        "dateCreated: 20260803\n"
        "dateUpdated: 20260803\n"
        "status: draft\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )

    violations = validate_document(doc)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM005
    assert violations[0].key == "status"
    assert violations[0].actual == "draft"
    assert "not_started" in violations[0].accepted


def test_fm006_invalid_doctype(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "---\n"
        "docType: task-breakdown\n"
        "project: squadron\n"
        "dateCreated: 20260803\n"
        "dateUpdated: 20260803\n"
        "status: not_started\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )

    violations = validate_document(doc)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM006
    assert violations[0].actual == "task-breakdown"


def test_fm007_malformed_date(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "---\n"
        "docType: notes\n"
        "project: squadron\n"
        "dateCreated: 2026-08-03\n"
        "dateUpdated: 20260803\n"
        "status: not_started\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )

    violations = validate_document(doc)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM007
    assert violations[0].key == "dateCreated"


def test_fm008_not_utf8(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_bytes(b"---\ndocType: notes\n---\n\n\xff\xfe garbage\n")

    violations = validate_document(doc)

    assert len(violations) == 1
    assert violations[0].code == ViolationCode.FM008


def test_valid_slice_design_yields_zero_violations(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(_VALID_SLICE_DESIGN, encoding="utf-8")

    assert validate_document(doc) == []


def test_valid_tasks_yields_zero_violations(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(_VALID_TASKS, encoding="utf-8")

    assert validate_document(doc) == []


def test_valid_review_yields_zero_violations(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(_VALID_REVIEW, encoding="utf-8")

    assert validate_document(doc) == []


def test_two_problems_yield_two_violations(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "---\n"
        "docType: task-breakdown\n"
        "project: squadron\n"
        "dateCreated: 20260803\n"
        "dateUpdated: 20260803\n"
        "status: draft\n"
        "---\n\nbody\n",
        encoding="utf-8",
    )

    violations = validate_document(doc)

    codes = {v.code for v in violations}
    assert codes == {ViolationCode.FM005, ViolationCode.FM006}


def test_machine_artifact_gate_evidence_validates_clean(tmp_path: Path) -> None:
    evidence = GateEvidence(
        policy="findings-addressed",
        reduced_verdict="PASS",
        addressed_verdict="PASS",
        review_verdict="PASS",
        outcomes=[
            FindingOutcome(
                finding_id="F001",
                status=FindingStatus.ADDRESSED,
                screen=SettlingScreen.JUDGE,
            )
        ],
    )
    rendered = render_gate_evidence(evidence, step_name="findings_addressed", date_created="20260804")
    doc = tmp_path / "gate-evidence.md"
    doc.write_text(rendered, encoding="utf-8")

    assert validate_document(doc) == []


def test_machine_artifact_resolution_validates_clean(tmp_path: Path) -> None:
    record = ResolutionRecord(
        index=172,
        review_file="172-review.slice.probe.md",
        review_type="slice",
        slice_name="probe",
        project="squadron",
        review_verdict="PASS",
        resolution="accepted",
        date_created=20260804,
    )
    rendered = render_resolution(record)
    doc = tmp_path / "resolution.md"
    doc.write_text(rendered, encoding="utf-8")

    assert validate_document(doc) == []


def test_machine_artifact_devlog_stub_validates_clean(tmp_path: Path) -> None:
    """The devlog stub _read_or_create writes (T25) validates clean.

    This is the regression guard against the gate firing on squadron's own
    write path, mirroring the gate-evidence and resolution guards above.
    """
    doc = tmp_path / "DEVLOG.md"
    devlog_read_or_create(doc, today="20260804", project="squadron")

    assert validate_document(doc) == []


def test_devlog_append_advances_dateupdated(tmp_path: Path) -> None:
    """The real-world defect T25/T26 close: DEVLOG.md carried a stale
    dateUpdated because the append path never re-stamped it by hand.
    """
    doc = tmp_path / "DEVLOG.md"
    doc.write_text(
        "---\n"
        "docType: devlog\n"
        "project: squadron\n"
        "layer: project\n"
        "dateCreated: 20260801\n"
        "dateUpdated: 20260801\n"
        "---\n\n# Development Log\n\n---\n\n## 20260801\n\nold entry\n",
        encoding="utf-8",
    )

    action = DevlogAction()
    context = ActionContext(
        pipeline_name="test-pipeline",
        run_id="r1",
        params={"content": "new entry", "_project": "squadron", "path": str(doc)},
        step_name="step1",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(tmp_path),
    )

    result = asyncio.run(action.execute(context))

    assert result.success
    updated = read_frontmatter(doc)
    assert updated is not None
    assert str(updated["dateUpdated"]) != "20260801"
