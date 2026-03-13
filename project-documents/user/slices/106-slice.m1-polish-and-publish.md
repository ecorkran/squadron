---
docType: slice-design
slice: m1-polish-and-publish
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [foundation, sdk-agent-provider, cli-foundation, review-workflow-templates]
interfaces: []
status: complete
dateCreated: 20260222
dateUpdated: 20260222
---

# Slice Design: M1 Polish & Publish

## Overview

Polish the M1 deliverable for public release. This slice bundles the UX improvements, configuration persistence, and documentation needed to make the orchestration CLI presentable and usable by external developers. The output is a tool that someone can discover through a blog post, clone, install, and run their first review within minutes.

## Value

Adoption enablement. The orchestration CLI already works — this slice makes it work *for other people*. Specific value:

- **Verbosity levels** reduce noise for regular use while preserving detail when debugging
- **Persistent config** eliminates repetitive `--cwd` flags, the single biggest friction point in daily use
- **Text color improvements** make review output scannable at a glance
- **`--rules` flag** lets users point code reviews at specific rules files without building language detection
- **README and documentation** are the difference between "my side project" and "tool you can adopt"

## Technical Scope

### Included

- **Verbosity levels**: Default shows headings + verdict only; `-v` shows full findings; `-vv` shows tool usage details
- **Persistent configuration**: `orchestration config set KEY VALUE` / `orchestration config get KEY` / `orchestration config list`; file-based storage at `~/.config/orchestration/config.toml`; project-level override via `.orchestration.toml` in cwd
- **Text color improvements**: Brighter body text (matching heading luminance); ensure output is readable across common terminal backgrounds without setting background color
- **`--rules` flag on `review code`**: Takes a path to a rules file, contents appended to the system prompt; composable with `--diff` and `--files`
- **README**: Installation, quickstart (first review in <5 minutes), command reference, configuration, examples
- **Additional docs**: Template authoring guide (for future user-defined templates), architecture overview for contributors

### Excluded

- Language detection or automatic rule routing — explicit `--rules` flag is sufficient for M1
- User-defined templates (YAML) — documented as a future capability, not implemented
- CI integration / structured JSON output — post-M1
- Interactive review mode — post-M1
- Hook callbacks — schema is ready, no callbacks wired

## Dependencies

### Prerequisites

- **Review Workflow Templates** (slice 105, complete): The review CLI and runner that this slice polishes.
- **CLI Foundation** (slice 103, complete): Typer app structure that gains the `config` subcommand.

### External Packages

- **tomli** / **tomllib** (Python 3.11+ has tomllib built-in): TOML config file reading
- **tomli-w**: TOML config file writing (tomllib is read-only)
- All other dependencies already in pyproject.toml

## Technical Decisions

### Configuration System Design

Two config file locations with clear precedence:

1. **User-level**: `~/.config/orchestration/config.toml` — personal defaults
2. **Project-level**: `.orchestration.toml` in the working directory — project-specific overrides

Precedence (highest to lowest): CLI flag → project config → user config → built-in default.

Initial configurable keys:

| Key | Type | Default | Description |
|---|---|---|---|
| `cwd` | `string` | `.` (current dir) | Default working directory for review commands |
| `verbosity` | `int` | `0` | Default verbosity (0=summary, 1=findings, 2=tool details) |
| `default_rules` | `string` | `null` | Default rules file path for code reviews |

The config system is deliberately minimal — a flat key-value store with typed access. No nested sections, no complex merging logic. TOML is chosen over JSON (comments allowed, human-editable) and YAML (no additional dependency, less ambiguity).

```toml
# ~/.config/orchestration/config.toml
cwd = "~/source/repos/manta/orchestration/project-documents/user"
verbosity = 1
```

```toml
# .orchestration.toml (project-level, overrides user config)
cwd = "./project-documents/user"
default_rules = "./rules/python.md"
```

### Config CLI Commands

