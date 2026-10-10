"""Code-host errors print bracketed text intact (slice 940 D5, #177)."""

from __future__ import annotations

import pytest

from squadron.cli.commands.pr import render_code_host_error
from squadron.codehost.errors import CodeHostError


def test_bracketed_repository_name_survives(capsys: pytest.CaptureFixture[str]) -> None:
    render_code_host_error(CodeHostError("no remote points at acme/tool[codex]"))

    assert "acme/tool[codex]" in capsys.readouterr().err
