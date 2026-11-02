"""Config keys of the dispatch step's file-in, file-out contract (slice 949 D1).

A leaf module on purpose: ``steps/dispatch.py`` validates and forwards these keys and
``actions/dispatch_io.py`` acts on them. Each imports this module; neither imports the
other, so there is no cycle between the step layer and the action layer.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePath

#: Files whose content is appended to the prompt, in order.
PROMPT_FILES_KEY = "prompt_files"
#: Name of an earlier top-level dispatch step whose reply is appended to the prompt.
REPLY_FROM_KEY = "reply_from"
#: How the step's own reply is read: see ``ReplyFormat``.
REPLY_FORMAT_KEY = "reply_format"
#: File that receives the step's reply.
REPLY_FILE_KEY = "reply_file"
#: File that receives the exact prompt delivered to the model.
DELIVERED_PROMPT_FILE_KEY = "delivered_prompt_file"

#: Every key above, in the order the docs list them.
DISPATCH_IO_KEYS: tuple[str, ...] = (
    PROMPT_FILES_KEY,
    REPLY_FROM_KEY,
    REPLY_FORMAT_KEY,
    REPLY_FILE_KEY,
    DELIVERED_PROMPT_FILE_KEY,
)


class ReplyFormat(StrEnum):
    """What a dispatch step's reply is expected to be."""

    TEXT = "text"  # the reply is kept as it is (the default)
    JSON = "json"  # the first JSON object in the reply is extracted (D4)


def path_error(value: str) -> str | None:
    """Why *value* is not an acceptable file path for these keys, or ``None``.

    Paths resolve against the run's working directory, so they must be relative and must
    not climb out of it. Symlinks are not resolved: pipelines are trusted author content
    and this check only catches mistakes (D1). The one function runs at load time and at
    run time, so the two cannot disagree.
    """
    if not value.strip():
        return "path is empty"
    path = PurePath(value)
    if path.is_absolute():
        return f"path '{value}' must be relative to the working directory"
    if ".." in path.parts:
        return f"path '{value}' must not contain '..'"
    return None
