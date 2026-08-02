"""Tests for the findings-addressed policy's deterministic screens (slice 305).

Every test here asserts that no judge transport is reached: the screens are
the zero-token layer, and a screen that quietly falls through to a model call
is the cost regression this slice exists to prevent.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest

from squadron.pipeline.actions.findings_addressed import (
    FindingRecord,
    FindingStatus,
    RoundDiff,
    SettlingScreen,
    compute_round_diff,
    concern_plus,
    read_findings,
    run_deterministic_screens,
    screen_no_prior_round,
)
from squadron.pipeline.models import ActionResult
from squadron.review.models import Verdict

_CWD = "/repo"


@pytest.fixture
def no_transport() -> Iterator[None]:
    """Fail the test if the judge transport is invoked."""

    def _forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("judge transport was called from a deterministic screen")

    with patch("squadron.review.review_client.run_review_with_profile", _forbidden):
        yield


def _finding(
    finding_id: str,
    severity: str = "CONCERN",
    category: str = "correctness",
    location: str = "src/x.py:12",
) -> FindingRecord:
    return FindingRecord(
        finding_id=finding_id,
        severity=severity,
        category=category,
        location=location,
        summary=f"summary for {finding_id}",
    )


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["git"], returncode=returncode, stdout=stdout, stderr="")


def _fake_git(responses: dict[str, subprocess.CompletedProcess[str] | None]) -> Any:
    """Return a run_git stand-in dispatching on the git subcommand."""

    def _run(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        return responses[args[0]]

    return _run


# ---------------------------------------------------------------------------
# Finding reading — severity subset and malformed handling
# ---------------------------------------------------------------------------


def test_note_and_pass_findings_are_not_concern_plus() -> None:
    result = ActionResult(
        success=True,
        action_type="review",
        outputs={},
        findings=[
            {"id": "F001", "severity": "NOTE", "category": "style", "location": "a.py:1"},
            {"id": "F002", "severity": "PASS", "category": "style", "location": "a.py:2"},
            {"id": "F003", "severity": "CONCERN", "category": "correctness", "location": "a.py:3"},
            {"id": "F004", "severity": "FAIL", "category": "correctness", "location": "a.py:4"},
        ],
    )
    accountable = concern_plus(read_findings(result))
    assert [record.finding_id for record in accountable] == ["F003", "F004"]


def test_malformed_finding_is_kept_as_residue_and_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A finding missing fields cannot be screened, so it must not be dropped."""
    result = ActionResult(
        success=True,
        action_type="review",
        outputs={},
        findings=[{"id": "F001", "summary": "no severity, no location"}],
    )
    with caplog.at_level(logging.WARNING):
        records = concern_plus(read_findings(result))

    assert [record.finding_id for record in records] == ["F001"]
    assert records[0].malformed is True
    assert "F001" in caplog.text


# ---------------------------------------------------------------------------
# Screen 0 — no prior round
# ---------------------------------------------------------------------------


def test_screen_0_passes_with_annotation_never_unknown(
    caplog: pytest.LogCaptureFixture, no_transport: None
) -> None:
    with caplog.at_level(logging.INFO):
        result = screen_no_prior_round(pipeline_name="p", step_name="settled", iteration=1)

    assert result.leg_verdict == Verdict.PASS
    assert result.deciding_screen == SettlingScreen.NO_PRIOR_ROUND
    assert result.outcomes == []
    assert result.residue == []
    assert "no prior round" in caplog.text
    assert "iteration=1" in caplog.text


# ---------------------------------------------------------------------------
# Screen 1 — byte-identical round
# ---------------------------------------------------------------------------


def test_screen_1_marks_every_prior_finding_unaddressed(
    caplog: pytest.LogCaptureFixture, no_transport: None
) -> None:
    with patch(
        "squadron.pipeline.actions.findings_addressed.screens.run_git",
        _fake_git({"diff": _completed(), "status": _completed(), "rev-parse": _completed("abc123\n")}),
    ):
        diff = compute_round_diff(cwd=_CWD)

    assert diff.is_empty is True
    assert diff.prior_sha == "abc123"

    with caplog.at_level(logging.WARNING):
        result = run_deterministic_screens(
            prior_findings=[_finding("F001"), _finding("F002")],
            fresh_findings=[],
            diff=diff,
        )

    assert result.leg_verdict == Verdict.FAIL
    assert result.deciding_screen == SettlingScreen.BYTE_IDENTICAL
    assert result.residue == []
    assert {outcome.finding_id for outcome in result.outcomes} == {"F001", "F002"}
    assert all(outcome.status == FindingStatus.UNADDRESSED for outcome in result.outcomes)
    assert all(outcome.screen == SettlingScreen.BYTE_IDENTICAL for outcome in result.outcomes)
    assert "no changes" in caplog.text


