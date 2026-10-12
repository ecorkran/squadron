"""Rules file discovery, language detection, and content loading for reviews."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from squadron.config.manager import get_config
from squadron.project_rules.frontmatter import load_rules_frontmatter, match_rules_files
from squadron.review.git_utils import run_git
from squadron.review.templates import user_templates_dir


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

    cwd_path = Path(cwd)
    for candidate in ("rules", ".claude/rules"):
        p = cwd_path / candidate
        if p.is_dir():
            return p, RulesSource.PROJECT

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


def load_rules_content(rules_files: list[Path]) -> str:
    """Read and concatenate content of each rules file."""
    parts: list[str] = []
    for path in rules_files:
        try:
            parts.append(path.read_text().strip())
        except OSError:
            continue
    return "\n\n---\n\n".join(parts)


def get_template_rules(template_name: str, rules_dir: Path) -> str | None:
    """Check for review.md and review-{template_name}.md in rules_dir.

    Returns concatenated content or None if neither exists.
    """
    parts: list[str] = []
    for filename in (f"review-{template_name}.md", "review.md"):
        path = rules_dir / filename
        if path.is_file():
            try:
                parts.append(path.read_text().strip())
            except OSError:
                pass
    return "\n\n---\n\n".join(parts) if parts else None


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


def load_review_rules(
    template_name: str,
    rules_dir: Path | None,
    file_paths: list[str] | None = None,
    manual_rules_content: str | None = None,
    cwd: str | None = None,
) -> str | None:
    """Assemble review rules from all sources, in CLI-equivalent order.

    Combines, in order:
      1. Template rules (``review.md`` and ``review-{template_name}.md``)
      2. Manual override rules supplied by caller
      3. Language-auto-detected rules matched against *file_paths*

    Returns the concatenated content, or ``None`` if no source produced
    anything. Single source of truth for both CLI and pipeline review
    paths — keeps the two in lockstep.
    """
    # Template-specific rules (prepended to manual content, per CLI order)
    rules_content: str | None = manual_rules_content
    if rules_dir is not None:
        template_rules = get_template_rules(template_name, rules_dir)
        if template_rules:
            rules_content = (
                template_rules
                if rules_content is None
                else f"{template_rules}\n\n---\n\n{rules_content}"
            )

    # Language auto-detection from changed/target files
    if rules_dir is not None and file_paths:
        frontmatter = load_rules_frontmatter(rules_dir)
        auto_files = match_rules_files(file_paths, rules_dir, frontmatter, cwd)
        auto_content = load_rules_content(auto_files)
        if auto_content:
            rules_content = (
                auto_content if rules_content is None else f"{rules_content}\n\n---\n\n{auto_content}"
            )

    return rules_content
