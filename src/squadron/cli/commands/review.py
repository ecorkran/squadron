"""review subcommand — execute review workflows via templates."""

from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import TypedDict

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from squadron.config.manager import get_config
from squadron.review.models import ReviewResult, Severity, Verdict
from squadron.review.runner import run_review
from squadron.review.templates import (
    ReviewTemplate,
    get_template,
    list_templates,
    load_builtin_templates,
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
    Level 2: above + raw output (tool usage details)
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
        if verbosity >= 2 and result.raw_output:
            console.print()
            console.rule("Raw Output", style="dim")
            console.print(result.raw_output)
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

    if verbosity >= 2 and result.raw_output:
        console.print()
        console.rule("Raw Output", style="dim")
        console.print(result.raw_output)


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
) -> str:
    """Format a ReviewResult as markdown with YAML frontmatter."""
    today = result.timestamp.strftime("%Y%m%d")
    lines = [
        "---",
        "docType: review",
        f"reviewType: {review_type}",
        f"slice: {slice_info['slice_name']}",
        "project: squadron",
        f"verdict: {result.verdict.value}",
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

    if result.raw_output:
        lines.append("## Raw Output")
        lines.append("")
        lines.append(result.raw_output)

    return "\n".join(lines)


_REVIEWS_DIR = Path("project-documents/user/reviews")


def _save_review_file(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo,
    as_json: bool = False,
    reviews_dir: Path | None = None,
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
        path.write_text(_format_review_markdown(result, review_type, slice_info))

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


class SliceInfo(TypedDict):
    """Resolved slice metadata from Context-Forge."""

    index: int
    name: str
    slice_name: str
    design_file: str | None
    task_files: list[str]
    arch_file: str


def _run_cf(args: list[str]) -> str:
    """Run a cf CLI command and return stdout. Exit on failure."""
    try:
        result = subprocess.run(
            ["cf", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        rprint(
            "[red]Error: 'cf' (Context-Forge CLI) is not installed"
            " or not on PATH.[/red]"
        )
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as exc:
        rprint(f"[red]Error running 'cf {' '.join(args)}': {exc.stderr.strip()}[/red]")
        raise typer.Exit(code=1) from exc
    return result.stdout


def _resolve_slice_number(num: str) -> SliceInfo:
    """Resolve a bare slice number to file paths via Context-Forge.

    Shells out to ``cf slice list --json``, ``cf tasks list --json``,
    and ``cf get --json`` to resolve design file, task files, and
    architecture document for the given slice index.
    """
    index = int(num)

    # --- slice list ---
    slice_data = json.loads(_run_cf(["slice", "list", "--json"]))
    match = next(
        (e for e in slice_data.get("entries", []) if e.get("index") == index),
        None,
    )
    if match is None:
        rprint(
            f"[red]Error: No slice with index {index} in the current slice plan.[/red]"
        )
        raise typer.Exit(code=1)

    design_file: str | None = match.get("designFile")
    # derive kebab-case slice name from design file path or entry name
    if design_file:
        stem = Path(design_file).stem  # e.g. "118-slice.composed-workflows"
        slice_name = stem.split(".", 1)[1] if "." in stem else stem
    else:
        slice_name = match["name"].lower().replace(" ", "-")

    # --- tasks list ---
    tasks_data = json.loads(_run_cf(["tasks", "list", "--json"]))
    task_match = next(
        (e for e in tasks_data if e.get("index") == index),
        None,
    )
    task_files: list[str] = []
    if task_match and task_match.get("files"):
        task_files = task_match["files"]

    # --- architecture doc ---
    project_data = json.loads(_run_cf(["get", "--json"]))
    arch_raw = project_data.get("fileArch", "")
    # fileArch is a name like "100-arch.orchestration-v2", resolve to path
    arch_file = f"project-documents/user/architecture/{arch_raw}.md" if arch_raw else ""

    return SliceInfo(
        index=index,
        name=match["name"],
        slice_name=slice_name,
        design_file=design_file,
        task_files=task_files,
        arch_file=arch_file,
    )


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
) -> ReviewResult:
    """Common logic for running a review and displaying results.

    Returns the ReviewResult so callers can save it.
    """
    load_builtin_templates()
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

    resolved_model = _resolve_model(model_flag, template)

    try:
        result = asyncio.run(
            _execute_review(template, inputs, rules_content, resolved_model)
        )
    except Exception as exc:
        err_str = str(exc).lower()
        if "rate_limit" in err_str:
            rprint(
                "[red]Error: Rate limited by the API. "
                "Please wait a moment and try again.[/red]"
            )
        else:
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
) -> ReviewResult:
    """Execute the review asynchronously."""
    return await run_review(template, inputs, rules_content=rules_content, model=model)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@review_app.command("arch")
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
    """Run an architectural review."""
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
    inputs = {"input": input_file, "against": against, "cwd": resolved_cwd}
    result = _run_review_command(
        "arch", inputs, output, output_path, verbosity, model_flag=model
    )

    if slice_info and not no_save:
        path = _save_review_file(result, "arch", slice_info, as_json=use_json)
        rprint(f"[green]Saved review to {path}[/green]")


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
    inputs = {"input": input_file, "against": against, "cwd": resolved_cwd}
    result = _run_review_command(
        "tasks", inputs, output, output_path, verbosity, model_flag=model
    )

    if slice_info and not no_save:
        path = _save_review_file(result, "tasks", slice_info, as_json=use_json)
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
    model: str | None = typer.Option(
        None, "--model", help="Model override (e.g. opus, sonnet)"
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
            diff = "main"

    if use_json:
        output = "json"

    verbosity = _resolve_verbosity(verbose)
    resolved_cwd = _resolve_cwd(cwd)

    # Resolve rules: CLI flag > config default
    rules_path = rules
    if not rules_path:
        config_rules = get_config("default_rules")
        if isinstance(config_rules, str):
            rules_path = config_rules
    rules_content = _resolve_rules_content(rules_path)

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
    )

    if slice_info and not no_save:
        path = _save_review_file(result, "code", slice_info, as_json=use_json)
        rprint(f"[green]Saved review to {path}[/green]")


@review_app.command("list")
def review_list() -> None:
    """List available review templates."""
    load_builtin_templates()
    templates = list_templates()
    if not templates:
        rprint("[dim]No templates available.[/dim]")
        return

    rprint("[bold]Available review templates:[/bold]")
    max_name_len = max(len(t.name) for t in templates)
    for t in templates:
        rprint(f"  {t.name:<{max_name_len}}  {t.description}")
