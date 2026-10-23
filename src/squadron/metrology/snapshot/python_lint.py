"""Python lint count from ruff (slice 400, D4, D8).

Ruff runs read-only (``--no-cache``) over the explicit snapshot file list with
``--exit-zero``, so any non-zero exit is a failure, not a finding. Tool-level
``include``/``exclude`` aren't applied: every metric covers the same files.
"""

from __future__ import annotations

import json
from pathlib import Path

from squadron.metrology.snapshot.config_hash import file_content_hash, pyproject_table_hash
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
    RULE_SET_SOURCE_TOOL_DEFAULTS,
    Measurement,
    RuleSetIdentity,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

RUFF_TOOL_NAME = "ruff"
PROJECT_TOOL_DIRS = (".venv/bin",)

#: ``--exit-zero`` makes findings exit 0, so any other exit code is a failure.
_REPORT_EXITS = frozenset({0})
_RUFF_ARGS = ("check", "--no-cache", "--exit-zero", "--output-format", "json")

_COUNTING = (
    "ruff findings per file under the project's own rule selection; syntax errors count as findings"
)

#: Ruff config files in precedence order, then the pyproject table.
_RUFF_CONFIG_FILES = ("ruff.toml", ".ruff.toml")
_PYPROJECT = "pyproject.toml"
_PYPROJECT_TABLE = ("tool", "ruff")


def resolve_ruff_rule_set(repo_root: Path) -> RuleSetIdentity:
    """The ruff config in effect: ruff.toml, .ruff.toml, pyproject [tool.ruff], else defaults."""
    for name in _RUFF_CONFIG_FILES:
        if (repo_root / name).is_file():
            return RuleSetIdentity(source=name, content_hash=file_content_hash(repo_root / name))
    pyproject = repo_root / _PYPROJECT
    if pyproject.is_file():
        table_hash = pyproject_table_hash(pyproject, _PYPROJECT_TABLE)
        if table_hash is not None:
            return RuleSetIdentity(source=f"{_PYPROJECT}[tool.ruff]", content_hash=table_hash)
    return RuleSetIdentity(source=RULE_SET_SOURCE_TOOL_DEFAULTS, content_hash=None)


def _count_findings(stdout: str, repo_root: Path) -> dict[str, int] | str:
    """Findings per file from ruff's JSON, or a failure detail."""
    try:
        parsed: object = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return f"ruff output isn't valid JSON: {exc}"
    if not isinstance(parsed, list):
        return "ruff output isn't a JSON list"
    counts: dict[str, int] = {}
    for entry in parsed:  # pyright: ignore[reportUnknownVariableType]
        filename = entry.get("filename") if isinstance(entry, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        if not isinstance(filename, str):
            return "ruff finding has no filename"
        relative = repo_relative(filename, repo_root)
        if relative is None:
            return f"ruff reported a path outside the repo: {filename}"
        counts[relative] = counts.get(relative, 0) + 1
    return counts


def measure_ruff_lint(ctx: AdapterContext, files: list[str]) -> Measurement:
    """Lint count for *files*; absent (never partial) when ruff can't give a full answer."""
    language, metric = SourceLanguage.PYTHON, SnapshotMetric.LINT_COUNT
    tool_path = resolve_tool(ctx.repo_root, RUFF_TOOL_NAME, PROJECT_TOOL_DIRS, use_path=True)
    if tool_path is None:
        return tool_missing(language, metric, RUFF_TOOL_NAME, f"{PROJECT_TOOL_DIRS[0]} or on PATH")
    version = probe_or_failure(ctx, language, metric, tool_path)
    if isinstance(version, Measurement):
        return version
    try:
        rule_set = resolve_ruff_rule_set(ctx.repo_root)
    except ValueError as exc:
        return tool_failed(language, metric, str(exc), command="resolve ruff rule set")
    counts: dict[str, int] = {}

    def fold(stdout: str) -> str | None:
        parsed = _count_findings(stdout, ctx.repo_root)
        if isinstance(parsed, str):
            return parsed
        for path, count in parsed.items():
            counts[path] = counts.get(path, 0) + count
        return None

    failure = run_chunked(
        ctx,
        language=language,
        metric=metric,
        tool_name=RUFF_TOOL_NAME,
        tool_path=tool_path,
        files=files,
        build_argv=lambda chunk: [str(tool_path), *_RUFF_ARGS, *chunk],
        ok_exits=_REPORT_EXITS,
        fold=fold,
    )
    if failure is not None:
        return failure
    return Measurement(
        metric=metric,
        language=language,
        tool=ToolIdentity(name=RUFF_TOOL_NAME, version=version, counting=_COUNTING),
        rule_set=rule_set,
        per_file=counts,
    )
