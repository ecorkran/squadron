"""File and reply handling for dispatch steps (slice 949).

Holds the logic behind a dispatch step's ``prompt_files``, ``reply_from``, ``reply_format``,
``reply_file`` and ``delivered_prompt_file`` keys, so ``actions/dispatch.py`` gains only call
sites: prompt assembly (D2), reply hand-off between steps (D3), JSON extraction (D4) and the
output files (D5). The key names and ``ReplyFormat`` live in ``pipeline/dispatch_keys.py``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

from squadron.core.file_write import write_new_file
from squadron.pipeline.actions import ActionType
from squadron.pipeline.dispatch_keys import (
    DELIVERED_PROMPT_FILE_KEY,
    PROMPT_FILES_KEY,
    REPLY_FILE_KEY,
    REPLY_FROM_KEY,
    path_error,
)
from squadron.pipeline.models import ActionResult, results_for_step

_logger = logging.getLogger(__name__)

#: ``ActionResult.outputs`` keys a dispatch step records its reply under.
RESPONSE_KEY = "response"
REPLY_JSON_KEY = "reply_json"

_PART_SEPARATOR = "\n\n"


class DispatchInputError(Exception):
    """A dispatch step's inputs (a prompt file, an earlier step's reply) are unusable."""


class OutputWriteError(Exception):
    """A dispatch step's reply or delivered-prompt file could not be written."""


def _reject_constant(name: str) -> object:
    raise ValueError(f"{name} is not valid JSON")


_STRICT_DECODER = json.JSONDecoder(parse_constant=_reject_constant)


def extract_json_object(text: str) -> str | None:
    """The first JSON object in *text*, as the original substring, or ``None`` (D4).

    Each ``{`` is tried in order; the first span that decodes is returned verbatim, never
    re-serialized. Code fences need no special case: the scan sees through them. ``NaN``
    and ``Infinity`` are refused so the result is valid strict JSON for any consumer.
    """
    start = text.find("{")
    while start != -1:
        try:
            _, end = _STRICT_DECODER.raw_decode(text, start)
        except ValueError:
            # Not JSON from this brace (a bad token, or a refused constant): try the next one.
            start = text.find("{", start + 1)
            continue
        return text[start:end]
    return None


def _read_prompt_file(relative: str, cwd: Path) -> str:
    """One prompt file's content, verbatim UTF-8 (D2)."""
    if (problem := path_error(relative)) is not None:
        raise DispatchInputError(f"'{PROMPT_FILES_KEY}': {problem}")
    path = cwd / relative
    try:
        # is_file() first: it refuses missing paths, directories, FIFOs and devices, so the
        # read below cannot block on a pipe. It raises PermissionError when a parent
        # directory cannot be searched, hence inside the try.
        if not path.is_file():
            raise DispatchInputError(
                f"prompt file '{relative}' is not a regular file (missing, a directory or a pipe)"
            )
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise DispatchInputError(f"prompt file '{relative}' cannot be read: {exc}") from exc


def assemble_prompt(
    *,
    prompt: str | None,
    prompt_files: Sequence[str],
    reply: str | None,
    cwd: Path,
) -> str:
    """The prompt: *prompt*, then each file, then *reply*, joined by a blank line (D2).

    Placeholders were resolved on the step config before this runs, so ``{...}`` text
    inside a file is never substituted. A step with only *prompt* comes back unchanged.
    """
    parts: list[str] = [] if prompt is None else [prompt]
    parts.extend(_read_prompt_file(relative, cwd) for relative in prompt_files)
    if reply is not None:
        parts.append(reply)
    return _PART_SEPARATOR.join(parts)


def step_reply(prior_outputs: Mapping[str, ActionResult], step_name: str) -> str:
    """The reply the dispatch step *step_name* handed on (D3).

    ``reply_json`` when the step extracted one, else ``response``. A step with no dispatch
    result, a failed one, or one with no reply (it kept an existing artifact and skipped
    the call) cannot feed another step, and an empty reply is never passed on.
    """
    dispatched = [
        result
        for result in results_for_step(prior_outputs, step_name)
        if result.action_type == ActionType.DISPATCH
    ]
    if not dispatched:
        raise DispatchInputError(f"'{REPLY_FROM_KEY}' step '{step_name}' has no dispatch result")
    outputs = dispatched[-1].outputs
    if not dispatched[-1].success:
        raise DispatchInputError(f"'{REPLY_FROM_KEY}' step '{step_name}' failed, so it has no reply")
    reply = outputs.get(REPLY_JSON_KEY) or outputs.get(RESPONSE_KEY)
    if not isinstance(reply, str) or not reply:
        raise DispatchInputError(f"'{REPLY_FROM_KEY}' step '{step_name}' recorded no reply")
    return reply


def _checked_output_path(key: str, relative: str, cwd: Path) -> Path:
    if (problem := path_error(relative)) is not None:
        raise OutputWriteError(f"'{key}': {problem}")
    return cwd / relative


def _write(path: Path, text: str) -> None:
    try:
        write_new_file(path, text.encode("utf-8"), force=True)
    except OSError as exc:
        raise OutputWriteError(f"cannot write '{path}': {exc}") from exc


def _prior_bytes(path: Path) -> bytes | None:
    """The file's current bytes, or ``None`` when it does not exist."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise OutputWriteError(f"cannot read '{path}' before replacing it: {exc}") from exc


def _restore(path: Path, prior: bytes | None) -> None:
    """Put the prompt file back as it was; log at ERROR if even that fails (D5)."""
    try:
        if prior is None:
            path.unlink(missing_ok=True)
        else:
            write_new_file(path, prior, force=True)
    except OSError:
        _logger.exception(
            "dispatch: could not restore prompt file '%s' after a failed reply write; "
            "the file now holds this step's delivered prompt",
            path,
        )


def write_step_files(
    *,
    cwd: Path,
    delivered_prompt_file: str | None,
    delivered_prompt: str,
    reply_file: str | None,
    reply: str,
) -> None:
    """Write the delivered prompt, then the reply, each replacing its file whole (D5).

    The prompt file goes first and the reply file last. If the reply write fails, the
    prompt file is put back as it was (or removed when it was new), so a failed step leaves
    both files as they were.
    """
    prompt_path = (
        None
        if delivered_prompt_file is None
        else _checked_output_path(DELIVERED_PROMPT_FILE_KEY, delivered_prompt_file, cwd)
    )
    reply_path = None if reply_file is None else _checked_output_path(REPLY_FILE_KEY, reply_file, cwd)
    prior = None if prompt_path is None else _prior_bytes(prompt_path)
    if prompt_path is not None:
        _write(prompt_path, delivered_prompt)
    if reply_path is None:
        return
    try:
        _write(reply_path, reply)
    except OutputWriteError:
        if prompt_path is not None:
            _restore(prompt_path, prior)
        raise
