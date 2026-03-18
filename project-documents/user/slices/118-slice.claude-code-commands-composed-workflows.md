---
docType: slice-design
slice: claude-code-commands-composed-workflows
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [sq-slash-command, context-forge-workflow-navigation]
interfaces: []
dateCreated: 20260317
dateUpdated: 20260317
status: not_started
---

# Slice Design: Claude Code Commands — Composed Workflows

## Overview

Create higher-level Claude Code command files in a `workflow/` namespace that chain squadron and context-forge together, leveraging Claude Code's reasoning to interpret results and suggest next actions. Unlike the `sq/` commands (thin wrappers around single CLI calls), these commands orchestrate multi-step workflows — running multiple tools, interpreting their combined output, and guiding the developer toward the right next action.

Three commands:
- `/workflow:next-step` — project state assessment and action recommendation
- `/workflow:design-review` — context-aware architectural review
- `/workflow:ensemble-review` — multi-provider review with synthesis

## Value

Reduces the cognitive overhead of "what do I do next?" and "how do I run a proper review?" into single slash commands. The developer invokes one command and Claude Code handles the multi-step orchestration — querying project state, assembling context, running reviews, and synthesizing results. This is especially valuable for the Context Forge workflow where the correct sequence of actions (check status → build context → run review → advance phase) is well-defined but tedious to execute manually.

These commands also serve as a lightweight ensemble pattern — running the same review across multiple AI providers and synthesizing results — before the full message bus (M2) exists.

## Technical Scope

### Included

- Three command markdown files in `commands/workflow/`:
  - `next-step.md` — `/workflow:next-step`
  - `design-review.md` — `/workflow:design-review`
  - `ensemble-review.md` — `/workflow:ensemble-review`
- Update to `uninstall_commands` to also remove the `workflow/` subdirectory
- Update to existing tests to verify both `sq/` and `workflow/` directories are handled
- Manual verification instructions

### Excluded

- New Python code beyond the uninstall fix — these are markdown command files only
- Commands that require the squadron daemon (all three use `cf` and `sq review`, neither of which needs the daemon)
- Auto-detection of project type or context-forge availability — commands fail explicitly if `cf` is not available
- Additional workflow commands beyond the three specified — iterate based on real usage

## Dependencies

### Prerequisites

- **Claude Code Commands — sq Wrappers (slice 116)** (complete): Establishes `commands/` directory structure, `sq/` namespace, install/uninstall mechanism, and wheel bundling via `force-include`.
- **Context-Forge workflow navigation** (external): The `cf` CLI must be installed and a context-forge project initialized in the working directory. Commands: `cf status`, `cf next`, `cf build`. These are provided by the context-forge MCP server and its associated CLI.

### External Packages

None. Command files are plain markdown. The uninstall fix uses only `shutil` and `pathlib` (already imported).

## Technical Decisions

### Command Namespace

Commands live in `commands/workflow/` (not `commands/sq/`). This creates the `/workflow:*` namespace in Claude Code, keeping composed workflows visually distinct from single-command wrappers. The existing install mechanism in [install.py](src/squadron/cli/commands/install.py) already iterates all subdirectories of `commands/`, so `workflow/` files are installed automatically — no install code changes needed.

### Command Design Philosophy

Each command file is a multi-step prompt that instructs Claude Code to:
1. Run one or more CLI commands (using `!` backtick execution)
2. Interpret the combined output
3. Provide actionable recommendations or synthesized results

Commands are **opinionated but overridable** — they have a default behavior that works for the common case, but accept `$ARGUMENTS` for customization. For example, `/workflow:design-review` defaults to reviewing the current slice against the architecture doc, but the user can override both paths.

### No YAML Frontmatter in Command Files

The existing `sq/` command files do not use YAML frontmatter (they are plain markdown). The `cf/` commands installed by context-forge do use frontmatter with `description` and `allowed-tools` fields. For consistency with the `sq/` pattern already established in this project, the `workflow/` commands will **not** use frontmatter. Claude Code discovers commands by filename; frontmatter is optional and adds no functional value for these commands.

**Update:** After reviewing the `cf/` commands, the `description` field in frontmatter is valuable — Claude Code uses it for auto-discovery and the `/` menu. The `workflow/` commands will include minimal frontmatter with `description` only, matching the pattern used by `cf/` commands. No `allowed-tools` constraint since these commands need access to Bash, Read, and other tools.

### Context-Forge Availability

Commands that depend on `cf` (all three) will instruct Claude to run the `cf` command and handle failure explicitly — if `cf` is not installed or no project is initialized, the error output from `cf` itself is sufficient. The command prompts include a note to check `cf` availability if the command fails. No silent fallbacks.

### Ensemble Review Provider Strategy

