from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from squadron.skills.models import InstallResult, PackEntry, SkillSourceError
from squadron.skills.resolver import resolve_source


def install_pack(pack_name: str, entry: PackEntry, commands_dir: Path) -> InstallResult:
    """Resolve source and copy .md files to the appropriate commands directory.

    For prefix entries: copies all *.md from source to commands_dir/<prefix>/.
    For dispatch_file entries: copies <dispatch_file>.md to commands_dir/sq/.

    Raises SkillSourceError on bad source (propagated from resolver).
    """
    is_github = entry.source.startswith("github:")

    if is_github:
        return _install_with_temp_dir(pack_name, entry, commands_dir)
    return _install_from_path(pack_name, entry, commands_dir, resolve_source(entry, pack_name))


def _install_with_temp_dir(pack_name: str, entry: PackEntry, commands_dir: Path) -> InstallResult:
    tmp = tempfile.mkdtemp(prefix="squadron-skills-install-")
    try:
        # Temporarily patch the already-cloned path from resolver
        source_path = resolve_source(entry, pack_name)
        return _install_from_path(pack_name, entry, commands_dir, source_path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _install_from_path(
    pack_name: str, entry: PackEntry, commands_dir: Path, source_path: Path
) -> InstallResult:
    if entry.prefix is not None:
        return _install_prefix(pack_name, entry.prefix, source_path, commands_dir)
    if entry.dispatch_file is not None:
        return _install_dispatch(pack_name, entry.dispatch_file, source_path, commands_dir)
    # PackEntry validator guarantees exactly one — this is unreachable
    raise SkillSourceError(f"Pack '{pack_name}' has neither prefix nor dispatch_file.")


def _install_prefix(
    pack_name: str, prefix: str, source_path: Path, commands_dir: Path
) -> InstallResult:
    dest = commands_dir / prefix
    dest.mkdir(parents=True, exist_ok=True)

    files_written: list[str] = []
    for md_file in sorted(source_path.glob("*.md")):
        shutil.copy2(md_file, dest / md_file.name)
        files_written.append(md_file.name)

    return InstallResult(pack_name=pack_name, files_written=files_written, destination=dest)


def _install_dispatch(
    pack_name: str, dispatch_file: str, source_path: Path, commands_dir: Path
) -> InstallResult:
    src_file = source_path / f"{dispatch_file}.md"
    if not src_file.exists():
        raise SkillSourceError(
            f"dispatch_file '{dispatch_file}.md' not found in source for pack '{pack_name}'."
        )

    dest_dir = commands_dir / "sq"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / f"{dispatch_file}.md"
    shutil.copy2(src_file, dest_file)

    return InstallResult(
        pack_name=pack_name,
        files_written=[f"{dispatch_file}.md"],
        destination=dest_dir,
    )
