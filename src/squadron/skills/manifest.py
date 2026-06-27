from __future__ import annotations

import tomllib
from importlib.resources import files
from pathlib import Path

from pydantic import BaseModel, ValidationError

from squadron.skills.models import PackEntry

USER_MANIFEST = Path.home() / ".config" / "squadron" / "skills.toml"
PROJECT_MANIFEST_NAME = ".squadron/skills.toml"

# Origin string for the shipped default manifest (used in CLI display).
SHIPPED_DEFAULT_ORIGIN = "default"


class SkillsManifest(BaseModel):
    packs: dict[str, PackEntry]
    origin: str


def load(path: Path) -> SkillsManifest:
    """Read a skills.toml file and return a SkillsManifest.

    Raises FileNotFoundError if path does not exist.
    Raises ValueError with path context on TOML parse failure.
    """
    with open(path, "rb") as fh:
        try:
            data = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Could not parse skills.toml at {path}: {exc}") from exc

    try:
        packs = {name: PackEntry(**entry) for name, entry in data.get("packs", {}).items()}
    except (ValidationError, TypeError) as exc:
        raise ValueError(f"Invalid pack entry in skills.toml at {path}: {exc}") from exc
    return SkillsManifest(packs=packs, origin=str(path))


def merge(user: SkillsManifest, project: SkillsManifest) -> SkillsManifest:
    """Merge user and project manifests; project-level packs win on name collision."""
    merged_packs = {**user.packs, **project.packs}
    return SkillsManifest(packs=merged_packs, origin="merged")


def _load_shipped_default() -> SkillsManifest | None:
    """Read the skills.toml shipped inside the squadron package via importlib.resources."""
    try:
        text = (files("squadron") / "data" / "skills.toml").read_text()
    except (FileNotFoundError, TypeError):
        return None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    try:
        packs = {name: PackEntry(**entry) for name, entry in data.get("packs", {}).items()}
    except (ValidationError, TypeError):
        return None
    return SkillsManifest(packs=packs, origin=SHIPPED_DEFAULT_ORIGIN)


def load_effective(cwd: Path | None = None) -> SkillsManifest | None:
    """Load the effective manifest by merging shipped default, user-level, and project-level configs.

    Merge order (lowest → highest priority): shipped default → user-level → project-level.
    Returns None only if all three are absent (test scenarios where the default is patched out).
    """
    shipped = _load_shipped_default()
    user_manifest: SkillsManifest | None = None
    project_manifest: SkillsManifest | None = None

    if USER_MANIFEST.exists():
        user_manifest = load(USER_MANIFEST)

    if cwd is not None:
        project_path = cwd / PROJECT_MANIFEST_NAME
        if project_path.exists():
            project_manifest = load(project_path)

    # Build the effective manifest from lowest to highest priority.
    effective: SkillsManifest | None = shipped
    if user_manifest is not None:
        effective = merge(effective, user_manifest) if effective is not None else user_manifest
    if project_manifest is not None:
        effective = merge(effective, project_manifest) if effective is not None else project_manifest
    return effective
