"""review subcommand — execute review workflows via templates."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import typer
from openai import RateLimitError
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from squadron.config.manager import get_config
from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.models.aliases import resolve_model_alias
from squadron.review.addressed.judge import JUDGE_TEMPLATE_NAME
from squadron.review.git_utils import (
    DiffRangeUnresolvedError,
    find_git_root,
    resolve_slice_diff_range,
)
from squadron.review.models import ReviewResult, Severity, Verdict
from squadron.review.persistence import (
    TASKS_DIR,
    SliceInfo,
    resolve_slice_info,
    save_review_result,
)
from squadron.review.resolution import Resolution, ResolutionResult, resolve_review
from squadron.review.resolution_evidence import ResolutionError
from squadron.review.review_client import run_review_with_profile
from squadron.review.rules import (
    extract_diff_paths,
    load_review_rules,
    resolve_rules_dir,
)
from squadron.review.template_inputs import missing_input_files
from squadron.review.templates import (
    ReviewTemplate,
    get_template,
    list_templates,
    load_all_templates,
)

_logger = logging.getLogger(__name__)

review_app = typer.Typer(
    name="review",
    help="Run review workflows using built-in templates.",
    no_args_is_help=True,
)

_VERDICT_COLORS: dict[Verdict, str] = {
    Verdict.PASS: "bright_green",
    Verdict.CONCERNS: "yellow",
    Verdict.FAIL: "red",
    Verdict.UNKNOWN: "dim",
}

_RESOLUTION_COLORS: dict[Resolution, str] = {
    Resolution.ADDRESSED: "bright_green",
    Resolution.UNADDRESSED: "red",
    Resolution.UNKNOWN: "dim",
}

_SEVERITY_COLORS: dict[Severity, str] = {
    Severity.PASS: "bright_green",
    Severity.NOTE: "cyan",
    Severity.CONCERN: "yellow",
    Severity.FAIL: "red",
}


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def display_result(
    result: ReviewResult,
    output_mode: str,
    output_path: str | None,
    verbosity: int = 0,
) -> None:
    """Format and deliver review results based on output mode."""
    match output_mode:
        case "terminal":
            _display_terminal(result, verbosity)
        case "json":
            _display_json(result)
        case "file":
            _write_file(result, output_path)
        case _:
            rprint(f"[red]Unknown output mode: {output_mode}[/red]")
            raise typer.Exit(code=1)


def _display_terminal(result: ReviewResult, verbosity: int = 0) -> None:
    """Rich-formatted terminal output with verbosity levels.

    Level 0: verdict badge + finding headings with severity
    Level 1: above + full finding descriptions
    """
    console = Console()
    color = _VERDICT_COLORS.get(result.verdict, "dim")

    header = Text(f"Review: {result.template_name}", style="bold")
    header.append("  Verdict: ", style="dim")
    header.append(result.verdict.value, style=f"bold {color}")
    if result.model is not None:
        header.append("  Model: ", style="dim")
        header.append(result.model)

    console.print(Panel(header, expand=False))

    if not result.findings:
        console.print("  No specific findings.", style="dim")
        return

    for finding in result.findings:
        sev_color = _SEVERITY_COLORS.get(finding.severity, "dim")
        console.print()  # blank line before each finding
        console.print(
            f"[{sev_color}][{finding.severity.value}][/{sev_color}] "
            f"[bold white]{finding.title}[/bold white]"
        )
        if verbosity >= 1 and finding.category:
            console.print(f"  category: {finding.category}", style="dim")
            console.print()  # blank line after category
        if verbosity >= 1 and finding.description:
            for line in finding.description.split("\n"):
                console.print(line)
        if verbosity >= 1 and finding.file_ref:
            console.print(f"  -> {finding.file_ref}", style="cyan")


def _display_json(result: ReviewResult) -> None:
    """JSON output to stdout."""
    typer.echo(json.dumps(result.to_dict(), indent=2))


def _write_file(result: ReviewResult, output_path: str | None) -> None:
    """Write JSON to file."""
    if not output_path:
        rprint("[red]Error: --output file requires a path argument.[/red]")
        raise typer.Exit(code=1)
    path = Path(output_path)
    path.write_text(json.dumps(result.to_dict(), indent=2))
    rprint(f"[green]Review result written to {path}[/green]")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_cwd(cwd: str | None) -> str:
    """Resolve cwd: CLI flag overrides config default."""
    if cwd is not None:
        return cwd
    config_val = get_config("cwd")
    if isinstance(config_val, str):
        return config_val
    return "."


def _save_and_report(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo,
    *,
    as_json: bool = False,
    input_file: str | None = None,
    name_suffix: str | None = None,
) -> bool:
    """Persist a review, reporting either where it landed or why it did not.

    Returns whether the file was written. ``save_review_result`` refuses to
    overwrite an existing review whose prior content it could not archive
    (slice 306 Part D). That refusal is reported here rather than surfacing as
    a traceback — the review itself has already been displayed, so the run is
    not lost — but the caller must still exit non-zero: an unwritten review is
    a review Context Forge and every other downstream reader cannot see, and
    reporting success for it would be a silent failure.
    """
    try:
        path = save_review_result(
            result,
            review_type,
            slice_info,
            as_json=as_json,
            input_file=input_file,
            name_suffix=name_suffix,
        )
    except OSError as exc:
        rprint(f"[red]Review not saved: {exc}[/red]")
        return False
    rprint(f"[green]Saved review to {path}[/green]")
    return True


def _exit_on(verdict: Verdict, saved: bool) -> None:
    """Exit with the code the run earned: 2 for a FAIL verdict, 1 for an unsaved review.

    A FAIL verdict keeps precedence — it is the more specific signal, and both
    codes are non-zero — but a review that could not be written must never exit
    0. Downstream readers gate on the file, not on the terminal output.
    """
    if verdict == Verdict.FAIL:
        raise typer.Exit(code=2)
    if not saved:
        raise typer.Exit(code=1)


# Loggers whose records answer "what did the reviewing agent actually do": each tool call
# with its arguments and a result preview, and the agentic loop's guard warnings.
_AGENT_LOG_NAMES = ("squadron.providers", "squadron.tools", "squadron.review")


def _configure_agent_logging(verbosity: int) -> None:
    """Route agent/tool logs to stderr at -v (INFO) and -vv (DEBUG).

    Mirrors ``sq run``'s verbosity wiring. At the default verbosity nothing is attached,
    so a plain review's output is unchanged. Without this, the per-tool-call DEBUG records
    the agentic loop already emits are unreachable from the review CLI.
    """
    if verbosity <= 0:
        return
    level = logging.DEBUG if verbosity >= 2 else logging.INFO
    for name in _AGENT_LOG_NAMES:
        agent_logger = logging.getLogger(name)
        agent_logger.setLevel(level)
        if not agent_logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            agent_logger.addHandler(handler)


def _resolve_verbosity(verbose: int) -> int:
    """Resolve verbosity: CLI flag overrides config default.

    Also attaches agent/tool log handlers for the resolved level — every review subcommand
    routes through here, so the wiring cannot drift between them.
    """
    if verbose > 0:
        resolved = verbose
    else:
        config_val = get_config("verbosity")
        resolved = config_val if isinstance(config_val, int) else 0
    _configure_agent_logging(resolved)
    return resolved


def _aggregate_verdicts(results: list[object]) -> Verdict:
    """Return the worst verdict across a list of ReviewResults.

    Ordering: FAIL > CONCERNS > PASS. An empty list returns PASS.
    Used when a single review command produces multiple results
    (e.g. split task files reviewed part-by-part).
    """
    worst = Verdict.PASS
    rank = {Verdict.PASS: 0, Verdict.CONCERNS: 1, Verdict.FAIL: 2}
    for result in results:
        verdict = getattr(result, "verdict", Verdict.PASS)
        if rank[verdict] > rank[worst]:
            worst = verdict
    return worst


def _resolve_rules_content(rules_path: str | None) -> str | None:
    """Read rules file content if a path is provided."""
    if not rules_path:
        return None
    path = Path(rules_path)
    if not path.is_file():
        rprint(f"[red]Error: Rules file not found: {rules_path}[/red]")
        raise typer.Exit(code=1)
    return path.read_text()


def _resolve_arch_file(num: str) -> str:
    """Resolve an initiative index to an architecture document path.

    Searches ``project-documents/user/architecture/`` for files matching
    ``{num}-arch.*.md``.
    """
    arch_dir = Path("project-documents/user/architecture")
    pattern = f"{num}-arch.*.md"
    matches = sorted(arch_dir.glob(pattern))
    if not matches:
        rprint(f"[red]Error: No architecture document matching '{pattern}' in {arch_dir}/[/red]")
        raise typer.Exit(code=1)
    if len(matches) > 1:
        rprint(f"[yellow]Warning: Multiple arch docs for index {num}, using {matches[0].name}[/yellow]")
    return str(matches[0])


def _resolve_slice_number(num: str) -> SliceInfo:
    """Resolve a bare slice number to file paths via Context-Forge.

    Delegates to ``resolve_slice_info`` (shared with pipeline review
    action) and wraps errors in CLI-friendly messages.
    """
    try:
        client = ContextForgeClient()
        return resolve_slice_info(client, int(num))
    except ContextForgeNotAvailable:
        rprint(
            "[red]Error: Context Forge (cf) is not installed or not on PATH.[/red]\n"
            "Install it with: [bold]npm install -g @context-forge/cli[/bold]\n"
            "Then run: [bold]sq install-commands[/bold]"
        )
        raise typer.Exit(code=1) from None
    except (ContextForgeError, ValueError) as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


def _resolve_profile(
    flag: str | None,
    template: ReviewTemplate | None = None,
) -> str:
    """Resolve profile: CLI flag → template → config → sdk.

    Model-based inference is handled upstream by alias resolution
    in _run_review_command().
    """
    if flag is not None:
        return flag
    if template is not None and template.profile is not None:
        return template.profile
    config_val = get_config("default_review_profile")
    if isinstance(config_val, str):
        return config_val
    return "sdk"


def _resolve_model(
    flag: str | None,
    template: ReviewTemplate | None = None,
    template_name: str | None = None,
) -> str | None:
    """Resolve model: CLI flag → per-template config → global config → template default.

    Per-template config keys follow the pattern ``default_model_{template}``
    (e.g. ``default_model_arch``, ``default_model_code``).
    """
    if flag is not None:
        return flag
    # Per-template config (e.g. default_model_arch)
    if template_name is not None:
        try:
            tmpl_val = get_config(f"default_model_{template_name}")
            if isinstance(tmpl_val, str):
                return tmpl_val
        except KeyError:
            pass
    # Global default
    config_val = get_config("default_model")
    if isinstance(config_val, str):
        return config_val
    if template is not None and template.model is not None:
        return template.model
    return None


def _run_review_command(
    template_name: str,
    inputs: dict[str, str],
    output: str,
    output_path: str | None,
    verbosity: int = 0,
    rules_content: str | None = None,
    model_flag: str | None = None,
    profile_flag: str | None = None,
    rules_dir: Path | None = None,
) -> ReviewResult:
    """Common logic for running a review and displaying results.

    Returns the ReviewResult so callers can save it.
    """
    load_all_templates()
    template = get_template(template_name)
    if template is None:
        available = [t.name for t in list_templates()]
        rprint(f"[red]Error: Unknown template '{template_name}'. Available: {available}[/red]")
        raise typer.Exit(code=1)

    # Validate required inputs
    for req in template.required_inputs:
        if req.name not in inputs:
            rprint(
                f"[red]Error: Missing required input '{req.name}' for template '{template_name}'.[/red]"
            )
            raise typer.Exit(code=1)

    # input/against must name real files — a stale or mistyped path would
    # otherwise reach the model with its content silently absent, and the
    # model reviews a document it never saw (issue #18).
    for key, value in missing_input_files(inputs):
        rprint(f"[red]Error: {key} file not found: {value}[/red]")
        raise typer.Exit(code=1)

    # Prepend template-specific rules (review.md / review-{template}.md).
    # Language auto-detection is handled by the caller (review_code) where
    # file paths are known; _run_review_command only sees the template.
    if rules_dir is not None:
        rules_content = load_review_rules(
            template_name,
            rules_dir,
            file_paths=None,
            manual_rules_content=rules_content,
        )

    # Resolve model from flag → per-template config → config → template default
    raw_model = _resolve_model(model_flag, template, template_name)
    alias_model: str | None = None
    alias_profile: str | None = None
    if raw_model is not None:
        alias_model, alias_profile = resolve_model_alias(raw_model)

    resolved_model = alias_model or raw_model
    resolved_profile = _resolve_profile(profile_flag or alias_profile, template)

    try:
        result = asyncio.run(
            _execute_review(
                template,
                inputs,
                rules_content,
                resolved_model,
                resolved_profile,
                verbosity=verbosity,
            )
        )
    except RateLimitError as exc:
        rprint("[red]Error: Rate limited by the API. Please wait a moment and try again.[/red]")
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        rprint(f"[red]Error: Review failed — {exc}[/red]")
        raise typer.Exit(code=1) from exc

    display_result(result, output, output_path, verbosity)

    return result


async def _execute_review(
    template: ReviewTemplate,
    inputs: dict[str, str],
    rules_content: str | None = None,
    model: str | None = None,
    profile: str = "sdk",
    verbosity: int = 0,
) -> ReviewResult:
    """Execute the review asynchronously."""
    return await run_review_with_profile(
        template,
        inputs,
        profile=profile,
        rules_content=rules_content,
        model=model,
        verbosity=verbosity,
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@review_app.command("slice")
def review_slice(
    input_file: str = typer.Argument(help="Document to review (or slice number)"),
    against: str | None = typer.Option(
        None, "--against", help="Architecture document to review against"
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory (default: config or .)"),
    model: str | None = typer.Option(None, "--model", help="Model override (e.g. opus, sonnet)"),
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
    rules_dir_flag: str | None = typer.Option(None, "--rules-dir", help="Rules directory override"),
) -> None:
    """Run a slice design review."""
    slice_info: SliceInfo | None = None
    if input_file.isdigit():
        slice_info = _resolve_slice_number(input_file)
        if not slice_info["design_file"]:
            rprint(f"[red]Error: No design file for slice {slice_info['index']}.[/red]")
            raise typer.Exit(code=1)
        input_file = slice_info["design_file"]
        against = slice_info["arch_file"]

    if not against:
        rprint("[red]Error: --against is required when not using a slice number.[/red]")
        raise typer.Exit(code=1)

    if use_json:
        output = "json"

    verbosity = _resolve_verbosity(verbose)
    resolved_cwd = _resolve_cwd(cwd)
    resolved_rules_dir = resolve_rules_dir(resolved_cwd, None, rules_dir_flag)
    inputs = {
        "input": input_file,
        "against": against,
        "cwd": resolved_cwd,
    }
    result = _run_review_command(
        "slice",
        inputs,
        output,
        output_path,
        verbosity,
        model_flag=model,
        profile_flag=profile,
        rules_dir=resolved_rules_dir,
    )

    saved = True
    if slice_info and not no_save:
        saved = _save_and_report(result, "slice", slice_info, as_json=use_json, input_file=input_file)

    _exit_on(result.verdict, saved)


@review_app.command("arch")
def review_arch(
    input_file: str = typer.Argument(help="Architecture document to review (path or initiative index)"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory (default: config or .)"),
    model: str | None = typer.Option(None, "--model", help="Model override (e.g. opus, sonnet)"),
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
    rules_dir_flag: str | None = typer.Option(None, "--rules-dir", help="Rules directory override"),
) -> None:
    """Review an architecture document on its own merits."""
    arch_index: int | None = None
    if input_file.isdigit():
        arch_index = int(input_file)
        input_file = _resolve_arch_file(input_file)

    if use_json:
        output = "json"

    verbosity = _resolve_verbosity(verbose)
    resolved_cwd = _resolve_cwd(cwd)
    resolved_rules_dir = resolve_rules_dir(resolved_cwd, None, rules_dir_flag)
    inputs = {
        "input": input_file,
        "cwd": resolved_cwd,
    }
    result = _run_review_command(
        "arch",
        inputs,
        output,
        output_path,
        verbosity,
        model_flag=model,
        profile_flag=profile,
        rules_dir=resolved_rules_dir,
    )

    saved = True
    if arch_index is not None and not no_save:
        # Build a minimal SliceInfo for save — arch reviews use initiative index
        arch_name = (
            Path(input_file).stem.split(".", 1)[1]
            if "." in Path(input_file).stem
            else Path(input_file).stem
        )
        try:
            project_name = ContextForgeClient().get_project().name
        except (ContextForgeNotAvailable, ContextForgeError) as exc:
            _logger.warning("Could not resolve project name from ContextForge: %s", exc)
            project_name = "unknown"
        arch_slice_info = SliceInfo(
            index=arch_index,
            name=arch_name,
            slice_name=arch_name,
            design_file=None,
            task_files=[],
            arch_file=input_file,
            project=project_name,
        )
        saved = _save_and_report(
            result, "arch", arch_slice_info, as_json=use_json, input_file=input_file
        )

    _exit_on(result.verdict, saved)


@review_app.command("tasks")
def review_tasks(
    input_file: str = typer.Argument(help="Task breakdown file to review (or slice number)"),
    against: str | None = typer.Option(None, "--against", help="Parent slice design to review against"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory (default: config or .)"),
    model: str | None = typer.Option(None, "--model", help="Model override (e.g. opus, sonnet)"),
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
    rules_dir_flag: str | None = typer.Option(None, "--rules-dir", help="Rules directory override"),
) -> None:
    """Run a task plan review.

    When the slice's task breakdown is split across multiple files
    (e.g. ``161-tasks.name-1.md`` / ``161-tasks.name-2.md``), each
    file is reviewed separately against the same parent design and
    persisted under its own ``part-N`` suffix. The command's exit
    code reflects the worst verdict across all parts.
    """
    slice_info: SliceInfo | None = None
    task_file_paths: list[str] = []
    if input_file.isdigit():
        slice_info = _resolve_slice_number(input_file)
        if not slice_info["task_files"]:
            rprint(f"[red]Error: No task file for slice {slice_info['index']}.[/red]")
            raise typer.Exit(code=1)
        if not slice_info["design_file"]:
            rprint(f"[red]Error: No design file for slice {slice_info['index']}.[/red]")
            raise typer.Exit(code=1)
        task_file_paths = [str(TASKS_DIR / f) for f in slice_info["task_files"]]
        against = slice_info["design_file"]
    else:
        task_file_paths = [input_file]

    if not against:
        rprint("[red]Error: --against is required when not using a slice number.[/red]")
        raise typer.Exit(code=1)

    if use_json:
        output = "json"

    verbosity = _resolve_verbosity(verbose)
    resolved_cwd = _resolve_cwd(cwd)
    resolved_rules_dir = resolve_rules_dir(resolved_cwd, None, rules_dir_flag)

    results: list[tuple[str, object]] = []  # (task_path, ReviewResult)
    saved = True
    multi_part = len(task_file_paths) > 1
    for part_idx, task_path in enumerate(task_file_paths, start=1):
        if multi_part:
            rprint(
                f"[bold]Reviewing tasks part {part_idx} of {len(task_file_paths)}: {task_path}[/bold]"
            )
        inputs = {
            "input": task_path,
            "against": against,
            "cwd": resolved_cwd,
        }
        result = _run_review_command(
            "tasks",
            inputs,
            output,
            output_path,
            verbosity,
            model_flag=model,
            profile_flag=profile,
            rules_dir=resolved_rules_dir,
        )
        results.append((task_path, result))

        if slice_info and not no_save:
            suffix = f"part-{part_idx}" if multi_part else None
            # Every part is saved before exiting: the reviews have already been
            # paid for, so one unwritable part must not cost the others.
            saved = (
                _save_and_report(
                    result,
                    "tasks",
                    slice_info,
                    as_json=use_json,
                    input_file=task_path,
                    name_suffix=suffix,
                )
                and saved
            )

    _exit_on(_aggregate_verdicts([r for _, r in results]), saved)


@review_app.command("code")
def review_code(
    slice_number: str | None = typer.Argument(
        None, help="Optional slice number for context (e.g. 118)"
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Project directory (default: config or .)"),
    files: str | None = typer.Option(None, "--files", help="Glob pattern to scope the review"),
    diff: str | None = typer.Option(None, "--diff", help="Git ref to diff against"),
    rules: str | None = typer.Option(None, "--rules", help="Path to additional rules file"),
    rules_dir_flag: str | None = typer.Option(None, "--rules-dir", help="Rules directory override"),
    no_rules: bool = typer.Option(False, "--no-rules", help="Suppress all rule injection"),
    model: str | None = typer.Option(None, "--model", help="Model override (e.g. opus, sonnet)"),
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
    fan: int | None = typer.Option(
        None,
        "--fan",
        help="Fan-out width (reserved for slice 182; not yet functional)",
    ),
) -> None:
    """Run a code review."""
    if fan is not None:
        rprint("[yellow]--fan is reserved for future fan-out support (slice 182); ignored.[/yellow]")

    # Load template early to access diff_exclude_patterns
    load_all_templates()
    code_template = get_template("code")
    exclude_patterns = code_template.diff_exclude_patterns if code_template else None

    slice_info: SliceInfo | None = None
    if slice_number is not None and slice_number.isdigit():
        slice_info = _resolve_slice_number(slice_number)
        if not diff:
            resolved_cwd_for_diff = _resolve_cwd(cwd)
            try:
                diff = resolve_slice_diff_range(int(slice_number), resolved_cwd_for_diff)
            except DiffRangeUnresolvedError as exc:
                rprint(f"[red]Error: {exc}[/red]")
                raise typer.Exit(code=1) from exc

    if not slice_info and not diff and not files:
        if slice_number is not None:
            rprint(
                f"[red]Error: slice number '{slice_number}' is not numeric; "
                "provide a numeric slice, --diff, or --files.[/red]"
            )
        else:
            rprint("[red]Error: provide a slice number, --diff, or --files.[/red]")
        raise typer.Exit(code=1)

    if use_json:
        output = "json"

    verbosity = _resolve_verbosity(verbose)
    resolved_cwd = _resolve_cwd(cwd)
    # Code review runs git commands — use the git root so diff and rules work
    # correctly even when config cwd points to a subdirectory.
    review_cwd = find_git_root(resolved_cwd) or resolved_cwd

    rules_content: str | None = None
    resolved_rules_dir: Path | None = None

    if not no_rules:
        # Resolve explicit rules file: CLI flag > config default
        rules_path = rules
        if not rules_path:
            config_rules = get_config("default_rules")
            if isinstance(config_rules, str):
                rules_path = config_rules
        manual_content = _resolve_rules_content(rules_path)

        # Resolve rules dir and changed-file paths for language auto-detection.
        # Rules live in the repo root (.claude/rules/), not the config cwd.
        resolved_rules_dir = resolve_rules_dir(review_cwd, None, rules_dir_flag)
        file_paths: list[str] = []
        if resolved_rules_dir is not None:
            file_paths = extract_diff_paths(diff, review_cwd, exclude_patterns) if diff else []
            if not file_paths and files:
                import glob as _glob

                file_paths = _glob.glob(files, root_dir=review_cwd)

        rules_content = load_review_rules(
            "code",
            resolved_rules_dir,
            file_paths=file_paths,
            manual_rules_content=manual_content,
        )

    inputs: dict[str, str] = {"cwd": review_cwd}
    if files:
        inputs["files"] = files
    if diff:
        inputs["diff"] = diff
    if exclude_patterns:
        inputs["diff_exclude_patterns"] = ",".join(exclude_patterns)
    result = _run_review_command(
        "code",
        inputs,
        output,
        output_path,
        verbosity,
        rules_content,
        model_flag=model,
        profile_flag=profile,
        # rules_content is already fully assembled above (template rules +
        # language auto-detection + manual override) — passing rules_dir here
        # too would make _run_review_command redundantly re-prepend template
        # rules onto content that already has them (issue #24).
        rules_dir=None,
    )

    saved = True
    if slice_info and not no_save:
        saved = _save_and_report(result, "code", slice_info, as_json=use_json)

    _exit_on(result.verdict, saved)


@review_app.command("list")
def review_list() -> None:
    """List available review templates."""
    load_all_templates()
    templates = list_templates()
    if not templates:
        rprint("[dim]No templates available.[/dim]")
        return

    rprint("[bold]Available review templates:[/bold]")
    max_name_len = max(len(t.name) for t in templates)
    for t in templates:
        rprint(f"  {t.name:<{max_name_len}}  {t.description}")


def _resolve_judge_model(model_flag: str | None, profile_flag: str | None) -> tuple[str | None, str]:
    """Resolve the resolve-path judge's model and profile from the CLI flags.

    Same cascade every other review command uses — flag → per-template config →
    global config → template default, with alias expansion — so the judge is
    selected the same way here as anywhere else.
    """
    load_all_templates()
    template = get_template(JUDGE_TEMPLATE_NAME)
    raw_model = _resolve_model(model_flag, template, JUDGE_TEMPLATE_NAME)

    alias_model: str | None = None
    alias_profile: str | None = None
    if raw_model is not None:
        alias_model, alias_profile = resolve_model_alias(raw_model)

    return alias_model or raw_model, _resolve_profile(profile_flag or alias_profile, template)


def _display_resolution(result: ResolutionResult, verbosity: int) -> None:
    """Per-finding table, then where the artifact landed and what it concluded."""
    console = Console()
    color = _RESOLUTION_COLORS.get(result.resolution, "dim")

    header = Text(f"Resolution: {result.review_path.name}", style="bold")
    header.append("  ", style="dim")
    header.append(result.resolution.value, style=f"bold {color}")
    console.print(Panel(header, expand=False))

    if result.outcomes:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Finding")
        table.add_column("Status")
        table.add_column("Settled by")
        if verbosity >= 1:
            table.add_column("Note")
        for outcome in result.outcomes:
            row = [outcome.finding_id, outcome.status.value, outcome.screen.value]
            if verbosity >= 1:
                row.append(outcome.note or "")
            table.add_row(*row)
        console.print(table)
    else:
        console.print("  No CONCERN+ findings were in scope.", style="dim")

    base = result.base or "unresolved"
    source = result.base_source.value if result.base_source is not None else "not needed"
    console.print(f"  measured against {base} ({source})", style="dim")
    rprint(f"[green]Wrote resolution to {result.artifact_path}[/green]")
    rprint(f"resolution: {result.resolution.value}")


@review_app.command("resolve")
def review_resolve(
    index: int = typer.Argument(..., help="Slice number whose review to resolve (e.g. 305)"),
    review_type: str | None = typer.Argument(
        None, help="Review type (e.g. code, slice); inferred when only one review exists"
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Project directory (default: config or .)"),
    model: str | None = typer.Option(None, "--model", help="Judge model override (e.g. opus)"),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Provider profile (e.g. openrouter, openai, local, sdk)",
    ),
    no_judge: bool = typer.Option(
        False, "--no-judge", help="Run the deterministic screens only; never consult the judge"
    ),
    since: str | None = typer.Option(
        None, "--since", help="Git ref to measure from, overriding the review's reviewedSha"
    ),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, help="Verbosity level (-v, -vv)"),
) -> None:
    """Record whether a prior review's findings were addressed.

    Writes a resolution artifact beside the review and never edits the review
    itself. Exits 0 on ADDRESSED so the command composes in a shell; UNADDRESSED
    and UNKNOWN both exit 1 — an answer that could not be reached is not a pass.
    """
    verbosity = _resolve_verbosity(verbose)
    resolved_cwd = _resolve_cwd(cwd)
    # The resolve path runs git commands — use the git root so the diff resolves
    # even when the config cwd points at a subdirectory (mirrors review code).
    review_cwd = find_git_root(resolved_cwd) or resolved_cwd

    model_id, resolved_profile = _resolve_judge_model(model, profile)

    try:
        result = asyncio.run(
            resolve_review(
                index,
                review_type,
                model_id=model_id,
                profile=resolved_profile,
                no_judge=no_judge,
                since=since,
                cwd=review_cwd,
            )
        )
    except (ResolutionError, OSError) as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    _display_resolution(result, verbosity)

    if result.resolution != Resolution.ADDRESSED:
        raise typer.Exit(code=1)
