"""The code-host contract.

Eleven operations, exactly as the design's listing gives them. An implementation
serves one or more hosts and answers questions about repositories on them; it
never decides *which* repository — that is the job of the target grammar and
remote selection, which stay host-agnostic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from squadron.codehost.models import (
    FetchedRange,
    HostComment,
    OperatorIdentity,
    PullRequestRecord,
    RepositoryLocator,
    ResolvedPullRequest,
    ReviewDiscussion,
)

if TYPE_CHECKING:
    # Defined in targets.py (Part C). Imported under TYPE_CHECKING so the
    # annotation resolves for type checkers without a runtime import cycle:
    # selection passes a parsed target in, and targets.py imports nothing here.
    from squadron.codehost.targets import PullRequestTarget
    from squadron.core.process_runner import ProcessRunner


class CodeHost(Protocol):
    """A read-and-write interface to one code-hosting service."""

    @property
    def runner(self) -> ProcessRunner:
        """The process runner every call from this host goes through.

        On the protocol so a caller's *git* work travels the same seam as the
        host calls. A caller that builds its own runner alongside the host
        splits the seam in two: substituting the host then redirects only part
        of what the command actually runs.
        """
        ...

    def serves_host(self, hostname: str) -> bool:
        """Whether this implementation handles ``hostname``.

        Bare-form resolution needs it: a checkout may carry remotes on several
        hosts, and only the ones this implementation serves are candidates.
        Local and read-only — it asks the implementation, not the network.
        """
        ...

    def resolve_pull_request(
        self, locator: RepositoryLocator, target: PullRequestTarget, *, cwd: str
    ) -> ResolvedPullRequest:
        """Resolve a target to a full pull-request record.

        ``cwd`` is the resolved repository root. The bare form reads HEAD from
        the checkout, so it has to read it from the repository the command is
        targeting rather than from the process's own working directory — an
        agent's cwd is its tool jail root, which may be elsewhere entirely.
        """
        ...

    def default_branch(self, locator: RepositoryLocator) -> str: ...

    def branch_exists(self, locator: RepositoryLocator, branch: str) -> bool:
        """Whether ``branch`` exists on the host.

        A missing branch is an answer, so this returns ``False``. Only
        transport and auth failures raise.
        """
        ...

    def fetch_pull_request_refs(
        self, resolved: ResolvedPullRequest, *, remote_name: str, cwd: str
    ) -> FetchedRange:
        """Fetch base and head into local refs and describe the range.

        On the protocol because the refspec is the host's convention; the
        implementation supplies refspecs and delegates the git work to
        ``refs.fetch_and_range``.

        Takes the resolved pull request rather than the bare record: the
        post-fetch "base moved since resolution" check compares against
        ``base_sha``, the base tip the host reported at resolution (a fetched
        base that only advanced past it is accepted, #131), and that
        field lives on ``ResolvedPullRequest`` by design (PM decision
        20260913 — the design fixed both shapes and they disagreed).
        """
        ...

    def list_unresolved_discussions(self, record: PullRequestRecord) -> list[ReviewDiscussion]: ...

    def find_marked_comments(self, record: PullRequestRecord, *, marker: str) -> list[HostComment]:
        """Every comment on the pull request whose body contains ``marker``.

        Every match regardless of author, ordered oldest-first by
        ``created_at``, with ``author_login`` populated from the payload
        rather than assumed. Partitioning by author — and choosing which of
        the operator's own matches is canonical — is the caller's job,
        because the caller is what reports the non-own matches (D1).
        """
        ...

    def update_comment(self, record: PullRequestRecord, comment_id: str, body: str) -> HostComment: ...

    def post_comment(self, record: PullRequestRecord, body: str) -> HostComment: ...

    def open_pull_request(
        self,
        locator: RepositoryLocator,
        *,
        base: str,
        head: str,
        title: str,
        body: str,
    ) -> PullRequestRecord: ...

    def identify_operator(self, hostname: str) -> OperatorIdentity: ...
