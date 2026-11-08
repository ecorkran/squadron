"""The yield report: counts, the pooled row, rendering and the case sets it names (slice 422 D12)."""

# The exact-text snapshot below has lines longer than the line limit by design.
# ruff: noqa: E501

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from squadron.benchmark.fairness import FAIRNESS_RULE_VERSION
from squadron.benchmark.yield_report import build_yield, render_json, render_text
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import (
    CandidateRejection,
    CaseSet,
    FixQualification,
    HiddenTestVerdict,
    HiddenTestVerdictKind,
    QualificationOutcome,
    TestRejection,
)
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.snapshot_models import SourceLanguage

T0 = datetime(2026, 11, 1, tzinfo=UTC)
SAMPLES, TARGET = 3, 0.20


def project(value: str) -> ProjectId:
    return ProjectId(value=value, source=ProjectIdSource.RECORDED)


def environment(lock: str = "l") -> EnvironmentIdentity:
    return EnvironmentIdentity(
        language=SourceLanguage.PYTHON,
        lockfile_path="uv.lock",
        lockfile_sha256=lock * 64,
        interpreter_version="3.12",
        installer_version="uv",
        platform="darwin",
        scrub_spec_version=1,
    )


def record(
    proj: str,
    sha: str,
    outcome: QualificationOutcome,
    rejection: CandidateRejection | None = None,
    *,
    case_id: str | None = None,
    verdicts: tuple[TestRejection, ...] = (),
    at: int = 0,
    env: EnvironmentIdentity | None = None,
) -> FixQualification:
    return FixQualification(
        project_id=project(proj),
        commit_sha=sha * 40,
        parent_sha="0" * 40,
        issue_ref=None,
        rule_version=FAIRNESS_RULE_VERSION,
        environment=env,
        repeats=3,
        outcome=outcome,
        case_id=case_id,
        rejection=rejection,
        hidden_verdicts=tuple(
            HiddenTestVerdict(
                node_id=f"t.py::t{i}", kind=HiddenTestVerdictKind.REJECTED, rejection=reason
            )
            for i, reason in enumerate(verdicts)
        ),
        created_at=T0 + timedelta(minutes=at),
    )


Q, R, H = (
    QualificationOutcome.QUALIFIED,
    QualificationOutcome.REJECTED,
    QualificationOutcome.HARNESS_ERROR,
)


def sample_records() -> list[FixQualification]:
    return [
        record("alpha", "a", Q, case_id="case-aaaaaaaaaaaaaaaa", env=environment()),
        record("alpha", "b", R, CandidateRejection.NO_TEST_CHANGE),
        record(
            "alpha",
            "c",
            R,
            CandidateRejection.NO_QUALIFYING_HIDDEN_TEST,
            verdicts=(
                TestRejection.PATCHES_PROJECT_CODE,
                TestRejection.PATCHES_PROJECT_CODE,
                TestRejection.REACHES_PAST_BOUNDARY,
            ),
        ),
        record("alpha", "d", H),
        record("alpha", "e", R, CandidateRejection.MERGE_COMMIT),
        record("beta", "f", R, CandidateRejection.NO_TEST_CHANGE),
        record("beta", "1", R, CandidateRejection.NO_TEST_CHANGE),
    ]


def report():  # type: ignore[no-untyped-def]
    return build_yield(sample_records(), [], SAMPLES, TARGET)


def test_counts_equal_the_hand_counts() -> None:
    alpha, beta = report().rows
    assert (alpha.project, alpha.candidates, alpha.qualified, alpha.harness_errors) == (
        "alpha",
        5,
        1,
        1,
    )
    assert alpha.rejected == {
        CandidateRejection.NO_TEST_CHANGE: 1,
        CandidateRejection.NO_QUALIFYING_HIDDEN_TEST: 1,
        CandidateRejection.MERGE_COMMIT: 1,
    }
    assert (beta.candidates, beta.qualified) == (2, 0)
    assert beta.rejected == {CandidateRejection.NO_TEST_CHANGE: 2}


def test_the_pooled_row_sums_the_rows() -> None:
    pooled = report().pooled
    assert pooled is not None
    assert (pooled.project, pooled.candidates, pooled.qualified, pooled.harness_errors) == (
        "pooled",
        7,
        1,
        1,
    )
    assert pooled.rejected[CandidateRejection.NO_TEST_CHANGE] == 3
    assert pooled.rejected[CandidateRejection.MERGE_COMMIT] == 1
    assert pooled.separability.qualified_cases == 1


