---
docType: tasks
slice: pipeline-tasks-review-covers-every-split-task-file
project: squadron
lld: user/slices/930-slice.pipeline-tasks-review-covers-every-split-task-file.md
dependencies: [195]
projectState: >
  Slice design written (2026-09-28), not yet implemented. Pipeline `review:` steps over a
  split task breakdown review only part 1 (`_tasks_input` returns `task_files[0]`). The CLI
  `sq review tasks` already reviews every part. Release 0.16.0 is current on main.
dateCreated: 20260929
dateUpdated: 20260929
status: in_progress
---

## Context Summary

- Working on **930 pipeline-tasks-review-covers-every-split-task-file**: fixes issue #153.
  A pipeline `review:` step gets the same per-part behavior `sq review tasks` has, and both
  callers share part naming and verdict folding through a new `review/parts.py`.
- Adds `review/parts.py`, `pipeline/actions/review_outputs.py`, and a fan-out flag in the
  template-input registry. Edits `ReviewAction`, `DispatchAction` feedback, `batch_report`,
  and CLI `review_tasks`. Fixes the latent `KeyError` on UNKNOWN in `_aggregate_verdicts`.
- Design decisions are in the slice design; tasks reference it by section rather than
  restating it. Each part's failure modes and the fold table are the contract.
