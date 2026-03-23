"""Smoke test — verifies the package is importable."""

from __future__ import annotations

import squadron


def test_package_importable() -> None:
    """The squadron package must be importable with a version string."""
    assert isinstance(squadron.__version__, str)
    assert len(squadron.__version__) > 0
