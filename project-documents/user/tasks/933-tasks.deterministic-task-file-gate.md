---
docType: tasks
slice: deterministic-task-file-gate
project: squadron
lld: user/slices/933-slice.deterministic-task-file-gate.md
dependencies: [930]
projectState: >
  Slice design 933 complete after two review rounds (20261010). No code written. A pure
  scanner flags merge steps in task files; both tasks-review paths call it before any model
  call and save a FAIL result per offending part.
dateCreated: 20261010
dateUpdated: 20261011
status: in_progress
---

## Context Summary

- Working on **933 deterministic-task-file-gate**. A tasks review scans every task file part
  for merge checklist items and headings first. Any hit stops the whole review: no model call
  for any part, a FAIL `ReviewResult` saved for each offending part only, non-zero exit.
- The slice design is the contract: "What counts as a merge step" (pattern rules and negative
  fixtures), "Failure mode", and "Integration Requirements" (exact FAIL artifact fields). Tasks
  reference those sections rather than repeating them.
- New module `src/squadron/review/task_gate.py` holds pure functions only, no I/O. File reads
  live in the sibling `src/squadron/review/task_gate_files.py` (`gate_task_files`), which both
  callers use; the reads are synchronous (deliberate, see design "Component Structure").
- The gate works on each part's review inputs dict (`input`, `against`, `cwd`), the same dict
  the model review would get, so the FAIL result's `input_files` is complete with no
  caller-side patching.
- Hook sites: CLI `review_tasks` in `src/squadron/cli/commands/review.py` (before its per-part
  loop) and pipeline `ReviewAction._review` in `src/squadron/pipeline/actions/review.py` (after
  the per-part `_validate_inputs` loop, before the `_run_part` loop). Both call the same gate
  function.
- Existing tests mock the model at `squadron.cli.commands.review.run_review_with_profile` and
  `squadron.pipeline.actions.review.run_review_with_profile`
  (`tests/review/test_split_review_parity.py` shows both). The no-model-call tests use the same
  patch targets.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors), its tests,
  and a commit on the slice branch with a semantic prefix.
- Out of scope: rewriting historical task files, other forbidden content (time estimates),
  pipeline `branch: merge` steps.
- Next planned slice: 942.
- Effort: 2/5.

---

## Task 1 — Create the slice branch

- [x] Run `cf config get git.integration_branch`; call its value the target (`main` if empty). Confirm `git status` is clean and the current branch is the target
- [x] `git checkout -b 933-slice.deterministic-task-file-gate {target}`
  - [x] Success: `git branch --show-current` prints `933-slice.deterministic-task-file-gate`

---

## Task 2 — Vendor real-file fixtures

Test infrastructure first. Source repos are siblings under `/Users/manta/source/repos/manta/`;
the suite must never read them, so copy excerpts in. Source lines (all under
`project-documents/user/tasks/`; the text is shown here in prose because this file must pass
the gate it describes):

| ID | Repo | File | Lines | Text (abridged) |
|----|------|------|-------|-----------------|
| P1 | trading-data | `184-tasks.polish-gaps-endpoint.md` | 211, 220 | "T14 — Commit and merge"; "Merge to `main`." |
| P2 | trading-data | `185-tasks.staleness-surface-for-api-clients.md` | 410, 415 | "Commit the doc update, then merge"; "Success: branch merged, tree clean…" |
| P3 | trading-data | `908-tasks.pypi-distribution-and-production-cutover.md` | 146, 147 | "4.1 Merge, tag, and publish"; "Merge to `main` (`--no-ff`)…" |
| P4 | trading-data | `909-tasks.mt-update-self-update-command.md` | 237, 238 | "5.1 Merge and release"; "Merge the slice branch into `main`…" |
| P5 | trading-ui | `124-tasks.chart-data-binding.md` | 496 | "Merge into the target per the project Git Rules…" |
| P6 | trading-ui | `125-tasks.late-container-mount-fix.md` | 325 | "Merge: re-read `cf config get git.integration_branch`…" |