- Out of scope: splitting/merging task files, cleaning old unsuffixed reviews, the
  context-forge gate (context-forge#106), parallel parts.
- Every task that changes code ends with `ruff format`, `ruff check`, `pyright` (zero
  errors) and the relevant tests before its commit.
- Effort: 2/5. Next planned slice: per `cf next` after 930 closes.

---

## Task 1 — Create the slice branch and pin single-file behavior

- [x] Confirm `cf config get git.integration_branch` is empty (target = `main`) and
      `git status` is clean
- [x] `git checkout -b 930-slice.pipeline-tasks-review-covers-every-split-task-file main`
  - [x] Success: `git branch --show-current` prints the new branch name

- [x] Add a characterization test for a one-task-file slice, **before any source change**,
      so it runs against unmodified code and guards every later task
  - [x] Create `tests/pipeline/actions/test_review_action_single_file.py` (follow
        `test_review_action.py` fixtures): run `ReviewAction` for a `tasks` review on a slice
        with one task file and a mocked review client
  - [x] Assert the saved artifact is unsuffixed and its content equals a checked-in snapshot
        (`tests/pipeline/actions/snapshots/`), and assert the `ActionResult` `outputs`
        keys/values, `verdict`, `findings`, and `metadata` against literals in the test
  - [x] Generate the snapshot by running this test on the current, unmodified branch and
        reading the output once
  - [x] Success: passes now; must keep passing, unedited, through Tasks 4, 6, 7 and 8
- [x] Format, lint, typecheck, commit: `test: pin single-file review action output before fan-out`

---

## Task 2 — `review/parts.py` (design: Component Structure, `review/parts.py`)

- [x] Create `src/squadron/review/parts.py`
  - [x] Frozen dataclass `ReviewPart` with `input_path: str`, `name_suffix: str | None`
  - [x] `review_parts(input_paths: list[str]) -> list[ReviewPart]`: suffix `None` for exactly
        one path, `part-1..part-N` (1-based) for two or more. This is the only place in the
        codebase that produces the `part-N` string
  - [x] Empty input raises `ValueError` (zero parts means nothing to review)
  - [x] `worst_verdict(verdicts: Iterable[str]) -> str` ranking `PASS < CONCERNS < FAIL <
        UNKNOWN` over `Verdict` values. Derive the rank table from the `Verdict` enum members
        (one definition, no string literals scattered)
  - [x] Ties return the first occurrence; a value outside `Verdict` raises `ValueError`;
        empty input raises `ValueError`
  - [x] Success: module has no imports from `cli/` or `pipeline/`

- [x] Create `tests/review/test_parts.py`
  - [x] `review_parts`: 1 path → `[ReviewPart(path, None)]`; 3 paths → suffixes `part-1`,
        `part-2`, `part-3` in order; empty raises
  - [x] `worst_verdict` parametrized: every ordered pair across the four verdicts, single
        value, all-UNKNOWN, PASS+UNKNOWN → UNKNOWN, a `Verdict` member passed directly
        (it is a `StrEnum`), empty raises, unknown string raises
  - [x] Tie behavior: the returned value equals the first of equal-rank inputs
  - [x] Success: `pytest tests/review/test_parts.py` passes

- [x] Format, lint, typecheck, commit: `feat: add review parts naming and worst-verdict fold`

---

## Task 3 — CLI `review_tasks` uses `parts.py` (design: Migration Plan)

- [x] In `src/squadron/cli/commands/review.py`, replace the inline
      `multi_part` / `f"part-{part_idx}"` logic in `review_tasks` with
      `review_parts(task_file_paths)`
  - [x] Iterate `review_parts(...)` and take `part.input_path` / `part.name_suffix`
  - [x] Keep the "Reviewing tasks part i of N" banner keyed on `len(parts) > 1`
  - [x] Keep `SaveOutcome` folding in the CLI (CLI-specific exit codes)
- [x] Replace `_exit_on(_aggregate_verdicts(...), outcome)` with
      `worst_verdict(str(r.verdict) for _, r in results)` and convert back with
      `Verdict(...)` for `_exit_on`
- [x] Delete `_aggregate_verdicts`; `grep -rn _aggregate_verdicts src tests` must be empty
      after updating any test that imported it
- [x] Tighten `results` to `list[tuple[str, ReviewResult]]` now that `getattr` is gone
  - [x] Success: existing CLI review tests pass unchanged

- [x] Add a CLI test in `tests/review/test_cli_review.py` (follow that file's existing
      split-tasks fixture): a two-part slice where part 2 parses UNKNOWN exits non-zero
      and does not raise `KeyError`
  - [x] Success: the test fails on the old `_aggregate_verdicts` and passes now

- [x] Format, lint, typecheck, commit: `refactor: share part naming and verdict fold in review_tasks`

---

## Task 4 — Registry fan-out in `template_inputs.py` (design: `template_inputs.py`)

- [x] `TemplateInputSpec`: add `fans_out: bool = False`; change `source` type to
      `Callable[[SliceInfo, str], list[str]]`
- [x] Convert the scalar sources (`_design_file`, `_arch_file`, `_diff_range`) to return a
      one-element list, or `[]` when they have nothing. Rename `_tasks_input` to
      `_task_files` and have it return every task file path (`TASKS_DIR / name`, in
      `info["task_files"]` order)
- [x] Set `fans_out=True` on the `input` spec of both `tasks` and `judge.tasks-vs-slice`
- [x] Add `resolve_template_input_parts(template_name, info, cwd, inputs) -> list[dict[str, str]]`
      and delete `resolve_template_inputs`
  - [x] Does not mutate `inputs`; returns one dict per part, scalar keys copied into each
  - [x] A key already in `inputs` wins and is not fanned out (explicit `input:` → one part)
  - [x] More than one `fans_out` spec in an entry raises `ValueError`
  - [x] Fan-out source returning `[]` → one dict without that key (the existing
        missing-required-input `KeyError` in `ReviewAction` still reports it)
  - [x] Unknown template name → `[dict(inputs)]` (one unchanged dict)
- [x] Interim shim so the build stays green: in `ReviewAction._resolve_slice_inputs`
      (`pipeline/actions/review.py`) call the new function and update `inputs` from the
      first dict only. Comment it as temporary; Task 7a replaces it
- [x] Update the stale reference to `_tasks_input` in the docstring at
      `src/squadron/pr/tasks.py` (grep confirmed it is the only non-test mention)

- [x] Update `tests/review/test_template_inputs.py`: migrate every `resolve_template_inputs`
      call to the new function (it returns dicts instead of mutating), keeping each test's
      intent
  - [x] New: multi-file `tasks` yields K dicts sharing one `against`, `input` differs
  - [x] New: multi-file `judge.tasks-vs-slice` fans out the same way
  - [x] New: caller-supplied `input` yields exactly one dict with the caller's value
  - [x] New: two `fans_out` specs in one entry raise `ValueError` (use a monkeypatched
        registry entry)
  - [x] New: empty task list yields one dict with no `input` key
  - [x] New: the input `inputs` dict is not mutated
  - [x] Success: `pytest tests/review/test_template_inputs.py tests/pipeline/actions/test_review_action.py`
        passes with the interim shim

- [x] Format, lint, typecheck, commit: `feat: fan out task-file inputs per part in the template registry`

---

## Task 5 — `review_outputs.py` (design: The output contract)

- [x] Create `src/squadron/pipeline/actions/review_outputs.py`
  - [x] `ReviewOutputKey(StrEnum)` with `RESPONSE`, `INPUT_FILE`, `INPUT_FILES`,
        `REVIEW_FILE`, `REVIEW_FILES`, `UNSAVED_PARTS`. Values `response`, `input_file`,
        `input_files`, `review_file`, `review_files`, `unsaved_parts`; the first four
        single-part values must match the literals used today
  - [x] `FINDING_INPUT_FILE = "input_file"` (per-finding key)
  - [x] `review_input_files(result) -> list[str]`: `INPUT_FILES` if present, else
        `[INPUT_FILE]` if present, else `[]`
  - [x] `unsaved_parts(result) -> list[str]`: `[]` when absent
  - [x] `finding_input_file(finding) -> str | None`
  - [x] A present key with the wrong type (for example `input_files` not a `list[str]`,
        `input_file` not a `str`, a non-string finding value) raises `TypeError`; never
        treated as absent
  - [x] Success: pyright strict passes with no `cast` in the readers (narrow with
        `isinstance`)

- [x] Create `tests/pipeline/actions/test_review_outputs.py`
  - [x] Each reader: key absent, correct shape, wrong shape (`TypeError`)
  - [x] `review_input_files` prefers `INPUT_FILES` over `INPUT_FILE` when both exist
  - [x] Key values equal the legacy literals for the single-part keys
  - [x] Success: passes

- [x] Format, lint, typecheck, commit: `feat: add typed review output keys and readers`

---

## Task 6 — Extract `_run_part` from `ReviewAction._review` (pure refactor)

Behavior must not change; this task exists so Task 7a adds the loop to small functions.

- [x] In `src/squadron/pipeline/actions/review.py`, move the model call, provider-failure
      artifact, judge enforcement, save, and per-part `ActionResult` construction out of
      `_review` into `async def _run_part(...)`
  - [x] Parameters carry everything the moved code reads today (template, inputs for this
        part, model/profile, rules content, allowed tools, `slice_info`, `context`,
        `rules_source`); use a small frozen dataclass for the shared per-review settings
        rather than a 12-argument signature
  - [x] `_run_part` returns the same `ActionResult` `_review` returns today, and takes an
        optional `name_suffix` (unused until Task 7a; passes through to both save calls and
        `_save_failure_artifact`)
  - [x] `_review` keeps template/model/profile resolution, input building, validation,
        and rules resolution, then calls `_run_part` once
  - [x] Success: `_review` and `_run_part` each fit within ~50 lines of code; both save
        branches (`slice_info` and step-target) still exist exactly once
- [x] Use `ReviewOutputKey` members for the output keys written here (single-part values
      are unchanged)
  - [x] Success: `pytest tests/pipeline/actions/test_review_action.py tests/pipeline/actions/test_review_action_integration.py`
        passes with **no test edits**
  - [x] Success: `tests/pipeline/actions/test_review_action_single_file.py` (Task 1) also
        passes unedited, so the saved artifact is byte-identical to the pre-change snapshot

- [x] Format, lint, typecheck, commit: `refactor: extract per-part run from ReviewAction`

---

## Task 7a — Part loop, validation, and failure handling in `ReviewAction` (design: Data Flow, Failure Modes)

Until Task 7b lands, multiple parts return the **last** part's `ActionResult` (temporary,
commented as such); single-part behavior is already final.

