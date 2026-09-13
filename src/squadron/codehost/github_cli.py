"""The GitHub implementation of :class:`~squadron.codehost.protocol.CodeHost`.

Every host call goes through ``gh``, and every ``gh`` call goes through one
private helper so the hostname, the environment, and the timeout are applied in
exactly one place. Failures are classified on *structure* — exit codes, HTTP
status fields, GraphQL error types — never by matching message text, which
changes between ``gh`` releases without notice.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any, NoReturn, cast

from squadron.codehost.errors import (
    AmbiguousBranchPullRequestsError,
    CodeHostError,
    GitHubCliMissingError,
    HostCommandTimeoutError,
    HostRequestRejectedError,
    HostResponseMalformedError,
    HostUnauthenticatedError,
    HostUnreachableError,
    NoOpenPullRequestForBranchError,
    OperatorUnidentifiedError,
    PullRequestNotFoundError,
    TargetUnresolvableError,
)
from squadron.codehost.github_config import read_gh_hosts
from squadron.codehost.github_parse import (
    dig,
    dig_list,
    require_int,
    require_str,
    to_discussions,
    to_resolved,
)
from squadron.codehost.github_queries import (
    PR_FOR_BRANCH_QUERY,
    PR_QUERY,
    REVIEW_THREADS_QUERY,
)
from squadron.codehost.models import (
    OperatorIdentity,
    PullRequestRecord,
    RepositoryLocator,
    ResolvedPullRequest,
    ReviewDiscussion,
)
from squadron.codehost.targets import PullRequestTarget
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
)

_logger = logging.getLogger(__name__)

#: Wall-clock bound on any single ``gh`` invocation.
HOST_COMMAND_TIMEOUT_SECONDS = 30

#: How many pages of review threads to walk before giving up. A silently
#: truncated list is a review that quietly misses comments, so hitting this
#: logs at WARNING rather than returning short without comment.
MAX_DISCUSSION_PAGES = 10

#: The one host recognized without a ``hosts.yml`` entry.
DEFAULT_GITHUB_HOST = "github.com"

#: ``gh`` exits 4 specifically for an authentication failure.
_GH_AUTH_EXIT_CODE = 4

#: Environment applied to every ``gh`` call. A wedged prompt blocks forever, and
#: an update banner or colour codes land in output this module parses.
_GH_ENV: Mapping[str, str] = {
    "GH_PROMPT_DISABLED": "1",
    "GH_NO_UPDATE_NOTIFIER": "1",
    "NO_COLOR": "1",
}


def _log_and_raise(error: CodeHostError) -> NoReturn:
    """Log a classified failure once, then raise it.

    Every failure path is observable before it propagates; no silent path.
    """
    _logger.warning("%s: %s", type(error).__name__, error)
    raise error


class GitHubCli:
    """Reads GitHub through the operator's ``gh``.

    ``hosts`` is the set this implementation answers for — built once by the
    caller from ``gh``'s hosts file plus ``github.com``.
    """

    def __init__(self, runner: ProcessRunner, hosts: frozenset[str]) -> None:
        self._runner = runner
        self._hosts = hosts

    def serves_host(self, hostname: str) -> bool:
        """Whether this implementation answers for ``hostname``."""
        return hostname in self._hosts

    def resolve_pull_request(
        self, locator: RepositoryLocator, target: PullRequestTarget
    ) -> ResolvedPullRequest:
        """Resolve a target to a full pull-request record."""
        number = target.number
        if number is None:
            number = self._number_for_branch(locator, self._branch_for(target))
        node = self._pull_request_node(locator, number)
        return to_resolved(node, locator)

    def _branch_for(self, target: PullRequestTarget) -> str:
        """The branch a non-numeric target refers to."""
        if target.branch is not None:
            return target.branch
        # Form 1: whatever the checkout is on right now.
        result = self._runner.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=None,
            timeout=HOST_COMMAND_TIMEOUT_SECONDS,
        )
        branch = result.stdout.strip()
        if result.returncode != 0 or not branch or branch == "HEAD":
            raise TargetUnresolvableError(
                "HEAD is detached, so there is no branch to resolve a pull request from",
                fix_hint="Check out a branch, or name the pull request by number or URL.",
            )
        return branch

    def _number_for_branch(self, locator: RepositoryLocator, branch: str) -> int:
        """Find the one open pull request whose head is ``branch``.

        Asks for two so one can be told from many without a second page.
        """
        payload = self._graphql(
            locator.host,
            PR_FOR_BRANCH_QUERY,
            owner=locator.owner,
            name=locator.repository,
            branch=branch,
        )
        nodes = dig_list(payload, ("data", "repository", "pullRequests", "nodes"))
        if not nodes:
            raise NoOpenPullRequestForBranchError(
                f"no open pull request has head {branch!r}",
                fix_hint="Open one, or name the pull request by number.",
            )
        if len(nodes) > 1:
            numbers = ", ".join(str(node.get("number")) for node in nodes)
            raise AmbiguousBranchPullRequestsError(
                f"branch {branch!r} has several open pull requests: {numbers}",
                fix_hint="Name the one you mean by number.",
            )
        return require_int(nodes[0], "number", ("gh", "graphql"))

    def _pull_request_node(self, locator: RepositoryLocator, number: int) -> Mapping[str, Any]:
        """Fetch one pull request's fields."""
        payload = self._graphql(
            locator.host,
            PR_QUERY,
            owner=locator.owner,
            name=locator.repository,
            number=str(number),
        )
        node = dig(payload, ("data", "repository", "pullRequest"))
        if not isinstance(node, dict):
            raise PullRequestNotFoundError(
                f"no pull request #{number} in {locator.owner}/{locator.repository}"
            )
        return cast(dict[str, Any], node)

    def default_branch(self, locator: RepositoryLocator) -> str:
        """The repository's default branch."""
        payload = self._rest(locator.host, f"repos/{locator.owner}/{locator.repository}")
        return require_str(payload, "default_branch", ("gh", "api"))

    def branch_exists(self, locator: RepositoryLocator, branch: str) -> bool:
        """Whether ``branch`` exists on the host.

        A missing branch is an answer, not a failure, so 404 returns ``False``.
        Anything else raises.
        """
        path = f"repos/{locator.owner}/{locator.repository}/branches/{branch}"
        result = self._run_gh(["api", path], host=locator.host)
        if result.returncode == 0:
            return True
        error = _classify_failure(result, locator.host)
        if isinstance(error, HostRequestRejectedError) and error.status == 404:
            return False
        _log_and_raise(error)

    def identify_operator(self, hostname: str) -> OperatorIdentity:
        """Who the operator is authenticated as on ``hostname``."""
        payload = self._rest(hostname, "user")
        login = payload.get("login")
        if not login:
            raise OperatorUnidentifiedError(
                f"gh returned no login for {hostname}",
                fix_hint=f"gh auth login --hostname {hostname}",
            )
        return OperatorIdentity(host=hostname, login=str(login))

    def list_unresolved_discussions(self, record: PullRequestRecord) -> list[ReviewDiscussion]:
        """Every unresolved review thread, paged to a bounded depth."""
        discussions: list[ReviewDiscussion] = []
        cursor: str | None = None
        for page in range(MAX_DISCUSSION_PAGES):
            payload = self._graphql(
                record.host,
                REVIEW_THREADS_QUERY,
                owner=record.owner,
                name=record.repository,
                number=str(record.number),
                cursor=cursor or "",
            )
            threads = dig(payload, ("data", "repository", "pullRequest", "reviewThreads"))
            if not isinstance(threads, dict):
                raise HostResponseMalformedError(
                    ("gh", "graphql"), "reviewThreads missing from response"
                )
            thread_map = cast(dict[str, Any], threads)
            discussions.extend(to_discussions(thread_map))

            page_info = thread_map.get("pageInfo")
            if not isinstance(page_info, dict):
                break
            info = cast(dict[str, Any], page_info)
            if not info.get("hasNextPage"):
                return discussions
            cursor = str(info.get("endCursor") or "")
            if page == MAX_DISCUSSION_PAGES - 1:
                # A silently short list is a review that quietly misses
                # comments, so say so rather than returning truncated.
                _logger.warning(
                    "stopped at %s pages of review threads for %s; %s collected and more remain",
                    MAX_DISCUSSION_PAGES,
                    record.key,
                    len(discussions),
                )
        return discussions

    def _graphql(self, host: str, query: str, **variables: str) -> Mapping[str, Any]:
        """Run a GraphQL query, returning the parsed payload."""
        args = ["api", "graphql"]
        for key, value in variables.items():
            args += ["-F", f"{key}={value}"]
        args += ["-f", f"query={query}"]
        return self._json(args, host=host)

    def _rest(self, host: str, path: str) -> Mapping[str, Any]:
        """Run a REST call, returning the parsed payload."""
        return self._json(["api", path], host=host)

    def _json(self, args: Sequence[str], *, host: str) -> Mapping[str, Any]:
        """Invoke gh and parse its stdout as a JSON object."""
        result = self._run_gh(args, host=host)
        if result.returncode != 0:
            _log_and_raise(_classify_failure(result, host))
        parsed = _try_parse_json(result.stdout)
        if not isinstance(parsed, dict):
            raise HostResponseMalformedError(tuple(result.argv), "expected a JSON object on stdout")
        payload = cast(dict[str, Any], parsed)
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            # GraphQL reports failure in-band with exit 0.
            _log_and_raise(_classify_graphql_errors(cast(list[Any], errors), host))
        return payload

    def _run_gh(self, args: Sequence[str], *, host: str, cwd: str | None = None) -> ProcessResult:
        """Invoke ``gh``. The only place in this module that does.

        Appends ``--hostname`` so the host always comes from the resolved
        remote or target, never from a default and never from ``GH_HOST``.
        """
        argv = ["gh", *args, "--hostname", host]
        try:
            return self._runner.run(
                argv,
                cwd=cwd,
                timeout=HOST_COMMAND_TIMEOUT_SECONDS,
                env=_GH_ENV,
            )
        except ProcessNotFoundError as exc:
            _logger.warning("gh is not on PATH")
            raise GitHubCliMissingError(
                "the GitHub CLI (gh) is not on PATH",
                fix_hint="brew install gh — or see https://cli.github.com",
            ) from exc
        except ProcessTimedOutError as exc:
            _logger.warning("gh exceeded %ss: %s", exc.timeout, " ".join(exc.argv))
            raise HostCommandTimeoutError(exc.argv, exc.timeout) from exc


