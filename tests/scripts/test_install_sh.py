"""Thin pytest wrapper: runs the bash idempotency smoke test for install.sh."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).parent / "test_install_sh.sh"


def test_install_sh_idempotency() -> None:
    """install.sh does not re-invoke install stubs when tools are already on PATH."""
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ},
    )
    assert result.returncode == 0, (
        f"test_install_sh.sh failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