def test_untracked_file_alone_is_not_a_byte_identical_round(no_transport: None) -> None:
    """git diff misses untracked files; porcelain is why the screen is honest."""
    with patch(
        "squadron.pipeline.actions.findings_addressed.screens.run_git",
        _fake_git(
            {
                "diff": _completed(),
                "status": _completed("?? src/new_file.py\n"),
                "rev-parse": _completed("abc123\n"),
            }
        ),
    ):
        diff = compute_round_diff(cwd=_CWD)

    assert diff.is_empty is False
    assert "src/new_file.py" in diff.changed_paths


# ---------------------------------------------------------------------------
# Git failure — the one condition that earns UNKNOWN
# ---------------------------------------------------------------------------


def test_git_failure_yields_unknown_naming_the_command(
    caplog: pytest.LogCaptureFixture, no_transport: None
) -> None:
    with patch(
        "squadron.pipeline.actions.findings_addressed.screens.run_git",
        _fake_git({"diff": _completed(returncode=128)}),
    ):
        diff = compute_round_diff(cwd=_CWD)

    assert diff.failed_command == "git diff HEAD --name-only"

    with caplog.at_level(logging.WARNING):
        result = run_deterministic_screens(
            prior_findings=[_finding("F001")], fresh_findings=[], diff=diff
        )

    assert result.leg_verdict == Verdict.UNKNOWN
    assert result.deciding_screen is None
    assert "git diff HEAD --name-only" in caplog.text


def test_git_unavailable_yields_unknown(no_transport: None) -> None:
    """run_git returning None (git not invocable) is a failure, not an empty diff."""
    with patch(
        "squadron.pipeline.actions.findings_addressed.screens.run_git",
        _fake_git({"diff": None}),
    ):
        diff = compute_round_diff(cwd=_CWD)

    assert diff.failed_command is not None
    assert diff.is_empty is False


# ---------------------------------------------------------------------------
# Screen 2 — conservative exact matching
# ---------------------------------------------------------------------------


def _changed_diff() -> Any:
    return _fake_git(
        {
            "diff": _completed("src/x.py\n"),
            "status": _completed(),
            "rev-parse": _completed("abc123\n"),
        }
    )


def test_screen_2_settles_a_recurring_exact_match(no_transport: None) -> None:
    with patch("squadron.pipeline.actions.findings_addressed.screens.run_git", _changed_diff()):
        diff = compute_round_diff(cwd=_CWD)

    result = run_deterministic_screens(
        prior_findings=[_finding("F001", location="src/x.py:12", category="correctness")],
        fresh_findings=[_finding("F009", location="src/x.py:12", category="correctness")],
        diff=diff,
    )

    assert result.leg_verdict is None, "screen 2 does not decide the leg on its own"
    assert result.residue == []
    assert len(result.outcomes) == 1
    assert result.outcomes[0].status == FindingStatus.UNADDRESSED
    assert result.outcomes[0].screen == SettlingScreen.EXACT_MATCH


def test_screen_2_leaves_an_unmatched_finding_as_residue(no_transport: None) -> None:
    with patch("squadron.pipeline.actions.findings_addressed.screens.run_git", _changed_diff()):
        diff = compute_round_diff(cwd=_CWD)

    result = run_deterministic_screens(
        prior_findings=[_finding("F001", location="src/x.py:12")],
        fresh_findings=[_finding("F009", location="src/y.py:40")],
        diff=diff,
    )

    assert result.outcomes == []
    assert [record.finding_id for record in result.residue] == ["F001"]


def test_unverified_locations_never_settle_in_screen_2(no_transport: None) -> None:
    """904 normalizes every unknown location to one token; matching on it would
    collide two unrelated findings and trap the loop until exhaustion."""
    with patch("squadron.pipeline.actions.findings_addressed.screens.run_git", _changed_diff()):
        diff = compute_round_diff(cwd=_CWD)

    result = run_deterministic_screens(
        prior_findings=[_finding("F001", location="unverified", category="correctness")],
        fresh_findings=[_finding("F009", location="unverified", category="correctness")],
        diff=diff,
    )

    assert result.outcomes == []
    assert [record.finding_id for record in result.residue] == ["F001"]


def test_no_prior_concern_plus_findings_passes_without_screening(no_transport: None) -> None:
    """Nothing to hold the round accountable for — a known state, so PASS."""
    result = run_deterministic_screens(
        prior_findings=[],
        fresh_findings=[_finding("F009")],
        diff=RoundDiff(changed_paths=frozenset(), is_empty=True, prior_sha="abc123"),
    )
    assert result.leg_verdict == Verdict.PASS
