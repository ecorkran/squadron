"""Package data directory locator.

Provides ``data_dir()`` — the single source of truth for where shipped
default data files (models.toml, templates/, pipelines/) are located at
runtime.  Works in both wheel installs and editable installs.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path


def data_dir() -> Path:
    """Return the path to the squadron/data package directory.

    Resolution order:
    1. ``importlib.resources.files("squadron") / "data"`` — works in wheel
       installs where package data is bundled inside the wheel.
    2. ``Path(__file__).parent`` — works in editable installs because this
       ``__init__.py`` lives inside ``src/squadron/data/``.
    """
    try:
        candidate = Path(importlib.resources.files("squadron") / "data")  # type: ignore[arg-type]
        if candidate.is_dir():
            return candidate
    except (TypeError, AttributeError):
        pass

    return Path(__file__).parent
