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
    PullRequestCreationRejectedError,
    PullRequestNotFoundError,
    TargetUnresolvableError,
)
from squadron.codehost.github_config import read_gh_hosts
from squadron.codehost.github_parse import (
    dig,
    dig_list,
    require,
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
    FetchedRange,
    HostComment,
    OperatorIdentity,
    PullRequestRecord,
    RepositoryLocator,
    ResolvedPullRequest,
    ReviewDiscussion,
)
from squadron.codehost.refs import fetch_and_range
from squadron.codehost.targets import PullRequestTarget
from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
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


def _nested_login(comment: Mapping[str, Any]) -> str:
    """The login of a comment's author, or empty when absent."""
    user = comment.get("user")
    if not isinstance(user, dict):
        return ""
    return str(cast(Mapping[str, Any], user).get("login", ""))


def _nested_sha(payload: Mapping[str, Any]) -> str:
    """The head sha from a pull-request payload's ``head`` object."""
    head = payload.get("head")
    if not isinstance(head, dict):
        return ""
    return str(cast(Mapping[str, Any], head).get("sha", ""))


def _to_comment(payload: Mapping[str, Any], argv: Sequence[str]) -> HostComment:
    """Build a comment record from a REST comment payload."""
    return HostComment(
        id=str(require(payload, "id", argv)),
        author_login=_nested_login(payload),
        body=str(payload.get("body") or ""),
        url=str(payload.get("html_url") or ""),
    )


