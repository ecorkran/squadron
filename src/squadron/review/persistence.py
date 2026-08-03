"""Review file persistence — formatting and saving review output files.

Shared between CLI review commands and pipeline review actions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Protocol, TypedDict

from squadron.review.git_utils import run_git
from squadron.review.models import ReviewResult

_logger = logging.getLogger(__name__)

_REVIEWS_DIR = Path("project-documents/user/reviews")

#: Where a review's prior content is preserved before an overwrite, relative
#: to the reviews directory. Defined once — the guard, its tests, and anything
#: that later reads archived reviews all reference this.
_ARCHIVE_SUBDIR = "archive"

#: Directory prefix for task-breakdown files, relative to project root.
#: SliceInfo["task_files"] entries are bare filenames — join with this to
#: get the full relative path (mirrors _REVIEWS_DIR's role for reviews).
TASKS_DIR = Path("project-documents/user/tasks")


class SliceInfo(TypedDict):
    """Resolved slice metadata from Context-Forge."""

    index: int
    name: str
    slice_name: str
    design_file: str | None
    task_files: list[str]
    arch_file: str
    project: str


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
        project=project.name,
    )


def yaml_escape(text: str) -> str:
    """Escape backslashes and double quotes for YAML double-quoted values."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def resolve_reviewed_sha(cwd: str) -> str | None:
    """HEAD at review-authoring time, or ``None`` when git cannot answer.

    The stamp anchors ``sq review resolve``'s "what changed since the review"
    diff (slice 306 Part A). Both persistence paths — CLI and pipeline action —
    resolve it the same way, so a review carries the same anchor regardless of
    which one authored it.

    ``None`` is returned, and a WARNING logged, when git is absent, the
    directory is not a repository, or HEAD does not resolve (an empty repo with
    no commits). The caller omits the key entirely rather than writing a
    placeholder: a fabricated SHA would send the resolve path diffing against
    a commit that does not exist.
    """
    completed = run_git(["rev-parse", "HEAD"], cwd=cwd)
    if completed is None:
        _logger.warning("review: git could not be invoked in %s; reviewedSha will not be stamped", cwd)
        return None
    if completed.returncode != 0:
        _logger.warning(
            "review: `git rev-parse HEAD` failed in %s (%s); reviewedSha will not be stamped",
            cwd,
            completed.stderr.strip() or f"exit {completed.returncode}",
        )
        return None

    sha = completed.stdout.strip()
    if not sha:
        _logger.warning(
            "review: `git rev-parse HEAD` returned no SHA in %s; reviewedSha will not be stamped",
            cwd,
        )
        return None
    return sha


def format_review_markdown(
    result: ReviewResult,
    review_type: str,
    slice_info: SliceInfo | None = None,
    source_document: str | None = None,
    model: str | None = None,
    verdict_override: str | None = None,
    revision_number: int | None = None,
    reviewed_sha: str | None = None,
) -> str:
    """Format a ReviewResult as markdown with YAML frontmatter.

    Args:
        result: The review result to format.
        review_type: Review type label (e.g. ``"slice"``, ``"code"``).
        slice_info: Optional slice metadata for frontmatter fields.
        source_document: Explicit source document path; falls back to
            ``slice_info["design_file"]`` when not provided.
        model: Explicit model name; falls back to ``result.model``.
        verdict_override: Explicit verdict string; falls back to
            ``result.verdict.value``. Judge templates deliberately omit a
            verdict line from their raw output (the score is the source of
            truth), so ``result.verdict`` is always ``UNKNOWN`` for them —
            callers that have already derived a threshold-based verdict
            (``enforce_judge``) pass it here so the persisted file shows the
            real gating decision instead of the always-empty raw parse.
        revision_number: Squadron's loop-iteration revision count (slice 911
            Part B). Emitted only when supplied — a review authored outside
            a loop, or via the CLI, carries no such key.
        reviewed_sha: HEAD at the moment the review was authored (slice 306
            Part A) — the anchor ``sq review resolve`` diffs against to ask
            what changed since. Emitted only when supplied: a review authored
            where git was unavailable carries no key rather than a fabricated
            placeholder, and the resolve path falls back to file history.
    """
    today = result.timestamp.strftime("%Y%m%d")
    resolved_model = model or result.model or "unknown"
    resolved_verdict = verdict_override or result.verdict.value

    # Source document resolution
    if source_document is None and slice_info is not None:
        source_document = slice_info.get("design_file") or ""
    source_doc = source_document or ""

    # Slice-derived fields
    slice_name = slice_info["slice_name"] if slice_info else "unknown"
    slice_index = slice_info["index"] if slice_info else 0
    project_name = slice_info["project"] if slice_info else "unknown"

    lines = [
        "---",
        "docType: review",
        "layer: project",
        f"reviewType: {review_type}",
        f"slice: {slice_name}",
        f"project: {project_name}",
        f"verdict: {resolved_verdict}",
        f"sourceDocument: {source_doc}",
        f"aiModel: {resolved_model}",
        "status: complete",
        f"dateCreated: {today}",
        f"dateUpdated: {today}",
    ]
    if reviewed_sha is not None:
        lines.append(f"reviewedSha: {reviewed_sha}")
    if revision_number is not None:
        lines.append(f"revision_number: {revision_number}")

    # Numeric scoring foundation (slice 300): emit score/criteria as top-level
    # frontmatter only when present. A score-less result is byte-for-byte
    # unchanged. provenance is never emitted here (reserved — slice 301).
    if result.score is not None:
        lines.append(f"score: {result.score}")
    if result.criteria is not None:
        lines.append("criteria:")
        for name, value in result.criteria.items():
            lines.append(f"  {name}: {value}")

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
    lines.append(f"**Verdict:** {resolved_verdict}")
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


