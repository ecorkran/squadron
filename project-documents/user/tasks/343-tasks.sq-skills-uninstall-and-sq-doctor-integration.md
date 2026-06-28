---
docType: tasks
slice: sq-skills-uninstall-and-sq-doctor-integration
project: squadron
lld: user/slices/343-slice.sq-skills-uninstall-and-sq-doctor-integration.md
dependencies: [342]
projectState: Slice 342 complete. Analysis pack bundled and installable. skills subpackage (models, manifest, resolver, installer, CLI) fully functional. No install receipt written yet; no uninstall command; sq doctor has no Skill Packs section.
dateCreated: 20260626
dateUpdated: 20260626
status: not_started
---

## Context Summary

- Working on slice 343: `sq skills uninstall` and `sq doctor` integration
- Adds an install receipt written by `installer.py` after every successful install; `uninstall` reads the receipt to remove exactly the files that were written
- Adds `sq skills uninstall <pack>` subcommand to `skills.py`
- Adds `SECTION_SKILLS` and `check_skill_packs()` to `doctor_checks.py`; wires into `doctor.py`'s section order and `run_all_checks()`
- No new external dependencies; all I/O is local filesystem
- See LLD for full design including receipt format, error cases, and `sq doctor` behavior
- Next planned slice: 344 (add `understand-anything` to analysis pack)

---

## Tasks

- [ ] **T1: Create branch and verify prereqs**
  - [ ] Verify on branch `343-slice.sq-skills-uninstall-and-sq-doctor-integration` (create from `main` if absent)
  - [ ] Run `pytest tests/skills/ tests/cli/` — all pass (confirms slice 342 foundation is intact)
  - [ ] Run `sq skills install analysis` — verify receipt directory does not yet exist at `~/.config/squadron/receipts/`
  - [ ] Success: branch exists; all 342 tests pass; no receipt directory present

- [ ] **T2: Add `InstallReceipt` model to `models.py`**
  - [ ] In `src/squadron/skills/models.py`, add a Pydantic `InstallReceipt` model with fields: `pack_name: str`, `surface: str` ("prefix" or "dispatch_file"), `destination: Path`, `files_written: list[str]`
  - [ ] Add a `SurfaceType` `StrEnum` with values `PREFIX = "prefix"` and `DISPATCH_FILE = "dispatch_file"` to type the `surface` field (keeps magic strings out of callers)
  - [ ] Success: `python -c "from squadron.skills.models import InstallReceipt, SurfaceType; print(SurfaceType.PREFIX)"` prints `prefix` without error

- [ ] **T3: Tests for `InstallReceipt` model**
  - [ ] In `tests/skills/test_models.py`, add tests for `InstallReceipt`:
    - Valid construction with `surface=SurfaceType.PREFIX` and a list of filenames
    - Valid construction with `surface=SurfaceType.DISPATCH_FILE`
    - `destination` field accepts a `Path`; round-trips correctly via `.model_dump()` / `.model_validate()`
  - [ ] Run `pytest tests/skills/test_models.py` — all pass
  - [ ] Success: all model tests pass; no regressions

- [ ] **T4: Create `receipts.py` with `write_receipt` / `read_receipt`**
  - [ ] Create `src/squadron/skills/receipts.py`
  - [ ] Define `DEFAULT_RECEIPTS_DIR: Path = Path.home() / ".config" / "squadron" / "receipts"` as a module-level constant
  - [ ] Implement `write_receipt(receipt: InstallReceipt, receipts_dir: Path) -> None`: serialize the receipt to TOML (use `tomli-w` if available, or build a minimal TOML string manually for this simple flat structure); write to `receipts_dir / f"{receipt.pack_name}.toml"`; create `receipts_dir` if absent (`mkdir(parents=True, exist_ok=True)`)
  - [ ] Implement `read_receipt(pack_name: str, receipts_dir: Path) -> InstallReceipt | None`: read `receipts_dir / f"{pack_name}.toml"` with `tomllib`; return `InstallReceipt` if file exists and is valid; return `None` if file is absent; raise `ValueError` with path context on malformed TOML
  - [ ] Check `pyproject.toml` for `tomli-w`; if absent, use manual TOML serialization (a flat key=value block is trivial for these fields) — do not add a new dependency without Project Manager approval
  - [ ] If using manual TOML, all string values (`pack_name`, `surface`, `destination`) must be TOML-quoted: e.g. `destination = "{path}"`, not `destination = {path}`. Cast `destination` to `str` before quoting. The list field must use TOML array syntax with quoted elements: `files_written = ["a.md", "b.md"]`
  - [ ] Success: module imports cleanly; both functions are importable from `squadron.skills.receipts`

