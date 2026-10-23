"""Python type-error count from pyright, gated on a resolved uv environment (D7, D8).

Pyright's answer depends on the installed packages, so type errors are measured only
when the project's uv environment exists and is in sync with ``uv.lock``. Otherwise
they are absent with ``environment_unresolved`` naming the failing condition.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from squadron.metrology.snapshot.config_hash import file_content_hash, pyproject_table_hash
from squadron.metrology.snapshot.contract import AdapterContext
from squadron.metrology.snapshot.python_lint import PROJECT_TOOL_DIRS
from squadron.metrology.snapshot.runner import probe_version, resolve_tool, stderr_head
from squadron.metrology.snapshot.tool_support import (
    absent,
    probe_or_failure,
    repo_relative,
    run_chunked,
    tool_failed,
    tool_missing,
)
from squadron.metrology.snapshot_models import (
    RULE_SET_SOURCE_TOOL_DEFAULTS,
    AbsenceReason,
    EnvironmentIdentity,
    Measurement,
    RuleSetIdentity,
    SnapshotMetric,
    SourceLanguage,
    ToolIdentity,
)

_logger = logging.getLogger(__name__)

PYRIGHT_TOOL_NAME = "pyright"
UV_TOOL_NAME = "uv"
LOCKFILE = "uv.lock"
VENV_DIR = ".venv"
VENV_PYTHON = ".venv/bin/python"

#: Lockfiles of other tools. Only uv is supported; adding one is new adapter code.
_UNSUPPORTED_LOCKFILES = ("poetry.lock", "Pipfile.lock", "pdm.lock")

_PYRIGHT_CONFIG_FILE = "pyrightconfig.json"
_PYPROJECT = "pyproject.toml"
_PYPROJECT_TABLE = ("tool", "pyright")

#: ``uv sync --check`` exits 1 when the environment is out of date; 0 when in sync.
_UV_IN_SYNC = 0
_UV_OUT_OF_SYNC = 1
#: Pyright exits 0 with no errors and 1 with errors; both carry a JSON report.
_PYRIGHT_REPORT_EXITS = frozenset({0, 1})

_COUNTING = (
    "pyright errors per file (warnings and information excluded), over every snapshot "
    "file regardless of pyright's own include setting"
)

_METRIC = SnapshotMetric.TYPE_ERRORS
_LANGUAGE = SourceLanguage.PYTHON


def _unresolved(detail: str) -> Measurement:
    _logger.warning("%s: environment unresolved (%s)", _METRIC.value, detail)
    return absent(_LANGUAGE, _METRIC, AbsenceReason.ENVIRONMENT_UNRESOLVED, detail)


def _check_lock_and_venv(repo_root: Path) -> str | None:
    """The failing condition among conditions 1 and 2 of D7, or None if both hold."""
    if not (repo_root / LOCKFILE).is_file():
        for other in _UNSUPPORTED_LOCKFILES:
            if (repo_root / other).is_file():
                return f"lockfile type not supported: {other}"
        return f"{LOCKFILE} not found"
    if not (repo_root / VENV_DIR).is_dir():
        return f"{VENV_DIR} not found"
    return None


def resolve_environment(ctx: AdapterContext) -> EnvironmentIdentity | Measurement:
    """The environment identity if resolved, else the absent measurement to return."""
    failing = _check_lock_and_venv(ctx.repo_root)
    if failing is not None:
        return _unresolved(failing)
    uv = resolve_tool(ctx.repo_root, UV_TOOL_NAME, (), use_path=True)
    if uv is None:
        return tool_missing(_LANGUAGE, _METRIC, UV_TOOL_NAME, "PATH")
    argv = [str(uv), "sync", "--check", "--locked", "--offline"]
    result = ctx.runner.run(argv, cwd=ctx.repo_root, timeout_s=ctx.tool_timeout_s)
    command = " ".join(argv)
    if result.timed_out:
        return tool_failed(
            _LANGUAGE,
            _METRIC,
            f"uv timed out after {ctx.tool_timeout_s}s",
            command=command,
            stderr=result.stderr,
        )
    if result.exit_code == _UV_OUT_OF_SYNC:
        return _unresolved(f"{VENV_DIR} is out of sync with {LOCKFILE}")
    if result.exit_code != _UV_IN_SYNC:
        return tool_failed(
            _LANGUAGE,
            _METRIC,
            f"uv exited {result.exit_code}: {stderr_head(result.stderr)}",
            command=command,
            stderr=result.stderr,
        )
    python = probe_version(ctx.runner, ctx.repo_root / VENV_PYTHON, ctx.repo_root, ctx.tool_timeout_s)
    if python.version is None:
        return tool_failed(
            _LANGUAGE,
            _METRIC,
            f"can't read the {VENV_PYTHON} version: {python.failure}",
            command=f"{VENV_PYTHON} --version",
        )
    return EnvironmentIdentity(
        lockfile_path=LOCKFILE,
        lockfile_sha256=file_content_hash(ctx.repo_root / LOCKFILE),
        interpreter_version=python.version,
    )


def resolve_pyright_rule_set(repo_root: Path) -> RuleSetIdentity:
    """pyrightconfig.json, then pyproject [tool.pyright], else explicit tool defaults."""
    config = repo_root / _PYRIGHT_CONFIG_FILE
    if config.is_file():
        return RuleSetIdentity(source=_PYRIGHT_CONFIG_FILE, content_hash=file_content_hash(config))
    pyproject = repo_root / _PYPROJECT
    if pyproject.is_file():
        table_hash = pyproject_table_hash(pyproject, _PYPROJECT_TABLE)
        if table_hash is not None:
            return RuleSetIdentity(source=f"{_PYPROJECT}[tool.pyright]", content_hash=table_hash)
    return RuleSetIdentity(source=RULE_SET_SOURCE_TOOL_DEFAULTS, content_hash=None)


def _count_errors(stdout: str, repo_root: Path) -> dict[str, int] | str:
    """Error-severity diagnostics per file from pyright's JSON, or a failure detail."""
    try:
        report: object = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return f"pyright output isn't valid JSON: {exc}"
    diagnostics: object = report.get("generalDiagnostics") if isinstance(report, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(diagnostics, list):
        return "pyright output has no generalDiagnostics list"
    counts: dict[str, int] = {}
    for diagnostic in diagnostics:  # pyright: ignore[reportUnknownVariableType]
        if not isinstance(diagnostic, dict) or diagnostic.get("severity") != "error":  # pyright: ignore[reportUnknownMemberType]
            continue
        filename = diagnostic.get("file")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        relative = repo_relative(filename, repo_root) if isinstance(filename, str) else None
        if relative is None:
            return f"pyright reported a path outside the repo: {filename!r}"
        counts[relative] = counts.get(relative, 0) + 1
    return counts


def measure_pyright_types(ctx: AdapterContext, files: list[str]) -> Measurement:
    """Type-error count; absent (never partial) unless the environment and pyright both resolve."""
    environment = resolve_environment(ctx)
    if isinstance(environment, Measurement):
        return environment
    tool_path = resolve_tool(ctx.repo_root, PYRIGHT_TOOL_NAME, PROJECT_TOOL_DIRS, use_path=True)
    if tool_path is None:
        return tool_missing(_LANGUAGE, _METRIC, PYRIGHT_TOOL_NAME, f"{PROJECT_TOOL_DIRS[0]} or on PATH")
    version = probe_or_failure(ctx, _LANGUAGE, _METRIC, tool_path)
    if isinstance(version, Measurement):
        return version
    try:
        rule_set = resolve_pyright_rule_set(ctx.repo_root)
    except ValueError as exc:
        return tool_failed(_LANGUAGE, _METRIC, str(exc), command="resolve pyright rule set")
    counts: dict[str, int] = {}

    def fold(stdout: str) -> str | None:
        parsed = _count_errors(stdout, ctx.repo_root)
        if isinstance(parsed, str):
            return parsed
        for path, count in parsed.items():
            counts[path] = counts.get(path, 0) + count
        return None

    failure = run_chunked(
        ctx,
        language=_LANGUAGE,
        metric=_METRIC,
        tool_name=PYRIGHT_TOOL_NAME,
        tool_path=tool_path,
        files=files,
        build_argv=lambda chunk: [
            str(tool_path),
            "--outputjson",
            "--pythonpath",
            VENV_PYTHON,
            *chunk,
        ],
        ok_exits=_PYRIGHT_REPORT_EXITS,
        fold=fold,
    )
    if failure is not None:
        return failure
    return Measurement(
        metric=_METRIC,
        language=_LANGUAGE,
        tool=ToolIdentity(name=PYRIGHT_TOOL_NAME, version=version, counting=_COUNTING),
        rule_set=rule_set,
        environment=environment,
        per_file=counts,
    )
