---
docType: tasks
slice: manifest-format-and-sq-skills-install-list
project: squadron
lld: user/slices/341-slice.manifest-format-and-sq-skills-install-list.md
dependencies: [340]
projectState: Slice 340 complete (dispatch model adopted). Branch main is clean. No skills subpackage exists yet; no sq skills commands exist.
dateCreated: 20260625
dateUpdated: 20260625
status: not_started
---

## Context Summary

- Working on slice 341: manifest format and `sq skills install/list`
- Slice 340 (spike) confirmed dispatch model; manifest supports both `prefix` and `dispatch_file`
- New `squadron/skills/` subpackage: `models.py`, `manifest.py`, `resolver.py`, `installer.py`
- New CLI layer: `cli/commands/skills.py` with `skills_app` Typer sub-app
- `app.py` wires in `skills_app` via `add_typer`
- No new third-party dependencies: `tomllib` (stdlib 3.11+), Pydantic (already present), `subprocess` + system `git`
- Next: slice 342 (analysis pack, bundled)

---

## Tasks

- [ ] **T1: Create `squadron/skills/` subpackage and models**
  - [ ] Create `src/squadron/skills/__init__.py` (empty, exports nothing yet)
  - [ ] Create `src/squadron/skills/models.py` with:
    - `PackEntry` — Pydantic model: `source: str`, `prefix: str | None = None`, `dispatch_file: str | None = None`; validator raises `ValueError` if both or neither of `prefix`/`dispatch_file` are set
    - `InstallResult` — dataclass: `pack_name: str`, `files_written: list[str]`, `destination: Path`
    - `SkillSourceError` — exception class (subclass of `Exception`)
  - [ ] Success: `python -c "from squadron.skills.models import PackEntry, InstallResult, SkillSourceError"` exits 0; `PackEntry(source='bundled', prefix='a', dispatch_file='b')` raises `ValueError`; `PackEntry(source='bundled')` raises `ValueError`

- [ ] **T2: Tests for models**
  - [ ] Create `tests/skills/__init__.py` and `tests/skills/test_models.py`
  - [ ] Test `PackEntry` validation: prefix-only passes, dispatch_file-only passes, both raises, neither raises
  - [ ] Test `SkillSourceError` is catchable as `Exception`
  - [ ] Success: `pytest tests/skills/test_models.py` passes

- [ ] **T3: Implement `manifest.py` — load and merge**
  - [ ] Create `src/squadron/skills/manifest.py`
  - [ ] `SkillsManifest` — Pydantic model: `packs: dict[str, PackEntry]`, `origin: str` (filepath string for display)
  - [ ] `load(path: Path) -> SkillsManifest` — reads TOML via `tomllib`; raises `ValueError` with "Could not parse skills.toml at {path}: {detail}" on `TOMLDecodeError`; raises `FileNotFoundError` as-is
  - [ ] `merge(user: SkillsManifest, project: SkillsManifest) -> SkillsManifest` — union of packs; project-level wins on name collision; `origin` set to `"merged"`
  - [ ] `load_effective(cwd: Path | None = None) -> SkillsManifest | None` — loads user-level (`~/.config/squadron/skills.toml`) and optionally project-level (`cwd/.squadron/skills.toml`); returns merged result, or `None` if neither exists
  - [ ] Success: `python -c "from squadron.skills.manifest import load_effective"` exits 0

- [ ] **T4: Tests for manifest**
  - [ ] `tests/skills/test_manifest.py` using `tmp_path` fixtures
  - [ ] Test `load()` with valid TOML returns correct `SkillsManifest`
  - [ ] Test `load()` with malformed TOML raises `ValueError` with path in message
  - [ ] Test `merge()`: additive union, project-level pack wins on collision
  - [ ] Test `load_effective()` with no files returns `None`; with only user-level returns user manifest; with both returns merged
  - [ ] Success: `pytest tests/skills/test_manifest.py` passes

- [ ] **T5: Implement `resolver.py` — source resolution**
  - [ ] Create `src/squadron/skills/resolver.py`
  - [ ] `resolve_source(entry: PackEntry, pack_name: str) -> Path` — returns a local `Path` to the directory containing `.md` files:
    - `"bundled"`: use `importlib.resources` to find `squadron/commands/<pack_name>/`; raise `SkillSourceError` if not found
    - Absolute path: validate exists and is a directory; raise `SkillSourceError` otherwise
    - Relative path (starts with `./` or `../`): resolve relative to user config dir; raise `SkillSourceError` if not found
    - `"github:<org>/<repo>"`: shallow clone to `tempfile.TemporaryDirectory`; return the cloned path; raise `SkillSourceError` if `git` not on PATH or clone fails — caller is responsible for cleanup
    - Any unrecognized pattern: raise `SkillSourceError("Unknown source format '...' for pack '...'.")`
  - [ ] GitHub path: use `subprocess.run(["git", "clone", "--depth=1", url, dest], capture_output=True)`; check `git` availability via `shutil.which("git")` before attempting
  - [ ] Success: `python -c "from squadron.skills.resolver import resolve_source"` exits 0

