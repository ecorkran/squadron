"""The CLI's ``.env`` loader, unpatched.

Every other test runs with ``_load_env_file`` patched to a no-op by the root
``hermetic_environment`` fixture, so this is the one test of the real loader.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Bound at collection, before any fixture replaces the module attribute.
from squadron.cli.app import _load_env_file  # pyright: ignore[reportPrivateUsage]

_PROBE_VAR = "SQUADRON_TEST_ENV_FILE_PROBE"


def test_load_env_file_reads_cwd_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".env").write_text(f"{_PROBE_VAR}=loaded\n")
    monkeypatch.chdir(tmp_path)
    try:
        _load_env_file()
        assert os.environ.get(_PROBE_VAR) == "loaded"
    finally:
        os.environ.pop(_PROBE_VAR, None)
