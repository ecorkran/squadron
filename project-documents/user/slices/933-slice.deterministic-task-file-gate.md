---
docType: slice-design
slice: deterministic-task-file-gate
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [930]
interfaces: []
dateCreated: 20261010
dateUpdated: 20261011
status: complete
---

# Slice Design: Deterministic Task-File Gate

## Overview
A tasks review first scans every task file for merge steps. A file with one gets verdict FAIL and the offending line numbers, and no model is called. The guide forbids merge items in task files (`guide.ai-project.005-task-breakdown`, line 150; `rules/git.md`, "Merging (Phase 7 only…)"), but prose has not stopped them: trading-data 184, 185, 908 and 909 and trading-ui 124 and 125 all shipped one, checked off.

## Value
A prose rule a model can ignore is not a gate. The scan is plain code that runs before any model call, so an agent can no longer reach "merge into the target" through a task item before code review. It also costs nothing: a bad file never pays for a model review.

## Technical Scope
In scope:
- A scanner over task-file text that returns merge-step lines (number and text).
- Calling it before the first model call in both code paths that run a tasks review: `sq review tasks` (CLI) and the pipeline `review:` action. The `/sq:review tasks` slash command shells out to the CLI, and squadron's server has no review tool today, so those two paths cover every interface. A future MCP review tool must call the same gate.
- A FAIL `ReviewResult` built from the scan, saved and reported like any other tasks review.

Out of scope:
- Historical task files. Nothing rewrites them; the gate only affects reviews run from now on.
- Other forbidden task content (time estimates, etc.).
- Pipeline `branch: merge` steps. Those are engine ops, not task items.

## Dependencies
### Prerequisites
- Slice 930 (complete): the tasks review covers every split task file, so the gate scans every part.

