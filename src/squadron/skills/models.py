from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, model_validator


class SurfaceType(StrEnum):
    """How a pack exposes its commands — mirrors PackEntry's two surface forms."""

    PREFIX = "prefix"
    DISPATCH_FILE = "dispatch_file"


class PackEntry(BaseModel):
    source: str
    prefix: str | None = None
    dispatch_file: str | None = None

    @model_validator(mode="after")
    def _exactly_one_surface(self) -> PackEntry:
        has_prefix = self.prefix is not None
        has_dispatch = self.dispatch_file is not None
        if has_prefix and has_dispatch:
            raise ValueError(
                "PackEntry must have exactly one of 'prefix' or 'dispatch_file', not both."
            )
        if not has_prefix and not has_dispatch:
            raise ValueError("PackEntry must have exactly one of 'prefix' or 'dispatch_file'.")
        return self


@dataclass
class InstallResult:
    pack_name: str
    files_written: list[str] = field(default_factory=list[str])
    destination: Path = field(default_factory=lambda: Path("."))


class InstallReceipt(BaseModel):
    """Persisted record of an install, consulted by uninstall to remove exact files."""

    pack_name: str
    surface: SurfaceType
    destination: Path
    files_written: list[str]


class SkillSourceError(Exception):
    """Raised when a skill source cannot be resolved or fetched."""
