---
docType: slice-design
slice: project-rename-squadron
project: orchestration
parent: user/architecture/100-slices.orchestration-v2.md
dependencies: [auth-strategy-credential-management]
interfaces: [claude-code-commands-thin, mcp-server, conversation-persistence]
status: in_progress
dateCreated: 20260305
dateUpdated: 20260305
---

# Slice Design: Project Rename — orchestration → squadron

## Overview

Rename the project from "orchestration" to "squadron" across all surfaces: Python package, CLI entry point, configuration paths, documentation, and internal references. The CLI command becomes `sq` (short form) with `squadron` as the long form. After this slice, `sq spawn reviewer`, `sq review arch`, and `sq auth status` all work, and the old `orchestration` command no longer exists.

Squadron — a group of manta rays — continues the existing naming theme (manta@anemone) while avoiding the collision with every other AI project named "orchestration."

## Value

**Distinctiveness.** "orchestration" is generic to the point of being unsearchable. "squadron" is unique, memorable, and short. Package discovery, GitHub visibility, and word-of-mouth all improve.

**CLI ergonomics.** `sq` is two characters. `orchestration` is thirteen. Every developer interaction gets faster.

**Pre-command branding.** Slice 118 (Claude Code commands) ships command files referencing `sq`. Doing the rename first means those commands are correct from day one rather than requiring a coordinated update later.

## Technical Scope

### Included

**Package rename:**
- `src/orchestration/` → `src/squadron/`
- All internal imports updated (`from orchestration.` → `from squadron.`)
- `pyproject.toml`: project name, package directory, entry points
- `uv.lock` regenerated

**CLI entry points:**
- Primary: `sq = "squadron.cli.app:app"`
- Long form: `squadron = "squadron.cli.app:app"`
- Old `orchestration` entry point removed

**Configuration paths:**
- User config: `~/.config/orchestration/` → `~/.config/squadron/`
  - `config.toml`, `providers.toml`, auth credentials
- Project config: `.orchestration.toml` → `.squadron.toml`
- First-run migration: if `~/.config/squadron/` doesn't exist but `~/.config/orchestration/` does, copy contents and print a one-time notice
- Old directory left in place (no deletion) with a `MIGRATED.txt` note

**Daemon paths:**
- Socket/PID file paths that reference "orchestration" updated to "squadron"
- Daemon detection logic checks new paths

**Logging:**
- Logger names: `orchestration.*` → `squadron.*`

**Error messages:**
- All user-facing strings that say `orchestration` updated (e.g., `"Use 'orchestration list' to see active agents"` → `"Use 'sq list' to see active agents"`)

**Tests:**
- All imports in `tests/` updated
- Test fixtures referencing config paths updated
- No test logic changes — only string/import updates

**Documentation:**
- `README.md`: all command examples, installation instructions, project name
- `CLAUDE.md`: project identity references
- Any other `.md` files in the repo

**Git:**
- Single commit for the rename: `refactor: rename orchestration → squadron`
- Repo directory name change is the developer's responsibility (outside this slice)
- GitHub repo rename is optional and tracked as a follow-up note, not a task

### Excluded

- **GitHub repo rename** — This has downstream effects (git remotes, links in other projects, CI if any). Documented as a follow-up action, not part of this slice.
- **context-forge references** — context-forge's architecture docs reference "orchestration" as a project name. Those references will be updated when context-forge's project knowledge is refreshed, not in this slice.
- **ai-project-guide doc filenames** — Files like `100-arch.orchestration-v2.md` in project-documents follow the naming convention using the project name at creation time. Renaming these is optional and can be done separately; the content matters more than the filename.
- **PyPI publishing** — The package isn't published yet. When it is, it will publish as `squadron`.

## Dependencies

### Prerequisites

- **Auth Strategy & Credential Management (slice 114, complete):** The config and auth paths being renamed were established in slices 106 and 114. All config-related code must be stable before renaming.

### External Packages

No new packages. This is a pure refactor.

## Architecture

This slice has no architectural changes. The internal structure, module layout, and all APIs remain identical — only the names change.

### Migration Plan

#### Source Directory

```
src/orchestration/           →  src/squadron/
src/orchestration/__init__.py    →  src/squadron/__init__.py
src/orchestration/cli/           →  src/squadron/cli/
src/orchestration/engine/        →  src/squadron/engine/
src/orchestration/providers/     →  src/squadron/providers/
src/orchestration/review/        →  src/squadron/review/
src/orchestration/config/        →  src/squadron/config/
...                                 (all subdirectories follow)
```

#### pyproject.toml Changes

```toml
# Before
[project]
name = "orchestration"

[project.scripts]
orchestration = "orchestration.cli.app:app"

# After
[project]
name = "squadron"

[project.scripts]
sq = "squadron.cli.app:app"
squadron = "squadron.cli.app:app"
```

#### Import Updates

Every Python file in `src/` and `tests/` that imports from `orchestration`:

```python
# Before
from orchestration.engine.registry import AgentRegistry
from orchestration.providers.base import AgentProvider

# After
from squadron.engine.registry import AgentRegistry
from squadron.providers.base import AgentProvider
```

