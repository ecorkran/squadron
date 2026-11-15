---
docType: review
layer: project
reviewType: code
slice: slice-cases
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/426-slice.slice-cases.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: eeba535072da261a6110d63f3db996c7e6f5ec47
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
diffTruncated: false
effort: xhigh
turns: 23
promptTokens: 3464341
cachedTokens: 3066801
cacheWriteTokens: 397522
completionTokens: 69730
durationSeconds: 322.5
costUsd: 0.878913
costBasis: provider
runId: run-20261115-p6-26b3510a
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: consistency-rot
    summary: "Case language is hard-coded in the slice-case CLI, separate from the production source of truth"
    location: "src/squadron/cli/commands/benchmark_slice.py:59-60"
  - id: F002
    severity: concern
    category: correctness
    summary: "The printed cost bound rounds the per-call figure to cents"
    location: "src/squadron/benchmark/diff_judge_plan.py:225-231"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "Duplicated pair-verdict wording and an identical pairwise model"
    location: "src/squadron/benchmark/pairwise_render.py:21-26"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "`JudgeOptions.repos` is never read"
    location: "src/squadron/cli/commands/benchmark_judge.py:76"
  - id: F005
    severity: note
    category: test-debt
    summary: "The pipeline test's forfeit assertion cannot fail"
    location: "tests/benchmark/test_slice_pipeline_end_to_end.py:188"
  - id: F006
    severity: note
    category: test-debt
    summary: "The real-git normalization test uses a three-way disjunction"
    location: "tests/benchmark/test_diff_normalize.py:211"
  - id: F007
    severity: note
    category: performance-resource
    summary: "Repeated per-call work in the pairwise report and the judge prompt"
    location: "src/squadron/benchmark/pairwise_report.py:76"
  - id: F008
    severity: note
    category: correctness
    summary: "Judged diffs are text-mode captures, so CRLF is normalized before the judge sees it"
    location: "src/squadron/benchmark/diff_judge_reference.py:45"
  - id: F009
    severity: note
    category: other
    summary: "This branch carries slice 402's work"
    location: "src/squadron/metrology/review_ingest.py"
  - id: F010
    severity: pass
    category: other
    summary: "New imports and production wiring resolve"
    location: "src/squadron/benchmark/production_deps.py:230-240"
  - id: F011
    severity: pass
    category: correctness
    summary: "Judge cost accounting charges every call"
    location: "src/squadron/benchmark/diff_judge_budget.py#metered"
---

# Review: code — slice 426

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 22 successful tool call(s) of 22 made; 688148 of 688148 diff characters reached the model

## Findings

### [CONCERN] Case language is hard-coded in the slice-case CLI, separate from the production source of truth

`build_deps` passes `SourceLanguage.PYTHON` twice, to the fix-case adapter and to the suite runner. The production path defines `CASE_LANGUAGE = SourceLanguage.PYTHON` at `src/squadron/benchmark/production_deps.py:66` and passes it to `register_slice_runner` at `production_deps.py:236`. Grading also reads `CASE_LANGUAGE` (`grade_services.py:88,106,132`). Changing the constant therefore moves the runner and grading while `sq benchmark slice-cases build` stays on Python, so the two entry points can diverge without an error. Import the shared constant into the CLI. The same literal already appears in `case_build.py:129,132`, which predates this slice.

### [CONCERN] The printed cost bound rounds the per-call figure to cents

`render_bound` formats the per-call figure with `:.2f` (`source = f"{figure:.2f} ..."` at line 226, and the overshoot line at 231). A judge call costing under half a cent prints as `$0.00 (max observed)`. The total is also formatted from the full-precision value, so a line can read `= $0.10, capped at run cap $0.10` while the branch was chosen on the unrounded numbers. This is the one cost statement the operator reads before spending, and D16 requires it to be stated. Format with enough precision to show the smallest figure, or print a sub-cent figure in scientific notation.

### [CONCERN] Duplicated pair-verdict wording and an identical pairwise model