`/workflow:ensemble-review` runs `sq review` multiple times with different `--provider` flags. The command file specifies a default set of providers but allows override via `$ARGUMENTS`. The synthesis step asks Claude Code to compare results across providers, identify consensus findings, and flag divergent opinions.

Default providers for ensemble: the command will instruct Claude to check available providers via `sq auth status` and use all configured providers. This avoids hardcoding provider names that may not be configured.

## Command File Specifications

### `/workflow:next-step`

**Purpose:** Assess current project state and recommend the next action.

**Flow:**
1. Run `cf status` to get current phase, slice, and task progress
2. Run `cf next` to get context-forge's recommended next action
3. Interpret both outputs together
4. Recommend a specific action: run a review, start implementation, advance phase, or address blockers

**Content:**

```markdown
---
description: Assess project state and recommend the next action (uses cf + sq)
---

Assess the current project state and recommend what to do next.

Step 1 — Run these commands and review their output:

`cf status`

`cf next`

Step 2 — Based on the output, recommend a specific next action. Consider:
- If a review is needed, suggest the exact `/sq:review-*` or `/workflow:design-review` command with arguments
- If implementation should start, suggest `/cf:build` to load context
- If the current phase is complete, suggest advancing to the next phase
- If there are blockers or incomplete prerequisites, flag them

Keep the recommendation to 2-3 actionable sentences. Don't restate the status output — the user can see it.

If `cf` is not available, inform the user that context-forge must be installed and a project initialized.
```

### `/workflow:design-review`

**Purpose:** Run an architectural review with automatically assembled context.

**Flow:**
1. Run `cf status` to identify the current slice and architecture document
2. Run `cf build` to assemble the full context (or use the slice and arch paths from status)
3. Run `sq review arch` with the current slice design against the architecture document
4. Present results with actionable recommendations

**Content:**

```markdown
---
description: Run an architectural review with auto-assembled context (uses cf + sq)
---

Run an architectural review for the current slice design.

Step 1 — Get the current project context:

`cf status`

Step 2 — From the status output, identify:
- The current slice design file path (under `project-documents/user/slices/`)
- The architecture document path (under `project-documents/user/architecture/`)

If `$ARGUMENTS` are provided, use them to override the slice and/or architecture paths. Format: `/workflow:design-review [slice-path] [--against arch-path]`

Step 3 — Run the architectural review:

`sq review arch <slice-path> --against <arch-path> -v`

Step 4 — Present the review results. If the verdict is FAIL or CONCERNS:
- Highlight the top findings
- Suggest specific fixes
- Offer to re-run the review after fixes are applied

If `cf` is not available, ask the user to provide the slice and architecture paths directly, then proceed with step 3.
```

### `/workflow:ensemble-review`

**Purpose:** Run the same review across multiple providers and synthesize results.

**Flow:**
1. Check available providers via `sq auth status`
2. Run `sq review arch` (or `sq review code` / `sq review tasks`) with each configured provider
3. Synthesize results — identify consensus findings and divergent opinions
4. Present a unified assessment

**Content:**

```markdown
---
description: Run a review across multiple AI providers and synthesize results
---

Run an ensemble review — the same review executed by multiple AI providers, then synthesized.

Step 1 — Check which providers are configured:

`sq auth status`

Step 2 — Determine the review type and target from `$ARGUMENTS`. Default: architectural review of the current slice.

If no arguments provided, run `cf status` to identify the current slice and architecture document, then use `sq review arch <slice> --against <arch>`.

Supported review types (specify as first argument):
- `arch` — architectural review (default)
- `code` — code review
- `tasks` — task plan review

Step 3 — Run the review with each configured provider. For each provider shown as configured in step 1:

`sq review <type> <target-args> --provider <provider-name> -v`

Run each provider sequentially and capture the results.

Step 4 — Synthesize the results:
- **Consensus findings**: Issues flagged by all or most providers
- **Unique insights**: Findings from only one provider that seem valuable
- **Divergent opinions**: Areas where providers disagree — note the disagreement and your assessment
- **Overall verdict**: Your synthesized pass/concerns/fail assessment

Present the synthesis clearly. The individual provider results are supporting evidence — lead with the synthesis.

If only one provider is configured, run the review with that provider and note that ensemble comparison requires multiple providers.
```

## Package Structure

```
commands/
├── sq/                          # Existing (slice 116)
│   ├── spawn.md
│   ├── task.md
│   ├── list.md
│   ├── shutdown.md
│   ├── review-arch.md
│   ├── review-tasks.md
│   ├── review-code.md
│   └── auth-status.md
└── workflow/                    # New (this slice)
    ├── next-step.md
    ├── design-review.md
    └── ensemble-review.md

src/squadron/cli/commands/
└── install.py                   # Minor update: uninstall handles workflow/ too
```

## Integration Points

