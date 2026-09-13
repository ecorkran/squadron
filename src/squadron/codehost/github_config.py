"""Reading ``gh``'s own configuration.

Pure filesystem reads — no subprocess. The adapter learns which hosts the
operator has authenticated against by reading the top-level keys of ``gh``'s
hosts file, which is cheap and answerable offline.

Absence is a normal state, not an error: an operator who has never run
``gh auth login`` has no hosts file, and squadron still installs and runs. Auth
failures are reported at invocation by the adapter, not predicted here.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import cast

import yaml

_logger = logging.getLogger(__name__)

#: Where ``gh`` keeps its hosts file when ``GH_CONFIG_DIR`` is unset.
_DEFAULT_GH_CONFIG_DIR = Path.home() / ".config" / "gh"

#: The file within that directory listing authenticated hosts as top-level keys.
_HOSTS_FILENAME = "hosts.yml"


def gh_hosts_file_path() -> Path:
    """Return the path to ``gh``'s hosts file.

    Honors ``GH_CONFIG_DIR`` so a test — or an operator with a relocated
    config — resolves somewhere other than the real home directory.
    """
    config_dir = os.environ.get("GH_CONFIG_DIR")
    base = Path(config_dir) if config_dir else _DEFAULT_GH_CONFIG_DIR
    return base / _HOSTS_FILENAME


def read_gh_hosts() -> set[str]:
    """Return the hostnames ``gh`` has credentials for.

    Yields an empty set — never raises — when the file is missing, unreadable,
    or not the mapping it is expected to be. Each of those is logged at DEBUG
    rather than WARNING: none is a fault, and the doctor check reports presence
    separately for the operator's benefit.
    """
    path = gh_hosts_file_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _logger.debug("gh hosts file not present at %s", path)
        return set()
    except OSError:
        # Unreadable for any other reason (permissions, a directory in its
        # place). Still not a squadron fault; doctor reports readability.
        _logger.debug("gh hosts file at %s could not be read", path, exc_info=True)
        return set()

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        _logger.debug("gh hosts file at %s is not valid YAML", path, exc_info=True)
        return set()

    if not isinstance(parsed, dict):
        _logger.debug("gh hosts file at %s is not a mapping", path)
        return set()

    # safe_load returns Any, so the parsed mapping's keys stay Unknown to the
    # type checker even after the isinstance narrowing above. Cast once here.
    hosts = cast(dict[object, object], parsed)
    return {str(key) for key in hosts}
