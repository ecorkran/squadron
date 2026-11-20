"""File I/O around one comb call, as the hidden ``_stage`` command runs it (slice 430 D6).

The input file is a JSON list of ``RecallFinding`` (the parent stage's kept findings); the
call itself is ``recipes.comb_call.run_comb_stage``. The output file is written only after
the model call returns, so its absence means the call never finished (D8).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from squadron.core.process_runner import ProcessRunner
from squadron.metrology.recall_run_models import RecallFinding

_FINDINGS = TypeAdapter(list[RecallFinding])


class StageInputError(ValueError):
    """The input file is unreadable or not a JSON list of findings."""


def read_stage_input(path: Path) -> list[RecallFinding]:
    try:
        return _FINDINGS.validate_json(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise StageInputError(f"comb input {path} unreadable: {exc}") from exc


def changed_files(runner: ProcessRunner, cwd: Path, base: str, timeout: float) -> str:
    """``git diff --name-only <base> HEAD`` in the sandbox; a failure raises."""
    result = runner.run(["git", "diff", "--name-only", base, "HEAD"], cwd=str(cwd), timeout=timeout)
    if result.returncode != 0:
        raise StageInputError(
            f"git diff --name-only {base} HEAD failed: {result.stderr.strip()[-300:]}"
        )
    return result.stdout.strip()


def write_stage_output(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2), encoding="utf-8")
