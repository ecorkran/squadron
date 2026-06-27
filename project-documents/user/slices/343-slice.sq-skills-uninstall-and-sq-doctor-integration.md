---
docType: slice-design
slice: sq-skills-uninstall-and-sq-doctor-integration
project: squadron
parent: 340-slices.skill-pack-infrastructure.md
initiative: 340
index: 343
dependencies: [342]
interfaces: [344]
dateCreated: 20260626
dateUpdated: 20260626
status: design
---

# Slice Design: `sq skills uninstall` and `sq doctor` Integration

## Overview

This slice completes the `sq skills` surface with `uninstall <pack>` and adds a "Skill Packs" section to `sq doctor`. `uninstall` removes exactly the files that `install` wrote by consulting an install receipt written at install time. `sq doctor` reports installed/missing status for every pack declared in the effective manifest and provides per-missing-pack fix hints.

## Value

Users can cleanly remove packs without manually hunting for installed files, and `sq doctor` gives a complete picture of the installed skill set alongside provider and integration status. Together these close the operational lifecycle: install → use → inspect → uninstall.

## Technical Scope

### In scope
- Install receipt file written by `installer.py` after a successful install
- `sq skills uninstall <pack>` command in `skills.py`
- `check_skill_packs()` check function added to `doctor_checks.py`
- `SECTION_SKILLS` added to the doctor section order in `doctor.py`
- Tests for uninstall command and the new doctor check

### Out of scope
- Orphan detection (packs installed but absent from any manifest) — see **Decision: No Orphan Detection** below
- `sq skills update` — deferred to future work
- Any changes to install logic beyond writing the receipt

## Dependencies

- [342] — the `analysis` pack is the concrete reference for install/uninstall round-trip testing; the `load_effective()` shipped-default path must work

## Architecture

### Install Receipt

The installer currently returns an `InstallResult` that the CLI prints and discards. To support uninstall without re-resolving the source (especially problematic for `github:` sources), the installer persists a receipt file immediately after a successful install.

**Location:** `~/.config/squadron/receipts/<pack_name>.toml`

**Content (TOML):**
```toml
pack_name = "analysis"
surface = "prefix"        # "prefix" | "dispatch_file"
destination = "/Users/you/.claude/commands/analysis"
files_written = ["tech-debt-audit.md"]
```

The receipt directory (`~/.config/squadron/receipts/`) is created on first write. The receipt is overwritten on reinstall (idempotent). The receipt is deleted on successful uninstall.

### New Model: `InstallReceipt`

Added to `src/squadron/skills/models.py`:

```python
class InstallReceipt(BaseModel):
    pack_name: str
    surface: str          # "prefix" or "dispatch_file"
    destination: Path
    files_written: list[str]
```

Two helper functions added alongside the model (or in a new `src/squadron/skills/receipts.py`):
- `write_receipt(receipt: InstallReceipt, receipts_dir: Path) -> None`
- `read_receipt(pack_name: str, receipts_dir: Path) -> InstallReceipt | None`

`receipts_dir` defaults to `Path.home() / ".config" / "squadron" / "receipts"` and is injected for testability.

### Modified: `installer.py`

`install_pack()` gains an optional `receipts_dir: Path | None = None` parameter (defaults to the standard path). After the file-copy step completes, it writes the receipt. Failure to write the receipt logs a WARNING but does not fail the install — the install itself succeeded.

```
install_pack(pack_name, entry, commands_dir, receipts_dir=None)
  → ... (existing copy logic) ...
  → write_receipt(InstallReceipt(...), receipts_dir or DEFAULT_RECEIPTS_DIR)
  → return InstallResult(...)
```

### New Command: `sq skills uninstall`

Added to `src/squadron/cli/commands/skills.py`:

```
sq skills uninstall <pack_name> [--commands-dir <path>] [--receipts-dir <path>]
```

**Logic:**
1. Read receipt from `receipts_dir / f"{pack_name}.toml"`. If absent: print error and exit(1).
2. For each filename in `receipt.files_written`:
   - `dest_file = Path(receipt.destination) / filename`
   - Remove if it exists; if already gone, continue silently.
3. If surface is `"prefix"` and `Path(receipt.destination)` is now empty: remove the directory.
4. Delete the receipt file.
5. Print: `Uninstalled pack '<pack_name>': <n> file(s) removed from <destination>`.

**Error cases:**
- No receipt: `Pack '<pack_name>' is not installed (no receipt found). Use 'sq skills list' to check status.`
- Receipt exists but destination files already gone: complete normally, count removed = 0, print info message rather than error.

