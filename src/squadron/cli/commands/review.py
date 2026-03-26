"""review subcommand — execute review workflows via templates."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TypedDict

import typer
from openai import RateLimitError
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from squadron.config.manager import get_config
from squadron.integrations.context_forge import (
    ContextForgeClient,
    ContextForgeError,
    ContextForgeNotAvailable,
)
from squadron.models.aliases import resolve_model_alias
from squadron.review.git_utils import resolve_slice_diff_range
from squadron.review.models import ReviewResult, Severity, Verdict
from squadron.review.review_client import run_review_with_profile
from squadron.review.rules import (
    detect_languages_from_paths,
    get_template_rules,
    load_rules_content,
    load_rules_frontmatter,
    match_rules_files,
    resolve_rules_dir,
)
from squadron.review.templates import (
    ReviewTemplate,
    get_template,
    list_templates,
    load_all_templates,
)

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

_SEVERITY_COLORS: dict[Severity, str] = {
    Severity.PASS: "bright_green",
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
        console.print(
            f"  [{sev_color}][{finding.severity.value}][/{sev_color}] "
            f"[bold white]{finding.title}[/bold white]"
        )
        if verbosity >= 1 and finding.description:
            for line in finding.description.split("\n"):
                console.print(f"    {line}")
        if verbosity >= 1 and finding.file_ref:
            console.print(f"    -> {finding.file_ref}", style="cyan")


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
# Review file persistence
# ---------------------------------------------------------------------------


def _format_review_markdown(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo,
    input_file: str | None = None,
) -> str:
    """Format a ReviewResult as markdown with YAML frontmatter."""
    today = result.timestamp.strftime("%Y%m%d")
    source_doc = input_file or slice_info.get("design_file") or ""
    lines = [
        "---",
        "docType: review",
        "layer: project",
        f"reviewType: {review_type}",
        f"slice: {slice_info['slice_name']}",
        "project: squadron",
        f"verdict: {result.verdict.value}",
        f"sourceDocument: {source_doc}",
        f"aiModel: {result.model or 'unknown'}",
        "status: complete",
        f"dateCreated: {today}",
        f"dateUpdated: {today}",
        "---",
        "",
        f"# Review: {review_type} — slice {slice_info['index']}",
        "",
        f"**Verdict:** {result.verdict.value}",
        f"**Model:** {result.model or 'default'}",
        "",
    ]

    if result.findings:
        lines.append("## Findings")
        lines.append("")
        for finding in result.findings:
            lines.append(f"### [{finding.severity.value}] {finding.title}")
            if finding.description:
                lines.append("")
                lines.append(finding.description)
            if finding.file_ref:
                lines.append(f"\n-> {finding.file_ref}")
            lines.append("")
    else:
        lines.append("No specific findings.")
        lines.append("")

    return "\n".join(lines)


_REVIEWS_DIR = Path("project-documents/user/reviews")


def _save_review_file(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo,
    as_json: bool = False,
    reviews_dir: Path | None = None,
    input_file: str | None = None,
) -> Path:
    """Save review output to the reviews directory.

    Returns the path of the saved file.
    """
    target = reviews_dir or _REVIEWS_DIR
    target.mkdir(parents=True, exist_ok=True)

    base = f"{slice_info['index']}-review.{review_type}.{slice_info['slice_name']}"

    if as_json:
        path = target / f"{base}.json"
        path.write_text(json.dumps(result.to_dict(), indent=2))
    else:
        path = target / f"{base}.md"
        path.write_text(
            _format_review_markdown(result, review_type, slice_info, input_file)
        )

    return path


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


def _resolve_verbosity(verbose: int) -> int:
    """Resolve verbosity: CLI flag overrides config default."""
    if verbose > 0:
        return verbose
    config_val = get_config("verbosity")
    if isinstance(config_val, int):
        return config_val
    return 0


def _resolve_rules_content(rules_path: str | None) -> str | None:
    """Read rules file content if a path is provided."""
    if not rules_path:
        return None
    path = Path(rules_path)
    if not path.is_file():
        rprint(f"[red]Error: Rules file not found: {rules_path}[/red]")
        raise typer.Exit(code=1)
    return path.read_text()


def _extract_diff_paths(diff_ref: str, cwd: str) -> list[str]:
    """Run git diff and extract +++ b/ file paths."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", diff_ref],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (FileNotFoundError, OSError):
        pass
    return []


