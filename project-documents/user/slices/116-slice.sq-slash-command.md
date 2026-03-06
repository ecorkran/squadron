---
docType: slice-design
slice: sq-slash-command
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [project-rename]
interfaces: [composed-workflows]
status: complete
dateCreated: 20260305
dateUpdated: 20260306
---

# Slice Design: Claude Code Commands — sq Wrappers

## Overview

Create markdown command files that expose squadron CLI capabilities as Claude Code slash commands. Commands are invoked as `/sq:spawn`, `/sq:review-arch`, etc. within Claude Code sessions. Each command file contains a prompt that instructs Claude to execute the corresponding `sq` CLI command via the Bash tool, passing through user-supplied arguments.

The command files are maintained in the squadron repo under `commands/` as the source of truth. A CLI install/uninstall mechanism (`sq install-commands` / `sq uninstall-commands`) copies them into `~/.claude/commands/` for user-level availability.

## Value

Eliminates context-switching between Claude Code and the terminal. Developers working inside Claude Code can invoke squadron reviews, spawn agents, and check status without leaving their AI-assisted workflow. The commands are thin wrappers — they add no logic, just bridge the invocation gap.

This also establishes the command file infrastructure that slice 117 (Composed Workflows) builds on.

## Technical Scope

### Included

- Eight command markdown files in `commands/sq/`:
  - `spawn.md` — `/sq:spawn`
  - `task.md` — `/sq:task`
  - `list.md` — `/sq:list`
  - `shutdown.md` — `/sq:shutdown`
  - `review-arch.md` — `/sq:review-arch`
  - `review-tasks.md` — `/sq:review-tasks`
  - `review-code.md` — `/sq:review-code`
  - `auth-status.md` — `/sq:auth-status`
- CLI `sq install-commands` command that copies command files to the target directory
- CLI `sq uninstall-commands` command that removes installed command files
- `--target` flag for custom install directory (default: `~/.claude/commands/`)
- Unit tests for install/uninstall logic
- Manual verification instructions for command execution

### Excluded

- Composed/chained workflow commands (slice 117)
- Project-level command installation (`.claude/commands/` within a repo) — user-level only for v1
- Auto-install on package install (pip/uv post-install hooks are fragile)
- Command files for `sq serve`, `sq message`, `sq history`, `sq models`, `sq config` — these are less frequently needed from within Claude Code and can be added later

## Dependencies

### Prerequisites

- **Project Rename (slice 115)** (complete): CLI entry point is `sq`.

### External Packages

None. This slice uses only stdlib (`shutil`, `pathlib`) and Typer (already in pyproject.toml).

## Technical Decisions

### Claude Code Command File Format

Claude Code custom slash commands are markdown files placed in `~/.claude/commands/`. The filename (minus `.md`) becomes the command name. Subdirectories create namespaced commands: `commands/sq/spawn.md` becomes `/sq:spawn`.

The file content becomes a user message prompt when the command is invoked. `$ARGUMENTS` is replaced with the full argument string the user provides after the command name.

### Command Content Pattern

Each command file follows a consistent pattern: instruct Claude to run the `sq` CLI command and interpret the output.

```markdown
Run the following command and report the results:

`sq spawn $ARGUMENTS`

If the command fails, show the error and suggest corrections based on the available flags. Run `sq spawn --help` if the user needs usage information.
```

This pattern:
- Delegates execution to the Bash tool (Claude interprets the backtick-wrapped command as something to execute)
- Passes arguments through transparently
- Provides graceful error handling without duplicating CLI help text
- Keeps command files minimal and maintainable

### Review Commands: Structured Arguments

The review commands (`review-arch`, `review-tasks`, `review-code`) need slightly more structured prompts because they have required arguments with specific flags:

```markdown
Run an architectural review using squadron:

`sq review arch $ARGUMENTS`

This command requires:
- A positional argument: the document to review
- `--against`: the architecture/context document to review against

Example: `sq review arch slices/105-slice.review-workflow-templates.md --against architecture/100-arch.orchestration-v2.md`

Report the review results. If the command fails, show the error and suggest corrections.
```

### Source Directory Structure

Command files live in the repo at `commands/sq/`:

```
commands/
└── sq/
    ├── spawn.md
    ├── task.md
    ├── list.md
    ├── shutdown.md
    ├── review-arch.md
    ├── review-tasks.md
    ├── review-code.md
    └── auth-status.md
```

The `sq/` subdirectory maps directly to the Claude Code namespace. When installed to `~/.claude/commands/`, the structure is preserved, producing `/sq:spawn`, `/sq:task`, etc.

### Install Mechanism

`sq install-commands` copies the `commands/` directory contents into the target directory (default `~/.claude/commands/`). The source files are bundled with the package.

```python
@app.command("install-commands")
def install_commands(
    target: str = typer.Option(
        "~/.claude/commands",
        "--target",
        help="Target directory for command files",
    ),
) -> None:
    """Install squadron slash commands for Claude Code."""
```

Behavior:
- Resolves `~` in the target path
- Creates the target directory (and `sq/` subdirectory) if it doesn't exist
- Copies each `.md` file from the bundled `commands/sq/` to `{target}/sq/`
- Overwrites existing files (updates to latest version)
- Reports what was installed

### Uninstall Mechanism

`sq uninstall-commands` removes the `sq/` subdirectory from the target directory.

```python
@app.command("uninstall-commands")
def uninstall_commands(
    target: str = typer.Option(
        "~/.claude/commands",
        "--target",
        help="Target directory to remove commands from",
    ),
) -> None:
    """Remove squadron slash commands from Claude Code."""
```

Behavior:
- Removes `{target}/sq/` directory and all files within it
- Does not touch other command files in the target directory
- Reports what was removed (or that nothing was found)

### Bundling Command Files in the Package

The `commands/` directory is at the repo root. For package distribution, these files must be included in the wheel. The `pyproject.toml` configuration:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/squadron"]

[tool.hatch.build.targets.wheel.force-include]
"commands" = "squadron/commands"
```

At runtime, the install command locates the bundled files via `importlib.resources`:

```python
from importlib.resources import files

def _get_commands_dir() -> Path:
    """Locate the bundled commands directory."""
    return Path(str(files("squadron") / "commands"))
```

### No Daemon Required

These commands invoke `sq` as a subprocess (via Claude's Bash tool). Commands like `sq spawn`, `sq task`, `sq list` already require the daemon to be running — they produce clear error messages if it isn't. The command files don't need to handle daemon lifecycle.

Review commands (`sq review arch/tasks/code`) use the SDK directly and don't need the daemon at all.

## Package Structure

```
commands/                          # Source of truth (repo root)
└── sq/
    ├── spawn.md
    ├── task.md
    ├── list.md
    ├── shutdown.md
    ├── review-arch.md
    ├── review-tasks.md
    ├── review-code.md
    └── auth-status.md

src/squadron/cli/commands/
└── install.py                     # install-commands / uninstall-commands

tests/cli/
└── test_install_commands.py       # Install/uninstall logic tests
```

## Command File Specifications

### `/sq:spawn`

```markdown
Run the following command:

`sq spawn $ARGUMENTS`

Common flags: `--name NAME` (required), `--type sdk|openai`, `--provider PROVIDER`, `--profile PROFILE`, `--cwd PATH`, `--model MODEL`, `--system-prompt TEXT`.

If no arguments are provided, run `sq spawn --help` and show the usage.
```

### `/sq:task`

```markdown
Run the following command:

`sq task $ARGUMENTS`

This sends a one-shot task to a named agent. Format: `sq task AGENT_NAME "prompt text"`

If no arguments are provided, run `sq task --help` and show the usage.
```

### `/sq:list`

```markdown
Run the following command and display the results:

`sq list $ARGUMENTS`

Optional flags: `--state STATE`, `--provider PROVIDER`. Shows all active agents with their type, state, and provider.
```

### `/sq:shutdown`

```markdown
Run the following command:

`sq shutdown $ARGUMENTS`

Provide an agent name to shut down a specific agent, or use `--all` to shut down all agents.
```

### `/sq:review-arch`

```markdown
Run an architectural review using squadron:

`sq review arch $ARGUMENTS`

Required arguments:
- Positional: path to the document to review
- `--against PATH`: architecture or context document to review against