- [x] Create `tests/review/fixtures/task_gate/` with one excerpt file per source below. Each excerpt keeps the offending lines verbatim (including `- [x]`, indentation, bold markers and backticks) plus a few surrounding checklist lines
- [x] Each excerpt starts with a comment line naming the source repo, file and original line numbers. Record, per excerpt, which lines of the excerpt itself are expected hits (in `README.md` in the same directory, or as constants in the test file from Task 4)
  - [x] One excerpt per row of the source table above (P1–P6), each covering every listed line
- [x] Add one negatives excerpt from squadron's own task files (`project-documents/user/tasks/`): find real checklist lines that use merge vocabulary without being a merge step (e.g. `grep -nE "^\s*- \[.\].*\bmerge" project-documents/user/tasks/*.md`), copy at least three, and note their source lines. Expected hits: none
  - [x] Success: seven excerpt files exist, each with source and line notes; no test reads outside `tests/`

---

## Task 3 — Scanner and pattern table

Rules, from design "What counts as a merge step" (prose here, not checklist, for the same
reason as Task 2):

- R1 leading word: the item's first word, after stripping bold markers and a "T14 —" or "4.1"
  style label, is the merge word, and it is followed immediately by "to"/"into", by a git
  object, or by a colon, or it is the whole item.
- R2 joined verb: the merge word joined to a commit/release verb — "commit and …", "then …",
  "… and release", "…, tag".
- R3 object window: the merge word followed by a git object within `MERGE_OBJECT_WINDOW` words.
- R4 success criterion: "branch" or "slice" directly followed by "merged".

- [x] Create `src/squadron/review/task_gate.py` with a frozen dataclass `MergeStepLine(line_number: int, text: str)` (1-based line numbers)
- [x] Define the pattern table: one module-level collection of named patterns, the only place that defines what a merge step is. Include `MERGE_OBJECT_WINDOW = 4` and the git-object list (`branch`, `main`, `target`, `slice branch`, `integration branch`) as named constants beside it
- [x] Implement each of rules R1–R4 above as its own named entry in the table
- [x] Word boundary for `merge`/`merges`/`merged`: whitespace, punctuation (including backticks) or line edges; a hyphen or underscore is not a boundary, and a following letter is not either (`merge-base`, `--no-merges`, `merge_gate`, `mergeFixResults` never match). Matching is case-insensitive. Backticks around a git object (`` `main` ``) still count as that object
- [x] Implement `scan_merge_steps(text: str) -> list[MergeStepLine]`: only checklist items (`- [ ]` / `- [x]` at any indent) and headings are candidates; skip YAML frontmatter at the top of the file; prose and notes are never flagged
  - [x] Success: module has no file or network I/O; `pyright` zero errors

## Task 4 — Scanner tests

- [x] Create `tests/review/test_task_gate.py`
- [x] Parametrized test over excerpts P1–P6 from Task 2: `scan_merge_steps` returns exactly the expected line numbers, and each `text` matches the line
- [x] Test over the squadron negatives excerpt: returns `[]`
- [x] Parametrized test over the nine negatives listed in design "What counts as a merge step" (the "Not flagged" list), each written as a checklist line exactly as the design gives it. Each returns `[]`
- [x] Tests for the design's frontmatter and prose negatives (frontmatter containing the merged word; the "Slice 183 complete…" prose line): not flagged. A level-2 heading built from P1's second line is flagged
- [x] Test that a checklist item consisting of the bare merge word alone, and an indented lower-case `- [x]` version of P1's second line, are both flagged
- [x] Parametrized per-rule tests built from synthetic checklist lines (cases listed below the checklist), independent of the fixtures, so the pattern table is not fitted to six files
  - [x] R2: each joined-verb case is flagged
  - [x] R3 boundary: a git object exactly `MERGE_OBJECT_WINDOW` words after the merge word is flagged; one word further is not (build both lines from the constant, not a literal 4)
  - [x] Success: all tests pass; any failure here means adjusting the pattern table, not the fixtures
