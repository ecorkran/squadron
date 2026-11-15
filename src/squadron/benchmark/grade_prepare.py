"""Preparing the tree to grade: the diff, the review, the restored config, the reinstall.

The tree is rebuilt from the start commit plus the subject's diff and committed as the
benchmark identity, so ``start..HEAD`` is exactly what the subject changed (slice 425 D1).
The review comes first, on the tree as the producer wrote it; then the tool config is
restored so every later check runs under the start commit's config (D4); then a reinstall if
dependencies changed (D5). A step that cannot continue raises ``GradeAbsent``.
"""

from __future__ import annotations

import hashlib
import json

from squadron.benchmark.adapter import EnvironmentFailureReason, EnvironmentResolutionError
from squadron.benchmark.grade_checks import load_baseline, record_baseline
from squadron.benchmark.grade_deps import absent
from squadron.benchmark.grade_review import ReviewFailed, review_floor
from squadron.benchmark.grade_run import GitFailure, GradeRun, run_git
from squadron.benchmark.grading_adapter import ProducerConfigError
from squadron.metrology.grade_models import GradeAbsence, GradeSubject, ReviewOutcome, ReviewSummary

COMMIT_MESSAGE = "benchmark: graded subject"
#: Why a reinstall failed, as an absence (D5): the producer's own tree, or the harness.
REINSTALL_ABSENCE: dict[EnvironmentFailureReason, GradeAbsence] = {
    EnvironmentFailureReason.LOCK_STALE_OR_UNRESOLVABLE: GradeAbsence.PRODUCER_ENV_UNRESOLVABLE,
    EnvironmentFailureReason.NO_LOCKFILE: GradeAbsence.PRODUCER_ENV_UNRESOLVABLE,
    EnvironmentFailureReason.LOCKFILE_UNSUPPORTED: GradeAbsence.PRODUCER_ENV_UNRESOLVABLE,
    EnvironmentFailureReason.INSTALL_TIMEOUT: GradeAbsence.ENVIRONMENT_FAILED,
    EnvironmentFailureReason.INSTALLER_MISSING: GradeAbsence.ENVIRONMENT_FAILED,
}


def verify_environment(run: GradeRun) -> None:
    """The grade sandbox must reproduce the environment the subject was made in (D1)."""
    actual = run.sandbox.identity.identity_digest
    expected = run.target.environment_digest
    if actual != expected:
        raise absent(
            GradeAbsence.ENVIRONMENT_CHANGED,
            f"the grade environment {actual[:12]} differs from the expected {expected[:12]}",
        )


def take_baseline(run: GradeRun) -> None:
    """The step before the diff applies: empty for a replay, the baseline for a reference."""
    if run.target.subject is GradeSubject.REFERENCE:
        record_baseline(run)


def subject_diff(run: GradeRun) -> str:
    """The diff to apply: a replay's stored one, or ``start..reference`` from the user's checkout."""
    target = run.target
    if target.subject is GradeSubject.REPLAY:
        if target.diff_sha256 is None:
            raise ValueError("a replay target carries the sha256 of its stored diff")
        return run.deps.store.diffs.get(target.diff_sha256).decode("utf-8")
    case = run.case
    try:
        return run_git(
            run,
            ["diff", "--binary", case.start_sha, case.reference_sha],
            cwd=str(run.deps.repo_root_for(case)),
            in_sandbox=False,
        )
    except GitFailure as exc:
        raise absent(GradeAbsence.REFERENCE_UNREADABLE, exc.detail) from exc


def apply_subject(run: GradeRun) -> str:
    """Apply the diff to the start tree and commit it; returns the new HEAD."""
    diff = subject_diff(run)
    tree = str(run.sandbox.tree)
    try:
        run_git(
            run,
            ["apply", "--binary", "--whitespace=nowarn", "-"],
            cwd=tree,
            in_sandbox=True,
            stdin=diff,
        )
        run_git(run, ["add", "-A"], cwd=tree, in_sandbox=True)
        run_git(run, ["commit", "-q", "-m", COMMIT_MESSAGE], cwd=tree, in_sandbox=True)
        head = run_git(run, ["rev-parse", "HEAD"], cwd=tree, in_sandbox=True).strip()
    except GitFailure as exc:
        raise absent(GradeAbsence.DIFF_APPLY_FAILED, exc.detail) from exc
    run.head_sha = head
    return head