- [ ] **T6: Tests for resolver**
  - [ ] `tests/skills/test_resolver.py`
  - [ ] Test absolute local path: valid directory resolves; missing path raises `SkillSourceError`
  - [ ] Test unknown source format raises `SkillSourceError` with pack name in message
  - [ ] Test missing `git` binary raises `SkillSourceError` with install hint (mock `shutil.which` to return `None`)
  - [ ] Skip GitHub clone test if no network (mark with `pytest.mark.network`)
  - [ ] Success: `pytest tests/skills/test_resolver.py` passes (network tests may be skipped)

- [ ] **T7: Commit checkpoint — subpackage foundation**
  - [ ] Verify `ruff format src/squadron/skills/ tests/skills/` and `ruff check` pass with no errors
  - [ ] Verify `pyright` reports 0 errors for `src/squadron/skills/`
  - [ ] `git add` and commit: `feat(skills): add skills subpackage — models, manifest, resolver`

- [ ] **T8: Implement `installer.py` — file copy**
  - [ ] Create `src/squadron/skills/installer.py`
  - [ ] `install_pack(pack_name: str, entry: PackEntry, commands_dir: Path) -> InstallResult` — resolves source, copies `.md` files:
    - For `prefix` entry: destination is `commands_dir / entry.prefix`; copy all `*.md` from source dir; create dest if absent
    - For `dispatch_file` entry: destination parent is `commands_dir / "sq"`; copy single file `<entry.dispatch_file>.md` from source dir
    - Both cases: `shutil.copy2` each file; collect filenames in `InstallResult.files_written`
    - For `github:` source: clone to temp dir, resolve files within temp dir, copy, then temp dir is cleaned up by context manager
  - [ ] Raise `SkillSourceError` (propagated from resolver) on bad source; let it bubble to CLI for display
  - [ ] Success: `python -c "from squadron.skills.installer import install_pack"` exits 0

- [ ] **T9: Tests for installer**
  - [ ] `tests/skills/test_installer.py` using `tmp_path`
  - [ ] Test prefix install: `.md` files copied to `commands_dir/<prefix>/`; `InstallResult.files_written` contains filenames
  - [ ] Test dispatch_file install: single file copied to `commands_dir/sq/<name>.md`
  - [ ] Test idempotent install: running `install_pack` twice does not raise; files overwritten
  - [ ] Test missing source dir raises `SkillSourceError`
  - [ ] Success: `pytest tests/skills/test_installer.py` passes

- [ ] **T10: Implement `cli/commands/skills.py` — Typer layer**
  - [ ] Create `src/squadron/cli/commands/skills.py`
  - [ ] `skills_app = typer.Typer(name="skills", help="Manage skill packs.", no_args_is_help=True)`
  - [ ] `install` subcommand: takes `pack_name: str` positional arg; loads effective manifest; looks up pack (error if not found: "Pack '{name}' not found in skills.toml. Available: ..."); calls `install_pack`; prints Rich success summary
  - [ ] `list` subcommand: loads effective manifest; for each pack, checks whether install destination exists and is non-empty; renders Rich table with columns: Pack, Source, Surface, Status (Installed / Not installed), Origin (user/project)
  - [ ] Both commands: if `load_effective()` returns `None`, print actionable "No skills.toml found. Create one at ~/.config/squadron/skills.toml to manage skill packs." and exit with code 1
  - [ ] Catch `SkillSourceError` in `install`; print error message via Rich `[red]` and exit with code 1 (no traceback)
  - [ ] Success: `sq skills --help` shows `install` and `list` subcommands

- [ ] **T11: Wire `skills_app` into `app.py`**
  - [ ] Add `from squadron.cli.commands.skills import skills_app` import to `app.py`
  - [ ] Add `app.add_typer(skills_app, name="skills")` after the existing `add_typer` calls
  - [ ] Success: `sq skills --help` exits 0 and shows both subcommands

- [ ] **T12: Tests for CLI commands**
  - [ ] `tests/skills/test_cli_skills.py` using Typer `CliRunner`
  - [ ] Test `sq skills list` with no manifest: exits 1, message contains "No skills.toml found"
  - [ ] Test `sq skills install nonexistent` with a manifest that does not contain that pack: exits 1, message contains pack name and "not found"
  - [ ] Test `sq skills install <pack>` with a local-path pack entry and a temp source dir: exits 0, output contains file count
  - [ ] Test `sq skills list` with a manifest containing one installed and one not-installed pack: output shows both with correct status
  - [ ] Success: `pytest tests/skills/test_cli_skills.py` passes

- [ ] **T13: Full validation pass**
  - [ ] Run `ruff format src/ tests/` — no changes
  - [ ] Run `ruff check src/ tests/` — 0 errors
  - [ ] Run `pyright` — 0 errors
  - [ ] Run `pytest tests/skills/` — all pass
  - [ ] Run `sq skills --help`, `sq skills install --help`, `sq skills list --help` — all exit 0

- [ ] **T14: Commit final**
  - [ ] `git add` all new and modified files
  - [ ] Commit: `feat(skills): add sq skills install/list with TOML manifest support`