class SliceInfo(TypedDict):
    """Resolved slice metadata from Context-Forge."""

    index: int
    name: str
    slice_name: str
    design_file: str | None
    task_files: list[str]
    arch_file: str


def _resolve_slice_number(num: str) -> SliceInfo:
    """Resolve a bare slice number to file paths via Context-Forge.

    Uses ``ContextForgeClient`` to call ``cf list slices --json``,
    ``cf list tasks --json``, and ``cf get --json``.
    """
    index = int(num)

    try:
        client = ContextForgeClient()

        # --- slice list ---
        slices = client.list_slices()
        match = next((s for s in slices if s.index == index), None)
        if match is None:
            rprint(
                f"[red]Error: No slice with index {index}"
                " in the current slice plan.[/red]"
            )
            raise typer.Exit(code=1)

        design_file = match.design_file
        # derive kebab-case slice name from design file path or entry name
        if design_file:
            stem = Path(design_file).stem
            slice_name = stem.split(".", 1)[1] if "." in stem else stem
        else:
            slice_name = match.name.lower().replace(" ", "-")

        # --- tasks list ---
        tasks = client.list_tasks()
        task_match = next((t for t in tasks if t.index == index), None)
        task_files = task_match.files if task_match else []

        # --- architecture doc ---
        project = client.get_project()
        arch_file = project.arch_file

    except ContextForgeNotAvailable:
        rprint(
            "[red]Error: 'cf' (Context-Forge CLI) is not installed"
            " or not on PATH.[/red]"
        )
        raise typer.Exit(code=1)
    except ContextForgeError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    return SliceInfo(
        index=index,
        name=match.name,
        slice_name=slice_name,
        design_file=design_file,
        task_files=task_files,
        arch_file=arch_file,
    )


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
    flag: str | None, template: ReviewTemplate | None = None
) -> str | None:
    """Resolve model: CLI flag → config → template default → None (SDK default)."""
    if flag is not None:
        return flag
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
        rprint(
            f"[red]Error: Unknown template '{template_name}'."
            f" Available: {available}[/red]"
        )
        raise typer.Exit(code=1)

    # Validate required inputs
    for req in template.required_inputs:
        if req.name not in inputs:
            rprint(
                f"[red]Error: Missing required input '{req.name}'"
                f" for template '{template_name}'.[/red]"
            )
            raise typer.Exit(code=1)

    # Prepend template-specific rules (review.md / review-{template}.md)
    if rules_dir is not None:
        template_rules = get_template_rules(template_name, rules_dir)
        if template_rules:
            rules_content = (
                template_rules
                if rules_content is None
                else f"{template_rules}\n\n---\n\n{rules_content}"
            )

    # Resolve model from flag → config → template, then resolve alias
    raw_model = _resolve_model(model_flag, template)
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
        rprint(
            "[red]Error: Rate limited by the API. "
            "Please wait a moment and try again.[/red]"
        )
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        rprint(f"[red]Error: Review failed — {exc}[/red]")
        raise typer.Exit(code=1) from exc

    display_result(result, output, output_path, verbosity)

    # Exit with non-zero if review has failures
    if result.verdict == Verdict.FAIL:
        raise typer.Exit(code=2)

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
    cwd: str | None = typer.Option(
        None, "--cwd", help="Working directory (default: config or .)"
    ),
    model: str | None = typer.Option(
        None, "--model", help="Model override (e.g. opus, sonnet)"
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Provider profile (e.g. openrouter, openai, local, sdk)",
    ),
    verbose: int = typer.Option(
        0, "--verbose", "-v", count=True, help="Verbosity level (-v, -vv)"
    ),
    output: str = typer.Option(
        "terminal", "--output", help="Output format: terminal, json, file"
    ),
    output_path: str | None = typer.Option(
        None, "--output-path", help="File path for --output file"
    ),
    use_json: bool = typer.Option(
        False, "--json", help="Output and save as JSON instead of markdown"
    ),
    no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
    rules_dir_flag: str | None = typer.Option(
        None, "--rules-dir", help="Rules directory override"
    ),
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

    if slice_info and not no_save:
        path = _save_review_file(
            result, "slice", slice_info, as_json=use_json, input_file=input_file
        )
        rprint(f"[green]Saved review to {path}[/green]")


