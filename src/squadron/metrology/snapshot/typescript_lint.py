"""TypeScript lint count from the project's own ESLint (slice 400, D4, D5, D8).

ESLint comes only from ``node_modules/.bin`` (never ``PATH``, never ``npx``, which can
download and write), runs without ``--cache``, and uses the project's flat config.
Findings are counted per file. Files ESLint skips through the config's ``ignores`` are
dropped from the measurement and listed in ``tool_ignored_files`` (D4), so the lint
file set differs from the length file set by exactly that recorded list.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from squadron.metrology.snapshot.config_hash import file_content_hash
from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.runner import resolve_tool
from squadron.metrology.snapshot.tool_support import (
    probe_or_failure,
    repo_relative,
    run_chunked,
    tool_failed,
    tool_missing,
)
from squadron.metrology.snapshot_models import (
    Measurement,
    RuleSetIdentity,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

ESLINT_TOOL_NAME = "eslint"
ESLINT_PROJECT_DIRS = ("node_modules/.bin",)
ESLINT_BINARY = f"{ESLINT_PROJECT_DIRS[0]}/{ESLINT_TOOL_NAME}"

#: Flat-config file names, in the order ESLint itself looks for them.
ESLINT_CONFIG_FILES = ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs")
_NO_CONFIG_DETAIL = "no eslint.config.{js,mjs,cjs} found"

#: ESLint exits 0 (no error-severity findings) or 1 (error-severity findings) with a
#: JSON report. Exit 2 is a fatal failure such as a config that fails to load.
_REPORT_EXITS = frozenset({0, 1})

_COUNTING = (
    "ESLint messages (errors and warnings) per file under the project's flat config; "
    "files skipped by the config's ignores are listed, not counted"
)

_METRIC = SnapshotMetric.LINT_COUNT
_LANGUAGE = SourceLanguage.TYPESCRIPT


def resolve_eslint_rule_set(repo_root: Path) -> RuleSetIdentity | None:
    """The first flat-config file present, hashed by content; None when there is none."""
    for name in ESLINT_CONFIG_FILES:
        config = repo_root / name
        if config.is_file():
            return RuleSetIdentity(source=name, content_hash=file_content_hash(config))
    return None


def _is_ignored_notice(result: dict[str, object]) -> bool:
    """True for ESLint's "file ignored" entry, as captured from ESLint 10.

    Its shape (see the fixtures README): a single non-fatal warning with a null
    ``ruleId`` and no position. A real null-``ruleId`` warning, such as an unused
    disable directive, always carries a line and column.
    """
    messages = result.get("messages")
    if not isinstance(messages, list) or len(cast("list[object]", messages)) != 1:
        return False
    message = cast("list[object]", messages)[0]
    if not isinstance(message, dict):
        return False
    fields = cast("dict[str, object]", message)
    return (
        fields.get("ruleId") is None
        and fields.get("severity") == 1
        and not fields.get("fatal")
        and "line" not in fields
    )


def _read_report(
    stdout: str, repo_root: Path, counts: dict[str, int], ignored: list[str]
) -> str | None:
    """Fold one ESLint JSON report into *counts* and *ignored*; return a failure detail or None."""
    try:
        report: object = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return f"eslint output isn't valid JSON: {exc}"
    if not isinstance(report, list):
        return "eslint output isn't a JSON list"
    for result in report:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(result, dict):
            return "eslint result isn't an object"
        filename = result.get("filePath")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        relative = repo_relative(filename, repo_root) if isinstance(filename, str) else None
        if relative is None:
            return f"eslint reported a path outside the repo: {filename!r}"
        if _is_ignored_notice(cast("dict[str, object]", result)):
            ignored.append(relative)
            continue
        messages = result.get("messages")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(messages, list):
            return f"eslint result for {relative} has no messages list"
        if messages:
            counts[relative] = counts.get(relative, 0) + len(messages)  # pyright: ignore[reportUnknownArgumentType]
    return None


def measure_eslint_lint(ctx: AdapterContext, files: list[str]) -> Measurement:
    """Lint count for *files*; absent (never partial) when ESLint can't give a full answer."""
    tool_path = resolve_tool(ctx.repo_root, ESLINT_TOOL_NAME, ESLINT_PROJECT_DIRS, use_path=False)
    if tool_path is None:
        return tool_missing(_LANGUAGE, _METRIC, ESLINT_BINARY)
    rule_set = resolve_eslint_rule_set(ctx.repo_root)
    if rule_set is None:
        return tool_failed(_LANGUAGE, _METRIC, _NO_CONFIG_DETAIL, command="resolve eslint config")
    version = probe_or_failure(ctx, _LANGUAGE, _METRIC, tool_path)
    if isinstance(version, Measurement):
        return version
    counts: dict[str, int] = {}
    ignored: list[str] = []
    failure = run_chunked(
        ctx,
        language=_LANGUAGE,
        metric=_METRIC,
        tool_name=ESLINT_TOOL_NAME,
        tool_path=tool_path,
        files=files,
        build_argv=lambda chunk: [str(tool_path), "--format", "json", *chunk],
        ok_exits=_REPORT_EXITS,
        fold=lambda stdout: _read_report(stdout, ctx.repo_root, counts, ignored),
    )
    if failure is not None:
        return failure
    return Measurement(
        metric=_METRIC,
        language=_LANGUAGE,
        tool=ToolIdentity(name=ESLINT_TOOL_NAME, version=version, counting=_COUNTING),
        rule_set=rule_set,
        per_file=counts,
        tool_ignored_files=ignored,
    )
