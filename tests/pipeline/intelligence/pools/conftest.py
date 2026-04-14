"""Shared fixtures for pool infrastructure tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.models.aliases import ModelAlias


@pytest.fixture
def sample_aliases() -> dict[str, ModelAlias]:
    """Return a representative alias dict covering the built-in pool members.

    Tiers used: free, cheap, moderate, expensive — with pricing set so
    cheapest-strategy tests can verify tie-breaking.
    """
    return {
        "minimax": ModelAlias(
            profile="openrouter",
            model="minimax/minimax-m2.7",
            cost_tier="cheap",
            pricing={"input": 0.30, "output": 1.25},
        ),
        "glm5": ModelAlias(
            profile="openrouter",
            model="z-ai/glm-5",
            cost_tier="cheap",
            pricing={"input": 0.72, "output": 2.30},
        ),
        "kimi25": ModelAlias(
            profile="openrouter",
            model="moonshotai/kimi-k2.5",
            cost_tier="cheap",
            pricing={"input": 0.45, "output": 2.83},
        ),
        "grok-fast": ModelAlias(
            profile="openrouter",
            model="x-ai/grok-4.1-fast",
            cost_tier="cheap",
            pricing={"input": 0.20, "output": 0.50},
        ),
        "opus": ModelAlias(
            profile="sdk",
            model="claude-opus-4-6",
            cost_tier="subscription",
        ),
        "gpt54": ModelAlias(
            profile="openai",
            model="gpt-5.4",
            cost_tier="expensive",
            pricing={"input": 2.50, "output": 15.00},
        ),
        "gemini": ModelAlias(
            profile="gemini",
            model="gemini-3.1-pro-preview-customtools",
            cost_tier="expensive",
            pricing={"input": 2.00, "output": 12.00},
        ),
        "flash3": ModelAlias(
            profile="gemini",
            model="gemini-3-flash-preview",
            cost_tier="cheap",
            pricing={"input": 0.50, "output": 3.00},
        ),
        "gemma4": ModelAlias(
            profile="openrouter",
            model="google/gemma-4-31b-it",
            cost_tier="cheap",
            pricing={"input": 0.14, "output": 0.40},
        ),
        "qwen36-free": ModelAlias(
            profile="openrouter",
            model="qwen/qwen3.6-plus:free",
            cost_tier="free",
            pricing={"input": 0.00, "output": 0.00},
        ),
    }


@pytest.fixture
def builtin_pools_toml() -> str:
    """Return the text of the shipped src/squadron/data/pools.toml."""
    from squadron.data import data_dir

    return (data_dir() / "pools.toml").read_text()


@pytest.fixture
def tmp_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate pool-state.toml writes to a temporary directory.

    Monkeypatches the config dir used by the state persistence functions
    so tests do not touch ~/.config/squadron/.
    """
    config_dir = tmp_path / "squadron"
    config_dir.mkdir()

    import squadron.pipeline.intelligence.pools.loader as loader_mod

    monkeypatch.setattr(loader_mod, "_config_dir", lambda: config_dir)
    return config_dir / "pool-state.toml"