#### Config Path Migration

```python
# In squadron/config/manager.py (or wherever config paths are resolved)

def _get_config_dir() -> Path:
    new_dir = Path.home() / ".config" / "squadron"
    old_dir = Path.home() / ".config" / "orchestration"

    if not new_dir.exists() and old_dir.exists():
        shutil.copytree(old_dir, new_dir)
        (old_dir / "MIGRATED.txt").write_text(
            "Config migrated to ~/.config/squadron/\n"
            "This directory can be safely deleted.\n"
        )
        # Print once to stderr so it doesn't corrupt piped output
        print("Migrated config from ~/.config/orchestration/ → ~/.config/squadron/",
              file=sys.stderr)

    return new_dir
```

Project-level config: code that looks for `.orchestration.toml` should look for `.squadron.toml` instead. No automatic migration for project-level config — it's a single file the developer renames manually. Document this in the migration note.

#### Daemon Paths

Wherever the daemon stores its socket or PID file (likely under `~/.config/orchestration/` or `/tmp/orchestration-*`), update the path construction to use `squadron`. The config migration above handles the `~/.config/` case. Any `/tmp/` paths just start using the new name — stale old-name files are harmless and cleaned up by the OS.

## Technical Decisions

### Dual Entry Points (sq + squadron)

`sq` is the daily-driver command. `squadron` is the explicit long form for scripts, documentation, and discoverability (`squadron --help` is clearer than `sq --help` for a first-time user). Both point to the same Typer app. No alias mechanism needed — pyproject.toml supports multiple script entries natively.

### Copy-not-move for Config Migration

The old `~/.config/orchestration/` directory is left in place rather than renamed. Reasons: if the developer has multiple machines or environments at different stages of the rename, the old directory still works. The `MIGRATED.txt` file signals that the copy happened. Deletion is the developer's choice.

### Single Commit

The entire rename lands in one commit. This makes `git bisect` clean — there's no intermediate state where half the code says "orchestration" and half says "squadron." The commit message is `refactor: rename orchestration → squadron` with a body listing the major categories of changes.

## Integration Points

### Provides to Other Slices

- **Claude Code Commands (slice 118):** Command files reference `sq` as the CLI binary. This slice must land first.
- **MCP Server (slice 13):** The MCP server package name, tool prefixes, and documentation will use "squadron."
- **Conversation Persistence (slice 115):** Database paths and logging namespaces use the new name.
- **All future slices:** Import paths, config paths, and CLI references use `squadron`/`sq` going forward.

### Consumes from Other Slices

- **All completed slices (100–114):** This slice renames the artifacts they produced. No behavioral dependency.

## Success Criteria

### Functional Requirements

- `sq --help` displays the squadron CLI help with all existing commands
- `squadron --help` displays identical output
- `sq spawn --name test --type sdk` works identically to the old `orchestration spawn`
- `sq review arch`, `sq review code`, `sq review tasks` all function
- `sq auth status` shows provider credentials
- `sq serve` starts the daemon
- `sq config list` shows configuration
- Config migration: on first run, if `~/.config/orchestration/` exists and `~/.config/squadron/` doesn't, config is copied and a notice is printed
- `.squadron.toml` is recognized as project-level config
- All existing tests pass with updated imports

### Technical Requirements

- Zero references to the string `"orchestration"` in `src/squadron/` (enforced by grep in final validation)
  - Exception: migration code that references the old path, and any historical notes in comments
- `ruff check` passes
- `ruff format --check` passes
- `pyright` (or mypy) passes with zero errors
- `pytest` full suite passes
- `uv sync` succeeds with the new package name

## Implementation Notes

### Suggested Implementation Order

1. **Rename source directory** — `mv src/orchestration src/squadron`. Update `pyproject.toml` name and entry points. Run `uv sync`. Verify `sq --help` works.
2. **Update all imports** — Mechanical find-and-replace across `src/` and `tests/`. Run `ruff check` to catch any missed references.
3. **Update config paths** — Change path construction in config manager. Add migration logic. Update project-level config filename.
4. **Update daemon paths** — Socket/PID path construction.
5. **Update error messages and user-facing strings** — Grep for `"orchestration"` in all `.py` files.
6. **Update documentation** — README, CLAUDE.md, any other markdown.
7. **Update logger names** — Grep for logger instantiation.
8. **Final validation** — `grep -r "orchestration" src/ tests/` to find stragglers. Run full test suite. Run type checker and linter.
9. **Single commit** — `refactor: rename orchestration → squadron`

### Testing Strategy

No new tests. All existing tests are updated (imports only) and must pass. The validation grep (`grep -r "orchestration" src/`) serves as the acceptance test for completeness.

### Agent Suitability

This is an ideal agent task. It's mechanical, well-defined, and has a clear validation criterion (grep returns zero hits). The implementing agent needs the full source tree in its working directory. Suggested model: Sonnet (it's a refactor, not a design task). The only subtlety is the config migration logic, which requires a small amount of new code.
