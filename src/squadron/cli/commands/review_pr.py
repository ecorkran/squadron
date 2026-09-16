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
from squadron.codehost.models import PullRequestRecord, ResolvedPullRequest
from squadron.codehost.protocol import CodeHost
from squadron.codehost.worktree import ScratchWorktree
from squadron.config.manager import get_config
from squadron.integrations.context_forge import cf_project_name
from squadron.review.git_utils import EmptyScopeError, assert_reviewable_scope
from squadron.review.persistence import save_review_result
from squadron.review.reviews_dir import resolve_reviews_dir
from squadron.review.rules import RulesSource, load_review_rules, resolve_rules_dir
from squadron.review.save_target import TargetKind
from squadron.review.templates import get_template, load_all_templates

_logger = logging.getLogger(__name__)


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
) -> tuple[str | None, RulesSource]:
    """Rules-directory provenance is part of the two-root split, not only CLAUDE.md.

    Resolved from ``checkout_cwd`` explicitly, never via ``_resolve_review_cwd``
    (Task G.5) — that helper would resolve the rules directory from whichever root
    ``inputs["cwd"]`` ends up holding once the worktree branch runs, which is exactly
    the mistake this function exists to avoid: an unreviewed rules directory planted in
    the PR's own worktree must never reach the reviewer's instructions.

    Returns the assembled rules content **and** which source produced the
    rules. The source is written to the artifact as ``rulesSource`` (D6), so it
    has to survive this call rather than being resolved a second time later —
    a second resolution could disagree with the one the reviewer actually got.
    """
    rules_path = rules_flag
    if not rules_path:
        config_rules = get_config("default_rules", cwd=checkout_cwd)
        if isinstance(config_rules, str):
            rules_path = config_rules
    manual_content = Path(rules_path).read_text() if rules_path else None

    checkout_rules_dir, rules_source = resolve_rules_dir(checkout_cwd, None, rules_dir_flag)
    # A --rules file with no directory resolving is still rules reaching the
    # reviewer. Reporting NONE there would claim the run got none, the mirror
    # image of the --no-rules reasoning: the key must not under-report any more
    # than it over-reports.
    if checkout_rules_dir is None and manual_content is not None:
        rules_source = RulesSource.FILE
    file_paths = changed_paths if checkout_rules_dir is not None else []
    content = load_review_rules(
        "code",
        checkout_rules_dir,
        file_paths=file_paths,
        manual_rules_content=manual_content,
    )
    return content, rules_source


class PrTarget:
    """A review of a pull request, as persistence sees it (slice 383, D3).

    Built here rather than in ``review/``, which must never import
    ``codehost``. Satisfying ``SaveTargetProtocol`` structurally is what lets
    the CLI hand persistence a target the review package never learns about.

    The stem carries no slice-name segment: a PR has no slice name, and
    deriving one from the PR title would be a fabricated identifier that
    changes whenever someone edits the title.
    """

    def __init__(self, record: PullRequestRecord, rules_source: RulesSource) -> None:
        self._record = record
        self._rules_source = rules_source

    @property
    def rules_source(self) -> RulesSource:
        """Which source produced the rules the reviewer was given (D6).

        Carried here so the artifact records the resolution this run actually
        used. Written to frontmatter in Task 8, after byte-identity is green.
        """
        return self._rules_source

    def filename_stem(self, review_type: str) -> str:
        return f"{self._record.path_key}-review.{review_type}"

    def frontmatter_fields(self) -> dict[str, object]:
        # No slice key — this review is not about one. The nested mapping
        # renders as indented lines the way `criteria:` already does (D2).
        return {
            "pr": {
                "host": self._record.host,
                "owner": self._record.owner,
                "repository": self._record.repository,
                "number": self._record.number,
                "url": self._record.url,
            },
            "targetKind": TargetKind.PR.value,
            "rulesSource": self._rules_source.value,
        }

    def source_document(self) -> str | None:
        return self._record.url

    def reviewed_sha(self) -> str | None:
        """The PR's head, never the operator's.

        ``save_review_result`` used to stamp ``resolve_reviewed_sha(".")`` —
        the process working directory, which on this path is the operator's
        own tree. That yields a real, plausible-looking sha for a commit the
        review never examined, which is why D3 moved the resolution onto the
        target. 384's staleness check compares this value against the live PR
        head, so a wrong one reads as "up to date" while being unrelated.
        """
        return self._record.head_sha


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
    output_path: str | None = typer.Option(
        None,
        "--output-path",
        help="File path for --output file (a JSON dump, not the review artifact).",
    ),
    reviews_dir_flag: str | None = typer.Option(
        None,
        "--reviews-dir",
        help=(
            "Directory for the saved review artifact. Overrides the project's "
            "reviews directory and review.external_reviews_dir. Distinct from "
            "--output-path, which is a JSON dump destination."
        ),
    ),
    use_json: bool = typer.Option(False, "--json", help="Output and save as JSON instead of markdown"),
    no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
) -> None:
    """Review a pull request's code over its fetched merge-base range."""
    checkout_cwd = resolve_repo_cwd(cwd)

    try:
        host, resolved, fetched = resolve_and_fetch_pull_request(target, checkout_cwd)
        # Inside the handler: assemble_pr_metadata fetches unresolved discussions over the
        # adapter, so transport/auth failures there are adapter failures like any other and
        # must render the same way rather than escaping as a traceback.
        pr_metadata = assemble_pr_metadata(resolved, host)
    except CodeHostError as exc:
        render_code_host_error(exc)
        raise typer.Exit(code=1) from exc

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

    # --no-rules reports NONE rather than the source a resolver would have
    # picked: no rules reached the reviewer, so naming a directory in the
    # artifact would claim a provenance this run does not have.
    if no_rules:
        rules_content, rules_source = None, RulesSource.NONE
    else:
        rules_content, rules_source = _resolve_pr_rules_content(
            checkout_cwd, rules_dir_flag, rules, list(fetched.changed_paths)
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

    def _save_pr(target: PrTarget) -> bool:
        """Persist the review, reporting where it landed and which rule chose there.

        The location is printed whether or not the write succeeds: an operator
        who does not know where their review went has been failed either way
        (D5), and a failed write names the path they would have to fix.
        """
        reviews_dir, rule = resolve_reviews_dir(
            flag=reviews_dir_flag,
            cwd=checkout_cwd,
            host=resolved.record.host,
            owner=resolved.record.owner,
            repository=resolved.record.repository,
        )
        console = Console(stderr=True)
        try:
            path = save_review_result(
                result,
                "code",
                as_json=use_json,
                reviews_dir=reviews_dir,
                input_file=resolved.record.url,
                target=target,
                project_name=cf_project_name(),
                heading_label=f"PR #{resolved.record.number}",
            )
        except OSError as exc:
            # Never a fall-through to the next precedence rule: writing
            # somewhere the operator did not ask for, and reporting success,
            # is the failure this names the path to avoid (D5).
            console.print(f"[red]Review not saved to {reviews_dir} ({rule}): {exc}[/red]")
            return False
        console.print(f"[green]Saved review to {path}[/green] [dim]({rule})[/dim]")
        return True

    outcome = _resolve_save_outcome(
        no_save=no_save,
        # A PR review always has a target, so NOT_PERSISTABLE is unreachable
        # here — it survives for the case it actually describes, a slice-less
        # `sq review code` with nothing to name an artifact under (D8).
        target=PrTarget(resolved.record, rules_source),
        save=_save_pr,
        review_type="pr",
    )

    _exit_on(result.verdict, outcome)
