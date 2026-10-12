"""Rule-file frontmatter parsing and path-glob matching.

Shared by review rule loading and dispatch rule selection. Imports nothing
from ``squadron.review`` or ``squadron.pipeline``.
"""

from __future__ import annotations

import re
from pathlib import Path

# Frontmatter YAML block at start of file
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_PATHS_RE = re.compile(r"^paths\s*:\s*\[(.+?)\]", re.MULTILINE)
_PATHS_LIST_RE = re.compile(r"^paths\s*:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)


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
