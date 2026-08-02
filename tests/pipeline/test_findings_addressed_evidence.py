"""Tests for the gate-evidence artifact (slice 305 Part F).

The artifact's whole reason for existing outside the ``*-review.*`` namespace
is that metrology sweeps that namespace for judge samples. That exclusion is
asserted here against the real discovery function, not just the glob.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import yaml

from squadron.pipeline.actions.findings_addressed import (
    GATE_EVIDENCE_DOC_TYPE,
    FindingOutcome,
    FindingStatus,
    GateEvidence,
    SettlingScreen,
    render_gate_evidence,
    save_gate_evidence,
)
from squadron.review.models import Verdict

_REVIEWS_SUBDIR = Path("project-documents/user/reviews")


def _evidence(**overrides: object) -> GateEvidence:
    defaults: dict[str, object] = {
        "policy": "findings-addressed",
        "reduced_verdict": Verdict.FAIL,
        "addressed_verdict": Verdict.FAIL,
        "review_verdict": Verdict.CONCERNS,
        "outcomes": [
            FindingOutcome(
                finding_id="F001",
                status=FindingStatus.UNADDRESSED,
                screen=SettlingScreen.EXACT_MATCH,
                note="re-found at src/x.py:12 (correctness)",
            ),
            FindingOutcome(
                finding_id="F002",
                status=FindingStatus.MOVED,
                screen=SettlingScreen.JUDGE,
                successor_id="F077",
            ),
        ],
        "deciding_screen": None,
        "prior_round_sha": "abc123",
        "revision_number": 2,
        "judge_model": "claude-sonnet-5",
        "judge_template": "judge.findings-addressed",
    }
    defaults.update(overrides)
    return GateEvidence(**defaults)  # pyright: ignore[reportArgumentType]


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text()
    assert text.startswith("---\n")
    body = text.split("---\n", 2)[1]
    parsed = yaml.safe_load(body)
    assert isinstance(parsed, dict)
    return parsed  # pyright: ignore[reportUnknownVariableType]


def test_filename_never_matches_the_review_glob(tmp_path: Path) -> None:
    path = save_gate_evidence(_evidence(), step_name="settled", slice_index=305, cwd=str(tmp_path))

    assert path is not None
    assert path.name == "305-gate.findings-addressed.settled-r2.md"
    # The exact glob discover_judge_results uses.
    assert list((tmp_path / _REVIEWS_SUBDIR).glob("*-review.*")) == []


def test_discover_judge_results_ignores_gate_evidence(tmp_path: Path) -> None:
    from squadron.metrology.discovery import discover_judge_results

    save_gate_evidence(_evidence(), step_name="settled", slice_index=305, cwd=str(tmp_path))

    assert discover_judge_results(cwd=str(tmp_path)) == []


def test_frontmatter_round_trips(tmp_path: Path) -> None:
    path = save_gate_evidence(_evidence(), step_name="settled", slice_index=305, cwd=str(tmp_path))
    assert path is not None

    frontmatter = _frontmatter(path)
    assert frontmatter["docType"] == GATE_EVIDENCE_DOC_TYPE
    assert frontmatter["policy"] == "findings-addressed"
    assert frontmatter["verdict"] == "FAIL"
    assert frontmatter["addressedVerdict"] == "FAIL"
    assert frontmatter["reviewVerdict"] == "CONCERNS"
    assert frontmatter["priorRoundSha"] == "abc123"
    assert frontmatter["revision_number"] == 2
    assert frontmatter["judgeTemplate"] == "judge.findings-addressed"

    statuses = frontmatter["findingStatuses"]
    assert isinstance(statuses, list)
    assert statuses[0]["id"] == "F001"
    assert statuses[0]["status"] == FindingStatus.UNADDRESSED.value
    assert statuses[0]["screen"] == SettlingScreen.EXACT_MATCH.value
    assert statuses[1]["successor"] == "F077"


def test_frontmatter_survives_hostile_model_authored_text(tmp_path: Path) -> None:
    """Notes embed finding locations, which are arbitrary model text.

    A colon-space, a leading '#' or '-', or an embedded newline would break
    hand-rendered frontmatter — and an artifact that exists to be
    machine-readable must parse.
    """
    hostile = "re-found at src/foo.py: line 45\n# not a comment\n- not a list item"
    evidence = _evidence(
        outcomes=[
            FindingOutcome(
                finding_id="F001",
                status=FindingStatus.UNADDRESSED,
                screen=SettlingScreen.EXACT_MATCH,
                note=hostile,
            )
        ],
    )
    path = save_gate_evidence(evidence, step_name="a: step # here", slice_index=305, cwd=str(tmp_path))
    assert path is not None

    frontmatter = _frontmatter(path)
    assert frontmatter["gateStep"] == "a: step # here"
    statuses = frontmatter["findingStatuses"]
    assert isinstance(statuses, list)
    assert statuses[0]["note"] == hostile


def test_metadata_and_artifact_carry_the_same_record(tmp_path: Path) -> None:
    """One source object backs both — a divergence here means two assemblies."""
    evidence = _evidence()
    path = save_gate_evidence(evidence, step_name="settled", slice_index=305, cwd=str(tmp_path))
    assert path is not None

    metadata = evidence.to_metadata()
    frontmatter = _frontmatter(path)
    assert metadata["prior_round_sha"] == frontmatter["priorRoundSha"]
    assert metadata["revision_number"] == frontmatter["revision_number"]
    assert metadata["addressed_verdict"] == frontmatter["addressedVerdict"]
    assert metadata["finding_statuses"] == [
        {
            "id": record["id"],
            "status": record["status"],
            "screen": record["screen"],
            "successor": record.get("successor"),
            "note": record.get("note"),
        }
        for record in frontmatter["findingStatuses"]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    ]


def test_screen_0_decision_is_still_written(tmp_path: Path) -> None:
    """Every decision leaves evidence, including the ones no judge saw."""
    evidence = _evidence(
        reduced_verdict=Verdict.PASS,
        addressed_verdict=Verdict.PASS,
        review_verdict=Verdict.PASS,
        outcomes=[],
        deciding_screen=SettlingScreen.NO_PRIOR_ROUND,
        prior_round_sha=None,
        revision_number=1,
        judge_model=None,
        judge_template=None,
    )
    path = save_gate_evidence(evidence, step_name="settled", slice_index=305, cwd=str(tmp_path))
    assert path is not None
    assert path.name.endswith("-r1.md")

    frontmatter = _frontmatter(path)
    assert frontmatter["noPriorRound"] is True
    assert frontmatter["decidingScreen"] == SettlingScreen.NO_PRIOR_ROUND.value
    assert frontmatter["priorRoundSha"] is None
    assert "findingStatuses" not in frontmatter


def test_unwritable_reviews_directory_warns_and_returns_none(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A file where the reviews directory should be — mkdir cannot succeed."""
    blocker = tmp_path / _REVIEWS_SUBDIR.parent
    blocker.parent.mkdir(parents=True, exist_ok=True)
    blocker.write_text("not a directory")

    with caplog.at_level(logging.WARNING):
        path = save_gate_evidence(_evidence(), step_name="settled", slice_index=305, cwd=str(tmp_path))

    assert path is None
    assert "gate evidence" in caplog.text


def test_missing_slice_index_warns_rather_than_fabricating_one(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        path = save_gate_evidence(_evidence(), step_name="settled", slice_index=None, cwd=str(tmp_path))

    assert path is None
    assert "no slice index" in caplog.text
    assert not (tmp_path / _REVIEWS_SUBDIR).exists()


def test_rendered_body_lists_every_finding_outcome() -> None:
    body = render_gate_evidence(_evidence(), step_name="settled")
    assert "`F001`: **unaddressed** [exact_match]" in body
    assert "`F002`: **moved** [judge] (successor: F077)" in body
