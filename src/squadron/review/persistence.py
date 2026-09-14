"""Review file persistence — formatting and saving review output files.

Shared between CLI review commands and pipeline review actions.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypedDict

from squadron.documents.schema import DocType, DocumentStatus
from squadron.providers.errors import ProviderError
from squadron.review.git_utils import run_git
from squadron.review.models import ReviewResult, Verdict, VerdictSource

_logger = logging.getLogger(__name__)

#: Where review artifacts live, relative to the project root. Public so the
#: resolve path (slice 306) locates reviews through the same constant that
#: writes them rather than repeating the literal.
REVIEWS_DIR = Path("project-documents/user/reviews")

#: Where a review's prior content is preserved before an overwrite, relative
#: to the reviews directory. Defined once — the guard, its tests, and anything
#: that later reads archived reviews all reference this.
_ARCHIVE_SUBDIR = "archive"

#: Directory prefix for task-breakdown files, relative to project root.
#: SliceInfo["task_files"] entries are bare filenames — join with this to
#: get the full relative path (mirrors REVIEWS_DIR's role for reviews).
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


def _findings_not_parsed_section(reason: str) -> list[str]:
    """Body lines for a degraded review, differing only in why it degraded.

    Both degraded paths — a verdict without findings, and neither — must say the same
    two things: this is not a clean review, and the model's own words are below. Only
    the cause differs, so only the cause is a parameter.
    """
    return [
        "## Findings Not Parsed",
        "",
        f"**This review is degraded.** {reason}",
        "",
        "**The model's actual response is not lost:** read the `### Raw Response` "
        "section below, which this artifact always carries when a review is degraded. "
        "Do not read this review as clean.",
        "",
    ]


_NOT_COMPUTED = "not computed"
_NOT_OFFERED = "not offered"


def _run_digest_lines(result: ReviewResult) -> list[str]:
    """A small always-on record of what the parse actually saw.

    ``### Raw Response`` is emitted only when a review degrades, so the
    artifacts least likely to be questioned — a confident PASS — were the
    least auditable on disk. #91 and #92 were diagnosable only because those
    particular runs happened to degrade, and the 8-vs-35 finding discrepancy
    that started #91 is invisible in either artifact (#93).

    The counts come from the parser via ``ReviewResult``; this renders them
    and never re-parses. A second parse here would drift from the first and
    report on a document nobody acted on. This is a body section, not
    frontmatter: frontmatter is a consumed contract that ``cf`` scans and the
    verdict gate now checks, and diagnostic keys there invite coupling.
    """
    scan = result.finding_scan
    if result.tools_given is None:
        tool_calls = _NOT_OFFERED
    else:
        # `is None`, never `or 0`: a genuine zero is a real answer here ("offered tools,
        # called none" — the case slice 265 D5 exists to make visible) and must not render
        # as the not-reported sentinel.
        tool_calls = _render_optional(result.tool_calls_made)

    # Newline-free detection (slice 918 D10a). Computed here from raw_output rather than
    # carried on a field: the text is already in hand at render time, so a field and its
    # plumbing would buy nothing.
    #
    # This does NOT fix issue #96 (the parser's handling of such a response) — it is out of
    # scope. What it buys is that the artifact says *which* of the three known shapes
    # occurred, which the response length alone cannot distinguish:
    #   - never-emitted output (#92): length 0, and a stop reason explaining why;
    #   - all-tools-failed (kimi27): non-zero length, made == failed > 0;
    #   - emitted-but-unparseable (#96): non-zero length, tools fine, no line breaks.
    #
    # For whoever fixes #96: the leniency that makes a newline-free response parse must not
    # reopen issue #91. Slice 917 Part F's fence masking and section bounding both assume
    # line structure, so they need reviewing in the same change, not after it.
    newline_free = bool(result.raw_output) and "\n" not in result.raw_output

    lines = [
        "### Run Digest",
        "",
        f"- Response length: {len(result.raw_output)} chars",
        f"- Response is newline-free: {'yes' if newline_free else 'no'}",
        f"- Tool calls made: {tool_calls}",
        f"- Tool calls failed: {_render_optional(result.failed_tool_calls)}",
        f"- Stop reason: {_render_optional(result.stop_reason)}",
        f"- Reasoning characters: {_render_optional(result.reasoning_chars)}",
        f"- `## Summary` located: {_render_tristate(result.summary_section_located)}",
        f"- `## Findings` located: {_render_tristate(result.findings_section_located)}",
        f"- Finding-shaped matches — whole response: {scan.total if scan else _NOT_COMPUTED}",
        f"- Finding-shaped matches — inside fences: {scan.in_fences if scan else _NOT_COMPUTED}",
        f"- Finding-shaped matches — in findings section: {scan.in_section if scan else _NOT_COMPUTED}",
        f"- Finding-shaped matches — surviving validation: {scan.surviving if scan else _NOT_COMPUTED}",
    ]
    # Slice 919 Part 1 (#96), design D4: emitted only when normalization
    # actually ran, never an always-present "count: 0" line. A response that
    # took the unmodified path (D5) must render byte-identical to before this
    # slice — the clean_pass_artifact.md snapshot guard depends on it, since
    # it never triggers normalization.
    if result.normalized_break_count > 0:
        lines.append(
            f"- Response line structure was normalized before parsing "
            f"({result.normalized_break_count} break(s) inserted; see #96)"
        )
    lines.append("")
    return lines


def _render_tristate(value: bool | None) -> str:
    """``None`` means the parser did not produce this fact, not ``false``."""
    if value is None:
        return _NOT_COMPUTED
    return "yes" if value else "no"


def _render_optional(value: object | None) -> str:
    """Render a not-reported value as the sentinel, and every reported value as itself.

    The distinction the ``x or 0`` idiom destroys: ``0`` and ``None`` are different
    answers. Zero failed tool calls is a fact about a healthy run; ``None`` means no
    provider stamped the fact at all (the SDK path, design D12). Collapsing them makes
    an instrumented run indistinguishable from an uninstrumented one, which is the
    distinction slice 918 exists to provide.
    """
    if value is None:
        return _NOT_COMPUTED
    return str(value)


def _review_frontmatter_lines(
    *,
    review_type: str,
    slice_name: str,
    project_name: str,
    verdict: str,
    verdict_source: VerdictSource | None,
    source_doc: str,
    model: str,
    today: str,
    reviewed_sha: str | None,
    revision_number: int | None,
    tools_given: list[str] | None,
    tool_calls_made: int | None,
    tools_suppressed_reason: str | None,
) -> list[str]:
    """The frontmatter block every review artifact opens with.

    Takes resolved values rather than a ``ReviewResult`` so a provider failure
    — which has no result to render — emits the same keys through the same
    code rather than a second, drifting copy.

    Optional keys are emitted only when supplied, which is what keeps an
    artifact byte-for-byte unchanged when a feature does not apply:
    ``reviewedSha`` (slice 306), ``revision_number`` (slice 911), the tool
    telemetry pair (slice 265 D5 — an absent ``toolsGiven`` means "never
    offered", while ``toolCallsMade: 0`` means "offered, used none"),
    ``toolsSuppressedReason`` (slice 266, present only when a declared set was
    emptied), and ``verdictSource`` (slice 919 Part 2, #97 — absent for the
    nothing-parsed branch, D8, where there is no verdict to attribute
    provenance to).
    """
    lines = [
        "---",
        f"docType: {DocType.REVIEW}",
        "layer: project",
        f"reviewType: {review_type}",
        f"slice: {slice_name}",
        f"project: {project_name}",
        f"verdict: {verdict}",
    ]
    if verdict_source is not None:
        lines.append(f"verdictSource: {verdict_source.value}")
    lines.extend(
        [
            f"sourceDocument: {source_doc}",
            f"aiModel: {model}",
            f"status: {DocumentStatus.COMPLETE}",
            f"dateCreated: {today}",
            f"dateUpdated: {today}",
        ]
    )
    if reviewed_sha is not None:
        lines.append(f"reviewedSha: {reviewed_sha}")
    if revision_number is not None:
        lines.append(f"revision_number: {revision_number}")
    if tools_given is not None:
        lines.append(f"toolsGiven: [{', '.join(tools_given)}]")
        # `is None` rather than `or 0`, matching the digest: this branch is only reached
        # when tools *were* given, so a zero here is the real "offered but unused" count.
        lines.append(f"toolCallsMade: {0 if tool_calls_made is None else tool_calls_made}")
    if tools_suppressed_reason is not None:
        lines.append(f"toolsSuppressedReason: {tools_suppressed_reason}")
    return lines


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
    # Keyed on the *resolved* verdict deliberately (design D3): a judge template's raw
    # parse is always UNKNOWN because its verdict is score-derived and arrives as an
    # override, so keying on result.verdict would embed every judge's raw response.
    degraded = resolved_verdict == Verdict.UNKNOWN.value or result.fallback_used

    # Source document resolution
    if source_document is None and slice_info is not None:
        source_document = slice_info.get("design_file") or ""
    source_doc = source_document or ""

    # Slice-derived fields
    slice_name = slice_info["slice_name"] if slice_info else "unknown"
    slice_index = slice_info["index"] if slice_info else 0
    project_name = slice_info["project"] if slice_info else "unknown"

    lines = _review_frontmatter_lines(
        review_type=review_type,
        slice_name=slice_name,
        project_name=project_name,
        verdict=resolved_verdict,
        # A judge template's verdict_override is a threshold-based verdict computed by the
        # caller (enforce_judge), never something parse_review_output derived — result.verdict
        # stays UNKNOWN and result.verdict_source stays None in that case, which is the
        # honest answer: squadron's parser never determined provenance for it. Part 2 records
        # provenance for what the parser resolved, not for a caller's own override.
        verdict_source=result.verdict_source,
        source_doc=source_doc,
        model=resolved_model,
        today=today,
        reviewed_sha=reviewed_sha,
        revision_number=revision_number,
        tools_given=result.tools_given,
        tool_calls_made=result.tool_calls_made,
        tools_suppressed_reason=result.tools_suppressed_reason,
    )

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
                # location and summary are the only fields in this hand-built
                # block carrying model-authored free text; both must be quoted.
                lines.append(f'    location: "{yaml_escape(sf.location)}"')

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
    elif result.fallback_used:
        # A degraded parse must never render as a clean review. The findings exist in
        # the model's output; squadron could not parse them into the required
        # '### [SEVERITY] Title' form, and saying "No specific findings." here asserts
        # the opposite of what happened (issue #72).
        lines.extend(
            _findings_not_parsed_section(
                f"A verdict of {resolved_verdict} was parsed, but no findings could be "
                "extracted from the model's response — most often because it did not "
                "follow the required `### [SEVERITY] Title` format. Findings are left "
                "empty rather than fabricated from unstructured text."
            )
        )
    elif degraded:
        # An UNKNOWN verdict with nothing parsed used to fall through to "No specific
        # findings." — the same false claim of cleanliness issue #72 fixed for the
        # fallback case, reached by the other door (#61).
        lines.extend(
            _findings_not_parsed_section(
                "No verdict and no findings could be extracted from the model's "
                "response, so the verdict is left UNKNOWN rather than assumed."
            )
        )
    else:
        lines.append("No specific findings.")
        lines.append("")

    lines.extend(_run_digest_lines(result))

    # A degraded review's raw response is evidence, not verbosity-gated output (design
    # D3): the artifact is often the only surviving record of what the model said. The
    # -vv appendix below renders it too, so it is emitted here only when that appendix
    # is absent — one copy either way.
    if degraded and result.system_prompt is None:
        lines.append("### Raw Response")
        lines.append("")
        lines.append(result.raw_output)
        lines.append("")

    # Debug appendix — included when prompt capture fields are populated
    if result.system_prompt is not None:
        lines.append("---")
        lines.append("")
        lines.append("## Debug: Prompt & Response")
        lines.append("")
        lines.append("### System Prompt")
        lines.append("")
        if result.default_system_prompt_preset_used:
            # The CLI's preset text is not squadron's to capture, so say what the
            # recorded text actually is rather than letting it read as the whole prompt.
            lines.append(
                "_Sent with the Claude Code `claude_code` system-prompt preset; the text "
                "below is the appended part._"
            )
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
        # The stable slot holds the most recent prior copy. It is also
        # single-slot: before overwriting it, its current occupant is moved
        # aside under a timestamped name, so a run of bad reviews cannot
        # walk a good review out of existence one overwrite at a time
        # (issue #73). Retention is unbounded by design — these are small
        # text files and losing one is the failure being prevented.
        if archived.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            generation = archived.with_name(f"{archived.stem}.{stamp}{archived.suffix}")
            if not generation.exists():
                generation.write_bytes(archived.read_bytes())
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
    target = base_dir / REVIEWS_DIR
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
    target = reviews_dir or REVIEWS_DIR
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


def format_provider_failure_markdown(
    exc: ProviderError,
    review_type: str,
    slice_info: SliceInfo | None,
    *,
    model: str | None = None,
    source_document: str | None = None,
    tools_given: list[str] | None = None,
    reviewed_sha: str | None = None,
) -> str:
    """Render an artifact recording that the provider failed to deliver a review.

    A provider failure used to leave nothing on disk: the CLI printed an error
    and exited, the pipeline logged and returned ``success=False``. For a
    pipeline run the artifact is the whole durable record, so the evidence the
    provider collected — why the model stopped, how much of its budget went to
    reasoning, whether it touched its tools — was discarded one layer above
    where it was gathered (#84).

    The artifact says the provider failed. It does not say the review found
    nothing: an empty findings list is a claim about the code, and this run
    made no such claim. ``verdict: UNKNOWN`` is a real ``Verdict`` member, so
    the commit gate accepts it and existing pipeline gates treat it fail-closed.
    The distinguishing marker is the ``## Provider Failure`` body section.
    """
    today = datetime.now(tz=UTC).strftime("%Y%m%d")
    slice_name = slice_info["slice_name"] if slice_info else "unknown"
    slice_index = slice_info["index"] if slice_info else 0
    project_name = slice_info["project"] if slice_info else "unknown"
    source_doc = source_document or (slice_info.get("design_file") or "" if slice_info else "")

    lines = _review_frontmatter_lines(
        review_type=review_type,
        slice_name=slice_name,
        project_name=project_name,
        verdict=Verdict.UNKNOWN.value,
        # Omitted: a provider failure has no verdict to attribute provenance to (there is
        # no ReviewResult here at all, let alone one the parser resolved a verdict from).
        verdict_source=None,
        source_doc=source_doc,
        model=model or "unknown",
        today=today,
        reviewed_sha=reviewed_sha,
        revision_number=None,
        tools_given=tools_given,
        tool_calls_made=exc.tool_calls_made,
        tools_suppressed_reason=None,
    )
    lines.append("---")
    lines.append("")

    # No "— slice 0" for a run with no slice: a fabricated index reads as real.
    title = (
        f"# Review: {review_type} — slice {slice_index}" if slice_info else f"# Review: {review_type}"
    )
    lines.append(title)
    lines.append("")
    lines.append(f"**Verdict:** {Verdict.UNKNOWN.value}")
    lines.append(f"**Model:** {model or 'unknown'}")
    lines.append("")
    lines.append("## Provider Failure")
    lines.append("")
    lines.append(
        "The provider raised before delivering a response, so no review was "
        "produced. This artifact records the failure; it is not a review "
        "finding nothing."
    )
    lines.append("")
    lines.append("```")
    lines.append(str(exc))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def save_provider_failure(
    exc: ProviderError,
    review_type: str,
    slice_info: SliceInfo | None,
    *,
    model: str | None = None,
    source_document: str | None = None,
    tools_given: list[str] | None = None,
    reviewed_sha: str | None = None,
    cwd: str | None = None,
    slice_name: str | None = None,
    slice_index: int | None = None,
    name_suffix: str | None = None,
) -> Path | None:
    """Write a provider-failure artifact into the review's own slot.

    The live slot deliberately receives the failure rather than keeping the
    previous run's artifact. A stale PASS left in place is read by the next
    pipeline gate as this run's verdict and waves the step through, which is
    the silent pass-through the review gates exist to prevent. The prior
    content is preserved by ``archive_existing_review`` on the way.

    ``slice_name`` and ``slice_index`` name the file when there is no
    ``slice_info`` — the pipeline's step name and index, matching how the
    success path names a slice-less review.

    ``name_suffix`` matches ``save_review_result``'s: a split tasks review
    writes each part to its own ``.part-N`` slot, so a failure in one part must
    land in that part's slot rather than a slot no success path ever writes —
    where consecutive part failures would also overwrite each other.

    Returns the saved path, or ``None`` when the write failed (already logged).
    """
    content = format_provider_failure_markdown(
        exc,
        review_type,
        slice_info,
        model=model,
        source_document=source_document,
        tools_given=tools_given,
        reviewed_sha=reviewed_sha,
    )
    resolved_name = slice_info["slice_name"] if slice_info else slice_name
    if resolved_name is not None and name_suffix:
        resolved_name = f"{resolved_name}.{name_suffix}"
    resolved_index = slice_info["index"] if slice_info else slice_index
    if resolved_name is None or resolved_index is None:
        _logger.warning(
            "Cannot save provider-failure artifact for %s review: no slice info "
            "and no fallback name/index supplied.",
            review_type,
        )
        return None
    return save_review_file(content, review_type, resolved_name, resolved_index, cwd=cwd)
