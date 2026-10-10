"""Rules file discovery, language detection, and content loading for reviews."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from squadron.config.manager import get_config
from squadron.review.git_utils import run_git
from squadron.review.templates import user_templates_dir

# Frontmatter YAML block at start of file
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_PATHS_RE = re.compile(r"^paths\s*:\s*\[(.+?)\]", re.MULTILINE)
_PATHS_LIST_RE = re.compile(r"^paths\s*:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)


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


def _parse_frontmatter_paths(content: str) -> list[str] | None:
    """Extract the paths list from YAML frontmatter, or None if not present."""
    fm_match = _FRONTMATTER_RE.match(content)
    if fm_match is None:
        return None
    fm_body = fm_match.group(1)

    # Inline list: paths: [**/*.py, **/*.pyi]
    inline = _PATHS_RE.search(fm_body)
    if inline:
        raw = inline.group(1)
        parts = [p.strip().strip("\"'") for p in raw.split(",")]
        return [p for p in parts if p]

    # Block list:
    # paths:
    #   - **/*.py
    block = _PATHS_LIST_RE.search(fm_body)
    if block:
        raw = block.group(1)
        items = [
            line.strip().lstrip("- ").strip().strip("\"'")
            for line in raw.splitlines()
            if line.strip().startswith("-")
        ]
        return [i for i in items if i]

    return None


def _filename_to_glob(stem: str) -> list[str]:
    """Derive glob patterns from a rules filename (e.g. 'python' → ['**/*.py'])."""
    _STEM_TO_EXTS: dict[str, list[str]] = {
        "python": ["**/*.py", "**/*.pyi"],
        "typescript": ["**/*.ts", "**/*.tsx"],
        "javascript": ["**/*.js", "**/*.jsx", "**/*.mjs", "**/*.cjs"],
        "rust": ["**/*.rs"],
        "go": ["**/*.go"],
        "java": ["**/*.java"],
        "ruby": ["**/*.rb"],
        "csharp": ["**/*.cs"],
        "cpp": ["**/*.cpp", "**/*.cc", "**/*.cxx", "**/*.h", "**/*.hpp"],
        "c": ["**/*.c", "**/*.h"],
        "shell": ["**/*.sh", "**/*.bash"],
        "yaml": ["**/*.yaml", "**/*.yml"],
        "toml": ["**/*.toml"],
        "json": ["**/*.json"],
        "markdown": ["**/*.md"],
    }
    return _STEM_TO_EXTS.get(stem.lower(), [f"**/*.{stem.lower()}"])


def load_rules_frontmatter(rules_dir: Path) -> dict[str, list[str]]:
    """Scan rules_dir, parse YAML frontmatter paths field from each .md file.

    Returns {filename: [glob_patterns]}.
    Files without a paths field use filename-based fallback.
    """
    result: dict[str, list[str]] = {}
    for md_file in sorted(rules_dir.glob("*.md")):
        try:
            content = md_file.read_text()
        except OSError:
            continue
        paths = _parse_frontmatter_paths(content)
        if paths is None:
            paths = _filename_to_glob(md_file.stem)
        result[md_file.name] = paths
    return result


# First line of an extensionless script that makes it a shell script.
_SHELL_SHEBANG_RE = re.compile(r"^#!\s*(?:/usr/bin/env\s+(?:-\S+\s+)*)?(?:\S*/)?(?:ba)?sh\b")
# Extension a shebang-detected shell script is matched as, so it meets the same
# frontmatter globs as a file literally named ``*.sh``.
_SHELL_SCRIPT_SUFFIX = ".sh"


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a rules-frontmatter glob to a full-path regex.

    ``**/`` spans any directories (including none), ``*`` and ``?`` stay inside
    one path segment. Matching is case-insensitive, as extension matching was.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z", re.IGNORECASE)


def _is_shell_script(path: Path) -> bool:
    """True when ``path`` has no extension and starts with a bash or sh shebang."""
    if path.suffix:
        return False
    try:
        with path.open("r", errors="replace") as handle:
            first_line = handle.readline()
    except OSError:
        # Deleted in the diff or unreadable: nothing to sniff, so it is not a script.
        return False
    return _SHELL_SHEBANG_RE.match(first_line) is not None


def _paths_to_match(file_paths: list[str], cwd: str | None) -> list[str]:
    """``file_paths`` plus, for each shebang shell script, its ``.sh`` stand-in."""
    root = Path(cwd) if cwd else Path(".")
    paths = [p.replace("\\", "/") for p in file_paths]
    paths += [f"{p}{_SHELL_SCRIPT_SUFFIX}" for p in paths if _is_shell_script(root / p)]
    return paths


def match_rules_files(
    file_paths: list[str],
    rules_dir: Path,
    frontmatter: dict[str, list[str]],
    cwd: str | None = None,
) -> list[Path]:
    """Return the rules files whose ``paths`` globs match any of ``file_paths``.

    Globs match the whole path, so ``**/.gitlab-ci.yml`` does not pick up
    other ``.yml`` files. Extensionless files with a bash/sh shebang (read
    relative to ``cwd``) match as if named ``*.sh``.
    """
    candidates = _paths_to_match(file_paths, cwd)
    matched: set[Path] = set()
    for filename, patterns in frontmatter.items():
        regexes = [_glob_to_regex(pattern) for pattern in patterns]
        if any(rx.match(path) for rx in regexes for path in candidates):
            matched.add(rules_dir / filename)
    return sorted(matched)


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
