---
docType: reference
project: squadron
dateCreated: 20261115
dateUpdated: 20261115
status: draft
---

# Design and task review recall: candidate cases (mining spike, 2026-11-15)

Read-only pass over `/Users/manta/source/repos/manta/squadron`. 15 candidates examined (the stop limit), all from squadron; no sibling repo was needed. Nothing was checked out, no model was called.

Validity rule applied (from `review-recall-runbook.md` and `review-recall-cases.md`, carried over to documents): a flaw counts only if, at the reviewed commit, the document contradicted itself, its parent, or code in the repo at that commit, left out something its own success criteria required, or held a task that could not be completed as written, and a later commit proves it. It does not count if the correction follows a later decision or scope change, adds a capability or gate, fills in an unspecified detail, or records names and facts that only existed after other slices were built. Borderline items are marked INVALID and tagged `borderline`.

Labels on evidence: **read** = I read the diff and the reviewed text or code named; **inferred** = judged from a commit subject or from the task file's own description without checking the code.

## Totals

- Candidates examined: 15
- Cases with at least one valid flaw: 9
- Valid flaws: 25 (12 need only the document, 11 need code at the reviewed commit, 2 are uncompletable tasks that need the design plus an estimate of run time)
- Invalid or unproven: 57 (6 tagged borderline; 17 unproven, all in 427)
- Source of the valid ones: 20 of 25 come from the design corrections each 42x task file records in its Context Summary ("Design gaps found while reading the code", or for 420 and 421 a correction raised by the task review), written one or two days after the design review and applied later by a `docs: correct slice NNN design` commit or by the implementation. 2 come from the 426 live-run tasks. 3 come from older one-off `docs: correct ... design` commits (915, 302).

## What makes the reviewed-at commit unreliable

