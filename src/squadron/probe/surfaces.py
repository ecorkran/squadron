"""Per-surface probe specs: the contract strings and how each surface is detected.

One ``SurfaceSpec`` per ``CommandTarget``. The contract strings (``entry``,
``concept``, ``graph_build``) are defined here and nowhere else; the contract
document is their source of truth.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from squadron.skills.dispatcher import dispatcher_skills
from squadron.skills.targets import DELIVERIES, CommandTarget

logger = logging.getLogger(__name__)

UNDERSTAND_SKILL = "understand"
CLAUDE_SKILL_FILE = Path("analysis") / "understand.md"
CLAUDE_DISPATCHER_FILE = Path("sq") / "analysis.md"
CODEX_SKILL_FILE = Path("analysis-understand") / "SKILL.md"

PLUGIN_NAME = "understand-anything"
CLAUDE_PLUGINS_FILE = Path(".claude/plugins/installed_plugins.json")
CODEX_PLUGIN_SKILL_FILE = Path("understand") / "SKILL.md"
USER_PLUGIN_SCOPE = "user"


@dataclass(frozen=True)
class SurfaceSpec:
    """What the probe reports for one agent surface, and how it detects the skill."""

    key: str
    entry: str
    concept: str
    graph_build: str
    #: Given the project root; None means the probe could not determine it.
    analysis_skill_installed: Callable[[Path], bool | None]
    #: Given the project root; None means the probe could not determine it.
    understand_plugin_installed: Callable[[Path], bool | None]


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


def _codex_plugin_installed(project_root: Path) -> bool | None:
    skills_root = DELIVERIES[CommandTarget.AGENTS].resolve_root(local=False)
    return (skills_root / CODEX_PLUGIN_SKILL_FILE).is_file()


def _plugin_entry_applies(entry: dict[str, object], project_root: Path) -> bool:
    """A user-scope entry, or one whose ``projectPath`` is this project."""
    if entry.get("scope") == USER_PLUGIN_SCOPE:
        return True
    project_path = entry.get("projectPath")
    return isinstance(project_path, str) and Path(project_path).resolve() == project_root.resolve()


def _claude_plugin_installed(project_root: Path) -> bool | None:
    plugins_file = (Path("~") / CLAUDE_PLUGINS_FILE).expanduser()
    if not plugins_file.is_file():
        return False
    try:
        data = json.loads(plugins_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        # An unreadable or malformed plugin registry means unknown, not a probe failure.
        logger.warning("understand_plugin_installed unknown: cannot read %s: %s", plugins_file, error)
        return None
    plugins = cast(dict[str, object], data).get("plugins") if isinstance(data, dict) else None
    if not isinstance(plugins, dict) or not all(
        isinstance(entries, list) for entries in cast(dict[str, object], plugins).values()
    ):
        logger.warning(
            "understand_plugin_installed unknown: %s has no 'plugins' object of lists", plugins_file
        )
        return None
    for key, entries in cast(dict[str, list[dict[str, object]]], plugins).items():
        if key.split("@")[0] == PLUGIN_NAME and any(
            _plugin_entry_applies(entry, project_root) for entry in entries
        ):
            return True
    return False


SURFACES: dict[CommandTarget, SurfaceSpec] = {
    CommandTarget.CLAUDE: SurfaceSpec(
        key="claude-code",
        entry="/sq:analysis understand",
        concept="/sq:analysis understand concept",
        graph_build="/understand",
        analysis_skill_installed=_claude_skill_installed,
        understand_plugin_installed=_claude_plugin_installed,
    ),
    CommandTarget.AGENTS: SurfaceSpec(
        key="codex",
        entry="analysis-understand",
        concept="analysis-understand concept",
        graph_build="understand",
        analysis_skill_installed=_codex_skill_installed,
        understand_plugin_installed=_codex_plugin_installed,
    ),
}

# A new target without a surface spec is a missing probe entry, not a default.
assert set(SURFACES) == set(CommandTarget), "every CommandTarget needs a SurfaceSpec"
