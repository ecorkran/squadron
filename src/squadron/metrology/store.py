"""User-level metrology store.

One JSON file per record in ``~/.config/squadron/metrology/``, modeled
directly on ``StateManager`` (``pipeline/state.py``): Pydantic records at the
file boundary, a schema-version guard, atomic write-then-rename, and a
glob-and-filter query surface. No database dependency — the join and
aggregation this slice needs are satisfied by per-record JSON.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from squadron.config.manager import get_config
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.models import (
    RECORD_TYPE_SAMPLE,
    JudgeConfigId,
    MetrologyRecord,
    SampleVerdict,
)

_logger = logging.getLogger(__name__)

#: Schema version stamped into every record. A record whose version is not in
#: the supported set is rejected on read (mirrors StateManager).
_SCHEMA_VERSION = 1
_SUPPORTED_SCHEMA_VERSIONS = {1}

_DEFAULT_STORE_DIR = Path.home() / ".config" / "squadron" / "metrology"


class SchemaVersionError(Exception):
    """Raised when a metrology record file has an unsupported schema_version."""

    def __init__(self, version: object) -> None:
        super().__init__(f"Unsupported metrology record schema_version: {version!r}")
        self.version = version


def resolve_store_dir(cwd: str = ".") -> Path:
    """Resolve the store directory from config, else the user-level default.

    Reads ``metrology.store_dir`` (never a hard-coded call-site default); an
    unset key falls back to ``~/.config/squadron/metrology/``.
    """
    configured = get_config("metrology.store_dir", cwd=cwd)
    if isinstance(configured, str) and configured.strip():
        return Path(configured).expanduser()
    return _DEFAULT_STORE_DIR


def generate_sample_id(now: datetime | None = None) -> str:
    """Return a unique ``sample-{YYYYMMDD}-{uuid8}`` id (mirrors run_id)."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"sample-{stamp}-{uuid.uuid4().hex[:8]}"


class MetrologyStore:
    """Manages metrology record files on disk."""

    def __init__(self, store_dir: Path | None = None) -> None:
        self._store_dir = store_dir if store_dir is not None else _DEFAULT_STORE_DIR
        try:
            self._store_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise MetrologyStoreError(
                f"Could not create metrology store dir {self._store_dir}: {exc}"
            ) from exc

    @property
    def store_dir(self) -> Path:
        return self._store_dir

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _record_path(self, sample_id: str) -> Path:
        return self._store_dir / f"{sample_id}.json"

    def _write_atomic(self, path: Path, data: str) -> None:
        """Write *data* to *path* atomically via a sibling ``.tmp`` file.

        On failure no partial record is left at the final path — the write
        lands on the ``.tmp`` sibling and only an atomic rename publishes it.
        """
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(data, encoding="utf-8")
            tmp.rename(path)
        except OSError as exc:
            raise MetrologyStoreError(f"Failed to write metrology record {path}: {exc}") from exc

    def _load_raw(self, path: Path) -> MetrologyRecord:
        """Read, version-check, and validate one record file."""
        loaded: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise SchemaVersionError(None)
        raw = cast("dict[str, object]", loaded)
        version = raw.get("schema_version")
        if version not in _SUPPORTED_SCHEMA_VERSIONS:
            raise SchemaVersionError(version)
        return MetrologyRecord.model_validate(raw)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_sample(self, sample: SampleVerdict) -> str:
        """Envelope and persist a sample verdict; return its ``sample_id``."""
        record = MetrologyRecord(
            schema_version=_SCHEMA_VERSION,
            record_type=RECORD_TYPE_SAMPLE,
            sample=sample,
        )
        self._write_atomic(
            self._record_path(sample.sample_id),
            json.dumps(record.model_dump(mode="json"), indent=2),
        )
        return sample.sample_id

    def load_record(self, sample_id: str) -> MetrologyRecord:
        """Load and validate one record by id.

        Raises:
            FileNotFoundError: no record file for ``sample_id``.
            SchemaVersionError: the file's ``schema_version`` is unsupported.

        Unlike ``list_samples`` (which tolerantly skips a bad sibling so one
        corrupt file can't sink a whole query), this targeted read surfaces a
        version mismatch loudly.
        """
        path = self._record_path(sample_id)
        if not path.exists():
            raise FileNotFoundError(f"No metrology record for sample_id={sample_id!r}")
        return self._load_raw(path)

    def list_samples(
        self,
        project_id: str | None = None,
        judge_config: JudgeConfigId | None = None,
    ) -> list[SampleVerdict]:
        """Return stored sample verdicts, optionally filtered in memory.

        Globs the store dir, loads and validates each record, and filters by
        ``project_id`` and/or ``judge_config``. Unreadable / unknown-version
        files are skipped with a WARNING (a corrupt sibling must not sink the
        whole query) — a SchemaVersionError on a *specific* load surfaces
        only through the read path that targets one file, not this scan.
        """
        samples: list[SampleVerdict] = []
        for path in sorted(self._store_dir.glob("*.json")):
            try:
                record = self._load_raw(path)
            except (OSError, ValueError, SchemaVersionError):
                _logger.warning("Skipping unreadable metrology record: %s", path)
                continue
            sample = record.sample
            if sample is None or record.record_type != RECORD_TYPE_SAMPLE:
                continue
            if project_id is not None and sample.project_id.value != project_id:
                continue
            if judge_config is not None and sample.judge_config != judge_config:
                continue
            samples.append(sample)
        samples.sort(key=lambda s: s.captured_at, reverse=True)
        return samples

    def count_samples(self, project_id: str) -> int:
        """Number of sample verdicts recorded for one project (budget check)."""
        return len(self.list_samples(project_id=project_id))