def review_once(run: GradeRun) -> ReviewOutcome:
    """One budgeted review of ``start..HEAD``; the findings go to the ``reviews`` sidecar.

    The budget is checked before the call (``GradeCapReached`` propagates and writes no
    record) and charged after it, failures included, at the per-review figure when the review
    reports no cost.
    """
    deps = run.deps
    deps.budget.before_review()
    try:
        outcome = deps.reviewer(run.sandbox.tree, run.case.start_sha)
    except ReviewFailed as exc:
        # A failed review spent what it spent (or the per-review figure when it reported
        # nothing), so repeated failures still reach the cap and the record shows the spend.
        deps.budget.after_review(exc.cost_usd)
        run.review_costs.append(exc.cost_usd)
        raise absent(GradeAbsence.REVIEW_FAILED, exc.detail) from exc
    deps.budget.after_review(outcome.cost_usd)
    payload = {
        "findings": [finding.model_dump(mode="json") for finding in outcome.findings],
        "unnormalized_count": outcome.unnormalized_count,
    }
    digest = deps.store.reviews.put(json.dumps(payload, sort_keys=True).encode("utf-8"))
    run.review_summaries.append(ReviewSummary.from_outcome(outcome, digest))
    run.review_costs.append(outcome.cost_usd)
    return outcome


def review_reference(run: GradeRun) -> None:
    """The reference's ``review_floor_runs`` reviews and the noise floor they give (D8).

    Each run is budgeted before it starts. A failed run fails the reference, so a floor never
    comes from fewer runs; a cap hit between runs propagates and no record is written.
    """
    runs = run.deps.grader.review_floor_runs
    outcomes = [review_once(run) for _ in range(runs)]
    run.review_floor = review_floor(outcomes, runs)


def record_lockfile(run: GradeRun) -> None:
    """The sha256 of the producer's lock file, ``None`` when its tree has none (every grade)."""
    path = run.sandbox.tree / run.sandbox.identity.lockfile_path
    run.lockfile_sha256 = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def restore_config(run: GradeRun) -> None:
    """Restore the start commit's tool config by section; the edits are counted (D4)."""
    try:
        result = run.adapter.restore_tool_config(run.sandbox.tree, run.start)
    except ProducerConfigError as exc:
        raise absent(GradeAbsence.PRODUCER_ENV_UNRESOLVABLE, str(exc)) from exc
    run.config_edits = result.config_edits


def reinstall_if_dependencies_changed(run: GradeRun) -> None:
    """Reinstall from the producer's lock when dependencies changed (D5)."""
    try:
        changed = run.adapter.deps_changed(run.sandbox.tree, run.start)
    except ProducerConfigError as exc:
        raise absent(GradeAbsence.PRODUCER_ENV_UNRESOLVABLE, str(exc)) from exc
    if not changed:
        return
    run.reinstalled = True
    try:
        run.sandbox.reinstall()
    except EnvironmentResolutionError as exc:
        raise absent(REINSTALL_ABSENCE[exc.reason], f"{exc.reason.value}: {exc.detail}") from exc


def prepare_tree(run: GradeRun) -> None:
    """Environment check, baseline, diff, reference read (replays), review, restored config
    and reinstall, in D1's order."""
    verify_environment(run)
    take_baseline(run)
    apply_subject(run)
    record_lockfile(run)
    if run.target.subject is GradeSubject.REPLAY:
        # A store read: a missing reference stops the grade before the paid review.
        load_baseline(run)
        review_once(run)
    else:
        review_reference(run)
    restore_config(run)
    reinstall_if_dependencies_changed(run)