def _classify_failure(result: ProcessResult, host: str) -> CodeHostError:
    """Turn a non-zero ``gh`` exit into a typed error.

    Structural signals only, applied in order. Message text is never matched:
    it is not a contract and changes between ``gh`` releases.
    """
    if result.returncode == _GH_AUTH_EXIT_CODE:
        return HostUnauthenticatedError(
            f"not authenticated to {host}",
            fix_hint=f"gh auth login --hostname {host}",
        )

    parsed = _try_parse_json(result.stdout)

    if isinstance(parsed, dict):
        # json.loads yields Any; narrow once here so the accessors below are
        # typed rather than each needing its own cast.
        payload = cast(dict[str, Any], parsed)

        status = payload.get("status")
        if status is not None:
            return _classify_http_status(str(status), payload, host)

        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            return _classify_graphql_errors(cast(list[Any], errors), host)

    # Residual bucket: gh ran but produced no HTTP answer we can read. The
    # verbatim stderr is what tells the operator the real cause — including a
    # squadron-side argv bug, which would otherwise vanish into "unreachable".
    return HostUnreachableError(
        f"{host} could not be reached: {result.stderr.strip() or '(no stderr)'}"
    )


def _classify_http_status(status: str, payload: Mapping[str, Any], host: str) -> CodeHostError:
    """Map a REST ``status`` field onto a typed error."""
    message = str(payload.get("message", "")) or f"request to {host} failed"
    if status == "401":
        return HostUnauthenticatedError(message, fix_hint=f"gh auth login --hostname {host}")
    if status == "404":
        # The caller turns this into the operation-specific not-found error;
        # it alone knows whether a PR, a branch, or a repository was missing.
        return HostRequestRejectedError(404, message)
    try:
        code = int(status)
    except ValueError:
        return HostResponseMalformedError(("gh",), f"non-numeric status field: {status!r}")
    return HostRequestRejectedError(code, message)


def _classify_graphql_errors(errors: Sequence[Any], host: str) -> CodeHostError:
    """Map a GraphQL ``errors`` array onto a typed error."""
    first = cast(dict[str, Any], errors[0]) if isinstance(errors[0], dict) else {}
    error_type = str(first.get("type", ""))
    message = str(first.get("message", "")) or f"GraphQL request to {host} failed"
    if error_type == "NOT_FOUND":
        return HostRequestRejectedError(404, message)
    return HostRequestRejectedError(0, message)


def _try_parse_json(text: str) -> object | None:
    """Parse ``text`` as JSON, or return ``None`` when it is not JSON.

    Not an error path: much of what ``gh`` writes on failure is plain prose,
    and the caller falls through to the unreachable bucket.
    """
    stripped = text.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def build_github_host(runner: ProcessRunner) -> GitHubCli:
    """Construct a ``GitHubCli`` for the operator's configured hosts.

    The one entry point the CLI uses. ``github.com`` is always included: it is
    the host recognized without a ``hosts.yml`` entry.
    """
    hosts = frozenset({DEFAULT_GITHUB_HOST, *read_gh_hosts()})
    return GitHubCli(runner, hosts)
