"""Per-surface probe specs: the contract strings and how each surface is detected.

One ``SurfaceSpec`` per ``CommandTarget``. The contract strings (``entry``,
``concept``, ``graph_build``) are defined here and nowhere else; the contract
document is their source of truth.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from squadron.skills.dispatcher import dispatcher_skills
from squadron.skills.targets import DELIVERIES, CommandTarget

logger = logging.getLogger(__name__)

UNDERSTAND_SKILL = "understand"
CLAUDE_SKILL_FILE = Path("analysis") / "understand.md"
CLAUDE_DISPATCHER_FILE = Path("sq") / "analysis.md"
CODEX_SKILL_FILE = Path("analysis-understand") / "SKILL.md"


@dataclass(frozen=True)
class SurfaceSpec:
    """What the probe reports for one agent surface, and how it detects the skill."""

    key: str
    entry: str
    concept: str
    graph_build: str
    #: Given the project root; None means the probe could not determine it.
    analysis_skill_installed: Callable[[Path], bool | None]


def _install_roots(target: CommandTarget, project_root: Path) -> list[Path]:
    """Machine root and project root for a target.

    ``resolve_root(local=True)`` reads ``Path.cwd()``, which is wrong when
    ``sq probe`` runs from a subdirectory, so the project root is joined here.
    """
    delivery = DELIVERIES[target]
    return [delivery.resolve_root(local=False), project_root / delivery.local_root]


def _any_scope(results: list[bool | None]) -> bool | None:
    """True if any scope has it; else None if any scope is unknown; else False."""
    if True in results:
        return True
    if None in results:
        return None
    return False


def _claude_scope_has_skill(commands_root: Path) -> bool | None:
    skill_file = commands_root / CLAUDE_SKILL_FILE
    dispatcher_file = commands_root / CLAUDE_DISPATCHER_FILE
    if not skill_file.is_file() or not dispatcher_file.is_file():
        return False
    try:
        skills = dispatcher_skills(dispatcher_file.read_text(encoding="utf-8"))
    except OSError as error:
        # An unreadable dispatcher means the install state is unknown, not a probe failure.
        logger.warning("analysis_skill_installed unknown: cannot read %s: %s", dispatcher_file, error)
        return None
    if skills is None:
        logger.warning(
            "analysis_skill_installed unknown: %s has no 'Valid skills:' line", dispatcher_file
        )
        return None
    return UNDERSTAND_SKILL in skills


def _claude_skill_installed(project_root: Path) -> bool | None:
    roots = _install_roots(CommandTarget.CLAUDE, project_root)
    return _any_scope([_claude_scope_has_skill(root) for root in roots])


def _codex_skill_installed(project_root: Path) -> bool | None:
    roots = _install_roots(CommandTarget.AGENTS, project_root)
    return _any_scope([(root / CODEX_SKILL_FILE).is_file() for root in roots])


SURFACES: dict[CommandTarget, SurfaceSpec] = {
    CommandTarget.CLAUDE: SurfaceSpec(
        key="claude-code",
        entry="/sq:analysis understand",
        concept="/sq:analysis understand concept",
        graph_build="/understand",
        analysis_skill_installed=_claude_skill_installed,
    ),
    CommandTarget.AGENTS: SurfaceSpec(
        key="codex",
        entry="analysis-understand",
        concept="analysis-understand concept",
        graph_build="understand",
        analysis_skill_installed=_codex_skill_installed,
    ),
}

# A new target without a surface spec is a missing probe entry, not a default.
assert set(SURFACES) == set(CommandTarget), "every CommandTarget needs a SurfaceSpec"
