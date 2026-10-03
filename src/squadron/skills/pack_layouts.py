"""Per-target skill-pack layouts — where a pack lands and how to tell it is there.

A pack's source is the same for every target; what differs is the on-disk shape
the target's runtime reads. Claude Code reads flat markdown under
``<root>/<prefix>/`` or one dispatch file under ``<root>/sq/``. An agent-skills
runtime reads one directory per skill under a root shared with every other skill
source. Install, ``sq skills list`` and doctor all read this table rather than
re-deriving paths (D6).
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from squadron.skills.models import InstallResult, PackEntry, SkillSourceError
from squadron.skills.targets import CommandTarget


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


def _agents_install(pack_name: str, entry: PackEntry, source: Path, root: Path) -> InstallResult:
    raise SkillSourceError(f"Pack '{pack_name}': the agents layout is not implemented yet.")


def _agents_installed_path(entry: PackEntry, root: Path) -> Path | None:
    return None


PACK_LAYOUTS: dict[CommandTarget, PackLayout] = {
    CommandTarget.CLAUDE: PackLayout(install=_claude_install, installed_path=_claude_installed_path),
    CommandTarget.AGENTS: PackLayout(install=_agents_install, installed_path=_agents_installed_path),
}

# A new target without a layout is a missing install path, not a default.
assert set(PACK_LAYOUTS) == set(CommandTarget), "every CommandTarget needs a PackLayout"
