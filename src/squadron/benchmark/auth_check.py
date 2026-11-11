"""Auth check for benchmark producers: resolve aliases, probe in a scrubbed home.

Slice 421 D8. One probe per distinct profile runs ``sq benchmark _auth-probe`` in
a throwaway scrubbed home; a ``no`` is a result, a probe that cannot start is not.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.benchmark.scrubbed_env import (
    CredentialGrant,
    MissingCredentialError,
    ScrubbedEnvironment,
)
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessRunner,
    ProcessTimedOutError,
)
from squadron.models.aliases import resolve_model_alias
from squadron.providers.base import ProfileName

_logger = logging.getLogger(__name__)

PROBE_PROMPT = "Reply with the single word: ok"


class UnresolvedProfileError(Exception):
    """A model alias is unknown or resolves to no provider profile."""

    def __init__(self, alias: str, detail: str) -> None:
        super().__init__(f"model alias '{alias}' {detail}")
        self.alias = alias


def resolve_alias_profile(alias: str) -> tuple[str, ProfileName]:
    """Resolve ``alias`` to ``(model_id, ProfileName)`` or raise naming the alias."""
    model_id, profile = resolve_model_alias(alias)
    if profile is None:
        raise UnresolvedProfileError(alias, "is unknown or has no provider profile")
    try:
        return model_id, ProfileName(profile)
    except ValueError:
        raise UnresolvedProfileError(
            alias, f"names profile '{profile}', which is not a built-in profile"
        ) from None


class ProbeStartError(Exception):
    """The ``sq`` binary cannot start in the scrubbed environment (says nothing of auth)."""

    def __init__(self, sq_path: str, detail: str) -> None:
        super().__init__(f"{sq_path} cannot start in the scrubbed environment: {detail}")
        self.detail = detail


class AuthAnswer(StrEnum):
    YES = "yes"
    NO = "no"
    YES_CARRYOVER_REPLACED = "yes_carryover_replaced"


@dataclass(frozen=True)
class AuthCheckResult:
    profile: ProfileName
    alias: str
    answer: AuthAnswer
    exit_code: int | None
    stderr: str
    detail: str = ""


def run_auth_check(
    aliases: Sequence[str],
    runner: ProcessRunner,
    root: Path,
    harness_env: Mapping[str, str],
    sq_path: str,
    timeout_s: float,
) -> list[AuthCheckResult]:
    """Probe each distinct profile behind ``aliases``; the first alias names its row."""
    resolved = [(alias, *resolve_alias_profile(alias)) for alias in aliases]
    first_alias: dict[ProfileName, str] = {}
    for alias, _model_id, profile in resolved:
        first_alias.setdefault(profile, alias)
    return [
        _probe_profile(profile, alias, runner, root, harness_env, sq_path, timeout_s)
        for profile, alias in first_alias.items()
    ]


def _probe_profile(
    profile: ProfileName,
    alias: str,
    runner: ProcessRunner,
    root: Path,
    harness_env: Mapping[str, str],
    sq_path: str,
    timeout_s: float,
) -> AuthCheckResult:
    sandbox_id = f"authcheck-{uuid.uuid4().hex[:8]}"
    environment = ScrubbedEnvironment(
        root, sandbox_id, CredentialGrant.for_profiles([profile]), harness_env
    )
    try:
        variables = environment.variables(())
    except MissingCredentialError as exc:
        return AuthCheckResult(profile, alias, AuthAnswer.NO, None, str(exc))
    try:
        environment.prepare()
        _preflight(runner, sq_path, environment, variables, timeout_s)
        result = _run_probe(profile, alias, runner, sq_path, environment, variables, timeout_s)
        return _mark_replaced(result, environment)
    finally:
        environment.cleanup()


def _preflight(
    runner: ProcessRunner,
    sq_path: str,
    environment: ScrubbedEnvironment,
    variables: Mapping[str, str],
    timeout_s: float,
) -> None:
    try:
        result = runner.run(
            [sq_path, "--version"],
            cwd=str(environment.home),
            timeout=timeout_s,
            env=variables,
            replace_env=True,
        )
    except (ProcessNotFoundError, ProcessTimedOutError) as exc:
        _logger.error("auth-check preflight could not start: %s", exc)
        raise ProbeStartError(sq_path, str(exc)) from exc
    if result.returncode != 0:
        _logger.error("auth-check preflight exited %s", result.returncode)
        raise ProbeStartError(sq_path, f"exit {result.returncode}: {result.stderr.strip()}")


def _run_probe(
    profile: ProfileName,
    alias: str,
    runner: ProcessRunner,
    sq_path: str,
    environment: ScrubbedEnvironment,
    variables: Mapping[str, str],
    timeout_s: float,
) -> AuthCheckResult:
    try:
        result = runner.run(
            [sq_path, "benchmark", "_auth-probe", "--model", alias],
            cwd=str(environment.home),
            timeout=timeout_s,
            env=variables,
            replace_env=True,
        )
    except ProcessTimedOutError:
        _logger.warning("auth probe for profile %s timed out", profile)
        return AuthCheckResult(profile, alias, AuthAnswer.NO, None, "timed out")
    except ProcessNotFoundError as exc:
        raise ProbeStartError(sq_path, str(exc)) from exc
    answered = result.returncode == 0 and bool(result.stdout.strip())
    return AuthCheckResult(
        profile,
        alias,
        AuthAnswer.YES if answered else AuthAnswer.NO,
        result.returncode,
        result.stderr,
    )


def _mark_replaced(result: AuthCheckResult, environment: ScrubbedEnvironment) -> AuthCheckResult:
    """A carried credential copy that changed means the tool rewrote the login."""
    replaced = environment.changed_carried_paths
    if not replaced:
        return result
    detail = "carried credential rewritten by the probe: " + ", ".join(str(path) for path in replaced)
    answer = AuthAnswer.YES_CARRYOVER_REPLACED if result.answer is AuthAnswer.YES else result.answer
    return AuthCheckResult(
        result.profile, result.alias, answer, result.exit_code, result.stderr, detail
    )
