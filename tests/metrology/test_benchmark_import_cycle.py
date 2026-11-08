"""Metrology must not import from ``squadron.benchmark`` (import-order cycle, slice 422).

A cycle only shows when the first import of the process enters from one side, which a
shared pytest process hides. Each entry point is imported in a fresh interpreter.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

ENTRY_POINTS = [
    "squadron.cli.app",
    "squadron.benchmark.adapter",
    "squadron.metrology.benchmark_models",
    "squadron.metrology.models",
]


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_module_imports_first_in_a_fresh_interpreter(module: str) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", f"import {module}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
