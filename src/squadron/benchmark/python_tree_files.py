"""File-level operations on a sandbox tree for the Python fix-case adapter (slice 422 D4, D11).

Kept apart from ``python_fairness`` so that file stays on pytest and the trace plugin.
"""

from __future__ import annotations

import logging
import os
import tomllib
from collections.abc import Mapping
from pathlib import Path, PurePosixPath

from squadron.benchmark.fairness import HarnessFailure
from squadron.metrology.benchmark_models import GraderCommand, GraderCommandKind

_logger = logging.getLogger(__name__)

PYPROJECT_NAME = "pyproject.toml"
SUITE_ARGV = ("python", "-m", "pytest")
LINT_ARGV = ("ruff", "check")
TYPECHECK_ARGV = ("pyright",)
_RUFF_CONFIG_FILE = "ruff.toml"
_PYRIGHT_CONFIG_FILE = "pyrightconfig.json"


def _failure(detail: str) -> HarnessFailure:
    _logger.error("fix-case harness failure: %s", detail)
    return HarnessFailure(detail)


def _resolve_inside(root: Path, relative: str) -> Path:
    """``root / relative`` with ``..`` folded away; a path that leaves ``root`` is a failure."""
    pure = PurePosixPath(relative)
    if not relative or pure.is_absolute() or ".." in pure.parts:
        raise _failure(f"overlay path {relative!r} is not a path inside the tree")
    target = Path(os.path.normpath(root / pure))
    try:
        target.relative_to(root)
    except ValueError:
        raise _failure(f"overlay path {relative!r} escapes the tree") from None
    return target


def _prune_empty_parents(root: Path, start: Path) -> None:
    """Remove empty directories upward from ``start`` so a removed file leaves no trace."""
    directory = start
    while directory != root and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def overlay_files(tree: Path, files: Mapping[str, bytes | None]) -> None:
    """Write each ``path -> bytes`` and remove each ``path -> None``, creating directories.

    Every path is validated before any is touched. An ``OSError`` is logged at ERROR and
    raised as ``HarnessFailure``.
    """
    root = tree.resolve()
    targets = {path: _resolve_inside(root, path) for path in files}
    for path, content in files.items():
        target = targets[path]
        try:
            if content is None:
                target.unlink(missing_ok=True)
                _prune_empty_parents(root, target.parent)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
        except OSError as exc:
            _logger.exception("overlay of %s failed", path)
            raise HarnessFailure(f"overlay of {path} failed: {exc}") from exc


def _read_toml(path: Path) -> dict[str, object]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise _failure(f"{path} does not parse: {exc}") from exc


def grader_commands_for(tree: Path) -> tuple[GraderCommand, ...]:
    """``suite`` always; ``lint`` and ``typecheck`` only when the parent configures the tool."""
    tool = _read_toml(tree / PYPROJECT_NAME).get("tool")
    tools: dict[str, object] = tool if isinstance(tool, dict) else {}  # pyright: ignore[reportUnknownVariableType]
    commands = [GraderCommand(kind=GraderCommandKind.SUITE, argv=SUITE_ARGV)]
    if "ruff" in tools or (tree / _RUFF_CONFIG_FILE).is_file():
        commands.append(GraderCommand(kind=GraderCommandKind.LINT, argv=LINT_ARGV))
    if "pyright" in tools or (tree / _PYRIGHT_CONFIG_FILE).is_file():
        commands.append(GraderCommand(kind=GraderCommandKind.TYPECHECK, argv=TYPECHECK_ARGV))
    return tuple(commands)
