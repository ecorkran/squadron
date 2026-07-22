"""Project-identity derivation for the metrology store.

Squadron has no project identity today; this slice introduces a stable,
explicit one. Primary source is the git remote URL; fallback is a recorded
``metrology.project_id`` in ``.squadron.toml``. If neither is present the
derivation fails explicitly — it never substitutes a filesystem path.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from pathlib import Path
from typing import cast

import yaml

from squadron.config.manager import get_config
from squadron.metrology.errors import MetrologyIdentityError, MetrologyTargetError
from squadron.metrology.models import (
    JudgeConfigId,
    JudgeResultRef,
    ProjectId,
    ProjectIdSource,
)

_logger = logging.getLogger(__name__)

#: Frontmatter keys the persisted 300 review file uses. Centralized so the
#: mapping from on-disk field to canonical judge field lives in one place.
_FM_TEMPLATE = "reviewType"
_FM_MODEL = "aiModel"
_FM_VERDICT = "verdict"
_FM_SCORE = "score"
_FM_CRITERIA = "criteria"
_FM_FINDINGS = "findings"
_FM_TIMESTAMP = "dateUpdated"
_FM_SOURCE_DOC = "sourceDocument"

#: Judge fields that must be present to hash a result. A file missing any of
#: these is malformed for calibration purposes — never hash a partial result.
_REQUIRED_JUDGE_FIELDS = (_FM_TEMPLATE, _FM_MODEL, _FM_SCORE)

#: Bounded timeout for the git-remote subprocess so an unresponsive git
#: cannot hang capture. Mirrors the existing git_utils subprocess pattern
#: (check=False) but adds an explicit timeout — a hung call is treated as
#: "remote absent" and falls through to the recorded-id path.
_GIT_REMOTE_TIMEOUT_S = 5.0

#: scp-style remote form: ``[user@]host:path`` (no scheme, single colon
#: separating host from path, path not starting with ``/``).
_SCP_RE = re.compile(r"^(?:[^@/]+@)?(?P<host>[^:/]+):(?P<path>.+)$")


def _read_git_remote_url(cwd: str) -> str | None:
    """Return the origin remote URL, or ``None`` if unavailable.

    Absent git / non-repo / no remote / timeout are all normal "remote
    absent" outcomes, not errors — the caller falls through to the recorded
    id. A timeout is logged at WARNING so a chronically slow git is visible.
    """
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
            timeout=_GIT_REMOTE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        _logger.warning(
            "git remote lookup timed out after %ss in %s; treating remote as absent",
            _GIT_REMOTE_TIMEOUT_S,
            cwd,
        )
        return None
    except (FileNotFoundError, OSError):
        # git not installed / not executable — a normal remote-absent case.
        return None

    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    return url or None


def normalize_remote_url(url: str) -> str:
    """Collapse a git remote URL to one canonical identity string.

    Strips credentials, scheme, and a trailing ``.git``, and normalizes the
    scp-vs-https forms so that ``https://github.com/o/r.git``,
    ``git@github.com:o/r.git`` and ``https://u:p@github.com/o/r`` all yield
    ``github.com/o/r``.
    """
    text = url.strip()

    # scheme://[credentials@]host/path  or  scp-style  user@host:path
    if "://" in text:
        _, _, rest = text.partition("://")
        # Strip any embedded credentials before the host.
        if "@" in rest:
            rest = rest.split("@", 1)[1]
        host_path = rest
    else:
        scp = _SCP_RE.match(text)
        if scp:
            host_path = f"{scp.group('host')}/{scp.group('path')}"
        else:
            host_path = text

    host_path = host_path.rstrip("/")
    if host_path.endswith(".git"):
        host_path = host_path[: -len(".git")]
    return host_path


def derive_project_id(cwd: str) -> ProjectId:
    """Derive the stable project identity for ``cwd``.

    Precedence:
    1. git remote URL (normalized) → source ``remote``.
    2. recorded ``metrology.project_id`` in ``.squadron.toml`` → ``recorded``.
    3. neither → ``MetrologyIdentityError`` naming the fix.

    Never derives identity from a filesystem path.
    """
    remote_url = _read_git_remote_url(cwd)
    if remote_url is not None:
        canonical = normalize_remote_url(remote_url)
        if canonical:
            return ProjectId(value=canonical, source=ProjectIdSource.REMOTE)

    recorded = get_config("metrology.project_id", cwd=cwd)
    if isinstance(recorded, str) and recorded.strip():
        return ProjectId(value=recorded.strip(), source=ProjectIdSource.RECORDED)

    raise MetrologyIdentityError(
        "No stable project identity: this repo has no git remote and no "
        "recorded metrology.project_id. Record one with "
        "'sq config set metrology.project_id <id> --project' before sampling."
    )


# ---------------------------------------------------------------------------
# Judge-result reference and judge-configuration identity
# ---------------------------------------------------------------------------


def read_review_frontmatter(review_file: Path) -> dict[str, object]:
    """Parse the YAML frontmatter of a persisted 300 review file.

    Nothing else in the codebase reads a persisted review back — the review
    flow parses raw LLM output, not the on-disk file — so this is the reader
    for the id-less join.

    Raises:
        MetrologyTargetError: the file is missing, has no frontmatter block,
            or the frontmatter is not a mapping.
    """
    if not review_file.is_file():
        raise MetrologyTargetError(
            f"Review result not found: {review_file}. "
            "Produce it (e.g. 'sq review slice <n>') before sampling."
        )

    text = review_file.read_text(encoding="utf-8")
    # Frontmatter is the first '---'-delimited block. Lenient: tolerate a
    # leading blank line or BOM before the opening fence.
    stripped = text.lstrip("﻿ \n")
    if not stripped.startswith("---"):
        raise MetrologyTargetError(f"Review file has no YAML frontmatter block: {review_file}")
    parts = stripped.split("---", 2)
    if len(parts) < 3:
        raise MetrologyTargetError(f"Review file frontmatter block is not closed: {review_file}")
    try:
        loaded = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise MetrologyTargetError(
            f"Review file frontmatter is not valid YAML ({review_file}): {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise MetrologyTargetError(f"Review file frontmatter did not parse to a mapping: {review_file}")
    return {str(key): value for key, value in cast("dict[object, object]", loaded).items()}


def _canonical_projection(frontmatter: dict[str, object]) -> dict[str, object]:
    """Build the deterministic judge-field projection that is hashed.

    Findings are reduced to a stable, order-independent list keyed by id;
    criteria are sorted by name. Volatile presentation fields (paths already
    relative in the file, formatting) are excluded.
    """
    findings_raw: object = frontmatter.get(_FM_FINDINGS)
    findings: list[dict[str, str]] = []
    if isinstance(findings_raw, list):
        for entry in cast("list[object]", findings_raw):
            if not isinstance(entry, dict):
                continue
            item = cast("dict[object, object]", entry)
            findings.append(
                {
                    "id": str(item.get("id", "")),
                    "severity": str(item.get("severity", "")),
                    "category": str(item.get("category", "")),
                    "summary": str(item.get("summary", "")),
                    "location": str(item.get("location", "")),
                }
            )
    findings.sort(key=lambda finding: finding["id"])

    criteria_raw: object = frontmatter.get(_FM_CRITERIA)
    criteria: dict[str, object] = {}
    if isinstance(criteria_raw, dict):
        typed_criteria = cast("dict[object, object]", criteria_raw)
        criteria = {str(name): typed_criteria[name] for name in sorted(typed_criteria, key=str)}

    return {
        "verdict": frontmatter.get(_FM_VERDICT),
        "score": frontmatter.get(_FM_SCORE),
        "criteria": criteria,
        "template_name": frontmatter.get(_FM_TEMPLATE),
        "model": frontmatter.get(_FM_MODEL),
        "timestamp": frontmatter.get(_FM_TIMESTAMP),
        "findings": findings,
    }


def _require_judge_fields(frontmatter: dict[str, object], review_file: Path) -> None:
    """Fail fast if a required judge field is absent — never hash partials."""
    missing = [field for field in _REQUIRED_JUDGE_FIELDS if frontmatter.get(field) in (None, "")]
    if missing:
        raise MetrologyTargetError(
            f"Review file {review_file} is missing required judge field(s): "
            f"{', '.join(missing)}. Cannot reference a partial result."
        )


def _relative_review_path(review_file: Path, cwd: str) -> str:
    """Return the review path relative to ``cwd`` (posix), or its name."""
    resolved = review_file.resolve()
    root = Path(cwd).resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        # Outside cwd (e.g. an absolute path elsewhere) — fall back to the
        # filename so the reference stays machine-independent.
        return review_file.name


def derive_result_ref(
    review_file: Path,
    project_id: ProjectId,
    cwd: str = ".",
) -> JudgeResultRef:
    """Content-address a persisted judge result.

    The hash is a SHA-256 over the canonical judge-field projection, so the
    same result yields the same hash and a materially different result yields
    a different one. Missing / malformed / partial files raise
    ``MetrologyTargetError``.
    """
    frontmatter = read_review_frontmatter(review_file)
    _require_judge_fields(frontmatter, review_file)
    projection = _canonical_projection(frontmatter)
    canonical_json = json.dumps(projection, sort_keys=True, ensure_ascii=False)
    content_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    return JudgeResultRef(
        project_id=project_id.value,
        relative_review_path=_relative_review_path(review_file, cwd),
        content_hash=content_hash,
    )


def _template_content_hash(template_name: str) -> str | None:
    """Hash the resolved template's behavior-defining content.

    Never fabricates: a ``reviewType`` that doesn't map cleanly to a known
    template yields ``None`` (322 decides how the version key is finalized).
    ``ReviewTemplate`` holds no raw-YAML field, so the hash is taken over the
    template's identity-bearing fields (the prompt, model, and judge block
    that define its scoring behavior), not the file bytes.
    """
    # Imported lazily: the review.templates package pulls in the review
    # subsystem, which the metrology core otherwise does not need.
    from squadron.review.templates import get_template

    template = get_template(template_name)
    if template is None:
        return None
    behavior = {
        "name": template.name,
        "description": template.description,
        "system_prompt": template.system_prompt,
        "model": template.model,
        "prompt_template": template.prompt_template,
        "judge": template.judge,
    }
    canonical = json.dumps(behavior, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def derive_judge_config_id(review_file: Path) -> JudgeConfigId:
    """Derive ``(template_name, model, template_content_hash)`` for a result.

    Reads the persisted review's frontmatter; raises ``MetrologyTargetError``
    if the required template/model fields are absent.
    """
    frontmatter = read_review_frontmatter(review_file)
    _require_judge_fields(frontmatter, review_file)
    template_name = str(frontmatter[_FM_TEMPLATE])
    model = str(frontmatter[_FM_MODEL])
    return JudgeConfigId(
        template_name=template_name,
        model=model,
        template_content_hash=_template_content_hash(template_name),
    )
