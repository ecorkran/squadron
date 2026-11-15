"""Content-addressed sidecar files, one directory per kind (slice 425 D11).

Records that would outgrow their bound keep a hash and the bytes live at
``<store>/sidecars/<kind>/<sha256><suffix>``. The sidecar tree is below the store
root, never beside the ``*.json`` records, so record scans never read it. Files are
write-once, written atomically, and every read and every re-put verifies the content
against its hash. Slice 424's ``DiffSidecars`` is this class for the ``diffs`` kind.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from enum import StrEnum
from pathlib import Path
from typing import NoReturn

from squadron.metrology.errors import MetrologyStoreError

_logger = logging.getLogger(__name__)

SIDECAR_ROOT = Path("sidecars")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class SidecarKind(StrEnum):
    """What a sidecar holds; each kind has its own directory and file suffix."""

    DIFFS = "diffs"
    SNAPSHOTS = "snapshots"
    NODES = "nodes"
    REVIEWS = "reviews"


SIDECAR_SUFFIXES: dict[SidecarKind, str] = {
    SidecarKind.DIFFS: ".diff",
    SidecarKind.SNAPSHOTS: ".json",
    SidecarKind.NODES: ".json",
    SidecarKind.REVIEWS: ".json",
}


class ContentSidecars:
    """Write-once, hash-verified files of one kind under a store root."""

    def __init__(self, root: Path, kind: SidecarKind) -> None:
        self._label = f"{kind.value} sidecar"
        self._suffix = SIDECAR_SUFFIXES[kind]
        self._directory = root / SIDECAR_ROOT / kind.value

    def put(self, data: bytes) -> str:
        """Store *data* under its sha256, atomically, unless already present and intact."""
        digest = hashlib.sha256(data).hexdigest()
        path = self._path(digest)
        if path.exists():
            self._verified_bytes(digest, path)
        else:
            self._write_atomic(path, data)
        return digest

    def get(self, sha256: str) -> bytes:
        """The stored bytes; a missing file or a content/hash mismatch raises."""
        if not _SHA256.fullmatch(sha256):
            self._fail(f"{self._label} key {sha256!r} is not a sha256 hex digest")
        path = self._path(sha256)
        if not path.exists():
            self._fail(f"{self._label} {path} is missing")
        return self._verified_bytes(sha256, path)

    def _path(self, digest: str) -> Path:
        return self._directory / f"{digest}{self._suffix}"

    def _verified_bytes(self, digest: str, path: Path) -> bytes:
        try:
            data = path.read_bytes()
        except OSError as exc:
            _logger.exception("Cannot read %s %s", self._label, path)
            raise MetrologyStoreError(f"Cannot read {self._label} {path}: {exc}") from exc
        if hashlib.sha256(data).hexdigest() != digest:
            self._fail(f"{self._label} {path} does not match its sha256 (tampered or corrupt)")
        return data

    def _write_atomic(self, path: Path, data: bytes) -> None:
        tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            tmp.replace(path)
        except OSError as exc:
            _logger.exception("Failed to write %s %s", self._label, path)
            tmp.unlink(missing_ok=True)
            raise MetrologyStoreError(f"Failed to write {self._label} {path}: {exc}") from exc

    @staticmethod
    def _fail(message: str) -> NoReturn:
        _logger.error(message)
        raise MetrologyStoreError(message)
