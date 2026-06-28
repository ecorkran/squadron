"""Install receipt persistence — write at install, read at uninstall.

A receipt records exactly which files an install wrote so uninstall can remove
them deterministically, without re-resolving (and re-cloning) the source.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomli_w

from squadron.skills.models import InstallReceipt

DEFAULT_RECEIPTS_DIR: Path = Path.home() / ".config" / "squadron" / "receipts"


def write_receipt(receipt: InstallReceipt, receipts_dir: Path) -> None:
    """Serialize a receipt to ``receipts_dir/<pack_name>.toml`` (TOML).

    Creates ``receipts_dir`` if absent. Overwrites any existing receipt for the
    pack (reinstall is idempotent).
    """
    receipts_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "pack_name": receipt.pack_name,
        "surface": str(receipt.surface),
        "destination": str(receipt.destination),
        "files_written": receipt.files_written,
    }
    target = receipts_dir / f"{receipt.pack_name}.toml"
    with open(target, "wb") as fh:
        tomli_w.dump(payload, fh)


def read_receipt(pack_name: str, receipts_dir: Path) -> InstallReceipt | None:
    """Read and validate the receipt for ``pack_name``.

    Returns ``None`` if no receipt file exists. Raises ``ValueError`` (with the
    offending path in the message) if the file exists but is malformed.
    """
    path = receipts_dir / f"{pack_name}.toml"
    if not path.exists():
        return None

    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
        return InstallReceipt.model_validate(data)
    except (tomllib.TOMLDecodeError, ValueError) as exc:
        raise ValueError(f"Malformed install receipt at {path}: {exc}") from exc