- [ ] **T5: Tests for `receipts.py`**
  - [ ] In `tests/skills/`, add `test_receipts.py`
  - [ ] Test `write_receipt` / `read_receipt` round-trip: write a receipt for an analysis-like pack, read it back, assert all fields match (use `tmp_path` fixture)
  - [ ] Test `read_receipt` returns `None` when receipt file does not exist
  - [ ] Test `write_receipt` creates the `receipts_dir` if it does not exist
  - [ ] Test `read_receipt` raises `ValueError` on malformed TOML
  - [ ] Run `pytest tests/skills/test_receipts.py` — all pass
  - [ ] Success: all receipt helper tests pass

- [ ] **T6: Extend `installer.py` to write receipt after install**
  - [ ] In `src/squadron/skills/installer.py`, import `write_receipt`, `DEFAULT_RECEIPTS_DIR`, `InstallReceipt`, `SurfaceType` from `receipts.py` / `models.py`
  - [ ] Add `receipts_dir: Path | None = None` parameter to `install_pack()`; default to `DEFAULT_RECEIPTS_DIR` if `None`
  - [ ] After a successful install (after `_install_from_path` returns `InstallResult`), build an `InstallReceipt` from the result and call `write_receipt()`; wrap in `try/except` — on failure, log `WARNING` but do not re-raise (install itself succeeded)
  - [ ] Determine `surface` from `entry`: `SurfaceType.PREFIX` if `entry.prefix is not None`, else `SurfaceType.DISPATCH_FILE`
  - [ ] Success: `install_pack()` signature updated; receipt is written to `receipts_dir` after any successful install

- [ ] **T7: Tests for receipt writing in `installer.py`**
  - [ ] In `tests/skills/test_installer.py`, add tests:
    - After a successful `install_pack()` call (prefix case), `receipts_dir / "analysis.toml"` exists and `read_receipt()` returns correct fields
    - After a successful `install_pack()` call (dispatch_file case), receipt surface is `"dispatch_file"`
    - If `write_receipt` raises (monkeypatch it), `install_pack()` still returns normally and does not raise
  - [ ] Run `pytest tests/skills/test_installer.py` — all pass, including pre-existing tests
  - [ ] Success: receipt-writing tests pass; no regressions in installer tests

- [ ] **T8: Commit checkpoint — receipt infrastructure**
  - [ ] Run `ruff format src/squadron/skills/ tests/skills/` — no changes
  - [ ] Run `ruff check src/squadron/skills/ tests/skills/` — 0 errors
  - [ ] Run `pyright --strict` — 0 errors
  - [ ] Run `pytest tests/skills/` — all pass
  - [ ] `git add src/squadron/skills/models.py src/squadron/skills/receipts.py src/squadron/skills/installer.py tests/skills/`
  - [ ] Commit: `feat(skills): add install receipt written by installer`

- [ ] **T9: Add `uninstall` subcommand to `skills.py`**
  - [ ] In `src/squadron/cli/commands/skills.py`, import `read_receipt` and `DEFAULT_RECEIPTS_DIR` from `squadron.skills.receipts`
  - [ ] Add `@skills_app.command()` function `uninstall(pack_name: str, commands_dir: Path = ..., receipts_dir: Path = ...)` with `--commands-dir` and `--receipts-dir` options (defaults to `_DEFAULT_COMMANDS_DIR` and `DEFAULT_RECEIPTS_DIR` respectively)
  - [ ] Logic: (1) call `read_receipt(pack_name, receipts_dir)` — if `None`, print error and `raise typer.Exit(code=1)`; (2) iterate `receipt.files_written`, remove `Path(receipt.destination) / filename` if it exists; (3) if surface is `"prefix"` and destination directory is now empty, remove it; (4) delete receipt file; (5) print success with count removed
  - [ ] Error message when no receipt: `Pack '<pack_name>' is not installed (no receipt found). Use 'sq skills list' to check status.`
  - [ ] Success message: `Uninstalled pack '<pack_name>': <n> file(s) removed from <destination>`
  - [ ] Also update the `install` CLI command to accept `--receipts-dir` option and pass it through to `install_pack()` (enables integration test coverage without touching the real receipts directory)
  - [ ] Success: `sq skills uninstall --help` exits 0 and shows usage

- [ ] **T10: Tests for `uninstall` command**
  - [ ] In `tests/skills/test_cli_skills.py` (or a new `tests/cli/commands/test_skills_uninstall.py`), add tests using Typer's `CliRunner`:
    - Install then uninstall (round-trip): install pack into `tmp_path`, then uninstall using `--commands-dir tmp_path --receipts-dir tmp_receipts`; assert installed files removed, receipt deleted
    - Unrelated file not removed: place an extra `.md` file in the prefix directory before install; after uninstall, assert the extra file is still present
    - Uninstall when no receipt: assert exit code 1 and error message contains "not installed"
    - Uninstall idempotent removal: if a file in `files_written` is already gone before uninstall, command completes without error
  - [ ] Run `pytest tests/skills/` (or the new test file) — all pass
  - [ ] Success: all uninstall tests pass; no regressions