### Provides to Other Slices

- **Pattern for future composed commands:** Establishes the `workflow/` namespace and the multi-step command prompt pattern. Future workflow commands (e.g., `/workflow:implement`, `/workflow:ship`) follow the same approach.
- **Ensemble review pattern:** Demonstrates multi-provider review synthesis that can inform the design of the Ensemble Review slice (slice 130) when it moves to formal multi-agent orchestration.

### Consumes from Prior Slices

- **sq Wrappers (slice 116):** `commands/` directory structure, install/uninstall mechanism, wheel bundling.
- **Review Workflow Templates (slice 105):** `sq review arch/tasks/code` commands that the workflow commands invoke.
- **Auth Strategy (slice 114):** `sq auth status` for provider discovery in ensemble review.

### External Dependencies

- **Context-Forge CLI:** `cf status`, `cf next`, `cf build` commands. These are provided by the context-forge project (external to squadron). Commands degrade gracefully — if `cf` is unavailable, they instruct the user to provide paths manually or install context-forge.

## Success Criteria

### Functional Requirements

- Three command `.md` files exist in `commands/workflow/` with valid multi-step prompts
- `/workflow:next-step` runs `cf status` + `cf next` and produces an actionable recommendation
- `/workflow:design-review` identifies the current slice/arch from `cf status` and runs `sq review arch`
- `/workflow:ensemble-review` discovers providers from `sq auth status` and runs reviews across all configured providers
- All three commands accept `$ARGUMENTS` for customization
- All three commands handle `cf` unavailability explicitly (no silent failures)
- `sq install-commands` installs both `sq/` and `workflow/` command files
- `sq uninstall-commands` removes both `sq/` and `workflow/` directories

### Technical Requirements

- `commands/workflow/` directory included in wheel (existing `force-include` covers all of `commands/`)
- Uninstall logic updated to handle all command subdirectories (not just `sq/`)
- All tests pass with `pytest`
- `pyright` passes with zero errors
- `ruff check` and `ruff format` pass

### Verification Walkthrough

1. **Verify command files exist:**
   ```bash
   ls commands/workflow/
   # Expected: next-step.md  design-review.md  ensemble-review.md
   ```

2. **Install commands:**
   ```bash
   sq install-commands
   # Expected: Installed 11 command(s) — 8 from sq/, 3 from workflow/
   ls ~/.claude/commands/workflow/
   # Expected: next-step.md  design-review.md  ensemble-review.md
   ```

3. **Test `/workflow:next-step` in Claude Code:**
   ```
   /workflow:next-step
   ```
   Expected: Claude runs `cf status` and `cf next`, then recommends a specific next action.

4. **Test `/workflow:design-review` in Claude Code:**
   ```
   /workflow:design-review
   ```
   Expected: Claude identifies the current slice from `cf status`, runs `sq review arch` against the architecture doc, presents results.

5. **Test `/workflow:ensemble-review` in Claude Code:**
   ```
   /workflow:ensemble-review arch
   ```
   Expected: Claude checks `sq auth status`, runs architectural review with each configured provider, synthesizes results.

6. **Verify uninstall:**
   ```bash
   sq uninstall-commands
   # Expected: removes both sq/ and workflow/ directories
   ls ~/.claude/commands/sq/ 2>/dev/null   # Should not exist
   ls ~/.claude/commands/workflow/ 2>/dev/null  # Should not exist
   ```

7. **Verify wheel bundling:**
   ```bash
   uv build
   unzip -l dist/*.whl | grep workflow
   # Expected: workflow/next-step.md, workflow/design-review.md, workflow/ensemble-review.md
   ```

## Implementation Notes

### Suggested Implementation Order

1. **Command file authoring** (effort: 1/5) — Write the three `.md` files in `commands/workflow/`. The prompt design is the most important part — prompts must be clear enough that Claude executes the correct sequence of commands and interprets results usefully.

2. **Uninstall fix** (effort: 0.5/5) — Update `uninstall_commands` in [install.py](src/squadron/cli/commands/install.py) to remove all squadron command subdirectories (not just `sq/`). The install side already works correctly since it iterates all subdirectories.

3. **Tests** (effort: 0.5/5) — Update existing install/uninstall tests to verify `workflow/` files are included. Add source verification test for `commands/workflow/` directory.

4. **Validation** (effort: 0.5/5) — Build wheel, verify bundling. Install commands, verify count. Manual test in Claude Code.

### Testing Strategy

- **Install tests:** Verify both `sq/` and `workflow/` files are installed (11 total commands)
- **Uninstall tests:** Verify both subdirectories are removed; other command directories are untouched
- **Source verification:** All expected command files exist in `commands/workflow/` and are non-empty
- **No integration tests with Claude Code:** Manual verification during implementation is sufficient (same as slice 116)
