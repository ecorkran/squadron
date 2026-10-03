"""Per-target skill-pack layouts — where a pack lands and how to tell it is there.

A pack's source is the same for every target; what differs is the on-disk shape
the target's runtime reads. Claude Code reads flat markdown under
``<root>/<prefix>/`` or one dispatch file under ``<root>/sq/``. An agent-skills
runtime reads one directory per skill under a root shared with every other skill
source. Install, ``sq skills list`` and doctor all read this table rather than
re-deriving paths (D6).
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from squadron.documents.frontmatter import split_document
from squadron.skills.models import InstallResult, PackEntry, SkillSourceError
from squadron.skills.targets import CommandTarget, write_skill_dirs

#: Directory in a pack's source that holds its agents (Codex) skills (D2).
AGENTS_SOURCE_DIR = "agents"
SKILL_FILE = "SKILL.md"
_SKILL_NAME = re.compile(r"^[a-z0-9-]+$")
_LEADING_HTML_COMMENT = re.compile(r"^\s*<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class PackLayout:
    """How one target installs a pack and recognizes an installed one.

    ``install(pack_name, entry, source, root)`` copies from a resolved source
    directory into ``root``; ``installed_path(entry, root)`` returns the path that
    proves an install, or ``None``.
    """

    install: Callable[[str, PackEntry, Path, Path], InstallResult]
    installed_path: Callable[[PackEntry, Path], Path | None]


# ---------------------------------------------------------------------------
# Claude: flat markdown
# ---------------------------------------------------------------------------


def _claude_install(pack_name: str, entry: PackEntry, source: Path, root: Path) -> InstallResult:
    if entry.prefix is not None:
        return _claude_install_prefix(pack_name, entry.prefix, source, root)
    if entry.dispatch_file is not None:
        return _claude_install_dispatch(pack_name, entry.dispatch_file, source, root)
    # PackEntry validator guarantees exactly one — this is unreachable
    raise SkillSourceError(f"Pack '{pack_name}' has neither prefix nor dispatch_file.")


def _claude_install_prefix(pack_name: str, prefix: str, source: Path, root: Path) -> InstallResult:
    dest = root / prefix
    dest.mkdir(parents=True, exist_ok=True)

    files_written: list[str] = []
    for md_file in sorted(source.glob("*.md")):
        shutil.copy2(md_file, dest / md_file.name)
        files_written.append(md_file.name)

    return InstallResult(pack_name=pack_name, files_written=files_written, destination=dest)


def _claude_install_dispatch(
    pack_name: str, dispatch_file: str, source: Path, root: Path
) -> InstallResult:
    src_file = source / f"{dispatch_file}.md"
    if not src_file.exists():
        raise SkillSourceError(
            f"dispatch_file '{dispatch_file}.md' not found in source for pack '{pack_name}'."
        )

    dest_dir = root / "sq"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, dest_dir / f"{dispatch_file}.md")

    return InstallResult(
        pack_name=pack_name,
        files_written=[f"{dispatch_file}.md"],
        destination=dest_dir,
    )


def _claude_installed_path(entry: PackEntry, root: Path) -> Path | None:
    if entry.prefix is not None:
        dest = root / entry.prefix
        return dest if dest.is_dir() and any(dest.iterdir()) else None
    dest = root / "sq" / f"{entry.dispatch_file}.md"
    return dest if dest.is_file() else None


# ---------------------------------------------------------------------------
# Agents: one directory per skill
# ---------------------------------------------------------------------------


def dispatch_skill_name(dispatch_file: str) -> str:
    """The agents counterpart of ``/sq:<dispatch_file>``."""
    return f"sq-{dispatch_file}"


def _skill_frontmatter(skill_md: Path) -> dict[str, object] | None:
    """Parse a SKILL.md's frontmatter, tolerating a leading HTML comment.

    Forked skills carry an attribution comment above the fence (squadron's own
    ``analysis-tech-debt-audit`` does), so the fence need not be on line 1.
    """
    text = _LEADING_HTML_COMMENT.sub("", skill_md.read_text(encoding="utf-8"), count=1)
    split = split_document(text)
    if split is None:
        return None
    try:
        loaded = yaml.safe_load(split[1])
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    return {str(k): v for k, v in cast("dict[object, object]", loaded).items()}


def _skill_dir_problems(skill_dir: Path) -> list[str]:
    """D3's per-skill rules: a SKILL.md whose ``name`` is its directory, with a description."""
    label = f"{AGENTS_SOURCE_DIR}/{skill_dir.name}"
    skill_md = skill_dir / SKILL_FILE
    if not skill_md.is_file():
        return [f"{label}/{SKILL_FILE} is missing"]
    frontmatter = _skill_frontmatter(skill_md)
    if frontmatter is None:
        return [f"{label}/{SKILL_FILE} has no YAML frontmatter"]
    problems: list[str] = []
    name = frontmatter.get("name")
    if name != skill_dir.name:
        problems.append(f"{label}/{SKILL_FILE} declares name {name!r}; it must be {skill_dir.name!r}")
    description = frontmatter.get("description")
    if not (isinstance(description, str) and description.strip()):
        problems.append(f"{label}/{SKILL_FILE} has no description")
    return problems


