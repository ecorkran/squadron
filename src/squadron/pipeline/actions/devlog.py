"""Devlog action — writes a structured DEVLOG entry."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from squadron.pipeline.actions import ActionType, register_action
from squadron.pipeline.models import ActionContext, ActionResult, ValidationError

_DATE_HEADER_RE = re.compile(r"^## \d{8}$")


class DevlogAction:
    """Pipeline action that appends a structured entry to DEVLOG.md."""

    @property
    def action_type(self) -> str:
        return ActionType.DEVLOG

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        errors: list[ValidationError] = []
        has_content = "content" in config
        has_prior = bool(config.get("_has_prior_outputs"))

        if not has_content and not has_prior:
            errors.append(
                ValidationError(
                    field="content",
                    message=(
                        "No 'content' provided and no prior_outputs available "
                        "— entry will be minimal"
                    ),
                    action_type=self.action_type,
                )
            )
        return errors

    async def execute(self, context: ActionContext) -> ActionResult:
        # Determine file path
        path_param = context.params.get("path")
        devlog_path = (
            Path(str(path_param)) if path_param else Path(context.cwd) / "DEVLOG.md"
        )

        # Build entry content
        content = context.params.get("content")
        if content:
            entry_text = str(content)
        else:
            entry_text = _auto_generate(context)

        # Build full entry with title
        title = context.params.get("title")
        if title:
            entry = f"**{title}**\n{entry_text}"
        else:
            entry = f"**{context.pipeline_name}: {context.step_name}**\n{entry_text}"

        today = date.today().strftime("%Y%m%d")
        today_header = f"## {today}"

        try:
            lines = _read_or_create(devlog_path)
            updated = _insert_entry(lines, today_header, entry)
            devlog_path.write_text("\n".join(updated))
        except OSError as exc:
            return ActionResult(
                success=False,
                action_type=self.action_type,
                outputs={},
                error=str(exc),
            )

        return ActionResult(
            success=True,
            action_type=self.action_type,
            outputs={"path": str(devlog_path), "entry": entry},
        )


def _auto_generate(context: ActionContext) -> str:
    """Build an entry from prior_outputs."""
    if not context.prior_outputs:
        return "No prior outputs recorded."

    parts: list[str] = []
    for step_name, result in context.prior_outputs.items():
        status = "PASS" if result.success else "FAIL"
        line = f"- {step_name}: {status}"
        if result.verdict:
            line += f" (verdict: {result.verdict})"
        parts.append(line)

    return "\n".join(parts)


def _read_or_create(path: Path) -> list[str]:
    """Read existing DEVLOG.md or create a minimal one."""
    if path.exists():
        return path.read_text().splitlines()

    path.parent.mkdir(parents=True, exist_ok=True)
    minimal = [
        "---",
        "docType: devlog",
        "---",
        "",
        "# Development Log",
        "",
        "---",
        "",
    ]
    path.write_text("\n".join(minimal))
    return minimal


def _insert_entry(lines: list[str], today_header: str, entry: str) -> list[str]:
    """Insert entry under today's date header, creating it if needed."""
    result = list(lines)
    entry_lines = ["", *entry.splitlines(), ""]

    # Find existing today header
    for i, line in enumerate(result):
        if line.strip() == today_header:
            # Insert after the header (skip blank line after header if present)
            insert_at = i + 1
            if insert_at < len(result) and not result[insert_at].strip():
                insert_at += 1
            result[insert_at:insert_at] = entry_lines
            return result

    # No today header — find first date header or separator after frontmatter
    insert_at = _find_content_start(result)
    result[insert_at:insert_at] = [today_header, "", *entry.splitlines(), ""]
    return result


def _find_content_start(lines: list[str]) -> int:
    """Find the index where new date entries should be inserted.

    Skips past frontmatter, the title line, description, and the
    separator that follows.
    """
    in_frontmatter = False
    past_frontmatter = False
    separator_count = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == "---" and not past_frontmatter:
            separator_count += 1
            if separator_count == 2:
                past_frontmatter = True
                in_frontmatter = False
            elif separator_count == 1:
                in_frontmatter = True
            continue

        if in_frontmatter:
            continue

        if past_frontmatter:
            # Look for the content separator (--- after title/description)
            if stripped == "---":
                # Return position after this separator + blank line
                next_i = i + 1
                while next_i < len(lines) and not lines[next_i].strip():
                    next_i += 1
                return next_i

            # Look for first date header
            if _DATE_HEADER_RE.match(stripped):
                return i

    return len(lines)


register_action(ActionType.DEVLOG, DevlogAction())