Optional: `--cwd DIR`, `--model MODEL`, `--output FORMAT`, `-v`/`-vv` for verbosity.

Example: `sq review arch slices/105-slice.md --against architecture/100-arch.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
```

### `/sq:review-tasks`

```markdown
Run a task plan review using squadron:

`sq review tasks $ARGUMENTS`

Required arguments:
- Positional: path to the task breakdown file
- `--against PATH`: parent slice design to review against

Optional: `--cwd DIR`, `--model MODEL`, `--output FORMAT`, `-v`/`-vv` for verbosity.

Example: `sq review tasks tasks/105-tasks.md --against slices/105-slice.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
```

### `/sq:review-code`

```markdown
Run a code review using squadron:

`sq review code $ARGUMENTS`

Optional flags:
- `--cwd DIR`: project directory to review
- `--files PATTERN`: glob pattern to scope the review
- `--diff REF`: git ref to diff against (reviews changed files)
- `--rules PATH`: path to additional rules file
- `--model MODEL`: model override
- `-v`/`-vv`: verbosity level

Example: `sq review code --diff main` or `sq review code --files "src/**/*.py"`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
```

### `/sq:auth-status`

```markdown
Run the following command and display the results:

`sq auth status $ARGUMENTS`

Shows configured credentials and their validation status for each provider profile.
```

## Integration Points

### Provides to Other Slices

- **Composed Workflows (slice 117):** Establishes the `commands/` directory structure, the `sq/` namespace, and the install mechanism. Slice 117 adds `commands/workflow/` using the same infrastructure.

### Consumes from Prior Slices

- **Project Rename (slice 115):** CLI entry point is `sq`.
- **CLI Foundation (slice 103):** Typer app structure for adding `install-commands` / `uninstall-commands`.
- **Review Workflow Templates (slice 105):** Review commands that the slash commands wrap.
- **Auth Strategy (slice 114):** `sq auth status` command that `/sq:auth-status` wraps.

## Success Criteria

### Functional Requirements

- All eight command `.md` files exist in `commands/sq/` and contain valid Claude Code command prompts
- `sq install-commands` copies command files to `~/.claude/commands/sq/`
- `sq install-commands --target /custom/path` installs to the specified directory
- `sq uninstall-commands` removes the `sq/` directory from `~/.claude/commands/`
- Install creates target directories if they don't exist
- Install overwrites existing files (enables updates)
- Uninstall only removes `sq/` subdirectory, not other command files
- Uninstall reports gracefully if nothing is installed
- Each command file references the correct `sq` subcommand with appropriate arguments
- Review command files include usage examples and required argument documentation

### Technical Requirements

- `commands/` directory included in package wheel via `pyproject.toml` build config
- `importlib.resources` used to locate bundled command files at runtime
- All tests pass with `pytest`
- `pyright` passes with zero errors
- `ruff check` and `ruff format` pass

## Implementation Notes

### Suggested Implementation Order

1. **Command file authoring** (effort: 0.5/5) — Write all eight `.md` files in `commands/sq/`. The content is the most design-sensitive part: prompts need to be clear enough that Claude executes the right command, concise enough to not waste context.

2. **Package bundling** (effort: 0.5/5) — Update `pyproject.toml` to include `commands/` in the wheel. Verify with `importlib.resources` that files are locatable at runtime.

3. **Install/uninstall CLI commands** (effort: 0.5/5) — `install.py` with two Typer commands. Simple file copy/delete operations with path resolution and user feedback.

4. **Tests** (effort: 0.5/5) — Test install/uninstall behavior using `tmp_path`. Verify file creation, overwrite, cleanup, and error cases.

5. **Manual verification** (effort: 0.5/5) — Install commands, verify they appear in Claude Code's `/` menu, execute a few to confirm they work end-to-end.

### Testing Strategy

- **Install tests:** Verify files are copied to target, directories created, existing files overwritten, correct file count.
- **Uninstall tests:** Verify `sq/` directory removed, other files untouched, graceful when nothing installed.
- **Source verification:** Verify all expected command files exist in `commands/sq/` and are non-empty.
- **No integration tests with Claude Code:** Command execution depends on Claude Code runtime. Manual verification during implementation is sufficient.
