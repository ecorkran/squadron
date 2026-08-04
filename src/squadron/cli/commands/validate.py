"""validate subcommand — mechanical frontmatter enforcement."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from squadron.config.keys import CONFIG_KEYS
from squadron.config.manager import get_config
from squadron.documents.validate import (
    DocumentRootError,
    Violation,
    validate_paths_with_checked,
)

validate_app = typer.Typer(
    name="validate",
    help="Validate process-document frontmatter against the canonical schema.",
    no_args_is_help=True,
)

_EXIT_CLEAN = 0
_EXIT_VIOLATIONS = 1
_EXIT_INVOCATION_ERROR = 2


def _format_violation(violation: Violation) -> str:
    key_part = f" {violation.key}" if violation.key else ""
    detail_part = f": {violation.detail}" if violation.detail else ""
    actual_part = f" {violation.actual!r} is not valid" if violation.actual is not None else ""
    message = f"{violation.path}:{violation.line}: {violation.code}{key_part}{actual_part}{detail_part}"
    if not violation.accepted:
        return message
    accepted_line = "    accepted: " + " | ".join(violation.accepted)
    return f"{message}\n{accepted_line}"


@validate_app.command("docs")
def validate_docs(
    paths: list[Path] = typer.Argument(None, help="Paths to validate (default: walk the root)"),
    root: Path | None = typer.Option(None, "--root", help="Override validate.docs_root"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="Suppress the summary line"),
) -> None:
    """Validate process-document frontmatter against the canonical schema.

    With no PATHS, walks the configured document root. With PATHS, validates
    only those that fall under the root — others are silently skipped, so a
    caller may pass an unfiltered file list.
    """
    docs_root_key = CONFIG_KEYS["validate.docs_root"].name
    resolved_root = root if root is not None else Path(str(get_config(docs_root_key)))

    try:
        checked, violations = validate_paths_with_checked(paths or None, root=resolved_root)
    except DocumentRootError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=_EXIT_INVOCATION_ERROR) from exc

    for violation in violations:
        print(_format_violation(violation))

    if not quiet:
        violating_files = {v.path for v in violations}
        summary = (
            f"{len(checked)} documents checked, "
            f"{len(violations)} violations in {len(violating_files)} files"
        )
        print(summary, file=sys.stderr)

    raise typer.Exit(code=_EXIT_VIOLATIONS if violations else _EXIT_CLEAN)