def archive_existing_review(path: Path) -> bool:
    """Preserve an existing review's content before it is overwritten.

    Re-running a review over a file someone hand-edited used to destroy that
    content silently (slice 306 Part D). The prior bytes are copied to
    ``<reviews>/archive/`` under the original filename — both Context Forge's
    artifact scanning and squadron's own metrology globs enumerate the reviews
    directory non-recursively and skip entries that are not ``.md`` files, so
    an ``archive/`` subdirectory is invisible to them and needs no name
    mangling.

    Returns ``True`` when the caller may write: either nothing was there, or a
    verified copy now exists. Returns ``False`` when the copy could not be
    made *or could not be verified* — the caller must then abort, because a
    guard that proceeds after a failed copy destroys exactly the content it
    exists to protect (design review F003).
    """
    if not path.exists():
        return True

    archived = path.parent / _ARCHIVE_SUBDIR / path.name
    try:
        original = path.read_bytes()
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes(original)
        read_back = archived.read_bytes()
    except OSError:
        _logger.exception(
            "review: could not archive %s to %s; refusing to overwrite it", path, archived
        )
        return False

    if read_back != original:
        _logger.error(
            "review: archived copy of %s at %s does not match the original "
            "(%d bytes read back, %d expected); refusing to overwrite it",
            path,
            archived,
            len(read_back),
            len(original),
        )
        return False

    _logger.warning("review: overwriting %s; prior content archived to %s", path, archived)
    return True


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
        The path of the saved file, or ``None`` on write failure — which now
        includes an existing file whose content could not be archived first
        (see :func:`archive_existing_review`).
    """
    base_dir = Path(cwd) if cwd else Path(".")
    target = base_dir / _REVIEWS_DIR
    ext = "json" if as_json else "md"
    filename = f"{slice_index}-review.{review_type}.{slice_name}.{ext}"
    path = target / filename

    if not archive_existing_review(path):
        return None

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
    verdict_override: str | None = None,
    revision_number: int | None = None,
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

    ``verdict_override`` is forwarded to ``format_review_markdown`` for
    markdown output and to ``ReviewResult.to_dict()`` for ``as_json``
    output — see their docstrings. Both persist the same threshold-derived
    verdict for judge templates rather than the always-``UNKNOWN`` raw
    parse.

    ``revision_number`` is forwarded to ``format_review_markdown`` for
    markdown output only (slice 911 Part B); ``as_json`` output carries no
    equivalent field. The CLI never passes this — only a loop-iteration
    review action does.

    Raises:
        OSError: If a file already exists at the target path and its content
            could not be archived (see :func:`archive_existing_review`). The
            existing file is left untouched — losing a review to a silent
            overwrite is the failure this refuses to allow.
    """
    target = reviews_dir or _REVIEWS_DIR
    target.mkdir(parents=True, exist_ok=True)

    base = f"{slice_info['index']}-review.{review_type}.{slice_info['slice_name']}"
    if name_suffix:
        base = f"{base}.{name_suffix}"

    if as_json:
        path = target / f"{base}.json"
        content = json.dumps(result.to_dict(verdict_override=verdict_override), indent=2)
    else:
        path = target / f"{base}.md"
        # The reviews directory is resolved relative to the process working
        # directory, so HEAD is resolved against the same root.
        content = format_review_markdown(
            result,
            review_type,
            slice_info,
            source_document=input_file,
            verdict_override=verdict_override,
            revision_number=revision_number,
            reviewed_sha=resolve_reviewed_sha("."),
        )

    if not archive_existing_review(path):
        raise OSError(
            f"refusing to overwrite {path}: its prior content could not be archived to "
            f"{path.parent / _ARCHIVE_SUBDIR / path.name}"
        )
    path.write_text(content)

    return path
