"""install-commands / uninstall-commands — manage Claude Code slash commands."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich import print as rprint

from squadron.cli.commands.install_settings import remove_precompact_hook


def _get_commands_source() -> Path:
    """Locate the bundled commands directory.

    In a wheel install, importlib.resources resolves to the package-internal
    commands/ directory. In a dev/editable install, the force-include hasn't
    taken effect, so we fall back to the repo-root commands/ directory.
    """
    from importlib.resources import files

    pkg_path = Path(str(files("squadron") / "commands"))
    if pkg_path.is_dir() and any(pkg_path.iterdir()):
        return pkg_path

    # Dev fallback: walk up from src/squadron/ to repo root
    repo_root = Path(str(files("squadron"))).parent.parent
    dev_path = repo_root / "commands"
    if dev_path.is_dir():
        return dev_path

    rprint("[red]Error: Could not locate bundled command files.[/red]")
    raise typer.Exit(code=1)


def install_commands(
    target: str = typer.Option(
        "~/.claude/commands",
        "--target",
        help="Target directory for command files",
    ),
) -> None:
    """Install squadron slash commands for Claude Code.

    Note: the PreCompact hook is no longer installed by default. Claude
    Code's PreCompact hook API has no documented way to override
    compaction instructions — the hook's output fields (``systemMessage``
    et al.) cannot authoritatively replace the default summarizer prompt,
    and injection behavior is inconsistent across Claude Code versions.
    Use ``sq run`` pipelines from a standard terminal for deterministic,
    project-aware compaction (see slice 158). ``sq uninstall-commands``
    will still remove a previously installed squadron PreCompact entry.
    """
    source = _get_commands_source()
    target_dir = Path(target).expanduser()

    installed: list[str] = []
    removed: list[str] = []
    for sub in sorted(source.iterdir()):
        if not sub.is_dir():
            continue
        dest_sub = target_dir / sub.name
        dest_sub.mkdir(parents=True, exist_ok=True)
        source_files = {md_file.name for md_file in sub.glob("*.md")}
        for md_file in sorted(sub.glob("*.md")):
            shutil.copy2(md_file, dest_sub / md_file.name)
            installed.append(f"{sub.name}/{md_file.name}")
        for existing in sorted(dest_sub.glob("*.md")):
            if existing.name not in source_files:
                existing.unlink()
                removed.append(f"{sub.name}/{existing.name}")

    if not installed:
        rprint("[yellow]No command files found to install.[/yellow]")
    else:
        rprint(f"[green]Installed {len(installed)} command(s) to {target_dir}:[/green]")
        for name in installed:
            rprint(f"  {name}")

        if removed:
            rprint(f"[yellow]Removed {len(removed)} stale command(s):[/yellow]")
            for name in removed:
                rprint(f"  {name}")


def uninstall_commands(
    target: str = typer.Option(
        "~/.claude/commands",
        "--target",
        help="Target directory to remove commands from",
    ),
    hook_target: str = typer.Option(
        "./.claude/settings.json",
        "--hook-target",
        help="Target settings.json to remove the PreCompact hook entry from",
    ),
) -> None:
    """Remove squadron slash commands from Claude Code."""
    target_dir = Path(target).expanduser()
    sq_dir = target_dir / "sq"

    if not sq_dir.is_dir():
        rprint(f"[yellow]Nothing to remove — {sq_dir} does not exist.[/yellow]")
    else:
        files_removed = list(sq_dir.glob("*.md"))
        shutil.rmtree(sq_dir)
        rprint(f"[green]Removed {sq_dir} ({len(files_removed)} file(s)).[/green]")

    # Remove the PreCompact hook entry from the project-local settings.json.
    hook_path = Path(hook_target).expanduser()
    try:
        removed = remove_precompact_hook(hook_path)
    except RuntimeError as exc:
        rprint(f"[red]Error removing PreCompact hook: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    if removed:
        rprint(f"[green]Removed PreCompact hook from {hook_path}[/green]")
