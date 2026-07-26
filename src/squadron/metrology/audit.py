"""The audit harness: run the tech-debt-audit skill against a project.

Surface-agnostic — no Typer imports — matching the 320/321/322 core/CLI
split. The CLI shells in ``cli/commands/metrology.py`` are thin wrappers
over this module.

The instrument's identity travels with every run. ``audit_prompt_hash`` is
taken from the vendored skill file **actually used for that run**, not from
the canonical fork, so a fork/squadron divergence lands in the data even if
it escapes the CI sync guard. Audits taken under differing hashes are never
pooled — the same comparability discipline 322 canonized for judge
templates.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from squadron.metrology.errors import MetrologyError
from squadron.skills.models import SkillSourceError
from squadron.skills.resolver import _resolve_bundled  # pyright: ignore[reportPrivateUsage]

_logger = logging.getLogger(__name__)

#: The pack and file the audit instrument lives in, resolved through the
#: skills resolver so the harness works whether or not ``sq skills install``
#: has been run.
_AUDIT_PACK = "analysis"
_AUDIT_SKILL_FILENAME = "tech-debt-audit.md"

#: Prefixed to the audit prompt to suppress the skill's repeat-run mode.
#:
#: The skill is a living document by default: on a repeat run it reads the
#: previous audit file and emits a RESOLVED/NEW diff. That behavior is
#: correct for interactive use and fatal for variance measurement — run 2
#: of a series would be anchored to run 1 rather than an independent
#: sample, biasing the measured floor toward zero.
#:
#: Defined once here and asserted against the skill file by
#: ``tests/metrology/test_audit_skill_sync.py``, so the string the harness
#: sends and the string the skill documents cannot drift apart.
INDEPENDENT_RUN_MARKER = "INDEPENDENT RUN: do not read or update any existing audit file"


class AuditSkillError(MetrologyError):
    """The tech-debt-audit skill file could not be resolved or read.

    Names the pack and the expected filename, since the fix is either
    installing the pack or repairing a damaged install — not something the
    caller can infer from a bare path.
    """


def resolve_audit_skill() -> Path:
    """Return the path to the vendored tech-debt-audit skill file.

    Resolves through ``_resolve_bundled`` rather than a relative path, so it
    works from an editable checkout and an installed wheel alike, and so the
    harness and the sync guard exercise the same lookup.
    """
    try:
        pack_dir = _resolve_bundled(_AUDIT_PACK)
    except SkillSourceError as exc:
        raise AuditSkillError(
            f"Could not resolve the '{_AUDIT_PACK}' skill pack: {exc}. "
            f"Install it with 'sq skills install {_AUDIT_PACK}'."
        ) from exc

    skill_path = pack_dir / _AUDIT_SKILL_FILENAME
    if not skill_path.is_file():
        raise AuditSkillError(
            f"The '{_AUDIT_PACK}' pack has no {_AUDIT_SKILL_FILENAME} at {skill_path}. "
            f"Reinstall it with 'sq skills install {_AUDIT_PACK}'."
        )
    return skill_path


def audit_prompt_hash(skill_path: Path) -> str:
    """Return the SHA-256 of the skill file — the instrument's identity.

    Hashed from raw bytes, so any edit at all produces a different hash. An
    edit to the instrument invalidates comparison across the edit, and the
    baseline report groups on this rather than blending runs taken under
    different prompts.
    """
    try:
        return hashlib.sha256(skill_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AuditSkillError(f"Could not read the audit skill at {skill_path}: {exc}") from exc


def build_audit_prompt(skill_path: Path, *, independent_run: bool) -> str:
    """Return the audit prompt: the skill body, plus a run-mode preamble.

    When ``independent_run`` is True the prompt is prefixed with
    ``INDEPENDENT_RUN_MARKER``, which the skill documents as the condition
    under which its repeat-run clause does not apply. Variance runs set it so
    each run is an independent sample; a plain baseline run does not, leaving
    the living-document behavior interactive users get.
    """
    try:
        body = skill_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AuditSkillError(f"Could not read the audit skill at {skill_path}: {exc}") from exc

    if not independent_run:
        return body
    return f"{INDEPENDENT_RUN_MARKER}\n\n{body}"
