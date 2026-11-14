"""Names shared by every part of the fix pipeline (slice 423).

A leaf module: it imports nothing from ``squadron.pipeline`` so the step type, the
action, the commit plan, the prompt renderer and the hidden commands can all use
the same keys and values without import cycles.
"""

from __future__ import annotations

from enum import StrEnum

# Step / pipeline param keys (``fix.yaml``, ``-p`` flags).
ISSUE_PARAM = "issue"
ISSUE_FILE_PARAM = "issue-file"
COMMIT_TO_PARAM = "commit-to"

# ``fix-context`` output keys. The commit action reads the same keys back from the
# step's prior outputs.
ISSUE_NUMBER_KEY = "issue_number"
ISSUE_SOURCE_KEY = "issue_source"
ISSUE_TEXT_SHA256_KEY = "issue_text_sha256"
START_HEAD_KEY = "start_head"
START_BRANCH_KEY = "start_branch"
COMMIT_TO_KEY = "commit_to"


class CommitTo(StrEnum):
    """Where the fix commit lands."""

    TARGET = "target"  # the integration target; it must be checked out
    CURRENT = "current"  # the branch checked out when fix-context runs; no cf


#: The ``commit-to`` values, in declaration order, for validation and help text.
COMMIT_TO_VALUES = tuple(member.value for member in CommitTo)


class IssueSource(StrEnum):
    """Where the issue text came from."""

    FILE = "file"  # a frozen file, read verbatim
    GITHUB = "github"  # fetched through the code host
