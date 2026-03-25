"""Typed interface to Context Forge CLI operations.

Centralizes all CF subprocess calls behind a single client class
with typed return values, replacing scattered subprocess.run() calls.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ContextForgeNotAvailable(Exception):
    """Raised when the ``cf`` CLI is not installed or not on PATH."""


class ContextForgeError(Exception):
    """Raised when a ``cf`` command fails (non-zero exit or bad output)."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SliceEntry:
    """A single slice from ``cf list slices --json``."""

    index: int
    name: str
    design_file: str | None
    status: str


@dataclass
class TaskEntry:
    """A single task group from ``cf list tasks --json``."""

    index: int
    files: list[str] = field(default_factory=lambda: [])


@dataclass
class ProjectInfo:
    """Project metadata from ``cf get --json``."""

    arch_file: str
    slice_plan: str
    phase: str
    slice: str


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ContextForgeClient:
    """Typed interface to Context Forge CLI operations."""

    def _run(self, args: list[str]) -> str:
        """Run a ``cf`` CLI command and return stdout.

        Raises:
            ContextForgeNotAvailable: if ``cf`` is not on PATH.
            ContextForgeError: if the command exits non-zero.
        """
        try:
            result = subprocess.run(
                ["cf", *args],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise ContextForgeNotAvailable(
                "'cf' (Context-Forge CLI) is not installed or not on PATH."
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() if exc.stderr else str(exc)
            raise ContextForgeError(f"cf {' '.join(args)}: {stderr}") from exc
        return result.stdout

    def _run_json(self, args: list[str]) -> Any:
        """Run a ``cf`` CLI command and parse stdout as JSON.

        Raises:
            ContextForgeError: if stdout is not valid JSON.
        """
        stdout = self._run(args)
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise ContextForgeError(
                f"cf {' '.join(args)}: invalid JSON output: {exc}"
            ) from exc

    def is_available(self) -> bool:
        """Return True if ``cf`` is installed and responsive."""
        try:
            self._run(["--version"])
        except ContextForgeNotAvailable:
            return False
        return True

    def list_slices(self) -> list[SliceEntry]:
        """Return all slices from ``cf list slices --json``."""
        data: dict[str, Any] = self._run_json(["list", "slices", "--json"])
        raw_entries: list[dict[str, Any]] = data.get("entries", [])
        return [
            SliceEntry(
                index=int(e["index"]),
                name=str(e["name"]),
                design_file=e.get("designFile"),
                status=str(e.get("status", "")),
            )
            for e in raw_entries
        ]

    def list_tasks(self) -> list[TaskEntry]:
        """Return all task groups from ``cf list tasks --json``."""
        raw_entries: list[dict[str, Any]] = self._run_json(["list", "tasks", "--json"])
        return [
            TaskEntry(
                index=int(e["index"]),
                files=e.get("files", []),
            )
            for e in raw_entries
        ]

    def get_project(self) -> ProjectInfo:
        """Return project metadata from ``cf get --json``."""
        data: dict[str, Any] = self._run_json(["get", "--json"])
        arch_raw: str = str(data.get("fileArch", ""))
        # Resolve arch file: bare name → full path with .md suffix
        if arch_raw and not arch_raw.endswith(".md"):
            arch_file = f"project-documents/user/architecture/{arch_raw}.md"
        else:
            arch_file = arch_raw
        return ProjectInfo(
            arch_file=arch_file,
            slice_plan=str(data.get("fileSlicePlan", "")),
            phase=str(data.get("phase", "")),
            slice=str(data.get("slice", "")),
        )
