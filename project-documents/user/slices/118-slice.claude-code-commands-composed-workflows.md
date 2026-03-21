---
docType: slice-design
slice: claude-code-commands-composed-workflows
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [sq-slash-command, context-forge-workflow-navigation]
interfaces: []
dateCreated: 20260317
dateUpdated: 20260320
status: in-progress
---

# Slice Design: Claude Code Commands — Composed Workflows

## Overview

Add a `/sq:run-slice` command that automates the full slice lifecycle — design (phase 4), task breakdown (phase 5), and implementation (phase 6) — by chaining Context Forge and squadron commands together. The user provides a slice number and the command drives the entire flow: building context, designing, reviewing, compacting, and implementing.

This is a single command file in the existing `commands/sq/` namespace. It leverages Claude Code's reasoning to interpret review results, decide whether to iterate or proceed, and manage context window efficiently via `/compact` between phases.

## Value

Today, executing a slice requires the operator to manually invoke 10+ commands in sequence across two tools (`cf` and `sq`), remember the correct phase transitions, and manage context compaction. `/sq:run-slice` reduces this to a single invocation. The operator can kick off a slice and let Claude Code drive, intervening only when reviews surface issues that need human judgment.

## Technical Scope

### Included

- One new command file: `commands/sq/run-slice.md` → `/sq:run-slice`
- The command prompt encodes the full phase 4→5→6 pipeline with review gates
- Uses existing commands: `cf set`, `cf build`, `sq review tasks`, `sq review code`, `/compact`
- Update existing review commands (`review-tasks.md`, `review-code.md`, `review-arch.md`) to support:
  - Bare slice number input (e.g., `/sq:review-tasks 191`) with path resolution via `cf get`
  - Review file persistence to `project-documents/user/reviews/`
- CLI number shorthand: `sq review tasks 221`, `sq review arch 221`, `sq review code 221` resolve paths via `cf slice list --json` / `cf task list --json` — same UX as the slash commands but on the CLI directly

### Excluded

- Automated resolution of review findings (TODOs in design for future iteration)
- Automated resolution of review findings (TODOs in design for future iteration)
- Smart resume from mid-pipeline (documented as enhancement)
- Additional composed commands — deferred until real usage validates need

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

### Path Resolution via Context-Forge

All commands that accept a slice number use `cf slice list --json` and `cf task list --json` for file resolution. This delegates path knowledge to CF rather than hardcoding glob patterns.

The resolution flow for a bare number (e.g., `191`):
1. Run `cf slice list --json` → find entry where `index == 191` → get `designFile`
2. Run `cf task list --json` → find entry where `index == 191` → get tasks file path
3. Extract slice name from the design file path (e.g., `worktree-aware-file-operations`)
4. Derive review output path: `project-documents/user/reviews/{nnn}-review.{type}.{slice-name}.md`

For project-level context (architecture doc, project path): use `cf get`.

This approach:
- **CF owns naming conventions** — commands don't hardcode file patterns
- **Worktree-aware** — CF resolves paths for the current worktree automatically
- **Does not mutate CF state** — no `cf set slice` during resolution
- **Fails explicitly** if no matching entry is found (e.g., null `designFile`)
- **Future-proof** — when CF gains `--all`, cross-worktree lookups come free
- **JSON format** — structured lookup, no string parsing of table output

For `run-slice`, the `$ARGUMENTS` value is the slice identifier — a number or name. The command uses `cf slice list --json` to verify the slice exists and resolve paths before starting the pipeline.

### Review File Persistence

Review output is saved to `project-documents/user/reviews/` with index-matched naming:

```
project-documents/user/reviews/
  {nnn}-review.arch.{slice-name}.md    # arch review (slice design check)
  {nnn}-review.tasks.{slice-name}.md   # task review (phase 5 gate)
  {nnn}-review.code.{slice-name}.md    # code review (phase 6 gate)
```

This pairs reviews with their subject:
```
179-slice.some-feature.md          # slice design
179-tasks.some-feature.md          # task breakdown
179-review.arch.some-feature.md    # arch review (slice design check)
179-review.tasks.some-feature.md   # task review (phase 5 gate)
179-review.code.some-feature.md    # code review (phase 6 gate)
```

Each review file gets YAML frontmatter:
```yaml
---
docType: review
reviewType: tasks | code
slice: {slice-name}
project: squadron
verdict: PASS | CONCERNS | FAIL
dateCreated: YYYYMMDD
dateUpdated: YYYYMMDD
---
```

On re-review (e.g., after fixing findings), the file is overwritten. Git handles version history if prior review state is needed.

