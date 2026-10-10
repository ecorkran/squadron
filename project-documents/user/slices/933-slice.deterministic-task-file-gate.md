---
docType: slice-design
slice: deterministic-task-file-gate
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [930]
interfaces: []
dateCreated: 20261010
dateUpdated: 20261010
status: not_started
---

# Slice Design: Deterministic Task-File Gate

## Overview
A tasks review first scans every task file for merge steps. A file with one gets verdict FAIL and the offending line numbers, and no model is called. The guide forbids merge items in task files (`guide.ai-project.005-task-breakdown`, line 150; `rules/git.md`, "Merging (Phase 7 only…)"), but prose has not stopped them: trading-data 184, 185, 908 and 909 all shipped one, checked off.

## Value
A prose rule a model can ignore is not a gate. The scan is plain code that runs before any model call, so an agent can no longer reach "merge into the target" through a task item before code review. It also costs nothing: a bad file never pays for a model review.

## Technical Scope
In scope:
- A scanner over task-file text that returns merge-step lines (number and text).
- Calling it before the first model call in both code paths that run a tasks review: `sq review tasks` (CLI) and the pipeline `review:` action. The `/sq:review tasks` slash command shells out to the CLI, and squadron's server has no review tool today, so those two paths cover every interface.
- A FAIL `ReviewResult` built from the scan, saved and reported like any other tasks review.

Out of scope:
- Historical task files. Nothing rewrites them; the gate only affects reviews run from now on.
- Other forbidden task content (time estimates, etc.).
- Pipeline `branch: merge` steps. Those are engine ops, not task items.

## Dependencies
### Prerequisites
- Slice 930 (complete): the tasks review covers every split task file, so the gate scans every part.

### Interfaces Required
- `review_parts` / `resolve_slice_inputs` give the list of part files for a slice.
- `ReviewResult`, `ReviewFinding`, `Verdict` from `squadron.review.models`.
- `missing_input_files` pattern: the existing pre-model input check the gate sits next to.

## Architecture
### Component Structure
- `squadron/review/task_gate.py` (new): `scan_merge_steps(text) -> list[MergeStepLine]` and `merge_gate_result(scans) -> ReviewResult | None`. Pure functions, no I/O.
- CLI: `review_tasks` calls the gate once over all parts before its per-part loop.
- Pipeline: `ReviewAction._review` calls the same gate after parts are resolved and validated, before the first model call, when `template_name` is `tasks`.

### Data Flow
Task file paths → read each file → `scan_merge_steps` per file → if any hits, build a FAIL `ReviewResult` per offending part (findings carry file, line and text) and skip the model; otherwise continue to the normal review. A multi-part review saves the FAIL under that part's own `part-N` slot, as a normal part verdict does.

### State Management
None. The scanner is stateless and the FAIL result persists through the existing save path.

## Technical Decisions
### What counts as a merge step
A line is flagged when it is a checklist item (`- [ ]` or `- [x]` at any indent) or a heading, and its text names merging a branch. Prose, frontmatter and notes are never flagged.

Patterns live in one table in `task_gate.py`, each with a name. A line is flagged if any pattern matches its text, case-insensitive:
- starts with `merge` (as the item's first word, ignoring bold markers and an `T14 —` style label);
- `merge` joined to a commit/release verb: `commit and merge`, `then merge`, `merge and release`, `merge, tag`;
- `merge` followed within a few words by a git object: `branch`, `main`, `target`, `slice`, `integration`;
- `branch merged` / `slice merged` as a success criterion.

Not flagged (these are the negative fixtures): `merge defaults`, `merge blocker`, `zero errors is the merge gate`, `mergeFixResults`, `merges built-in and user profiles`, `merge-base`, `--no-merges`, and any `merged`/`merge` in frontmatter or plain prose such as "Slice 183 complete and merged to main".

### Failure mode
If a task file cannot be read, the gate raises; the review does not skip the scan. A missing file already fails earlier in `missing_input_files`, so this path is an I/O error only.

### Alternatives considered
- Asking the review model to check: rejected, that is the same prose-rule failure.
- Flagging every `merge` word: rejected, it hits ordinary vocabulary and teaches people to ignore the gate.

### Patterns and Conventions
- No dispatch by string matching on template names beyond one constant for the tasks template.
- The pattern table is the single place to change what counts as a merge step.

## Integration Points
### Provides to Other Slices
- `scan_merge_steps` for any later check that wants to read task files.

### Consumes from Other Slices
- 930's multi-part resolution. If a part is missing, 930's existing behavior applies unchanged.

## Success Criteria
### Functional Requirements
- A task file with a merge checklist item or heading gets verdict FAIL, with the line number and text in findings, and no model call is made.
- A task file without one reviews exactly as before.
- Every part of a split breakdown is scanned; one bad part fails the review.
- Same behavior from `sq review tasks <n>`, `sq review tasks <file> --against …`, the slash command, and a pipeline tasks review.

### Technical Requirements
- Fixtures are the real lines from trading-data 184 (`T14 — Commit and merge`, `Merge to main`), 185 (`Commit the doc update, then merge`, `Success: branch merged…`), 908 (`4.1 Merge, tag, and publish`), 909 (`5.1 Merge and release`), and trading-ui 124/125 where present, plus real negatives from squadron's own task files.
- A test runs the gate over each real file from the list and expects FAIL.
- A test asserts the model is never called when the gate fails.
- ruff, pyright zero errors.

### Integration Requirements
- The FAIL artifact is saved and readable by existing review readers.

### Verification Walkthrough
1. `sq review tasks <slice>` on a slice whose task file has a line like `- [ ] Merge to main`: prints verdict FAIL, lists the line number and text, exits non-zero, and the run shows no model call or cost.
2. Remove the line and rerun: the normal review runs.
3. Run a pipeline with a `review: {template: tasks}` step against the same file: the step fails with the same findings.

## Risk Assessment
### Technical Risks
- False positives on phrases like "merge gate". The negative fixtures above are the control; the pattern table is the one place to adjust.

## Implementation Notes
### Development Approach
1. Scanner and pattern table with the real-line fixtures.
2. FAIL result builder.
3. CLI hook, then pipeline hook.
4. Tests for both paths including the no-model-call assertion.

### Special Considerations
- Interface parity: the CLI and pipeline paths must call the same function, not two copies of the check.