```
orchestration config set KEY VALUE    # Set a config value (user-level by default)
orchestration config set KEY VALUE --project  # Set in project-level config
orchestration config get KEY          # Show resolved value and source
orchestration config list             # Show all config with sources
orchestration config path             # Show config file locations
```

Example:
```
$ orchestration config set cwd ~/source/repos/manta/orchestration
Set cwd = ~/source/repos/manta/orchestration (user config)

$ orchestration config list
  cwd         ~/source/repos/manta/orchestration  (user)
  verbosity   0                                    (default)
```

### Verbosity Levels

| Level | Flag | Shows |
|---|---|---|
| 0 (default) | (none) | Verdict badge + finding headings with severity |
| 1 | `-v` | Above + full finding descriptions |
| 2 | `-vv` | Above + tool usage details (which files read, commands run) |

Verbosity applies to the `display_result` function in the review runner. The review agent produces the same output regardless of verbosity — the display layer filters what's shown. This means the full output is always available if the user re-runs with `-v`.

Configurable default via `orchestration config set verbosity 1`.

### Text Color Strategy

The review output must be readable across terminal backgrounds without setting the background color. Current issue: green body text is low-contrast on warm/light backgrounds.

Approach:
- **Severity badges**: Keep high-saturation colors — bright green for PASS, yellow/amber for CONCERN, red for FAIL. These are short and benefit from color coding.
- **Finding headings**: White/bright-white (high luminance, readable on any background)
- **Body text**: Default terminal foreground (no color override) for descriptions. This respects the user's terminal theme.
- **File paths and code references**: Cyan or blue (works on both dark and light backgrounds)

Use `rich` markup consistently. No ANSI escape codes — let `rich` handle terminal capability detection.

### `--rules` Flag

```
orchestration review code --rules path/to/rules.md [--cwd DIR] [--files PATTERN] [--diff REF]
```

Implementation: the runner reads the rules file content and appends it to the code template's system prompt:

```python
system_prompt = template.system_prompt
if rules_path:
    rules_content = Path(rules_path).read_text()
    system_prompt += f"\n\n## Additional Review Rules\n\n{rules_content}"
```

The rules file is read by the orchestration CLI (not the review agent) and injected into the system prompt. This is simpler than having the agent Read the rules file and ensures the rules are always applied regardless of agent behavior.

Configurable default via `orchestration config set default_rules ./rules/python.md`.

## Package Structure

New and modified files:

```
src/orchestration/
├── config/
│   ├── __init__.py
│   ├── manager.py          # Config loading, merging, persistence
│   └── keys.py             # Typed config key definitions and defaults
├── cli/commands/
│   ├── config.py           # NEW: config subcommand
│   └── review.py           # MODIFIED: verbosity flag, --rules flag, config integration
└── review/
    └── runner.py            # MODIFIED: verbosity-aware display, rules injection

tests/
├── config/
│   ├── test_manager.py     # Config loading, merging, precedence
│   └── test_cli_config.py  # Config CLI commands
└── review/
    └── test_runner.py       # MODIFIED: verbosity levels, rules injection

docs/
├── README.md               # Primary documentation
├── COMMANDS.md             # Full command reference
└── TEMPLATES.md            # Template authoring guide (for future user templates)
```

## Data Flow

### Config Resolution

```
CLI command invoked
  │
  ▼
Load user config: ~/.config/orchestration/config.toml
  │ (may not exist — all keys have defaults)
  ▼
Load project config: {cwd}/.orchestration.toml
  │ (may not exist — user config values carry through)
  ▼
Apply CLI flags (override any config value)
  │
  ▼
Resolved config available to command handler
```

### Review with Config + Rules

