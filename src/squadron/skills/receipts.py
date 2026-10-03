"""Install receipt persistence — write at install, read at uninstall.

A receipt records exactly which files an install wrote so uninstall can remove
them deterministically, without re-resolving (and re-cloning) the source.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import tomli_w
from rich import print as rprint

from squadron.skills.models import InstallReceipt


def default_receipts_dir() -> Path:
    """Return the user-level directory holding install receipts."""
    return Path.home() / ".config" / "squadron" / "receipts"


def write_receipt(receipt: InstallReceipt, receipts_dir: Path) -> None:
    """Serialize a receipt to ``receipts_dir/<pack_name>.toml`` (TOML).

    Creates ``receipts_dir`` if absent. Overwrites any existing receipt for the
    pack (reinstall is idempotent).
    """
    receipts_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "pack_name": receipt.pack_name,
        "destination": str(receipt.destination),
        "files_written": receipt.files_written,
    }
    # Omitted entirely when it does not apply (the bundled-commands installer). TOML has
    # no null, and writing str(None) would round-trip as the literal string "None" and
    # fail validation on read.
    if receipt.surface is not None:
        payload["surface"] = str(receipt.surface)
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


def remove_receipt_files(receipt: InstallReceipt) -> int:
    """Delete exactly the files ``receipt`` records and prune directories left empty.

    Entries resolving outside ``receipt.destination`` are skipped with a warning — a
    corrupted or hand-edited receipt must not delete anything squadron did not write.
    Directories are shared with the user's own files, so this never removes a tree:
    a directory goes only once it holds nothing, deepest first, so a skill's nested
    ``agents/`` is gone before its parent is tested. ``receipt.destination`` itself is
    never removed; a caller that owns it (a Claude prefix pack) removes it separately.

    Returns the number of files removed. A recorded file that is already gone is not
    an error — the desired end state, absent, already holds.
    """
    destination = receipt.destination
    resolved_destination = destination.resolve()
    removed = 0
    touched_dirs: set[Path] = set()
    for relative in receipt.files_written:
        path = destination / relative
        resolved_path = path.resolve()
        if resolved_path != resolved_destination and resolved_destination not in resolved_path.parents:
            rprint(
                f"[yellow]Skipping receipt entry outside the install destination: {relative!r}[/yellow]"
            )
            continue
        touched_dirs.add(path.parent)
        if path.exists():
            path.unlink()
            removed += 1

    for directory in sorted(touched_dirs, key=lambda p: len(p.parts), reverse=True):
        while (
            directory.is_dir()
            and directory != destination
            and destination in directory.parents
            and not any(directory.iterdir())
        ):
            directory.rmdir()
            directory = directory.parent
    return removed