- [x] Commit: `feat: add task-file merge-step scanner`

Per-rule cases (prose, so this file passes its own gate): R2 joined verbs "commit and merge",
"commit, then merge", "merge and release", "merge, tag, and publish"; R3 window lines of the
form "merge <n filler words> branch" with n = window − 1 (flagged) and
n = window (not flagged), where "branch" is the git object.

---

## Task 5 — FAIL result builder

- [ ] In `task_gate.py`, define `TASK_GATE_MODEL = "squadron-task-gate"` once
- [ ] Implement `merge_gate_results(scans: Sequence[tuple[Mapping[str, str], list[MergeStepLine]]]) -> dict[str, ReviewResult]` per design "Component Structure": each entry is one part's review inputs dict and its hits. Empty dict when every scan is empty; otherwise one entry per offending part, keyed by its `input` path, none for clean parts
- [ ] Each `ReviewResult` follows design "Integration Requirements" exactly: `verdict=Verdict.FAIL`, `template_name="tasks"` (use the existing tasks template name constant if one exists; otherwise define one in `task_gate.py`), `model=TASK_GATE_MODEL`, `verdict_source=VerdictSource.IMPOSED`, `tools_given=None`, `tool_calls_made=None`, no profile, no cost or token fields
- [ ] One `ReviewFinding` per hit, severity FAIL, naming the line number and quoting the line text; `raw_output` states that the gate found merge steps and no model ran
- [ ] `input_files` is a copy of that part's inputs dict (`input`, `against`, `cwd`), exactly what a model review of the part records
  - [ ] Success: `pyright` zero errors

## Task 6 — FAIL result builder tests

- [ ] In `tests/review/test_task_gate.py`: empty scans → `{}`; two parts, one with hits → one entry, keyed by the offending part's `input` path, with `input_files` equal to that part's inputs dict
- [ ] Assert every field listed in Task 5 on the built result, including `tools_given is None` and `tool_calls_made is None`
- [ ] Read-back test: save the result through the existing persistence path used for tasks reviews (find it from `_save_and_report` / `save_review_result`, writing into `tmp_path`), read the file back, and assert the frontmatter has `aiModel: squadron-task-gate` and `verdictSource: imposed`, and has no `toolsGiven` or `toolCallsMade` keys
  - [ ] Success: tests pass
- [ ] Commit: `feat: build FAIL review results from task-gate hits`

---

## Task 7 — Shared read-and-gate helper

Both callers read files, then call the gate. Put that in one place so the two paths cannot drift.

- [ ] Create `src/squadron/review/task_gate_files.py` with `gate_task_files(part_inputs: Sequence[Mapping[str, str]]) -> dict[str, ReviewResult]`: reads each part's `input` file as UTF-8, scans it, returns `merge_gate_results(...)` over the (inputs, hits) pairs. `task_gate.py` stays free of I/O
- [ ] `OSError` and `UnicodeDecodeError` propagate with the file path in the message (re-raise a clear error naming the path; never skip the file)
- [ ] Tests (in `tests/review/test_task_gate_files.py`): a clean file → `{}`; an offending file → one FAIL entry; a file of invalid UTF-8 bytes in `tmp_path` → raises, and the message contains the path
  - [ ] Success: tests pass
- [ ] Commit: `feat: add task-file gate entry point for review callers`

---

## Task 8 — CLI hook in `review_tasks`