def _naming_problems(entry: PackEntry, skill_dirs: list[Path]) -> list[str]:
    """D3's naming rules: the directory name is all that ties a skill to its pack."""
    problems: list[str] = []
    if entry.prefix is not None:
        for skill_dir in skill_dirs:
            name = skill_dir.name
            if not (name.startswith(f"{entry.prefix}-") and _SKILL_NAME.match(name)):
                problems.append(
                    f"{AGENTS_SOURCE_DIR}/{name} must be named {entry.prefix}-<name> "
                    "(lowercase a-z, 0-9 and hyphens)"
                )
        return problems
    expected = dispatch_skill_name(str(entry.dispatch_file))
    names = {d.name for d in skill_dirs}
    if expected not in names:
        problems.append(f"{AGENTS_SOURCE_DIR}/{expected}/ is missing")
    for name in sorted(names - {expected}):
        problems.append(
            f"{AGENTS_SOURCE_DIR}/{name} is not allowed; a dispatch_file pack ships only "
            f"{AGENTS_SOURCE_DIR}/{expected}/"
        )
    return problems


def validate_agents_source(pack_name: str, entry: PackEntry, source: Path) -> Path:
    """Check a pack's ``agents/`` tree against D2/D3; return it, or raise listing every problem."""
    agents_dir = source / AGENTS_SOURCE_DIR
    if not agents_dir.is_dir():
        raise SkillSourceError(
            f"Pack '{pack_name}' has no {AGENTS_SOURCE_DIR}/ directory at {source}; it ships "
            "no Codex content. Install it for Claude with --ide claude."
        )
    skill_dirs = sorted(d for d in agents_dir.iterdir() if d.is_dir())
    if not skill_dirs:
        problems = [f"{AGENTS_SOURCE_DIR}/ holds no skill directories"]
    else:
        problems = _naming_problems(entry, skill_dirs)
        for skill_dir in skill_dirs:
            problems.extend(_skill_dir_problems(skill_dir))
    if problems:
        listed = "\n".join(f"  - {problem}" for problem in problems)
        raise SkillSourceError(
            f"Pack '{pack_name}' has invalid Codex content at {agents_dir}:\n{listed}"
        )
    return agents_dir


def _agents_install(pack_name: str, entry: PackEntry, source: Path, root: Path) -> InstallResult:
    # Validate everything before writing anything: the root is shared with every
    # other skill source, so a half-written pack is someone else's clutter.
    agents_dir = validate_agents_source(pack_name, entry, source)
    files_written = write_skill_dirs(agents_dir, root)
    return InstallResult(pack_name=pack_name, files_written=files_written, destination=root)


def _agents_installed_path(entry: PackEntry, root: Path) -> Path | None:
    if entry.prefix is not None:
        skill_files = sorted(root.glob(f"{entry.prefix}-*/{SKILL_FILE}"))
        return skill_files[0] if skill_files else None
    skill_md = root / dispatch_skill_name(str(entry.dispatch_file)) / SKILL_FILE
    return skill_md if skill_md.is_file() else None


PACK_LAYOUTS: dict[CommandTarget, PackLayout] = {
    CommandTarget.CLAUDE: PackLayout(install=_claude_install, installed_path=_claude_installed_path),
    CommandTarget.AGENTS: PackLayout(install=_agents_install, installed_path=_agents_installed_path),
}

# A new target without a layout is a missing install path, not a default.
assert set(PACK_LAYOUTS) == set(CommandTarget), "every CommandTarget needs a PackLayout"