The `--receipts-dir` option exists for testability; it defaults to the same constant as `install_pack`.

### Modified: `doctor_checks.py`

New constant added:
```python
SECTION_SKILLS = "Skill Packs"
```

New check function:
```python
def check_skill_packs(
    commands_dir: Path | None = None,
    cwd: Path | None = None,
) -> list[CheckResult]:
```

**Logic:**
1. `manifest = load_effective(cwd=cwd or Path.cwd())` — load the effective manifest (shipped default + user + project).
2. If `manifest is None`: return a single `CheckResult(name="skills.toml", status=OK, detail="no manifest found; using defaults", section=SECTION_SKILLS, required=False)`.
3. For each `(name, entry)` in `manifest.packs`:
   - Determine install presence using the same logic as `sq skills list`:
     - prefix pack: `(commands_dir / entry.prefix).exists() and any((commands_dir / entry.prefix).iterdir())`
     - dispatch_file pack: `(commands_dir / "sq" / f"{entry.dispatch_file}.md").exists()`
   - `installed` → `CheckStatus.OK`, detail `"installed at <path>"`
   - `not installed` → `CheckStatus.WARN`, detail `"not installed"`, fix_hint `"sq skills install <name>"`
4. Return the list sorted by pack name.

`check_skill_packs` is a pure, testable function — no subprocess, no network, filesystem reads only.

### Modified: `doctor.py`

`SECTION_SKILLS` added to `_SECTION_ORDER` after `SECTION_INTEGRATIONS`:

```python
_SECTION_ORDER = [SECTION_INSTALL, SECTION_PROVIDERS, SECTION_INTEGRATIONS, SECTION_SKILLS, SECTION_CONFIG]
```

`run_all_checks()` in `doctor_checks.py` gains a call:
```python
_run("skill packs", check_skill_packs)
```

## Technical Decisions

### Decision: Receipt file over source re-resolution

**Alternative:** On uninstall, re-resolve the pack source to derive what files *would* have been installed, then remove those. Works for `bundled` and local paths; fails for `github:` sources without re-cloning. Even for stable sources, re-resolution couples uninstall to source availability — if the bundled source ever changes (new skills added), uninstall would remove more files than install wrote.

**Chosen:** Receipt file at `~/.config/squadron/receipts/<pack>.toml`. Written by the installer; read by uninstall. Correct for all source types. Deterministic regardless of source availability at uninstall time. The receipt is a small TOML file; cost is negligible.

### Decision: No orphan detection

Orphan detection would mean: scan `~/.claude/commands/` for directories not declared in any manifest entry and warn. This adds complexity (directory scanning, heuristics for what counts as a squadron-managed directory) for limited value — the analysis pack is always in the shipped default manifest, so it can never become an orphan through normal use. Deferred indefinitely; the design does not block adding it later.

### Decision: Warn (not Missing) for uninstalled packs in `sq doctor`

Skill packs are optional; no pack is required for squadron to function. An uninstalled pack declared in the manifest is informational, not a blocking problem. `CheckStatus.WARN` (which shows only with `-v` unless the user looks carefully) would hide it — but actually re-reading `doctor.py:51`, WARN rows are suppressed unless verbose. Since "not installed" is notable and actionable (fix hint provided), using `CheckStatus.WARN` is appropriate: visible with `-v`, suppressed in the non-verbose summary count as "warnings", and the fix hint is shown when visible. This matches the pattern for `check_slash_commands` (WARN when not installed).

### Decision: `receipts_dir` injected, not hardcoded in business logic

Both `installer.py` and the new uninstall command accept `receipts_dir` as an optional parameter defaulting to the standard path. This follows the same pattern as `commands_dir` in the existing install/list commands and makes the receipt path fully testable without filesystem mocking.

## Component Interactions

```
sq skills install analysis
  → installer.py: install_pack() → copy files → write_receipt() → ~/.config/squadron/receipts/analysis.toml
  → skills.py: prints success

sq skills uninstall analysis
  → skills.py: uninstall()
      → read_receipt("analysis") → InstallReceipt
      → remove files listed in receipt.files_written from receipt.destination
      → delete receipt file
      → print summary

sq doctor
  → doctor_checks.py: run_all_checks()
      → check_skill_packs()
          → manifest.load_effective()
          → per-pack: check presence in commands_dir
          → return list[CheckResult] for SECTION_SKILLS
  → doctor.py: _render_table() — renders Skill Packs section
```

