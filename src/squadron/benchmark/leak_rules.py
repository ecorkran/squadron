"""The facts a leak scan judges against, built once per replay (slice 424 D7).

``LeakRules`` holds only data. ``build_leak_rules`` runs no command: every fact (the user's
``HOME``, the ``uv cache dir`` output, the install location, ...) is a parameter, so tests
inject them and the caller owns how each is discovered.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_DISTRIBUTION_SEPARATORS = re.compile(r"[-_.]+")


def normalize_distribution(name: str) -> str:
    """The PEP 503 form of a distribution name: lower case, runs of ``-_.`` as ``-``."""
    return _DISTRIBUTION_SEPARATORS.sub("-", name).lower()


def path_forms(path: Path) -> tuple[Path, ...]:
    """A directory as written and as the filesystem resolves it (``/tmp`` vs ``/private/tmp``).

    Only roots are resolved, never the paths a model wrote: resolving those would follow a
    ``.venv`` symlink out of the sandbox and flag every run of the project's own interpreter.
    """
    lexical = Path(os.path.normpath(path.absolute()))
    resolved = path.resolve()
    return (lexical,) if resolved == lexical else (lexical, resolved)


@dataclass(frozen=True)
class LeakRules:
    #: The tree as written (relative paths resolve against it).
    tree: Path
    #: The tree in every form; what "inside the tree" means.
    tree_roots: tuple[Path, ...]
    #: The sandbox's own tree, home and output directory, in every form.
    sandbox_roots: tuple[Path, ...]
    #: The user's real HOME, checkout, harness install location and uv cache, in every form.
    protected_roots: tuple[Path, ...]
    real_home: Path
    #: PEP 503 normalized.
    distribution_name: str
    host_owner: str
    host_repo: str


def build_leak_rules(
    *,
    tree: Path,
    home: Path,
    output_dir: Path,
    real_home: Path,
    repo_root: Path,
    install_location: Path,
    uv_cache: Path,
    distribution_name: str,
    host_owner: str,
    host_repo: str,
) -> LeakRules:
    """The rules for one replay from facts the harness already holds."""
    sandbox = (tree, home, output_dir)
    protected = (real_home, repo_root, install_location, uv_cache)
    return LeakRules(
        tree=Path(os.path.normpath(tree.absolute())),
        tree_roots=path_forms(tree),
        sandbox_roots=tuple(form for path in sandbox for form in path_forms(path)),
        protected_roots=tuple(form for path in protected for form in path_forms(path)),
        real_home=Path(os.path.normpath(real_home.absolute())),
        distribution_name=normalize_distribution(distribution_name),
        host_owner=host_owner,
        host_repo=host_repo,
    )
