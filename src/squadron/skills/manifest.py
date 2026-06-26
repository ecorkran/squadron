from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, ValidationError

from squadron.skills.models import PackEntry

USER_MANIFEST = Path.home() / ".config" / "squadron" / "skills.toml"
PROJECT_MANIFEST_NAME = ".squadron/skills.toml"


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


def load_effective(cwd: Path | None = None) -> SkillsManifest | None:
    """Load the effective manifest by merging user-level and optional project-level configs.

    Returns None if neither file exists.
    """
    user_manifest: SkillsManifest | None = None
    project_manifest: SkillsManifest | None = None

    if USER_MANIFEST.exists():
        user_manifest = load(USER_MANIFEST)

    if cwd is not None:
        project_path = cwd / PROJECT_MANIFEST_NAME
        if project_path.exists():
            project_manifest = load(project_path)

    if user_manifest is None and project_manifest is None:
        return None
    if user_manifest is None:
        return project_manifest
    if project_manifest is None:
        return user_manifest
    return merge(user_manifest, project_manifest)
