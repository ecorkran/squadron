"""The prompt the slice-case diff judge sends (slice 426 D12).

The packaged ``pairwise-diff-judge.md`` is loaded and hashed the way 177's pairwise prompt
is; its sha256 is the ``JudgeRef.prompt_hash``, so these judgments never mix with 177's. The
frontmatter the file carries is not part of what the judge reads.
"""

from __future__ import annotations

import hashlib
from functools import cache

from squadron.data import data_dir
from squadron.replay.judge import strip_frontmatter

_PROMPT_PATH = ("benchmark", "pairwise-diff-judge.md")


@cache
def diff_judge_prompt() -> str:
    """The packaged judge prompt, as stored (frontmatter included)."""
    return data_dir().joinpath(*_PROMPT_PATH).read_text(encoding="utf-8")


@cache
def diff_judge_prompt_hash() -> str:
    """SHA-256 of the packaged prompt; judgments under another hash are another judge."""
    return hashlib.sha256(diff_judge_prompt().encode("utf-8")).hexdigest()


def diff_prompt(task_text: str, diff_a: str, diff_b: str) -> str:
    """The packaged prompt, then ``## Task``, ``## Implementation A`` and ``## Implementation B``.

    The task text and both diffs are included verbatim: nothing is shortened here, because an
    oversized prompt excludes the case instead (D14).
    """
    body = strip_frontmatter(diff_judge_prompt()).strip()
    return (
        f"{body}\n\n## Task\n\n{task_text}\n\n"
        f"## Implementation A\n\n{diff_a}\n\n## Implementation B\n\n{diff_b}\n"
    )
