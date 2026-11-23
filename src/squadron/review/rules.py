"""Rules file discovery, language detection, and content loading for reviews."""

from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from squadron.config.manager import get_config
from squadron.integrations.context_forge import GUIDE_RULES_DIR
from squadron.project_rules.frontmatter import (
    RuleFrontmatter,
    RuleStep,
    effective_steps,
    load_rules_frontmatter,
    match_rules_files,
    path_globs,
)
from squadron.project_rules.render import RULES_SEPARATOR
from squadron.project_rules.selection import is_review_template_rule
from squadron.review.git_utils import run_git
from squadron.review.templates import user_templates_dir

_logger = logging.getLogger(__name__)


class RulesSource(StrEnum):
    """Which source produced the resolved rules directory.

    Written to review frontmatter as ``rulesSource``, so the values are part
    of the artifact contract: lowercase, and read back by consumers.
    """

    FLAG = "flag"
    CONFIG = "config"
    PROJECT = "project"
    USER = "user"
    TEMPLATE = "template"
    #: Rules reached the reviewer from an explicit ``--rules`` file (or the
    #: ``default_rules`` config key) with no rules *directory* resolving. The
    #: enum otherwise names directory sources; without this member such a run
    #: recorded ``none``, which a consumer would read as "no rules were given"
    #: while rules demonstrably were.
    FILE = "file"
    NONE = "none"


#: Where a project keeps its own rules, in resolution order.
PROJECT_RULES_CANDIDATES = ("rules", ".claude/rules")


def project_rules_dir(cwd: str) -> Path | None:
    """The project's own rules directory under *cwd*, ``None`` when it has none.

    Never consults config, flags or the user's home: the benchmark grading review (slice 425
    D7) must see exactly the rules the graded tree carries, whoever runs it.
    """
    for candidate in PROJECT_RULES_CANDIDATES:
        directory = Path(cwd) / candidate
        if directory.is_dir():
            return directory
    return None


def resolve_rules_dir(
    cwd: str,
    config_rules_dir: str | None,
    cli_rules_dir: str | None,
) -> tuple[Path | None, RulesSource]:
    """Resolve the rules directory and report which source produced it.

    Priority: CLI flag > config > {cwd}/rules/ > {cwd}/.claude/rules/
    > ~/.config/squadron/rules/ > ~/.config/squadron/templates/ > None.

    Both project-local candidates report :attr:`RulesSource.PROJECT`: the
    question the source answers is *whose* rules these are, and the answer
    for either layout is the project's.
    """
    if cli_rules_dir is not None:
        p = Path(cli_rules_dir)
        return (p, RulesSource.FLAG) if p.is_dir() else (None, RulesSource.NONE)

    if config_rules_dir is None:
        config_val = get_config("rules_dir")
        if isinstance(config_val, str):
            config_rules_dir = config_val

    if config_rules_dir is not None:
        p = Path(config_rules_dir)
        return (p, RulesSource.CONFIG) if p.is_dir() else (None, RulesSource.NONE)

    project_dir = project_rules_dir(cwd)
    if project_dir is not None:
        return project_dir, RulesSource.PROJECT

    user_rules = Path.home() / ".config" / "squadron" / "rules"
    if user_rules.is_dir():
        return user_rules, RulesSource.USER

    # Tail position, appended rather than inserted: this branch is reachable
    # only where the resolver previously returned None, so every input that
    # resolved to a path before still resolves to the same one. User review
    # templates live beside user models and pipelines under ~/.config/squadron.
    user_templates = user_templates_dir()
    if user_templates.is_dir():
        return user_templates, RulesSource.TEMPLATE

    return None, RulesSource.NONE


def _read_rule(path: Path) -> str | None:
    """A rule file's stripped content, or None with a WARNING naming it when unreadable."""
    try:
        return path.read_text().strip()
    except OSError as exc:
        _logger.warning("Skipping unreadable rule file %s: %s", path, exc)
        return None


def _read_rules(rules_files: list[Path]) -> list[tuple[Path, str]]:
    """Each readable rules file with its content; unreadable ones are logged and left out."""
    return [(path, content) for path in rules_files if (content := _read_rule(path)) is not None]


def load_rules_content(rules_files: list[Path]) -> str:
    """Read and concatenate content of each rules file."""
    return RULES_SEPARATOR.join(content for _, content in _read_rules(rules_files))


def get_template_rules(template_name: str, rules_dir: Path) -> str | None:
    """Check for review.md and review-{template_name}.md in rules_dir.

    Returns concatenated content or None if neither exists.
    """
    candidates = [
        rules_dir / filename
        for filename in (f"review-{template_name}.md", "review.md")
        if (rules_dir / filename).is_file()
    ]
    parts = [content for _, content in _read_rules(candidates)]
    return RULES_SEPARATOR.join(parts) if parts else None


