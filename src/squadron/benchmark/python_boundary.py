"""Run the boundary resolver in a sandbox and read its answer (slice 422 D6).

The resolver (``pytest_trace/boundary_resolver.py``) runs under the parent's interpreter
with the project installed. This side writes its input, runs it, and maps its exit codes: an
import failure is ``BoundaryUndecidable`` (a verdict on the candidate), anything else that
goes wrong is ``HarnessFailure`` (logged at ERROR; never a verdict).
"""

from __future__ import annotations

import json
import logging
import tomllib
from typing import Any

from squadron.benchmark.adapter import SandboxContext
from squadron.benchmark.fairness import (
    AllowedBoundary,
    BoundaryUndecidable,
    harness_failure,
    run_for_harness,
)
from squadron.benchmark.python_failure import venv_bin
from squadron.benchmark.python_tree_files import PYPROJECT_NAME, copy_trace_plugin

_logger = logging.getLogger(__name__)

RESOLVER_FILE = "boundary_resolver.py"
RESOLVER_CONFIG_FILE = "boundary_config.json"
#: Repeated from ``boundary_resolver.IMPORT_FAILURE_EXIT``, which this side cannot import (a
#: test asserts they agree).
IMPORT_FAILURE_EXIT = 3


def _project_declarations(ctx: SandboxContext) -> dict[str, Any]:
    """The distribution name and script targets from the tree's ``pyproject.toml``."""
    path = ctx.tree / PYPROJECT_NAME
    if not path.is_file():
        return {"name": None, "scripts": []}
    try:
        project = tomllib.loads(path.read_text(encoding="utf-8")).get("project", {})
    except tomllib.TOMLDecodeError as exc:
        raise harness_failure(f"{path} does not parse: {exc}") from exc
    scripts: list[str] = []
    for table in ("scripts", "gui-scripts"):
        scripts.extend(str(target) for target in project.get(table, {}).values())
    return {"name": project.get("name"), "scripts": scripts}


def resolve_boundary(ctx: SandboxContext) -> AllowedBoundary:
    """The ``(module, qualname)`` entries tests may reach; empty when nothing is declared."""
    plugin_dir = copy_trace_plugin(ctx)
    config = ctx.output_dir / RESOLVER_CONFIG_FILE
    config.write_text(json.dumps(_project_declarations(ctx)), encoding="utf-8")
    argv = [str(venv_bin(ctx.tree) / "python"), str(plugin_dir / RESOLVER_FILE), str(config)]
    result = run_for_harness(
        ctx.runner,
        argv,
        "the boundary resolver",
        cwd=str(ctx.tree),
        timeout=ctx.suite_timeout_s,
        env=ctx.env.variables((venv_bin(ctx.tree),)),
        replace_env=True,
    )
    if result.returncode == IMPORT_FAILURE_EXIT:
        raise BoundaryUndecidable(result.stderr.strip())
    if result.returncode != 0:
        raise harness_failure(
            f"the boundary resolver exited {result.returncode}; stderr: {result.stderr.strip()}"
        )
    return _parse(result.stdout)


def _parse(stdout: str) -> AllowedBoundary:
    try:
        entries = json.loads(stdout)["allowed"]
        return AllowedBoundary(frozenset((str(module), str(qualname)) for module, qualname in entries))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise harness_failure(
            f"the boundary resolver's output does not parse ({exc}): {stdout!r}"
        ) from exc
