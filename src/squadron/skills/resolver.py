from __future__ import annotations

import importlib.resources
import shutil
import subprocess
import tempfile
from pathlib import Path

from squadron.skills.models import PackEntry, SkillSourceError

_USER_CONFIG_DIR = Path.home() / ".config" / "squadron"


def resolve_source(entry: PackEntry, pack_name: str) -> Path:
    """Return a local Path to the directory containing .md files for the pack.

    For github: sources the returned path lives inside a TemporaryDirectory;
    the caller is responsible for cleanup (use as context manager or keep reference).
    """
    source = entry.source

    if source == "bundled":
        return _resolve_bundled(pack_name)

    if source.startswith("github:"):
        return _resolve_github(source, pack_name)

    if source.startswith("./") or source.startswith("../"):
        return _resolve_relative(source, pack_name)

    candidate = Path(source)
    if candidate.is_absolute():
        return _resolve_absolute(candidate, pack_name)

    raise SkillSourceError(f"Unknown source format '{source}' for pack '{pack_name}'.")


def _resolve_bundled(pack_name: str) -> Path:
    try:
        pkg = importlib.resources.files("squadron") / "commands" / pack_name
        # Materialize to a real filesystem path
        with importlib.resources.as_file(pkg) as path:
            if not path.is_dir():
                raise SkillSourceError(f"Bundled pack '{pack_name}' not found in squadron package.")
            return path
    except (TypeError, FileNotFoundError) as exc:
        raise SkillSourceError(f"Bundled pack '{pack_name}' not found in squadron package.") from exc


def _resolve_absolute(path: Path, pack_name: str) -> Path:
    if not path.exists() or not path.is_dir():
        raise SkillSourceError(
            f"Local source path '{path}' for pack '{pack_name}' does not exist or is not a directory."
        )
    return path


def _resolve_relative(source: str, pack_name: str) -> Path:
    resolved = (_USER_CONFIG_DIR / source).resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise SkillSourceError(
            f"Relative source path '{source}' for pack '{pack_name}' "
            f"not found (resolved to '{resolved}')."
        )
    return resolved


def _resolve_github(source: str, pack_name: str) -> Path:
    if shutil.which("git") is None:
        raise SkillSourceError(
            f"Cannot install pack '{pack_name}' from GitHub: 'git' is not on PATH. "
            "Install git and try again."
        )

    # source format: "github:<org>/<repo>"
    repo_spec = source[len("github:") :]
    url = f"https://github.com/{repo_spec}.git"

    tmp_dir = tempfile.mkdtemp(prefix="squadron-skills-")
    result = subprocess.run(
        ["git", "clone", "--depth=1", url, tmp_dir],
        capture_output=True,
    )
    if result.returncode != 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        stderr = result.stderr.decode(errors="replace").strip()
        raise SkillSourceError(f"Failed to clone '{url}' for pack '{pack_name}': {stderr}")

    return Path(tmp_dir)
