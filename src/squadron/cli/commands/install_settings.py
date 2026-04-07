"""Settings.json merge helpers for the PreCompact hook install/uninstall.

Squadron owns a single entry in ``.claude/settings.json`` identified by a
``_managed_by: "squadron"`` marker inside its nested ``hooks[*]`` command.
The merge helpers in this module read, write, and remove that entry
without touching any user-authored or third-party hook entries.

On corrupt JSON the loader raises ``RuntimeError`` rather than silently
overwriting the file — this is the one place in the installer where we
surface a hard error instead of being lenient.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast


def settings_json_path(target_root: Path) -> Path:
    """Return ``<target_root>/.claude/settings.json``."""
    return target_root / ".claude" / "settings.json"


def _load_settings(path: Path) -> dict[str, object]:
    """Load the settings.json file as a dict, or ``{}`` if missing.

    Raises:
        RuntimeError: if the file exists but cannot be parsed as JSON.
    """
    if not path.is_file():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Refusing to overwrite corrupt settings.json at {path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise RuntimeError(
            f"Refusing to overwrite settings.json at {path}: top-level is not an object"
        )
    return cast(dict[str, object], data)


def _save_settings(path: Path, data: dict[str, object]) -> None:
    """Write ``data`` to ``path`` as pretty-printed JSON with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# squadron entry shape and identification
# ---------------------------------------------------------------------------


def _squadron_entry() -> dict[str, object]:
    """Return a fresh copy of the squadron-managed PreCompact entry."""
    return {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": "sq _precompact-hook",
                "_managed_by": "squadron",
            }
        ],
    }


def _is_squadron_entry(entry: object) -> bool:
    """Return True if ``entry`` is a squadron-managed PreCompact entry.

    Safe against unexpected shapes: a missing or non-dict entry, missing
    ``hooks`` list, or non-dict inner hook all yield ``False``.
    """
    if not isinstance(entry, dict):
        return False
    entry_dict = cast(dict[str, object], entry)
    inner = entry_dict.get("hooks")
    if not isinstance(inner, list):
        return False
    for hook in cast(list[object], inner):
        if isinstance(hook, dict):
            hook_dict = cast(dict[str, object], hook)
            if hook_dict.get("_managed_by") == "squadron":
                return True
    return False


# ---------------------------------------------------------------------------
# write / remove
# ---------------------------------------------------------------------------


def write_precompact_hook(settings_path: Path) -> None:
    """Add or refresh the squadron PreCompact entry in ``settings_path``.

    - Creates the file (and its parent directory) if missing.
    - Preserves unrelated top-level keys, other hook event names, and any
      non-squadron ``PreCompact`` entries.
    - Replaces an existing squadron-managed entry in place (idempotent).
    """
    data = _load_settings(settings_path)

    hooks_obj = data.setdefault("hooks", {})
    if not isinstance(hooks_obj, dict):
        raise RuntimeError(
            f"Refusing to overwrite settings.json at {settings_path}: "
            "'hooks' is not an object"
        )
    hooks = cast(dict[str, object], hooks_obj)

    precompact_obj = hooks.setdefault("PreCompact", [])
    if not isinstance(precompact_obj, list):
        raise RuntimeError(
            f"Refusing to overwrite settings.json at {settings_path}: "
            "'hooks.PreCompact' is not a list"
        )
    precompact = cast(list[object], precompact_obj)

    new_entry = _squadron_entry()
    replaced = False
    for i, entry in enumerate(precompact):
        if _is_squadron_entry(entry):
            precompact[i] = new_entry
            replaced = True
            break
    if not replaced:
        precompact.append(new_entry)

    _save_settings(settings_path, data)


def remove_precompact_hook(settings_path: Path) -> bool:
    """Remove the squadron-managed PreCompact entry, preserving others.

    Returns:
        True if an entry was removed, False otherwise.

    Tidy cleanup: if ``hooks.PreCompact`` becomes empty after removal, the
    key is deleted; if ``hooks`` then becomes empty, it is deleted too.
    """
    if not settings_path.is_file():
        return False

    data = _load_settings(settings_path)
    hooks_obj = data.get("hooks")
    if not isinstance(hooks_obj, dict):
        return False
    hooks = cast(dict[str, object], hooks_obj)

    precompact_obj = hooks.get("PreCompact")
    if not isinstance(precompact_obj, list):
        return False
    precompact = cast(list[object], precompact_obj)

    filtered = [e for e in precompact if not _is_squadron_entry(e)]
    if len(filtered) == len(precompact):
        return False

    if filtered:
        hooks["PreCompact"] = filtered
    else:
        del hooks["PreCompact"]
        if not hooks:
            del data["hooks"]

    _save_settings(settings_path, data)
    return True
