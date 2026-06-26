---
docType: slice-design
parent: 340-slices.skill-pack-infrastructure.md
initiative: 340
index: 341
project: squadron
dateCreated: 20260625
dateUpdated: 20260625
status: complete
slice: manifest-format-and-sq-skills-install-list
---

# Slice Design: Manifest Format and `sq skills install/list`

## Overview

This slice defines the `skills.toml` schema and implements two commands: `sq skills install <pack>` and `sq skills list`. It establishes the core mechanism for the skill pack infrastructure — a declarative TOML manifest that names packs and their sources, a resolver that turns source declarations into local file paths, and a file-copy installer that writes markdown files into `~/.claude/commands/<prefix>/`. The dispatch model is adopted (spike 340 confirmed this), so the manifest supports both `prefix` and `dispatch_file` as command surface options.

## Value

After this slice, a user can install any skill pack from a local path, a bundled source, or a GitHub repository with a single command. The mechanism is generic: slice 342 (analysis pack) simply adds a bundled pack declaration and works via this infrastructure.

## Technical Scope

### In scope
- `skills.toml` schema definition (user-level and project-level)
- Resolver for `bundled`, local-path, and `github:<org>/<repo>` sources
- `sq skills install <pack>` — resolves source, copies markdown files, reports what was written
- `sq skills list` — reads manifest, checks installed status per pack, reports
- Idempotent install (overwrite existing files; note if already current)
- Clear error handling for all failure modes (missing pack, unreachable source, bad manifest)
- Merge semantics for project-level vs. user-level manifest (defined below)

### Out of scope
- `sq skills uninstall` (slice 343)
- `sq doctor` integration (slice 343)
- Version pinning / lock files (future work)
- `sq skills update` (future work)
- Registry / community pack index (future work)

## Dependencies

- [340] — dispatch vs. prefix decision (complete; dispatch model adopted)
- [100] — `importlib.resources` bundling pattern, `_get_commands_source()` (reference)

## Architecture

### Manifest Location and Merge Semantics

Two manifest files are supported:

| Level | Path | Role |
|-------|------|------|
| User-level | `~/.config/squadron/skills.toml` | Default; applies everywhere |
| Project-level | `<cwd>/.squadron/skills.toml` | Additive override; extends user-level |

**Merge rule: additive union.** The project-level manifest adds pack entries not present in the user-level manifest. If a pack name appears in both, the project-level entry wins (it overrides the user-level entry for that name). Entries from both levels appear in `sq skills list` with their origin noted.

Rationale: override semantics are simpler to reason about than deep merge; additive-wins avoids silent suppression of user-level packs; project-level override is the natural affordance for "use this forked version of pack X in this project."

### Schema

```toml
# ~/.config/squadron/skills.toml

[packs.analysis]
source = "bundled"
prefix = "analysis"           # installs to ~/.claude/commands/analysis/

[packs.my-dispatch-pack]
source = "github:org/repo"
dispatch_file = "analysis"    # installs a single dispatcher to ~/.claude/commands/sq/analysis.md
# (dispatch_file and prefix are mutually exclusive)

[packs.local-experiment]
source = "/path/to/local/pack"
prefix = "exp"
```

**Pack entry fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | yes | `"bundled"`, an absolute/relative path, or `"github:<org>/<repo>"` |
| `prefix` | string | one of | Directory name under `~/.claude/commands/` where `.md` files are copied |
| `dispatch_file` | string | one of | Basename (no extension) of a single dispatcher file installed at `~/.claude/commands/sq/<name>.md` |

Exactly one of `prefix` or `dispatch_file` must be present. The resolver raises a clear error if both are present or neither is.

### Source Types

| Source value | Resolution |
|---|---|
| `"bundled"` | `importlib.resources` resolves `squadron/commands/<pack-name>/` from the wheel (same pattern as `_get_commands_source()`) |
| Absolute path (`/...`) | Used directly as a directory; must exist at install time |
| Relative path (`./...`) | Resolved relative to the manifest file's directory |
| `"github:<org>/<repo>"` | Shallow clone (`depth=1`) to a temp directory; copy `.md` files from repo root or `commands/` subdirectory if present; discard clone |

For the `github:` source, the repo is expected to contain `.md` files directly at its root or in a `commands/<pack-name>/` subdirectory. No branch or ref pinning in v1; `HEAD` of the default branch is always fetched.

