"""Pre-emption fragments: static guidance generated from a stored baseline.

The intervention half of the audit oracle. 323 measured what a project's
audit finds repeatedly; this module turns that into short static text a
pipeline can opt into prepending to a dispatch prompt.

Three properties are deliberate and load-bearing:

**The guidance is a fixed lookup table, not generated prose.**
``CATEGORY_GUIDANCE`` is human-authored, one line per ``AuditCategory``.
Deriving it from findings' ``summary`` fields would reintroduce exactly the
run-to-run non-determinism 323 spent the slice normalizing away, and would
make the fragment's content a function of which particular audit run
happened to be latest.

**A fragment is frozen at generation.** It is written to a file, stamped
with the source baseline's ``audit_prompt_hash``/``measured_at``, and never
recomputed at dispatch time — dispatch does not query the metrology store.
Staleness is therefore detectable (``check_freshness``) rather than hidden
behind a silently-changing prompt.

**Reads degrade, they do not raise.** ``read_fragment_header`` and
``read_fragment_body`` return ``None`` on a missing, unreadable, or
malformed file. Their dispatch-time caller must never fail a dispatch over
a fragment problem: a missing fragment has no measurement to poison, which
is what makes this asymmetric with 323's audit-run failure handling.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from squadron.metrology.audit_models import (
    AuditCategory,
    PreemptionFragment,
    ProjectBaseline,
)
from squadron.metrology.audit_models import (
    FreshnessResult as FreshnessResult,
)

__all__ = [
    "CATEGORY_GUIDANCE",
    "FRAGMENT_HEADER_HASH_KEY",
    "FRAGMENT_HEADER_MEASURED_AT_KEY",
    "check_freshness",
    "fragment_path_for",
    "read_fragment_body",
    "read_fragment_header",
    "render_fragment",
    "write_fragment",
]

#: One short corrective instruction per issue class. Fixed and
#: human-authored — see this module's docstring for why this is not
#: generated from audit output. A category added to ``AuditCategory``
#: without a line here fails ``tests/metrology/test_preemption.py``.
CATEGORY_GUIDANCE: dict[AuditCategory, str] = {
    AuditCategory.ARCHITECTURAL_DECAY: (
        "Architectural decay: keep new code behind the existing module "
        "boundaries — do not add cross-layer imports or reach around an "
        "established interface for convenience."
    ),
    AuditCategory.CONSISTENCY_ROT: (
        "Consistency rot: follow the conventions already present in the "
        "files you touch (naming, structure, error shapes) rather than "
        "introducing a second way of doing the same thing."
    ),
    AuditCategory.TYPE_CONTRACT_DEBT: (
        "Type-contract debt: annotate every new signature and attribute "
        "precisely — no bare containers, no implicit Any, no widening a "
        "return type to avoid a narrow one."
    ),
    AuditCategory.TEST_DEBT: (
        "Test debt: land tests with the code they cover, including the "
        "failure paths — not only the success case."
    ),
    AuditCategory.DEPENDENCY_CONFIG_DEBT: (
        "Dependency and config debt: do not hard-code values that belong in "
        "config, and do not add a dependency where existing ones suffice."
    ),
    AuditCategory.PERFORMANCE_RESOURCE: (
        "Performance and resource use: bound loops and I/O over unbounded "
        "inputs, and release or context-manage every resource you acquire."
    ),
    AuditCategory.ERROR_HANDLING_OBSERVABILITY: (
        "Error handling and observability: catch specific exceptions, never "
        "swallow one silently, and make each failure path observable via a "
        "log at WARNING or above."
    ),
    AuditCategory.SECURITY_HYGIENE: (
        "Security hygiene: no credentials or secrets in source, validate "
        "input at the boundary, and never interpolate untrusted values into "
        "a query or command string."
    ),
    AuditCategory.DOCUMENTATION_DRIFT: (
        "Documentation drift: update the docstrings and docs that describe "
        "behavior you change, in the same edit that changes it."
    ),
    AuditCategory.OTHER: (
        "Other recurring issues: prefer the smallest change that satisfies "
        "the requirement, and leave the code no harder to read than you "
        "found it."
    ),
}

#: Machine-parseable header keys written above the fragment body. Defined
#: once and used by both the writer and the reader so the two can never
#: drift into disagreeing about the format.
FRAGMENT_HEADER_HASH_KEY = "audit_prompt_hash"
FRAGMENT_HEADER_MEASURED_AT_KEY = "measured_at"

_HEADER_DELIMITER = "---"
_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def _sanitize_project_id(value: str) -> str:
    """Reduce a project id to a filesystem-safe basename.

    Project ids are git-remote-derived and routinely contain ``/`` and
    ``:``. Collapsing every unsafe run to a single ``-`` is lossy across
    ids that differ only in punctuation; the fragment's own header carries
    the authoritative project identity, so the filename is a convenience,
    not an identifier.
    """
    sanitized = _UNSAFE_FILENAME_CHARS.sub("-", value).strip("-")
    if not sanitized:
        raise ValueError(f"project id has no filesystem-safe characters: {value!r}")
    return sanitized


def fragment_path_for(project_id_value: str, *, directory: Path) -> Path:
    """The conventional fragment path for a project within ``directory``.

    Shared by the writer and by ``--check`` so a freshness check can never
    look somewhere other than where ``write_fragment`` writes.
    """
    return directory / f"{_sanitize_project_id(project_id_value)}.md"


def render_fragment(baseline: ProjectBaseline) -> PreemptionFragment:
    """Render a project's baseline into static pre-emption guidance.

    Selection is presence-based: any category with a nonzero baseline count
    contributes its guidance line. It is deliberately *not* floor-filtered —
    floor precision bounds the interpretation of a delta, which is the
    delta report's job; a category the audit finds at all is worth naming
    in guidance regardless of how noisily it is counted.
    """
    present = [cell.category for cell in baseline.cells if cell.count > 0]
    measured = baseline.measured_at.isoformat()
    if present:
        header = (
            f"The tech-debt audit of this project (baseline measured "
            f"{measured}) has repeatedly found the issue classes below. "
            f"Avoid introducing them in this work:"
        )
        body = "\n".join(f"- {CATEGORY_GUIDANCE[category]}" for category in present)
    else:
        # Never an empty body: at the dispatch side an empty prepend is
        # indistinguishable from having no fragment at all.
        header = (
            f"The tech-debt audit of this project (baseline measured "
            f"{measured}) found no recurring issue classes at baseline. "
            f"Maintain the existing standard:"
        )
        body = "- No issue classes were present at baseline."
    return PreemptionFragment(
        project_id=baseline.project_id,
        audit_prompt_hash=baseline.audit_prompt_hash,
        measured_at=baseline.measured_at,
        text=f"{header}\n{body}",
    )


def write_fragment(fragment: PreemptionFragment, *, directory: Path) -> Path:
    """Write a fragment with a machine-parseable header, overwriting any prior.

    Overwrite is the intended behavior: a project has exactly one current
    fragment, and keeping superseded ones would invite dispatching against
    a baseline that is no longer the project's.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = fragment_path_for(fragment.project_id.value, directory=directory)
    header = "\n".join(
        [
            _HEADER_DELIMITER,
            f"{FRAGMENT_HEADER_HASH_KEY}: {fragment.audit_prompt_hash}",
            f"{FRAGMENT_HEADER_MEASURED_AT_KEY}: {fragment.measured_at.isoformat()}",
            _HEADER_DELIMITER,
        ]
    )
    path.write_text(f"{header}\n\n{fragment.text}\n", encoding="utf-8")
    return path


