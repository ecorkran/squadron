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

Add a `/sq:run-slice` command that automates the full slice lifecycle — design (phase 4), task breakdown (phase 5), and implementation (phase 6) — by chaining Context Forge and squadron commands together. The user provides a slice number and the command drives the entire flow: building context, designing, reviewing, compacting, and implementing.

This is a single command file in the existing `commands/sq/` namespace. It leverages Claude Code's reasoning to interpret review results, decide whether to iterate or proceed, and manage context window efficiently via `/compact` between phases.

## Value

Today, executing a slice requires the operator to manually invoke 10+ commands in sequence across two tools (`cf` and `sq`), remember the correct phase transitions, and manage context compaction. `/sq:run-slice` reduces this to a single invocation. The operator can kick off a slice and let Claude Code drive, intervening only when reviews surface issues that need human judgment.

## Technical Scope

### Included

- One command file: `commands/sq/run-slice.md` → `/sq:run-slice`
- The command prompt encodes the full phase 4→5→6 pipeline with review gates
- Uses existing commands: `cf set`, `cf build`, `sq review tasks`, `sq review code`, `/compact`

### Excluded

- New Python code — this is a markdown command file only
- Automated resolution of review findings (TODOs in design for future iteration)
- Smart resume from mid-pipeline (documented as enhancement)
- Additional composed commands (ensemble-review, next-step, design-review from prior design) — deferred until real usage validates need

## Dependencies

### Prerequisites

- **Claude Code Commands — sq Wrappers (slice 116)** (complete): `commands/sq/` directory, install mechanism, wheel bundling.
- **Context-Forge CLI** (external): `cf set`, `cf build`, `cf get` commands must be available. Context-forge project must be initialized with a slice plan set.

### External Packages

None. This is a markdown command file.

## Technical Decisions

### Namespace: `/sq:run-slice`

Stays in the `sq/` namespace rather than creating a separate `workflow/` namespace. Reasons:
- One command doesn't justify a new namespace
- The `sq/` install/uninstall mechanism already works — no code changes needed
- Users already know to look under `/sq:*` for squadron commands

### Pipeline Steps

The command encodes this sequence:

```
1. Validate: cf get → confirm slice plan is set, slice exists in plan
2. Phase 4 (Slice Design):
   a. cf set phase 4
   b. cf set slice {slice-identifier}
   c. cf build → Claude designs the slice
3. Phase 5 (Task Breakdown):
   a. cf set phase 5
   b. cf build → Claude creates task breakdown
   c. sq review tasks {tasks-file} --against {slice-file} → review quality
   d. If FAIL/CONCERNS: iterate on findings, re-review
4. Compact:
   a. /compact [keep slice design and task breakdown summaries for slice {nnn}]
5. Phase 6 (Implementation):
   a. cf set phase 6
   b. cf build → Claude implements from tasks
   c. sq review code --diff main → review implementation
   d. If FAIL/CONCERNS: iterate on findings, re-review
```

### Review Gates

After task review (step 3c) and code review (step 5c), the command instructs Claude to:
- If verdict is PASS: proceed to next step
- If verdict is CONCERNS: assess severity — minor concerns proceed with a note, significant concerns attempt a fix and re-review (once)
- If verdict is FAIL: stop and present findings to the operator for guidance

This is a simple heuristic. The TODOs in the command acknowledge that smarter loop/signal logic is future work.

### Context Management

The `/compact` between phases 5 and 6 is critical. By the time task breakdown and review are complete, the context window is heavily loaded. Compacting with explicit keep instructions preserves the essential design/task summaries while freeing space for implementation.

### Slice Identification

The `$ARGUMENTS` value is the slice identifier — a number, name, or partial match. The command uses `cf get` output to resolve the slice plan, then searches the slice plan file for a matching entry. This mirrors how the operator would manually find a slice.

### Enhancement: Smart Resume (Future)

When invoked on a slice where work has already started:
- If slice design file exists but no task file → skip to phase 5
- If both slice design and task files exist → skip to phase 6 (ideally with a review first, but review tracking is not yet in place)

This is deferred to a future iteration — for now the command starts from phase 4.

## Command File Specification

### `/sq:run-slice`

**File:** `commands/sq/run-slice.md`

**Invocation:** `/sq:run-slice 118` or `/sq:run-slice composed-workflows`

**Content:**

