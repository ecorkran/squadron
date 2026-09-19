"""``sq pr`` — pull-request commands over the code-host adapter.

This slice ships ``show``: resolve a target, fetch its endpoints, and report
the range. Read-only against the host and against the working tree. 385 adds
``create`` here.
"""

from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from squadron.cli.commands.cwd_resolution import resolve_repo_cwd
from squadron.codehost.errors import CodeHostError, TargetUnresolvableError
from squadron.codehost.github_cli import build_github_host
from squadron.codehost.models import FetchedRange, RepositoryLocator, ResolvedPullRequest
from squadron.codehost.protocol import CodeHost
from squadron.codehost.remotes import GIT_QUERY_TIMEOUT_SECONDS, list_remotes, select_remote
from squadron.codehost.targets import PullRequestTarget, parse_target
from squadron.core.process_runner import SubprocessRunner
from squadron.integrations.context_forge import ContextForgeClient
from squadron.pr.assembly import PrFacts, assemble_facts
from squadron.pr.base import select_base
from squadron.pr.body import (
    BodyIncompleteError,
    CompositionError,
    check_body_complete,
    compose_body,
    compose_one_shot,
    resolve_title,
)
from squadron.pr.inputs import (
    EmptyCommitRangeError,
    find_latest_in_range_review,
    gather_commits_and_slice,
)
from squadron.pr.preconditions import check_head_pushed
from squadron.providers.base import ProfileName
from squadron.review.git_utils import GitRangeUnavailableError

pr_app = typer.Typer(
    name="pr",
    help="Inspect and review pull requests.",
    no_args_is_help=True,
)


def resolve_locator(
    target: str | None, repo_cwd: str
) -> tuple[CodeHost, RepositoryLocator, PullRequestTarget]:
    """Build the host and resolve *target* to the repository it names.

    Returns the parsed target too, so a caller that goes on to resolve a
    pull request does not parse it a second time.

    The first three steps ``resolve_and_fetch_pull_request`` performs before
    it resolves an *existing* pull request. ``create`` (385) needs only
    these — host, remotes, locator — not an existing PR's refs, so this is
    extracted as the shared prefix rather than duplicated (D6).

    Raises ``CodeHostError`` on any adapter failure.
    """
    host = build_github_host(SubprocessRunner())
    # Git work goes through the host's own runner, not a second one: the
    # factory is the single seam, so substituting the host has to redirect
    # every process call a caller makes, not only the gh ones.
    runner = host.runner

    parsed = parse_target(target)
    remotes = list_remotes(runner, repo_cwd)
    locator = select_remote(parsed, remotes, host.serves_host)
    return host, locator, parsed


def resolve_and_fetch_pull_request(
    target: str | None, repo_cwd: str
) -> tuple[CodeHost, ResolvedPullRequest, FetchedRange]:
    """Resolve *target* to a pull request and fetch its base/head endpoints.

    The exact sequence ``sq pr show`` established: parse the target, pick the
    serving remote, resolve the pull request, fetch its refs. Shared with
    ``sq review pr`` (slice 382, Task G.1) so the two commands stay provably
    identical up to the point their behavior diverges — this is not a second
    implementation of ``pr show``'s resolution, it is the same one.

    Raises ``CodeHostError`` on any adapter failure; callers render it the
    same way ``pr show`` does.
    """
    host, locator, parsed = resolve_locator(target, repo_cwd)
    resolved = host.resolve_pull_request(locator, parsed, cwd=repo_cwd)
    fetched = host.fetch_pull_request_refs(resolved, remote_name=locator.remote_name, cwd=repo_cwd)
    return host, resolved, fetched


def render_code_host_error(exc: CodeHostError) -> None:
    """Print a CodeHostError the way every code-host command reports one.

    Errors go to stderr so a command piped into a parser (e.g. ``--json``)
    stays parseable when the command fails. Shared so ``sq review pr``
    reports adapter failures identically to ``sq pr show`` (Task G.7).
    """
    errors = Console(stderr=True)
    errors.print(f"[red]{exc}[/red]")
    if exc.fix_hint:
        errors.print(f"[dim]{exc.fix_hint}[/dim]")


