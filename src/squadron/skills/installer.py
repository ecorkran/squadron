from __future__ import annotations

import logging
import shutil
from pathlib import Path

from squadron.skills.models import (
    InstallReceipt,
    InstallResult,
    PackEntry,
    SkillSourceError,
    SurfaceType,
)
from squadron.skills.receipts import DEFAULT_RECEIPTS_DIR, write_receipt
from squadron.skills.resolver import clone_github, resolve_source

logger = logging.getLogger(__name__)


def install_pack(
    pack_name: str,
    entry: PackEntry,
    commands_dir: Path,
    receipts_dir: Path | None = None,
) -> InstallResult:
    """Resolve source and copy .md files to the appropriate commands directory.

    For prefix entries: copies all *.md from source to commands_dir/<prefix>/.
    For dispatch_file entries: copies <dispatch_file>.md to commands_dir/sq/.

    After a successful copy, writes an install receipt to ``receipts_dir`` (the
    standard path when None). A receipt-write failure logs a WARNING but does not
    fail the install — the files are already in place.

    Raises SkillSourceError on bad source (propagated from resolver).
    """
    if entry.source.startswith("github:"):
        with clone_github(entry.source, pack_name) as tmp_dir:
            result = _install_from_path(pack_name, entry, commands_dir, Path(tmp_dir))
    else:
        source_path = resolve_source(entry, pack_name)
        result = _install_from_path(pack_name, entry, commands_dir, source_path)

    _write_install_receipt(entry, result, receipts_dir or DEFAULT_RECEIPTS_DIR)
    return result


def _write_install_receipt(entry: PackEntry, result: InstallResult, receipts_dir: Path) -> None:
    """Persist a receipt for a completed install; never raise (install succeeded)."""
    surface = SurfaceType.PREFIX if entry.prefix is not None else SurfaceType.DISPATCH_FILE
    receipt = InstallReceipt(
        pack_name=result.pack_name,
        surface=surface,
        destination=result.destination,
        files_written=result.files_written,
    )
    try:
        write_receipt(receipt, receipts_dir)
    except OSError:
        logger.warning(
            "Install of '%s' succeeded but receipt write to %s failed; "
            "uninstall will not be able to remove files automatically.",
            result.pack_name,
            receipts_dir,
            exc_info=True,
        )


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