### Interfaces Required
- The resolved part paths each path already holds before its first model call (`review_tasks`' part list; the parts `ReviewAction._review` has validated). The gate takes paths; it depends on no resolver method.
- `ReviewResult`, `ReviewFinding`, `Verdict` from `squadron.review.models`.
- `missing_input_files` pattern: the existing pre-model input check the gate sits next to.

## Architecture
### Component Structure
- `squadron/review/task_gate.py` (new): `scan_merge_steps(text) -> list[MergeStepLine]` and `merge_gate_results(scans: Sequence[tuple[Mapping[str, str], list[MergeStepLine]]]) -> dict[str, ReviewResult]`. Each entry pairs one part's review inputs dict (`input`, `against`, `cwd`) with its hits; the result is keyed by the part's `input` path, copies that inputs dict into `input_files`, and is empty when every part is clean. Pure functions, no I/O.
- `squadron/review/task_gate_files.py` (new): `gate_task_files(part_inputs: Sequence[Mapping[str, str]]) -> dict[str, ReviewResult]`, the one read-and-gate entry point both callers use, so the CLI and pipeline paths cannot drift. It holds the reads, keeping `task_gate.py` pure.
- CLI: `review_tasks` reads every part and calls the gate once before its per-part loop.
- File reads happen inside `gate_task_files`, a plain synchronous function. The CLI calls it directly; the pipeline, inside an async action, calls it through `asyncio.to_thread`, since reads plus per-line regex scans have no guaranteed <1ms bound (changed after code review F002; the design first argued for inline sync reads).
- Pipeline: `ReviewAction._review` calls the same gate after parts are resolved and validated, before the first model call, when `template_name` is `tasks`.

### Data Flow
Part inputs dicts → `gate_task_files` reads each `input` file → `scan_merge_steps` per file → `merge_gate_results`.

**Any hit in any part stops the whole review: no model call for any part.** A FAIL `ReviewResult` is built and saved for each offending part only (its own `part-N` slot for a split breakdown, the normal slot for a single file); clean parts are not reviewed and get no artifact. The CLI's worst-verdict exit code sees FAIL and exits non-zero; the pipeline passes the FAIL results through `fold_review_parts`, so the step's verdict is FAIL. If there are no hits, the normal review runs unchanged.

### State Management
None. The scanner is stateless and the FAIL result persists through the existing save path.

## Technical Decisions
### What counts as a merge step
A line is flagged when it is a checklist item (`- [ ]` or `- [x]` at any indent) or a heading, and its text names merging a branch. Prose, frontmatter and notes are never flagged.

Patterns live in one table in `task_gate.py`, each with a name. A line is flagged if any pattern matches its text, case-insensitive. `merge` always means the whole word (`merge`, `merges`, `merged`) bounded by whitespace, punctuation or line edges, where a hyphen or underscore is *not* a boundary: `merge-base`, `--no-merges`, `merge_gate` and `mergeFixResults` never contain the word, so their neighbours (`main` in `git merge-base main HEAD`) are never checked against the git-object rule.
- starts with `merge` (as the item's first word, ignoring bold markers and a `T14 —` style label) **and** is immediately followed by `to`/`into` (`Merge to main`; `Merge defaults … into profile` does not match), or by a git object below, or by a colon (`Merge: re-read …`), or is the whole item (`Merge`);
- `merge` joined to a commit/release verb: `commit and merge`, `then merge`, `merge and release`, `merge, tag`;
- `merge` followed within `MERGE_OBJECT_WINDOW` words (a named constant in the pattern table, set to 4) by a git object: `branch`, `main`, `target`, `slice branch`, `integration branch` (bare `slice` is not one, so `Merge slice config overrides` passes);
- `branch merged` / `slice merged` as a success criterion.

Not flagged (these are the negative fixtures, written as checklist items since that is the format the scanner reads): `- [ ] Merge defaults from config into profile`, `- [ ] Merge slice config overrides`, `- [ ] Fix merge blocker`, `- [ ] Zero errors is the merge gate`, `- [ ] Call mergeFixResults`, `- [ ] Merges built-in and user profiles`, `- [ ] Compute merge-base`, `- [ ] Run git log --no-merges`, `- [ ] Run git merge-base main HEAD`. Also not flagged: any `merged`/`merge` in frontmatter or plain prose such as "Slice 183 complete and merged to main".

### Failure mode
If a task file cannot be read or decoded (`OSError`, `UnicodeDecodeError`), the gate raises with the file path; the review does not skip the scan. A missing file already fails earlier in `missing_input_files`, so this path is an I/O or encoding error only.

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
- Fixtures are excerpts of the real task files, vendored under `tests/review/fixtures/task_gate/` with their original line numbers noted, so the suite never reads a sibling repo. The list is fixed: trading-data 184 (`T14 — Commit and merge`, `Merge to main`), 185 (`Commit the doc update, then merge`, `Success: branch merged…`), 908 (`4.1 Merge, tag, and publish`), 909 (`5.1 Merge and release`), trading-ui 124 (line 496, `Merge into the target per the project Git Rules…`) and 125 (line 325, `Merge: re-read cf config get git.integration_branch…`), plus real negatives from squadron's own task files.
- A test runs the gate over each vendored excerpt and expects FAIL at the noted lines.
- A test asserts the model is never called when the gate fails.
- ruff, pyright zero errors.

### Integration Requirements
- The FAIL artifact is saved and readable by existing review readers. No model ran, so its fields are explicit, never left for the implementer to invent: `model` is a constant `TASK_GATE_MODEL` (`squadron-task-gate`) defined once in `task_gate.py`, no profile, `verdict_source: imposed` (a measured fact, not a model opinion), `tools_given` and `tool_calls_made` both `None` (the model's tri-state for "ran without tools"; `[]`/`0` would claim a tool-capable run that was offered nothing), no cost or token telemetry. A test reads the saved artifact back through the existing readers and asserts the rendered frontmatter: `aiModel: squadron-task-gate`, `verdictSource: imposed`, and no `toolsGiven`/`toolCallsMade` keys.

### Verification Walkthrough
Verified 20261011 on branch `933-slice.deterministic-task-file-gate`. Run from the squadron repo root; `<scratch>` is any directory outside the repo.

1. Create a scratch task file whose last checklist item is a merge step:
   ```bash
   printf -- '---\ndocType: tasks\n---\n\n## Task 1\n\n- [ ] Add the scanner\n- [ ] Merge to main\n' > <scratch>/scratch-tasks.md
   sq review tasks <scratch>/scratch-tasks.md --against project-documents/user/slices/933-slice.deterministic-task-file-gate.md --no-save --model haiku; echo "exit=$?"
   ```
   Expected output, with no model call (the header names `squadron-task-gate`, not a model) and so no cost:
   ```
   Review: tasks  Verdict: FAIL  Model: squadron-task-gate
   [FAIL] Merge step at line 8: - [ ] Merge to main
   exit=2
   ```
   `/sq:review tasks <same arguments>` runs the same command and prints the same output.
2. Delete the `Merge to main` line and rerun the same command: the normal review runs. The header names the real model (e.g. `claude-haiku-4-5-…`) and the exit code reflects that model's verdict. A one-item stub file gets a content FAIL from the model; that verdict is the model's, not the gate's.
3. The pipeline path is covered by `tests/review/test_task_gate_pipeline.py`: a `review: {template: tasks}` step over an offending file returns verdict FAIL with no model call, saves the artifact with `aiModel: squadron-task-gate`, and writes the same artifact names as the CLI (`test_cli_and_pipeline_write_identical_gate_artifacts`). Run `uv run pytest tests/review/test_task_gate_pipeline.py -q`; expected `5 passed`.

Caveats: the gate reads only checklist items and headings; a merge step written as plain prose is not flagged (by design). An unreadable or undecodable task file exits 1 with `Cannot read task file <path> for the merge-step gate`.

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