- [x] Replace the interim shim: `_resolve_slice_inputs` returns
      `tuple[SliceInfo | None, list[dict[str, str]]]`; it returns `(None, [inputs])` when
      the slice cannot be resolved (existing WARNING preserved) and calls
      `resolve_template_input_parts` otherwise
- [x] In `_review`, when a slice is given and no explicit `input`, use the returned part
      dicts; otherwise `[inputs]`
- [x] Validate **every** part before the first model call: required inputs (existing
      `KeyError`) and `missing_input_files` (existing `KeyError`), each message naming the part
- [x] Compute `review_parts([p["input"] ...])` once for suffixes (single part with no
      `input` key, as today, stays a one-part run with no suffix)
- [x] Run parts sequentially. Before each model call log INFO
      `review: step %s part %d/%d: %s` (multi-part only)
- [x] Provider failure on part k: failure artifact into part k's slot via its suffix, log
      WARNING `review: provider failed in step %s part %d/%d; failure artifact: %s`,
      re-raise; parts already saved stay, later parts do not run. Single part keeps today's
      WARNING text
- [x] Save failure on part k stays non-fatal (existing `except`), logs via
      `logger.exception` naming the part; that part is recorded as unsaved

- [x] Tests in `tests/pipeline/actions/test_review_action.py` (follow its fixtures; add a
      sibling `test_review_action_parts.py` if the file would pass ~450 lines)
  - [x] 2 task files → 2 review calls in order, saves `…part-1.md` and `…part-2.md`, each
        `sourceDocument` names its own file
  - [x] Missing part-2 file raises `KeyError` **before any model call** (assert zero calls)
  - [x] Provider failure on part 2: part 1 artifact kept, failure artifact written under
        `part-2`, part-numbered WARNING present (`caplog`), step result `success=False`
  - [x] Save failure on part 2: later work continues, ERROR logged (`caplog`), part 2 recorded
        as unsaved
  - [x] Explicit `input:` with `slice:` → one part, unsuffixed
  - [x] Success: all pass, and `test_review_action_single_file.py` still passes unedited

