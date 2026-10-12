"""Rule-file frontmatter parsing and path-glob matching.

Shared by review rule loading and dispatch rule selection. Imports nothing
from ``squadron.review`` or ``squadron.pipeline``.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

logger = logging.getLogger(__name__)

# Frontmatter YAML block at start of file
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

_PATHS_KEY = "paths"
_STEPS_KEY = "steps"


class RuleStep(StrEnum):
    """Step kinds a rule file can declare itself relevant to (``steps`` key)."""

    DESIGN = "design"
    TASKS = "tasks"
    IMPLEMENT = "implement"
    REVIEW = "review"
    DISPATCH = "dispatch"


@dataclass(frozen=True)
class RuleFrontmatter:
    """Selection keys parsed from one rule file. ``None`` means the key is absent."""

    paths: list[str] | None
    steps: frozenset[RuleStep] | None


def _clean_item(raw: str) -> str:
    return raw.strip().strip("\"'")


def _parse_list_field(fm_body: str, key: str) -> list[str] | None:
    """Read ``key`` as an inline list, a block list, or a bare scalar; None if absent."""
    name = re.escape(key)
    # Inline list: paths: [**/*.py, **/*.pyi]
    inline = re.search(rf"^{name}\s*:\s*\[(.*?)\]", fm_body, re.MULTILINE)
    if inline:
        return [item for part in inline.group(1).split(",") if (item := _clean_item(part))]

    # Block list:
    # paths:
    #   - **/*.py
    block = re.search(rf"^{name}\s*:\s*\n((?:\s*-\s*.+\n?)+)", fm_body, re.MULTILINE)
    if block:
        items = [
            _clean_item(line.strip().lstrip("- "))
            for line in block.group(1).splitlines()
            if line.strip().startswith("-")
        ]
        return [i for i in items if i]

    # Bare scalar: steps: implement (comma-separated values accepted)
    scalar = re.search(rf"^{name}\s*:[ \t]*(\S.*?)\s*$", fm_body, re.MULTILINE)
    if scalar:
        return [item for part in scalar.group(1).split(",") if (item := _clean_item(part))]

    return None


def _parse_steps(values: list[str], filename: str) -> frozenset[RuleStep]:
    """Map ``steps`` values to :class:`RuleStep`; an unknown value raises (D3)."""
    steps: set[RuleStep] = set()
    for value in values:
        try:
            steps.add(RuleStep(value.lower()))
        except ValueError:
            allowed = ", ".join(step.value for step in RuleStep)
            raise ValueError(
                f"Rule file {filename}: unknown steps value {value!r} (allowed: {allowed})"
            ) from None
    return frozenset(steps)


def parse_rule_frontmatter(content: str, filename: str) -> RuleFrontmatter:
    """Parse ``paths`` and ``steps`` from one rule file's content.

    Layout is read leniently (inline, block, or scalar lists; any indent).
    Values are strict: an unknown ``steps`` value raises ``ValueError`` naming
    ``filename`` and the value.
    """
    fm_match = _FRONTMATTER_RE.match(content)
    if fm_match is None:
        return RuleFrontmatter(paths=None, steps=None)
    fm_body = fm_match.group(1)
    raw_steps = _parse_list_field(fm_body, _STEPS_KEY)
    return RuleFrontmatter(
        paths=_parse_list_field(fm_body, _PATHS_KEY),
        steps=None if raw_steps is None else _parse_steps(raw_steps, filename),
    )


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


def load_rules_frontmatter(rules_dir: Path) -> dict[str, RuleFrontmatter]:
    """Scan rules_dir and parse the frontmatter of each .md file.

    Returns ``{filename: RuleFrontmatter}``. An unreadable file logs a WARNING
    naming it and is left out.
    """
    result: dict[str, RuleFrontmatter] = {}
    for md_file in sorted(rules_dir.glob("*.md")):
        try:
            content = md_file.read_text()
        except OSError as exc:
            logger.warning("Skipping unreadable rule file %s: %s", md_file, exc)
            continue
        result[md_file.name] = parse_rule_frontmatter(content, md_file.name)
    return result


def path_globs(frontmatter: dict[str, RuleFrontmatter]) -> dict[str, list[str]]:
    """Each file's ``paths`` globs, or globs derived from its filename when absent.

    The filename fallback (``python.md`` → ``**/*.py``) is what review
    language-rule matching has always used.
    """
    return {
        name: fm.paths if fm.paths is not None else _filename_to_glob(Path(name).stem)
        for name, fm in frontmatter.items()
    }


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
