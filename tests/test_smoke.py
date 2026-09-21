"""Smoke test — verifies the package is importable."""

from __future__ import annotations

import importlib.metadata

from packaging.requirements import Requirement

import squadron


def test_package_importable() -> None:
    """The squadron package must be importable with a version string."""
    assert isinstance(squadron.__version__, str)
    assert len(squadron.__version__) > 0


def _declared_dependency_names() -> set[str]:
    """The base (non-extra) runtime dependency names declared for squadron-ai.

    Reads the installed distribution's own metadata via importlib.metadata,
    as tests/cli/test_version.py:17 does for the version, rather than
    hand-parsing pyproject.toml — this is what a real install actually
    resolved against, not just what the source file says.

    Each requirement string is parsed with packaging.requirements.Requirement
    (review 922, F004) rather than a hand-rolled regex and substring check —
    that parses the semantic content (name, marker) regardless of formatting,
    where a substring check on "extra ==" would silently pass unusual marker
    spacing through as a base dependency.
    """
    requires = importlib.metadata.requires("squadron-ai") or []
    names: set[str] = set()
    for requirement in requires:
        parsed = Requirement(requirement)
        if parsed.marker is not None:
            continue  # skip optional-extra deps (e.g. the dev group)
        names.add(parsed.name.lower())
    return names


def test_declared_dependencies_match_what_src_imports() -> None:
    """#65 (findings 2-3): anthropic and google-adk are unimported and must
    not be declared; rich is imported in 21 files under src/ and must be;
    mcp is imported by tools/mcp_bridge.py and tools/cf_tools.py and stays."""
    declared = _declared_dependency_names()
    assert "rich" in declared
    assert "mcp" in declared
    assert "anthropic" not in declared
    assert "google-adk" not in declared
