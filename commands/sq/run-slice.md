Automate the full slice lifecycle — design, task breakdown, and implementation — for the specified slice.

Input: `$ARGUMENTS` is the slice number or name (e.g., `118` or `composed-workflows`).

If no arguments are provided, ask the user which slice to run.

## Step 0: Validate

Run `cf get` to confirm:
- A slice plan is set (fileSlicePlan field is not empty)
- The project is initialized

If `cf get` fails or is not available, report that Context-Forge is required and stop.

Run `cf slice list --json` and find the entry matching `$ARGUMENTS` (by index number or by name). Extract:
- The slice `index` (referred to as `{nnn}` below)
- The slice `name`
- The `designFile` path (may be null if not yet created)

Extract the slice identifier for `cf set slice` from the design file name or entry name.

If no matching entry is found, report the error and stop.

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

When the task breakdown is complete, review it.

Run `cf slice list --json` and `cf task list --json` to resolve the current file paths for this slice (they may have been created in step 1/2). Then run:

`sq review tasks {task-file-path} --against {design-file-path} -v`

Note: Add `--model ALIAS` to use a different model (e.g., `--model gpt4o`). Model aliases automatically set the correct provider profile. Run `sq model list` to see available aliases. You can also specify `--profile PROFILE` explicitly (e.g., `--profile openrouter --model anthropic/claude-3.5-sonnet`).

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
- **PASS**: Commit the task breakdown and review file, proceed to step 3.
- **CONCERNS (minor)**: Commit the task breakdown and review file, note the concerns but proceed. Minor concerns can be addressed during implementation.
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
- **PASS**: Commit the review file, proceed to step 5.
- **CONCERNS (minor)**: Commit the review file, note the concerns, proceed to step 5 with caveats.
- **CONCERNS (significant) or FAIL**: Attempt to fix the findings and re-run the review once (overwrite the review file). If it still fails, commit the review file and stop — present the findings to the user for guidance.

<!-- TODO: Smarter review loop — detect which findings are auto-fixable vs. need human input, track fix attempts, avoid infinite loops -->

## Step 5: DEVLOG Entry

Write a session state summary to the project's root `DEVLOG.md`. Use `cf prompt get session-state-summary` to retrieve the summary template. The entry should briefly capture:
- Which slice was processed
- Review verdicts (task review and code review)
- Any unresolved concerns or deferred items

## Completion

When all steps are done, provide a brief summary:
- Slice design file path
- Task file path
- Review file paths
- Commits made during implementation
- Review verdicts (task review and code review)
- Any unresolved concerns or deferred items