1. **No design or task review in 420–427 has verdict PASS.** Every one is CONCERNS, committed as "review: CONCERNS, findings addressed". Nothing "passed"; the loop ended and the findings were addressed by edit.
2. **420–427 designs: the reviewed text is not in git.** All eight design reviews have `reviewedSha: ef6d51a9` (or `f2bf39ab` for 427's re-review), a commit where the design file did not exist yet (it was untracked). The design and its review were then committed together with the findings already addressed. The 425 review body confirms this: it complains D7 "sets no timeout", and the committed D7 has one. So the committed design was never re-reviewed, and some flaws were introduced by the addressing edits (425 "one reference per digest" and the cap departure; 426 "No edits to 424 or 425"). The snapshot to give other reviewers is the commit that added the design; whether the original review "missed" a flaw cannot be established for these.
3. **420–427 task files: the reviewed text is recoverable, but only through `refs/squadron/pre-collapse/<sha>`.** The task-review `reviewedSha` values (for example `6e72e0f7`) are not on `main`; they live under those refs (9 exist). The final committed file differs from the reviewed one (426: 138 insertions, 116 deletions after the last review, and tasks renumbered: reviewed Tasks 22/25/39 are final Tasks 23/26/41).
4. **`494b3d50` (the 426 correction) is on no branch or ref.** Only the reflog holds it; gc can remove it. Its content survives squashed inside `3958b48b`.
5. **Older reviews often have no `reviewedSha`** (181, 302, 322, 911, 191), or a `reviewedSha` that is the correcting commit or later (265, 195, 920, 923, 914, 403), meaning the correction came before the saved review. Those were screened out (list at the end).
6. **Clean on all counts:** only squadron-915-design (PASS, `reviewedSha` is the commit that added the design, correction 41 minutes after the review was committed).

---

## 1. squadron-420-design

- repo squadron; `project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md`; kind design
- reviewed-at: `5f4975ae` (commit that added design and review together; see caveat 2). Review `reviews/420-review.slice.effort-audit-across-dispatch-paths.md`, CONCERNS, claude-sonnet-5-5.
- correcting commit: `1b710c4e` "docs: align 420 design with task review (D5 stamp limit, D6 scope)" (read)
- flaws:
  - D5: says `stamp_effort_sent` also runs in the `except Exception` branch of `DispatchAction.execute`. The effort is resolved inside `_dispatch` and is not in scope there (`dispatch.py` at `5f4975ae`: `execute` line 423, `except` 467, `_dispatch` 515). **VALID**: contradicts code. Needs: code.
  - Success Criteria: "same model, profile and effort fall into one report row", while Overview and D6 define identity as five fields including `tool_use` and `max_output_tokens`. **VALID** (minor): self-contradiction. Needs: document alone.
  - D6 scope ("covers producer configs only", judge tables keyed on alias). INVALID: a clarification; the task review's claim was rejected.
  - New module `replay/config_label.py` (report.py over its line budget). INVALID: implementation fact.

## 2. squadron-421-design

- `project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md`; design
- reviewed-at: `a6c862e5` (added with review; caveat 2). Review `421-review.slice.benchmark-sandbox-and-case-record.md`, CONCERNS, claude-sonnet-5-5.
- correcting commit: `f5696cda` "docs: correct slice 421 design on ProcessRunner environment" (read)
- flaws:
  - Interfaces Required and D7: "`ProcessRunner`'s `env` parameter already lets every child process get the scrubbed environment". `core/process_runner.py:117-118` at `a6c862e5` merges: `{**os.environ, **env}`, so GH_TOKEN and the rest survive. **VALID**: contradicts code, and defeats the slice's containment goal. Needs: code. Found by the 421 task review (haiku), so a reviewer with tools can find it.

## 3. squadron-422-design

- `project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md`; design
- reviewed-at: `16c6575f` (added with review; caveat 2). Review `422-review.slice.fix-case-qualification-and-yield-report-keystone.md`, CONCERNS, claude-sonnet-5-5.
- correcting commits: `160b9a35` "feat: complete fix case qualification and yield report slice" (design edits for gaps 1-3, read) and `f86fc93e` "docs: bound 422 design walkthrough to one full run and small samples" (read). Gaps are listed in the 422 task file at `89520205`.
- flaws:
  - API Contracts: `is_test_side(self, tree: Path, path)`, but diff classification runs before any sandbox exists (Data Flow step order), so there is no tree to read. Corrected to take the parent's `pyproject.toml` text. **VALID**: self-contradiction. Needs: document alone.
  - Component list says `FairnessVerdict`; the protocol's `trace` returns `TraceVerdict`, which is defined nowhere. **VALID** (minor): self-contradiction. Needs: document alone.
  - Walkthrough step 4: "every line says `reused`", but D10 keys reuse on the sandbox's environment identity, so candidates rejected before the sandbox are recomputed. **VALID**: self-contradiction. Needs: document alone.
  - `trace` lacks an `AllowedBoundary` parameter. INVALID (borderline): an interface refinement; the adapter could have computed it.
  - Success Criteria name ebd45f3f, 9fc4fc1c, d6535d62 as real examples; the last two both close #291 (rejected by the design's own `multiple_closing_commits`), the first has no closing keyword. INVALID (borderline): the criterion does not say they must qualify through `build`, and the tasks tested them directly.
  - Walkthrough bounded to one full-history run and samples (`f86fc93e`). INVALID: a cost decision made after the first run.

## 4. squadron-422-tasks

- `project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md`; tasks
- reviewed-at: `8875b059` (`reviewedSha`, under `refs/squadron/pre-collapse/89520205…`); final commit `89520205`. Review `422-review.tasks.…md`, CONCERNS, claude-haiku-5-5, revision 2.
- correcting commit: `4f1ff988` "docs: bound 422 tasks 29 and 30 to existing records and small samples" (read)
- flaws:
  - Task 29: full `fix-cases build` by hand, BLOCKED if any of five example categories has no instance. INVALID: the run did complete once; the correction follows its result (1 qualified of 94) and a cost decision.
  - Task 30: walkthrough reruns the whole history. INVALID: same; a cost bound added after the run.

## 5. squadron-423-design

- `project-documents/user/slices/423-slice.fix-pipeline.md`; design
- reviewed-at: `bda5ce4b` (added with review; caveat 2). Review `423-review.slice.fix-pipeline.md`, CONCERNS, claude-sonnet-5-5.
- correcting commit: `3d0e78ca` "docs: add slice 423 tasks (review: CONCERNS)" records the corrections ("the design is not edited; these tasks follow the corrections"); implemented in `2cc45688`. I read the task file's list and checked the code at `bda5ce4b`; I did not read the implementation diff. The design text itself was never corrected, so the flaws are still in the current file.
- flaws:
  - D2: `fix-context` outputs `operation: build_context` and `context`, "so `DispatchAction` does not change". `_resolve_prompt` at `bda5ce4b` accepts only `action_type == CF_OP` and reads `outputs["stdout"]`. **VALID**: contradicts code. Needs: code. Confirmed by the 423 task review.
  - Component list names a class `IssueSource` (fetch or read the text) and Patterns names an `IssueSource` StrEnum (`file`, `github`). **VALID** (minor): self-contradiction. Needs: document alone.
  - D9/API: prompt-only renders `sq _fix-prompt … [--io-dir DIR]`, but `sq run` refuses `--io-dir` with `--prompt-only` (`run.py:1214` at `bda5ce4b`), so the flag can never be passed. **VALID** (minor): contradicts code. Needs: code.
  - D6 "any attribution lines the commit action already adds" (it adds none). INVALID: vacuously true, no behavior defect.
  - D8 `importlib.resources` versus `data_dir()`. INVALID: a convention detail; `data_dir()` wraps it.
  - One shared commit path for `sq _commit` and the action. INVALID: design refinement.
  - Start-branch check added to D5/D9. INVALID: a new gate.

## 6. squadron-424-design

- `project-documents/user/slices/424-slice.producer-only-replay-runner.md`; design
- reviewed-at: `9de42833` (added with review; caveat 2). Review `424-review.slice.producer-only-replay-runner.md`, CONCERNS, claude-sonnet-5-5.
- correcting commits: gap list in the task file at `1258e664`; `3d44ad04` changes one sentence. Gap list read; not checked against code (inferred).
- flaws (all INVALID):
  - `run.py` is ~1560 lines, new logic goes in a new module: file-size fact, structure choice.
  - Resume reload re-applies the transform: clarification.
  - Extra refused flags (`--explain`, `--validate`, `--status`, `--step-done`, `--next`): unspecified detail filled in.
  - `--max-cost`/`--io-dir` with `--prompt-only` stay refused: no change.
  - `RunState.producer_only` plumbing: implementation detail.
  - `benchmark.planned_samples` unset refuses: clarification.
  - "`bench_plan` arithmetic, which 425 extends with grading terms" (`3d44ad04`): follows 425's own decision.

## 7. squadron-425-design

- `project-documents/user/slices/425-slice.grading-and-paired-report.md`; design
- reviewed-at: `0f570296` (added with review; caveat 2). No commit touched the design between `0f570296` and the correction, so the `-` lines of the correction are the reviewed-at text. Review `425-review.slice.grading-and-paired-report.md`, CONCERNS, claude-sonnet-5-5, 6 findings.
- correcting commit: `3d44ad04` "docs: correct slice 425 design, add its grading cap to the slice plan, fix 424's bound sentence" (read in full; gap list in the task file at `e43d0334`)
- flaws:
  - D12: `measure_snapshot(root, …, commit_sha)` extracted from `take_snapshot_at` with no file list; the code measures `exported.files` from `export_commit` (`snapshot/take.py:186` at `0f570296`), which a sandbox tree does not have. **VALID**: contradicts code. Needs: code.
  - Database Schema: "a grade record stays under 16 KB", but `GradeResult` holds `hidden: tuple[NodeResult, …]`, `hidden_id_map` and full review findings, all unbounded. **VALID**: self-contradiction. Needs: document alone.
  - D13 keys rows on `(alias, model, profile, effort_sent)`; the design's own Prerequisites say rows group by 420's five-field identity. **VALID**: self-contradiction. Needs: document alone.
  - D7 puts `rules_hash` in `ReviewerRef` and takes rules from the start commit's tree (differs per case); D10 says the grader identity, which contains `ReviewerRef`, is one value per benchmark. **VALID**: self-contradiction. Needs: document alone. The review reported the same shape for the environment digest (F001) and missed this one.
  - API Contracts: `inject_hidden(tree, case, reference)`, but D4 injects "the import lines the reference added to `conftest.py`", which needs the start tree. **VALID**: self-contradiction. Needs: document alone.
  - Schema: `lockfile_sha256: str` is required, but D5 records it only on a reinstall and a tree may have no lock. **VALID** (minor): self-contradiction. Needs: document alone. Found by the 425 task review (F005).
  - Empty selections reach `run_suite` (pytest with no ids runs everything). INVALID (borderline): real hazard, but it rests on 421's runner and pytest behavior, not on this document, its parent or existing code.
  - One reference per (case, environment digest). INVALID (borderline): rests on 424's replays; text came from addressing review F001.
  - `_stat` is private in `audit_variance`. INVALID: naming, no contradiction.
  - `benchmark.review_timeout_s` has no stated default. INVALID: unspecified detail.
  - Seed derivation and cases-needed formula. INVALID: unspecified detail.
  - Report table registry for 426. INVALID: added extension point.
  - Absences for malformed producer TOML and a hung reinstall. INVALID: an added failure mode; the review's F002 raised the same class.
  - Reference-grade lookup path. INVALID (borderline): unspecified detail; found by the task review (F007).
  - Walkthrough names `test_grade_one.py`. INVALID: the other name was chosen later.
  - Grade models and store move to their own modules. INVALID: rests on other slices' file sizes.
  - D9 "departs from the architecture" on the grading cap. INVALID as a miss: the review reported it (F003); a control at most.

## 8. squadron-425-tasks

- `project-documents/user/tasks/425-tasks.grading-and-paired-report.md`; tasks
- reviewed-at: `cf9744e6` (`reviewedSha`, under `refs/squadron/pre-collapse/e43d0334…`; the walkthrough is Task 44 there, Task 45 in the final `e43d0334`). Review `425-review.tasks.grading-and-paired-report.md`, CONCERNS, claude-haiku-5-5, revision 2.
- correcting commit: `69f48c9a` "feat: implement slice 425 — Grading and Paired Report" (task-file diff read)
- flaws:
  - Task 45 step 1 needs "at least five qualified cases". INVALID: rewritten by a PM decision because only one case qualified (1 of 95), a fact that did not exist until 422 ran. The diff shows no BLOCKED note and nothing about run time; the lead's "hours-long run" reason is not what this correction records.

## 9. squadron-426-design

- `project-documents/user/slices/426-slice.slice-cases.md`; design
- reviewed-at: `d12c6c51` (added with review; caveat 2; no commit touched it before the correction). Review `426-review.slice.slice-cases.md`, CONCERNS, claude-sonnet-5-5, 7 findings.
- correcting commits: `afeb630d` "docs: correct slice 426 design for judge_pair counting, fork plan files, registration branch, keep and over-size counts" (read; gap list in the task file at `a8852faa`); `494b3d50` for the walkthrough.
- flaws:
  - D12: `judge_pair(prompt_a_first, prompt_b_first, dispatcher, timeout_s, label)` with "177's tests pass unchanged". `replay/judging.py:173` at `d12c6c51` counts `summary.calls` inside `_call`; the signature has no way to keep that count. **VALID**: contradicts code. Needs: code.
  - D3: uses `plan_file_for(index, root)` "at the fork". The function reads plan files under a directory (`stats/planning_docs.py:255`), and discovery has no working tree at the fork. **VALID**: contradicts code. Needs: code.
  - D3: `task_text` orders task files "sorted by name", which puts `-10` before `-2`; `start_point.py` already orders numerically (`_suffix_order`), and the order is part of the case id. **VALID** (minor, shows only with ten or more task files): Needs: code, or the document plus the naming convention.
  - D14/D15: the report counts `OverSizeCase` records and says the record "is replaced when the limit changes"; after the limit is raised and the case judged, the stale record remains and the case is counted both ways. **VALID**: self-contradiction. Needs: document alone.
  - Scope: "No edits to 424 or 425", while D8 removes 424's refusal of slice cases and Patterns widens 424's `CaseDrop.reason`. **VALID**: self-contradiction. Needs: document alone. Found by the 426 task review (F008). The sentence looks like the response to design-review F001, so the design reviewer probably never saw it.
  - `CfRegistration` exposes no registered state for `ReplaySandbox` cleanup. INVALID (borderline): an extraction detail.
  - `register`'s `branch` undefined. INVALID: unspecified detail.
  - `--keep` listed with no behavior. INVALID: unspecified detail.
  - Build stop prints a line per remaining index. INVALID: unspecified detail.
  - cf spike moved after the precondition gate. INVALID: sequencing that follows implementation state.
  - Walkthrough and success criterion moved from squadron to a fixture project (`494b3d50`). INVALID: PM decision.

## 10. squadron-426-tasks

- `project-documents/user/tasks/426-tasks.slice-cases.md`; tasks
- reviewed-at: `6e72e0f7` (`reviewedSha`, under `refs/squadron/pre-collapse/a8852faa…`; exact text the reviewer saw, where the three tasks are numbered 22, 25, 39) or `a8852faa` (final commit, tasks 23, 26, 41; tree identical to the pre-collapse tip `97bd25a3`). Review `426-review.tasks.slice-cases.md`, CONCERNS, claude-haiku-5-5, revision 2, 18 findings.
- correcting commit: `494b3d50` "docs: replace slice 426's live runs on squadron with fixture end-to-end tests" (read; caveat 4). The proof is the three `BLOCKED:` notes the implementing agent wrote under the tasks before that commit, with measurements.
- flaws:
  - Task 23 (live build on squadron): one suite run at a fork did not finish in 400 s, a candidate needs 3 runs at its tip, 9 of 15 slices reach the sandbox, and the session ends a command at 600 s. **VALID**: could not be completed as written. Needs: the design (qualification repeats × full suite × candidates at fork and tip) plus the suite's run time, which is not in any document; a reviewer has to estimate it.
  - Task 26 (live replay): needs Task 23's case and two whole-slice producer-only `P6` runs the session cannot hold open. **VALID**: same proof. Needs: same.
  - Task 41 steps 4-7: blocked only because 23 and 26 are. INVALID as a separate flaw (derivative; score it with Task 26).
  - The saved review's F011 (Task 26 has no outcome when no replay commits) is adjacent, not a hit.
  - Caution: the commit message also cites a PM decision ("no task runs against squadron's history or calls a model"). The BLOCKED evidence predates it, which is why this counts and 427 does not.

## 11. squadron-427-tasks

- `project-documents/user/archive/427-tasks.reviewer-recall.md` (moved from `tasks/` in `b0e23226`); tasks
- reviewed-at: `f8780ebb` (`reviewedSha`, under `refs/squadron/pre-collapse/45ad97da…`; tasks numbered 21 and 36 there) or `45ad97da` (final; 20 and 34). Review `427-review.tasks.reviewer-recall.md`, CONCERNS, claude-haiku-5-5, revision 2.
- correcting commit: `321f7240` "docs: replace slice 427's runs on squadron with a fixture build and live check" (read)
- flaws:
  - Task 20 (`recall build --limit 40` on squadron). INVALID (unproven): never attempted; 427 was never implemented and is archived. The commit records a PM decision made by analogy with 426, not a failure.
  - Task 34 (walkthrough on the squadron case set). INVALID (unproven): same.
  - If the PM accepts 426's evidence as proof for the same shape, both would become valid; nothing in this repo proves them.

## 12. squadron-427-design

- `project-documents/user/archive/427-slice.reviewer-recall.md`; design
- reviewed-at: `57ed59b6` (second round; `reviewedSha f2bf39ab` does contain the round-1 design, so this one is recoverable). Review `427-review.slice.reviewer-recall.md`, CONCERNS, claude-opus-5-5, 15 findings; round 1 (FAIL) is under `reviews/archive/`.
- correcting commit: none for the design content. `321f7240` changes only the walkthrough. The task file (`45ad97da`) lists 15 "design gaps found while reading the sibling task files"; Task 1 was to write them into the design and never ran.
- flaws:
  - The 15 listed gaps (`ReviewerRef` without `rules_hash`, `review_tree_diff` raising, source-path predicate, edit coordinates in bytes, diff-size definition, shared materializer, model and module homes, spacing measured in defected-tree lines, case identity fields, anchor parsing, operator spans, `--limit` default, `review_flag` store argument, seeds). INVALID (unproven): no correcting commit, and by the list's own heading most follow sibling task decisions made after the review. Read, not checked.
  - Walkthrough moved to a fixture. INVALID: PM decision.

## 13. squadron-915-design (cleanest case)

- `project-documents/user/slices/915-slice.loop-checkpoint-pause-resume-correctness.md`; design
- reviewed-at: `ec6f4e71` (`reviewedSha`; it is the commit that added the design, so the reviewed text is exact). Review `915-review.slice.loop-checkpoint-pause-resume-correctness.md`, **PASS**, minimax/minimax-m3 (5 pass, 3 notes), committed in `78b81d77`.
- correcting commit: `a2114d9b` "docs: correct slice 915 design scope and extend verification walkthrough" (read)
- flaws:
  - Part A changes `first_unfinished_step` and accounts for the two resume callers only. At `ec6f4e71` there are four: `run.py:653` (finalizes the run as COMPLETED when it returns `None`), `799`, `1102`, `1159`. **VALID**: contradicts code; the missed caller is correctness-relevant. Needs: code (one grep).
  - Part C adds the pause WARNING to `_execute_loop_body` only; `_execute_loop_step` short-circuits on PAUSED too (`executor.py:1136`), and Part B of the same design already covers both shapes. **VALID**: contradicts code. Needs: code, or the document alone by comparing Part B with Part C.
  - New criterion: a resume above `max:` fails loudly. INVALID: an added guard.

## 14. squadron-302-design

- `project-documents/user/slices/302-slice.design-phase-judge-templates.md`; design
- reviewed-at: uncertain between `bdb946df` (design added) and `d69ee7e4` ("address review concerns", 12 minutes before the review file was committed in `31e59338`). No `reviewedSha`. The flawed text is present at `31e59338`. Review `302-review.slice.design-phase-judge-templates.md`, CONCERNS, z-ai/glm-5.1 (F001 failure modes, F002 NFR note; neither is this).
- correcting commit: `00d14ed0` "fix: correct CLI invocation claims in slice 302 design" (read)
- flaws:
  - Success Criterion 3 and walkthrough step 3 run `sq review slice-vs-arch <artifact> <against> --template judge.slice-vs-arch`. `cli/commands/review.py` at `31e59338` has only `slice`, `arch`, `tasks`, `code`, `list`, each pinned to its template. **VALID**: contradicts code, and the criterion could not be met as written. Needs: code.

## 15. squadron-181-design

- `project-documents/user/slices/181-slice.pool-resolver-integration-and-cli.md`; design
- reviewed-at: `4f97bc49` (design and review added together, 2026-04-11; no `reviewedSha`). Review `181-review.slice.pool-resolver-integration-and-cli.md`, PASS, minimax/minimax-m2.7.
- correcting commit: `a5545607` "docs: correct slice 181 design — actual pools path and executor wiring" (read)
- flaws:
  - Wrong package path (`src/squadron/pools/`), `PoolBackend` attributed to slice 180, wiring placed in `executor.py`. INVALID: at `4f97bc49` neither pools directory exists, so slice 180 was not built yet; the correction records where 180 actually landed. Whether it contradicted 180's design was not checked (inferred).

---

## Screened out before becoming candidates

Looked at only far enough to rule out; not counted in the 15.

- 265 (`0d07e8f2`), 195 (`555bbcdd`), 920 (`95462d77`), 923 (`b279155a`), 914 (`96b03661`, `4ab636aa`), 403 (`f0c537df`): the saved review's `reviewedSha` is the correcting commit or later, so the review never saw the flawed text.
- 362 (`7b9e8b96`): adds a third correction to scope after checking an upstream plugin's source; scope addition.
- 928 (`4849ae2c`), 174 (`be0a499b`), 930 (`1354fd20`), 322 (`e4de8b26`, `b104844d`), 911 (`da538805`), 191 (`ca7484b0`): subjects only; not read. 928 ("probe results") and 174 (30 minutes after three review rounds) look like later facts and review responses. 322's review verdict is UNKNOWN.
- `git log --grep` for "uncheck", "rewrite", "replace" over the slice and task paths gave no leads beyond `494b3d50` and `321f7240`.

## Notes for building the benchmark from these

- The gap lists exist because the task-breakdown step reads the code and the design review mostly does not. 11 of the 25 valid flaws need code at the reviewed commit, so a reviewer run without tools can reach at most the 12 document-only ones.
- Four valid flaws were raised or confirmed by the later task review (421 env merge, 423 dispatch fallback, 425 lockfile F005, 426 no-edits F008), and 420's two were corrected in a commit titled "align 420 design with task review". They show the flaw is findable by a model with read tools.
- Minor flaws (6 tagged) are name, wording or edge-case inconsistencies; consider scoring them separately from the ones that would have produced wrong behavior (421, 423 dispatch, 425 snapshot/16 KB/rules hash/inject_hidden, 426 judge_pair/fork plan/over-size, 915 both, 302).
- 423's design was never edited, so its flaws can also be checked against the current file.
