"""Tests for install_settings.py — settings.json load/save and merge logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from squadron.cli.commands.install_settings import (
    _is_squadron_entry,
    _load_settings,
    _save_settings,
    _squadron_entry,
    remove_precompact_hook,
    settings_json_path,
    write_precompact_hook,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> dict[str, object]:
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)
    return data


def _third_party_entry() -> dict[str, object]:
    return {
        "matcher": "",
        "hooks": [{"type": "command", "command": "echo other"}],
    }


# ---------------------------------------------------------------------------
# T7: path + load + save
# ---------------------------------------------------------------------------


class TestSettingsPath:
    def testsettings_json_path(self, tmp_path: Path) -> None:
        assert settings_json_path(tmp_path) == tmp_path / ".claude" / "settings.json"


class TestLoadSettings:
    def test_missing_file_returns_empty_dict(self, tmp_path: Path) -> None:
        assert _load_settings(tmp_path / "settings.json") == {}

    def test_valid_json_returns_parsed_dict(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text('{"theme": "dark", "hooks": {}}')
        assert _load_settings(path) == {"theme": "dark", "hooks": {}}

    def test_corrupt_json_raises_runtime_error(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("{not valid json")
        with pytest.raises(RuntimeError, match="corrupt settings.json"):
            _load_settings(path)

    def test_non_object_top_level_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("[]")
        with pytest.raises(RuntimeError, match="not an object"):
            _load_settings(path)


class TestSaveSettings:
    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        path = tmp_path / "deeply" / "nested" / "settings.json"
        _save_settings(path, {"x": 1})
        assert path.is_file()
        assert _read_json(path) == {"x": 1}

    def test_writes_indented_json_with_trailing_newline(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _save_settings(path, {"theme": "dark"})
        content = path.read_text()
        assert content.endswith("\n")
        assert '  "theme"' in content  # 2-space indent


# ---------------------------------------------------------------------------
# _is_squadron_entry
# ---------------------------------------------------------------------------


class TestIsSquadronEntry:
    def test_valid_squadron_entry(self) -> None:
        assert _is_squadron_entry(_squadron_entry()) is True

    def test_third_party_entry(self) -> None:
        assert _is_squadron_entry(_third_party_entry()) is False

    def test_missing_hooks_key(self) -> None:
        assert _is_squadron_entry({"matcher": ""}) is False

    def test_non_dict(self) -> None:
        assert _is_squadron_entry("string") is False
        assert _is_squadron_entry(None) is False

    def test_hooks_not_list(self) -> None:
        assert _is_squadron_entry({"matcher": "", "hooks": "nope"}) is False


# ---------------------------------------------------------------------------
# T8: write_precompact_hook merge logic
# ---------------------------------------------------------------------------


class TestWritePrecompactHook:
    def test_fresh_file_creates_single_entry(self, tmp_path: Path) -> None:
        path = tmp_path / ".claude" / "settings.json"
        write_precompact_hook(path)

        data = _read_json(path)
        assert "hooks" in data
        hooks = data["hooks"]
        assert isinstance(hooks, dict)
        precompact = hooks["PreCompact"]
        assert isinstance(precompact, list)
        assert len(precompact) == 1
        assert _is_squadron_entry(precompact[0])

    def test_existing_file_without_hooks_key(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _save_settings(path, {"theme": "dark"})
        write_precompact_hook(path)

        data = _read_json(path)
        assert data["theme"] == "dark"
        hooks = data["hooks"]
        assert isinstance(hooks, dict)
        assert len(hooks["PreCompact"]) == 1  # type: ignore[index]

    def test_existing_non_squadron_entry_is_appended_not_replaced(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "settings.json"
        _save_settings(path, {"hooks": {"PreCompact": [_third_party_entry()]}})
        write_precompact_hook(path)

        data = _read_json(path)
        precompact = data["hooks"]["PreCompact"]  # type: ignore[index]
        assert len(precompact) == 2
        assert precompact[0] == _third_party_entry()
        assert _is_squadron_entry(precompact[1])

    def test_existing_squadron_entry_is_replaced_in_place(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        # An "old" squadron entry with extra cruft to verify full replacement
        stale = _squadron_entry()
        cast_hooks = stale["hooks"]
        assert isinstance(cast_hooks, list)
        cast_hooks[0]["command"] = "sq _precompact-hook --old-flag"  # type: ignore[index]
        _save_settings(
            path,
            {"hooks": {"PreCompact": [_third_party_entry(), stale]}},
        )
        write_precompact_hook(path)

        data = _read_json(path)
        precompact = data["hooks"]["PreCompact"]  # type: ignore[index]
        assert len(precompact) == 2
        # Third-party preserved at position 0
        assert precompact[0] == _third_party_entry()
        # Squadron entry at position 1, with the CURRENT command
        assert _is_squadron_entry(precompact[1])
        assert precompact[1]["hooks"][0]["command"] == "sq _precompact-hook"

    def test_preserves_unrelated_top_level_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _save_settings(path, {"theme": "dark", "model": "claude-opus"})
        write_precompact_hook(path)

        data = _read_json(path)
        assert data["theme"] == "dark"
        assert data["model"] == "claude-opus"

    def test_preserves_other_hook_event_names(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _save_settings(
            path,
            {
                "hooks": {
                    "PostToolUse": [{"matcher": "", "hooks": [{"type": "command"}]}]
                }
            },
        )
        write_precompact_hook(path)

        data = _read_json(path)
        hooks = data["hooks"]
        assert "PostToolUse" in hooks  # type: ignore[operator]
        assert "PreCompact" in hooks  # type: ignore[operator]

    def test_idempotent(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        write_precompact_hook(path)
        first = path.read_text()
        write_precompact_hook(path)
        second = path.read_text()
        assert first == second


# ---------------------------------------------------------------------------
# T9: remove_precompact_hook
# ---------------------------------------------------------------------------


class TestRemovePrecompactHook:
    def test_nonexistent_file_returns_false(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        assert remove_precompact_hook(path) is False
        assert not path.exists()

    def test_no_squadron_entry_returns_false_unchanged(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _save_settings(path, {"hooks": {"PreCompact": [_third_party_entry()]}})
        original = path.read_text()

        assert remove_precompact_hook(path) is False
        assert path.read_text() == original

    def test_only_squadron_entry_removes_key(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        write_precompact_hook(path)

        assert remove_precompact_hook(path) is True
        data = _read_json(path)
        # hooks.PreCompact should be gone; since hooks became empty, hooks too
        assert "hooks" not in data

    def test_squadron_plus_third_party_preserves_third_party(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "settings.json"
        _save_settings(path, {"hooks": {"PreCompact": [_third_party_entry()]}})
        write_precompact_hook(path)

        assert remove_precompact_hook(path) is True
        data = _read_json(path)
        precompact = data["hooks"]["PreCompact"]  # type: ignore[index]
        assert len(precompact) == 1
        assert precompact[0] == _third_party_entry()

    def test_preserves_unrelated_top_level_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _save_settings(path, {"theme": "dark"})
        write_precompact_hook(path)

        assert remove_precompact_hook(path) is True
        data = _read_json(path)
        assert data["theme"] == "dark"
        assert "hooks" not in data

    def test_preserves_other_hook_events_after_tidy(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        _save_settings(
            path,
            {"hooks": {"PostToolUse": [{"matcher": "", "hooks": []}]}},
        )
        write_precompact_hook(path)

        assert remove_precompact_hook(path) is True
        data = _read_json(path)
        # PostToolUse should still be there; PreCompact gone
        assert "hooks" in data
        assert "PostToolUse" in data["hooks"]  # type: ignore[operator]
        assert "PreCompact" not in data["hooks"]  # type: ignore[operator]