- [ ] In `review_tasks`, after `parts = review_parts(task_file_paths)` and before the per-part loop, build each part's inputs dict once (the `input`/`against`/`cwd` dict the loop already builds) and call `gate_task_files` on that list; the loop reuses the same dicts
- [ ] If the result is empty, the existing loop runs unchanged
- [ ] If not empty: skip the loop entirely (no `_run_review_command` call for any part). For each offending part, display the FAIL result with the existing `display_result` and save it through the existing `_save_and_report` / `_resolve_save_outcome` path with that part's `name_suffix`, so it lands in the same slot a model review of that part would. Clean parts get nothing
- [ ] Exit through the existing `_exit_on(worst_verdict, outcome)`, so FAIL gives a non-zero exit
- [ ] Keep the per-part save logic shared with the normal path rather than copying it (extract a helper if needed)
  - [ ] Success: `pyright` zero errors; existing CLI review tests still pass

## Task 9 — CLI hook tests

- [ ] In `tests/review/test_cli_review.py` (or a new `tests/review/test_task_gate_cli.py` if that file is near its size limit), with `run_review_with_profile` patched:
  - [ ] Single task file containing an unchecked copy of P1's second line: exit code non-zero, output shows FAIL and the line number, the patched model call is never called, one artifact saved in the normal (unsuffixed) slot
  - [ ] Split breakdown, part 2 offending: no model call for any part; one artifact under part 2's suffix; none for part 1
  - [ ] Clean task file: model called as before, normal result
  - [ ] `sq review slice` on a design file containing P1's second line: no gate, model called as before
  - [ ] `sq review tasks <file> --against <design>` form with an offending file: same FAIL behavior
  - [ ] Success: tests pass
- [ ] Commit: `feat: gate sq review tasks on merge steps before any model call`

---

## Task 10 — Pipeline hook in `ReviewAction._review`

- [ ] Define the tasks-template check through one constant (reuse the same one Task 5 uses); no new string comparisons on template names
- [ ] When the template is tasks, after the `_validate_inputs` loop and before the `_run_part` loop, call `gate_task_files(part_inputs)`
- [ ] If not empty: no `_run_part` call for any part. For each offending part, set `run_id` and save the FAIL result through the existing `_save_part` with that part's suffix, and build its `ActionResult` through the existing `_part_result`, so the artifact and step output match a model review's. Return `fold_review_parts` over those results
- [ ] If empty, the existing loop runs unchanged
  - [ ] Success: `pyright` zero errors; existing pipeline review tests still pass

## Task 11 — Pipeline hook and parity tests

- [ ] In a pipeline review test (follow `tests/review/test_split_review_parity.py` for context and cf-client setup), with `squadron.pipeline.actions.review.run_review_with_profile` patched:
  - [ ] Offending single task file: step verdict FAIL, the patched model call is never called, artifact saved with `aiModel: squadron-task-gate`
  - [ ] Split breakdown with one offending part: no model call; one artifact, under that part's suffix
  - [ ] Clean task file: model called as before
  - [ ] Non-tasks template (slice review) whose input file contains P1's second line: gate does not run, model called as before
- [ ] Parity test: same offending split project through the CLI and the pipeline step writes identical artifact file names (extend the pattern in `test_split_review_parity.py`)
  - [ ] Success: tests pass
- [ ] Commit: `feat: gate pipeline tasks reviews on merge steps`

---

## Task 12 — Full validation and walkthrough

- [ ] Run the full suite, `ruff format`, `ruff check`, `pyright`: zero errors, no new failures
- [ ] Run design "Verification Walkthrough" steps 1 and 2 by hand against a scratch task file outside the repo (`sq review tasks <file> --against <design> --no-save --model <model>`): step 1 prints FAIL with the line and exits non-zero with no model call or cost; step 2 (line removed) runs the normal review. Step 3 is covered by Task 11. Repeat step 1 through the `/sq:review tasks` slash command and confirm the same FAIL output
- [ ] Add a DEVLOG entry for Phase 6 completion
  - [ ] Success: walkthrough results match the design
- [ ] Commit: `docs: record slice 933 implementation in DEVLOG`
