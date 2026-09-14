"""``sq review pr <target>`` — review a pull request over the code-host adapter.

Ties together 381's boundary (resolve, fetch), file 1's worktree lifecycle and
convention-root split, and file 2's PR-metadata block (slice 382). Split out of
``review.py`` rather than growing that module further — it is already well past the
project's ~300-line source guideline.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console

from squadron.cli.commands.cwd_resolution import resolve_repo_cwd
from squadron.cli.commands.pr import render_code_host_error, resolve_and_fetch_pull_request
from squadron.cli.commands.review import (
    _exit_on,  # pyright: ignore[reportPrivateUsage]
    _resolve_save_outcome,  # pyright: ignore[reportPrivateUsage]
    _resolve_verbosity,  # pyright: ignore[reportPrivateUsage]
    _run_review_command,  # pyright: ignore[reportPrivateUsage]
    review_app,
)
from squadron.codehost.errors import CodeHostError
from squadron.codehost.models import ResolvedPullRequest
from squadron.codehost.protocol import CodeHost
from squadron.codehost.worktree import ScratchWorktree
from squadron.config.manager import get_config
from squadron.review.git_utils import EmptyScopeError, assert_reviewable_scope
from squadron.review.rules import load_review_rules, resolve_rules_dir
from squadron.review.templates import get_template, load_all_templates

_logger = logging.getLogger(__name__)

_NOT_PERSISTABLE_REASON = "PR review persistence is not yet available (383)"


def assemble_pr_metadata(resolved: ResolvedPullRequest, host: CodeHost) -> str:
    """Raw PR content the CLI assembles: title, body, linked issues, discussions.

    Deliberately unrendered — no fencing, no label, no truncation. ``_pr_block``
    (file 2, Task D.3) does that; this function only gathers the content.
    """
    record = resolved.record
    lines = [f"Title: {resolved.title}", "", "Body:", resolved.body]

    if resolved.linked_issue_numbers:
        issue_list = ", ".join(f"#{n}" for n in resolved.linked_issue_numbers)
        lines += ["", f"Linked issues: {issue_list}"]

    discussions = host.list_unresolved_discussions(record)
    if discussions:
        lines += ["", "Unresolved discussions:"]
        for d in discussions:
            lines += ["", f"- {d.path}:{d.line} ({d.author_login}):", d.body]

    return "\n".join(lines)


def _resolve_pr_max_bytes(cwd: str) -> int:
    max_bytes = get_config("review.max_file_size_bytes", cwd=cwd)
    if not isinstance(max_bytes, int):
        raise TypeError(f"review.max_file_size_bytes config value is not an int: {max_bytes!r}")
    return max_bytes


def _resolve_pr_rules_content(
    checkout_cwd: str,
    rules_dir_flag: str | None,
    rules_flag: str | None,
    changed_paths: list[str],
) -> str | None:
    """Rules-directory provenance is part of the two-root split, not only CLAUDE.md.

    Resolved from ``checkout_cwd`` explicitly, never via ``_resolve_review_cwd``
    (Task G.5) — that helper would resolve the rules directory from whichever root
    ``inputs["cwd"]`` ends up holding once the worktree branch runs, which is exactly
    the mistake this function exists to avoid: an unreviewed rules directory planted in
    the PR's own worktree must never reach the reviewer's instructions.
    """
    rules_path = rules_flag
    if not rules_path:
        config_rules = get_config("default_rules")
        if isinstance(config_rules, str):
            rules_path = config_rules
    manual_content = Path(rules_path).read_text() if rules_path else None

    checkout_rules_dir = resolve_rules_dir(checkout_cwd, None, rules_dir_flag)
    file_paths = changed_paths if checkout_rules_dir is not None else []
    return load_review_rules(
        "code",
        checkout_rules_dir,
        file_paths=file_paths,
        manual_rules_content=manual_content,
    )


@review_app.command("pr")
def review_pr(
    target: str | None = typer.Argument(
        None,
        help=(
            "Pull request to review: a number, owner/repo#number, repo#number, "
            "a pull-request URL, or a branch. Omit to use the current branch."
        ),
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Repository to resolve against."),
    rules: str | None = typer.Option(None, "--rules", help="Path to additional rules file"),
    rules_dir_flag: str | None = typer.Option(None, "--rules-dir", help="Rules directory override"),
    no_rules: bool = typer.Option(False, "--no-rules", help="Suppress all rule injection"),
    model: str | None = typer.Option(None, "--model", help="Model override (e.g. opus, sonnet)"),
    no_tools: bool = typer.Option(
        False,
        "--no-tools",
        help="Run this review without tools, even if the template declares them.",
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Provider profile (e.g. openrouter, openai, local, sdk)",
    ),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Verbosity level (-v, -vv)"),
    output: str = typer.Option("terminal", "--output", help="Output format: terminal, json, file"),
    output_path: str | None = typer.Option(None, "--output-path", help="File path for --output file"),
    use_json: bool = typer.Option(False, "--json", help="Output and save as JSON instead of markdown"),
    no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
) -> None:
    """Review a pull request's code over its fetched merge-base range."""
    checkout_cwd = resolve_repo_cwd(cwd)

    try:
        host, resolved, fetched = resolve_and_fetch_pull_request(target, checkout_cwd)
    except CodeHostError as exc:
        render_code_host_error(exc)
        raise typer.Exit(code=1) from exc

    pr_metadata = assemble_pr_metadata(resolved, host)

    # D2: no range normalization — 381's fetch already produced the correct
    # three-dot merge-base form.
    diff = fetched.diff_range

    load_all_templates()
    code_template = get_template("code")
    exclude_patterns = code_template.diff_exclude_patterns if code_template else None

    # D2: always against the checkout, regardless of whether a worktree exists —
    # the ref store is shared across worktrees.
    try:
        assert_reviewable_scope(diff, checkout_cwd, exclude_patterns)
    except EmptyScopeError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if use_json:
        output = "json"
    verbosity = _resolve_verbosity(verbose)

    rules_content = (
        None
        if no_rules
        else _resolve_pr_rules_content(checkout_cwd, rules_dir_flag, rules, list(fetched.changed_paths))
    )

    inputs: dict[str, str] = {"diff": diff}
    if exclude_patterns:
        inputs["diff_exclude_patterns"] = ",".join(exclude_patterns)
    inputs["pr"] = pr_metadata
    inputs["pr_max_bytes"] = str(_resolve_pr_max_bytes(checkout_cwd))

    worktree_path: Path | None = None

    def _run(review_cwd: str, convention_root: str | None):
        inputs["cwd"] = review_cwd
        # D8: setting_sources_override=[] regardless of --no-tools — the SDK's own
        # project-settings resolution is not gated by the tool flag.
        return _run_review_command(
            "code",
            inputs,
            output,
            output_path,
            verbosity,
            rules_content,
            model_flag=model,
            profile_flag=profile,
            no_tools=no_tools,
            failure_target=None,
            no_save=no_save,
            rules_dir=None,
            convention_root=convention_root,
            setting_sources_override=[],
        )

    if no_tools:
        # D5: tools disabled → no worktree. Single root, so convention_root is
        # omitted (None resolves to the same cwd — no split needed).
        result = _run(checkout_cwd, None)
    else:
        # ScratchWorktree.__enter__ sweeps orphans itself before creating this one
        # (design D3) — no separate sweep_orphans() call needed here.
        run_id = uuid.uuid4().hex[:8]
        with ScratchWorktree(
            host.runner, resolved.record, fetched.head_ref, run_id, checkout_cwd
        ) as worktree:
            worktree_path = worktree.path
            result = _run(str(worktree.path), checkout_cwd)

    # Both roots are reported alongside the result (design criterion) — a
    # display-layer addition, not a new ReviewResult field: 383 has not yet
    # defined what persistence needs here.
    roots = f"[dim]checkout: {checkout_cwd}"
    if worktree_path is not None:
        roots += f" | worktree: {worktree_path}"
    roots += "[/dim]"
    Console(stderr=True).print(roots)

    outcome = _resolve_save_outcome(
        no_save=no_save,
        target=None,
        save=lambda _target: False,
        review_type="pr",
        not_persistable_reason=_NOT_PERSISTABLE_REASON,
    )

    _exit_on(result.verdict, outcome)
