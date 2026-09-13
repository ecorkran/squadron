"""Tests for the shared CLI cwd resolution.

``sq review code`` and ``sq pr show`` both anchor at the git root; these pin
that behavior and the no-work-tree fallback (issue #86).

Config is faked by patching ``squadron.cli.commands.review.get_config`` —
the same seam the existing review tests use, which is why ``resolve_cwd``
reaches the config through that module.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from squadron.cli.commands import cwd_resolution, review
from squadron.cli.commands.cwd_resolution import resolve_cwd, resolve_repo_cwd


def _config_returning(value: str | None) -> Callable[[str], object]:
    """A ``get_config`` stub answering every key with ``value``."""

    def _stub(_key: str) -> object:
        return value

    return _stub


def _git_root_returning(value: str | None) -> Callable[[str], str | None]:
    """A ``find_git_root`` stub answering every cwd with ``value``."""

    def _stub(_cwd: str) -> str | None:
        return value

    return _stub


def test_flag_overrides_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(review, "get_config", _config_returning("/from/config"))
    assert resolve_cwd("/from/flag") == "/from/flag"


def test_config_used_when_flag_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(review, "get_config", _config_returning("/from/config"))
    assert resolve_cwd(None) == "/from/config"


def test_defaults_to_process_dir_when_config_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review, "get_config", _config_returning(None))
    assert resolve_cwd(None) == "."


def test_anchors_at_git_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A cwd inside the repo resolves to the repo root, not the subdirectory."""
    subdir = tmp_path / "project-documents" / "user"
    subdir.mkdir(parents=True)
    monkeypatch.setattr(review, "get_config", _config_returning(None))
    monkeypatch.setattr(cwd_resolution, "find_git_root", _git_root_returning(str(tmp_path)))
    assert resolve_repo_cwd(str(subdir)) == str(tmp_path)


def test_falls_back_to_resolved_cwd_outside_work_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(review, "get_config", _config_returning(None))
    monkeypatch.setattr(cwd_resolution, "find_git_root", _git_root_returning(None))
    assert resolve_repo_cwd(str(tmp_path)) == str(tmp_path)
