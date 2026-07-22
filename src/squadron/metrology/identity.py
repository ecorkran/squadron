"""Project-identity derivation for the metrology store.

Squadron has no project identity today; this slice introduces a stable,
explicit one. Primary source is the git remote URL; fallback is a recorded
``metrology.project_id`` in ``.squadron.toml``. If neither is present the
derivation fails explicitly — it never substitutes a filesystem path.
"""

from __future__ import annotations

import logging
import re
import subprocess

from squadron.config.manager import get_config
from squadron.metrology.errors import MetrologyIdentityError
from squadron.metrology.models import ProjectId, ProjectIdSource

_logger = logging.getLogger(__name__)

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