Review files are committed alongside the work they gate — the task review is committed with the task breakdown, the code review is committed after implementation.

### Enhancement: Smart Resume (Future)

When invoked on a slice where work has already started:
- If slice design file exists but no task file → skip to phase 5
- If both slice design and task files exist → skip to phase 6 (ideally with a review first, but review tracking is not yet in place)

This is deferred to a future iteration — for now the command starts from phase 4.

### Enhancement: JSON Review Output (Future)

Save review results as JSON alongside (or instead of) markdown, using `sq review --output json`. Enables piping into pipelines, aggregating findings across slices, or feeding a dashboard.

## Command File Specifications

### Updated: `/sq:review-tasks`

**File:** `commands/sq/review-tasks.md`

**New invocation:** `/sq:review-tasks 191` (bare number — resolves paths via `cf get`)

**Existing invocation still works:** `/sq:review-tasks path/to/tasks.md --against path/to/slice.md`

The updated command detects whether `$ARGUMENTS` starts with a number. If so, it resolves file paths, runs the review, and saves output to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md` with review frontmatter. If full paths are provided, it behaves as before but still saves the review file.

### Updated: `/sq:review-code`

**File:** `commands/sq/review-code.md`

**New invocation:** `/sq:review-code 191` (bare number — resolves slice, reviews code diff against main)

**Existing invocation still works:** `/sq:review-code --diff main --files "src/**/*.py"`

When given a bare number, the command resolves the slice context and runs `sq review code --diff main`. Review output is saved to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md`.

### Updated: `/sq:review-arch`

**File:** `commands/sq/review-arch.md`

**New invocation:** `/sq:review-arch 191` (bare number — resolves slice design, reviews holistically)

**Existing invocation still works:** `/sq:review-arch path/to/doc.md --against path/to/arch.md`

When given a bare number, the command performs a holistic architectural review of the slice design — checking it against both:
1. **Architecture document** (from `cf get` Architecture field) — does the design align with the system architecture?
2. **Slice plan entry** (from `cf slice list --json`, matching index) — does the design deliver what the plan says this slice should do?

This is one review answering one question: "does this slice design effectively cover what it's supposed to?" Review output is saved to `project-documents/user/reviews/{nnn}-review.arch.{slice-name}.md`.

### New: `/sq:run-slice`

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

Save the review output to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md`. Include YAML frontmatter:

```yaml
---
docType: review
reviewType: tasks
slice: {slice-name}
project: squadron
verdict: {PASS|CONCERNS|FAIL}
dateCreated: YYYYMMDD
dateUpdated: YYYYMMDD
---
```

Then the full review output as the body.

### Review gate:
- **PASS**: Commit the review file, proceed to step 3.
- **CONCERNS (minor)**: Commit the review file, note the concerns but proceed. Minor concerns can be addressed during implementation.
- **CONCERNS (significant) or FAIL**: Attempt to fix the findings and re-run the review once (overwrite the review file). If it still fails, commit the review file and stop — present the findings to the user for guidance.

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

Save the review output to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md`. Include YAML frontmatter:

```yaml
---
docType: review
reviewType: code
slice: {slice-name}
project: squadron
verdict: {PASS|CONCERNS|FAIL}
dateCreated: YYYYMMDD
dateUpdated: YYYYMMDD
---
```

Then the full review output as the body.

### Review gate:
- **PASS**: Commit the review file, report completion to the user.
- **CONCERNS (minor)**: Commit the review file, note the concerns, report completion with caveats.
- **CONCERNS (significant) or FAIL**: Attempt to fix the findings and re-run the review once (overwrite the review file). If it still fails, commit the review file and stop — present the findings to the user for guidance.

<!-- TODO: Smarter review loop — detect which findings are auto-fixable vs. need human input, track fix attempts, avoid infinite loops -->

## Step 5: DEVLOG Entry

Write a session state summary to the project's root `DEVLOG.md`. Use `cf prompt get session-state-summary` to retrieve the summary template. The entry should briefly capture:
- Which slice was processed
- Review verdicts
- Any unresolved concerns or deferred items

## Completion

When all steps are done, provide a brief summary:
- Slice design file path
- Task file path
- Review file paths
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
    ├── review-arch.md      # Updated — number shorthand + review persistence
    ├── review-tasks.md     # Updated — number shorthand + review persistence
    ├── review-code.md      # Updated — number shorthand + review persistence
    ├── auth-status.md      # Existing
    └── run-slice.md        # New (this slice)
