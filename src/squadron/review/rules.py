"""Rules file discovery, language detection, and content loading for reviews."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from squadron.config.manager import get_config

# Frontmatter YAML block at start of file
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_PATHS_RE = re.compile(r"^paths\s*:\s*\[(.+?)\]", re.MULTILINE)
_PATHS_LIST_RE = re.compile(r"^paths\s*:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)


def resolve_rules_dir(
    cwd: str,
    config_rules_dir: str | None,
    cli_rules_dir: str | None,
) -> Path | None:
    """Resolve the rules directory.

    Priority: CLI flag > config > {cwd}/rules/ > {cwd}/.claude/rules/
    > ~/.config/squadron/rules/ > None.
    """
    if cli_rules_dir is not None:
        p = Path(cli_rules_dir)
        return p if p.is_dir() else None

    if config_rules_dir is None:
        config_val = get_config("rules_dir")
        if isinstance(config_val, str):
            config_rules_dir = config_val

    if config_rules_dir is not None:
        p = Path(config_rules_dir)
        return p if p.is_dir() else None

    cwd_path = Path(cwd)
    for candidate in ("rules", ".claude/rules"):
        p = cwd_path / candidate
        if p.is_dir():
            return p

    user_rules = Path.home() / ".config" / "squadron" / "rules"
    if user_rules.is_dir():
        return user_rules

    return None


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


def detect_languages_from_paths(file_paths: list[str]) -> set[str]:
    """Extract extensions from file paths.

    Returns a set of extension strings (e.g. {'.py', '.ts'}).
    """
    extensions: set[str] = set()
    for path in file_paths:
        suffix = Path(path).suffix
        if suffix:
            extensions.add(suffix.lower())
    return extensions


def match_rules_files(
    extensions: set[str],
    rules_dir: Path,
    frontmatter: dict[str, list[str]],
) -> list[Path]:
    """Match extensions against glob patterns; return sorted list of matching paths."""
    matched: list[Path] = []
    for filename, patterns in frontmatter.items():
        for pattern in patterns:
            # Convert glob pattern extension to an extension string for matching
            pat_suffix = Path(pattern).suffix
            if pat_suffix and pat_suffix.lower() in extensions:
                matched.append(rules_dir / filename)
                break
            # Also try fnmatch on a synthetic path using each extension
            for ext in extensions:
                dummy = f"src/foo{ext}"
                if fnmatch.fnmatch(dummy, pattern):
                    matched.append(rules_dir / filename)
                    break
            else:
                continue
            break
    return sorted(set(matched))


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
