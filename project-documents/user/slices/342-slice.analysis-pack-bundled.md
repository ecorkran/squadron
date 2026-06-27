---
docType: slice-design
slice: analysis-pack-bundled
project: squadron
parent: 340-slices.skill-pack-infrastructure.md
initiative: 340
index: 342
dependencies: [341]
interfaces: [343]
dateCreated: 20260625
dateUpdated: 20260626
status: complete
---

# Slice Design: Analysis Pack (Bundled)

## Overview

This slice creates the first bundled skill pack for squadron: the `analysis` pack. It adds a `commands/analysis/` directory to the repo (parallel to `commands/sq/`), populates it with the `tech-debt-audit` skill and a dispatch router, wires it into the wheel via `pyproject.toml`, and registers it in a default `skills.toml` that ships with the package. After install, `sq skills install analysis` is a one-command on-ramp that works offline with no GitHub token.

## Value

Users working on existing codebases can get the `tech-debt-audit` skill (and future analysis skills) in one command, without manual file management. The pack demonstrates the bundled source type end-to-end, validates the installer infrastructure built in 341, and serves as the reference implementation for `sq doctor` integration in 343.

## Technical Scope

### In scope
- `commands/analysis/` directory with at minimum `tech-debt-audit.md`
- A dispatcher `analysis.md` in `commands/sq/` enabling `/sq:analysis <skill>` (dispatch model from spike 340; mirrors the existing pattern in `commands/sq/`)
- Default `skills.toml` shipped with the package, pre-declaring the analysis pack
- `pyproject.toml` packaging — `commands/analysis/` already covered by the existing `force-include` rule; verify and document
- `sq skills install analysis` works from the bundled source with no network access
- The installed commands are immediately usable in a Claude Code session after install

### Out of scope
- `sq doctor` integration (slice 343)
- `sq skills uninstall` (slice 343)
- Additional analysis skills beyond `tech-debt-audit` (future work; directory structure supports them trivially)

## Dependencies

- [341] — manifest loader, resolver (bundled source type), installer — all must be complete and functional

## Architecture

### Component Structure

Two new filesystem artifacts are added to the repo; one existing config file is extended:

```
commands/
  sq/
    analysis.md         # NEW: dispatch router — /sq:analysis <skill>
  analysis/
    tech-debt-audit.md  # NEW: the analysis skill

src/squadron/
  data/
    skills.toml           # NEW: default manifest shipped with the package
```

`skills.toml` is a new data file inside the package. It is the default manifest that `manifest.py`'s `load_effective()` consults when no user-level `~/.config/squadron/skills.toml` exists, or it is merged in as a base layer before user/project manifests override it. The exact merge role is specified in **Technical Decisions** below.

### Data Flow: `sq skills install analysis`

```
CLI: sq skills install analysis
  → manifest.py: load_effective() — finds "analysis" pack in effective manifest
  → pack entry: source="bundled", prefix="analysis"
  → resolver.py: resolve_source("analysis") 
      → importlib.resources → squadron/commands/analysis/ (or dev fallback)
      → returns Path to commands/analysis/
  → installer.py: copy *.md to ~/.claude/commands/analysis/
  → report: "Installed pack 'analysis': 1 file(s) → ~/.claude/commands/analysis"
```

The `resolve_source()` path for `bundled` already exists (slice 341). This slice adds the files it resolves to.

### Dispatch Router: `/sq:analysis`

`commands/sq/analysis.md` is a new entry in the existing `sq` command set — installed by `sq install-commands`, not by `sq skills install`. It acts as a top-level dispatcher: `/sq:analysis tech-debt` delegates to `/analysis:tech-debt-audit` (or invokes the skill logic directly, following the dispatch pattern confirmed in spike 340).

The content of `analysis.md` should follow the same structural pattern as other `commands/sq/*.md` dispatchers in the repo.

## Technical Decisions

### Default manifest: shipped as package data, role is base layer

A `skills.toml` at `src/squadron/data/skills.toml` is loaded by `load_effective()` as the lowest-priority base layer. The merge order is:

```
shipped default (base) ← user-level ~/.config/squadron/skills.toml ← project-level .squadron/skills.toml
```

User and project manifests can override or extend the shipped default. This means `sq skills list` shows the `analysis` pack out of the box without requiring the user to create a `skills.toml`. The user can override the `analysis` entry in their own manifest if they want a different source (e.g. a forked version).

If `load_effective()` currently only merges user + project, it is extended here to also load the shipped default as the base. This is a small, backward-compatible change: users who have no `skills.toml` will now see the analysis pack in `sq skills list`.

**Alternative considered:** write the shipped default to `~/.config/squadron/skills.toml` during `sq setup` or `sq install-commands`. Rejected: side-effecting a user config file during install is surprising and non-idempotent. Shipping as package data and reading it at runtime is clean and reversible.

### Packaging: existing `force-include` rule covers `commands/analysis/`

The `pyproject.toml` rule:
```toml
[tool.hatch.build.targets.wheel.force-include]
"commands" = "squadron/commands"
```
bundles the entire `commands/` tree into the wheel as `squadron/commands/`. Adding `commands/analysis/` is automatically included. No `pyproject.toml` change is needed for the commands themselves.

The `src/squadron/data/` directory (for `skills.toml`) must be added as a package data include. Hatch picks up `src/squadron/data/` automatically if it contains an `__init__.py` or is explicitly listed. The simplest approach: create `src/squadron/data/__init__.py` (empty) so `importlib.resources` can resolve `squadron.data`. Alternatively, declare it in `pyproject.toml` under `[tool.hatch.build.targets.wheel]`. Prefer the `__init__.py` approach for consistency with how `squadron/commands/` is resolved.

