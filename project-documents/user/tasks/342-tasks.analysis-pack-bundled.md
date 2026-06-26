---
docType: tasks
slice: analysis-pack-bundled
project: squadron
lld: user/slices/342-slice.analysis-pack-bundled.md
dependencies: [341]
projectState: Slice 341 complete. skills subpackage (models, manifest, resolver, installer, CLI) exists and all tests pass. Branch 340-planning.skill-pack-infrastructure holds slice design. No commands/analysis/ directory exists yet; no src/squadron/data/ package exists yet.
dateCreated: 20260625
dateUpdated: 20260625
status: not_started
---

## Context Summary

- Working on slice 342: analysis pack (bundled)
- Adds `commands/analysis/tech-debt-audit.md`, `commands/sq/analysis.md` dispatcher, and `src/squadron/data/skills.toml` default manifest
- Only code change to existing modules: extend `manifest.py`'s `load_effective()` to load the shipped default as a base layer
- `commands/analysis/` is covered by the existing `pyproject.toml` `force-include` rule — no packaging changes for commands
- `src/squadron/data/skills.toml` requires a new `src/squadron/data/__init__.py` for `importlib.resources` resolution
- Skill content sourced from `github:ecorkran/tech-debt-audit` (MIT, forked from `ksimback/tech-debt-skill`); file already created at `commands/analysis/tech-debt-audit.md`
- Next: slice 343 (`sq skills uninstall` and `sq doctor` integration)

---

## Tasks

- [ ] **T1: Create branch and verify prereqs**
  - [ ] Verify branch is `342-slice.analysis-pack-bundled` (create from `main` if absent)
  - [ ] Run `pytest tests/skills/` — all pass (confirms slice 341 foundation is intact)
  - [ ] Success: branch exists, all 341 tests pass

- [ ] **T2: Create `src/squadron/data/` package**
  - [ ] Create `src/squadron/data/__init__.py` (empty file)
  - [ ] Create `src/squadron/data/skills.toml` with content:
    ```toml
    # Default skill pack manifest shipped with squadron.
    # User and project-level skills.toml files override or extend these entries.

    [packs.analysis]
    source = "bundled"
    prefix = "analysis"
    ```
  - [ ] Verify `importlib.resources` can resolve it:
    `python -c "from importlib.resources import files; print((files('squadron') / 'data' / 'skills.toml').read_text())"`
  - [ ] Success: command prints the TOML content without error

- [ ] **T3: Extend `load_effective()` to load shipped default**
  - [ ] In `src/squadron/skills/manifest.py`, add a helper `_load_shipped_default() -> SkillsManifest | None` that reads `src/squadron/data/skills.toml` via `importlib.resources`; returns `None` if not found (should not happen in practice, but must not crash)
  - [ ] Update `load_effective()` to use the shipped default as the lowest-priority base layer. New merge order (lowest → highest priority): shipped default → user-level → project-level
  - [ ] If all three are absent, return `None` (unchanged behavior for the no-manifest case — but shipped default is always present in a normal install, so `None` will only occur in test scenarios where it is patched out)
  - [ ] Add a public constant `SHIPPED_DEFAULT_ORIGIN = "default"` for use in CLI display (the `origin` field of the shipped manifest)
  - [ ] Success: `python -c "from squadron.skills.manifest import load_effective; m = load_effective(); print(m.packs)"` shows `{'analysis': ...}` without any user-created `skills.toml`

- [ ] **T4: Tests for extended `load_effective()`**
  - [ ] In `tests/skills/test_manifest.py`, add new test class `TestLoadEffectiveWithDefault`
  - [ ] Test: with no user or project manifest, `load_effective()` returns the `analysis` pack from the shipped default (monkeypatch `USER_MANIFEST` to a nonexistent path; do not patch the shipped default loader)
  - [ ] Test: user manifest with a different `analysis` entry overrides the shipped default for that pack; other shipped packs are still present
  - [ ] Test: `load_effective()` result has `origin == "merged"` when user manifest is present alongside the default
  - [ ] Success: `pytest tests/skills/test_manifest.py` — all pass (including pre-existing tests)

