"""Review file persistence — formatting and saving review output files.

Shared between CLI review commands and pipeline review actions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol, TypedDict

from squadron.review.models import ReviewResult

_logger = logging.getLogger(__name__)

_REVIEWS_DIR = Path("project-documents/user/reviews")


class SliceInfo(TypedDict):
    """Resolved slice metadata from Context-Forge."""

    index: int
    name: str
    slice_name: str
    design_file: str | None
    task_files: list[str]
    arch_file: str


class CfClientProtocol(Protocol):
    """Minimal duck-type protocol for CF client used by resolve_slice_info."""

    def list_slices(self) -> list[Any]: ...
    def list_tasks(self) -> list[Any]: ...
    def get_project(self) -> Any: ...


def resolve_slice_info(cf_client: CfClientProtocol, index: int) -> SliceInfo:
    """Resolve a slice number to file paths via Context-Forge.

    Shared between CLI review commands and pipeline review actions.
    The ``cf_client`` is duck-typed — must have ``list_slices()``,
    ``list_tasks()``, and ``get_project()`` methods.

    Raises:
        ValueError: If the slice index is not found.
    """
    # Duck-typed: cf_client must have list_slices(), list_tasks(), get_project()
    slices = cf_client.list_slices()  # type: ignore[union-attr]
    match = next((s for s in slices if s.index == index), None)
    if match is None:
        raise ValueError(f"No slice with index {index} in the current slice plan")

    design_file = match.design_file
    if design_file:
        stem = Path(design_file).stem
        slice_name = stem.split(".", 1)[1] if "." in stem else stem
    else:
        slice_name = match.name.lower().replace(" ", "-")

    tasks = cf_client.list_tasks()  # type: ignore[union-attr]
    task_match = next((t for t in tasks if t.index == index), None)
    task_files: list[str] = list(task_match.files) if task_match else []

    project = cf_client.get_project()  # type: ignore[union-attr]
    arch_file = project.arch_file

    return SliceInfo(
        index=index,
        name=match.name,
        slice_name=slice_name,
        design_file=design_file,
        task_files=task_files,
        arch_file=arch_file,
    )


def yaml_escape(text: str) -> str:
    """Escape backslashes and double quotes for YAML double-quoted values."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def format_review_markdown(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo | None = None,
    source_document: str | None = None,
    model: str | None = None,
) -> str:
    """Format a ReviewResult as markdown with YAML frontmatter.

    Args:
        result: The review result to format.
        review_type: Review type label (e.g. ``"slice"``, ``"code"``).
        slice_info: Optional slice metadata for frontmatter fields.
        source_document: Explicit source document path; falls back to
            ``slice_info["design_file"]`` when not provided.
        model: Explicit model name; falls back to ``result.model``.
    """
    today = result.timestamp.strftime("%Y%m%d")
    resolved_model = model or result.model or "unknown"

    # Source document resolution
    if source_document is None and slice_info is not None:
        source_document = slice_info.get("design_file") or ""
    source_doc = source_document or ""

    # Slice-derived fields
    slice_name = slice_info["slice_name"] if slice_info else "unknown"
    slice_index = slice_info["index"] if slice_info else 0

    lines = [
        "---",
        "docType: review",
        "layer: project",
        f"reviewType: {review_type}",
        f"slice: {slice_name}",
        "project: squadron",
        f"verdict: {result.verdict.value}",
        f"sourceDocument: {source_doc}",
        f"aiModel: {resolved_model}",
        "status: complete",
        f"dateCreated: {today}",
        f"dateUpdated: {today}",
    ]

    if result.findings:
        lines.append("findings:")
        for sf in result.structured_findings:
            lines.append(f"  - id: {sf.id}")
            lines.append(f"    severity: {sf.severity}")
            lines.append(f"    category: {sf.category}")
            lines.append(f'    summary: "{yaml_escape(sf.summary)}"')
            if sf.location:
                lines.append(f"    location: {sf.location}")

    lines.append("---")
    lines.append("")
    lines.append(f"# Review: {review_type} — slice {slice_index}")
    lines.append("")
    lines.append(f"**Verdict:** {result.verdict.value}")
    lines.append(f"**Model:** {resolved_model}")
    lines.append("")

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

    # Debug appendix — included when prompt capture fields are populated
    if result.system_prompt is not None:
        lines.append("---")
        lines.append("")
        lines.append("## Debug: Prompt & Response")
        lines.append("")
        lines.append("### System Prompt")
        lines.append("")
        lines.append(result.system_prompt)
        lines.append("")
        lines.append("### User Prompt")
        lines.append("")
        lines.append(result.user_prompt or "")
        lines.append("")
        lines.append("### Rules Injected")
        lines.append("")
        lines.append(result.rules_content_used or "None")
        lines.append("")
        lines.append("### Raw Response")
        lines.append("")
        lines.append(result.raw_output)
        lines.append("")

    return "\n".join(lines)


def save_review_file(
    content: str,
    review_type: str,
    slice_name: str,
    slice_index: int,
    cwd: str | None = None,
    as_json: bool = False,
) -> Path | None:
    """Write review content to the reviews directory.

    Args:
        content: Pre-formatted review content (markdown or JSON string).
        review_type: Review type label (e.g. ``"slice"``, ``"code"``).
        slice_name: Kebab-case slice name for the filename.
        slice_index: Numeric slice index for the filename prefix.
        cwd: Working directory root; reviews dir is relative to this.
        as_json: If True, use ``.json`` extension instead of ``.md``.

    Returns:
        The path of the saved file, or ``None`` on write failure.
    """
    base_dir = Path(cwd) if cwd else Path(".")
    target = base_dir / _REVIEWS_DIR
    ext = "json" if as_json else "md"
    filename = f"{slice_index}-review.{review_type}.{slice_name}.{ext}"
    path = target / filename

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    except OSError:
        _logger.warning("Failed to save review file: %s", path)
        return None

    return path


def save_review_result(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo,
    as_json: bool = False,
    reviews_dir: Path | None = None,
    input_file: str | None = None,
    name_suffix: str | None = None,
) -> Path:
    """Save a ReviewResult to the reviews directory (CLI compatibility).

    This preserves the interface used by ``cli/commands/review.py``.
    Returns the path of the saved file.

    ``name_suffix`` is an optional dotted segment appended to the
    file's base name before the extension, used when a single slice
    produces multiple review outputs (e.g. split task files
    ``-1.md`` / ``-2.md`` each get their own review). For example,
    passing ``name_suffix="part-1"`` yields
    ``161-review.tasks.summary-step.part-1.md``.
    """
    target = reviews_dir or _REVIEWS_DIR
    target.mkdir(parents=True, exist_ok=True)

    base = f"{slice_info['index']}-review.{review_type}.{slice_info['slice_name']}"
    if name_suffix:
        base = f"{base}.{name_suffix}"

    if as_json:
        path = target / f"{base}.json"
        path.write_text(json.dumps(result.to_dict(), indent=2))
    else:
        path = target / f"{base}.md"
        path.write_text(
            format_review_markdown(
                result, review_type, slice_info, source_document=input_file
            )
        )

    return path
