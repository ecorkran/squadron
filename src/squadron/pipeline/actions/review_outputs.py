"""The review action's output contract: key names and typed readers.

``ActionResult.outputs`` and findings are untyped dicts. The review action
writes them with these keys, and every reader (dispatch feedback, the batch
report) goes through the functions below rather than spelling the keys as
literals. A present key holding the wrong type raises ``TypeError``: that is a
bug in the writer, never an absent value.
"""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from squadron.pipeline.models import ActionResult


class ReviewOutputKey(StrEnum):
    """Keys the review action writes into ``ActionResult.outputs``.

    The single-part keys keep the values they had before split reviews
    existed, so a single-part result is unchanged.
    """

    RESPONSE = "response"
    INPUT_FILE = "input_file"
    INPUT_FILES = "input_files"
    REVIEW_FILE = "review_file"
    REVIEW_FILES = "review_files"
    UNSAVED_PARTS = "unsaved_parts"


#: Per-finding key naming the part file a multi-part finding came from.
FINDING_INPUT_FILE = "input_file"


def _str_list(value: object, key: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeError(f"review output '{key}' must be a list of str, got {type(value).__name__}")
    items: list[str] = []
    # Widening only: every list is a list[object]; each item is checked below.
    for item in cast(list[object], value):
        if not isinstance(item, str):
            raise TypeError(f"review output '{key}' must hold only str, got {type(item).__name__}")
        items.append(item)
    return items


def _optional_str(mapping: dict[str, object], key: str) -> str | None:
    value = mapping.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError(f"review output '{key}' must be a str, got {type(value).__name__}")
    return value


def review_response(result: ActionResult) -> str:
    """The review's raw model output.

    Raises:
        TypeError: If ``RESPONSE`` is absent or not a str — every review
            result carries one.
    """
    response = _optional_str(result.outputs, ReviewOutputKey.RESPONSE)
    if response is None:
        raise TypeError(f"review output '{ReviewOutputKey.RESPONSE}' is missing")
    return response


def review_input_files(result: ActionResult) -> list[str]:
    """Every reviewed file: ``INPUT_FILES``, else ``[INPUT_FILE]``, else ``[]``."""
    if ReviewOutputKey.INPUT_FILES in result.outputs:
        return _str_list(result.outputs[ReviewOutputKey.INPUT_FILES], ReviewOutputKey.INPUT_FILES)
    single = _optional_str(result.outputs, ReviewOutputKey.INPUT_FILE)
    return [single] if single is not None else []


def review_file(result: ActionResult) -> str | None:
    """The saved review artifact for the worst part, or ``None`` when unsaved."""
    return _optional_str(result.outputs, ReviewOutputKey.REVIEW_FILE)


def unsaved_parts(result: ActionResult) -> list[str]:
    """Input paths of parts whose review could not be saved; ``[]`` when absent."""
    if ReviewOutputKey.UNSAVED_PARTS not in result.outputs:
        return []
    return _str_list(result.outputs[ReviewOutputKey.UNSAVED_PARTS], ReviewOutputKey.UNSAVED_PARTS)


def finding_input_file(finding: dict[str, object]) -> str | None:
    """The part file a finding came from, or ``None`` for a single-part finding."""
    return _optional_str(finding, FINDING_INPUT_FILE)
