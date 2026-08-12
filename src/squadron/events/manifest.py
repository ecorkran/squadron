"""Binding manifest loader — resolves events.yaml (design D6).

Resolution order: project (`{cwd}/project-documents/user/events.yaml`) then
user (`~/.config/squadron/events.yaml`), first found wins, no merge —
mirroring ``pipeline/loader.py:_search_dirs``. Built-in bindings are always
active unless named in ``disable:``; effective bindings are defaults (minus
disabled) followed by manifest bindings in file order.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from squadron.events import EventType
from squadron.events.schema import parse_manifest_yaml

if TYPE_CHECKING:
    from squadron.events.protocol import EventAction

_logger = logging.getLogger(__name__)

_PROJECT_MANIFEST_REL = Path("project-documents/user/events.yaml")
_USER_MANIFEST = Path.home() / ".config" / "squadron" / "events.yaml"


@dataclass(frozen=True)
class Binding:
    """One action bound to one event, with its params."""

    event: EventType
    action: str
    params: dict[str, object]
    source: str  # "built-in" or the manifest file path


@dataclass(frozen=True)
class EventManifest:
    """Resolved manifest: plugins to import and effective bindings."""

    plugins: tuple[str, ...]
    bindings: tuple[Binding, ...]
    disabled: frozenset[str]
    manifest_path: Path | None


class ManifestError(ValueError):
    """Raised when a manifest fails to parse or validate."""


#: Built-in bindings, always active unless named in `disable:`. Order
#: expresses the 909-before-911 contract on POST_ACTION.
DEFAULT_BINDINGS: tuple[Binding, ...] = (
    Binding(event=EventType.COMMIT, action="squadron.frontmatter-gate", params={}, source="built-in"),
    Binding(
        event=EventType.POST_ACTION, action="squadron.dispatch-artifact", params={}, source="built-in"
    ),
    Binding(
        event=EventType.POST_ACTION, action="squadron.revision-stamp", params={}, source="built-in"
    ),
)


def _resolve_manifest_path(
    *,
    cwd: str | None = None,
    project_path: Path | None = None,
    user_path: Path | None = None,
) -> Path | None:
    """Return the first manifest file found, or None (defaults only)."""
    project = project_path if project_path is not None else (Path(cwd or ".") / _PROJECT_MANIFEST_REL)
    if project.is_file():
        return project

    user = user_path if user_path is not None else _USER_MANIFEST
    if user.is_file():
        return user

    return None


def load_manifest(
    *,
    cwd: str | None = None,
    project_path: Path | None = None,
    user_path: Path | None = None,
) -> EventManifest:
    """Load and resolve the effective event manifest.

    Raises:
        ManifestError: On malformed YAML content — unknown event key,
            missing action name, or (via ``resolve_bindings``) an unknown
            action name. Never at fire time.
    """
    manifest_path = _resolve_manifest_path(cwd=cwd, project_path=project_path, user_path=user_path)

    if manifest_path is None:
        return EventManifest(
            plugins=(), bindings=DEFAULT_BINDINGS, disabled=frozenset(), manifest_path=None
        )

    with open(manifest_path) as f:
        loaded: Any = yaml.safe_load(f) or {}

    try:
        schema = parse_manifest_yaml(loaded, manifest_path=str(manifest_path))
    except ValueError as exc:
        raise ManifestError(str(exc)) from exc

    plugins = tuple(schema.plugins)
    disabled = frozenset(schema.disable)

    manifest_bindings: list[Binding] = [
        Binding(
            event=EventType(event_key),
            action=entry.action,
            params=entry.params,
            source=str(manifest_path),
        )
        for event_key, entries in schema.bindings.items()
        for entry in entries
    ]

    for binding in DEFAULT_BINDINGS:
        if binding.action in disabled:
            _logger.debug("%s: disabled by %s", binding.action, manifest_path)

    effective = tuple(b for b in DEFAULT_BINDINGS if b.action not in disabled) + tuple(
        manifest_bindings
    )

    return EventManifest(
        plugins=plugins,
        bindings=effective,
        disabled=disabled,
        manifest_path=manifest_path,
    )


def resolve_bindings(
    manifest: EventManifest,
    registered_names: list[str],
    get_action: Callable[[str], EventAction],
) -> None:
    """Validate every binding names a registered action that supports its event.

    Raises:
        ManifestError: Naming the manifest source, the offending action or
            event name, and (for an unknown action) the full list of
            registered actions — resolved once at load time, never at
            fire time.
    """
    for binding in manifest.bindings:
        if binding.action not in registered_names:
            raise ManifestError(
                f"{binding.source}: unknown action '{binding.action}' in binding for "
                f"'{binding.event.value}'. Registered actions: {registered_names}"
            )
        action = get_action(binding.action)
        if binding.event not in action.events:
            raise ManifestError(
                f"{binding.source}: action '{binding.action}' does not support event "
                f"'{binding.event.value}' (supports: {sorted(e.value for e in action.events)})"
            )
