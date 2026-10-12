"""Discovery of the project's conventions file (AGENTS.md first, D2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from squadron.project_rules.errors import ProjectRulesError


class ConventionsSource(StrEnum):
    """Where a run's project conventions came from.

    Written to review frontmatter as ``conventionsSource`` and to dispatch
    metadata as ``project_rules.conventions``, so the values are part of the
    artifact contract and read back by consumers.
    """

    AGENTS_MD = "AGENTS.md"
    CLAUDE_MD = "CLAUDE.md"
    DOT_CLAUDE_CLAUDE_MD = ".claude/CLAUDE.md"
    #: The provider loads the project's files itself (Claude SDK); squadron injected nothing.
    SDK_NATIVE = "sdk-native"
    NONE = "none"


#: Candidate order: the first one present is the conventions file (D2).
CONVENTIONS_CANDIDATES: tuple[ConventionsSource, ...] = (
    ConventionsSource.AGENTS_MD,
    ConventionsSource.CLAUDE_MD,
    ConventionsSource.DOT_CLAUDE_CLAUDE_MD,
)


class ConventionsReadError(ProjectRulesError):
    """A conventions file exists but can't be read. Never skipped in favor of the next."""


@dataclass(frozen=True)
class ConventionsFile:
    source: ConventionsSource
    path: Path
    content: str


@dataclass(frozen=True)
class ConventionsLookup:
    """The chosen conventions file (or ``None``) and the other candidates present."""

    chosen: ConventionsFile | None
    skipped: list[ConventionsSource] = field(default_factory=list[ConventionsSource])


def _present(path: Path) -> bool:
    # is_symlink catches a broken link, which exists() reports as absent.
    return path.exists() or path.is_symlink()


def find_conventions(root: Path) -> ConventionsLookup:
    """Pick the conventions file under ``root``: AGENTS.md, CLAUDE.md, .claude/CLAUDE.md.

    The content is returned as written (``@path`` lines are not resolved, #205).
    A candidate that is present but unreadable raises :class:`ConventionsReadError`
    naming the path.
    """
    present = [source for source in CONVENTIONS_CANDIDATES if _present(root / source.value)]
    if not present:
        return ConventionsLookup(chosen=None)
    source = present[0]
    path = root / source.value
    try:
        content = path.read_text()
    except OSError as exc:
        raise ConventionsReadError(f"Cannot read conventions file {path}: {exc}") from exc
    return ConventionsLookup(
        chosen=ConventionsFile(source=source, path=path, content=content),
        skipped=present[1:],
    )