- [x] Format, lint, typecheck, commit: `feat: run every split task file through the review action`

---

## Task 7b — `_fold` (design: Folding)

- [x] Implement `_fold(part_results)` per the design's fold table
  - [x] One part → return that `ActionResult` unchanged (identical to today, including
        the no-`review_file` result when a single save failed)
  - [x] `verdict`: `worst_verdict` over parts (values already judge-enforced per part)
  - [x] `provenance`: from the first part
  - [x] `findings`: all parts' findings in order, each dict gets `FINDING_INPUT_FILE`
        naming its part (copy the dict; do not mutate `StructuredFinding.__dict__`)
  - [x] `score` / `criteria`: from the lowest-scoring part among parts with a score, first
        part on ties; `None` only when no part has a score
  - [x] outputs: `RESPONSE` = parts' raw outputs joined under `## <input path>` headers;
        `INPUT_FILES` / `REVIEW_FILES` in part order (review files only for saved parts);
        `INPUT_FILE` / `REVIEW_FILE` = the worst-verdict part (first on ties; if that
        part is unsaved, `REVIEW_FILE` is omitted); `UNSAVED_PARTS` only when non-empty
  - [x] metadata: first part's values; `tool_calls_made` summed when present
- [x] Remove the Task 7a "last part's result" stopgap; `_review` returns `_fold(results)`

- [x] Tests (same files as Task 7a)
  - [x] PASS + CONCERNS → verdict CONCERNS; `REVIEW_FILE` and `INPUT_FILE` point at the
        CONCERNS part; findings carry `input_file`
  - [x] PASS + UNKNOWN → UNKNOWN; tie → first part is `REVIEW_FILE`
  - [x] Judge template (`judge.tasks-vs-slice`): per-part enforcement, lowest score wins,
        a part with no score is skipped, all-unscored gives `None`
  - [x] Judge part whose verdict degrades to UNKNOWN still reports the lowest real score
  - [x] `RESPONSE` joins each part's raw output under a `## <input path>` header, in order
  - [x] `tool_calls_made` metadata is the sum across parts; `provenance` is the first part's
  - [x] Worst-verdict part unsaved → `REVIEW_FILE` omitted, `UNSAVED_PARTS` lists that
        part's input path, `REVIEW_FILES` holds only saved parts
  - [x] Save failure on part 2: folded verdict still returned (completes the Task 7a case)
  - [x] Success: all pass

- [x] Format, lint, typecheck, commit: `feat: fold per-part review results into one worst-verdict result`

---

## Task 7c — Single-file regression check

- [x] Run `tests/pipeline/actions/test_review_action_single_file.py` (Task 1), unedited,
      against the final `ReviewAction`
  - [x] Success: passes — the unsuffixed artifact is byte-identical to the snapshot taken
        on pre-change code, and the `ActionResult` matches
  - [x] If it fails, fix the code; never regenerate the snapshot to make it pass
- [x] No commit unless a fix was needed: `fix: restore single-file review action output`

---

## Task 8 — Multi-file feedback prompt in dispatch (design: Feedback dispatch)

- [x] In `DispatchAction._resolve_feedback_prompt`, read files through
      `review_input_files(review)`; no string literal `"input_file"` remains in
      `dispatch.py`
  - [x] More than one file → "Revise each of these files in place; do not create new
        files:" followed by one bullet per path
  - [x] Exactly one file → today's sentence, byte-identical
  - [x] Zero files → no revise sentence (as today)
- [x] In `_findings_block`, append ` — <file>` when `finding_input_file(finding)` is set;
      findings without the key render exactly as today

- [x] Tests in `tests/pipeline/actions/test_dispatch.py`
  - [x] Multi-file review → prompt lists every file and each finding names its file
  - [x] Single-file review → prompt string equals today's (assert the full string)
  - [x] Wrong-typed `input_files` output raises `TypeError` through the dispatch path
  - [x] Success: passes

- [x] Format, lint, typecheck, commit: `feat: name every part file in review feedback dispatch`

---

## Task 9 — Batch report shows unsaved parts (design: Failure Modes, last paragraph)