- [ ] **T5: Verify `commands/analysis/tech-debt-audit.md`**
  - [ ] File already exists at `commands/analysis/tech-debt-audit.md` (attribution comment + skill content from `github:ecorkran/tech-debt-audit`)
  - [ ] Verify packaging: `python -c "from importlib.resources import files; print(list((files('squadron') / 'commands' / 'analysis').iterdir()))"`
  - [ ] Success: command lists `tech-debt-audit.md`; file is non-empty

- [ ] **T6: Add `commands/sq/analysis.md` dispatcher**
  - [ ] Create `commands/sq/analysis.md` following the existing dispatcher pattern (see `commands/sq/run.md` for structure)
  - [ ] The dispatcher reads `$ARGUMENTS`; the first word is the skill name (e.g. `tech-debt-audit`)
  - [ ] Routes `tech-debt-audit` → delegates to `/analysis:tech-debt-audit`
  - [ ] For unrecognized skill names, print usage and stop
  - [ ] Usage line: `/sq:analysis tech-debt-audit [target]`
  - [ ] Success: file exists at `commands/sq/analysis.md`; content follows dispatcher pattern; `sq install-commands` includes it in its output

- [ ] **T7: Commit checkpoint — data package and manifest extension**
  - [ ] Run `ruff format src/squadron/ tests/skills/` — no changes
  - [ ] Run `ruff check src/squadron/ tests/skills/` — 0 errors
  - [ ] Run `pyright` — 0 errors
  - [ ] Run `pytest tests/skills/` — all pass
  - [ ] `git add src/squadron/data/ src/squadron/skills/manifest.py tests/skills/test_manifest.py commands/analysis/ commands/sq/analysis.md`
  - [ ] Commit: `feat(skills): add analysis pack and shipped default manifest`

- [ ] **T8: CLI smoke test — `sq skills list` without user manifest**
  - [ ] Temporarily rename `~/.config/squadron/skills.toml` if it exists (restore after test)
  - [ ] Run `sq skills list` — output table includes `analysis` row with `Source=bundled`, `Status=Not installed`, `Origin=default`
  - [ ] Restore `skills.toml` if renamed
  - [ ] Success: analysis pack row visible with no user manifest

- [ ] **T9: CLI smoke test — `sq skills install analysis`**
  - [ ] Run `sq skills install analysis`
  - [ ] Expected output: `Installed pack 'analysis': 1 file(s) → .../.claude/commands/analysis`
  - [ ] Verify: `ls ~/.claude/commands/analysis/` shows `tech-debt-audit.md`
  - [ ] Run `sq skills install analysis` a second time — no error (idempotent)
  - [ ] Run `sq skills list` — `analysis` row shows `Status=Installed`
  - [ ] Success: all steps above pass

- [ ] **T10: Integration test — install pack via test fixture**
  - [ ] In `tests/skills/test_installer.py` (or a new `tests/skills/test_analysis_pack.py`), add a test that:
    1. Calls `install_pack("analysis", PackEntry(source="bundled", prefix="analysis"), commands_dir=tmp_path)` 
    2. Asserts `(tmp_path / "analysis" / "tech-debt-audit.md").exists()`
    3. Asserts `InstallResult.files_written` contains `"tech-debt-audit.md"`
  - [ ] Success: `pytest tests/skills/` — all pass

- [ ] **T11: Full validation pass**
  - [ ] Run `ruff format src/ tests/` — no changes
  - [ ] Run `ruff check src/ tests/` — 0 errors
  - [ ] Run `pyright` — 0 errors
  - [ ] Run `pytest tests/skills/` — all pass
  - [ ] Run `sq skills --help`, `sq skills install --help`, `sq skills list --help` — all exit 0
  - [ ] Success: all checks green

- [ ] **T12: Commit final and update slice status**
  - [ ] If T10 added new test files, `git add tests/skills/`
  - [ ] Commit: `feat(342): complete analysis pack bundled slice`
  - [ ] Update `342-slice.analysis-pack-bundled.md` frontmatter: `status: complete`
  - [ ] Update `340-slices.skill-pack-infrastructure.md`: mark entry 3 (slice 342) checked `[x]`
  - [ ] Commit: `docs: mark slice 342 complete`