```markdown
Automate the full slice lifecycle — design, task breakdown, and implementation — for the specified slice.

Input: `$ARGUMENTS` is the slice number or name (e.g., `118` or `composed-workflows`).

If no arguments are provided, ask the user which slice to run.

## Step 0: Validate

Run `cf get` to confirm:
- A slice plan is set (fileSlicePlan field is not empty)
- The project is initialized

Read the slice plan file and verify the slice from `$ARGUMENTS` exists in it. Extract the slice name and index.

If validation fails, report what's missing and stop.

## Step 1: Phase 4 — Slice Design

Set up and build context for slice design:

`cf set phase 4`
`cf set slice {slice-identifier}`
`cf build`

Follow the instructions from `cf build` output to create the slice design. This is the core design work — create the slice design document at the expected path.

When the slice design is complete, proceed to step 2.

## Step 2: Phase 5 — Task Breakdown

Advance to task breakdown:

`cf set phase 5`
`cf build`

Follow the instructions from `cf build` output to create the task breakdown. Create the task file at the expected path.

When the task breakdown is complete, review it:

`sq review tasks project-documents/user/tasks/{nnn}-tasks.{slice-name}.md --against project-documents/user/slices/{nnn}-slice.{slice-name}.md -v`

### Review gate:
- **PASS**: Proceed to step 3.
- **CONCERNS (minor)**: Note the concerns but proceed. Minor concerns can be addressed during implementation.
- **CONCERNS (significant) or FAIL**: Attempt to fix the findings and re-run the review once. If it still fails, stop and present the findings to the user for guidance.

<!-- TODO: Smarter review loop — track iteration count, categorize finding severity, signal human when stuck rather than retrying blindly -->

## Step 3: Compact

Compact the context to free space for implementation:

/compact [keep slice design, task breakdown, and task review summaries for slice {nnn}]

## Step 4: Phase 6 — Implementation

Advance to implementation:

`cf set phase 6`
`cf build`

Follow the instructions from `cf build` output to implement the slice from the task breakdown.

When implementation is complete, review the code:

`sq review code --diff main -v`

### Review gate:
- **PASS**: Report completion to the user.
- **CONCERNS (minor)**: Note the concerns, report completion with caveats.
- **CONCERNS (significant) or FAIL**: Attempt to fix the findings and re-run the review once. If it still fails, stop and present the findings to the user for guidance.

<!-- TODO: Smarter review loop — detect which findings are auto-fixable vs. need human input, track fix attempts, avoid infinite loops -->

## Completion

When all steps are done, provide a brief summary:
- Slice design file path
- Task file path
- Commits made during implementation
- Review verdicts (task review and code review)
- Any unresolved concerns or deferred items
```

## Package Structure

```
commands/
└── sq/
    ├── spawn.md            # Existing
    ├── task.md             # Existing
    ├── list.md             # Existing
    ├── shutdown.md         # Existing
    ├── review-arch.md      # Existing
    ├── review-tasks.md     # Existing
    ├── review-code.md      # Existing
    ├── auth-status.md      # Existing
    └── run-slice.md        # New (this slice)
```

No changes to `install.py` — the new file is in the existing `sq/` directory.

## Integration Points

### Provides to Other Slices

- **Automation pattern:** Establishes the pattern for multi-step composed commands. Future commands (e.g., a hypothetical `/sq:run-review-cycle`) can follow the same approach.

### Consumes from Prior Slices

- **sq Wrappers (slice 116):** `commands/sq/` directory, install mechanism, wheel bundling.
- **Review Workflow Templates (slice 105):** `sq review tasks` and `sq review code` commands invoked during review gates.

### External Dependencies

- **Context-Forge CLI:** `cf get`, `cf set`, `cf build` commands. Must be installed and project initialized.

## Success Criteria

### Functional Requirements

- `commands/sq/run-slice.md` exists with the complete pipeline prompt
- `/sq:run-slice 118` drives through design → tasks → review → compact → implement → review
- Command validates slice exists in the slice plan before starting
- Task review runs after phase 5 with a review gate (stop on FAIL)
- Code review runs after phase 6 with a review gate (stop on FAIL)
- `/compact` is invoked between phases 5 and 6 with appropriate keep instructions
- Command handles missing `cf` explicitly (no silent failures)

### Technical Requirements

- Command file included in wheel (existing `force-include` covers `commands/`)
- `sq install-commands` installs the new file alongside existing commands (9 total)
- All existing tests continue to pass
- `pyright`, `ruff check`, `ruff format` pass (no Python changes expected)

### Verification Walkthrough

1. **Verify command file exists:**
   ```bash
   ls commands/sq/run-slice.md
   ```

2. **Install and verify:**
   ```bash
   sq install-commands
   # Expected: Installed 9 command(s) to ~/.claude/commands
   ls ~/.claude/commands/sq/run-slice.md
   ```

3. **Test in Claude Code (dry run):**
   ```
   /sq:run-slice 118
   ```
   Expected: Claude validates the slice exists, sets phase 4, runs `cf build`, begins the design pipeline. Each phase transition is visible. Review gates produce pass/fail verdicts. Context is compacted between phases 5 and 6.

4. **Verify wheel bundling:**
   ```bash
   uv build
   unzip -l dist/*.whl | grep run-slice
   # Expected: squadron/commands/sq/run-slice.md
   ```

## Implementation Notes

### Suggested Implementation Order

1. **Command file authoring** (effort: 1/5) — Write `run-slice.md`. The prompt structure is the most design-sensitive part — it needs to be precise enough that Claude follows the pipeline correctly, handles review gates, and manages context.

2. **Update install test** (effort: 0.5/5) — Update the expected command count in existing install tests (8 → 9).

3. **Manual verification** (effort: 1/5) — Run `/sq:run-slice` on a real slice to verify the full pipeline works end-to-end. This is the most important validation step — the command's value depends entirely on whether Claude follows the multi-step instructions reliably.

### Testing Strategy

- **Source verification:** `commands/sq/run-slice.md` exists and is non-empty
- **Install test:** Expected file count increases from 8 to 9
- **No automated integration test:** The command's behavior depends on Claude Code runtime + context-forge state. Manual verification during implementation is the primary validation.
