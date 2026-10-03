from __future__ import annotations

import logging
from pathlib import Path

from squadron.skills.models import (
    InstallReceipt,
    InstallResult,
    PackEntry,
    SurfaceType,
)
from squadron.skills.pack_layouts import PACK_LAYOUTS
from squadron.skills.receipts import default_receipts_dir, write_receipt
from squadron.skills.resolver import clone_github, resolve_source
from squadron.skills.targets import CommandTarget, receipt_name

logger = logging.getLogger(__name__)


def install_pack(
    pack_name: str,
    entry: PackEntry,
    commands_dir: Path,
    receipts_dir: Path | None = None,
    target: CommandTarget = CommandTarget.CLAUDE,
    *,
    local: bool = False,
) -> InstallResult:
    """Resolve the pack's source and install it in ``target``'s layout under ``commands_dir``.

    The layout is ``PACK_LAYOUTS[target]``: Claude copies flat markdown into
    ``<prefix>/`` or ``sq/``; agents copies the source's ``agents/`` skill
    directories after validating them.

    After a successful copy, writes an install receipt named
    ``receipt_name(pack_name, target, local=local)`` to ``receipts_dir`` (the
    standard path when None). ``local`` only names the receipt; ``commands_dir``
    is already the resolved destination. A receipt-write failure logs a WARNING
    but does not fail the install — the files are already in place.

    Raises SkillSourceError on bad source (propagated from resolver or layout).
    """
    layout = PACK_LAYOUTS[target]
    if entry.source.startswith("github:"):
        with clone_github(entry.source, pack_name) as tmp_dir:
            result = layout.install(pack_name, entry, Path(tmp_dir), commands_dir)
    else:
        source_path = resolve_source(entry, pack_name)
        result = layout.install(pack_name, entry, source_path, commands_dir)

    receipt_key = receipt_name(pack_name, target, local=local)
    _write_install_receipt(receipt_key, entry, result, receipts_dir or default_receipts_dir())
    return result


def _write_install_receipt(
    receipt_key: str, entry: PackEntry, result: InstallResult, receipts_dir: Path
) -> None:
    """Persist a receipt for a completed install; never raise (install succeeded)."""
    surface = SurfaceType.PREFIX if entry.prefix is not None else SurfaceType.DISPATCH_FILE
    receipt = InstallReceipt(
        pack_name=receipt_key,
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
