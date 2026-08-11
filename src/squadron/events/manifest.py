"""Binding manifest loader — resolves events.yaml (design D6).

Resolution order: project (`{cwd}/project-documents/user/events.yaml`) then
user (`~/.config/squadron/events.yaml`), first found wins, no merge —
mirroring ``pipeline/loader.py:_search_dirs``. Built-in bindings are always
active unless named in ``disable:``; effective bindings are defaults (minus
disabled) followed by manifest bindings in file order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import yaml

from squadron.events import EventType

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


def _parse_event_key(raw_key: object, manifest_path: Path) -> EventType:
    if not isinstance(raw_key, str):
        raise ManifestError(f"{manifest_path}: binding key {raw_key!r} must be a string event name")
    try:
        return EventType(raw_key)
    except ValueError as exc:
        valid = [member.value for member in EventType]
        raise ManifestError(
            f"{manifest_path}: unknown event '{raw_key}' in bindings — valid events: {valid}"
        ) from exc


def _parse_binding_entry(raw_entry: object, event: EventType, manifest_path: Path) -> Binding:
    if not isinstance(raw_entry, dict):
        raise ManifestError(
            f"{manifest_path}: binding entry for '{event.value}' must be a mapping with 'action'"
        )
    entry = cast(dict[str, Any], raw_entry)
    action = entry.get("action")
    if not isinstance(action, str) or not action:
        raise ManifestError(f"{manifest_path}: binding entry for '{event.value}' is missing 'action'")
    params_raw = entry.get("params", {})
    params = cast(dict[str, object], params_raw) if isinstance(params_raw, dict) else {}
    return Binding(event=event, action=action, params=params, source=str(manifest_path))


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

    if not isinstance(loaded, dict):
        raise ManifestError(f"{manifest_path}: top level must be a mapping")
    raw_dict = cast(dict[str, Any], loaded)

    plugins_raw: Any = raw_dict.get("plugins", []) or []
    if not isinstance(plugins_raw, list):
        raise ManifestError(f"{manifest_path}: 'plugins' must be a list of module paths")
    plugins = tuple(str(p) for p in cast(list[Any], plugins_raw))

    disable_raw: Any = raw_dict.get("disable", []) or []
    if not isinstance(disable_raw, list):
        raise ManifestError(f"{manifest_path}: 'disable' must be a list of action names")
    disabled = frozenset(str(d) for d in cast(list[Any], disable_raw))

    manifest_bindings: list[Binding] = []
    bindings_raw: Any = raw_dict.get("bindings", {}) or {}
    if not isinstance(bindings_raw, dict):
        raise ManifestError(f"{manifest_path}: 'bindings' must be a mapping of event -> entries")
    for raw_key, raw_entries in cast(dict[Any, Any], bindings_raw).items():
        event = _parse_event_key(raw_key, manifest_path)
        if not isinstance(raw_entries, list):
            raise ManifestError(f"{manifest_path}: bindings['{raw_key}'] must be a list")
        for raw_entry in cast(list[Any], raw_entries):
            manifest_bindings.append(_parse_binding_entry(raw_entry, event, manifest_path))

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


def resolve_bindings(manifest: EventManifest, registered_names: list[str]) -> None:
    """Validate every binding's action name is registered.

    Raises:
        ManifestError: Naming the manifest source, the unknown action name,
            and the full list of registered actions — resolved once at
            load time, never at fire time.
    """
    for binding in manifest.bindings:
        if binding.action not in registered_names:
            raise ManifestError(
                f"{binding.source}: unknown action '{binding.action}' in binding for "
                f"'{binding.event.value}'. Registered actions: {registered_names}"
            )
