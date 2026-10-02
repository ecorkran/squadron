"""Codex runtime resolution — no SDK types, safe to import without the extra.

The single source of the Codex install hint. ``openai_codex`` and the
bundled-binary package ``codex_cli_bin`` are probed with ``find_spec`` only,
so this module (and everything that imports it) works on a default install.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import shutil
from dataclasses import dataclass
from enum import StrEnum

from squadron.providers.errors import ProviderError

CODEX_INSTALL_COMMAND = "pip install 'squadron-ai[codex]'"

_SDK_MODULE = "openai_codex"
_SDK_DISTRIBUTION = "openai-codex"
_BUNDLED_BIN_MODULE = "codex_cli_bin"
_PATH_BINARY = "codex"

CODEX_PACKAGE_MISSING_MESSAGE = (
    f"The Codex provider needs the codex extra. Install it with: {CODEX_INSTALL_COMMAND}"
)
CODEX_NO_BINARY_MESSAGE = (
    "Codex runtime binary not found: the bundled binary is missing and no "
    f"'codex' is on PATH. Reinstall the extra ({CODEX_INSTALL_COMMAND}) "
    "or put a Codex CLI on PATH."
)


class CodexExtraMissingError(ProviderError):
    """The ``openai_codex`` package is not installed (the ``codex`` extra is missing)."""


class RuntimeSource(StrEnum):
    """Where the Codex runtime binary comes from."""

    bundled = "bundled"
    path = "path"


@dataclass(frozen=True)
class CodexRuntime:
    """A resolved Codex runtime.

    ``path`` is ``None`` for the bundled binary: the SDK locates it itself
    when ``CodexConfig.codex_bin`` is ``None``.
    """

    source: RuntimeSource
    path: str | None
    package_version: str | None


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _sdk_version() -> str | None:
    try:
        return importlib.metadata.version(_SDK_DISTRIBUTION)
    except importlib.metadata.PackageNotFoundError:
        # Importable but without dist metadata (e.g. a source checkout):
        # the version is informational only, so report it as unknown.
        return None


def resolve_codex_runtime() -> CodexRuntime:
    """Resolve the Codex runtime: bundled binary first, then ``codex`` on PATH.

    Raises:
        CodexExtraMissingError: the SDK package is missing (message carries
            the install hint).
        ProviderError: no binary exists anywhere (names both remedies).
    """
    if not _module_available(_SDK_MODULE):
        raise CodexExtraMissingError(CODEX_PACKAGE_MISSING_MESSAGE)
    version = _sdk_version()
    if _module_available(_BUNDLED_BIN_MODULE):
        return CodexRuntime(source=RuntimeSource.bundled, path=None, package_version=version)
    path_binary = shutil.which(_PATH_BINARY)
    if path_binary is not None:
        return CodexRuntime(source=RuntimeSource.path, path=path_binary, package_version=version)
    raise ProviderError(CODEX_NO_BINARY_MESSAGE)