The resolver validates the source type and raises `SkillSourceError` (a new exception type) with an actionable message for unknown formats or unreachable sources.

### File Copy Semantics

**For `prefix` packs:** copy all `*.md` files from the resolved source directory to `~/.claude/commands/<prefix>/`. Create the directory if absent. Overwrite existing files. Do not delete files in the destination that are absent from the source (only `uninstall` removes files; install is additive within a pack's prefix directory). Report each file copied.

**For `dispatch_file` packs:** copy the single dispatcher file (named `<dispatch_file>.md` in the source) to `~/.claude/commands/sq/<dispatch_file>.md`. Overwrite if present.

**Idempotency:** A second install of the same pack is not an error. Files are overwritten silently (no "already installed" noise). A summary line indicates the pack was (re)installed.

### Component Structure

```
src/squadron/
  skills/
    __init__.py
    manifest.py          # SkillsManifest dataclass, load(), merge()
    resolver.py          # resolve_source(pack) → Path, SkillSourceError
    installer.py         # install_pack(pack, manifest) → InstallResult
    models.py            # PackEntry dataclass, InstallResult dataclass
  cli/
    commands/
      skills.py          # sq skills Typer sub-app: install, list subcommands
```

`skills/` is a new subpackage of `squadron`. It has no dependency on CLI concerns; `cli/commands/skills.py` is the thin Typer layer.

### Data Flow: `sq skills install analysis`

```
CLI arg "analysis"
  → skills.py: load manifest (user + project merge)
  → manifest.py: look up pack entry "analysis"
  → resolver.py: resolve_source(entry) → local Path to commands/analysis/
  → installer.py: copy *.md to ~/.claude/commands/analysis/
  → report: "Installed N file(s) to ~/.claude/commands/analysis/"
```

### Data Flow: `sq skills list`

```
CLI: sq skills list
  → load manifest (user + project merge)
  → for each pack entry:
      check ~/.claude/commands/<prefix>/ (or sq/<dispatch_file>.md) exists and is non-empty
      report status: installed / not installed
  → render table
```

## Technical Decisions

**`tomllib` for parsing:** Python 3.11+ stdlib `tomllib` (read-only). No third-party TOML library. Writing the manifest is not a feature of this slice (users write it themselves); read-only is sufficient.

**`subprocess` + `git clone` for GitHub source:** No `gitpython` dependency. A single `subprocess.run(["git", "clone", "--depth=1", url, tmp_dir])` is sufficient. Check exit code; capture stderr for error messages. `git` must be available on `PATH`; if not, fail with a clear message: "git is required to install packs from GitHub sources. Install git and retry."

**`Pydantic` for manifest model:** `PackEntry` is a Pydantic model for external-boundary validation. `SkillsManifest` is a Pydantic model containing `dict[str, PackEntry]`. This validates the TOML structure at load time with field-level error messages.

**`tempfile.TemporaryDirectory`** for GitHub clone staging; used as a context manager so the clone is always cleaned up even on failure.

**Typer sub-app pattern:** `skills_app = typer.Typer(name="skills", help="Manage skill packs.")` added to `app.py` via `app.add_typer(skills_app, name="skills")`. This matches the existing `models_app`, `pools_app`, etc. pattern.

**No manifest auto-creation:** If neither manifest file exists, `sq skills list` reports "No skills.toml found. Create one at ~/.config/squadron/skills.toml to manage skill packs." `sq skills install <pack>` fails with the same message. We do not silently create an empty manifest.

## Integration Points

### Provides to slice 342 (Analysis Pack)
- `installer.py` `install_pack()` function — callable directly in tests and future `sq skills update`
- `manifest.py` `load()` — usable by slice 343 `sq doctor` checks
- The `bundled` source type, which slice 342 relies on for its pack entry

### Consumes from slice 100 / existing install.py
- `_get_commands_source()` pattern — replicated in `resolver.py` for the `bundled` source type, or extracted to a shared `squadron.resources` utility if both modules need it. Prefer extraction to avoid duplication.

### app.py change
Add one line: `app.add_typer(skills_app, name="skills")` and the corresponding import. No other changes to `app.py`.

## Success Criteria

1. `skills.toml` schema is documented (this slice design is the spec); Pydantic validation rejects invalid entries with actionable messages.
2. `sq skills install <pack>` works for all three source types: bundled, local path, and `github:org/repo`.
3. `sq skills list` shows installed/not-installed status for all manifest entries, noting origin (user-level or project-level).
4. Installing an already-installed pack is idempotent — no error, files overwritten, summary indicates (re)installed.
5. Invalid source type fails with a clear `SkillSourceError` message, not a traceback.
6. Unreachable GitHub source (bad URL, no network) fails with a clear message identifying the pack and URL.
7. Missing `skills.toml` produces an actionable "no manifest found" message, not a file-not-found traceback.
8. `prefix` and `dispatch_file` are mutually exclusive; presence of both or neither raises a validation error at manifest load time.
9. Project-level manifest overrides user-level for same-named packs; both sources appear in `sq skills list` output.
10. All new modules pass `pyright` strict mode and `ruff` lint/format with no errors.

## Risk Assessment

**GitHub fetch dependency:** `git` must be on `PATH`. Documented as a requirement; fails clearly if absent. Low risk for the primary user path (bundled and local-path sources have no external dependency).

**TOML write-by-user:** Users write `skills.toml` by hand; malformed TOML produces `tomllib.TOMLDecodeError`. Caught at load time with a helpful "Could not parse skills.toml at <path>: <detail>" message. Low risk.

## Verification Walkthrough

Prereq: squadron installed in dev mode; `commands/analysis/` exists (slice 342) OR substitute any local directory with `.md` files for the bundled-source steps.

> **Implementation note:** `ValidationError` from malformed `PackEntry` entries in the TOML is now caught by `load()` and re-raised as `ValueError` with path context. The CLI catches `ValueError` from `load_effective()` and prints an actionable error. Step 5 below reflects this behavior.

**1. Local-path source install**
```bash
mkdir -p /tmp/test-pack
echo "# test skill" > /tmp/test-pack/hello.md

cat >> ~/.config/squadron/skills.toml << 'EOF'
[packs.test]
source = "/tmp/test-pack"
prefix = "test-pack"
EOF

sq skills install test
# Output: Installed pack 'test': 1 file(s) → /Users/<you>/.claude/commands/test-pack

ls ~/.claude/commands/test-pack/
# Output: hello.md
```

**2. List with status**
```bash
sq skills list
# Output: Rich table with Pack/Source/Surface/Status/Origin columns
#         "test" row shows Source="/tmp/test-pack", Status="Installed"
```

**3. Idempotent reinstall**
```bash
sq skills install test
# Output: Installed pack 'test': 1 file(s) → /Users/<you>/.claude/commands/test-pack
# (no error; hello.md overwritten silently)
```

**4. Unknown pack**
```bash
sq skills install nonexistent
# exit code 1
# Output: Pack 'nonexistent' not found in skills.toml. Available: test
```

**5. Invalid manifest entry (both prefix and dispatch_file)**
```bash
cat >> ~/.config/squadron/skills.toml << 'EOF'
[packs.broken]
source = "bundled"
prefix = "a"
dispatch_file = "b"
EOF

sq skills install broken
# exit code 1
# Output: Error loading skills.toml: Invalid pack entry in skills.toml at
#         ~/.config/squadron/skills.toml: 1 validation error for PackEntry
#           Value error, PackEntry must have exactly one of 'prefix' or 'dispatch_file', not both.
```

**6. No manifest**
```bash
mv ~/.config/squadron/skills.toml /tmp/skills-backup.toml
sq skills list
# exit code 1
# Output: No skills.toml found. Create one at ~/.config/squadron/skills.toml to manage skill packs.
mv /tmp/skills-backup.toml ~/.config/squadron/skills.toml
```

**7. GitHub source (requires network and git)**
```bash
cat >> ~/.config/squadron/skills.toml << 'EOF'
[packs.gh-test]
source = "github:anthropics/claude-code"
prefix = "ghtest"
EOF

sq skills install gh-test
# Expected: clones repo, copies .md files found at repo root, reports count
# Note: if no .md files exist at repo root, files_written will be empty (0 file(s))
```

**8. Missing git binary (simulated)**
```bash
PATH_SAVE=$PATH; export PATH=/usr/bin  # strip git from PATH
sq skills install gh-test
# exit code 1
# Output: Error: Cannot install pack 'gh-test' from GitHub: 'git' is not on PATH. Install git and try again.
export PATH=$PATH_SAVE
```
