"""The fixed grading review (slice 425 D7, D8): who reviews, the call, and the noise floor.

Every graded diff is reviewed by one alias under the 300 ``code`` template with no tools, so
the reviewer cannot read the user's checkout, where the reference fix lives. This module
resolves the alias to a ``ReviewerRef``, makes the call, and reduces repeated reviews of one
reference diff to a noise floor.
"""

from __future__ import annotations

import asyncio
import difflib
import hashlib
import logging
import tempfile
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from squadron.config.keys import REVIEW_FLOOR_RUNS_MINIMUM
from squadron.core.finding_categories import ReviewCategory
from squadron.core.models import Effort
from squadron.metrology.audit_variance import summarize_counts
from squadron.metrology.floor_stat import FloorStat
from squadron.metrology.grade_models import ReviewerRef, ReviewOutcome
from squadron.metrology.review_models import CodeReviewFinding
from squadron.models.aliases import UnknownModelAliasError, get_all_aliases, model_effort
from squadron.review.categories import normalize_result_categories
from squadron.review.git_utils import run_git
from squadron.review.models import ReviewResult, Severity, Verdict
from squadron.review.review_client import run_review_with_profile
from squadron.review.rules import PROJECT_RULES_CANDIDATES, extract_diff_paths, load_review_rules
from squadron.review.templates import (
    BuiltinReviewTemplate,
    ReviewTemplate,
    get_template,
    load_all_templates,
)

_logger = logging.getLogger(__name__)


class MissingReviewTemplateError(RuntimeError):
    """The ``code`` review template is not registered, so no reviewer identity can be built."""


def code_template() -> ReviewTemplate:
    """The built-in ``code`` review template."""
    load_all_templates()
    template = get_template(BuiltinReviewTemplate.CODE.value)
    if template is None:
        _logger.error("the '%s' review template is not registered", BuiltinReviewTemplate.CODE.value)
        raise MissingReviewTemplateError(
            f"review template '{BuiltinReviewTemplate.CODE.value}' is not registered"
        )
    return template


def code_template_text() -> str:
    """The text of the built-in ``code`` review template (its system prompt)."""
    return code_template().system_prompt


def resolve_reviewer(
    alias: str, *, template_text: Callable[[], str] = code_template_text
) -> ReviewerRef:
    """The reviewer *alias* names: model, profile and effort from ``models.toml``, plus the
    sha256 of the ``code`` template text.

    An alias that ``models.toml`` does not define raises ``UnknownModelAliasError`` naming it.
    ``template_text`` is a parameter so tests need no installed templates.
    """
    known = get_all_aliases()
    entry = known.get(alias)
    if entry is None:
        _logger.error("grading reviewer alias '%s' is not defined in models.toml", alias)
        raise UnknownModelAliasError(alias, difflib.get_close_matches(alias, list(known), n=3))
    effort = model_effort(alias)
    return ReviewerRef.build(
        alias=alias,
        model=entry["model"],
        profile=entry["profile"],
        effort=None if effort is None else effort.value,
        template_hash=hashlib.sha256(template_text().encode("utf-8")).hexdigest(),
    )