def extract_diff_paths(
    diff_ref: str,
    cwd: str,
    exclude_patterns: list[str] | None = None,
) -> list[str]:
    """Run ``git diff --name-only`` and return changed file paths.

    When *exclude_patterns* is provided, matching files are filtered out
    via git pathspec exclusions. Returns an empty list on git failure.
    """
    args = ["diff", "--name-only", diff_ref]
    if exclude_patterns:
        args.append("--")
        args.append(".")
        args.extend(f":!{p}" for p in exclude_patterns)
    # Through run_git rather than subprocess directly, so this call is bounded by
    # the same timeout as every other git invocation. A direct call here left the
    # unreachable-remote hang reachable through the one path that always runs.
    result = run_git(args, cwd=cwd)
    if result is not None and result.returncode == 0:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return []


@dataclass(frozen=True)
class ReviewRules:
    """Assembled review rules and the project rule files among them.

    ``language_rules`` names the rule files sent to every review and those matched to
    the files under review. It is written to review frontmatter as ``projectRules``
    (slice 935 D7).
    """

    content: str | None
    language_rules: list[str] = field(default_factory=list[str])


def _is_always_on(name: str, fm: RuleFrontmatter) -> bool:
    """Whether a rule file goes to every review: ``steps`` names review and it has no ``paths``.

    It is opt-in. A file with neither key (workflow notes, or a language file matched by
    its name) is not sent to every review.
    """
    return (
        fm.paths is None
        and fm.steps is not None
        and RuleStep.REVIEW in fm.steps
        and not is_review_template_rule(name)
    )


def guide_rules_dir(cwd: str) -> Path | None:
    """The installed guide's rules directory under *cwd*, ``None`` when no guide is installed."""
    directory = Path(cwd) / GUIDE_RULES_DIR
    return directory if directory.is_dir() else None


def _guide_always_on(
    guide_dir: Path | None, rules_dir: Path | None, exclude: Collection[str]
) -> list[Path]:
    """The guide's rule files sent to every review, less names the project's own rules use."""
    if guide_dir is None or guide_dir == rules_dir:
        return []
    return [
        guide_dir / name
        for name, fm in sorted(load_rules_frontmatter(guide_dir).items())
        if name not in exclude and _is_always_on(name, fm)
    ]


def load_review_rules(
    template_name: str,
    rules_dir: Path | None,
    file_paths: list[str] | None = None,
    manual_rules_content: str | None = None,
    cwd: str | None = None,
    guide_rules_dir: Path | None = None,
) -> ReviewRules:
    """Assemble review rules from all sources, in CLI-equivalent order.

    Combines, in order:
      1. Template rules (``review.md`` and ``review-{template_name}.md``)
      2. Manual override rules supplied by caller
      3. Rules sent to every review (``steps`` names ``review`` and the file has no
         ``paths``): the guide's from *guide_rules_dir*, then the project's. A project
         file replaces the guide file of the same name.
      4. Language-auto-detected rules matched against *file_paths*, limited to
         rules whose ``steps`` include ``review`` (slice 935 D3)

    ``content`` is ``None`` if no source produced anything. Single source of
    truth for both CLI and pipeline review paths — keeps the two in lockstep.
    """
    # Template-specific rules (prepended to manual content, per CLI order)
    rules_content: str | None = manual_rules_content
    if rules_dir is not None:
        template_rules = get_template_rules(template_name, rules_dir)
        if template_rules:
            rules_content = (
                template_rules
                if rules_content is None
                else f"{template_rules}{RULES_SEPARATOR}{rules_content}"
            )

    # Rules sent to every review (the guide's, then the project's), then the project
    # rules matching the files under review.
    project_rules: list[str] = []
    frontmatter = load_rules_frontmatter(rules_dir) if rules_dir is not None else {}
    always = sorted(name for name, fm in frontmatter.items() if _is_always_on(name, fm))
    selected = _guide_always_on(guide_rules_dir, rules_dir, exclude=frontmatter.keys())
    if rules_dir is not None:
        selected += [rules_dir / name for name in always]
        if file_paths:
            relevant = {
                name: fm
                for name, fm in frontmatter.items()
                if name not in always and RuleStep.REVIEW in effective_steps(fm)
            }
            selected += match_rules_files(file_paths, rules_dir, path_globs(relevant), cwd)
    if selected:
        loaded = _read_rules(selected)
        project_rules = [path.name for path, _ in loaded]
        project_content = RULES_SEPARATOR.join(content for _, content in loaded)
        if project_content:
            rules_content = (
                project_content
                if rules_content is None
                else f"{rules_content}{RULES_SEPARATOR}{project_content}"
            )

    return ReviewRules(content=rules_content, language_rules=project_rules)