def _require_object(result: ProcessResult, argv: Sequence[str]) -> Mapping[str, Any]:
    """Parse stdout as a JSON object, or report drift."""
    parsed = _try_parse_json(result.stdout)
    if not isinstance(parsed, dict):
        raise HostResponseMalformedError(tuple(argv), "expected a JSON object on stdout")
    return cast(dict[str, Any], parsed)


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

    @property
    def runner(self) -> ProcessRunner:
        """The process runner every call from this host goes through.

        Exposed so a caller's *git* work — remote enumeration, fetching —
        travels the same seam as the host calls. Without it the factory is only
        half a seam: substituting the host redirects ``gh`` while git still
        shells out for real, which is precisely the gap that let a test assert
        against a host it never exercised.
        """
        return self._runner

    def serves_host(self, hostname: str) -> bool:
        """Whether this implementation answers for ``hostname``."""
        return hostname in self._hosts

    def resolve_pull_request(
        self, locator: RepositoryLocator, target: PullRequestTarget, *, cwd: str
    ) -> ResolvedPullRequest:
        """Resolve a target to a full pull-request record."""
        number = target.number
        if number is None:
            number = self._number_for_branch(locator, self._branch_for(target, cwd=cwd))
        node = self._pull_request_node(locator, number)
        return to_resolved(node, locator)

    def _branch_for(self, target: PullRequestTarget, *, cwd: str) -> str:
        """The branch a non-numeric target refers to.

        ``cwd`` is the resolved repository root, not the process's working
        directory: reading HEAD from the latter would name the branch of
        whatever repository happens to sit there, which is either a wrong
        answer or a "detached HEAD" that misdiagnoses "no repository here".
        """
        if target.branch is not None:
            return target.branch
        # Form 1: whatever the checkout is on right now.
        result = self._runner.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
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

    def fetch_pull_request_refs(
        self, resolved: ResolvedPullRequest, *, remote_name: str, cwd: str
    ) -> FetchedRange:
        """Fetch this pull request's base and head, and describe the range.

        GitHub's refspec conventions live here; the git work is delegated.
        ``refs/pull/<n>/head`` is fetchable for merged and cross-repository
        pull requests alike, so a fork head needs no second remote.

        Takes the resolved pull request because ``base_sha`` — the base tip at
        resolution, which makes the post-fetch check exact — is carried there
        rather than on the record.
        """
        record = resolved.record
        return fetch_and_range(
            self._runner,
            cwd=cwd,
            remote_name=remote_name,
            namespace=record.number,
            base_refspec_source=f"refs/heads/{record.base_ref}",
            head_refspec_source=f"refs/pull/{record.number}/head",
            expected_base_sha=resolved.base_sha,
            expected_head_sha=record.head_sha,
        )

    def find_marked_comments(self, record: PullRequestRecord, *, marker: str) -> list[HostComment]:
        """Every comment carrying ``marker``, any author, oldest first.

        ``marker`` is supplied by the caller: its format is 384's to define,
        and inventing one here would fix a convention this slice has no
        business fixing. The author filter that once lived here is gone —
        partitioning by author is the caller's job, because the caller is
        what reports the non-own matches (D1).
        """
        path = f"repos/{record.owner}/{record.repository}/issues/{record.number}/comments"
        comments = self._json_list(["api", "--paginate", path], host=record.host)

        marked = [comment for comment in comments if marker in str(comment.get("body") or "")]
        # Oldest first: a missing created_at sorts first under an empty-string
        # key, matching how the prior min() treated it.
        marked.sort(key=lambda comment: str(comment.get("created_at") or ""))
        return [
            HostComment(
                id=str(require(comment, "id", ("gh", "api", path))),
                author_login=_nested_login(comment),
                body=str(comment.get("body") or ""),
                url=str(comment.get("html_url") or ""),
            )
            for comment in marked
        ]

    def post_comment(self, record: PullRequestRecord, body: str) -> HostComment:
        """Add a comment to the pull request."""
        path = f"repos/{record.owner}/{record.repository}/issues/{record.number}/comments"
        payload = self._json(
            ["api", "-X", "POST", path, "--input", "-"],
            host=record.host,
            stdin=_body_payload(body),
        )
        return _to_comment(payload, ("gh", "api", path))

    def update_comment(self, record: PullRequestRecord, comment_id: str, body: str) -> HostComment:
        """Replace the body of a comment we previously posted."""
        path = f"repos/{record.owner}/{record.repository}/issues/comments/{comment_id}"
        payload = self._json(
            ["api", "-X", "PATCH", path, "--input", "-"],
            host=record.host,
            stdin=_body_payload(body),
        )
        return _to_comment(payload, ("gh", "api", path))

    def open_pull_request(
        self,
        locator: RepositoryLocator,
        *,
        base: str,
        head: str,
        title: str,
        body: str,
    ) -> PullRequestRecord:
        """Open a pull request, with the body over stdin."""
        path = f"repos/{locator.owner}/{locator.repository}/pulls"
        # The whole request body goes over stdin as one JSON object rather than
        # through -f/-F field flags. gh reads a field value beginning with "@"
        # from a file, and a title is free-form operator text: "@release-notes"
        # would be read off disk, or fail as a missing file. --input takes the
        # payload verbatim, so no value is interpreted. Field flags cannot be
        # mixed in — with --input they become URL query parameters.
        args = ["api", "-X", "POST", path, "--input", "-"]
        payload_in = json.dumps({"title": title, "head": head, "base": base, "body": body})
        result = self._run_gh(args, host=locator.host, stdin=payload_in)
        if result.returncode != 0:
            error = _classify_failure(result, locator.host)
            if isinstance(error, HostRequestRejectedError) and error.status == 422:
                # The host's own message names the cause — a head that does not
                # exist, or a pull request that is already open for this branch.
                _log_and_raise(
                    PullRequestCreationRejectedError(
                        str(error), fix_hint="Check the head branch exists and has no open PR."
                    )
                )
            _log_and_raise(error)

        payload = _require_object(result, ("gh", *args))
        argv = ("gh", "api", path)
        return PullRequestRecord(
            host=locator.host,
            owner=locator.owner,
            repository=locator.repository,
            number=require_int(payload, "number", argv),
            base_ref=base,
            head_ref=head,
            head_sha=_nested_sha(payload),
            url=require_str(payload, "html_url", argv),
        )

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

    def _json(self, args: Sequence[str], *, host: str, stdin: str | None = None) -> Mapping[str, Any]:
        """Invoke gh and parse its stdout as a JSON object."""
        result = self._run_gh(args, host=host, stdin=stdin)
        if result.returncode != 0:
            _log_and_raise(_classify_failure(result, host))
        payload = _require_object(result, ("gh", *args))
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            # GraphQL reports failure in-band with exit 0.
            _log_and_raise(_classify_graphql_errors(cast(list[Any], errors), host))
        return payload

    def _json_list(self, args: Sequence[str], *, host: str) -> list[dict[str, Any]]:
        """Invoke gh and parse its stdout as a JSON array of objects.

        ``--paginate`` concatenates pages into one array rather than the object
        ``_json`` expects, so the collection endpoints parse through here.
        """
        result = self._run_gh(args, host=host)
        if result.returncode != 0:
            _log_and_raise(_classify_failure(result, host))
        parsed = _try_parse_json(result.stdout)
        if not isinstance(parsed, list):
            raise HostResponseMalformedError(("gh", *args), "expected a JSON array on stdout")
        items = cast(list[Any], parsed)
        return [item for item in items if isinstance(item, dict)]

    def _run_gh(
        self,
        args: Sequence[str],
        *,
        host: str,
        cwd: str | None = None,
        stdin: str | None = None,
    ) -> ProcessResult:
        """Invoke ``gh``. The only place in this module that does.

        Appends ``--hostname`` so the host always comes from the resolved
        remote or target, never from a default and never from ``GH_HOST``.

        ``stdin`` carries a request body. Bodies never travel through argv:
        a review of any size would hit the argument-length limit, and its
        content would be exposed to shell-adjacent handling.
        """
        argv = ["gh", *args, "--hostname", host]
        try:
            return self._runner.run(
                argv,
                cwd=cwd,
                timeout=HOST_COMMAND_TIMEOUT_SECONDS,
                env=_GH_ENV,
                stdin=stdin,
            )
        except ProcessCwdNotFoundError:
            # D3 (squadron#112): a missing cwd is a configuration error, not a
            # missing gh install — let it propagate rather than reporting
            # "gh is not on PATH" for the wrong cause. Does not subclass
            # ProcessNotFoundError, so the handler below would not catch it
            # even without this explicit clause; kept explicit for clarity
            # and so this WARNING is logged before it surfaces.
            _logger.warning("gh invoked with a nonexistent cwd: %s", cwd)
            raise
        except ProcessNotFoundError as exc:
            _logger.warning("gh is not on PATH")
            raise GitHubCliMissingError(
                "the GitHub CLI (gh) is not on PATH",
                fix_hint="brew install gh — or see https://cli.github.com",
            ) from exc
        except ProcessTimedOutError as exc:
            _logger.warning("gh exceeded %ss: %s", exc.timeout, " ".join(exc.argv))
            raise HostCommandTimeoutError(exc.argv, exc.timeout) from exc


def _body_payload(body: str) -> str:
    """A one-field request body as JSON, for ``gh api --input -``.

    Comment bodies are operator and model text. Passed as ``-f body=@-`` the
    value is fine, but any field value beginning with ``@`` is read from a
    file by gh, so bodies travel as a JSON document instead of a field.
    """
    return json.dumps({"body": body})


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
