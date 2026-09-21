"""Prompt builder for the code review template."""

from __future__ import annotations

import re

# The block's own heading. Neutralized inside pr_metadata content (see _pr_block) so a
# malicious or coincidental occurrence of this exact text in a PR body cannot be mistaken
# for the real section boundary by a model reading the rendered prompt.
_PR_BLOCK_LABEL = "### Pull Request"

# Zero-width space (U+200B) — invisible in rendered text, breaks an exact substring match
# without altering what a human or model reads.
_ZERO_WIDTH_SPACE = "\u200b"

_BACKTICK_RUN_RE = re.compile(r"`+")


def _fence_for(content: str) -> str:
    """A backtick fence guaranteed longer than any run of backticks in *content*.

    A fixed-length fence is not containment: content carrying a run of backticks at least
    as long as the fence can prematurely close it. The fence is one backtick longer than
    the longest run found, minimum three (this is the same defect class fixed in 381's
    review-parser closer-length bug).
    """
    longest = max((len(m.group()) for m in _BACKTICK_RUN_RE.finditer(content)), default=0)
    return "`" * max(longest + 1, 3)


def _neutralize_label(content: str, label: str) -> str:
    """Break any verbatim occurrence of *label* inside *content* without changing its text.

    Inserts a zero-width space after the label's first character wherever it appears, so
    the visible text is unchanged but an exact string match against the real block label
    no longer succeeds.
    """
    if label not in content:
        return content
    broken = label[0] + _ZERO_WIDTH_SPACE + label[1:]
    return content.replace(label, broken)


def _pr_block(pr_metadata: str, max_bytes: int) -> str:
    """Render pull-request metadata as a contained, labeled, size-capped fenced block.

    slice 382, design D4. *pr_metadata* is already-assembled text (title, body, linked
    issue numbers, unresolved discussions) — this function only fences, labels, and
    truncates it; it does not read config or touch disk (see Task D.3's Corrections note:
    the caller resolves ``max_bytes`` once and threads it through ``inputs``, matching the
    existing ``diff_exclude_patterns`` precedent, so this stays a pure, config-free
    module).
    """
    # Deferred import: review_client is not imported at module load, only when a PR block
    # is actually being rendered — review_client never imports builders/code.py itself (it
    # is loaded at runtime via the dotted path code.yaml names), so this is a new,
    # one-directional edge, not a cycle.
    from squadron.review.review_client import _truncate  # pyright: ignore[reportPrivateUsage]

    truncated = _truncate(pr_metadata, "pr", max_bytes)
    neutralized = _neutralize_label(truncated, _PR_BLOCK_LABEL)
    fence = _fence_for(neutralized)
    return f"{_PR_BLOCK_LABEL}\n\n{fence}\n{neutralized}\n{fence}"


def code_review_prompt(inputs: dict[str, str]) -> str:
    """Build the code review prompt with conditional sections.

    Handles three scoping modes:
    - ``diff`` present: review changed files relative to a git ref
    - ``files`` present: review files matching a glob pattern
    - neither: agent surveys project structure
    """
    cwd = inputs.get("cwd", ".")
    diff = inputs.get("diff")
    files = inputs.get("files")

    # Substituted content is delimited with descriptive tags (#25) so the
    # model can tell the instructions from the material they are about.
    sections: list[str] = [
        f"Review code in the project at: {cwd}",
        "",
        "<scope>",
    ]

    if diff:
        exclude_patterns = inputs.get("diff_exclude_patterns")
        if exclude_patterns:
            pathspecs = " ".join(f"':!{p}'" for p in exclude_patterns.split(","))
            sections.append(
                f"Run `git diff {diff} -- . {pathspecs}` to identify changed "
                "source files, then review those files for quality and correctness."
            )
        else:
            sections.append(
                f"Run `git diff {diff}` to identify changed files, "
                "then review those files for quality and correctness."
            )
        sections.append(
            "Treat the diff as partial evidence, not a complete snapshot of the file. "
            "Do not make confident claims about code outside the shown hunk unless you "
            "inspect the underlying file or other supporting evidence first."
        )
    if files:
        sections.append(f"Focus your review on files matching the pattern: {files}")
    if not diff and not files:
        sections.append(
            "Survey the project structure using Glob and Grep to identify "
            "the most important areas to review. Focus on recently modified "
            "or core source files."
        )

    sections.append("</scope>")
    sections.append("")
    sections.append("<output_format>")
    sections.append(
        "Apply the project conventions from CLAUDE.md and language-specific "
        "best practices. Report your findings using the severity format "
        "described in your instructions."
    )
    sections.append("</output_format>")

    prompt = "\n".join(sections)

    pr_metadata = inputs.get("pr")
    if pr_metadata is not None:
        max_bytes_raw = inputs.get("pr_max_bytes")
        if max_bytes_raw is None:
            # No silent fallback cap (project rule) — a caller that supplies 'pr' without
            # the size bound the CLI is responsible for resolving is a caller error, not a
            # case to paper over with an arbitrary default.
            raise ValueError(
                "inputs['pr'] is present but inputs['pr_max_bytes'] is missing; the "
                "caller must resolve review.max_file_size_bytes and thread it through "
                "before invoking this prompt builder"
            )
        prompt = f"{prompt}\n\n{_pr_block(pr_metadata, int(max_bytes_raw))}"

    return prompt
