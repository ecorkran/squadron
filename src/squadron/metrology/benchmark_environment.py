"""The grader identity a benchmark result depended on (slice 421 D6).

Lives in ``metrology`` because stored records (``FixQualification``) embed it and the
metrology package must not import from ``squadron.benchmark``. ``benchmark.adapter``
imports it from here, so existing ``from squadron.benchmark.adapter import
EnvironmentIdentity`` imports keep working. Not the snapshot's ``EnvironmentIdentity``
in ``snapshot_models``, which describes a different thing.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, computed_field

from squadron.metrology.snapshot_models import SourceLanguage


class EnvironmentIdentity(BaseModel):
    """A grader identity: what a qualification or replay result depended on (D6)."""

    model_config = ConfigDict(frozen=True)

    language: SourceLanguage
    lockfile_path: str
    lockfile_sha256: str
    interpreter_version: str
    installer_version: str
    platform: str
    scrub_spec_version: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def identity_digest(self) -> str:
        """sha256 over every other field, in declared order."""
        parts = [
            self.language.value,
            self.lockfile_path,
            self.lockfile_sha256,
            self.interpreter_version,
            self.installer_version,
            self.platform,
            str(self.scrub_spec_version),
        ]
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
