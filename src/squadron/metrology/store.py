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
    RECORD_TYPE_AUDIT_FINDING,
    RECORD_TYPE_AUDIT_NOISE_FLOOR,
    RECORD_TYPE_GRADUATED_CONFIG,
    RECORD_TYPE_SAMPLE,
    AuditNoiseFloor,
    AuditRun,
    GraduatedConfig,
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


def generate_graduation_id(now: datetime | None = None) -> str:
    """Return a unique ``graduation-{YYYYMMDD}-{uuid8}`` id."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"graduation-{stamp}-{uuid.uuid4().hex[:8]}"


def generate_audit_run_id(now: datetime | None = None) -> str:
    """Return a unique ``audit-{YYYYMMDD}-{uuid8}`` id."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"audit-{stamp}-{uuid.uuid4().hex[:8]}"


def generate_noise_floor_id(now: datetime | None = None) -> str:
    """Return a unique ``floor-{YYYYMMDD}-{uuid8}`` id."""
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"floor-{stamp}-{uuid.uuid4().hex[:8]}"


def _judge_config_matches(stored: JudgeConfigId, wanted: JudgeConfigId) -> bool:
    """Whether a stored judge-config matches a filter.

    Always compares ``(template_name, model)``. ``template_content_hash`` is a
    322 version refinement that may be populated on the stored record but absent
    on a template+model filter — so it is compared **only when the filter
    specifies one**. Otherwise a template+model filter would silently return
    nothing once records start carrying a hash.
    """
    if stored.template_name != wanted.template_name or stored.model != wanted.model:
        return False
    if wanted.template_content_hash is None:
        return True
    return stored.template_content_hash == wanted.template_content_hash


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
        lands on the ``.tmp`` sibling and only an atomic replace publishes it.
        ``Path.replace`` overwrites on every platform; ``Path.rename`` raises
        ``FileExistsError`` on Windows when the target already exists.
        """
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(data, encoding="utf-8")
            tmp.replace(path)
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

    def write_graduation(self, graduated: GraduatedConfig, record_id: str | None = None) -> str:
        """Envelope and persist a graduated-config record; return its record id.

        ``record_id`` lets a caller overwrite an existing record in place
        (322's idempotent re-graduate: same identity updates the evidence
        snapshot rather than creating a second record). Omit it to mint a
        new id.
        """
        record_id = record_id or generate_graduation_id()
        record = MetrologyRecord(
            schema_version=_SCHEMA_VERSION,
            record_type=RECORD_TYPE_GRADUATED_CONFIG,
            graduated_config=graduated,
        )
        self._write_atomic(
            self._record_path(record_id),
            json.dumps(record.model_dump(mode="json"), indent=2),
        )
        return record_id

    def list_graduations(self) -> list[tuple[str, GraduatedConfig]]:
        """Return all stored ``(record_id, GraduatedConfig)`` pairs.

        Tolerantly skips an unreadable sibling with a WARNING (mirrors
        ``list_samples``) — one corrupt record must not sink the whole scan.
        """
        graduations: list[tuple[str, GraduatedConfig]] = []
        for path in sorted(self._store_dir.glob("*.json")):
            try:
                record = self._load_raw(path)
            except (OSError, ValueError, SchemaVersionError):
                _logger.warning("Skipping unreadable metrology record: %s", path)
                continue
            if record.record_type != RECORD_TYPE_GRADUATED_CONFIG or record.graduated_config is None:
                continue
            graduations.append((path.stem, record.graduated_config))
        return graduations

    def write_audit_run(self, run: AuditRun) -> str:
        """Envelope and persist one complete audit run; return its ``run_id``.

        A run is persisted as a whole or not at all — callers must not write
        a partially-parsed run, since a truncated audit would enter a noise
        floor as a spuriously low finding count.
        """
        record = MetrologyRecord(
            schema_version=_SCHEMA_VERSION,
            record_type=RECORD_TYPE_AUDIT_FINDING,
            audit_run=run,
        )
        self._write_atomic(
            self._record_path(run.run_id),
            json.dumps(record.model_dump(mode="json"), indent=2),
        )
        return run.run_id

    def write_noise_floor(self, floor: AuditNoiseFloor, record_id: str | None = None) -> str:
        """Envelope and persist a noise-floor record; return its record id.

        ``record_id`` lets a caller replace an existing floor in place — a
        floor recomputed after more runs are added updates rather than
        accumulating a second record for the same series. Omit it to mint a
        new id.
        """
        record_id = record_id or generate_noise_floor_id()
        record = MetrologyRecord(
            schema_version=_SCHEMA_VERSION,
            record_type=RECORD_TYPE_AUDIT_NOISE_FLOOR,
            audit_noise_floor=floor,
        )
        self._write_atomic(
            self._record_path(record_id),
            json.dumps(record.model_dump(mode="json"), indent=2),
        )
        return record_id

    def list_audit_runs(
        self,
        project_id: str | None = None,
        audit_prompt_hash: str | None = None,
    ) -> list[AuditRun]:
        """Return stored audit runs, optionally filtered in memory.

        ``audit_prompt_hash`` is the comparability guard: runs taken under
        different instruments are never pooled, so a caller reducing a
        variance series filters on it explicitly.

        Tolerantly skips an unreadable sibling with a WARNING — one corrupt
        record must not sink the whole scan.
        """
        runs: list[AuditRun] = []
        for path in sorted(self._store_dir.glob("*.json")):
            try:
                record = self._load_raw(path)
            except (OSError, ValueError, SchemaVersionError):
                _logger.warning("Skipping unreadable metrology record: %s", path)
                continue
            run = record.audit_run
            if run is None or record.record_type != RECORD_TYPE_AUDIT_FINDING:
                continue
            if project_id is not None and run.project_id.value != project_id:
                continue
            if audit_prompt_hash is not None and run.audit_prompt_hash != audit_prompt_hash:
                continue
            runs.append(run)
        runs.sort(key=lambda r: r.measured_at, reverse=True)
        return runs

    def list_noise_floors(self, project_id: str | None = None) -> list[tuple[str, AuditNoiseFloor]]:
        """Return all stored ``(record_id, AuditNoiseFloor)`` pairs.

        The record id is returned alongside the payload so a caller
        recomputing a floor can replace it in place via ``write_noise_floor``
        rather than accumulating duplicates for one series.
        """
        floors: list[tuple[str, AuditNoiseFloor]] = []
        for path in sorted(self._store_dir.glob("*.json")):
            try:
                record = self._load_raw(path)
            except (OSError, ValueError, SchemaVersionError):
                _logger.warning("Skipping unreadable metrology record: %s", path)
                continue
            floor = record.audit_noise_floor
            if floor is None or record.record_type != RECORD_TYPE_AUDIT_NOISE_FLOOR:
                continue
            if project_id is not None and floor.project_id.value != project_id:
                continue
            floors.append((path.stem, floor))
        # Newest first, matching ``list_audit_runs``. Glob order sorts by
        # path, so a caller reaching for "the latest floor" would otherwise
        # get whichever record id happened to sort last.
        floors.sort(key=lambda pair: pair[1].measured_at, reverse=True)
        return floors

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
            if judge_config is not None and not _judge_config_matches(
                sample.judge_config, judge_config
            ):
                continue
            samples.append(sample)
        samples.sort(key=lambda s: s.captured_at, reverse=True)
        return samples

    def count_samples(self, project_id: str) -> int:
        """Number of sample verdicts recorded for one project (budget check)."""
        return len(self.list_samples(project_id=project_id))