### `tech-debt-audit.md` content

Content sourced from `github:ecorkran/tech-debt-audit` (MIT license, forked from `ksimback/tech-debt-skill`). The file is stored as `commands/analysis/tech-debt-audit.md` in the squadron repo with an attribution comment prepended. The file has been created; no further content decisions needed.

### `resolve_source("bundled")` for `analysis` pack

The resolver currently resolves `bundled` as `squadron/commands/<pack-name>/`. For pack name `"analysis"`, it resolves to `squadron/commands/analysis/`. This is exactly the directory this slice creates. No resolver changes needed.

## Integration Points

### Provides to slice 343
- A concrete installed pack (`analysis`) for `sq doctor` to report on
- The `data/skills.toml` default manifest pattern that `sq doctor` will read via `load_effective()`

### Extends slice 341
- `manifest.py`'s `load_effective()` gains a base-layer step to load `src/squadron/data/skills.toml`
- This is the only code change in this slice; everything else is new files

## Success Criteria

### Functional Requirements
1. `commands/analysis/tech-debt-audit.md` exists in the repo and the installed wheel.
2. `commands/sq/analysis.md` exists and, when invoked as `/sq:analysis tech-debt`, routes to the tech-debt-audit skill.
3. `sq skills list` shows the `analysis` pack (source=bundled, not-installed) without any user-created `skills.toml`.
4. `sq skills install analysis` installs the pack with no network access and reports success.
5. After install, `~/.claude/commands/analysis/tech-debt-audit.md` exists and can be invoked in a Claude Code session as `/analysis:tech-debt-audit`.
6. A second `sq skills install analysis` is idempotent.

### Technical Requirements
7. `src/squadron/data/skills.toml` is loadable via `importlib.resources` in both wheel and dev-install.
8. `manifest.py`'s `load_effective()` includes the shipped default as base layer; existing tests remain green.
9. All new code passes `pyright` strict and `ruff` lint/format.

### Verification Walkthrough

**Prereq:** squadron dev install (`uv pip install -e .`); no user-level `~/.config/squadron/skills.toml`.

**1. List shows analysis pack with no user manifest**
```bash
sq skills list
```
Expected output (verified 20260626):
```
                          Skill Packs
┏━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┓
┃ Pack     ┃ Source  ┃ Surface          ┃ Status    ┃ Origin  ┃
┡━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━┩
│ analysis │ bundled │ prefix: analysis │ Installed │ default │
└──────────┴─────────┴──────────────────┴───────────┴─────────┘
```
Note: `Status=Installed` because `sq install-commands` was run; on a fresh system it shows `Not installed`.

**2. Install from bundled source (no network)**
```bash
sq skills install analysis
# Installed pack 'analysis': 1 file(s) → /Users/<you>/.claude/commands/analysis
ls ~/.claude/commands/analysis/
# tech-debt-audit.md
```
Verified 20260626: correct output.

**3. List shows installed**
```bash
sq skills list
# analysis  bundled  prefix: analysis  Installed  default
```
Verified 20260626.

**4. Verify command is invocable**

Open a Claude Code session in any repo and run:
```
/analysis:tech-debt-audit
```
Claude Code should recognise and invoke the skill. The skill file is at `~/.claude/commands/analysis/tech-debt-audit.md` after `sq skills install analysis`.

**5. Dispatcher route (sq commands)**
```bash
sq install-commands
# Installed 10 command(s) to ~/.claude/commands:
#   analysis/tech-debt-audit.md
#   sq/analysis.md
#   ...
```
Verified 20260626. Then in Claude Code: `/sq:analysis tech-debt-audit` → routes to tech-debt-audit skill via `commands/sq/analysis.md` dispatcher.

**6. Idempotent reinstall**
```bash
sq skills install analysis
# Installed pack 'analysis': 1 file(s) → /Users/<you>/.claude/commands/analysis
# (no error — verified 20260626)
```

**7. Package data smoke test**
```bash
# Verify shipped skills.toml resolves via importlib.resources (works in dev and installed)
python -c "from importlib.resources import files; print((files('squadron') / 'data' / 'skills.toml').read_text())"
# Prints TOML content — verified 20260626
```
**Caveat (dev mode):** `importlib.resources.files('squadron') / 'commands' / 'analysis'` does NOT resolve in editable installs because `commands/` is at the project root and mapped via `pyproject.toml` `force-include` (wheel-only). The resolver falls back to the project-root `commands/` directory via the `_resolve_bundled` dev fallback added in this slice. In an installed wheel, `importlib.resources` resolves `squadron/commands/analysis/` directly.

## Implementation Notes

### Development Order
1. Create `src/squadron/data/__init__.py` and `src/squadron/data/skills.toml` — shortest path to verifying `load_effective()` extension
2. Extend `manifest.py`'s `load_effective()` to load the shipped default as base layer; update tests
3. Add `commands/analysis/tech-debt-audit.md` (content from existing forked skill)
4. Add `commands/sq/analysis.md` dispatcher
5. End-to-end smoke test per walkthrough above

### Testing
- Unit test: `load_effective()` returns analysis pack entry even when no user/project manifest exists
- Unit test: user manifest overrides the default entry for the same pack name
- Integration smoke test: `sq skills install analysis` (invoked in test against a temp `commands_dir`) copies `tech-debt-audit.md`
- Network tests are not needed; this slice has no external dependencies
