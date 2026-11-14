"""Content-addressed diff sidecars for implementation replays (slice 424 D11).

A producer's diff is too large for its replay record, so the record carries a ``DiffRef``
and the bytes live at ``<store>/sidecars/diffs/<sha256>.diff``. The sidecar directory is
below the store root, never beside the ``*.json`` records, so record scans never read it.
Every read and every re-put verifies the content against its hash.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from pathlib import Path
from typing import NoReturn

from squadron.metrology.benchmark_replay_models import DiffRef
from squadron.metrology.errors import MetrologyStoreError

_logger = logging.getLogger(__name__)

SIDECAR_SUBDIRECTORY = Path("sidecars") / "diffs"
SIDECAR_SUFFIX = ".diff"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_DIFF_HEADER = b"diff --git "


def count_files_changed(diff: bytes) -> int:
    """Number of ``diff --git`` header lines (base85 binary payload lines cannot match)."""
    return int(diff.startswith(_DIFF_HEADER)) + diff.count(b"\n" + _DIFF_HEADER)


class DiffSidecars:
    """Write-once, hash-verified diff files under a store root."""

    def __init__(self, root: Path) -> None:
        self._directory = root / SIDECAR_SUBDIRECTORY

    def put(self, data: bytes) -> DiffRef:
        """Store *data* under its sha256, atomically, unless already present and intact."""
        digest = hashlib.sha256(data).hexdigest()
        path = self._path(digest)
        if path.exists():
            self._verified_bytes(digest, path)
        else:
            self._write_atomic(path, data)
        return DiffRef(sha256=digest, bytes=len(data), files_changed=count_files_changed(data))

    def get(self, sha256: str) -> bytes:
        """The stored diff; a missing file or a content/hash mismatch raises."""
        if not _SHA256.fullmatch(sha256):
            self._fail(f"Diff sidecar key {sha256!r} is not a sha256 hex digest")
        path = self._path(sha256)
        if not path.exists():
            self._fail(f"Diff sidecar {path} is missing")
        return self._verified_bytes(sha256, path)

    def _path(self, digest: str) -> Path:
        return self._directory / f"{digest}{SIDECAR_SUFFIX}"

    def _verified_bytes(self, digest: str, path: Path) -> bytes:
        try:
            data = path.read_bytes()
        except OSError as exc:
            _logger.exception("Cannot read diff sidecar %s", path)
            raise MetrologyStoreError(f"Cannot read diff sidecar {path}: {exc}") from exc
        if hashlib.sha256(data).hexdigest() != digest:
            self._fail(f"Diff sidecar {path} does not match its sha256 (tampered or corrupt)")
        return data

    def _write_atomic(self, path: Path, data: bytes) -> None:
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            tmp.replace(path)
        except OSError as exc:
            _logger.exception("Failed to write diff sidecar %s", path)
            tmp.unlink(missing_ok=True)
            raise MetrologyStoreError(f"Failed to write diff sidecar {path}: {exc}") from exc

    @staticmethod
    def _fail(message: str) -> NoReturn:
        _logger.error(message)
        raise MetrologyStoreError(message)
