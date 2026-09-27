"""Pinned machine state for the test suite (slice 923, issue #47).

Every value a test sees in place of the host's is defined here once. The pins
are chosen so a hidden host assumption fails on every machine, not only on the
one that happens to differ: a non-``main`` default branch, and a non-UTC,
half-hour-offset timezone.
"""

from __future__ import annotations

from pathlib import Path

from squadron.providers.profiles import BUILT_IN_PROFILES

PINNED_TZ = "Asia/Kolkata"
PINNED_COLUMNS = "80"
PINNED_DEFAULT_BRANCH = "hermetic-default"
PINNED_GIT_USER_NAME = "Squadron Tests"
PINNED_GIT_USER_EMAIL = "tests@squadron.invalid"

#: Env var prefixes owned by squadron: ``ORCH_`` is the ``Settings`` prefix.
SCRUBBED_ENV_PREFIXES = ("ORCH_", "SQUADRON_")
#: Single env vars that change squadron's behavior when inherited from the host.
SCRUBBED_ENV_VARS = ("CLAUDECODE", "GH_CONFIG_DIR", "FORCE_COLOR", "NO_COLOR")
#: The auth fallback in ``providers/auth.py`` — not a profile's ``api_key_env``.
_AUTH_FALLBACK_ENV_VAR = "OPENAI_API_KEY"

#: The developer's real home, captured before any fixture swaps ``HOME``.
#: Used only to restore it for ``host_cf`` tests.
REAL_HOME = Path.home()


def credential_env_vars() -> frozenset[str]:
    """Credential env vars from the built-in provider profiles, plus the auth fallback."""
    names = {p.api_key_env for p in BUILT_IN_PROFILES.values() if p.api_key_env}
    names.add(_AUTH_FALLBACK_ENV_VAR)
    return frozenset(names)


def write_git_config(path: Path) -> Path:
    """Write the session-wide git config that replaces the host's global config."""
    path.write_text(
        f"[init]\n\tdefaultBranch = {PINNED_DEFAULT_BRANCH}\n"
        f"[user]\n\tname = {PINNED_GIT_USER_NAME}\n\temail = {PINNED_GIT_USER_EMAIL}\n"
        "[commit]\n\tgpgsign = false\n"
        "[tag]\n\tgpgsign = false\n"
    )
    return path