```
$ orchestration review code --diff main -v
  │
  ▼
Resolve config:
  │ cwd: ~/source/repos/manta/orchestration  (from user config)
  │ verbosity: 1  (from -v flag, overrides default 0)
  │ default_rules: ./rules/python.md  (from project config)
  ▼
Build review:
  │ template = get_template("code")
  │ system_prompt = template.system_prompt + rules file content
  │ options = ClaudeAgentOptions(cwd=resolved_cwd, ...)
  ▼
Execute via ClaudeSDKClient (same as slice 105)
  ▼
Display with verbosity=1:
  │ ✅ Verdict badge
  │ ✅ Finding headings with severity
  │ ✅ Full finding descriptions
  │ ❌ Tool usage details (requires -vv)
```

## Integration Points

### Provides

- **Config system** is available to all future CLI commands, not just reviews. Any command can read `get_config("key")` to access persistent settings.
- **README** is the entry point for external adoption.

### Consumes

- **Review runner** (slice 105): Display formatting, system prompt construction
- **CLI app** (slice 103): Typer entry point for `config` subcommand and verbosity flag

## Success Criteria

### Functional Requirements

- `orchestration config set cwd PATH` persists the value to `~/.config/orchestration/config.toml`
- `orchestration config set KEY VALUE --project` persists to `.orchestration.toml`
- `orchestration config get KEY` shows resolved value and which source it came from
- `orchestration config list` shows all keys with values and sources
- Review commands respect `cwd` from config when `--cwd` flag is not provided
- CLI `--cwd` flag overrides config value
- Review output at verbosity 0 shows only verdict + finding headings
- Review output at verbosity 1 (`-v`) shows verdict + headings + full descriptions
- Review output at verbosity 2 (`-vv`) shows all details including tool usage
- `orchestration config set verbosity 1` makes `-v` the default
- `orchestration review code --rules path/to/rules.md` appends rules file content to the system prompt
- `orchestration config set default_rules path/to/rules.md` makes rules load by default for code reviews
- Review output text colors are readable on both dark and light terminal backgrounds
- README enables a new user to install and run their first review in under 5 minutes

### Technical Requirements

- All tests pass with `ClaudeSDKClient` mocked at the import boundary
- Config manager has test coverage for: load from both files, precedence merging, missing files, CLI flag override
- Verbosity filtering has test coverage for all three levels
- Rules injection has test coverage (rules content appears in system prompt)
- Type checker passes with zero errors
- `ruff check` and `ruff format` pass

## Implementation Notes

### Suggested Implementation Order

1. **Config manager** (effort: 1/5) — TOML read/write, precedence merging, typed access. No CLI yet.
2. **Config CLI commands** (effort: 1/5) — `config set`, `config get`, `config list`, `config path`.
3. **Verbosity levels + text colors** (effort: 1/5) — Modify `display_result` in review runner. Add `-v` flag to review commands. Wire config default.
4. **`--rules` flag + config integration** (effort: 1/5) — Rules file reading, system prompt injection, config-based `cwd` and `default_rules` resolution in review commands.
5. **README + documentation** (effort: 2/5) — This is the most time-intensive item. README with installation, quickstart, command reference, examples. COMMANDS.md reference. TEMPLATES.md guide.
6. **Tests** (effort: 1/5) — Config manager, config CLI, verbosity levels, rules injection.

### Documentation Strategy

The README is the most important deliverable for adoption. Structure:

- **Hero section**: One sentence explaining what it does, install command, one example review command
- **Quickstart**: Clone → install → configure credentials → run first review (target: 5 minutes)
- **Command reference**: All commands with examples (reference COMMANDS.md for full detail)
- **Configuration**: User vs project config, all keys, examples
- **Review templates**: What each template does, when to use it, example output
- **Architecture**: Brief overview for contributors (link to arch doc)

The quickstart is the critical path. If someone reads a blog post, clicks through to GitHub, and can't get a review running in 5 minutes, they bounce.

### Blog Post Content (Not Part of Implementation)

The implementing agent should NOT write the blog post — that's Erik's voice. But the README should provide all the raw material: clear value proposition, compelling examples, architecture overview. The screenshot of the tool reviewing its own task breakdown is the hero image.