class ReviewFailed(Exception):
    """The grading review produced no usable result (D7): the harness absence ``review_failed``."""

    def __init__(self, detail: str, cost_usd: float | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        #: What the failed call cost when it reported a cost; ``None`` when it did not.
        self.cost_usd = cost_usd


#: The async review call. ``run_review_with_profile`` in production, a double in tests.
ReviewCall = Callable[..., Awaitable[ReviewResult]]
_SEVERITIES = {severity.value.lower(): severity for severity in Severity}
#: How much of a failed review's raw output the ERROR log carries, to diagnose it.
RAW_OUTPUT_EXCERPT_CHARS = 1500


def _materialize_start_rules(tree: Path, base_sha: str, scratch: Path) -> Path | None:
    """The project's rules directory as the start commit has it, copied under *scratch*.

    The producer's diff is applied to *tree*, so the rules there may be the producer's own
    edit; the start commit's are the ones every config is reviewed under.
    """
    for candidate in PROJECT_RULES_CANDIDATES:
        listing = run_git(["ls-tree", "-r", "--name-only", base_sha, "--", candidate], cwd=str(tree))
        if listing is None or listing.returncode != 0:
            raise _fail(f"could not list {candidate} at {base_sha[:12]}")
        names = [name for name in listing.stdout.splitlines() if name.strip()]
        for name in names:
            shown = run_git(["show", f"{base_sha}:{name}"], cwd=str(tree))
            if shown is None or shown.returncode != 0:
                raise _fail(f"could not read {name} at {base_sha[:12]}")
            target = scratch / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(shown.stdout, encoding="utf-8")
        if names:
            return scratch / candidate
    return None


def _tree_rules(tree: Path, base_sha: str) -> str | None:
    """The rules the start commit carries, assembled as ``sq review code`` would.

    Only the start commit's own rules directory counts: config, flags, the user's home and
    the producer's edits are never consulted, so the same case gets the same rules for every
    config and whoever runs the grade.
    """
    with tempfile.TemporaryDirectory(prefix="sq-grade-rules-") as scratch:
        rules_dir = _materialize_start_rules(tree, base_sha, Path(scratch))
        if rules_dir is None:
            return None
        changed = extract_diff_paths(base_sha, str(tree))
        return load_review_rules(
            BuiltinReviewTemplate.CODE.value, rules_dir, file_paths=changed, cwd=str(tree)
        ).content


def _findings(result: ReviewResult) -> tuple[tuple[CodeReviewFinding, ...], int]:
    """The normalized findings in the 400 shape, and how many had an off-scale severity."""
    kept: list[CodeReviewFinding] = []
    dropped = 0
    for index, finding in enumerate(result.findings, 1):
        severity_text = str(getattr(finding.severity, "value", finding.severity))
        severity = _SEVERITIES.get(severity_text.strip().lower())
        if severity is None:
            _logger.warning(
                "grading review finding %d has off-scale severity %r; dropped", index, severity_text
            )
            dropped += 1
            continue
        kept.append(
            CodeReviewFinding(
                finding_id=f"F{index:03d}",
                severity=severity,
                category=None if finding.category is None else ReviewCategory(finding.category),
                raw_category=finding.raw_category,
                location=finding.location or finding.file_ref,
                summary=finding.title,
            )
        )
    return tuple(kept), dropped


def _fail(detail: str, cost_usd: float | None = None) -> ReviewFailed:
    _logger.error("grading review failed: %s", detail)
    return ReviewFailed(detail, cost_usd)


def review_tree_diff(
    tree: Path,
    base_sha: str,
    reviewer: ReviewerRef,
    *,
    timeout_s: float,
    review: ReviewCall = run_review_with_profile,
) -> ReviewOutcome:
    """Review ``base_sha..HEAD`` of *tree* with *reviewer* and return what it found (D7).

    The ``code`` template runs with no tools, so the diff and file contents are injected and
    the reviewer cannot read outside the sandbox. The call is bounded by *timeout_s*
    (``benchmark.review_timeout_s``, which the caller reads). A call that raises, times out,
    or returns verdict ``UNKNOWN`` with no findings, or saw only part of the diff, raises
    ``ReviewFailed`` after an ERROR log;
    a review that ran and found nothing is a valid outcome with zero findings.
    """
    rules = _tree_rules(tree, base_sha)
    call = review(
        code_template(),
        {"diff": base_sha, "cwd": str(tree)},
        profile=reviewer.profile,
        rules_content=rules,
        model=reviewer.model,
        no_tools=True,
        effort=None if reviewer.effort is None else Effort(reviewer.effort),
        alias=reviewer.alias,
    )
    try:
        result = asyncio.run(asyncio.wait_for(call, timeout_s))
    except TimeoutError as exc:
        raise _fail(f"the review timed out after {timeout_s}s") from exc
    except Exception as exc:
        _logger.exception("grading review call raised")
        raise ReviewFailed(f"the review call raised {type(exc).__name__}: {exc}") from exc
    if result.verdict is Verdict.UNKNOWN and not result.findings:
        _logger.error(
            "grading review (alias %s) wrote no review; the model's output began: %r",
            reviewer.alias,
            result.raw_output[:RAW_OUTPUT_EXCERPT_CHARS],
        )
        raise _fail("the review returned verdict UNKNOWN with no findings", result.cost_usd)
    injection = result.diff_injection
    if injection is not None and injection.truncated:
        # Findings on part of a diff must not be graded as findings on the whole of it.
        raise _fail(
            f"only {injection.injected_chars} of {injection.total_chars} diff characters "
            f"reached the model; cut files: {[f.path for f in injection.cut_files]}",
            result.cost_usd,
        )
    normalize_result_categories(result)
    findings, unnormalized = _findings(result)
    return ReviewOutcome(
        findings=findings,
        unnormalized_count=unnormalized,
        cost_usd=result.cost_usd,
        rules_hash=None if rules is None else hashlib.sha256(rules.encode("utf-8")).hexdigest(),
    )


def review_floor(outcomes: Sequence[ReviewOutcome], runs: int) -> FloorStat:
    """The noise floor of total findings across *runs* reviews of one reference diff (D8).

    Reduced with ``summarize_counts``, the same reduction 320's audit floor uses. A floor
    never comes from fewer runs than asked: fewer than *runs* outcomes raises, and so does
    *runs* below ``REVIEW_FLOOR_RUNS_MINIMUM`` (a failed floor run raises ``ReviewFailed`` before this).
    """
    if runs < REVIEW_FLOOR_RUNS_MINIMUM:
        raise ValueError(f"a review floor needs at least {REVIEW_FLOOR_RUNS_MINIMUM} runs, got {runs}")
    if len(outcomes) < runs:
        raise ValueError(f"a review floor of {runs} runs got only {len(outcomes)} outcomes")
    return summarize_counts([len(outcome.findings) for outcome in outcomes[:runs]])