- [x] `BatchItemRecord`: add `unsaved_parts: list[str]` (default empty), filled from the
      **last review action's** `unsaved_parts(result)`; `_last_review_file` reads through
      `ReviewOutputKey.REVIEW_FILE` (no `"review_file"` literal left in `batch_report.py`)
- [x] `render_line`: append `unsaved: <paths joined by ", ">` when non-empty
  - [x] Success: a line with no unsaved parts is byte-identical to today's

- [x] Tests in `tests/pipeline/test_batch_report.py`
  - [x] Item whose review `ActionResult` carries `UNSAVED_PARTS` renders `unsaved: …`
  - [x] Item without it renders as before
  - [x] Success: passes

- [x] Format, lint, typecheck, commit: `feat: report unsaved review parts in the batch report`

---

## Task 10 — CLI/pipeline parity test (design: Success Criteria, Technical Requirements)

- [x] Add a test that builds one fixture slice with 3 task files and runs both
      `review_tasks` (CLI, model mocked at the existing review-client boundary) and a
      pipeline `review: {template: tasks, slice: N}` step, then compares the **set of
      review filenames** each wrote
  - [x] Place it where both fixtures are reachable (`tests/review/`), reusing existing
        helpers rather than new scaffolding
  - [x] Also assert no unsuffixed `…tasks….md` file exists from either run
  - [x] Success: passes; fails if either side's suffix logic is changed

- [x] Integration requirement check: add or extend a `tasks-plan`-style loop test where
      part 1 PASSes and part 2 CONCERNS: with `skip_if_met: true` and `until: review.pass`
      the loop runs a revise round (does not log "already met")
  - [x] Success: passes

- [x] Format, lint, typecheck, commit: `test: assert CLI and pipeline write identical part artifacts`

---

## Task 11 — Full validation

- [x] `ruff format --check`, `ruff check`, `pyright` (zero errors), full `pytest` — run
      once each and read the output
- [x] `grep -rn "resolve_template_inputs\|_tasks_input\|_aggregate_verdicts" src tests`
      returns nothing
- [x] `grep -n '"input_file"\|"review_file"' src/squadron/pipeline/actions/dispatch.py src/squadron/pipeline/batch_report.py`
      returns nothing
- [x] No failing tests attributable to this slice. Failures from cf schema drift
      (context-forge #88) are pre-existing; list them, do not fix them here
  - [x] Success: all commands above clean

---

## Task 12 — Verification walkthrough against slice 914 (design: Verification Walkthrough)

Costs real model calls with `glm-flash`; run exactly the design's steps.

- [ ] Steps 1-2: confirm `914-tasks.*` has `-1/-2/-3`; if the stale unsuffixed
      `914-review.tasks.strict-type-checking-over-the-test-suite.md` exists, `git rm` it
- [ ] Step 3-4: save `/tmp/review-tasks-only.yaml` from the design, run
      `sq run /tmp/review-tasks-only.yaml 914 -v`; expect three calls in order and
      `part-1..part-3` artifacts, each `sourceDocument` naming its own file. If `sq run`
      rejects a file path, copy the YAML into the project pipelines directory and delete
      the copy afterward
- [ ] Step 5: `sq review tasks 914 --model glm-flash`; same three filenames, no new
      unsuffixed file
- [ ] Step 6: review-step verdict equals the worst of the three `verdict:` values; the
      loop log does not say `review.pass already met; 0 rounds run` when any part is below PASS
- [ ] Step 7: same pipeline on a one-task-file slice saves an unsuffixed artifact
  - [ ] Success: each step's expectation is met; any deviation is recorded and fixed
        before Task 13. Commit review artifacts only if the PM wants them kept

---

## Task 13 — Close out

- [ ] Add a short user-facing CHANGELOG bullet (technical detail goes in DEVLOG)
- [ ] Mark every task above `[x]`, including dropped items, before closing (the
      visualizer reads checkbox state)
- [ ] Set slice design `status: complete` and check the 930 entry in
      `900-slices.maintenance-and-refactoring.md`
- [ ] Add a DEVLOG entry (Session State Summary format)
- [ ] Run `sq review code` for slice 930 with an explicit `--model`; fix or record findings
- [ ] Commit the close-out changes on the slice branch: `docs: close out slice 930`
- [ ] Merge into the target: re-read `cf config get git.integration_branch`, then
      `git checkout main && git merge 930-slice.pipeline-tasks-review-covers-every-split-task-file`;
      if either command fails, stop and ask the Project Manager
  - [ ] Success: `git log --oneline -1` on main shows the slice's last commit; issue #153
        is referenced in the closing commit or comment
