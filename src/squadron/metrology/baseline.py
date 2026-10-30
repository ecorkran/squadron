"""Preflight and scope plan for ``sq metrology baseline`` (slice 404).

Runs every check that can fail on config or repository state before the
snapshot or any audit starts, so a missing model can't leave a snapshot with
no audit behind it. Runs no tools, writes nothing and makes no LLM call.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from squadron.config.manager import get_typed_config
from squadron.metrology.audit import (
    preflight_project,
    resolve_audit_model,
    resolve_audit_profile,
    resolve_audit_skill,
)
from squadron.metrology.audit_variance import MIN_USABLE_RUNS
from squadron.metrology.errors import BaselinePreflightError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.models import ProjectId
from squadron.metrology.snapshot.contract import AdapterRegistry
from squadron.metrology.snapshot.files import effective_exclusions, resolve_files
from squadron.metrology.snapshot.preflight import preflight


@dataclass(frozen=True)
class BaselinePlan:
    """What the baseline is about to measure and spend."""

    project_path: Path
    project_id: ProjectId
    head_sha: str
    file_count: int
    byte_count: int
    exclusions: list[str]
    runs: int
    cooldown_s: int
    profile: str
    model: str


def prepare_baseline(
    project_path: Path,
    registry: AdapterRegistry,
    *,
    profile: str | None,
    model: str | None,
) -> BaselinePlan:
    """Validate everything the baseline needs and describe its scope.

    Every config read uses ``cwd=project_path``, so the snapshot and the audit
    series see the same settings. Raises ``BaselinePreflightError`` for a missing
    model or too few runs; the snapshot, audit, skill and identity errors
    propagate unchanged.
    """
    config_cwd = str(project_path)
    checked = preflight(project_path)
    project_id = derive_project_id(config_cwd)
    preflight_project(project_path, require_clean=True, cwd=config_cwd)
    resolve_audit_skill()
    resolved_profile = resolve_audit_profile(profile, cwd=config_cwd)
    resolved_model = _require_model(model, config_cwd)
    runs = _require_runs(config_cwd)
    cooldown_s = int(get_typed_config("metrology.audit_run_cooldown_s", int, cwd=config_cwd))

    # The same calls take_snapshot makes, so the report and the snapshot agree.
    exclusions = effective_exclusions(checked.project_exclusions, registry.values())
    files = resolve_files(project_path, exclusions)
    return BaselinePlan(
        project_path=project_path,
        project_id=project_id,
        head_sha=checked.head_sha,
        file_count=len(files),
        byte_count=sum((project_path / relative).stat().st_size for relative in files),
        exclusions=exclusions,
        runs=runs,
        cooldown_s=cooldown_s,
        profile=resolved_profile,
        model=resolved_model,
    )


def _require_model(model: str | None, config_cwd: str) -> str:
    """A baseline needs a pinned model: an unpinned one isn't a fixed instrument."""
    resolved = resolve_audit_model(model, cwd=config_cwd)
    if resolved is None:
        raise BaselinePreflightError(
            "No audit model is pinned. A floor measured under a model the CLI picks "
            "can't be compared later. Set one with "
            "'sq config set metrology.audit_model <model>' or pass --model."
        )
    return resolved


def _require_runs(config_cwd: str) -> int:
    runs = int(get_typed_config("metrology.audit_variance_runs", int, cwd=config_cwd))
    if runs < MIN_USABLE_RUNS:
        raise BaselinePreflightError(
            f"metrology.audit_variance_runs is {runs}; a noise floor needs at least "
            f"{MIN_USABLE_RUNS} runs. Raise it with "
            f"'sq config set metrology.audit_variance_runs {MIN_USABLE_RUNS}'."
        )
    return runs