@review_app.command("arch", hidden=True)
def review_arch(
    input_file: str = typer.Argument(help="Document to review (or slice number)"),
    against: str | None = typer.Option(
        None, "--against", help="Architecture document to review against"
    ),
    cwd: str | None = typer.Option(
        None, "--cwd", help="Working directory (default: config or .)"
    ),
    model: str | None = typer.Option(
        None, "--model", help="Model override (e.g. opus, sonnet)"
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Provider profile (e.g. openrouter, openai, local, sdk)",
    ),
    verbose: int = typer.Option(
        0, "--verbose", "-v", count=True, help="Verbosity level (-v, -vv)"
    ),
    output: str = typer.Option(
        "terminal", "--output", help="Output format: terminal, json, file"
    ),
    output_path: str | None = typer.Option(
        None, "--output-path", help="File path for --output file"
    ),
    use_json: bool = typer.Option(
        False, "--json", help="Output and save as JSON instead of markdown"
    ),
    no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
) -> None:
    """Run a slice design review (deprecated: use 'review slice')."""
    rprint(
        "[yellow]Warning: 'review arch' is deprecated,"
        " use 'review slice' instead[/yellow]"
    )
    review_slice(
        input_file=input_file,
        against=against,
        cwd=cwd,
        model=model,
        profile=profile,
        verbose=verbose,
        output=output,
        output_path=output_path,
        use_json=use_json,
        no_save=no_save,
        rules_dir_flag=None,
    )


@review_app.command("tasks")
def review_tasks(
    input_file: str = typer.Argument(
        help="Task breakdown file to review (or slice number)"
    ),
    against: str | None = typer.Option(
        None, "--against", help="Parent slice design to review against"
    ),
    cwd: str | None = typer.Option(
        None, "--cwd", help="Working directory (default: config or .)"
    ),
    model: str | None = typer.Option(
        None, "--model", help="Model override (e.g. opus, sonnet)"
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Provider profile (e.g. openrouter, openai, local, sdk)",
    ),
    verbose: int = typer.Option(
        0, "--verbose", "-v", count=True, help="Verbosity level (-v, -vv)"
    ),
    output: str = typer.Option(
        "terminal", "--output", help="Output format: terminal, json, file"
    ),
    output_path: str | None = typer.Option(
        None, "--output-path", help="File path for --output file"
    ),
    use_json: bool = typer.Option(
        False, "--json", help="Output and save as JSON instead of markdown"
    ),
    no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
    rules_dir_flag: str | None = typer.Option(
        None, "--rules-dir", help="Rules directory override"
    ),
) -> None:
    """Run a task plan review."""
    slice_info: SliceInfo | None = None
    if input_file.isdigit():
        slice_info = _resolve_slice_number(input_file)
        if not slice_info["task_files"]:
            rprint(f"[red]Error: No task file for slice {slice_info['index']}.[/red]")
            raise typer.Exit(code=1)
        if not slice_info["design_file"]:
            rprint(f"[red]Error: No design file for slice {slice_info['index']}.[/red]")
            raise typer.Exit(code=1)
        input_file = f"project-documents/user/tasks/{slice_info['task_files'][0]}"
        against = slice_info["design_file"]

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
        "tasks",
        inputs,
        output,
        output_path,
        verbosity,
        model_flag=model,
        profile_flag=profile,
        rules_dir=resolved_rules_dir,
    )

    if slice_info and not no_save:
        path = _save_review_file(
            result, "tasks", slice_info, as_json=use_json, input_file=input_file
        )
        rprint(f"[green]Saved review to {path}[/green]")