```

No changes to `install.py` — file count stays at 9 (the new file is in the existing `sq/` directory, and the updated files don't change count).

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

**run-slice command:**
- `commands/sq/run-slice.md` exists with the complete pipeline prompt
- `/sq:run-slice 118` drives through design → tasks → review → compact → implement → review
- Command validates slice exists in the slice plan before starting
- Task review runs after phase 5 with a review gate (stop on FAIL)
- Code review runs after phase 6 with a review gate (stop on FAIL)
- `/compact` is invoked between phases 5 and 6 with appropriate keep instructions
- DEVLOG entry written at pipeline completion (using `cf prompt get session-state-summary` template)
- Command handles missing `cf` explicitly (no silent failures)

**Review command updates (review-tasks, review-code, review-arch):**
- All three accept a bare slice number (e.g., `/sq:review-tasks 191`)
- Number input triggers path resolution via `cf slice list --json` / `cf task list --json` — no need to type full paths
- `review-arch` performs holistic check: slice design vs. architecture doc + slice plan entry
- Works in worktrees (CF provides correct base path)
- Existing full-path invocations continue to work unchanged

**Review file persistence (all review commands + run-slice):**
- Review output saved to `project-documents/user/reviews/{nnn}-review.{type}.{slice-name}.md`
- Each review file includes YAML frontmatter (`docType`, `reviewType`, `verdict`, dates)
- Re-reviews overwrite the review file (git handles history)
- Review files are committed at each gate

### Technical Requirements

- Command file included in wheel (existing `force-include` covers `commands/`)
- `sq install-commands` installs the new file alongside existing commands (9 total)
- All existing tests continue to pass
- `pyright`, `ruff check`, `ruff format` pass (no Python changes expected)

### Verification Walkthrough

1. **Verify command file exists:**
   ```bash
   ls commands/sq/run-slice.md
   # Verified: file exists
   ```

2. **Install and verify:**
   ```bash
   sq install-commands --target /tmp/test-commands
   # Verified: Installed 9 command(s) to /tmp/test-commands
   ls /tmp/test-commands/sq/run-slice.md
   # Verified: file present
   rm -rf /tmp/test-commands
   ```

3. **Test in Claude Code (dry run):**
   ```
   /sq:run-slice {nnn}
   ```
   Expected: Claude validates the slice exists, sets phase 4, runs `cf build`, begins the design pipeline. Each phase transition is visible. Review gates produce pass/fail verdicts. Context is compacted between phases 5 and 6.
   Caveat: This is a manual PM test — behavior depends on Claude Code runtime + context-forge state.

4. **Verify wheel bundling:**
   ```bash
   uv build
   unzip -l dist/*.whl | grep run-slice
   # Verified: squadron/commands/sq/run-slice.md appears in wheel
   ```

5. **Full validation:**
   ```bash
   uv run ruff check          # Verified: All checks passed
   uv run ruff format --check # Verified: 130 files already formatted
   uv run pyright             # Verified: 0 errors, 0 warnings
   uv run pytest              # Verified: 448 passed
   ```

## Implementation Notes

### Suggested Implementation Order

1. **Command file authoring** (effort: 1/5) — Write `run-slice.md`. The prompt structure is the most design-sensitive part — it needs to be precise enough that Claude follows the pipeline correctly, handles review gates, and manages context.

2. **Update install test** (effort: 0.5/5) — Update the expected command count in existing install tests (8 → 9).

3. **Manual verification** (effort: 1/5) — Run `/sq:run-slice` on a real slice to verify the full pipeline works end-to-end. This is the most important validation step — the command's value depends entirely on whether Claude follows the multi-step instructions reliably.

### CLI Number Shorthand (effort: 2/5)

Add bare number resolution to the Python CLI so `sq review tasks 221` works the same as the slash command shorthand.

**Implementation:**
- Add `_resolve_slice_number(num: str) -> dict` helper in `review.py` that shells out to `cf slice list --json` and `cf task list --json`, finds the matching index, returns `designFile`, task file path, and slice name.
- In `review_arch` and `review_tasks`: detect `input_file.isdigit()`, call resolver, fill in `input_file` and `against` from the result.
- In `review_code`: add optional positional arg for slice number, resolve slice name for review context.
- Fail explicitly if `cf` is not available or slice number not found.

### Testing Strategy

- **Source verification:** `commands/sq/run-slice.md` exists and is non-empty
- **Install test:** Expected file count increases from 8 to 9
- **CLI number shorthand:** Unit tests for resolver + number detection (mocked `cf` output)
- **No automated integration test for slash commands:** The command's behavior depends on Claude Code runtime + context-forge state. Manual verification during implementation is the primary validation.
