"""Tests for the findings-addressed judge leg (slice 305 Part E).

Covers the status-line parser, transport invocation and its failure modes,
successor/contradiction verification, and the derivation rule. No test reaches
a real provider.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.findings_addressed import (
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    RoundDiff,
    SettlingScreen,
    derive_addressed_verdict,
    is_parse_failure,
    judge_residue,
    parse_status_lines,
    statuses_to_outcomes,
    verify_outcomes,
)
from squadron.pipeline.models import ActionContext
from squadron.review.models import ReviewResult, Verdict

_JUDGE_TRANSPORT = "squadron.pipeline.actions.findings_addressed.judge.run_review_with_profile"


def _finding(
    finding_id: str,
    location: str = "src/x.py:12",
    category: str = "correctness",
    severity: str = "CONCERN",
) -> FindingRecord:
    return FindingRecord(
        finding_id=finding_id,
        severity=severity,
        category=category,
        location=location,
        summary=f"summary for {finding_id}",
    )


def _context(**params: object) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-5", "sdk")
    return ActionContext(
        pipeline_name="p",
        run_id="run-1",
        params=params,
        step_name="settled",
        step_index=2,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd="/repo",
        iteration=2,
    )


def _review_result(raw_output: str) -> ReviewResult:
    return ReviewResult(
        verdict=Verdict.UNKNOWN,
        findings=[],
        template_name="judge.findings-addressed",
        input_files={},
        raw_output=raw_output,
    )


def _diff(*paths: str) -> RoundDiff:
    return RoundDiff(changed_paths=frozenset(paths), is_empty=not paths, prior_sha="abc123")


# ---------------------------------------------------------------------------
# T19 — status-line parser
# ---------------------------------------------------------------------------


def test_parses_well_formed_lines() -> None:
    statuses = parse_status_lines("F001: addressed\nF002: unaddressed\n")
    assert statuses["F001"].status == FindingStatus.ADDRESSED
    assert statuses["F002"].status == FindingStatus.UNADDRESSED


def test_parses_successor_suffix() -> None:
    statuses = parse_status_lines("F001: moved successor=F077")
    assert statuses["F001"].status == FindingStatus.MOVED
    assert statuses["F001"].successor_id == "F077"


def test_parses_case_variants_and_list_markers() -> None:
    statuses = parse_status_lines("- F001: ADDRESSED\n* F002 : Unaddressed")
    assert statuses["F001"].status == FindingStatus.ADDRESSED
    assert statuses["F002"].status == FindingStatus.UNADDRESSED


def test_parses_through_leading_prose() -> None:
    """The real output shape, as models actually deliver it."""
    raw = (
        "I reviewed the diff against each prior finding below.\n"
        "\n"
        "F001: addressed\n"
        "F002: moved successor=F310\n"
        "\n"
        "Let me know if you need more detail.\n"
    )
    statuses = parse_status_lines(raw)
    assert set(statuses) == {"F001", "F002"}
    assert statuses["F002"].successor_id == "F310"


def test_unknown_status_token_is_disputed(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        statuses = parse_status_lines("F001: mostly-fixed")
    assert statuses["F001"].status == FindingStatus.DISPUTED
    assert "mostly-fixed" in caplog.text


def test_missing_line_becomes_disputed(caplog: pytest.LogCaptureFixture) -> None:
    residue = [_finding("F001"), _finding("F002")]
    statuses = parse_status_lines("F001: addressed")
    with caplog.at_level(logging.WARNING):
        outcomes = statuses_to_outcomes(residue, statuses)
    assert [outcome.status for outcome in outcomes] == [
        FindingStatus.ADDRESSED,
        FindingStatus.DISPUTED,
    ]
    assert all(outcome.screen == SettlingScreen.JUDGE for outcome in outcomes)
    assert "F002" in caplog.text


def test_wholly_unparseable_response_is_a_parse_failure() -> None:
    residue = [_finding("F001")]
    statuses = parse_status_lines("I was unable to complete this task.")
    assert is_parse_failure(residue, statuses) is True


def test_a_response_about_other_findings_is_still_a_parse_failure() -> None:
    """Status lines that name no residue finding tell us nothing about it."""
    residue = [_finding("F001")]
    statuses = parse_status_lines("F999: addressed")
    assert is_parse_failure(residue, statuses) is True


# ---------------------------------------------------------------------------
# T20 — invocation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_residue_of_two_produces_exactly_one_transport_call() -> None:
    transport = AsyncMock(return_value=_review_result("F001: addressed\nF002: unaddressed"))
    residue = [_finding("F001"), _finding("F002", location="src/y.py:8")]

    with patch(_JUDGE_TRANSPORT, transport):
        result = await judge_residue(
            _context(review_from="fresh-review"),
            residue=residue,
            fresh_findings=[_finding("F009")],
            diff=_diff("src/x.py", "src/y.py"),
        )

    assert transport.await_count == 1
    prompt_inputs: dict[str, Any] = transport.await_args.args[1]
    assert "F001" in prompt_inputs["prior_findings"]
    assert "F002" in prompt_inputs["prior_findings"]
    assert "src/x.py" in prompt_inputs["round_diff"]
    assert "F009" in prompt_inputs["fresh_findings"]
    assert [outcome.finding_id for outcome in result.outcomes] == ["F001", "F002"]
    assert result.failed is False


@pytest.mark.asyncio
async def test_empty_residue_produces_zero_transport_calls() -> None:
    transport = AsyncMock()
    with patch(_JUDGE_TRANSPORT, transport):
        result = await judge_residue(_context(), residue=[], fresh_findings=[], diff=_diff("src/x.py"))
    transport.assert_not_awaited()
    assert result.outcomes == []
    assert result.failed is False


@pytest.mark.asyncio
async def test_judge_block_model_overrides_the_cascade() -> None:
    transport = AsyncMock(return_value=_review_result("F001: addressed"))
    context = _context(review_from="fresh-review", judge={"model": "haiku"})

    with patch(_JUDGE_TRANSPORT, transport):
        await judge_residue(
            context,
            residue=[_finding("F001")],
            fresh_findings=[],
            diff=_diff("src/x.py"),
        )

    context.resolver.resolve.assert_called_once_with("haiku", None)  # pyright: ignore[reportFunctionMemberAccess]


@pytest.mark.asyncio
async def test_transport_failure_fails_the_leg_closed(caplog: pytest.LogCaptureFixture) -> None:
    transport = AsyncMock(side_effect=RuntimeError("provider exploded"))

    with patch(_JUDGE_TRANSPORT, transport), caplog.at_level(logging.ERROR):
        result = await judge_residue(
            _context(),
            residue=[_finding("F001")],
            fresh_findings=[],
            diff=_diff("src/x.py"),
        )

    assert result.failed is True
    assert result.outcomes == []
    assert "provider exploded" in caplog.text
    assert derive_addressed_verdict(result.outcomes, judge_failed=result.failed) == Verdict.UNKNOWN


@pytest.mark.asyncio
async def test_unreadable_output_fails_the_leg_closed() -> None:
    transport = AsyncMock(return_value=_review_result("I could not determine anything."))

    with patch(_JUDGE_TRANSPORT, transport):
        result = await judge_residue(
            _context(),
            residue=[_finding("F001")],
            fresh_findings=[],
            diff=_diff("src/x.py"),
        )

    assert result.failed is True


# ---------------------------------------------------------------------------
# T21 — successor verification and contradiction check
# ---------------------------------------------------------------------------


def _outcome(status: FindingStatus, successor: str | None = None) -> FindingOutcome:
    return FindingOutcome(
        finding_id="F001", status=status, screen=SettlingScreen.JUDGE, successor_id=successor
    )


def test_moved_with_present_successor_survives() -> None:
    verified = verify_outcomes(
        [_outcome(FindingStatus.MOVED, "F077")],
        residue=[_finding("F001")],
        fresh_findings=[_finding("F077", location="src/y.py:3")],
        diff=_diff("src/x.py"),
    )
    assert verified[0].status == FindingStatus.MOVED
    assert verified[0].successor_id == "F077"


def test_moved_with_absent_successor_downgrades(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        verified = verify_outcomes(
            [_outcome(FindingStatus.MOVED, "F077")],
            residue=[_finding("F001")],
            fresh_findings=[],
            diff=_diff("src/x.py"),
        )
    assert verified[0].status == FindingStatus.DISPUTED
    assert verified[0].note is not None and "moved" in verified[0].note
    assert "F077" in caplog.text


def test_moved_without_any_successor_downgrades() -> None:
    verified = verify_outcomes(
        [_outcome(FindingStatus.MOVED)],
        residue=[_finding("F001")],
        fresh_findings=[],
        diff=_diff("src/x.py"),
    )
    assert verified[0].status == FindingStatus.DISPUTED


def test_addressed_over_untouched_path_downgrades(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        verified = verify_outcomes(
            [_outcome(FindingStatus.ADDRESSED)],
            residue=[_finding("F001", location="src/x.py:12")],
            fresh_findings=[],
            diff=_diff("src/unrelated.py"),
        )
    assert verified[0].status == FindingStatus.DISPUTED
    assert "src/x.py:12" in caplog.text


def test_addressed_over_touched_path_is_accepted() -> None:
    verified = verify_outcomes(
        [_outcome(FindingStatus.ADDRESSED)],
        residue=[_finding("F001", location="src/x.py:12")],
        fresh_findings=[],
        diff=_diff("src/x.py"),
    )
    assert verified[0].status == FindingStatus.ADDRESSED


def test_unverified_location_cannot_be_contradicted() -> None:
    """904's unknown-location token names no path, so nothing contradicts it."""
    verified = verify_outcomes(
        [_outcome(FindingStatus.ADDRESSED)],
        residue=[_finding("F001", location="unverified")],
        fresh_findings=[],
        diff=_diff("src/unrelated.py"),
    )
    assert verified[0].status == FindingStatus.ADDRESSED


