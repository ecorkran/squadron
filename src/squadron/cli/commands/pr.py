"""``sq pr`` — pull-request commands over the code-host adapter.

This slice ships ``show``: resolve a target, fetch its endpoints, and report
the range. Read-only against the host and against the working tree. 385 adds
``create`` here.
"""

from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from squadron.cli.commands.cwd_resolution import resolve_repo_cwd
from squadron.codehost.errors import CodeHostError
from squadron.codehost.github_cli import build_github_host
from squadron.codehost.models import FetchedRange, ResolvedPullRequest
from squadron.codehost.remotes import list_remotes, select_remote
from squadron.codehost.targets import parse_target
from squadron.core.process_runner import SubprocessRunner

pr_app = typer.Typer(
    name="pr",
    help="Inspect and review pull requests.",
    no_args_is_help=True,
)


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
    host = build_github_host(SubprocessRunner())
    # Git work goes through the host's own runner, not a second one: the
    # factory is the single seam, so substituting the host has to redirect
    # every process call this command makes, not only the gh ones.
    runner = host.runner

    try:
        parsed = parse_target(target)
        remotes = list_remotes(runner, repo_cwd)
        locator = select_remote(parsed, remotes, host.serves_host)
        resolved = host.resolve_pull_request(locator, parsed, cwd=repo_cwd)
        fetched = host.fetch_pull_request_refs(resolved, remote_name=locator.remote_name, cwd=repo_cwd)
    except CodeHostError as exc:
        # Every adapter failure has already been logged once at WARNING or
        # above by the layer that raised it; this is the operator-facing half.
        # Errors go to stderr so `sq pr show --json` piped into a parser stays
        # parseable when the command fails.
        errors = Console(stderr=True)
        errors.print(f"[red]{exc}[/red]")
        if exc.fix_hint:
            errors.print(f"[dim]{exc.fix_hint}[/dim]")
        raise typer.Exit(code=1) from exc

    if json_output:
        _render_json(resolved, fetched)
        return
    _render_terminal(resolved, fetched)


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