def test_test_rejections_are_counted_per_verdict_not_per_candidate() -> None:
    alpha = report().rows[0]
    assert alpha.test_rejections == {
        TestRejection.PATCHES_PROJECT_CODE: 2,
        TestRejection.REACHES_PAST_BOUNDARY: 1,
    }


def test_a_project_with_only_rejections_still_gets_a_row_saying_no_qualified_cases() -> None:
    beta = report().rows[1]
    assert beta.separability.no_qualified_cases is True
    assert "separability beta (k=3 samples, target 0.20): no qualified cases" in render_text(report())


def test_a_project_without_records_is_omitted() -> None:
    assert [row.project for row in report().rows] == ["alpha", "beta"]


def test_a_commit_counts_once_as_its_latest_record() -> None:
    early = record("alpha", "a", R, CandidateRejection.NO_ISSUE_HOST, at=0)
    later = record("alpha", "a", Q, case_id="case-bbbbbbbbbbbbbbbb", at=5, env=environment())
    result = build_yield([early, later], [], SAMPLES, TARGET)
    row = result.rows[0]
    assert (row.candidates, row.qualified, row.rejected) == (1, 1, {})


def test_the_latest_record_wins_whatever_its_environment_or_order_in_the_input() -> None:
    older_env = record("alpha", "a", Q, case_id="case-cccccccccccccccc", at=1, env=environment("o"))
    newer_pre = record("alpha", "a", R, CandidateRejection.NO_PACKAGING_BOUNDARY, at=9)
    for ordering in ([older_env, newer_pre], [newer_pre, older_env]):
        row = build_yield(ordering, [], SAMPLES, TARGET).rows[0]
        assert (row.qualified, row.rejected) == (0, {CandidateRejection.NO_PACKAGING_BOUNDARY: 1})


def test_no_records_at_all() -> None:
    empty = build_yield([], [], SAMPLES, TARGET)
    assert empty.rows == () and empty.pooled is None
    assert render_text(empty) == "no fix qualification records\n"


SNAPSHOT = """\
project  candidates  qualified  top rejections
alpha    5           1          harness_error 1, merge_commit 1, no_qualifying_hidden_test 1 (patches_project_code 2, reaches_past_boundary 1), no_test_change 1
beta     2           0          no_test_change 2
pooled   7           1          no_test_change 3, harness_error 1, merge_commit 1, no_qualifying_hidden_test 1 (patches_project_code 2, reaches_past_boundary 1)

separability alpha (k=3 samples, target 0.20): n=1 qualified -> MDD 1.14 -> not enough (need >= 33 cases)
separability beta (k=3 samples, target 0.20): no qualified cases (need >= 33 cases)
separability pooled (k=3 samples, target 0.20): n=1 qualified -> MDD 1.14 -> not enough (need >= 33 cases)
assumes independent outcomes, p=0.5, constant per-case difference; "enough" fails if per-case differences vary; 425 replaces this with measured variance
"""


def test_the_text_output_matches_the_documented_layout_exactly() -> None:
    assert render_text(report()) == SNAPSHOT


def test_enough_cases_reads_as_enough() -> None:
    many = [
        record("alpha", f"{i:x}", Q, case_id=f"case-{i:016x}", env=environment()) for i in range(40)
    ]
    text = render_text(build_yield(many, [], SAMPLES, TARGET))
    assert "n=40 qualified -> MDD 0.18 -> enough cases" in text


def test_json_names_the_case_set_and_version_and_round_trips() -> None:
    qualified = record("alpha", "a", Q, case_id="case-aaaaaaaaaaaaaaaa", env=environment())
    sets = [
        CaseSet(name="fix-alpha", version=1, case_ids=("case-aaaaaaaaaaaaaaaa",), created_at=T0),
        CaseSet(
            name="fix-alpha", version=2, case_ids=("case-aaaaaaaaaaaaaaaa", "case-zzz"), created_at=T0
        ),
        CaseSet(name="elsewhere", version=1, case_ids=("case-other",), created_at=T0),
    ]
    payload = json.loads(render_json(build_yield([qualified], sets, SAMPLES, TARGET)))
    assert payload["case_sets"] == [
        {"name": "fix-alpha", "version": 1},
        {"name": "fix-alpha", "version": 2},
    ]
    assert payload["rows"][0]["project"] == "alpha" and payload["rows"][0]["qualified"] == 1
    assert payload["pooled"]["project"] == "pooled"
    assert payload["rows"][0]["separability"]["cases_needed"] == 33
    assert "425" in payload["assumption"]
    assert json.loads(json.dumps(payload)) == payload