@pr_app.command("show")
def show(
    target: str | None = typer.Argument(
        None,
        help=(
            "Pull request to show: a number, owner/repo#number, repo#number, "
            "a pull-request URL, or a branch. Omit to use the current branch."
        ),
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Repository to resolve against."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Resolve a pull request, fetch its endpoints, and report the range."""
    repo_cwd = resolve_repo_cwd(cwd)

    try:
        _host, resolved, fetched = resolve_and_fetch_pull_request(target, repo_cwd)
    except CodeHostError as exc:
        # Every adapter failure has already been logged once at WARNING or
        # above by the layer that raised it; this is the operator-facing half.
        render_code_host_error(exc)
        raise typer.Exit(code=1) from exc

    if json_output:
        _render_json(resolved, fetched)
        return
    _render_terminal(resolved, fetched)


def _current_branch(host: CodeHost, *, cwd: str) -> str:
    """The branch HEAD is on, read through the host's own runner.

    Matches ``GitHubCli._branch_for``'s pattern for the current-branch
    target form: reading through ``host.runner`` rather than a second
    process-execution path keeps this call inside the same seam every other
    call on this path uses, so a test can fake every process call through
    one factory (D6, D8).
    """
    result = host.runner.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS
    )
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch or branch == "HEAD":
        raise TargetUnresolvableError(
            "HEAD is detached, so there is no branch to open a pull request from",
            fix_hint="Check out a branch first.",
        )
    return branch


async def _compose_title_and_body(
    facts: PrFacts, *, title_flag: str | None, model: str | None, profile: str
) -> tuple[str, str]:
    """Resolve the title and compose the body through one shared composer.

    Both calls use the same profile-bound composer, and both are resolved
    before dry-run and the real create path diverge, so the two paths share
    one title and one body rather than composing twice (D8).
    """

    async def composer(prompt: str) -> str:
        return await compose_one_shot(prompt, model=model, profile=profile)

    resolved_title = await resolve_title(
        title_flag=title_flag,
        slice_design_file=facts.slice_design_file,
        commits=facts.commits,
        compose=composer,
    )
    body = await compose_body(facts, compose=composer)
    return resolved_title, body


@pr_app.command("create")
def create(
    base: str | None = typer.Option(None, "--base", help="Base branch."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print title and body without creating."),
    model: str | None = typer.Option(None, "--model", help="Model for the one-shot composer."),
    profile: str = typer.Option(
        ProfileName.SDK, "--profile", help="Provider profile for the one-shot composer."
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Repository to resolve against."),
    title: str | None = typer.Option(None, "--title", help="PR title, overriding the slice's name."),
) -> None:
    """Open a pull request with a description assembled from the branch's own artifacts.

    Every refusal decidable without a model call happens before the model
    call (D8): identity, then the pushed-branch precondition, then base
    selection, all before input gathering, assembly, and composition.
    """
    repo_cwd = resolve_repo_cwd(cwd)
    errors = Console(stderr=True)

    try:
        host, locator, _parsed = resolve_locator(None, repo_cwd)
        head = _current_branch(host, cwd=repo_cwd)
        host.identify_operator(locator.host)

        local_sha_result = host.runner.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS
        )
        local_sha = local_sha_result.stdout.strip()
        check_head_pushed(host, locator, head=head, local_sha=local_sha, cwd=repo_cwd)

        selection = select_base(host, locator, base_flag=base, cwd=repo_cwd)
    except CodeHostError as exc:
        render_code_host_error(exc)
        raise typer.Exit(code=1) from exc

    errors.print(f"[dim]base: {selection.base} (source: {selection.source})[/dim]")

    # The host confirmed the base exists there, not in this clone — and
    # ``--base`` is taken verbatim — so the local range is its own refusal.
    try:
        inputs = gather_commits_and_slice(
            ContextForgeClient(), base=selection.base, head=head, cwd=repo_cwd
        )
        review = find_latest_in_range_review(
            base=selection.base,
            head=head,
            cwd=repo_cwd,
            host=locator.host,
            owner=locator.owner,
            repository=locator.repository,
        )
    except GitRangeUnavailableError as exc:
        errors.print(f"[red]{exc}[/red]")
        errors.print(f"[dim]Fetch {selection.base} into this clone, or pass --base.[/dim]")
        raise typer.Exit(code=1) from exc
    except EmptyCommitRangeError as exc:
        errors.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    facts = assemble_facts(inputs, review)

    try:
        resolved_title, body = asyncio.run(
            _compose_title_and_body(facts, title_flag=title, model=model, profile=profile)
        )
        check_body_complete(body, facts)
    except (CompositionError, BodyIncompleteError) as exc:
        errors.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if dry_run:
        print(resolved_title)
        print(body)
        return

    try:
        record = host.open_pull_request(
            locator, base=selection.base, head=head, title=resolved_title, body=body
        )
    except CodeHostError as exc:
        render_code_host_error(exc)
        raise typer.Exit(code=1) from exc

    console = Console()
    console.print(f"[green]{record.url}[/green]")


def _render_json(resolved: ResolvedPullRequest, fetched: FetchedRange) -> None:
    """One object with ``record``, ``resolved``, and ``fetched``.

    Shaped for 386's parity test, following ``doctor.py``'s JSON convention.
    """
    record = resolved.record
    output = {
        "record": {
            "host": record.host,
            "owner": record.owner,
            "repository": record.repository,
            "number": record.number,
            "key": record.key,
            "base_ref": record.base_ref,
            "head_ref": record.head_ref,
            "head_sha": record.head_sha,
            "url": record.url,
        },
        "resolved": {
            "title": resolved.title,
            "body": resolved.body,
            "state": str(resolved.state),
            "author_login": resolved.author_login,
            "base_sha": resolved.base_sha,
            "is_cross_repository": resolved.is_cross_repository,
            "head_repository": resolved.head_repository,
            "linked_issue_numbers": list(resolved.linked_issue_numbers),
        },
        "fetched": {
            "base_ref": fetched.base_ref,
            "head_ref": fetched.head_ref,
            "base_sha": fetched.base_sha,
            "head_sha": fetched.head_sha,
            "merge_base": fetched.merge_base,
            "diff_range": fetched.diff_range,
            "changed_paths": list(fetched.changed_paths),
        },
    }
    print(json.dumps(output, indent=2))


def _render_terminal(resolved: ResolvedPullRequest, fetched: FetchedRange) -> None:
    """The record, then what was fetched and the range it describes."""
    console = Console()
    record = resolved.record

    header = Table.grid(padding=(0, 2))
    header.add_column(style="dim")
    header.add_column()
    header.add_row("repository", f"{record.host}/{record.owner}/{record.repository}")
    header.add_row("number", f"#{record.number}")
    header.add_row("state", str(resolved.state))
    header.add_row("title", resolved.title)
    header.add_row("author", resolved.author_login)
    header.add_row("url", record.url)
    header.add_row("base", f"{record.base_ref} @ {resolved.base_sha}")
    header.add_row("head", f"{record.head_ref} @ {record.head_sha}")
    if resolved.is_cross_repository:
        header.add_row("fork", resolved.head_repository)
    console.print(Panel(header, title=record.key, expand=False))

    fetched_table = Table.grid(padding=(0, 2))
    fetched_table.add_column(style="dim")
    fetched_table.add_column()
    fetched_table.add_row("base ref", f"{fetched.base_ref} @ {fetched.base_sha}")
    fetched_table.add_row("head ref", f"{fetched.head_ref} @ {fetched.head_sha}")
    fetched_table.add_row("merge base", fetched.merge_base)
    fetched_table.add_row("diff range", fetched.diff_range)
    console.print(fetched_table)

    console.print()
    if not fetched.changed_paths:
        console.print("  No changed paths.", style="dim")
        return
    console.print(f"  {len(fetched.changed_paths)} changed paths:", style="dim")
    for path in fetched.changed_paths:
        console.print(f"    {path}")