- [ ] **T11: Commit checkpoint — uninstall command**
  - [ ] Run `ruff format src/squadron/ tests/` — no changes
  - [ ] Run `ruff check src/squadron/ tests/` — 0 errors
  - [ ] Run `pyright --strict` — 0 errors
  - [ ] Run `pytest tests/skills/` — all pass
  - [ ] `git add src/squadron/cli/commands/skills.py tests/`
  - [ ] Commit: `feat(skills): add sq skills uninstall command`

- [ ] **T12: Add `SECTION_SKILLS` and `check_skill_packs()` to `doctor_checks.py`**
  - [ ] In `src/squadron/cli/commands/doctor_checks.py`, add constant `SECTION_SKILLS = "Skill Packs"`
  - [ ] Add function `check_skill_packs(commands_dir: Path | None = None, cwd: Path | None = None) -> list[CheckResult]`
  - [ ] Logic: (1) call `load_effective(cwd=cwd or Path.cwd())`; (2) if manifest is `None`, return `[CheckResult(name="skills.toml", status=CheckStatus.OK, detail="no manifest; using defaults", section=SECTION_SKILLS, required=False)]`; (3) for each `(name, entry)` in `manifest.packs`, determine install presence using same logic as `sq skills list` (dir exists and non-empty for prefix; file exists for dispatch_file); (4) emit `CheckStatus.OK` if installed, `CheckStatus.WARN` with `fix_hint="sq skills install <name>"` if not; (5) return list sorted by pack name
  - [ ] Import `load_effective` from `squadron.skills.manifest`; import `_DEFAULT_COMMANDS_DIR` from `squadron.cli.commands.skills` or re-define it locally as `Path.home() / ".claude" / "commands"` to avoid circular import
  - [ ] Success: `check_skill_packs()` is importable and returns a non-empty list when the effective manifest contains the `analysis` pack

- [ ] **T13: Tests for `check_skill_packs()`**
  - [ ] In `tests/cli/` (e.g. `tests/cli/commands/test_doctor_checks.py`), add tests:
    - With analysis pack installed (dir and file exist in `tmp_path`): returns `CheckResult` with `status=OK` for `analysis`
    - With analysis pack not installed: returns `CheckResult` with `status=WARN` and `fix_hint` containing `"sq skills install analysis"`
    - When `load_effective()` is monkeypatched to return `None`: returns a single OK result describing "no manifest"
  - [ ] Run `pytest tests/cli/` — all pass
  - [ ] Success: doctor skill pack check tests pass; no regressions

- [ ] **T14: Wire `SECTION_SKILLS` into `doctor.py`**
  - [ ] In `src/squadron/cli/commands/doctor.py`, import `SECTION_SKILLS` from `doctor_checks`
  - [ ] Add `SECTION_SKILLS` to `_SECTION_ORDER` list after `SECTION_INTEGRATIONS`
  - [ ] In `src/squadron/cli/commands/doctor_checks.py`, in `run_all_checks()`, add `_run("skill packs", check_skill_packs)` after the integrations checks and before config checks
  - [ ] Success: `sq doctor` and `sq doctor -v` both exit without error; output includes "Skill Packs" section heading

- [ ] **T15: Tests for `sq doctor` Skill Packs output**
  - [ ] In `tests/cli/` (or existing doctor test file if present), add:
    - Test that `run_all_checks()` result contains at least one `CheckResult` with `section == "Skill Packs"`
    - Test that JSON output from `sq doctor --json` includes a check entry with `"section": "Skill Packs"`
  - [ ] Run `pytest tests/cli/` — all pass
  - [ ] Success: doctor output tests pass; no regressions

- [ ] **T16: Full validation pass and CLI smoke test**
  - [ ] Run `ruff format src/ tests/` — no changes
  - [ ] Run `ruff check src/ tests/` — 0 errors
  - [ ] Run `pyright --strict` — 0 errors
  - [ ] Run `pytest tests/` — all pass
  - [ ] Execute the verification walkthrough from the LLD (steps 1–8): install → inspect receipt → doctor shows installed → uninstall → doctor shows warn → graceful failure on second uninstall → reinstall → unrelated file preserved
  - [ ] Success: all checks green; walkthrough steps produce expected output

- [ ] **T17: Final commit and slice status updates**
  - [ ] `git add src/squadron/cli/commands/doctor_checks.py src/squadron/cli/commands/doctor.py tests/`
  - [ ] Commit: `feat(343): add sq doctor Skill Packs section`
  - [ ] Update `343-slice.sq-skills-uninstall-and-sq-doctor-integration.md` frontmatter: `status: complete`
  - [ ] Update `340-slices.skill-pack-infrastructure.md`: mark entry 4 (slice 343) checked `[x]`
  - [ ] Commit: `docs: mark slice 343 complete`
  - [ ] Success: all commits recorded; slice design and plan both reflect completion