## Integration Points

### Receives from slice 342
- `load_effective()` already loads shipped default; `analysis` pack always visible in manifest
- `commands/analysis/` bundled in wheel; `sq skills install analysis` installs it

### Provides to slice 344
- `sq skills uninstall analysis` enables clean round-trip tests for the expanded analysis pack
- `sq doctor` Skill Packs section reports pack presence; slice 344 adds another pack and benefits from doctor coverage automatically

## Success Criteria

1. `sq skills uninstall analysis` removes only `tech-debt-audit.md` from `~/.claude/commands/analysis/`; leaves any other files in that directory untouched.
2. Uninstalling a pack not installed prints a clear error and exits non-zero; no traceback.
3. After uninstall, `sq skills install analysis` reinstalls cleanly (idempotent round-trip).
4. `sq doctor` output includes a "Skill Packs" section with one row per manifest pack showing installed/not-installed status.
5. Each not-installed row shows `fix: sq skills install <pack_name>` as the fix hint.
6. `sq doctor --json` output includes skill pack check results in the `checks` array.
7. All new code passes `pyright` strict and `ruff` lint/format; existing tests remain green.

## Verification Walkthrough

**Prereq:** squadron dev install (`uv pip install -e .`); `sq skills install analysis` already run (so receipt exists).

**1. Inspect receipt after install**
```bash
cat ~/.config/squadron/receipts/analysis.toml
```
Expected:
```toml
pack_name = "analysis"
surface = "prefix"
destination = "/Users/<you>/.claude/commands/analysis"
files_written = ["tech-debt-audit.md"]
```

**2. Doctor shows analysis as installed**
```bash
sq doctor -v
```
Expected in output (within "Skill Packs" section):
```
Skill Packs
  ✓ analysis                   installed at ~/.claude/commands/analysis
```

**3. Uninstall the analysis pack**
```bash
sq skills uninstall analysis
# Uninstalled pack 'analysis': 1 file(s) removed from /Users/<you>/.claude/commands/analysis
ls ~/.claude/commands/analysis/
# (empty or directory gone)
ls ~/.config/squadron/receipts/
# (analysis.toml gone)
```

**4. Doctor shows analysis as not installed**
```bash
sq doctor -v
```
Expected:
```
Skill Packs
  ! analysis                   not installed
    fix: sq skills install analysis
```

**5. Uninstall when not installed — graceful failure**
```bash
sq skills uninstall analysis
# Pack 'analysis' is not installed (no receipt found). Use 'sq skills list' to check status.
# exit code 1
```

**6. Reinstall is clean**
```bash
sq skills install analysis
# Installed pack 'analysis': 1 file(s) → /Users/<you>/.claude/commands/analysis
sq doctor -v
# Skill Packs: ✓ analysis  installed at ~/.claude/commands/analysis
```

**7. Unrelated file is not removed**
```bash
# Place a non-pack file in the prefix directory
echo "custom" > ~/.claude/commands/analysis/my-custom-skill.md
sq skills install analysis
sq skills uninstall analysis
ls ~/.claude/commands/analysis/
# my-custom-skill.md  ← preserved; only tech-debt-audit.md was removed
```

**8. JSON output**
```bash
sq doctor --json | python3 -m json.tool | grep -A 5 '"section": "Skill Packs"'
```
Expected: one or more check objects with `"section": "Skill Packs"` and `"status": "ok"` or `"warn"`.

## Implementation Notes

### Development Order
1. Add `InstallReceipt` model to `models.py`; add `write_receipt` / `read_receipt` helpers
2. Extend `installer.py` to write receipt; update `install_pack` signature; update tests
3. Add `uninstall` command to `skills.py`; add tests
4. Add `SECTION_SKILLS` and `check_skill_packs()` to `doctor_checks.py`; update `_SECTION_ORDER` in `doctor.py`; add tests
5. End-to-end walkthrough per above

### Testing
- Unit: `write_receipt` / `read_receipt` round-trip with a temp directory
- Unit: `install_pack` writes receipt at the expected path after successful install
- Unit: `uninstall` removes declared files, leaves undeclared files, removes receipt
- Unit: `uninstall` with no receipt raises a clean error (exit code 1)
- Unit: `check_skill_packs()` with installed pack → OK row; with not-installed pack → WARN row with fix_hint
- Unit: `check_skill_packs()` with `manifest=None` → single OK row describing "no manifest"
- Integration: `doctor` output includes "Skill Packs" section header and one row per manifest pack