Three places repeat the same logic:
- The `PairVerdict` to wording mapping (`A_AHEAD`, `B_AHEAD`, `NOT_DISTINGUISHABLE`, `TOO_FEW_CASES`) is in `_pair_line` at `pairwise_render.py:21-26` and in `pair_text` at `report_fix_table.py:176-182`. A wording change has to be made twice.
- `PairwisePair` in `pairwise_models.py` has the same fields as `PairRow` at `report_models.py:64-73` (`label_a`, `label_b`, `n_cases`, `mean_difference`, `low`, `high`, `verdict`). Reuse `PairRow` or extract the shared shape.
- `render_slice_table` (`report_slice_table.py:86`) re-implements the checks block of `render_fix_table` (`report_fix_table.py:215-221`), where it only differs by heading and column set.

Each copy is small, but the verdict mapping and the model shape are real duplication, not similar code that changes for different reasons.

### [NOTE] `JudgeOptions.repos` is never read

The field is populated by the positional `JudgeOptions(...)` call in `make_judge_command`, but no code reads `options.repos`. `_execute` and `_plan` take the repository list as a separate argument. Remove the field.

### [NOTE] The pipeline test's forfeit assertion cannot fail

`assert "forfeit" in pairwise` always passes, because the pairwise header always contains the word `forfeit` (`pairwise_render.py:40`). Forfeit handling is covered in `test_pairwise_report.py` and `test_diff_judge_loop.py`, but this end-to-end assertion adds nothing. Assert the forfeit count on the `opus` row, for example by parsing that row.

### [NOTE] The real-git normalization test uses a three-way disjunction

`assert kept in result.text or f'"{kept}"' in result.text or "caf\\303\\251" in result.text` passes if any one of the three conditions holds. This is the only test that runs normalization over a real git diff, and it would not notice a kept section being dropped. Assert each kept path's exact `diff --git` header, using the quoted form for the non-ASCII name.

### [NOTE] Repeated per-call work in the pairwise report and the judge prompt

`set(slice_cases)` is rebuilt inside a comprehension on each judgment (line 76), and again on each over-size record (line 259). Hoist it to a local. Separately, `diff_prompt.py:18-20` reads and parses the packaged prompt file on every call, and `diff_prompt` runs once for each pair in `check_size` and once per judge call. Cache the file read with `functools.cache`. Both costs are small at current benchmark sizes.

### [NOTE] Judged diffs are text-mode captures, so CRLF is normalized before the judge sees it

`SubprocessRunner` runs with `text=True` (`core/process_runner.py:138`), so universal newlines rewrite `\r\n` to `\n` before `ReferenceDiffReader` re-encodes the result. Replay diffs take the same path (`replay_one.py:91-98`), so the contestants are treated consistently. `normalize`'s docstring says kept sections are "copied verbatim, line endings included", which holds for its input but not for the bytes that were stored. Document this at the reader, or capture bytes if faithful diffs matter.

### [NOTE] This branch carries slice 402's work

The diff from `afeb630` includes slice 402's code-review normalization and ingest: `review/categories.py`, `metrology/review_ingest.py`, `cli/commands/metrology_review_ingest.py`, its tests, its task and review files, and its DEVLOG entries. None of this is part of 426's design. Per AGENTS.md, slice branches fork from the target, so either the 426 branch was cut from the 402 branch or 402 was merged in. I reviewed these files only for the defects I could see in the hunks. The PM should confirm the branch base before merging 426.

### [PASS] New imports and production wiring resolve

Every symbol the diff imports exists: `select_remote`, `halt`, `AbsenceClass`, `strip_frontmatter`, `tail_text`, `SidecarKind`, `ProcessCwdNotFoundError`, `serves_host`, `PullRequestTarget`, and the codehost errors. `_Sandboxes.at` and `_positive_int` exist, so `register_slice_runner` receives a real factory. `Contestant` in `replay/judging.py` is still used, so it is not an unused import.

### [PASS] Judge cost accounting charges every call

The `metered` docstring says no call is counted as free. That holds: `one_shot_judge_dispatcher` (`replay/judge_dispatch.py:57-60`) re-raises every `Exception` as `JudgeCallError`, and `metered` charges on `JudgeCallError` and on `CancelledError`, which is how `wait_for` cuts a timed-out call. The `replay/judging.py` refactor keeps the call counting and the rule that a failed first call dispatches no second call.

### Run Digest

- Response length: 9503 chars
- Response is newline-free: no
- Tool calls made: 22
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 23
- Tokens — prompt / cached / cache write / completion / reasoning: 3464341 / 3066801 / 397522 / 69730 / not computed
- Duration: 322.5 s
- Cost: $0.88 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
