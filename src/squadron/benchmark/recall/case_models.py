"""Load and validate recall case files, and derive bug locations from history (D1).

The case payloads live in ``metrology/recall_case_models.py``. This module reads the
committed YAML into a ``CaseFileSpec``, then ``derive_locations`` resolves each bug's
locations from the files its proof commits changed (``git show --name-only``), unfiltered,
followed by the file's ``extra_locations``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator, model_validator

from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessRunner,
    ProcessTimedOutError,
)
from squadron.metrology.project_id import ProjectId
from squadron.metrology.recall_case_models import (
    BugLocation,
    CaseStatus,
    KnownBug,
    OriginalReview,
    RealBugCase,
    RecallCaseKind,
)

_logger = logging.getLogger(__name__)
#: An issue proof (``#123``); anything else is a commit.
_ISSUE_PROOF = re.compile(r"^#\d+$")


class CaseFileError(Exception):
    """A case file failed validation or its locations could not be derived."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


def _require_text(value: object, field: str) -> object:
    """YAML turns unquoted all-digit shas into numbers; refuse instead of guessing."""
    if isinstance(value, bool | int | float):
        raise ValueError(f"{field} {value!r} must be a quoted string")
    return value


class BugSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    description: str
    proof: tuple[str, ...]
    original_review: OriginalReview
    extra_locations: tuple[BugLocation, ...] = ()

    @field_validator("proof", mode="before")
    @classmethod
    def _proof_text(cls, value: object) -> object:
        if isinstance(value, list | tuple):
            items = cast("Sequence[object]", value)
            for item in items:
                _require_text(item, "proof")
            return items
        return value

    @model_validator(mode="after")
    def _checks(self) -> BugSpec:
        if not self.proof:
            raise ValueError(f"bug {self.id} has no proof")
        missing = [loc.file for loc in self.extra_locations if not (loc.reason and loc.reason.strip())]
        if missing:
            raise ValueError(f"bug {self.id}: extra location(s) without a reason: {missing}")
        if any(_ISSUE_PROOF.match(p) for p in self.proof) and not self.extra_locations:
            raise ValueError(f"bug {self.id} has an issue proof but no extra_locations")
        return self

    @property
    def commit_proofs(self) -> tuple[str, ...]:
        return tuple(p for p in self.proof if not _ISSUE_PROOF.match(p))


class CaseFileSpec(BaseModel):
    """A case file as written; ``repo`` keeps ``~`` unexpanded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    kind: RecallCaseKind
    repo: str
    host_repo: str
    distribution: str
    base: str
    head: str
    status: CaseStatus
    hand_run_id: str | None = None
    bugs: tuple[BugSpec, ...]
    notes: str | None = None

    @field_validator("base", "head", mode="before")
    @classmethod
    def _sha_text(cls, value: object) -> object:
        return _require_text(value, "sha")

    @field_validator("hand_run_id", mode="before")
    @classmethod
    def _hand_run_text(cls, value: object) -> object:
        return _require_text(value, "hand_run_id")

    @field_validator("bugs")
    @classmethod
    def _bugs_present(cls, value: tuple[BugSpec, ...]) -> tuple[BugSpec, ...]:
        if not value:
            raise ValueError("a case needs at least one bug")
        ids = [bug.id for bug in value]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate bug ids: {ids}")
        return value

    @property
    def repo_path(self) -> Path:
        return Path(self.repo).expanduser()


def load_case_file(path: Path) -> CaseFileSpec:
    """Read and schema-check one case file; any problem raises ``CaseFileError``."""
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise CaseFileError(path, f"unreadable: {exc}") from exc
    if not isinstance(raw, dict):
        raise CaseFileError(path, "not a YAML mapping")
    try:
        return CaseFileSpec.model_validate(raw)
    except ValidationError as exc:
        raise CaseFileError(path, _validation_reason(exc)) from exc


def _validation_reason(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        where = ".".join(str(item) for item in error["loc"]) or "file"
        parts.append(f"{where}: {error['msg']}")
    return "; ".join(parts)


def derive_locations(
    path: Path, spec: CaseFileSpec, runner: ProcessRunner, timeout: float
) -> tuple[KnownBug, ...]:
    """Each bug with its resolved locations: proof-commit files, then ``extra_locations``."""
    return tuple(_resolve_bug(path, spec, bug, runner, timeout) for bug in spec.bugs)


def _resolve_bug(
    path: Path, spec: CaseFileSpec, bug: BugSpec, runner: ProcessRunner, timeout: float
) -> KnownBug:
    files: list[str] = []
    for sha in bug.commit_proofs:
        for changed in _changed_files(path, spec, sha, runner, timeout):
            if changed not in files:
                files.append(changed)
    derived = tuple(BugLocation(file=file) for file in files)
    return KnownBug(
        id=bug.id,
        description=bug.description,
        proof=bug.proof,
        original_review=bug.original_review,
        locations=derived + bug.extra_locations,
        extra_locations=bug.extra_locations,
    )


def _changed_files(
    path: Path, spec: CaseFileSpec, sha: str, runner: ProcessRunner, timeout: float
) -> list[str]:
    argv = ["git", "show", "--name-only", "--format=", sha]
    try:
        result = runner.run(argv, cwd=str(spec.repo_path), timeout=timeout)
    except ProcessTimedOutError as exc:
        raise CaseFileError(path, f"git show of proof commit {sha} timed out after {timeout}s") from exc
    except (ProcessNotFoundError, ProcessCwdNotFoundError) as exc:
        raise CaseFileError(path, f"git show of proof commit {sha} could not run: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip()[-300:]
        raise CaseFileError(path, f"git show of proof commit {sha} failed: {detail}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def build_case(spec: CaseFileSpec, bugs: tuple[KnownBug, ...], project_id: ProjectId) -> RealBugCase:
    """The record for a validated spec and its resolved bugs."""
    return RealBugCase.build(
        project_id=project_id,
        name=spec.name,
        kind=spec.kind,
        repo=spec.repo,
        host_repo=spec.host_repo,
        distribution=spec.distribution,
        base=spec.base,
        head=spec.head,
        status=spec.status,
        hand_run_id=spec.hand_run_id,
        bugs=bugs,
        notes=spec.notes,
    )
