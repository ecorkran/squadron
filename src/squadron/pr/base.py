"""Base-branch selection for ``sq pr create`` (D1).

Three outcomes for the integration-branch term, not two: a configured
integration branch that is absent from the host is a refusal, never a
fall-through to the host default.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from squadron.codehost.errors import CodeHostError
from squadron.codehost.models import RepositoryLocator
from squadron.codehost.protocol import CodeHost
from squadron.review.git_utils import INTEGRATION_BRANCH_KEY


class BaseSource(StrEnum):
    """Which rule chose the base branch. Printed with the result, never inferred."""

    FLAG = "flag"
    INTEGRATION_BRANCH = "integration-branch"
    HOST_DEFAULT = "host-default"


@dataclass(frozen=True)
class BaseSelection:
    """The chosen base branch and which rule chose it."""

    base: str
    source: BaseSource


class IntegrationBranchAbsentError(CodeHostError):
    """The configured integration branch does not exist on the host.

    Refuses rather than falling through to the host default — a configured
    integration branch is a statement about where this work merges, and a
    host that has never heard of it means the configuration and the host
    disagree, not that no integration branch is set (D1).
    """


def _read_integration_branch(cf_client: object | None = None) -> str:
    """Return the configured integration branch, or ``""`` when unset or unreadable.

    Unlike ``resolve_diff_base``, this never degrades a *found* value — only
    an unreachable ``cf`` or an unset key is treated as absent. ``cf_client``
    is injectable for tests, matching ``resolve_diff_base``'s pattern.
    """
    from squadron.integrations.context_forge import (
        ContextForgeClient,
        ContextForgeError,
        ContextForgeNotAvailable,
    )

    if cf_client is None:
        cf_client = ContextForgeClient()

    getter = getattr(cf_client, "get_config", None)
    if getter is None:
        return ""

    try:
        value = str(getter(INTEGRATION_BRANCH_KEY)).strip()
    except (ContextForgeNotAvailable, ContextForgeError):
        return ""
    return value


def select_base(
    host: CodeHost,
    locator: RepositoryLocator,
    *,
    base_flag: str | None,
    cf_client: object | None = None,
) -> BaseSelection:
    """Choose the PR base per D1's table.

    - ``--base`` given: use it verbatim, no host confirmation — the operator
      named it, and a bad value gets a loud 422 from ``open_pull_request``.
    - integration branch set and present on the host: use it.
    - integration branch set and absent from the host: raise, naming it.
    - integration branch unset or empty: the host's default branch.
    """
    if base_flag is not None:
        return BaseSelection(base=base_flag, source=BaseSource.FLAG)

    integration_branch = _read_integration_branch(cf_client)
    if integration_branch:
        if host.branch_exists(locator, integration_branch):
            return BaseSelection(base=integration_branch, source=BaseSource.INTEGRATION_BRANCH)
        raise IntegrationBranchAbsentError(
            f"Configured integration branch {integration_branch!r} does not exist "
            f"on {locator.host}/{locator.owner}/{locator.repository}.",
            fix_hint=(f"Push {integration_branch!r} to the host, or correct git.integration_branch."),
        )

    default = host.default_branch(locator)
    return BaseSelection(base=default, source=BaseSource.HOST_DEFAULT)