@review_app.command("code")
def review_code(
    slice_number: str | None = typer.Argument(
        None, help="Optional slice number for context (e.g. 118)"
    ),
    cwd: str | None = typer.Option(
        None, "--cwd", help="Project directory (default: config or .)"
    ),
    files: str | None = typer.Option(
        None, "--files", help="Glob pattern to scope the review"
    ),
    diff: str | None = typer.Option(None, "--diff", help="Git ref to diff against"),
    rules: str | None = typer.Option(
        None, "--rules", help="Path to additional rules file"
    ),
    rules_dir_flag: str | None = typer.Option(
        None, "--rules-dir", help="Rules directory override"
    ),
    no_rules: bool = typer.Option(
        False, "--no-rules", help="Suppress all rule injection"
    ),
    model: str | None = typer.Option(
        None, "--model", help="Model override (e.g. opus, sonnet)"
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Provider profile (e.g. openrouter, openai, local, sdk)",
    ),
    verbose: int = typer.Option(
        0, "--verbose", "-v", count=True, help="Verbosity level (-v, -vv)"
    ),
    output: str = typer.Option(
        "terminal", "--output", help="Output format: terminal, json, file"
    ),
    output_path: str | None = typer.Option(
        None, "--output-path", help="File path for --output file"
    ),
    use_json: bool = typer.Option(
        False, "--json", help="Output and save as JSON instead of markdown"
    ),
    no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
) -> None:
    """Run a code review."""
    slice_info: SliceInfo | None = None
    if slice_number is not None and slice_number.isdigit():
        slice_info = _resolve_slice_number(slice_number)
        if not diff:
            resolved_cwd_for_diff = _resolve_cwd(cwd)
            diff = resolve_slice_diff_range(
                int(slice_number), resolved_cwd_for_diff
            )

    if use_json:
        output = "json"

    verbosity = _resolve_verbosity(verbose)
    resolved_cwd = _resolve_cwd(cwd)

    rules_content: str | None = None
    resolved_rules_dir: Path | None = None

    if not no_rules:
        # Resolve explicit rules file: CLI flag > config default
        rules_path = rules
        if not rules_path:
            config_rules = get_config("default_rules")
            if isinstance(config_rules, str):
                rules_path = config_rules
        rules_content = _resolve_rules_content(rules_path)

        # Auto-detect language rules from diff or files input
        resolved_rules_dir = resolve_rules_dir(resolved_cwd, None, rules_dir_flag)
        if resolved_rules_dir is not None:
            file_paths = _extract_diff_paths(diff, resolved_cwd) if diff else []
            if not file_paths and files:
                import glob as _glob

                file_paths = _glob.glob(files, root_dir=resolved_cwd)
            if file_paths:
                extensions = detect_languages_from_paths(file_paths)
                frontmatter = load_rules_frontmatter(resolved_rules_dir)
                auto_files = match_rules_files(
                    extensions, resolved_rules_dir, frontmatter
                )
                auto_content = load_rules_content(auto_files)
                if auto_content:
                    rules_content = (
                        auto_content
                        if rules_content is None
                        else f"{rules_content}\n\n---\n\n{auto_content}"
                    )

    inputs: dict[str, str] = {"cwd": resolved_cwd}
    if files:
        inputs["files"] = files
    if diff:
        inputs["diff"] = diff
    result = _run_review_command(
        "code",
        inputs,
        output,
        output_path,
        verbosity,
        rules_content,
        model_flag=model,
        profile_flag=profile,
        rules_dir=resolved_rules_dir,
    )

    if slice_info and not no_save:
        path = _save_review_file(result, "code", slice_info, as_json=use_json)
        rprint(f"[green]Saved review to {path}[/green]")


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
