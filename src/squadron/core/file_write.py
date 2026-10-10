"""Writing a file that must not clobber, or must replace whole."""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def write_new_file(path: Path, content: bytes, *, force: bool) -> Path:
    """Write *content* to *path*, creating parent directories; return *path*.

    Without *force* the file is created exclusively: an existing *path* raises
    ``FileExistsError`` naming it, and a failed write leaves no partial file.
    With *force* the content is written to a temporary sibling and moved over
    the target, so a failed write leaves the existing target untouched.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if force:
        _replace_file(path, content)
    else:
        _create_file(path, content)
    return path


def _create_file(path: Path, content: bytes) -> None:
    # Opened outside the try: FileExistsError means the file is not ours to clean up.
    handle = path.open("xb")
    written = False
    try:
        with handle:
            handle.write(content)
        written = True
    finally:
        if not written:
            path.unlink(missing_ok=True)


def _replace_file(path: Path, content: bytes) -> None:
    descriptor, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    tmp_path = Path(tmp_name)
    replaced = False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
        os.replace(tmp_path, path)
        replaced = True
    finally:
        if not replaced:
            with contextlib.suppress(FileNotFoundError):  # already gone: nothing to clean
                tmp_path.unlink()