def _read_text(path: Path) -> str | None:
    """Read a fragment file, or ``None`` if it cannot be read.

    ``OSError`` covers the missing, unreadable, and is-a-directory cases
    uniformly; the caller distinguishes *which* mode occurred for its
    warning, but none of them may propagate.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def read_fragment_header(path: Path) -> tuple[str, datetime] | None:
    """Parse only the header, returning ``(audit_prompt_hash, measured_at)``.

    Returns ``None`` — never raises — when the file is absent, empty, or
    the header is missing/truncated/unparseable, because this is also the
    dispatch-time read path where a fragment problem must degrade rather
    than fail the dispatch.

    Parsing is lenient about layout (surrounding whitespace, key order),
    strict only about the two keys being present and the timestamp being
    parseable.
    """
    text = _read_text(path)
    if text is None or not text.strip():
        return None

    found: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == _HEADER_DELIMITER:
            # Closing delimiter once both keys are in hand; otherwise the
            # opening one, which carries nothing.
            if found:
                break
            continue
        key, separator, value = stripped.partition(":")
        if not separator:
            continue
        key = key.strip()
        if key in (FRAGMENT_HEADER_HASH_KEY, FRAGMENT_HEADER_MEASURED_AT_KEY):
            found[key] = value.strip()

    audit_prompt_hash = found.get(FRAGMENT_HEADER_HASH_KEY)
    raw_measured_at = found.get(FRAGMENT_HEADER_MEASURED_AT_KEY)
    if not audit_prompt_hash or not raw_measured_at:
        return None
    try:
        measured_at = datetime.fromisoformat(raw_measured_at)
    except ValueError:
        return None
    return audit_prompt_hash, measured_at


def read_fragment_body(path: Path) -> str | None:
    """Read the fragment text below the header, or ``None`` if unusable.

    Requires a parseable header: a file whose header is malformed is not a
    fragment, and prepending its raw contents to a dispatch prompt would
    inject arbitrary unvalidated text. Returns ``None`` for an empty body
    for the same reason ``render_fragment`` never emits one.
    """
    if read_fragment_header(path) is None:
        return None
    text = _read_text(path)
    if text is None:
        return None

    lines = text.splitlines()
    closing_index: int | None = None
    seen_opening = False
    for index, line in enumerate(lines):
        if line.strip() != _HEADER_DELIMITER:
            continue
        if seen_opening:
            closing_index = index
            break
        seen_opening = True
    if closing_index is None:
        return None

    body = "\n".join(lines[closing_index + 1 :]).strip()
    return body or None


def check_freshness(fragment_path: Path, current_baseline: ProjectBaseline) -> FreshnessResult:
    """Compare a written fragment's header against the current baseline.

    ``is_current`` is ``True`` only on an exact ``audit_prompt_hash`` match:
    the hash is the instrument identity, so a fragment generated under a
    different audit prompt is stale by definition even if its timestamp is
    recent.
    """
    header = read_fragment_header(fragment_path)
    if header is None:
        return FreshnessResult(
            is_current=False,
            fragment_audit_prompt_hash=None,
            current_audit_prompt_hash=current_baseline.audit_prompt_hash,
            fragment_measured_at=None,
            note=(
                f"fragment absent or unreadable at {fragment_path} — "
                f"run 'sq metrology preempt generate' to create it"
            ),
        )

    fragment_hash, fragment_measured_at = header
    if fragment_hash == current_baseline.audit_prompt_hash:
        return FreshnessResult(
            is_current=True,
            fragment_audit_prompt_hash=fragment_hash,
            current_audit_prompt_hash=current_baseline.audit_prompt_hash,
            fragment_measured_at=fragment_measured_at,
            note=f"current — generated from baseline {fragment_hash}",
        )
    return FreshnessResult(
        is_current=False,
        fragment_audit_prompt_hash=fragment_hash,
        current_audit_prompt_hash=current_baseline.audit_prompt_hash,
        fragment_measured_at=fragment_measured_at,
        note=(
            f"stale — fragment was generated from baseline {fragment_hash}, "
            f"but the current baseline is {current_baseline.audit_prompt_hash}"
        ),
    )
