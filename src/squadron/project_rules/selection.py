"""Selecting the conventions file and rule files for one step (D3, D5, D6)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from squadron.project_rules.conventions import (
    ConventionsFile,
    ConventionsSource,
    find_conventions,
)
from squadron.project_rules.errors import ProjectRulesError
from squadron.project_rules.frontmatter import (
    RuleStep,
    effective_steps,
    globs_match,
    parse_rule_frontmatter,
    paths_to_match,
)

logger = logging.getLogger(__name__)

#: Config key holding the character budget; named in the over-budget error.
MAX_CHARS_KEY = "project_rules.max_chars"

#: Review template rules (``get_template_rules``) keep that role and never reach dispatch.
_REVIEW_TEMPLATE_RULE = "review.md"
_REVIEW_TEMPLATE_RULE_PREFIX = "review-"


class ProjectRulesBudgetError(ProjectRulesError):
    """The conventions file alone exceeds ``project_rules.max_chars`` (D6)."""


@dataclass(frozen=True)
class RuleContext:
    """Everything selection needs for one step, resolved by the caller."""

    step_kind: RuleStep
    #: Paths to match ``paths`` globs against; ``None`` skips the path check.
    file_paths: list[str] | None
    root: Path
    rules_dir: Path | None
    #: The conventions file the provider loads itself (D5), or ``None``.
    native: ConventionsSource | None
    max_chars: int


@dataclass(frozen=True)
class SelectedRule:
    name: str
    content: str


@dataclass(frozen=True)
class ProjectRules:
    """What one step gets: conventions (unless native), selected rules, and what was left out."""

    conventions: ConventionsFile | None
    native: bool
    skipped: list[ConventionsSource]
    rules: list[SelectedRule]
    dropped: list[str]
    #: Raw characters of the injected conventions and rule files (what the budget checks).
    chars: int

    @property
    def conventions_source(self) -> ConventionsSource:
        return ConventionsSource.NONE if self.conventions is None else self.conventions.source

    def to_record(self) -> dict[str, object]:
        """The D7 ``project_rules`` record for step metadata."""
        return {
            "conventions": self.conventions_source.value,
            "native": self.native,
            "skipped": [source.value for source in self.skipped],
            "rules": [rule.name for rule in self.rules],
            "dropped": list(self.dropped),
            "chars": self.chars,
        }


def is_review_template_rule(name: str) -> bool:
    return name == _REVIEW_TEMPLATE_RULE or name.startswith(_REVIEW_TEMPLATE_RULE_PREFIX)


def _candidate_rules(ctx: RuleContext) -> tuple[list[SelectedRule], list[str]]:
    """Rules relevant to the step, in filename order, before the budget (D3), and the
    unreadable ones dropped.

    Reads the files itself rather than through ``load_rules_frontmatter``: selection
    needs the content too, and an unreadable rule here is recorded in ``dropped``,
    where the review path only logs and skips it.
    """
    dropped: list[str] = []
    if ctx.rules_dir is None:
        return [], dropped
    candidates = None if ctx.file_paths is None else paths_to_match(ctx.file_paths, str(ctx.root))
    selected: list[SelectedRule] = []
    for path in sorted(ctx.rules_dir.glob("*.md")):
        if is_review_template_rule(path.name):
            continue
        try:
            content = path.read_text()
        except OSError as exc:
            logger.warning("Dropping unreadable rule file %s: %s", path, exc)
            dropped.append(path.name)
            continue
        fm = parse_rule_frontmatter(content, path.name)
        if ctx.step_kind not in effective_steps(fm):
            continue
        if fm.paths is not None and candidates is not None:
            if not globs_match(fm.paths, candidates):
                continue
        selected.append(SelectedRule(name=path.name, content=content))
    return selected, dropped


def select_project_rules(ctx: RuleContext) -> ProjectRules:
    """Pick the conventions file and the rules for ``ctx.step_kind`` within the budget.

    Raises :class:`ConventionsReadError` for an unreadable conventions file,
    :class:`UnknownRuleStepError` for an unknown ``steps`` value, and
    :class:`ProjectRulesBudgetError` when the conventions file alone is over budget.
    """
    lookup = find_conventions(ctx.root)
    chosen = lookup.chosen
    native = chosen is not None and chosen.source == ctx.native
    chars = 0
    if chosen is not None and not native:
        chars = len(chosen.content)
        if chars > ctx.max_chars:
            raise ProjectRulesBudgetError(
                f"Conventions file {chosen.path} is {chars} characters, over the "
                f"{ctx.max_chars}-character budget ({MAX_CHARS_KEY})"
            )

    candidates, dropped = _candidate_rules(ctx)
    rules: list[SelectedRule] = []
    for rule in candidates:
        if chars + len(rule.content) > ctx.max_chars:
            logger.warning(
                "Dropping rule %s (%d characters): over the %d-character budget (%s)",
                rule.name,
                len(rule.content),
                ctx.max_chars,
                MAX_CHARS_KEY,
            )
            dropped.append(rule.name)
            continue
        chars += len(rule.content)
        rules.append(rule)

    return ProjectRules(
        conventions=chosen,
        native=native,
        skipped=lookup.skipped,
        rules=rules,
        dropped=dropped,
        chars=chars,
    )
