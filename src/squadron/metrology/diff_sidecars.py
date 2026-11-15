"""Content-addressed diff sidecars for implementation replays (slice 424 D11).

A producer's diff is too large for its replay record, so the record carries a ``DiffRef``
and the bytes live at ``<store>/sidecars/diffs/<sha256>.diff``. The storage rules (write-once,
atomic, hash-verified, outside the record scan) are ``ContentSidecars``' (slice 425 D11);
this class adds the ``DiffRef`` a replay record keeps.
"""

from __future__ import annotations

from pathlib import Path

from squadron.metrology.benchmark_replay_models import DiffRef
from squadron.metrology.content_sidecars import (
    SIDECAR_ROOT,
    SIDECAR_SUFFIXES,
    ContentSidecars,
    SidecarKind,
)

SIDECAR_SUBDIRECTORY = SIDECAR_ROOT / SidecarKind.DIFFS.value
SIDECAR_SUFFIX = SIDECAR_SUFFIXES[SidecarKind.DIFFS]
_DIFF_HEADER = b"diff --git "


def count_files_changed(diff: bytes) -> int:
    """Number of ``diff --git`` header lines (base85 binary payload lines cannot match)."""
    return int(diff.startswith(_DIFF_HEADER)) + diff.count(b"\n" + _DIFF_HEADER)


class DiffSidecars:
    """Write-once, hash-verified diff files under a store root."""

    def __init__(self, root: Path) -> None:
        self._sidecars = ContentSidecars(root, SidecarKind.DIFFS)

    def put(self, data: bytes) -> DiffRef:
        """Store *data* under its sha256, atomically, unless already present and intact."""
        digest = self._sidecars.put(data)
        return DiffRef(sha256=digest, bytes=len(data), files_changed=count_files_changed(data))

    def get(self, sha256: str) -> bytes:
        """The stored diff; a missing file or a content/hash mismatch raises."""
        return self._sidecars.get(sha256)