# ---------------------------------------------------------------------------
# T22 — derivation rule
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("statuses", "judge_failed", "expected"),
    [
        ([], False, Verdict.PASS),
        ([FindingStatus.ADDRESSED], False, Verdict.PASS),
        ([FindingStatus.ADDRESSED, FindingStatus.MOVED], False, Verdict.PASS),
        ([FindingStatus.UNADDRESSED], False, Verdict.FAIL),
        ([FindingStatus.ADDRESSED, FindingStatus.UNADDRESSED], False, Verdict.FAIL),
        ([FindingStatus.DISPUTED], False, Verdict.UNKNOWN),
        # UNKNOWN dominates FAIL: a check that could not run is not a check
        # that ran and failed.
        ([FindingStatus.UNADDRESSED, FindingStatus.DISPUTED], False, Verdict.UNKNOWN),
        ([FindingStatus.ADDRESSED], True, Verdict.UNKNOWN),
        ([], True, Verdict.UNKNOWN),
    ],
)
def test_derivation_table(statuses: list[FindingStatus], judge_failed: bool, expected: str) -> None:
    outcomes = [
        FindingOutcome(finding_id=f"F{index}", status=status, screen=SettlingScreen.JUDGE)
        for index, status in enumerate(statuses)
    ]
    assert derive_addressed_verdict(outcomes, judge_failed=judge_failed) == expected
