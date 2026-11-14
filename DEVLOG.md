---
docType: devlog
project: squadron
dateCreated: 20260218
dateUpdated: 20261113
---

# Development Log

A lightweight, append-only record of development activity. Newest entries first.

Older entries: project-documents/user/archive/devlog/ (one file per quarter).

## 20261113


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

### Slice 423: Fix Pipeline — Complete

- **Commits** (branch `423-slice.fix-pipeline`): e80c22bb issue ref and frozen-file source; dd4a065c fix report checks; 5968ba6e fix commit plan and `CommitAction` for `fix`; fbb10293 dispatch prompt fallback accepts any `build_context` result; 400851dd fix prompt; 40468fab `fix-context` action and load test; da620cc7 `fix` step and `fix.yaml`, executor-level tests; 71b28ccf hidden `sq _fix-prompt` and `sq _commit --subject fix`; 6b65a83b prompt-only rendering, `run.md`, parity tests; 839adf57 docs and CHANGELOG; 64a2ef03 fetched issue source; then the verification fix and closing commit.
- **Delivered:** `sq run fix <issue>`: `fix-context → dispatch → commit`; issue from the code host (every comment, no cutoff) or a frozen `issue-file`; `commit-to: target|current`; the agent's JSON report is checked before anything is staged; refusals are `fix_report` failures or run-ending git errors. Full suite, pyright (0 errors) and ruff on `src`/`tests` pass.
- **Walkthrough (real runs, issue #316 in scratch clones):** frozen text, `commit-to: current`, `gh`/`cf` stand-ins on `PATH`: one `fix:` commit, state shows `issue_source: file` and the file's sha256. Cost cap: `failure_kind: cost_cap`, no commit. Fetched, target mode, cf-registered clone: one `fix:` commit with `Fixes #316`, `issue_source: github`; the new test fails at the parent and passes at the commit; the reported gates pass. The clones and the cf project are removed.
- **Surprises:**
  - The walkthrough caught squadron calling `cf get --json` at the start of every run (`execute_pipeline` read the project name even with no cf-using step), so the fix pipeline was not cf-free. Fixed: it reads it only when a step needs cf. The first tripwire test missed it because it passed `_project` itself.
  - A step's earlier results are keyed `{action_type}-{index}` while it runs and `{step}:{action_type}-{index}` after it completes; `results_for_step` only sees the second form. New `results_in_current_step` reads the first (`fix_commit`).
  - The design said `fix-context` outputs `context` for the dispatch; the dispatch fallback needs `operation: build_context` and `stdout`, from any action type (`_resolve_prompt` no longer requires `cf-op`).
  - `StepTypeName.FIX` was added with `FixStepType` (Task 10), not in Task 2: the registry-drift test fails while a name has no step type.
  - `sq run --dry-run` prints `fix-0 (fix)` only, as for every non-container step; the three actions show under `--prompt-only`. The design and tasks also named `sq runs show`, which does not exist (`sq runs list`, `sq run --status`, the state file).
  - The #316 fix's new test fails at the parent through a `TypeError` on a new keyword argument rather than through the symptom, so the pipeline's "failed before the change" check proves the test fails, not why.
  - `ruff check`/`ruff format --check` with no path flag 32 lint errors and 122 unformatted files in `project-documents/.../review-recall-results/` scripts, which are on `main`; `src` and `tests` are clean.
  - `.github/workflows/ci.yml` runs plain `uv run pytest` on push and PR to `main` with no exclusion, so `tests/load` is gated.
- **Pending:** manual check for the Project Manager: `/sq:run fix <n>` in an interactive Claude Code session on a clean target (expects the step 2 refusals under the same conditions, and on success a commit through `sq _commit --subject fix`). Running `fix` under 421's `ScrubbedEnvironment` waits on slice 421 (issue #296). `blocked` has no resume path by design.
- **Issues filed:** none.

## 20261112

### Release 0.24.28

- **Contents:** resuming a planning-plan item no longer flags an unimplemented dependency (#298); a planning pipeline started off the target stops before it spends (#277); the findings-addressed judge's spend is counted and `sq review resolve` prints it (#294); `allowed_tools: []` guarded on review and summary steps (#306). The 42-minute `real_history` tests are out of the default run (nightly job tracked in #319).

## 20261111

### Release 0.24.27

- **Contents:** slice 422 (fix-case qualification and yield report; squadron's yield was too low to separate configurations, 423–427 not recommended); `branch: merge` squashes a slice branch to one commit before merging; patch-recorder exception comments (#315, #316, #317 filed from the 422 review).

**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

## 20261110

### Release 0.24.26

- **Contents:** code-review PASS capped when most of the diff went unseen (#309) or a large diff got too few tool calls (#311, ask 2 still open); `Evidence:` line in review artifacts; benchmark sandbox copies carried logins instead of symlinking (#301).

## 20261109

### Release 0.24.25

- **Contents:** `read_file` accepts `path` restated as single-entry `paths` (#310); Claude subscription token passed into sdk benchmark sandboxes; claude-agent-sdk 0.2.179.

## 20261108

### Slice 422: Correction and outcome

- **Correction:** the D7 exemption covered only `_load_env_file`. `tests/conftest.py` has two more autouse fixtures that patch project code in every test (`DispatchBranchWorkAction._count_work` and `BlockedTasksAction._read_markers`, standing in for git and the task files). Most of the 546 `patches_project_code` verdicts, and the deciding targets in the Task 29 pins, come from those, not from the tests' own patches.
- **Re-measurement (uncommitted experiment, not kept):** exempting all three fixtures and re-judging the 10 most recent `no_qualifying_hidden_test` candidates under rule version 3 qualified 0 of 10 (35m48s). Project-wide `patches_project_code` fell 546 → 456 and `reaches_past_boundary` rose 2 → 92: squadron's tests call internals, which the fairness design rejects.
- **Outcome:** fix-case yield on squadron is not enough to separate configs (PM kill rule: fewer than 3 of 10). The exemption edits were not committed because the Task 29 pins would then fail under rule version 3. Slices 423–427 as planned are not started and not recommended. Existing `sq replay` (design and tasks) and `sq stats producers` answer the model-comparison questions for those phases.
- **Order decision above** (pool across projects, or 426 earlier) is superseded by this outcome.

### Slice 422: Real-commit verdicts (Task 29)

- **Full run (once):** `sq benchmark fix-cases build --set fix-squadron` over all 94 closing commits: 1 qualified (21013615, `case-85c975f100d51ec1`), 70 rejected, 23 `harness_error` (20 of them `submodule replay is not supported`, 1 trace timeout). Hidden verdicts: 553 `patches_project_code`, 3 `reaches_past_boundary`, 1 qualified. Squadron alone reads n=1, MDD 1.14, "not enough (need >= 33 cases)".
- **D7 exemption:** squadron's autouse `tests/conftest.py` fixture patches `squadron.cli.app._load_env_file` (since 3ea67555); it is exempted as environment isolation (`ENVIRONMENT_ISOLATION_PATCH_TARGETS`, rule version 2).
- **Pins:** ebd45f3f, 9fc4fc1c and d6535d62 are rejected for patching project code (deciding targets `BlockedTasksAction._read_markers`, `run._apply_param_overrides`, `run.load_pipeline`); 21013615 qualifies with its hidden test failing by assertion at the parent; c45d28e9 is rejected `reaches_past_boundary` at `one_shot_dispatch_with_telemetry`.
- **No instance in the 94 records:** (a) crash fix (`project_exception`), (b) `uses_symbol_added_by_fix`, (d) qualified CLI test (`CliRunner`). Fixture projects cover them.
- **Measured:** the three-commit patch pins took 9m32s; the two example pins took 33m16s (same machine, later in the session).
- **Scope change:** Tasks 29 (steps 3–4) and 30 no longer rerun the whole history; the design walkthrough follows.

### Slice 422: Verification walkthrough (Task 30)

- **Step 1:** the design's grep finds 96 closing lines; the store holds 94 records (3 are `multiple_issues_closed`, so the counts agree within the design's tolerance).
- **Steps 2 and 3:** `show` on 13e8381a (every hidden test `patches_project_code`) and on `case-85c975f100d51ec1`. The frozen text of the case contains issue #171's body; the issue has no comments, so the committer-date cutoff excluded nothing.
- **Step 4:** reran three commits, not all 94 (5.8 s): 21013615 and 13e8381a print `reused`, d4850abc repeats `merge_commit`; the case set stayed `fix-squadron` v1. The design's "every line says `reused`" is not met (Context Summary gap 5): candidates rejected before the sandbox stage repeat their reason.
- **Step 5:** the first other uv project with a `uv.lock` and a GitHub remote in `cf project list` order is context-visualizer. It has 1 closing commit and was built whole (3.5 s): 1 candidate, 0 qualified, `harness_error` (its start commit declares submodules, which the sandbox does not replay). Squadron n=1 of 94 (MDD 1.14), context-visualizer none, pooled n=1 of 95: all "not enough (need >= 33 cases)".
- **Order decision implied (design line 28):** the qualified count cannot separate two configs, so 423 → 424 → 425 does not stand as is; fix cases are pooled across cf projects, or 426's case building moves ahead of 424. The data do not choose between the two. Where the yield goes is corrected in "Correction and outcome" below; the `patches_project_code` count here is mostly squadron's autouse conftest fixtures. 21 of the 24 `harness_error` records across both projects are the submodule limitation of the history-free sandbox.
- **Step 6:** `yield --json` lists `fix-squadron` v1; the step 4 rerun created no new version.

### Slice 422: Final validation (Task 31)

- **Validation:** ruff format and check clean, pyright 0 errors, full suite 9547 passed, 6 skipped (11m40s; the real-commit pins file was excluded from that run and passed separately: 4 passed in 9m32s, 2 passed in 33m16s).
- **File size:** `metrology/benchmark_models.py` grew from 215 to 339 lines. It is 39 imports wide, so it stays unsplit; `github_cli.py` and `keys.py` were already over ~300 before this slice.
- **Deviations from the approved Success Criteria and Walkthrough (gaps 4 and 5):** the Project Manager bounded the walkthrough. The full history is built once; step 4 reruns three commits and prints `reused` only for those that reached the sandbox; step 5 reads context-visualizer whole (1 commit). The design's Verification Walkthrough and implementation-order line were edited to match at the Project Manager's direction.
- **Next:** 423. The order decision above (pool across projects, or 426 earlier) needs the Project Manager before 424.

## 20261107

### Release 0.24.24

- **Contents:** slice 421 (benchmark sandbox and case record), `sq runs list --json` and run working directory (#303), `pipeline.on_pause_command` (#302), tool-less `allowed_tools: []` dispatch on SDK models (#299).

## 20261106


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: CONCERNS)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: PASS)
- revise-code:commit-5: PASS

### Slice 421: Benchmark Sandbox and Case Record — Implementation Complete

- **Auth check (Task 9), run with this branch's `sq` (`.venv/bin/sq`):** `openai-oauth` (alias `luna`): **yes**. `sdk` (alias `sonnet`): **no**, `Not logged in · Please run /login`. No carried symlink was replaced. Aliases `haiku` and `luna` were used instead of the first listed alias per profile (`fable`, `astra`) to keep probe cost low; the answer is per profile.
- **Why `sdk` is a no:** `~/.claude/.credentials.json` does not exist on this machine (macOS); Claude Code keeps its login in the Keychain, so the carryover file in `auth_carryover.py` has nothing to link. The same probe unscrubbed answers `ok`. **PM decision needed before 422 starts:** how `sdk` producers get auth in a scrubbed home (Keychain access, an API-key profile, or openai-oauth only).
- **Replay baseline (Task 10):** `tests/replay tests/cli/test_replay_run.py` = 191 passed before the `HistoryFreeSandbox` extraction; 197 after (6 new tests, no existing test modified).
- **Design addition (Task 22):** `run_suite` passes `--continue-on-collection-errors`; without it one broken module makes pytest stop before running any test, and `all_tests()` would return only the collection error. Exit codes other than 0, 1, 4, 5 raise `SuiteRunError`.
- **Walkthrough (Task 28), `REV=69550e3e` (`v0.20.0`):** step 2 `lockfile_sha256` `3e75a85f…` matches `git show ${REV}:uv.lock | shasum -a 256` and the kept tree/home/out paths existed (write `${REV}:uv.lock`: zsh reads `$REV:u` as an uppercase modifier). Step 3 passes (9). Step 4 `--suite`: `failed=6, passed=5748, skipped=8`, all six `assertion_failure` (cf-schema and PR-fixture tests that need `cf`, which is not on the scrubbed PATH); `--node` with one printed id: exactly one result. Step 5 `test_stale_lock_fails` and the no-lockfile case pass. Step 6 passes (12). Step 7: a plain run leaves nothing under `~/.config/squadron/benchmark/`; a run killed 1 s in left a tree and lock, and the next run swept them with a WARNING; a `--keep` sandbox was swept the same way.
- **`sq replay run` manual check (Task 28):** `sq replay run --phase tasks --slice 400 --config luna --reviewer luna --max-revisions 1 --yes` ran to completion (`luna: accepted rounds 2 $0.0033`, exit 0, 1 record written, no sandbox left under `~/.config/squadron/replays/`), so the extraction and the unchanged `sweep_orphans` call behave as before.
- **Final validation (Task 29):** full suite 9029 passed, 5 skipped; ruff check and pyright (zero errors) clean; every new source file under 300 lines. `sq benchmark sandbox` and `sq benchmark auth-check` are CLI-only (no slash command until 422).
- **Resolved (PM decision, 2026-11-07):** `sdk` producers authenticate in the scrub with a Claude subscription token, not an API key. `claude setup-token` makes it; put `CLAUDE_CODE_OAUTH_TOKEN` in `.env` (or the harness environment). The `sdk` profile grants that variable into the sandbox when it is set (`AUTH_OPTIONAL_VARIABLES`). `sq benchmark auth-check --model haiku --model luna`: both **yes**. Without the token, `sdk` on macOS still answers no.
- **Next:** slice 422 (fix-case qualification).
- **Note:** `ProcessRunner.run` gained `replace_env` (Task 3): `env=` alone merged over `os.environ`.

### Slice 427: Task Breakdown Complete

- **Delivered:** `427-tasks.reviewer-recall.md`: 40 tasks, test-with ordering, 22 commit markers, 308 lines.
- **Order:** design corrections; config keys, operator table, edit engine and the Python adapter (need nothing from 421–425); the precondition gate (`BLOCKED:` while 421–425 are unimplemented); records and store; fixtures, verification, planting and build; the shared case materializer and `build`/`show`; a live build; matcher and statistics; runner and `run`; report, `latest_recall_for` and `review_flag`; slash commands; walkthrough; final validation.
- **Design gaps found (Task 1 writes them into the design):** `ReviewerRef` has no `rules_hash` after 425; `review_tree_diff` raises `ReviewFailed`; `RecallAdapter` needs `is_source_path`; `edit_span` columns are UTF-8 byte offsets; "diff lines" is added plus removed from `--numstat`; `run` and `show` need one shared materializer; recall models and store go in new modules; `review_flag` gets a `records` parameter because it has no store today (one call-site change in 425's report); interval seeds use sha256.
- **Noted:** 421–425 are not implemented, so Task 10 stops with `BLOCKED:` there; Tasks 2–9 do not wait. A live build that keeps no case files an issue and does not block the pure matcher and statistics tasks.
- **Next:** Project Manager approval, then Phase 6 implementation after 425.

### Slice 426: Task Breakdown Complete

- **Delivered:** `426-tasks.slice-cases.md`: 40 tasks, test-with ordering, 21 commit markers, 343 lines.
- **Order:** design corrections; `judge_pair`, `CfRegistration`, public artifact patterns and two config keys (need nothing from 421–425); the precondition gate (`BLOCKED:` while 421–425 are unimplemented); `with_tools` and the cf spike (`BLOCKED:` on a no); records and store; fixtures, `normalize`, discovery, fork task text, no-code check; qualification in three steps, build, `slice-cases build`, yield rows, live build; `SliceCaseRunner`, requalify routing, live replay; pairing, forfeits, prompt, over-size, judge loop, plan, bound and cap, `judge` command; per-kind report, pairwise reduction and rendering, mixed-kind test; slash commands; walkthrough; final validation.
- **Design gaps found (Task 1 writes them into the design):** `judge_pair` needs an `on_call` counter to keep `JudgeSummary.calls`; `plan_file_for` reads a working tree, so the fork's slice plans are written to a temp dir (D3); task files sort by numeric suffix, not name; `CfRegistration` needs a `registered` flag and its own error so `ReplaySandbox` cleanup is unchanged.
- **Noted:** 421–425 are not implemented, so Task 6 stops with `BLOCKED:` there; Tasks 2–5 do not wait.
- **Next:** Project Manager approval, then Phase 6 implementation after 425.

### Slice 425: Task Breakdown Complete

- **Delivered:** `425-tasks.grading-and-paired-report.md`: 47 tasks, test-with ordering, 25 commit markers.
- **Order:** `is_within_floor(float)` and `measure_snapshot` (need nothing from 421–424); the precondition gate (420, 421, 422, 424 implemented, else `BLOCKED:`); `ContentSidecars`, config keys, models, records, ids, store; `GradingAdapter` and real-commit fixture trees, then restoration, deps-changed, test edits, suppressions, injection and clashes; the grading review and its floor; `grade_one` in four steps plus the reference path and a per-`GradeAbsence` test; a live reference grade; `paired_stats` and the sample-count estimate; plan, bound, runner, resume and a killed-process test; report model and sections; `sq benchmark grade` and `report`; the yield line; `/sq:benchmark`; walkthrough; final validation.
- **Design gaps found (handled in the Context Summary, design not edited until Task 47):** `measure_snapshot` needs a `files` parameter (`take_snapshot_at` passes `exported.files`; the grader uses `resolve_files`); `audit_variance._stat` is private, so Task 22 makes it public instead of copying it; `benchmark.review_timeout_s` has no stated default, so it is declared with none and `grade` refuses naming it; new records and store methods may need `grade_models.py` / `grade_store.py` to keep the shared modules under ~300 lines.
- **Noted:** 421–424 are not implemented, so Task 4 stops with `BLOCKED:` there; Tasks 2–3 do not wait. Task 31 (live reference grade) and the walkthrough carry `BLOCKED:` conditions for a missing case or reviewer alias.
- **Next:** Project Manager approval, then Phase 6 implementation after 424.

### Slice 424: Task Breakdown Complete

- **Delivered:** `424-tasks.producer-only-replay-runner.md`: 37 tasks, test-with ordering, commit markers after each group.
- **Order:** the D9 follow-up issue; producer-only (protocol, phase config, definition transform, run state and flag, fresh and dry runs, prompt-only, executor check on `P6`) and the SDK `max_budget_usd` cap with its load test, none of which need 421–423; then the precondition gate (421–423 implemented, else `BLOCKED:`); the `fix` step's producer config; the transcript spike (a runtime that writes no transcript into the scrubbed home is `BLOCKED:`); records and sidecars; transcript sources and leak rules; identity, caps, bound and planning refusals; `FixCaseRunner`, outcome classification, `replay_one`; the runner with a killed-process test; `sq benchmark run` and `replay-show`; `/sq:benchmark`; walkthrough; final validation.
- **Design gaps found (handled in the Context Summary, design not edited):** `run.py` is ~1560 lines, so producer-only CLI logic goes in `run_producer_only.py`; the resume transform is applied once in `_load_run_definition`; `--producer-only` is also refused with `--explain`, `--validate`, `--status`, `--step-done`, `--next`; `branch: enter` is not run, so a preflight refuses a code-committing producer off its slice branch before any dispatch; the design's `sq run slice` is not a built-in, so `P456` is the multi-producer case; `RunState.producer_only` follows the `replay` field's plumbing.
- **Noted:** Task 11 stops with `BLOCKED:` until 421–423 are implemented; Tasks 1–10 do not wait. Task 2 files one GitHub issue (Codex/OpenAI-compatible in-dispatch cost enforcement), as D9 requires.
- **Next:** Project Manager approval, then Phase 6 implementation.

### Slice 423: Task Breakdown Complete

- **Delivered:** `423-tasks.fix-pipeline.md`: 16 tasks, test-with ordering, commit markers after each group.
- **Order:** shared names and enum entries; issue ref and frozen-file source; fix report; fix commit plan and `CommitAction` FIX subject; dispatch prompt fallback; prompt file; `FixContextAction` with a load test; `FixStepType` and `fix.yaml`; executor-level test; hidden commands (`sq _fix-prompt`, `sq _commit --subject fix`); prompt-only rendering, `run.md` and parity test; docs and CHANGELOG for file mode; fetched source (needs 422 `get_issue` and `render_issue`, not implemented yet, so it stops with `BLOCKED:` until 422 Tasks 5–6 land); walkthrough including a cf-registered target-mode run.
- **Design gaps found (corrected in the task file's Context Summary, design not edited):** the dispatch prompt fallback only accepts a `cf-op` result and reads `stdout`, so D2's "DispatchAction does not change" is wrong (Task 7 widens one condition); the commit action adds no attribution lines (D6); `IssueSource` names both an enum and a class; `sq run --prompt-only` refuses `--io-dir`, so `sq _fix-prompt --io-dir` is unreachable from `/sq:run`.
- **Noted:** Task 11 stops with `BLOCKED:` if 422's `get_issue` or `render_issue` is absent; Tasks 1–10 and 12–13 need nothing from 422. Walkthrough step 6 (`/sq:run`) is covered by the parity test plus rendered-JSON inspection.
- **Next:** Project Manager approval, then Phase 6 implementation.

### Slice 422: Task Breakdown Complete

- **Delivered:** `422-tasks.fix-case-qualification-and-yield-report-keystone.md`: 31 tasks, test-with ordering, commit markers after each group.
- **Order:** config keys; qualification record models and store; `get_issue` and frozen issue text; closing-commit discovery; fairness types and diff classification; test sets; fixture project and history helper; trace plugin (collect, static references, crossings, patches); Python fix-case adapter (collection, then file states and overlay); test-first; boundary resolver; trace verdict and registry; qualification pipeline in three stages; fixture end-to-end scenarios; `case_build` and separability; yield report; CLI and `/sq:benchmark`; real-commit pins; walkthrough; final validation.
- **Design gaps found (interface gaps 1–3 corrected in Task 31; the two success-criteria gaps are left for the Project Manager):** `trace` needs the `AllowedBoundary`; `FixCaseAdapter` needs `lockfile_names`, `is_test_source` and a `pyproject_text` argument on `is_test_side`, because diff classification runs before any sandbox; `TraceVerdict` and `FairnessVerdict` are one type; 9fc4fc1c and d6535d62 both close #291 (`multiple_closing_commits`) and ebd45f3f has no closing keyword, so the design's real examples cannot reach the fairness checks through `build`; walkthrough step 4 cannot show `reused` on pre-sandbox rejections.
- **Noted:** 421 is not implemented, so Task 1 stops if it is not. Tasks 29 and 30 carry `BLOCKED:` conditions (no real example for a fairness check; no second uv project).
- **Next:** Project Manager approval, then Phase 6 implementation after 421.

### Slice 421: Task Breakdown Complete

- **Delivered:** `421-tasks.benchmark-sandbox-and-case-record.md`: 26 tasks, test-with ordering, commit markers after each group.
- **Order:** config keys; auth spike (`ScrubbedEnvironment`, `CredentialGrant`, `_auth-probe`, `sq benchmark auth-check`, live run recorded in DEVLOG); `HistoryFreeSandbox` extraction with replay tests as baseline; case and case-set records with `BenchmarkRecordStore`; adapter seam and uv environment resolution; fixture project, reporter plugin, classification and `run_suite`; `BenchmarkSandbox`; real-process scrub test; `sq benchmark sandbox`; walkthrough and final validation.
- **Noted:** a `no` from the auth check is recorded as a result for the PM before 422; it does not block the rest of 421. The probe goes through `one_shot_dispatch`. `registry.py` lands with `run_suite` (Task 21) so the adapter satisfies the protocol first.
- **Next:** Project Manager approval, then Phase 6 implementation.

## 20261105

### Release 0.24.23

- **Contents:** slice 420 (effort audit across dispatch paths); #293 (implement step continues while task items are unchecked, and a partial branch no longer skips implement); SDK buffer-size fix for files over 1 MiB.

### Slice 420: Effort Audit Across Dispatch Paths: Implemented

- **Done:** every dispatch path now sends the alias's effort or records that none was sent. `stamp_effort_sent` writes the effort on dispatch, summary, review and compaction results (also on failures that have no usage record); `action_effort_sent` is the one reader. Compaction records the session's effort. The replay judge and the findings-addressed judge (pipeline gate and `sq review resolve`) send their alias's effort. `_dispatch-run` takes `--effort` and prompt-only rendering passes it. Replay outcomes and `sq stats producers` read the stamp first.
- **Replay identity (D6):** report rows and contestants are keyed by model, profile, effort sent, `tool_use` and `max_output_tokens`; the alias is display. `ProducerConfigRef` and `JudgeRef` gained optional fields, so old records load. `report.py` was over budget, so `replay/config_label.py` and `replay/pair_tally.py` were split out.
- **Guard:** `tests/providers/test_effort_inventory.py` walks the AST for `AgentConfig(...)` and `open_pipeline_session(...)`, requires each site classified, and maps inventory paths 1–12 to named tests (an executable map, not a comment).
- **Verified:** full suite 8839 passed, ruff and pyright clean. Walkthrough run live: compaction record reads `high` (was `null`); a `set_model` failure keeps `effort_sent: "xhigh"` with no usage record; `glm-flash` vs `glm-flash-low` replays are two report rows; judge at `low` records `low`.
- **Noted:** the installed Claude Code (2.1.311) does not know `claude-haiku-5-5`, so `haiku` and `haiku-xhigh` SDK aliases fail at `set_model` locally. Findings-addressed judge spend is still unrecorded: #294. `sq replay run` skips start commits with submodules (slice 167).
- **Next:** slice 421.

### Slice 420: Task Breakdown Complete

- **Delivered:** `420-tasks.effort-audit-across-dispatch-paths.md`: 15 tasks, 186 lines, test-with ordering, commit markers after each fix group.
- **Order:** `stamp_effort_sent`/`action_effort_sent`, then stamping in dispatch, summary and review, compaction, replay judge, findings-addressed judge, `_dispatch-run --effort` with the renderer, reader wiring, D6 identity in the replay report, enumeration test, CHANGELOG.
- **Noted:** the findings-addressed judge's missing `UsageRecord` becomes a GitHub issue in Task 15, per the design.
- **Next:** Project Manager approval, then Phase 6 implementation.

### Initiative 420: Slice Designs 420–427 Reviewed

- **Run:** `slices-plan` for plan 420 wrote all eight designs and DEVLOG entries, but every item failed at design-1: DEVLOG.md is over 1 MiB, and the Edit tool result carrying it went past the SDK's 1 MiB message buffer. Fixed in ef6d51a9. The review loop never ran.
- **Reviews:** `sq review slice` with sonnet-high on each: 420–426 CONCERNS, 427 FAIL (the matcher could match one finding to two defects; fixed). Responses are in each review file. Fixes favoured cuts.
- **Cross-slice changes:**
  - 423 depends on 422 for issue fetching.
  - 427 depends on 425 and imports its `ReviewerRef`, review call and `bootstrap_mean_interval`.
  - 424 owns `CaseKindRunner.requalify`.
  - 422 creates `/sq:benchmark`.
  - Config identity adds `tool_use` and `max_output_tokens` (420 D6).
  - Grading runs with its own cap in a sandbox rebuilt from start commit plus diff.
  - The slice-case reference is `tip_sha`.
  - The architecture and slice plan are updated to match.
- **Next:** Phase 5 task breakdown, starting with 420.

## 20261104

### Slice 427: Reviewer Recall — Design Complete

- **Delivered:** `427-slice.reviewer-recall.md`. It covers `sq benchmark recall build/run/report/show`, `RecallCase`, `RecallBuild`, `RecallRun` and `RecallReview` records, the `RecallAdapter` seam, the matcher, and 425's recall lookup.
- **Decided:**
  - Source diffs are single commits from history, bounded by diff size. No dependency on 422, 424 or 426 (D1).
  - Defects are planted by a fixed table of nine mutation operators on added source lines, applied as segment-exact text edits. No model plants or matches, so ground truth has no planter bias and building costs no LLM spend. Only correctness and error-handling defects are measured, and the report says so (D2, D3).
  - A defect is kept only if a test passing on the clean commit fails with that defect alone in every verification run, with an assertion or project exception. Import-only failures are rejected. Defects are spaced so one finding cannot match two (D4).
  - Matcher: same file, and line span within ±3 or a `path#symbol` anchor on an enclosing def/class. Category is not required and is reported as agreement. `PASS` findings are ignored. Matches are recomputed at report time under `MATCHER_VERSION` (D6).
  - Recall is the mean per-case found fraction with a case bootstrap interval. Pairs get 425's paired verdicts (D7).
  - `reviewer_key` is model, profile, effort sent and template hash. Alias and per-tree rules hash are excluded (D8). `ReviewerRef`, the no-tools review call and the bootstrap are shared with 425, written by whichever slice lands first (D9).
  - 425's `review_flag` shows the grading reviewer's recall when `latest_recall_for` returns a summary (D11).
- **Open risk:** yield of verifiable defects in squadron, where many lines are reached only through tests that patch internals.
- **Next:** slice review, then Phase 5 task breakdown for 427.

### Slice 426: Slice Cases — Design Complete

- **Delivered:** `426-slice.slice-cases.md`. It covers `sq benchmark slice-cases build/show`, `sq benchmark judge`, `SliceQualification` and `DiffJudgment` records, the slice-case runner on producer-only `P6`, diff normalization, and slice-case tables in the report.
- **Decided:**
  - Candidates come only from 403's `slice_ranges` record. The start is `fork_sha` and the reference is `tip_sha`, not the landing, so on a merge landing the reference holds only the slice's own work. Multiple landings and branches that merged the target are rejected and counted (D1, D2).
  - Task text is the design plus the task file at the fork, using 177's path patterns. Docs-only slices and cases with an empty regression selection are rejected (D3–D5).
  - The superseded set and exclusions reuse 422's closure digests and repeats. `SliceCaseAdapter` is structural, so 422's Python adapter satisfies it unchanged (D5, D7).
  - cf registration runs inside the scrubbed home, so the user's cf registry is never touched. `cf` reaches the producer's `PATH` through `with_tools` without changing `EnvironmentIdentity` (D9).
  - The judge gets normalized diffs: DEVLOG, CHANGELOG, task, review and slice docs, plus `uv.lock`, are dropped, and binaries become marker lines (D11). Pairs are sample-matched across configs plus each replay against the reference (D13).
  - Over-size rule: if the longest pair prompt exceeds `benchmark.judge_max_prompt_chars`, the whole case is skipped and counted. Nothing is truncated (D14). A config-absent replay forfeits its pairs (D15).
  - Pair verdicts come from 425's paired bootstrap over per-case win shares. Bradley-Terry strength is shown but does not decide rank (D17).
- **Open risk:** whether cf works under a redirected `HOME`. That is implementation step 1 (spike).
- **Next:** slice review, then Phase 5 task breakdown for 426.

### Slice 425: Grading and Paired Report — Design Complete

- **Delivered:** `425-slice.grading-and-paired-report.md`. It covers `sq benchmark grade` and `sq benchmark report`, `ReferenceGrade`, `ImplementationGrade` and `SampleSizeEstimate` records, the `GradingAdapter` seam, the paired bootstrap, and the measured sample-count estimate.
- **Decided:**
  - One fixed grade order per sandbox: review the producer's commit as written, restore tool config, run producer-new tests, snapshot, restore edited test files, run the regression suite, inject and run the hidden set (D1).
  - Hidden tests go into a sibling `test_sqhidden_<stem>.py` with the reference file, added conftest imports and hidden fixtures. Nothing the producer wrote is overwritten, and clashes are recorded (D3).
  - All `[tool.*]` tables are restored from the start commit except packaging tables (`uv`, `hatch`, `setuptools`, …), which follow the producer with `[project]` (D4).
  - The grading review runs with no tools, so it cannot read the user's checkout. Its noise floor is measured per case from repeated reference reviews, because 320's stored floors measure the audit prompt, not this reviewer (D7, D8).
  - Grading is a separate command with its own run cap and a bound built from the largest observed review cost (D9). Snapshots are measured in the sandbox without writing `code_snapshot` records, and they are stored as sidecars (D11, D12).
  - Percentile bootstrap over cases, 10,000 resamples, seeded from the benchmark id. Fewer than five cases gives no interval (D14). `sq benchmark yield` shows the measured estimate beside 422's analytic bound (D15).
- **Next:** slice review, then Phase 5 task breakdown for 425.

### Slice 424: Producer-Only Replay Runner — Design Complete

- **Delivered:** `424-slice.producer-only-replay-runner.md`. It covers `sq run --producer-only`, `sq benchmark run/status/replay-show`, `BenchmarkRun` and `ImplementationReplay` records, diff sidecars, and the leak scan.
- **Decided:**
  - Producer-only is a transform of the pipeline definition. It keeps the single top-level step whose type implements `ProducerStep`, and `implement` drops `review` and `checkpoint`. The executor and prompt-only mode stay unchanged (D1–D3).
  - Leak scans read the runtime's own transcripts in the scrubbed home (Claude Code JSONL, Codex rollouts). OpenAI-compatible profiles have no transcript, so they are refused (D6, D7).
  - The run cap is set by flag only and applies per invocation. The per-replay cap comes from the flag or `pipeline.max_cost_usd`. The stated bound includes one replay of overshoot (D8).
  - The 947 cap was checked only after each action, so a one-dispatch replay was unbounded. SDK dispatches now get `max_budget_usd` (affects every capped SDK run). Codex is checked after each dispatch, and an issue is to be filed (D9).
  - Hidden-test injection moves to 425 and cf sandbox registration to 426. The 421 and 422 lines are corrected.
- **Open risk:** whether the runtimes write transcripts into a redirected `HOME`. That is implementation step 1 (spike).
- **Next:** slice review, then Phase 5 task breakdown for 424.

### Slice 423: Fix Pipeline — Design Complete

- **Delivered:** `423-slice.fix-pipeline.md`. `sq run fix <issue>` is one `fix` step that expands to `fix-context → dispatch → commit` (new `fix` commit subject). It has no branch, task file or review.
- **Decided:**
  - The issue comes from `CodeHost.get_issue` (from 422, rendered with no cutoff) or from a frozen `issue-file` resolved against `--io-dir`. The commit goes to the target or, with `commit-to=current`, the checked-out branch, with no cf call (D2, D3, D5).
  - The agent runs the gates and ends its reply with a JSON fix report. The pipeline checks its shape before staging, and `blocked` pauses the run (D4).
  - The commit is `fix: {summary}` plus `Fixes #n`. It needs a clean tree at the start and an unchanged HEAD (D5, D6).
  - The `sq run` cf check uses step configs with params substituted, so a sandbox run needs no cf (D7).
  - Prompt-only parity comes from the hidden `sq _fix-prompt` and `sq _commit --subject fix`, which call the same code. Squadron has no MCP run surface, so MCP parity is out of scope (D9).
- **Effort:** 3/5 (plan said 2/5).
- **Next:** slice review, then Phase 5 task breakdown for 423.

### Slice 422: Fix Case Qualification and Yield Report — Design Complete

- **Delivered:** `422-slice.fix-case-qualification-and-yield-report-keystone.md`. It covers discovery from closing commits, frozen issue text through a new `CodeHost.get_issue`, per-node hidden and superseded sets, the Python fairness checks, `FixQualification` records, and the yield report.
- **Decided:**
  - Every closing commit is a candidate, including those without tests. Multi-commit and merge fixes are rejected with a counted reason (D1).
  - Issue text is cut off at the fix commit's committer date. Content edited after that rejects the candidate (D2).
  - Test sets come from per-node closure digests. Support changes other than added `conftest.py` fixtures reject the candidate (D3).
  - The boundary check combines a static reference closure with `sys.setprofile` crossings against the parent's script targets and top-level `__all__`. Method calls are allowed. The gaps are stated (D6).
  - Any patch owned by a project module, class or instance disqualifies the test (D7).
  - Verdicts are per test, and a case needs one surviving hidden test (D8). Checks run cheapest first (D9).
  - Records are keyed on the parent's environment digest and `FAIRNESS_RULE_VERSION` (D10).
  - Separability uses an analytic worst-case MDD until 425 measures real variance, with new config keys `planned_samples` and `target_pass_rate_difference` (D12).
- **Next:** slice review, then Phase 5 task breakdown for 422.

### Slice 421: Benchmark Sandbox and Case Record — Design Complete

- **Delivered:** `421-slice.benchmark-sandbox-and-case-record.md`. It covers content-addressed case and case-set records, `HistoryFreeSandbox` extracted from `ReplaySandbox`, uv environment resolution, the scrubbed producer environment, the auth check, and the benchmark adapter seam with a pytest suite runner.
- **Decided:**
  - `reference_sha` is part of case identity (D1). Case sets are versioned by content and keyed by name (D2). Benchmark record I/O goes in its own module over two new store primitives (D3).
  - Only `uv.lock` is supported: no lockfile fails with `no_lockfile`, and there is no unpinned fallback (D5).
  - The scrubbed environment is built from an allowlist with `HOME` redirected, because squadron's config directory has no override variable (D7). Auth files are symlinked, not copied, and the auth check is an empirical probe per profile (D8).
  - The suite runner uses an injected pytest reporter plugin, not junitxml (D10). Failures get a fifth kind, `other_exception` (D11).
- **Open risk:** whether Claude auth from the macOS Keychain survives a redirected `HOME`. That is implementation step 1.
- **Next:** slice review, then Phase 5 task breakdown for 421.

### Slice 420: Effort Audit Across Dispatch Paths — Design Complete

- **Delivered:** `420-slice.effort-audit-across-dispatch-paths.md`, with an inventory of 17 dispatch paths. All three providers apply effort.
- **Defects found:** compaction records `null` for a turn that ran at the session's effort; the replay judge and the findings-addressed judge drop the alias's effort; `_dispatch-run` has no `--effort`; replay and `sq stats producers` read a failed run with no telemetry as "not sent".
- **Decided:** `null` stays "not sent" (D1). `effort_sent` is stamped on action metadata on every path that reaches a provider, with one reader that falls back to the legacy record (D5). Replay config identity is (model, profile, effort sent), and the alias is display only (D6). An AST enumeration test keeps the inventory current (D7).
- **Out of scope:** the findings-addressed judge writes no `UsageRecord` (its spend is unrecorded), so it needs an issue.
- **Next:** Phase 5 task breakdown for 420.

### Initiative 420: Model Benchmark — Slice Plan Complete

- **Delivered:** `420-slices.model-benchmark.md`, eight slices: 420 effort audit, 421 benchmark sandbox and case record, 422 fix-case qualification and yield report (keystone), 423 `sq run fix` pipeline, 424 producer-only replay runner, 425 grading and paired report, 426 slice cases, 427 reviewer recall.
- **Decided:** the arch's fix-cases slice and its replay-and-grading slice are each split in two (each had more than six concerns). The agent-auth check sits in 421. 423 has no dependencies in the initiative. 427 needs only 421.
- **Ordering by measurement:** 422's yield report decides whether fix cases are pooled across projects or slice-case building moves ahead of 424.
- **Next:** Phase 4 slice design for 420 (effort audit).

### Release 0.24.22

- **Contents:** the 0.24.21 changes. 0.24.21's tag CI failed on `test_max_cost_cannot_be_set_through_a_param`: CI's forced colour and width split `--max-cost` inside Rich's error box, so the substring check missed it. The test now checks the exit code and `reserved_param_error`. Nothing was published for 0.24.21.

### Release 0.24.21

- **Contents:** per-run cost cap, `sq run --max-cost` and pipeline `max_cost_usd` (#241); `sq run --io-dir` and the guarded `commit` step (#292). Unblocks amoeba slices 180 and 184–186.

### Initiative 420: Model Benchmark — Architecture Complete

- **Delivered:** `420-arch.model-benchmark.md`, registered as the active arch. Benchmarks implementation and code review per config (model, effort) on the project's own history: fix cases first (parent + frozen issue text + hidden fix test), slice cases second (400 slice ranges), graded in 177's history-free sandbox by a step separate from the producer, with repeated samples compared on paired per-case differences. Reviewer recall via planted defects.
- **Dependencies:** 140, 320 and 400 complete; 300 in progress (307 open, not needed). #216 fixed in 0.24.19.
- **Decided:** hidden fix tests qualify mechanically (test-first failure at the parent, reach code only through packaging-declared entry points and exports, no patching of project code); no per-case human review, no per-project boundary file. Replays run the producer step of production pipelines (`implement` from P6; a new `sq run fix <issue>` pipeline) with no review loop, close-out, DEVLOG or merge; review happens once in grading.
- **Arch review (CONCERNS, 13 findings, 12 fixed, F011 partly):** grader pins the start commit's suite and tool config; cases carry hidden and superseded test sets; crash fixes qualify; the implement step's embedded review is stripped in replays; scrubbed producer env plus transcript leak scan; diff normalization and pairwise judging for slice cases only; paired bootstrap statistic; run-level dollar cap; environment-keyed qualification; diff sidecar files. Reviewer recall and `sq run fix` kept.
- **Arch re-review (CONCERNS, 12 findings, 11 fixed or moved to slice scope, F012 declined):** tool config restored by section; new `sq run` producer-only mode (no pipeline step reuse exists today); `PATH` and leak-path rules, "no leak detected" wording; config-caused vs harness-caused absences; per-test hidden/superseded sets; both cost caps required. Slice scope now in the arch's Anticipated Slices: repeated qualification with flaky-test exclusion, yield report power check, auth check in fix-cases slice, replay resume.
- **Open for slice design:** fix-case yield (the fix-cases slice ends at a yield report; pooling across projects if low); the producer-only mode's interface; environment resolution in the sandbox; defect planting and finding-to-defect matching; diff size limits for the judge.
- **Next:** PM decides whether the architecture is ready for slice planning.

### Release 0.24.20

- **Contents:** a space after the comma in `-p a=1, b=2` is accepted on `sq run` and `sq review` (#291); the summary step resolves a slice from an `each` loop record instead of warning.

### Release 0.24.19

- **Contents:** an alias's `effort` now applies to steps in the shared SDK session; the session opens at its first step's effort and a later mismatch warns once per alias (#216). Also filed #290 (two slow tests).

## 20261103

### Release 0.24.18

- **Contents:** planning loops resolve their final review's notes inside the loop and collapse the resolution into the document's one commit (#287). Also closed #257 (shipped in slice 202) and filed #289 (split executor.py).

### Release 0.24.17

- **Contents:** an implement step pauses while the slice design has pending PM decisions (#240); `sq stats producers` leaves replay runs out (#229); a citation range ending one line past EOF is no longer marked unverified (#196, numbering dropped); `sq pipelines list` keeps a shadowed built-in in its group (#283). Also the metrology audit CLI tests no longer wait out the run cooldown, about 6 minutes off the full suite (#180). #224 closed as already fixed. All as standing-fixes task groups on `main`.

### Release 0.24.16

- **Contents:** everything 0.24.15 was to carry, plus `sq run` skipping the Context Forge pre-flight for pipelines whose steps don't use it (#288). 0.24.15 was tagged but its CI run failed (a `--help` text assertion in the #286 tests broke under CI's forced colour), so nothing published; its changelog entries moved here and its tag stays dead.
- **Carried from 0.24.15:** review tool-coverage line and read-before-PASS prompt (#279), per-file review diff cap with a per-file record of cut files (#278), `-p review-model=` on `sq review` (#286). All three as standing-fixes task groups on `main`.

## 20261102

### Release 0.24.14

- **Contents:** slice 949, isolated file-in, file-out dispatch steps, `--validate --strict` and the no-tools guard (#284). Code review verdict CONCERNS; F002 and F003 deliberately not fixed.

### Slice 949: Isolated File-In, File-Out Dispatch Steps — Implementation Complete, Review Pending

- **Branch:** `949-slice.isolated-file-in-file-out-dispatch-steps`, seven task commits (A known keys and `--validate --strict`, B no-tools guard, C new keys, D `dispatch_io` and the dispatch call sites, E prompt-only refusal and docs); not merged, nothing pushed.
- **Delivered:** `prompt_files`, `reply_from`, `reply_format`, `reply_file`, `delivered_prompt_file` on `dispatch`; `known_keys` on every step type and `sq run --validate --strict`; `allowed_tools: []` fails with `failure_kind: tool_isolation` on the SDK session or a file-reading provider; prompt-only refuses the new keys.
- **Departures from the tasks:** key names and the path check live in `pipeline/dispatch_keys.py` (import cycle, review F005); the dispatch paths keep their signatures and each resolve the prompt through `asyncio.to_thread` (the routing tests pin them), the session path now before `set_model`; `body_steps` added to loop, each and fan_out because fan_out's `inner_steps` is a synthetic classification step.
- **Surprise:** strict validation over the built-ins found a dead `slice:` key on the `close-out` dispatch step of P6, P56, P456, implement and implement-plan. Removed from the YAMLs.
- **Caught late:** `Path.is_file()` raises `PermissionError` when a parent directory cannot be searched, which escaped as a raw error instead of `DispatchInputError`; fixed, with a test.
- **Walkthrough:** all seven steps run with the real `sq` and match, with `glm-flash` (an openrouter alias) instead of `deepseek4-flash`. `sq run` needs a cf-registered project, so the scratch files lived in `.sq949/` under the repo root, since removed. Step 7 first showed a raw `ValueError` traceback; it now raises `PromptOnlyUnsupportedError`, which the CLI turns into a one-paragraph error and exit 1. The walkthrough text records the real commands and outputs.
- **Pending:** code review not run.

### Slice 949: Isolated File-In, File-Out Dispatch Steps — Task Breakdown Complete

- **Output:** `949-tasks.isolated-file-in-file-out-dispatch-steps.md`, 19 tasks in five parts (A strict validation, B no-tools guard, C new keys and reply lookup, D `dispatch_io` and `_dispatch` restructure, E prompt-only, docs, verification), with five commit markers. Tests follow their implementation. Not yet reviewed or implemented.
- **Note:** the design body (Component Structure, D8) uses `inner_steps` with a `getattr` test for recursion; the tasks follow that. The earlier DEVLOG line naming `ContainsSteps`/`walk_steps` does not match the design body.
- **Walkthrough:** T19 runs walkthrough steps 1–3 and 7 directly; steps 4–6 need a live `deepseek4-flash` route and are run only if one is configured.

### Slice 949: Isolated File-In, File-Out Dispatch Steps — Design Complete

- **Output:** `949-slice.isolated-file-in-file-out-dispatch-steps.md` (rewritten from the template after the first draft was deleted); `cf validate design` passes. Fixes #284. Phase 5 not started.
- **Decisions:** dispatch keys `prompt_files` (list), `reply_from`, `reply_format` (`text`|`json`), `reply_file`, `delivered_prompt_file`. `reply_from` is limited to top-level steps naming an earlier top-level dispatch step. A failed, skipped or reply-less named result fails the reading step. JSON rule: the first `{` that `raw_decode` accepts (NaN/Infinity rejected), kept byte for byte as `outputs["reply_json"]`. Both output files are staged together and written only on success. `allowed_tools: []` fails before dispatch with `failure_kind: tool_isolation` on the session path or a `can_read_files` provider. Required `StepType.known_keys` plus `ContainsSteps`/`walk_steps` drive `--validate --strict`. Plain `--validate` is unchanged (no warnings). `--prompt-only` rejects the new keys.
- **Behavior change to note at release:** `allowed_tools: []` on SDK or Codex dispatch steps now fails. No built-in pipeline or template uses it.

### Release 0.24.13

- **Contents:** slice 202, one commit per planning document (#257); fix #282 (summary steps read the slice's files; `/sq:summary --restore` prefers `interactive`).

## 20261101

### Slice 202: One Commit Per Planning Document — Implementation Complete, Review Pending

- **Branch:** `202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits`, task commits plus a rework commit; not merged, nothing pushed. Full suite, ruff and pyright clean. All tasks checked; the Verification Walkthrough passed live on a scratch clone (`## Verification Walkthrough` in the slice design).
- **Delivered:** a `commit_each_iteration` planning loop collapses its phase commit and round commits (and the dispatch agents' commits among them) into one commit when it completes: `commit-tree` with the same tree, a `refs/squadron/pre-collapse/<sha>` backup ref, a compare-and-swap `update-ref`. It refuses with one WARNING when it cannot prove the commits are its own, unpublished and the tip of the target. Code loops never collapse.
- **Decision (D1 revised):** the ledger claims commits by HEAD stamps (`head_stamp.py`, on every dispatch and commit result), not by listing shas. The first design listed the commit action's shas, and the first live run refused: the SDK dispatch agents commit their own work, so those commits sat between the pipeline's. A commit made between two of the loop's actions (an operator's during a pause) breaks the chain and the loop will not collapse.
- **Surprises:** the live runs found two bugs the scripted tests had not: the agent commits above, and a double claim of the last round when a loop paused at its exhaustion checkpoint. Both now have tests. A commit landing while an agent is mid-action cannot be told from the agent's own; only a person committing in the same checkout during a run can cause it.
- **Pending:** code review not run. The scratch clone directory under the session scratchpad was left for the PM to delete (the removal was blocked by a safety check). `main` still carries the seven task-planning commits unsquashed; backup tag `backup/pre-squash-202` is local.

### Slice 202: One Commit Per Planning Document — Design Complete

- **Output:** `202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md`; `cf validate design` passes. Fixes #257. Phase 5 not started.
- **Decisions:** a cumulative `LoopCommitLedger` in `StepState` (carried across resume) records the phase commit and each round sha; collapse via `commit-tree` + compare-and-swap `update-ref` (index and working tree untouched); five proof checks, each with its own `CollapseOutcome` and WARNING line; message from `compose_message` over the collapsed range; backup ref `refs/squadron/pre-collapse/<sha>` keeps `reviewedSha` stamps resolvable; collapse only on COMPLETED and never changes loop status; code loops excluded; no opt-out key.
- **Deferred:** prompt-only parity rides on #145 (loops are not rendered in prompt-only yet).

### Slice 202: One Commit Per Planning Document — Task Breakdown Complete

- **Output:** `202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md` (9 tasks, 250 lines, test-with, a `**Commit**:` marker per task). Order: commit action outputs, ledger model/state, open, record/carry, collapse proofs and message, collapse writes, executor call sites with the scripted-loop and item-rerun tests, resolve/CHANGELOG, live walkthrough.
- **Open point recorded in task 8.1:** whether `sq review resolve` follows `refs/squadron/pre-collapse/<sha>` is untested; if not, it becomes an issue rather than silent scope.

### Release 0.24.12

- **Contents:** removed `sq squash` and the `squash` pipeline step (closes #258, #272, #274, #280; #257 stays open for collapsing each review loop's commits into one). A pipeline file that still has a `squash:` step fails to load with a message to delete it. Guide v0.22.15 and the refreshed CLAUDE.md/AGENTS.md (marker-based commit cadence).

## 20261031

### Release 0.24.11

- **Contents:** slice 403 (slice ranges, `snapshot --commit`, rollup reports), slice 404 (`sq metrology baseline`), completing initiative 400; `sq squash` fixes (tasks runs survive design edits, clearer no-run reason) and `sq squash --drop-backups`.

## 20261030

### Slice 404: Adoption Baseline Command — Implementation Complete, Review Pending

- **Branch:** `404-slice.adoption-baseline-command`, 6 code commits plus docs; not merged. All 8 tasks checked; the walkthrough passed live on a scratch repository (`## Verification` in the task file).
- **Delivered:** `sq metrology baseline [PATH] [--profile] [--model]`. `prepare_baseline` runs every check and the scope plan before anything is written; `run_audit_series` is the loop `audit variance` now shares; printers moved to `metrology_audit_output.py` (`SeriesPrinter`, `print_floor`). Exits 0 with a floor, 1 without one or on a failed check, 130 on interrupt.
- **Decisions:** a model must be pinned (`BaselinePreflightError`); no floor means exit 1 plus `sq metrology audit variance PATH`, since no command reduces stored runs. `audit variance --help` is byte-identical to `main`'s and `test_audit_cli.py` is unedited.
- **Surprises:** each audit run writes its own analysis file, so a three-run baseline leaves three untracked files. The end-of-run line names only the newest; the next refusal lists all. The dirty-tree text is 400's and still says "re-run `sq metrology snapshot`". The profile is checked before the model, so a bare `baseline .` with no profile names the profile first.
- **Pending:** the live walkthrough wrote a `github.com/manta/baseline-demo` snapshot, three runs and a floor into the user store. Code review not run.

### Slice 404: Adoption Baseline Command — Task Breakdown Complete

- **Output:** `404-tasks.adoption-baseline-command.md`, 14 tasks, test-with ordering, commits after Tasks 2, 6, 8, 11, 12. Phase 6 not started.
- **Decisions at breakdown:** D7 (probe flip) dropped — 440 deleted `sq probe` and `BaselineReport`; walkthrough step 7 void. `prepare_baseline` takes the adapter registry so scope and snapshot share one exclusion set. `run_audit_series` takes an injectable `sleep`.
- **Found:** existing `audit variance` CLI tests sleep the real 60s cooldown (~120s per test); left as is.

## 20261029

### Slice 403: Slice Ranges and Rollup Reports — Complete

- **Branch:** `403-slice.slice-ranges-and-rollup-reports`, 19 commits from `d694cd2a` to `d6a724a1`; not merged. Full suite 8387 passed, 5 skipped; ruff and pyright clean. All 45 tasks checked; the walkthrough passed live (`## Verification` in the task file).
- **Delivered:** `sq metrology slice-ranges`, `snapshot --commit REV`, `report slice|project|history`. Durable slice-range record (`slice_ranges`, one per project, landings append-only); commit export via `git archive` into a temp tree measured with the live checkout's tools (`AdapterContext.environment_root`); lockfile gate for type errors at an export; comparison with named breaks; review counts per category.
- **Decision:** the resolver calls `run_git` itself rather than reusing `_find_slice_branch` and friends; `git_utils` gained only `slice_merge_grep_pattern`, `parse_slice_branch` and `parse_fork_point`. The design wording was aligned with this (f0c537df).
- **Surprises:** a clone of a checkout that is not on `main` has no local `main`, so slice resolution there returns `git_error` (loud, by design); the walkthrough uses `git clone -b main`. The "no stored snapshot" notice was an INFO log the CLI never showed; it is now a stderr line. A metric absent at both commits is not a history break. `git status` rewrites `.git/index` on racy timestamps, so the export test uses `--no-optional-locks`.
- **Pending:** the TypeScript conformance case is skipped locally (no live `node_modules/.bin/eslint`). `report slice` for the walkthrough wrote slice ranges and two snapshots into the user store. Review file for the code review does not exist yet. Optional review findings left: F005 (merging Effort-1 tasks) was not done.
- **Also this session:** ai-project-guide updated to v0.22.11 (`36a33b91`, on `main`); cf #138 closed as not planned at squadron's request.

### Release 0.24.10

- **Contents:** `sq onboard register-comprehension` registers the codebase comprehension doc with cf (`cf set comprehension`, cf 0.19.22+); the comprehension analysis flow runs it after writing or refreshing the doc. Requested by cf slice 274.

## 20261028

### Release 0.24.9

- **Contents:** an implement step whose agent ends on a question pauses the run (`agent_question`); `failure.agent_text` in `sq runs wait --json` for steps that wrote no artifact. Both requested by Amoeba.

### Release 0.24.8

- **Contents:** (0.24.7 was tagged but never published: two new loader tests read `p5.yaml` where the built-in is `P5.yaml`, which fails on case-sensitive CI.) #276 (`sq squash` finds runs past one-commit stretches, explains no-ops, warns on pipeline overrides that lack built-in steps), #275 (onboard graph build excludes cf-installed tooling), slice 403 task breakdown and review fixes.

## 20261027

### Slice 403: Slice Ranges and Rollup Reports — Task Breakdown Complete (Phase 5)

- `user/tasks/403-tasks.slice-ranges-and-rollup-reports.md`: 45 tasks, 307 lines, test-with ordering, commit per checkpoint.
- Decision at breakdown (refines D2): the existing `_find_slice_branch` / `_resolve_fork_point` collapse a failed git call into "not found", and `_search_merge_commit` returns only the newest merge. The resolver therefore calls `run_git` itself (needs every landing and the `GIT_ERROR` distinction). `git_utils` gains only `slice_merge_grep_pattern`, `parse_slice_branch` and `parse_fork_point`; no helper renames, no `first_parent` argument.
- Coverage at an export is absent and never reaches its `git ls-files` call; squadron sets no `metrology.coverage_report`, so in-place-equals-export holds.
- Slice plan still marks 403 parked behind 404 (deferred 20261025); nothing needs it before 420.

### Release 0.24.6

- **Contents:** slice 440 `sq onboard` (replaces `sq probe`; live adoption run on a tank-game clone passed, #273), slice 402 code-review category normalization and `sq metrology ingest-reviews`. Follow-ups: #275, #276.

## 20261026

### Slice 440: sq onboard — Implementation Complete (Phase 6)

- Branch `440-slice.sq-onboard`, all 26 tasks. `sq onboard` (report, `register`, `decline`, `prompt`), `CfAdoptionClient` + report parsers in `integrations/cf_adoption.py`, `ContextForgeClient(cwd, timeout_s)` + `run_report`, `onboard/` package (`decide_step`, graph, surfaces, comprehension finder), `/sq:onboard` and `sq-onboard` command files, `sq probe` deleted. `SliceEntry.retroactive` is required and `set_slice` refuses a retroactive entry.
- Not done: the live walkthrough. Installed cf is 0.19.19 and has no `cf detect`, so the fixtures are still copied from the cf 271 design, not recorded from real cf. Tracked as #273; the slice stays incomplete until it passes.
- Surprises:
  - The strict `retroactive` key broke 45 `test_sources.py` tests that mock raw cf JSON, and ~47 `SliceEntry(` constructors across the tests needed the new field. Nothing in `src` constructed one.
  - `ContextForgeClient` had only private `_run`/`_run_json`, so `CfAdoptionClient` needed public `run`/`run_json` delegates (the pipeline reaches the private ones with `pyright: ignore`).
  - A full `pytest` takes about 14 minutes.

### Slice 440: sq onboard — Task Breakdown Complete (Phase 5)

- `440-tasks.sq-onboard.md`: 26 tasks in seven parts (fixtures, cf client + retroactive guard, `CfAdoptionClient`, probe move then delete, onboard core, CLI, agent surfaces, docs/validation), test-with throughout.
- Recorded fixtures come from cf 271 design D3/D5/D8 at context-forge `93ee3511`.
- The live walkthrough (needs cf 271, 272, guide #47) is a slice precondition tracked as #273, not a task; the slice stays incomplete until it passes.

## 20261025

### Slice 440: sq onboard — Design Complete (Phase 4)

- `440-slice.sq-onboard.md`, `cf validate design` passes. Read-only `sq onboard` report with a closed step table (`decide_step`, D1), `register`/`decline`/`prompt` subcommands over a new `CfAdoptionClient`, `ContextForgeClient(cwd=…)` + `run_report` for cf's stdout error envelope, probe package folded into `onboard/` and `sq probe` deleted, retroactive entries refused at the pipeline's `set_slice` (covers P4–P6).
- Findings from cf source: cwd resolution prefix-matches (a monorepo subdir resolves to its parent project), so "registered" comes from `cf project list --json` by exact path and `decline` passes `--project <root>` (cf config treats an unknown value as a directory). Adoption from a cf-registered worktree is excluded.
- The stale-graph question can't be remembered without state, so the graph only gates until a comprehension doc exists (D2).
- Next: Phase 5 task breakdown. Live run waits on cf 271/272 and guide #47.

### Slice 402: Code-Review Normalization and Ingest — Implementation Complete (Phase 6)

- Branch `402-slice.code-review-normalization-and-ingest`. `sq review code` findings now carry a category from `ReviewCategory` (the ten audit values plus `correctness`), normalized in the review client for templates that set `normalize_categories` (only `code.yaml`). New `sq metrology ingest-reviews` writes one `code_review` record per code-review file; historical reviews are mapped through a fixed 16-string table and marked `read_side_mapped`. `AuditCategory` moved to `core/finding_categories.py`; the arch, slice and tasks review output is unchanged.
- Live check: ingest over squadron's own reviews gave 89 records (591 findings: 102 `other`, 113 missing, 55 `correctness`), re-run replaces all 89. A live `sq review code 402 --model sonnet` wrote `categoriesNormalized: true` with every category canonical.
- Surprises:
  - The corpus drifted since the design: `103-review.code.cli-foundation.md`, `0-review.code.review-1.md` and the PR review are all `UNKNOWN` now, so they are skipped. Fixtures use 156 and a synthetic PR review instead.
  - A tasks review with verdict `RESOLVED` failed the first real ingest, because the verdict was validated before the review type. Non-code reviews are now skipped whatever their verdict.
  - `resolve_reviews_dir` needs host, owner and repository, not just `cwd`; ingest takes them from the project id.
  - `review-verdict-gate` refuses to commit a `docType: review` file without a verdict, so the missing-verdict fixture has no `docType`.
  - The pipeline's structured `findings` output gained a null `raw_category` key; one golden test was updated.
- Code review (sonnet) found one real gap, dropped findings with an unrecognized severity were silent. Fixed with a WARNING and a `Dropped:` summary line.

### Release 0.24.5

- **Contents:** fix #271: `sq squash` finds a run buried under later commits (anywhere in unpushed first-parent history) and recreates the commits above it byte for byte with new parents, merges included (`pipeline/squash_rewrite.py`, `run_git_bytes`). Squash path sets now include parent documents (arch doc for slice/tasks, slice plan for arch) so review responses that amend them stay in the run; trailing parent-only commits are trimmed. Verified on a rebuild of context-forge's pre-squash 268 history: tasks 268, slice 268 and arch 260 each collapse to one commit under the merge.

### Release 0.24.4

- **Contents:** certifi floor `>=2026.10.19` (lock moved to 2026.10.23) so installs drop the emSign root removed from Mozilla, Apple and Microsoft trust stores.

### Release 0.24.3

- **Contents:** first publish of 0.24.2 (slice 948, `sq metr`); 0.24.2's tag CI failed on `test_root_help_shows_metrology_and_hides_metr`, which parsed `--help` text that CI renders with ANSI colour. The test now reads the Click registration's `hidden` flag. Also ai-project-guide 0.22.7 guide updates.

### Release 0.24.2

- **Contents:** slice 948 (`sq squash slice|tasks|arch|plan`, squash step in the planning pipelines; fixes #257, #258) and `sq metr` shorthand.

### Slice 948: Squash Planning Commit Sets — Implementation Complete (Phase 6)

- Branch `948-slice.squash-planning-commit-sets-command-and-pipeline-action`. New: `pipeline/squash.py` (`plan_squash`, `apply_squash`, `check_squash_scope`), `sq squash`, `squash` step/action/renderer, step after every planning loop in P4, P5, P45, P456, P56, `slices-plan`, `tasks-plan`. Part B: `sq metr` hidden mount, own commit.
- `commit_plan.subject_paths` returns a `SubjectPaths` (candidates + archive prefix rule); `build_commit_plan` uses it, so commit and squash share one path set. Shared cf mock moved to `tests/pipeline/commit_fixtures.py`.
- Commit split deviates: T2–T5 code landed in one commit (refusals with run detection), since `squash.py` was written whole.
- Live check passed in a temp clone. It needs the clone registered with cf (`cf init --lite` + `cf set plan`), else `PROJECT_NOT_FOUND`; walkthrough in the slice design records this.
- PM syntax change after Phase 6: `sq squash <kind> <index>`, kind `slice|tasks|arch|plan` (`SquashKind`, `SquashTarget`); step YAML is `squash: { kind: slice }`, `index` defaults to `{slice}`. New `plan` kind: slice plan file + DEVLOG (`commit_plan.slice_plan_paths`, `persistence.resolve_slice_plan_file`); no review template targets a slice plan, so no reviews in that set. `arch` stays architecture-only for now.
- Live check found plan-only commits folded under a slice squash (the slice plan is in the design's path set) with a plan commit as survivor. Fix: the run starts at the oldest commit that touches the artifact itself (`SubjectPaths.is_artifact`), replacing the DEVLOG-only trim.
- A squash only takes the run ending at HEAD: `sq squash plan 900` under newer design commits is "nothing to squash".
- Not done: code review (Phase 7), merge.

### Slice 948: Squash Planning Commit Sets — Task Breakdown Complete (Phase 5)

- Tasks: `project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md`, 16 tasks, test-with ordering, all git tests on real temp repos.
- Order: path-set extraction from `commit_plan.py` → `plan_squash` (run + refusals) → `apply_squash` (backup tag, restore on failure) → `sq squash` → step/action/renderer → built-in pipeline placement → docs → Part B `sq metr` (own commit).
- Settled here: `architecture` takes `--plan N`; step goes after planning loops in P4, P5, P45, P456, P56, `slices-plan`, `tasks-plan` (none after code loops); pushed check tests only the run's oldest commit; existing backup tag at HEAD is reused.
- Design D5 is off: `git commit -C` keeps the first commit's author date. No code for it; tests assert message and author only.

## 20261024

### Slice 402: Code-Review Normalization and Ingest — Task Breakdown Complete (Phase 5)

- Tasks: `project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md`, 29 tasks, test-with ordering, one commit per implementation and test pair.
- Order: `AuditCategory` move to `core/finding_categories.py` → template flag → `code.yaml` vocabulary and sync test → `normalize_category` → model fields, client hook, frontmatter → findings-addressed mixed-round test → record models and store → read-side alias table → fixtures, ingest module, CLI → walkthrough 1–3, CHANGELOG, live step 4.
- Ingest fixtures copy real frontmatter from `103-review.code.cli-foundation.md` (no `reviewedSha`), the 947 code review, the PR #116 review and `0-review.code.review-1.md`.
- `review_path` is relative to `--cwd` when inside it, else absolute; identity's `_relative_review_path` falls back to the bare filename, so ingest doesn't reuse it.

### Release 0.24.1

- **Contents:** slice 401 (complexity, duplication and coverage metrics); fixes #256, #265, #266, #267, and the non-interactive checkpoint warning text.

### Slice 401: Complexity, Duplication and Coverage — Implementation Complete (Phase 6)

- Branch `401-slice.complexity-duplication-and-coverage`, one commit per task pair. Four metrics added to both adapters through the unchanged 400 contract: `cyclomatic_complexity`, `duplicated_lines`, `covered_lines`, `coverable_lines`. The only diff to `snapshot_models.py` is enum members; `take.py`, `contract.py`, `files.py`, `store.py` and `registry.py` are untouched.
- Walkthrough passed on squadron, a clean clone of context-forge and a scratch vitest project. 400's `file_length` and `function_length` are identical on the same commit before and after (checked with a worktree of `main`).
- Surprises:
  - Istanbul writes a function's first line twice: once under `<method>`, once under the class. Only class-level `<line>` entries sum to the root `lines-valid`, so the reader counts those. Found by capturing a real report, not from the spec.
  - Success Criterion 3's Python fixture said 6; D2 (a comprehension's `for` and its `if` both count) gives 7. The criterion now says 7.
  - `tokenize` and `ast.parse` fail on the same files, so "function length unaffected" cannot hold for an untokenizable Python file. The test asserts file length is still counted.
  - The duplication tokenizer takes `(path, text)`, not `text`: `.tsx` needs the TSX grammar.
  - `coverage.py` would have passed 300 lines with the measurements, so `coverage_measurements.py` is separate.
- Not done: the old-commit 400 snapshot records in the dev store are still skipped with a warning; snapshots only measure HEAD, so they can't be re-taken. Delete them by hand if the warning bothers you.

## 20261023

### Slice 401: Complexity, Duplication and Coverage — Task Breakdown Complete (Phase 5)

- Tasks: `project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md`, 29 tasks, test-with ordering, one commit per implementation and test pair.
- Order: enums → Python and TypeScript complexity counters → `MeasuredFunction` / `measure_parse_metrics` rename that wires complexity into both walks → duplication pass, then each language's tokenizer → coverage key and preflight → real Cobertura fixtures (coverage.py, Istanbul via scratch vitest) → reader → freshness → per-language measurements → adapter wiring → render, docs, walkthrough.
- Surprise: `PythonAdapter.metrics` is `frozenset(SnapshotMetric)`, so adding the enum members would make it claim unmeasured metrics and `take_snapshot` would raise. Task 2 makes it an explicit set, and each later task adds a metric when that metric is measured.
- `typescript_complexity` takes the counted-function predicate as a parameter, so it doesn't import `typescript_length`, which itself imports it.

### Release 0.24.0

- **Contents:** Slice 400 keystone: `sq metrology snapshot` measures a clean commit's file length, function length, lint and type errors per language, with absent metrics recorded as absent, never zero. #259: `sq review` prints a `Usage:` line (tokens and cost). Designs for slices 401–404 (docs only).

## 20261022

### Slice 404: Adoption Baseline Command — Design Complete (Phase 4)

- Design: `project-documents/user/slices/404-slice.adoption-baseline-command.md`. `cf validate design` passes, and all 7 decisions are `decided`.
- Key decisions:
  - `sq metrology baseline [PATH]`: all config is read from PATH. Every preflight (snapshot, identity, audit, skill, profile, model, run count) runs before the snapshot, so nothing is written or spent on a config failure.
  - The model must be pinned (`--model` or `metrology.audit_model`). An unpinned model fails, unlike `audit run`.
  - The variance series is the audit run. There's no separate fourth run, because `baseline_report` already reports the newest run in the group, with the floor beside it. Runs are pinned to the snapshot's SHA.
  - The series loop moves out of `audit variance` into `metrology/audit_series.py`, shared by both commands. `audit variance` behavior is unchanged.
  - The scope report uses the snapshot's own file set and says plainly that the audit agent isn't limited by exclusions. No prompt.
  - A partial failure keeps the snapshot and runs, and points to `audit variance` to finish. Re-running the baseline is refused by 400's clean-tree check because of the audit's untracked analysis file.
  - The probe's `baseline.available` becomes constant `true`. Field and `probe_version` are unchanged.
- Next: task breakdown for 404 (Phase 5).

### Slice 403: Slice Ranges and Rollup Reports — Design Complete (Phase 4)

- Design: `project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md`. `cf validate design` passes, and all 10 decisions are `decided`.
- Key decisions:
  - A slice range is an append-only list of landings. On `main`, slices 172, 305 and 940 each landed twice. Merge landings are searched on the target's first-parent line only, which excludes sync merges into slice branches, and there's no fallback to `main`. A fast-forward is resolved from the reflog only when the tip is on the target's first-parent line.
  - Before/after = the target just before and just after the landing (`M^1`→`M`, or fork→tip for a fast-forward). This refines the architecture's fork→merge: fork→merge would include other work merged in between.
  - Commit export: `git archive` with exclude pathspecs (git 2.50.1 accepts them; `ls-tree` doesn't). `AdapterContext.environment_root` is the one contract change: tools and the venv come from the live checkout, and sources and configs from the export. An export of a clean HEAD must equal the in-place snapshot. Type counts at an export need an identical `uv.lock` hash.
  - Comparability is decided per measurement, and breaks are named. An exclusions change marks every row, and a limits change marks only the over-limit figures. Audit figures reuse `compute_delta`. Review figures say `no floor measured`. No `score` key anywhere.
  - Commands: `slice-ranges`, `snapshot --commit`, and `report slice|project|history` (`trend` is taken).
- Next: task breakdown for 403 (Phase 5). 403 can't be implemented before 402.

### Slice 402: Code-Review Normalization and Ingest — Design Complete (Phase 4)

- Design: `project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md`. `cf validate design` passes, and all 9 decisions are `decided`.
- Key decisions:
  - `ReviewCategory` = `AuditCategory` + `correctness`. Both live in a new leaf module, `core/finding_categories.py` (`AuditCategory` moved, with re-exports), so the review client doesn't import the metrology package.
  - Normalization is opt-in through a `normalize_categories` template flag (only `code.yaml` sets it) and runs in the review client's parse closure. The shared parser is unchanged, so arch, slice and tasks output can't move.
  - Write time matches strictly: anything out of vocabulary becomes `other` with `rawCategory` kept. The historical alias table is read-side only, and records built through it are marked `read_side_mapped`.
  - `sq metrology ingest-reviews`: one `code_review` record per file, keyed on project + content hash, so it's idempotent and a re-reviewed file adds a round. Skips non-code and `UNKNOWN`-verdict reviews. A missing `reviewedSha` is recorded with a reason. The slice comes only from `sourceDocument`.
- Corpus: 116 code reviews, 70 distinct category strings, 113 `uncategorized`, 37 without `reviewedSha`.
- Next: task breakdown for 402 (Phase 5).

### Slice 401: Complexity, Duplication and Coverage — Design Complete (Phase 4)

- Design: `project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md`. `cf validate design` passes, and all 7 decisions are `decided`.
- Key decisions:
  - Complexity (McCabe) and duplication (exact 100-token windows) are counted in-process on 400's parse, so they share function length's function set. No new dependency.
  - Coverage comes from Cobertura XML (coverage.py and Istanbul) as two metrics: `covered_lines` and `coverable_lines`.
  - A report matches the commit when no tracked file is newer than it. It's configured with `metrology.coverage_reports`.
  - Contract unchanged: only enum members are added. The store back-fills missing metrics on read, so 400 records aren't silently skipped.
- Note: Istanbul's Cobertura always writes `version="0.1"`, so a change of coverage provider isn't visible in the identity. The counting text states it.
- Next: task breakdown for 401 (Phase 5).

### Slice 400: Snapshot Record and First Adapters — Implementation Complete (Phase 6)

- Branch `400-slice.snapshot-record-and-first-adapters-keystone`, 34 tasks, not merged (Phase 7 after review). `sq metrology snapshot [--cwd] [--json]` writes one `code_snapshot` record per (project, commit) with file length, function length, lint count and type errors; Python measures all four, TypeScript length and lint.
- Modules under `src/squadron/metrology/snapshot/`: contract, registry, preflight, files, lengths, runner, tool_support, config_hash, take, render, python_{adapter,lint,types}, typescript_{adapter,length,lint}. Models in `snapshot_models.py`; envelope field and store methods in `models.py`/`store.py`.
- **tree-sitter 0.26.0 segfaults** (pymalloc corruption) parsing real context-forge files with the 0.23.2 grammar; 0.24.0 and 0.25.2 are clean. Pinned `tree-sitter>=0.25.2,<0.26` with a test. Found only by the walkthrough, not by unit tests.
- Walkthrough (all ten steps) is recorded in the slice design. Findings: squadron's pyright count includes `tests/` (1,769 errors in 201 files) because the snapshot ignores pyright's `include`; 15 of context-forge's 396 TypeScript files hit grammar error nodes and are listed as `unparsed_files`.
- Real tool output is stored as fixtures in `tests/metrology/fixtures/snapshot/` with an exit-code table. pyright exit 3 (bad config) still prints a valid zero-error JSON report, so the exit code decides, not the JSON.
- Next: code review of the slice, then 401.

### Slice 400: Snapshot Record and First Adapters — Task Breakdown Complete (Phase 5)

- Tasks: `project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md`, 35 tasks, 300 lines, test-with ordering and a commit per milestone.
- Order: dependencies → models/store → config/preflight → contract, files, lengths, runner, orchestrator → real tool-output fixtures → Python adapter (ast, ruff, uv+pyright) → TypeScript adapter (tree-sitter, ESLint) → registry/CLI → docs → walkthrough.
- Fixture source for ESLint's skipped-file case: context-forge's `ignores` covers tracked `**/vitest.config.ts` and `**/tests/**`. ESLint there is 10.12.0.

### Slice 400: Snapshot Record and First Adapters — Design Complete (Phase 4)

- Design: `project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md`. `cf validate design` passes, and all 10 decisions are `decided`.
- Key decisions:
  - One `code_snapshot` record per (project, commit), overwritten in place on a re-snapshot.
  - Identity rules (rule set, environment, absent-with-detail) are enforced by a model validator.
  - One exclusion set applied through git pathspecs. Tool-level include/exclude settings are ignored, so pyright counts `tests/` on squadron.
  - The second language is TypeScript: tree-sitter for length (new dependencies `tree-sitter` and `tree-sitter-typescript`) and the project's own ESLint for lint. Verified against context-forge.
  - Python type counts only when `uv sync --check --locked --offline` passes.
  - A before/after `git status --ignored` check enforces read-only.
- Note: squadron's `.squadron.toml` is gitignored, so its limits (300/50) and exclusions belong to the checkout. The record carries them.
- Next: task breakdown for 400 (Phase 5).

## 20261021

### Release 0.23.8

- **Contents:** a phase step whose agent ends on a question with no artifact now pauses the run with the question and resume command (#249).

### Release 0.23.7

- **Contents:** pipeline failure recovery (#230, #248): usage-limit pause and resume, `--flagged` batch retry, recovery command at run end, `set_model` retry, interrupted batch-item edit committed on resume.

### Release 0.23.6

- **Contents:** slice 366: `/sq:analysis understand` routing on Claude Code and Codex with install guidance, and `sq probe --json` capability probe.

## 20261020

### Initiative 400: Code Quality Measurement — Slice Plan Complete (Phase 3)

- Slice plan: `project-documents/user/architecture/400-slices.code-quality-measurement.md`. It has five slices: 400 snapshot record and first adapters (keystone: Python plus one non-Python language; length, lint and type counts; clean HEAD only), 401 complexity, duplication and coverage, 402 code-review normalization and ingest, 403 slice ranges and rollup reports, and 404 adoption baseline command.
- Commit export moved from the keystone to 403, its first consumer. The architecture's anticipated-slices list was updated to match.
- The architecture design review came back CONCERNS. All 10 findings were accepted and answered in the review file (2b3bc66f).
- Next: slice design for 400 (Phase 4).

### Slice 366: Dispatcher Routing and Documentation — Implementation Complete (Phase 6)

- Branch `366-slice.dispatcher-routing-and-documentation`, one commit per task; not merged (Phase 7). Full suite: 7523 passed, 4 skipped; ruff and pyright clean.
- Shipped: `dispatcher_skills()` parser and drift test; `understand` routed through `/sq:analysis` and `$sq-analysis`; install guidance in both skill copies; `sq probe [--json]` (package `squadron.probe`, contract test reads the example in `capability-probe-contract.md`); README, `docs/COMMANDS.md`, CHANGELOG.
- Walkthrough: steps 1, 2, 6, 7, 8 verified; steps 3–5 verified running the skill directly. Defect found and fixed: on Claude Code `/sq:analysis understand` could not delegate, because `understand.md` had `disable-model-invocation: true` and the Skill tool refuses it (`tech-debt-audit.md` has the same flag but an HTML comment above its frontmatter keeps it from being parsed). PM decision (20261020): drop the flag from `understand.md` and delete the `openai.yaml` twin; typing `/sq:analysis understand` is the explicit invocation. The absent-graph guidance and README now say that building the graph is a paid multi-agent run (PM's API bill for a 250k LOC repo was about $70).
- Walkthrough gap fixed: the Codex dispatcher stays stale until `sq install-commands --ide codex`; added to step 1. That command also writes `~/.codex/rules/squadron.rules`.
- Probe fields unchanged from the contract. After merge, tell cf, sq-cf and ai-project-guide-70 that `sq probe` exists, and cf about the contract table typing (see below).

### Slice 366: Dispatcher Routing and Documentation — Tasks Complete (Phase 5)

- Tasks: `project-documents/user/tasks/366-tasks.dispatcher-routing-and-documentation.md` (13 tasks, 342 lines, one commit per task). Order: parser, drift test, dispatchers, installer pin, skill guidance, probe (types, graph, surfaces, plugin, build, contract, CLI), docs, walkthrough.
- The design's "CLI reference" is `docs/COMMANDS.md`; README gets a pointer only.
- Both skill copies carry Claude and Codex install commands, so one constants test covers README and both copies.
- Contract table now types `analysis_skill_installed` and `understand_plugin_installed` as "bool or null" to match D7/D8; tell CF with the post-merge notice.

### Slice 366: Dispatcher Routing and Documentation — Design Complete (Phase 4)

- Design: `project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md` (`cf validate design` passes).
- The understand skill is already in `commands/analysis/` and gets installed. The slice is now routing (`/sq:analysis` and Codex `$sq-analysis`), missing-graph install guidance, README, and a dispatcher/pack drift test.
- Key decisions: route both surfaces (D1). Pass flow arguments through without validating them (D2). Missing-graph guidance is conditional wording and does not detect the plugin, because `~/.claude/plugins/installed_plugins.json` is an undocumented Claude Code internal file (D3). README covers capability (a) only and `/sq:overview` stays with 365 (D4).
- Must land before CF 260's handoff slice. The capability probe (`sq probe --json`) was folded into 366 afterward (PM-approved 20261020) and added as D6–D11, so routing and the probe ship together per the contract's Shipping Order.
- Reviewed by claude-haiku-5-5 over three rounds (CONCERNS each; accepted at threshold). Planning docs amended: 360-arch (D3), slice plan item 6, initiative plan item 16, probe contract, 365 README owner (#247).
- Next: task breakdown (Phase 5).

### Release 0.23.5

- **Contents:** the 0.23.4 changes. 0.23.4's tag CI failed on one test (`test_run_id_is_listed_in_help`): CI forces colour, so Rich styled `--run-id` across ANSI codes and the substring check missed it. The test now checks the option's `hidden` flag on the command. Nothing was published for 0.23.4.

### Release 0.23.4

- **Contents:** public `sq run --run-id` plus a `run_id=` launch line (#243); `sq runs wait --json` outcome document with checkpoint, failure and reviews detail (#244); branch `when:` and a `merge` param on the code pipelines (#245); `--decision` / `--instructions` on a plain `--resume` (#246); tests pinning `--timeout 0` and non-interactive resume; haiku alias → claude-haiku-5-5; probe contract and 440/cf-260 planning docs. Requested by Amoeba (its S9–S13).

### Initiative 400: Code Quality Measurement — Architecture Complete (Phase 2)

- Architecture: `project-documents/user/architecture/400-arch.code-quality-measurement.md`. Initiatives 400, 420 and 440 were added to the initiative plan on 20261019; context-forge's counterpart to 440 is its initiative 260.
- Key decisions: snapshots and normalized review findings are new record types in 320's store, keyed on `ProjectId` and commit SHA. Unmeasured metrics are recorded as absent with a reason, never as 0. Length limits come from project config, with no squadron default. Normalization maps review categories onto `AuditCategory` only; the review and audit severity scales stay separate (323's rule). Reports are breakdowns with no composite score, and the data never feeds a gate.
- Preferred direction: review templates emit the closed vocabulary at write time; historical reviews are mapped afterwards and marked as such.
- Anticipated slices: snapshot record plus Python adapter (keystone), more language adapters, review normalization and ingest, rollup and trend reports, adoption baseline command.
- Next: slice plan (Phase 3), `400-slices.code-quality-measurement`.

## 20261019

### Release 0.23.3

- **Contents:** slice 947 Unattended Pipelines (`pipeline.max_cost_usd` cost cap, BLOCKED-task pause, no invented review gates, background shell wait; #235, #223, #234, #239) and `sq review code --commit SHA`.

## 20261018

### Slice 947: Unattended Pipelines — Implementation Complete (Phase 6)

- Branch `947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells` (from `main`), merged to `main` as 8ea2575c after the code review (loop steps now stop at the cost cap; notes fixed; #241/#242 logged). Full suite 7396 passed, 4 skipped before the last two fixes; pyright 0 errors; the touched areas pass after them.
- Shipped: D12 dispatch end on the CLI's `idle` state (#239); no-invented-gates review criterion for non-judge templates (`assemble_system_prompt`); `pipeline.max_cost_usd` with `RunSpend` and `FailureKind.COST_CAP`; `squadron.blocked-tasks` and the executor's `awaits_human` copy from event outcomes (#223); shell reporting and wait (#234); docs and CHANGELOG.
- Probe (D10): a Bash command past its `timeout`, and Monitor, start `local_bash` shells the #199 hook never sees; the CLI reports `idle` while one runs and injects a continuation turn when it ends. The wait therefore adds a ledger term to the D12 end rule. Evidence is in the design and on #234.
- Found and fixed beyond the plan: `sq config set` could not store decimals; a cap failure under `on_item_failure: continue` would only flag the item (now fatal to the batch); a failed `fan_out` branch lost its error text; resume after a BLOCKED pause skipped `implement` under `existing: keep` once the branch had a commit (new reserved param `resumed_from_handoff`).
- Walkthrough: live in a scratch project (removed after, with its 7 run states); results are in the slice design. `stop_task` verified to end a `local_bash` task.
- Task 6 (gate rule and `BLOCKED:` convention) landed in CLAUDE.md and the vendored guide; guide v0.21.9 regenerated CLAUDE.md/AGENTS.md. #235, #223, #234, #239 closed.

### Slice 947: Unattended Pipelines — Task Breakdown Complete

- Tasks: `project-documents/user/tasks/947-tasks.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md` (24 tasks, test-with, a commit per feature).
- [#239](https://github.com/ecorkran/squadron/issues/239) is folded into 947 as design D12 and Task 1, instead of slice 990. The dispatch ends on the CLI's `idle` session state (`CLAUDE_CODE_EMIT_SESSION_STATE_EVENTS=1`), with the ledger as the fallback when no state frames arrive. It goes first because the D10 probe and the D11 shell wait both run over `_collect_turns`. The probe gains a fifth question: does the CLI report `running` while a shell is live? If it does, the D11 wait is the D12 wait.
- Probe script location decided: `scripts/probes/background_shell.py`.
- Next: Phase 6 on branch `947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells`.

## 20261017

### Slice 947: Unattended Pipelines — Design Complete

- Design: `project-documents/user/slices/947-slice.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md` (D1–D11, all decided; `cf validate design` PASS).
- #235: shared no-invented-gates criterion appended in `review_client.py` for non-judge templates (judges excluded: calibration); `CLAUDE.md` rule + `BLOCKED:` convention, upstream as [ai-project-guide#45](https://github.com/ecorkran/ai-project-guide/issues/45); task-breakdown guide side already shipped (#44). Cost cap from config `pipeline.max_cost_usd` only, summed from stamped usage in `_execute_step_once`, per invocation and not persisted (revisions 1–2 dropped the YAML field and `RunState.spent_usd`).
- #223: `squadron.blocked-tasks` POST_ACTION bound before `dispatch-branch-work`, pauses via `awaits_human`; resume re-runs implement. Pending-decision pre-check deferred to [#240](https://github.com/ecorkran/squadron/issues/240) (blocked on context-forge#121).
- #234: #199's deny hook was already live when #234 was filed, so Task 1 is a real-SDK probe (shell `task_type`, backgrounding path, continuation turn, progress frames). Then shells are waited on (bounded, progress doesn't reset idle) and reported.
- Next: Phase 5 task breakdown.

### Release 0.23.2

- **Contents:** fixes for [#219](https://github.com/ecorkran/squadron/issues/219) (resume restores earlier step results), [#233](https://github.com/ecorkran/squadron/issues/233), [#236](https://github.com/ecorkran/squadron/issues/236) and [#238](https://github.com/ecorkran/squadron/issues/238) (`sq review --max` stamping, unquoted `dateUpdated`, atomic frontmatter writes); standing fixes slice renumbered 944 to 990; ai-project-guide v0.21.5; slice 947 added to the plan.

### Release 0.23.1

- **Contents:** slice 178 Artifact Usage Stamping ([#222](https://github.com/ecorkran/squadron/issues/222)); revise-round artifact kind fix (41019030); Codex read-only sandbox warning fix (cb6c082c).

### Slice 178: Artifact Usage Stamping — Implementation Complete

- Branch `178-slice.artifact-usage-stamping`, Tasks 1–19 done. Not merged: Phase 7 merges into `main` after the code review passes.
- Built: `RunCost.frontmatter_fields` key table, `review/frontmatter_usage.py`, `review/artifact_usage.py`, `events/builtin/artifact_paths.py`, `squadron.usage-stamp` (POST_ACTION after `revision-stamp`), `stats/artifacts_report.py`, and the `artifact spend` line on `sq stats slice`.
- Walkthrough (scratch slice 958, branch `178-walkthrough-scratch`, kept): all six steps pass; results are in the slice design.
- Fix found by the walkthrough (41019030): built-in revise steps are plain `dispatch` steps with no artifact kind, so `usage-stamp` and `revision-stamp` skipped every revise round (`revision_number` had never fired in a real run). A dispatch step now takes `artifact: design|tasks`; P4/P5/P45/P456/P56 set it. `sq review --revise` strips it because it writes no run state ([#236](https://github.com/ecorkran/squadron/issues/236)). The user's override copies of p5 and p45-user were patched by hand ([#237](https://github.com/ecorkran/squadron/issues/237)).
- Filed: [#235](https://github.com/ecorkran/squadron/issues/235) (reviewers invent confirmation gates; replace with an enforced cost cap, next up), [#238](https://github.com/ecorkran/squadron/issues/238) (`dateUpdated` written quoted).
- Code review CONCERNS: F001–F006 fixed (6092476f), F007–F008 kept; disposition in the review file.
- Validation: ruff clean, pyright 0 errors, full suite 7287 passed, 4 skipped.

## 20261016

### Slice 178: Artifact Usage Stamping — Tasks Complete

- Tasks: `project-documents/user/tasks/178-tasks.artifact-usage-stamping.md` (19 tasks, 258 lines). Parts: A refactors (`RunCost.frontmatter_fields`, `review/frontmatter_usage.py`, `dispatch_artifact_paths`), B `review/artifact_usage.py`, C `squadron.usage-stamp` + binding, D `artifacts_usage_report` + `artifact spend` line, E docs and walkthrough.
- Design correction carried in tasks: the `slice` header renders in `cli/stats_effort_views.py`, not `cli/stats_views.py`.
- Next: task review, then Phase 6 on branch `178-slice.artifact-usage-stamping` from `main`.

### Slice 179: Staged Effort Estimates and Accuracy — Design Complete

- Design: `project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md` (`cf validate design` PASS). Depends on [176, 178]. Effort 3/5.
- Estimate store (D1): one `effort` key (1–5) in slice-design frontmatter. Its history is read from git, not from a list in the file. `cf validate frontmatter` accepts the added key (in-root probe).
- Stages (D2): each committed change takes its stage from the latest review committed strictly before it (`design`, `after-slice-review`, `after-tasks-review`, `after-code-review`); plan is the plan entry value. Git bound becomes 3 + V + E (one `git log -G '^effort:'` call).
- Re-estimate (D4): `_resolve_feedback_prompt` appends a conditional "update `effort` if scope changed" paragraph naming the design path.
- Accuracy (D6): Spearman rho per stage × measure via `statistics.correlation(method="ranked")`, with n and the `metrology.min_evidence_n` floor. `sq stats slices --stage plan|design|final`, plus `artifact_spend` measure from 178.
- Open: the ai-project-guide issue (add `effort` to the slice-design template and guide 004) is implementation step 1 and has not been filed yet. Until it lands, P4 designs carry no design-stage estimate.

### Slice 178: Artifact Usage Stamping — Design Complete

- Design: `project-documents/user/slices/178-slice.artifact-usage-stamping.md` (`cf validate design` PASS). Depends on [175, 176]; feeds 179. Effort 3/5.
- Scope finding: only dispatch writes artifacts with frontmatter. Compact writes no file, and summary's file emit has no frontmatter, so neither is stamped. Phase dispatches (design, tasks, and the P2 arch doc) are stamped.
- Shape: new built-in POST_ACTION `squadron.usage-stamp`, after `revision-stamp`, so it runs only when the dispatch-artifact post-condition passed. It never fails a run (911 D4).
- Loop decision (D2): one cumulative total per artifact under the review keys, plus `usageRounds`, `pricedRounds` and a sticky `usagePartial`. The prior total is read from the file. Per-round detail stays in run state and git. A mixed basis adds `CostBasis.MIXED`. If an agent drops the keys, the total restarts and a WARNING is logged.
- When more than one candidate file was written this run, nothing is stamped (WARNING) rather than splitting the cost.
- Refactors: `RunCost.frontmatter_fields` is the one key table; `stats/frontmatter_usage.py` is the shared reader; `artifact_paths` handles slice and plan resolution and the mtime check.
- Stats: new `sq stats artifacts [--slice]`, and an `artifact spend` line on `sq stats slice`. It is shown beside recorded spend and never added to it.
- Not filed: pipeline review artifacts that carry `runId` drop out of every stats view after pruning (175 reviews-report gap). It needs an issue.

### Release 0.23.0

- **Contents:** slice 177 (`sq replay run|judge|report`, prompt identity on every dispatch, closes #210); `sq stats` slice, producers and runs reports; review fixes to `build_context` provenance, `metrology.judge_timeout_s` handling and replay sandbox errors.

### Slice 177: Producer Replay and Pairwise Judging — implementation (Phase 6 complete)

- Branch `177-slice.producer-replay-and-pairwise-judging` (from `main`). All 39 tasks done; the merge waits for Phase 7. Full suite 7198 passed, 4 skipped; ruff and pyright clean.
- Shipped: `sq replay run|judge|report` (also `/sq:replay` and the Codex `sq-replay` skill), `metadata["prompt"]` on every dispatch, `cf_version` and `guide_version` on `build_context`, the prompt-identity footer in `sq stats producers`, the hidden `sq run --run-id`, `metrology.judge_timeout_s`, and the `producer_replay` and `pairwise_judgment` record types. New package `squadron/replay/`: `start_point`, `sandbox`, `runner`, `outcome`, `drafts`, `judge`, `judging`, `judge_jobs`, `judge_dispatch`, `bradley_terry`, `report`, `report_models`. `core/process_lock.py` is the lock shared with the PR-review worktree.
- Task 1 spike: slice 176 resolves at its start point, but only with two sandbox settings the design did not name: `cf set arch <initiative>` (a fresh `cf init --lite` project has no slice plan) and `cf config set git.integration_branch replay/<id>` (the planning-commit guard). Both are in the sandbox setup.
- Real run on slice 176's design (sonnet and haiku, opus reviewing and judging): both accepted in 2 rounds, about $2.5–2.9 each at API rates; 3 pairs judged in 6 calls and a re-run judged 0. Details are under Task 37 and in the design's Verification Walkthrough.
- Defects found and fixed along the way: `sq stats producers` counted a clean first-draft pass as not accepted whenever P4's loop was skipped (changelog bullet added); failed dispatches had no structured failure kind, so a `failure_kind` is now stamped; the sandbox's `sq` path was relative; the report's group key was an unhashable pydantic model; the stats JSON helper did not serialize pydantic models.
- Design deviations: an empty tracked `.gitmodules` (squadron has one) must not refuse a replay, so only a file that declares a submodule does; `read_outcome` is pure over run state and the drafts are read by `replay/drafts.py`; `sq stats run --json` does not expose dispatch `metadata`, so the walkthrough reads the run state file.
- Spend note: step 7 of the walkthrough ran an OpenRouter alias for real ($0.10) because unsetting its key in the environment did not remove its credentials.
- Open: #227 downstream-outcome scorer, #228 human check of pairwise picks, #229 `sq stats producers` counts replay runs. #224 still blocks `sol` as judge.

### Slice 177: Producer Replay and Pairwise Judging — Tasks Complete

- Tasks: `project-documents/user/tasks/177-tasks.producer-replay-and-pairwise-judging.md`, 39 tasks (353 lines), test-with pairs, commit per task. Effort 4/5.
- Task 1 is the D2 spike (`sq run P4 176` at slice 176's real start point); if the slice does not resolve, work stops and returns to the PM.
- Choices fixed in the task file: payloads in new `metrology/replay_models.py` (`models.py` is 294 lines); `MetrologyStore._iter_records()` extracted before adding list methods; worktree lock helpers move to `core/process_lock.py` (not tied to `PullRequestRecord`, but private); split task files are one artifact, concatenated in suffix order; `sq run` child invoked through an injected `SqRunInvoker` with no timeout (ProcessRunner requires one; D10 leaves hangs to 174's stall bounds); `_resolve_prompt` returns prompt + `PromptSource`.

### Slice 177: Producer Replay and Pairwise Judging — Design Complete

- Design: `project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md` (`cf validate design` PASS). Depends on [176, 320]. The plan entry says Effort 3/5; the design judges it closer to 4/5.
- Shape: `sq replay run|judge|report`. Each config runs as an `sq run P4|P5` subprocess inside a sandbox at the parent of the commit that added the original artifact. The fixed reviewer gives rounds-to-accept; the judge compares first drafts in pairs, in both orders, with the original first draft as a free baseline contestant; results are aggregated with Bradley-Terry (not Elo). Two new metrology record types, `producer_replay` and `pairwise_judgment`, replace 176 D1's single `producer_score`.
- Deviation from the plan entry: the sandbox is a depth-1 fetch, not a git worktree. A worktree shares refs, so a tool-using producer could read the original artifact from `main` (D3).
- Prompt identity (D8): every dispatch records the prompt's SHA-256 and source, and `build_context` records the cf and guide versions. `sq stats producers` keeps pooling across template revisions, because the guide changes weekly and splitting would push most cells below the floor.
- Open risk, settled first: at a design's start point the plan entry may not yet carry the `(index)` prefix (Phase 4 adds it in the same commit). Task 1 tests `sq run P4 176` at slice 176's real start point.
- Judge and reviewer are required arguments with no defaults. Don't use `sol` until #224 is fixed.

## 20261015

### Slice 176: Effort Calibration and Producer Model Effectiveness — implementation (Phase 6 complete)

- Branch `176-slice.effort-calibration-and-producer-model-effectiveness` (from `main`). Tasks 1–33 done; the merge waits for Phase 7. The #214 and #210 comments are drafted in the task file under Verification Notes, not posted.
- Shipped: `sq stats slice|slices|producers|runs` with `--json`. Every loop round is now persisted in run state (`prior_round_results`, `accepted`, `exhausted`), so `sq stats run` no longer undercounts revised loops. New `stats/` modules: `planning_docs`, `git_history`, `review_rounds`, `task_attribution`, `effort_report`, `effort_rollup`, `slice_spend`, `producer_units`, `producer_report`, `json_support`.
- Design changes made against real data: (1) task-group `extra` counts implementation commits only (doc commits would have put 6 planning commits into 175's group 1); (2) `producers` excludes only a phase step with no dispatch, because 9 of 24 failed phase steps here have a dispatch and no review, and the reviewer is the review action's `requested_model` (the task gate reports itself as `model`); paused phase steps are excluded and counted. D8 and the D9 table are updated.
- Fixes found by running on this repo's history: the rollup re-parsed every review per slice (76 s, now 11 s with one read); plan entry 32 held both "Effort: 4/5" and "Effort now 3/5" and is rewritten as one entry.
- Test changes: `stats_repo` fixture in `tests/conftest.py`, shared builders in `tests/stats/`; fixtures in `tests/stats/fixtures/planning/` are verbatim copies of real planning files. Full suite 6952 passed.
- Walkthrough: steps 2–8 pass; step 1 (live scratch-project run) not run. Observed median span by planned effort since 20261001: 2/5 1h28m, 3/5 3h21m, 4/5 7h22m.
- Open: the installed `/sq:stats` wrapper text lists only `run` and `reviews` until `sq install-commands` refreshes it. Five historical review versions with unreadable frontmatter (157, 161, 169, 343, 916) log a WARNING on every rollup.

### Slice 176: Effort Calibration and Producer Model Effectiveness — Tasks Complete

- Tasks: `project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md`, 31 tasks, test-with pairs, commit per checkpoint. Effort 3/5.
- Choices fixed in the task file: renderers split into `cli/stats_effort_views.py` and `cli/stats_producer_views.py` (`stats_views.py` is 242 lines); `parse_frontmatter(text)` extracted for `git show` content; `SLICES_DIR`/`ARCHITECTURE_DIR` beside `TASKS_DIR`; split task files read as one list; `GitHistory(project_root, run=run_git)` so tests count git calls.
- Surprises: `StepResult.prior_rounds` is a flat list, so Task 1 checks whether round boundaries survive and regroups it if not. 941 was fast-forwarded (no merge commit), so the rounds lower-bound cutoff is a date constant (20261013). No `173-slice.*` branch exists, which matches the design's `unavailable` case for 173. `/sq:stats` and `sq-stats` list subcommands in prose and need doc updates.

### Slice 176: Effort Calibration and Producer Model Effectiveness — Design Complete

- Design: `project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md` (`cf validate design` PASS). Effort 3/5, depends on [175].
- D1 split: replay runner, pairwise judge and the metrology record move to new slice plan entry 33 (Producer Replay and Pairwise Judging, depends on 176 and 320). 176 keeps an observed-runs report, `sq stats producers`. No eval tool is adopted (promptfoo and inspect_ai bring their own provider layers); only the method is borrowed.
- Surprises: run state persists only a loop's final round, so 175's `sq stats run` undercounts revised runs. D3 persists `prior_round_results`, `accepted` and `exhausted`. Recent task files (160–175) have no per-task `Effort`, so planned effort comes from the slice plan entry and is reported as an ordinal distribution, not a ratio (D2). Commits never cite task numbers, but the task files' prescribed `Commit:` subjects match git verbatim (16/16 in 175), and they are the attribution anchors (D5). Per-round review verdicts come from the committed versions of review artifacts (D6).
- The task-kind tag is already tracked as ai-project-guide#42 (`**Kind**: <value>`).

### Release 0.22.0

- **Contents:** slice 175 Usage and Cost Tracking — `sq stats run|reviews`, `/sq:stats`, usage and cost on SDK reviews and every pipeline LLM step, alias output budget on dispatch and summary (#172, #36, #154, #151, #158; #33 partial). Code review fixes: a failed review part stops the step, `--json` on a missing reviews dir, run-wide pricing-warning dedupe.

## 20261014

### Slice 175: Usage and Cost Tracking — implementation (Phase 6 complete)

- Branch `175-slice.usage-and-cost-tracking` (from `main`), merged 20261015. Tasks 1–33 done; Task 34 issue comments posted (#172, #36, #154, #151, #158 closed; #33 commented, left open).
- Shipped: `UsageRecord`/`CostBasis`/`cache_write` in `core/usage.py`; `price_usage` + `resolve_cost` (D3) replace `estimate_cost`; SDK `ResultMessage` reader (`providers/sdk/usage.py`) used by the SDK agent and `SDKExecutionSession` (own result, injected turns, drains; errors carry telemetry); `SessionReply` from dispatch/capture_summary/compact; `pipeline/usage_capture.py` builds every record, one per run via `ActionContext.usage_capture`; dispatch, summary, compact, review stamp `metadata.usage`; review artifacts gain `cacheWriteTokens`/`costUsd`/`costBasis` and a `Cost:` digest line; dispatch and summary send alias `max_output_tokens` (#151); `sq stats run|reviews` (+ `--json`), `/sq:stats`, `sq-stats` skill.
- Gaps the design missed, fixed here: `ResolvedModel` gained `alias` and `run_review_with_profile` an `alias` argument (no alias name reached pricing); review frontmatter `slice` holds the slice name, so `--slice` also matches the file name's leading index; the one-shot runners report the effort they sent through `usage_metadata` (keeps provider lookups inside the mocked boundary).
- Found: real CLI results carry `usage.output_tokens_details.thinking_tokens`; D1 assumed no reasoning split, so SDK `reasoning` stays `None` (possible follow-up).
- Tests: `ActionContext` constructions for LLM-action tests now pass a `UsageCapture` (no single shared helper existed); byte-identity review fixtures regenerated for the token-line and `Cost:` changes (383 pre/post sets together, so their diff is still the two 383 keys). pytest's metrology variance tests sleep the 60 s default cooldown, which dominates suite time.
- Walkthrough: all 7 steps pass. Step 2: glm-flash review `costBasis: alias_pricing`, $0.0053. Step 3: `sq run P4 108 -p model=glm-flash` → `sq stats run` total $0.09 (3 of 3 priced). Step 4: `OPENAI_LOG=debug` shows `max_completion_tokens` 128000/384000 sent; step text corrected (no squadron DEBUG line exists). Details in the slice design.
- Next: code review, Phase 7, release. Follow-on #214/#210 slice still needs a slice plan entry.

### Slice 175: Usage and Cost Tracking — task breakdown complete (Phase 5)

- Tasks: `user/tasks/175-tasks.usage-and-cost-tracking.md`, 34 tasks, 326 lines, effort 4/5. Test-with ordering; commits at each section. Revised per task review (CONCERNS): `usage_capture.stamp` guard, D7 flag on `UsageCapture`, reviews report in its own module, issue closure drafted for PM at Phase 7.
- Choices the design left open, fixed in the task file: D3 precedence in one `resolve_cost` beside `price_usage` (shared by `review_client` and `usage_capture`); pricing-warning set and D7 DEBUG flag owned per run by the executor (`ActionContext.usage_capture`) and per call by `review_client`; `SDKExecutionSession.dispatch/capture_summary/compact` return `SessionReply(text, telemetry)`, errors carry telemetry, D5 `partial` = stall with `session_usable False`.
- #151 budget follows the existing `applies_output_budget` capability. Real `ResultMessage` fixture is captured from `claude -p --output-format json` (Task 8).

### Slice 175: Usage and Cost Tracking — Design Complete

- Design: `user/slices/175-slice.usage-and-cost-tracking.md`, effort 4/5; `cf validate design` passes.
- Finding: 931 already built `core/usage.py`, OpenAI/Codex usage, alias effort, review frontmatter keys; only reviews consume it. SDK agent and `SDKExecutionSession` discard `ResultMessage` usage/cost; dispatch, summary, compact record nothing; `estimate_cost` has no callers; #158 implemented by 931 but still open.
- Decisions: `prompt` = all input incl. cached and new `cache_write` (D1); read `ResultMessage` only, sum per result incl. drains (D2); cost = provider-reported > alias pricing > none, partial price → none + WARNING (D3); `UsageRecord` built once in `pipeline/usage_capture.py`, stored in `ActionResult.metadata["usage"]`, no run-state schema bump; `StepState.duration_seconds`; `sq stats run|runs|reviews` read-only.
- Scoped out: MCP tool (squadron has no MCP server), #34 fix (measure only), SDK session effort application (#216 filed; recorded as `None` + WARNING), #214/#210 split to a follow-on slice (needs a slice plan entry). #173 is a precondition-gated probe.

### Release 0.21.9

- **Contents:** slice 946 Run Params and Pipeline Correctness: `-m` sets the default model only (#215), comma-separated `-p` (#207), deprecated slices skipped (#208), every loop round in summaries (#170), cf slice reset after a plan batch (#206), parser warning ids (#141), judge verdict shared with `sq review` (#140).

### Release 0.21.8

- **Contents:** slice 945 Dispatch Outcomes Match What Happened (Codex tool contract and silent success; #211, #202, #212 item 2), default tools for write steps and the bash warning (#213), Codex limited to read-only `allowed_tools`, #144 fix.

### Slice 945: implementation complete (Phase 6)

- Branch `945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success` (from `main`), not merged; code review comes before Phase 7. Full suite 6670 passed, 4 skipped; pyright 0 errors.
- Shipped: write-required contract (`AgentConfig.requires_writes`, `dispatch_requires_writes`, `WRITE_TOOL_NAMES`, telemetry key constants in `providers/base.py`); spawn refusals (Codex `allowed_tools`, Codex read-only on write-required; OpenAI-compatible without a write tool); `pipeline/actions/dispatch_outcome.py` wired into `_dispatch_via_agent`; SDK failed-call count fixed; one-line cf errors in the dispatch-artifact post-condition and the keep path (#202); `ActionResult.awaits_human` + `BranchFailure.UNFINISHED_TASKS` pause the run at a merge with unchecked tasks or no cf task files (#212 item 2).
- Found during the walkthrough: no profile could set a Codex `sandbox`, so the refusal's fix was unreachable. Added `ProviderProfile.sandbox` (providers.toml), passed through `profile_credentials`; README and CHANGELOG updated.
- Existing merge fixtures (`test_branch_merge`, `test_branch_composition`, `tests/cli/test_branch_run`) relied on cf listing no task files, the gap D6 closes; they now supply a finished task file.
- Walkthrough (steps 1-7) ran in a scratch repo registered with `cf init --lite` at `~/source/repos/manta/temp/scratch-945`; results are in the slice design. Caveats: step 6's error continues with the agent's final text; the P4 design agent on the stub slice declined to write, so step 2's file write was checked with a bare probe; P6 was not run, only its merge step.
- Not fixed: a bare Codex dispatch on a read-only sandbox still completes without writing (WARNING only, by design); the default SDK path has no tool telemetry; #212 item 1 stays open until the trading-ui run id is found. The Codex refusal names the provider id, not the profile name (`AgentConfig` lacks it).
- Next: code review, then Phase 7; then #210 item 1.

### Slice 945: task breakdown complete (Phase 5)

- Tasks: `user/tasks/945-tasks.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md`, 26 tasks, effort 3/5. Order: branch; D1 contract (`WRITE_TOOL_NAMES`, `requires_writes`, predicate in `dispatch_rules.py`); D4 SDK count; OpenAI `first_tool_error` + write-tool refusal; Codex refusals; `dispatch_outcome.py` + wiring; D5 cf one-liners; D6 `awaits_human`, `UNFINISHED_TASKS`, batch mapping; CHANGELOG; walkthrough.
- D6 note: `_flag_kind` checks PAUSED status first, so the `UNFINISHED_TASKS` → `STEP_FAILED` check must precede it.
- Next: Phase 6 implementation.

### Slice 945: design complete (Phase 4)

- Design: `user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md`, effort 3/5. Write-required dispatch (phase steps, revise dispatches) derived, not declared; providers refuse at spawn what they cannot honor (Codex: `allowed_tools`, read-only sandbox on write-required; OpenAI-compatible: no write tool); dispatch outcome table D3 (declared-not-given, zero calls on write-required, all calls failed → fail; partial failures → warn); SDK `failed_tool_calls` never counted (ToolResultBlock arrives in `UserMessage.content`) — fixed in scope; #202 one-line cf errors; #212 item 2: unchecked tasks at merge → `paused`.
- #15 check: no-artifact post-condition covers `design`/`tasks` only, not `implement`, revise, or bare dispatch. Bare text-only dispatch stays out of scope (warn on read-only Codex only).
- Open: #212 trading-ui run state not on this machine; finding for #212 item 1 — merge gate passes when cf lists no task files.
- Next: Phase 5 task breakdown.

## 20261013

### Release 0.21.7

- **Contents:** slice 941 (`sq review slice|tasks|code --max N [--revise-model M]`: review, then revise until it passes, using P4/P5/P6's loop); fix: a revise loop ends when its round commit fails (issue 200 follow-on, 85a7f7aa). Slice 935 plan entry checked.

### Slice 941: implementation complete (Phase 6)

- Branch `941-slice.review-and-revise-loop-from-sq-review-max` (from `main`), not merged; code review comes before Phase 7. Full suite 6599 passed, 4 skipped before the walkthrough fixes; pyright 0 errors.
- New: `pipeline/review_revise.py` (builder), `pipeline/run_session.py` (`classify_for_run` + `pipeline_session`, extracted from `sq run` per PM, so the loop's revise dispatch gets its SDK session), `cli/commands/review_revise.py` (`RoundPrinter`, runner, D6 validation); `RunObserver.round_completed`; one helper plus option declarations in `review.py`.
- Walkthrough fixes: `slice`/`tasks --max` must run on the integration target (planning commits); git faults exit 1 without a traceback; `--max` min 1; a failed review prints instead of crashing the printer; an unsaved final review exits 1; the builder requires `commit_each_iteration`.
- Walkthrough ran inside Claude Code in a scratch clone registered with `cf init --lite` (removed after): design loop FAIL→CONCERNS→FAIL exit 2; tasks loop with `--revise-model sonnet` accepted at CONCERNS exit 0; code loop on the slice branch exit 2, refused on `main`. The sdk reviser (opus) ran in-session, so `--max` needs no `CLAUDECODE` guard.
- Not done: `/sq:review --max` (step 6) needs an installed `sq` with `--max`. Declined from the walkthrough's reviews: design edits that grew scope (failed round review ends the loop, more builder checks), and `--cwd` anchoring cf/pipeline lookup, which plain `sq review` shares.
- Next: code review, then Phase 7; then #144.

## 20261012

### Slice 941: task breakdown complete (Phase 5)

- Tasks: `user/tasks/941-tasks.review-and-revise-loop-from-sq-review-max.md`, 12 tasks, effort 3/5. Order: branch + `RunObserver.round_completed`, `pipeline/review_revise.py` builder, `RoundPrinter`, runner (params/exit codes), option validation + wiring into `review_slice`/`review_tasks`/`review_code`, integration test, slash doc + CHANGELOG, walkthrough.
- Next: Phase 6 implementation on `941-slice.review-and-revise-loop-from-sq-review-max`.

### Slice 941: design complete (Phase 4)

- Design: `user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md`, effort 3/5. `sq review slice|tasks|code <index> --max N [--revise-model M]` composes `[review, <P4/P5/P6 loop>]` from the loaded pipeline (loop found by step type, `on_exhaust` → fail) and runs it with `execute_pipeline`; table `REVISE_PIPELINE_BY_KIND` keyed by `BuiltinReviewTemplate`. No resumable run state (composed definition can't be reloaded by name); rerun is the resume. Incompatible `sq review` options refused with `--max`; `code` requires the slice branch checked out.
- Plan deviation: squadron has no MCP review tool, so parity is CLI + `/sq:review` only.
- Next: Phase 5 task breakdown.

### Release 0.21.6

- **Contents:** slice 935 (project rules for every provider: AGENTS.md first, `steps` rule key, `project_rules.max_chars`; #181, #182); fixes #195, #59 (orphaned-run resume, `each` resume skips finished items).

### Slice 935: implementation complete (Phase 6)

- Branch `935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules` (from `main`), not merged; code review comes before Phase 7. Full suite 6533 passed, 4 skipped; pyright 0 errors.
- New `squadron.project_rules` (`conventions`, `frontmatter`, `selection`, `render`); pipeline glue in `pipeline/actions/dispatch_rules.py`; phase steps pass `RULES_STEP_PARAM`.
- Deviations: `conventionsSource`/`projectRules` ride on `ReviewResult` and are written once in persistence (known only after rules load or the review runs), not threaded through each save target; provider-failure artifacts carry neither. `load_review_rules` returns `ReviewRules(content, language_rules)`. `sql.md` matches implement and review via `**/tests/**/*.py` and `**/conftest.py`; D3 corrected.
- Walkthrough (scratch copy, `cf init --lite`, one-step pipelines; design section rewritten with the working commands):
  1. `conventionsSource: AGENTS.md` (luna). 2. `CLAUDE.md`. 3. `none`.
  4. qwen38-flash implement: `{"conventions":"AGENTS.md","native":false,"skipped":["CLAUDE.md"],"rules":["bug-fixes.md","python.md","shell.md","sql.md","testing.md"],"dropped":[],"chars":37502}`.
  5. `bug-fixes.md` with `steps: [implement]`: bare dispatch `"rules":[]`; code review `projectRules: [python.md, sql.md, testing.md]`.
  6. PM ran from a terminal with the branch's `.venv/bin/sq` (haiku, `sdk-session`): `{"conventions":"sdk-native"}`. The uv-tool `sq` on PATH is released 0.21.5 and records nothing.
  7. Budget 5000: fails with `…/AGENTS.md is 14798 characters, over the 5000-character budget (project_rules.max_chars)`.
  8. luna: `"conventions":"AGENTS.md","native":true`, five rules, `chars` 22731; with `AGENTS.md` removed: `"conventions":"CLAUDE.md","native":false`.
- The `openai` API-key aliases have no credits by design; use `openai-oauth` aliases (luna/sol/astra).

### Slice 935: task breakdown complete (Phase 5)

- Tasks: `user/tasks/935-tasks.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md`, 23 tasks, effort 3/5. Order: branch, helper move (no behavior change), `steps` parsing, conventions discovery + review switch, selection/render/budget, `dispatch_rules.py` + dispatch wiring, review filtering, docs, walkthrough.

### Slice 935: design complete (Phase 4)

- Design: `user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md`, effort 3/5. Fixes #181, #182.
- New `squadron.project_rules` package used by non-SDK dispatch and reviews. Conventions file: first of `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, injected whole as written; others recorded as skipped. Rule relevance via a new optional frontmatter key `steps`, with Claude Code-compatible defaults.
- SDK keeps native loading (records `sdk-native`). Codex loads `AGENTS.md` natively (verified by probe), so squadron skips that file for codex and injects only the selected rules. Budget `project_rules.max_chars` (48000): drop rules with WARNING, fail if the conventions file alone exceeds it.
- Recorded in dispatch metadata `project_rules` and review frontmatter `conventionsSource`/`projectRules`.
- Slice review (CONCERNS) addressed: `requires`/capability model cut (#204), `@` import resolution cut (#205), `RuleContext` carries `rules_dir` so `project_rules` never imports `review`, failure-mode table added.

### Release 0.21.5

- **Contents:** slice 943 (Proportionate Reviews); fixes #189, #200, #199, #143, #145; ai-project-guide v0.20.10.

## 20261011

### Slice 943: implementation complete (Phase 6)

- Branch `943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope` (from `main`), not merged; code review comes before Phase 7.
- `REVISE_GUIDANCE` in `dispatch.py`, appended by `_findings_block` when there are findings (both revise paths). Proportionality bullet and gap qualifier in `slice.yaml` and `tasks.yaml`, and a PROPORTIONALITY block in `arch.yaml`. No judge template changed.
- Rerun of trading-ui 127 (opus/sonnet): 5,064 → 5,217 → 5,287 words (+4.4%; baseline +65%). All CONCERNs were real correctness gaps, coverage held, nothing deferred. The pass rule changed from "final ≤ initial" to "no round grows more than about 10%" (PM accepted).
- The rerun needs a cf-registered worktree with its own integration branch, arch and plan (walkthrough step 2). Issues: #202 (cf error traceback in the artifact post-condition), #203 (heavy first drafts still pass proportionality).

### Slice 943: task breakdown complete (Phase 5)

- Tasks: `user/tasks/943-tasks.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md`, 9 tasks, effort 2/5. Order: branch, revise paragraph + tests, slice/tasks/arch template edits, CHANGELOG, slice 127 rerun (stops and reports on failure rather than iterating wording).

### Slice 943: design complete (Phase 4)

- Design: `user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md`, effort 2/5. Prompts only: two-sided proportionality criterion (overweight = CONCERN, cutting plan-assigned scope = CONCERN) and a gap-needs-a-requirement qualifier in slice/tasks/arch templates; a smallest-sufficient-change paragraph in `_findings_block` (deferrals become GitHub issues). Judge and code templates excluded (judge edits re-key 320 calibration).
- Baseline for verification (trading-ui 127, `run-20261010-p4-e8ba2e27`): design words 4,673 → 6,561 → 7,735 across rounds; in-session cut to 3,135. Rerun from trading-ui `2c5e9d4`.

### Release 0.21.4

- **Contents:** Slice 933 (deterministic task-file gate) with its code-review fixes (pipeline off-thread gate and unreadable-file handling, CLI short-circuit before the model loop, matched rule named in findings), plus the #201 fix and the tools/calls telemetry display already on main.

### Slice 933: implementation complete (Phase 6)

- Branch `933-slice.deterministic-task-file-gate` (from `main`), not yet merged; Phase 7 follows code review.
- `review/task_gate.py` (pure): `scan_merge_steps` with a named four-rule pattern table (`MERGE_OBJECT_WINDOW = 4`), and `merge_gate_results`, which builds FAIL `ReviewResult`s (`model=squadron-task-gate`, `verdict_source=imposed`, no tools, no profile, no cost) keyed by each part's `input` path, with that part's full inputs dict as `input_files`.
- `review/task_gate_files.py`: `gate_task_files(part_inputs)`, the one read-and-gate entry point both callers use; `TaskFileReadError` names the unreadable path.
- CLI `review_tasks`: builds every part's inputs dict up front, runs the missing-file check (extracted to `_exit_on_missing_inputs`) and the gate before the per-part loop; gated parts reuse the loop's display/save path. Pipeline `ReviewAction._gated_parts` reuses `_save_part`/`_part_result` and `fold_review_parts`.
- Tests: real-line fixtures under `tests/review/fixtures/task_gate/` (trading-data 184/185/908/909, trading-ui 124/125, squadron negatives); scanner, builder read-back, helper, CLI, pipeline and CLI/pipeline parity tests. Two existing routing tests in `tests/cli/test_review_resolve.py` reference task files that do not exist on disk; they now stub the gate.
- Walkthrough verified (design "Verification Walkthrough" updated with commands and output); the finding title now carries the offending line text so the default terminal view shows it.


### Slice 933: task breakdown complete (Phase 5)

- Tasks: `user/tasks/933-tasks.deterministic-task-file-gate.md`, 12 tasks, effort 2/5. Order: branch, vendored fixtures (trading-data 184/185/908/909, trading-ui 124/125, squadron negatives), scanner + tests, FAIL builder + read-back test, shared read-and-gate helper, CLI hook + tests, pipeline hook + parity tests, walkthrough.
- The task file keeps every literal merge example in prose and tables, never in checklist items, so it passes the gate it describes.

### Slice 933: slice design complete (Phase 4)

- Design: `user/slices/933-slice.deterministic-task-file-gate.md`. A pure scanner (`review/task_gate.py`) flags merge checklist items and headings in task files; both tasks-review paths (CLI and pipeline `review:` action) call it before any model call. Real-line fixtures from trading-data 184/185/908/909.
- Decision with the PM: pipelines that review, revise to threshold, then merge stay as they are; only merge items in task files are forbidden. ai-project-guide is rewording process.md:159 accordingly.
- Separate from 933: shell.md rule matching (`match_rules_files` is suffix-only) still needs its own slice.

## 20261009

### Release 0.21.3

- **Contents:** slice 940 Everyday CLI Fixes (#198 `sq pipelines copy`, #197 `sq models init`, #169 run names and path resume, #177 escaped CLI output, #193 review profile in `-v` and artifacts) and its code-review follow-ups; empty slice branch reporting and failing implement dispatch with no commits (sq-bug fix).


**p6: devlog-3**
- branch-0: PASS
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: FAIL)
- checkpoint-5: PASS
- commit-6: PASS
- dispatch-0: FAIL
- review-1: PASS (verdict: CONCERNS)
- commit-2: PASS

### Slice 940: implementation complete (Phase 6)

- **Delivered:** D5 guard test (`tests/cli/test_rich_escape_guard.py`, AST, no allowlist) plus the escape sweep over `src/squadron/cli`; D4 `RunState.pipeline_path`, `RunState.load_target`, run.py `_run_record_identity` / `_load_run_definition` (resume, `--step-done`, prompt-only next, item resume, implicit resume and `DefinitionCache` reload the recorded file; path args are no longer lowercased); D6 INFO log in the review action and `aiProfile` (`ReviewResult.profile`, failure writer parameter); D3 `core/file_write.write_new_file`; D1 `PipelineScope` / `pipeline_target_dir`, `sq pipelines copy`, `PipelineInfo.shadows` and a conditional marker column; D2 `models_init.build_starter_text`, `sq models init`, doctor wording; D7 styled list cells.
- **Choices the tasks left open:** `aiProfile` for success artifacts rides on the result (one stamp, every caller covered) instead of a parameter on both writers. The review's FAIL/concern findings were fixed in the same pass: resume executed `state.pipeline` after planning with `load_target`; a deliberate markup string had been escaped; dry-run step types and each-config values escaped; resume errors go to stderr; the guard only trusts `escape` / `markup.escape`. The `-v` test asserts handler wiring, not captured text (the stream handler binds stderr once per process).
- **Spec conflict:** after an unnamed `copy`, the name resolves to the copy, so repeating it is the own-file refusal; the "exists / --force" cases use a named copy.
- **Verification:** 6329 passed, 4 skipped; ruff and pyright clean. Walkthrough run in a scratch HOME (recorded in the slice). The real `~/.config/squadron` gained only `runs/` entries from a live `sq run p6 940 -v` in another session; no pipelines, models.toml or config.toml changes.
- **Not done:** no merge (Phase 7). `cf check` follows.
- **Next:** Phase 7 code review and merge into `main`.


### Slice 940: task breakdown complete (Phase 5)

- **Delivered:** `user/tasks/940-tasks.everyday-cli-fixes.md`, 23 tasks in five parts: D5 AST guard test and seven-task escape sweep, D4 run names and `pipeline_path`, D6 review profile log and `aiProfile`, D3/D1/D2/D7 helper, `pipelines copy`, `models init`, list color, then validation and close-out.
- **Next:** Phase 6 implementation on branch `940-slice.everyday-cli-fixes`.

## 20261008

### Release 0.21.2

- **Contents:** fixes only. Split task files: `tasks-plan` selection and `implement-plan` readiness read every `.part-N` tasks review and judge by the worst part, and step commits stage all parts (previously split slices were redone every run and their reviews left uncommitted). Clearer dispatch post-condition message when the agent writes no artifact. Blank line between groups in `sq pipelines list`. Logged #196 (review line citations are model-counted).

## 20261007

### Release 0.21.1

- **Contents:** slice 174 (run liveness, foreground stall bound, `sq runs prune`, `sq pipelines show`, readable listings; #190, #165) with code-review fixes: unsupported-schema runs protected from prune, heartbeat teardown no longer swallows cancellation.

### Slice 174: implementation complete (Phase 6)

- **Delivered:** RunState schema v5 (`RunOwner`, `heartbeat_at`, `active_step`, `active_item`, `progress_at`); `run_liveness` (`assess_liveness`, `process_alive`, LIVE/STALE/ORPHANED/UNOWNED); `RunObserver` replaces `on_step_complete`; `RunHeartbeat` around every SDK run (owner in the creating write, `claim` on resume); foreground idle bound with interrupt and drain (`DispatchStalledError`, dispatch maps it to `dispatch stalled: …`); `sq runs wait` exit 8; `cli/columns.py`; both listings rebuilt on it; `sq runs list -v` and one unavailable-pipeline summary line; `sq pipelines list -v`; `sq pipelines show [--path]`; `StateManager.scan_runs`; `run_prune` and `sq runs prune`. Config keys `pipeline.foreground_idle_timeout_s`, `pipeline.run_heartbeat_interval_s`. Issue #195 (resume an orphaned run).
- **Spike:** on the installed SDK, `interrupt()` returns at once; a fresh `receive_response()` yields the turn's own `ResultMessage` (`is_error`, `error_during_execution`) and the next `query()` works. D7 stands; the drain reads with `accept_error=True`. No state write runs off the loop thread, so no lock.
- **Choices the design left open:**
  - `resolve_pipeline` returns `PipelineLocation(name, source, path)`, not `PipelineInfo`, so `show` works on a pipeline that fails validation (recorded in the design).
  - One `_IdleTimeout` replaces `_BackgroundIdleTimeout`; `_collect_turns` knows which kind of read it made.
  - Progress-write failure handling lives once in `StateManager._write_progress`; `RunHeartbeat`'s done-callback logs anything else at ERROR.
  - Prune protection is one rule: every protected category a run has (paused, unowned, stale) must be selected, unless the run is named. Named missing runs are refusals. `apply_prune` attempts every file of a run and refuses paths outside the runs dir.
  - `RunOwner.heartbeat_interval_s` is rounded up to at least 1 for sub-second test intervals.
  - `format_duration` lives in `run_liveness`, shared by the listing, prune preview and wait's stale WARNING.
  - `DefinitionCache` (was `_Definitions`) is shared by listing and prune; `state_file_name` defines `{run_id}.json` once.
- **Verification:** main tree 6248 passed, 4 skipped (baseline 6081); pyright 0. Walkthrough steps 1–5 and 8 in a scratch HOME (`tests/pipeline/walkthrough_seed.py`); `sq runs list --all` 0.66–0.73 s for 188 runs. Steps 6–7 not run (`sq run` refuses inside Claude Code). Real runs dir preview: 95 runs in the default prune set, 34 unowned pre-174 leftovers. Frozen-worktree runs fail 4 cf schema-drift/live-contract tests (checkout path is not the registered project); they pass in the main tree.
- **Next:** Phase 7 code review, then merge into `main`; close #190 and #165 after the merge.

### Slice 174: task breakdown complete (Phase 5)

- **Tasks:** `user/tasks/174-tasks.run-liveness-stall-bounds-pruning-and-readable-listings.md` (42 tasks, 511 lines, one file; overrun under 100 so no split). Parts: spike and baseline; `RunObserver` refactor (no behaviour change); schema v5, `run_liveness`, `RunHeartbeat`; foreground stall (`DispatchStalledError`); wait and listing; `cli/columns.py` and both listings; `pipelines show` and `resolve_pipeline`; `run_prune` and `sq runs prune`; docs, issue, walkthrough.
- **Notes:** Task 2 (SDK interrupt spike, state-write threading check) gates Part C and D5; no merge task, per the Phase 5 guide.
- **Next:** PM approval, then Phase 6 on branch `174-slice.run-liveness-stall-bounds-pruning-and-readable-listings`.

### Slice 174: slice design complete (Phase 4)

- **Design:** `user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md`. RunState schema v5 (owner PID/host/interval, heartbeat, `active_step`, `active_item`, `progress_at`); `run_liveness.assess_liveness` (PID or stale heartbeat convicts; `orphaned` derived, never persisted); every SDK run, resumed runs included, is claimed as `running`; `sq runs wait` exit 8 for orphaned. Foreground idle bound `pipeline.foreground_idle_timeout_s` (1800): interrupt, bounded drain, `DispatchStalledError`; the session stays usable only when the interrupt completes. `sq runs prune` (categories, preview unless `--yes`, paused and live protected), `cli/columns.py` fitter (cf algorithm, non-shrinkable columns), one unavailable-pipeline summary line, plain `sq pipelines list`, `sq pipelines show [--path]`.
- **Open:** Phase 6 starts with an SDK interrupt spike; resuming orphaned runs is excluded (an issue is opened in Phase 6).
- **Next:** Phase 4 review, then Phase 5 task breakdown.

### Release 0.21.0

- **Contents:** slice 199 (`sq pipelines list`, `sq runs list`, `sq runs wait`; `sq run --list` removed; `sq list` → `sq agents list`; #185, #187), slice 934 (pipeline run correctness: merged slices not reimplemented #188, one review-profile cascade #184, `--dry-run` rejects unknown aliases/templates #175, lagging PR refs and single code-host failure output #186).

### Slice 199: implementation complete (Phase 6)

- **Delivered:** `sq pipelines list` (`PipelineSource`, `LISTING_ORDER`), `sq runs list` and `sq runs wait` on `pipeline/run_listing.py` (`RunSummary`, `ResumePoint`, `ResumeProblem`, `wait_for_run`, `WaitOutcome`, `WAIT_EXIT_CODES`); `cli/run_views.py` (status colours, run status panel, both listings, marker text); `pipeline/item_eligibility.py` shared with item resume; `first_unfinished_step_of`, public `RESUMABLE_STATUSES`, `RUNNING_STATUS`; `report_json_path(s)`. `sq run --list` removed; `sq list` → `sq agents list`. Follow-ups: #191 (RunStatus enum), #192 (`--json`).
- **Choices the design left open:** the agents skill `sq-list` appends arguments in prose, not `$ARGUMENTS` (an existing test forbids Claude-only substitution in agents skills); the run table is borderless and never folds Run ID / Status / Resume at, so at 80 columns Rich drops Pipeline, Target and Started; `wait_for_run` also treats `UnicodeDecodeError` as UNREADABLE (same read-error set as `list_runs`) and cuts its last sleep to the deadline; `WAIT_POLL_INTERVAL_SECONDS = 2.0`.
- **Verification:** walkthrough steps 1, 2, 5, 6, 8 against a scratch HOME; 3, 4, 7 read-only against the real runs dir (188 runs, `--all` 0.67 s; 33 of 68 default rows are `<pipeline unavailable>` from deleted test pipelines and `/tmp/*.yaml` runs). Full suite green with an empty HOME.
- **Next:** Phase 7 code review, then merge into `main`.

### Slice 199: task breakdown complete (Phase 5)

- **Tasks:** `user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md` (36 tasks, 402 lines, one file). Six parts: no-behaviour-change refactor (state, batch_report, item_eligibility, loader enum); `sq pipelines list` plus `--list` removal and `sq agents list`; `run_listing.py`; `sq runs list`; `sq runs wait`; docs, CHANGELOG and three follow-up issues (RunState.status enum, run PID, `--json`).
- **Notes:** the design now removes `sq run --list` outright (D8) and moves `sq list` to `sq agents list` (D14); no merge task, per the Phase 5 guide.
- **Next:** PM approval, then Phase 6 on branch `199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list`.

### Slice 934: Pipeline Run Correctness — Implementation Complete (Phase 6)

- **Delivered:** the four fixes, all on the slice branch. #184/#175: `review/profile_resolution.py` is the one review-profile cascade, used by `sq review` and the pipeline review step; the alias check takes each review step's own profile source; unknown review templates fail before the run; `--dry-run` classifies. #188: `merged_slice_branches` makes git the record of a merged slice, for `cf.slices_ready_to_implement` and item resume. #186: a lagging `refs/pull/N/head` reviews the API head (fetched by sha, then the head branch), with `RefAdjustment` data, source-naming errors, and `code_host_logging` so each failure prints once.
- **Choices the design left open:**
  - `SourceFn` became a `Protocol` so `cwd` can be a keyword; `evaluate_each_source(..., *, cwd)`.
  - `_action_profile_source` reads the template through the never-raising `_review_template`; the unknown-template error is collected separately, so a bad template is not also reported as a bad alias.
  - Ancestry timeouts raise `HostCommandTimeoutError` (D10's table) rather than being answered "no" (task 22a's wording); a non-0/1 exit is still answered "no".
  - `code_host_logging` is entered through `ctx.with_resource` in `review pr`, `pr show` and `pr create`. In `review pr` the fetch ran before `_resolve_verbosity`, so verbosity moved up and wrapping "the body after it" would have missed the failures.
  - `RefAdjustment.source` is a phrase (`fetched by sha`, `fetched from refs/heads/main`) and `describe()` is the printed line.
  - `_execute_review` lost its `"sdk"` default; the parameter is required.
- **Existing tests changed:** `tests/cli/test_review_profile.py` called the deleted `_resolve_profile`, so it calls the shared module and patches its config read; dry-run tests that built model-less pipelines now give them a model (a real run would fail them too); the error-table test counts 20 classes.
- **Walkthrough** (full commands and caveats in the slice design):
  - Step 1, `sq run review 931 --model glm-flash-low. --dry-run`: `Error: Pipeline classification failed — unknown model alias 'glm-flash-low.'; did you mean: glm-flash-low, glm-flash, gemini-flash? …`, exit 1.
  - Step 2, `default_review_profile=openrouter` and a literal id (`meta-llama/llama-3.1-8b-instruct`): `sq review slice 934 -v --no-save` printed `Review via openrouter (provider=openai, …)`; `sq run review 934 -v` dispatched through the OpenAI-compatible provider (its small model then failed on the full-diff code review; the failure artifact was deleted) and its verbose line names no profile (#193). With the key unset, both fail: `unknown model alias 'meta-llama/llama-3.1-8b-instruct' If this is a literal model ID, set a profile.` Key restored.
  - Step 3, scratch cf project (created, then removed), A merged `--no-ff` with unchecked tasks, `sq run implement-plan 100 --model sonnet --dry-run`: only `102 Slice B` listed, unflagged, and `slice 101: branch 101-slice.a is merged into main but cf reports not_started; treating it as complete. …`.
  - Step 4, `uv run pytest tests/codehost -k lagging -v`: 5 passed.
  - Not run live: the item-resume half of step 3 (needs model calls; covered by `tests/pipeline/test_item_resume_source.py`) and a real lagging PR (needs GHE).
- **Filed:** #193, the pipeline review step's verbose line does not name the profile (the design expected `profile=openrouter` in both headers).

### Slice 934: Pipeline Run Correctness — Tasks Complete

- **Delivered:** `user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md` (29 tasks, 287 lines): Part A #184/#175 (Tasks 2–12), Part B #188 (13–17), Part C #186 (18–26), Part D docs/walkthrough/close-out (27–29). Test-with ordering; a commit per task or pair.
- **Choices:** Walkthrough step 2 needs a credentialed non-SDK profile, so Task 28 runs only the unset half when none exists and records that in the DEVLOG. No merge task (Phase 7). The design's DEVLOG line mentioning a NullHandler is superseded by D8 (scoped `code_host_logging`).

## 20261006

### Slice 199: design complete (Phase 4)

- **Design:** `user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md` (#185, #187). `sq pipelines list` groups effective pipelines by `PipelineSource`; `sq runs list` (pure `run_listing.py` layer) lists runs `--resume` can act on: paused/failed at their first unfinished step, plus completed batch runs with flagged/not-run items (197). `sq run --list` becomes a deprecated alias.
- **Decisions:** single sources for the resume step (`first_unfinished_step_of`), item resumability (`RESUMABLE_OUTCOMES`), and report paths (`report_json_paths`), shared with item resume; failure cases show explicit row markers plus WARNING. No MCP surface exists in squadron, so parity is CLI + slash command + skill.
- **Next:** Phase 5 task breakdown.

### Slice 934: Pipeline Run Correctness — Design Complete

- **Delivered:** `user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md` (validator PASS).
- **Decisions:** #188: git, not task checkboxes, is the record of a merged slice. The test is ancestor of the target and not on its first-parent chain, which relies on 197's `--no-ff` merges. implement-plan does not check boxes for the agent. #184: one `review/profile_resolution.py` cascade, with `sq review`'s order. The alias check's profile source is per action (`resolve_full(profile_source=)`). #186: fetch the API head by sha, then `refs/heads/<head_ref>`, verifying the sha either way. Errors name each source. `FetchedRange.adjustments` replaces log-only notes. A NullHandler on `squadron.codehost` below `-vv`.
- **Surprises:** #175's guard already shipped in 196 (D13). What remains is the profile source (#184) and `--dry-run`, which skips classification: `sq run review 931 --model glm-flash-low. --dry-run` exits 0 today. #186's double print comes from `logging.lastResort` echoing the adapter's WARNING, since no handler is attached to `squadron.codehost`.

### Release 0.20.1

- **Contents:** 0.20.0 (unpublished: CI failed on two CLI tests that matched Rich output without stripping ANSI codes, which Typer forces on when `GITHUB_ACTIONS` is set) plus that test fix.

### Release 0.20.0

- **Contents:** slice 197 (implementation batch pipeline: `implement-plan`, item resume, project run lock, `report.json`), #183 (branch enter catch-up).

### Slice 197: implementation complete (Phase 6)

- **Delivered:** `implement-plan.yaml`; source `cf.slices_ready_to_implement` with `order_by_dependencies`; `existing: keep` on implement (`KeepCheck.BRANCH_WORK`, `branch_work_count`); catch-up merge on enter (#183) and `restore_target()`; `branch: { plan: }`; `FlagKind`, `ItemDecision`, `ItemOutcome.NOT_RUN`, `StepResult.exhausted`; versioned, atomic, per-item `report.json`; `control_params.py`; `run_lock.py` (`project_run_lock`, `pipeline_mutates`); `item_resume.py` and `sq run --resume … --item/--decision/--instructions` (`cli/commands/run_item.py`); P6, `implement`, P56 and P456 on the shared body with a drift test; loop `accept_decision`.
- **Choices the design left open:**
  - Item resume hands one item to the executor's `each` step through an explicit `ItemRerun` (item, loaded report, decision); the step skips its source and replaces that record. The CLI injects the body runner, so `item_resume.py` doesn't import the CLI.
  - `restore_target(target, cwd)` takes the target rather than reading it.
  - `KeepCheck` (artifact vs branch work) carries keep's meaning to dispatch; `ArtifactKind` gained no member, because its path resolver would silently misroute one.
  - An exhausted loop now carries the reason `loop exhausted at {verdict} (accept: …)`, as D7's example shows.
  - P56 and P456 lost the summary/compact/restore between implement and devlog: the drift test requires the D10 body there.
  - Tasks 9–15 landed as four commits where they shared files (`executor.py`, `sources.py`).
- **Found by the live walkthrough and fixed (each with a test):**
  - `StateManager.list_runs` read every `report.json` in the runs dir as a broken run state and logged a traceback for each.
  - `devlog: auto` inside `each` committed against the whole item record; `implement-plan` now uses `devlog: { mode: auto, slice: "{slice.index}" }`. The pipeline test's fake commit now rejects a non-index slice, as the real one does.
- **Design corrections** (recorded in the slice's walkthrough): `max-revisions=0` is rejected by the loader; cf derives status from task checkboxes, which makes D2's "all tasks checked" row unreachable; an implement with no commits fails on `DiffRangeUnresolvedError`, not `EmptyDiffError` (same outcome).
- **Filed:** #188, a merged slice whose implement agent left its tasks unchecked stays open: dependents can't resume and a batch rerun would reimplement it.
- **Pre-existing, not from this slice:** `tests/metrology/test_audit_cli.py::test_audit_variance_writes_a_floor` hangs at 0% CPU on clean `main` too; it was deselected for full-suite runs.
- **Tests:** 5763 passed / 4 skipped before the walkthrough fixes; ruff and pyright clean.
- **Live walkthrough** (scratch project, plan 100, `--model haiku`, which also sets the review model):
  1. `sq run implement-plan 100 --model haiku -v` with the architecture doc dirty → `item 108 FLAGGED: working tree not clean: …100-arch.tally-core.md`, 109 `not_run`, exit 1 (the halt path). After committing it: 108 then 109 in dependency order; 108 CONCERNS → 2 rounds → flagged at `devlog-4` (`commit needs a slice index`, fixed above); 109 `dependency 108 flagged`.
  2. `sq run --resume <run> --item 108 --decision retry` → `left unmerged slice branch 108-slice.longest-line for main`, `keeps existing work on 108-slice.longest-line (13 commits ahead of main)`, PASS after one round, `merge: slice 108 — Longest Line`, `RESOLVED`, exit 0.
  3. `--item 109 --decision retry` → exit 1, `dependency 108 not complete` (108's tasks unchecked, #188). After checking them off: CONCERNS/FAIL rounds → `review_unresolved` at `revise-code`, exit 1.
  4. `NOTES.md` committed on `main`, `cf set arch 200`, then `--item 109 --decision retry --instructions …` → `cf-op set_arch(100)` before enter, `caught 109-slice.longest-line-in-json up to main (merge --no-ff)`, implement kept (6 ahead), PASS, merged, exit 0; `NOTES.md` not in 109's diff.
  5. A second item resume during step 4 → exit 2, `another squadron run holds the project lock`. `--decision accept` on `not_run` 109 and `step_failed` 108 → exit 2 naming the kind. `--item 108 --decision retry` on the halted run after 108 merged → reconciled to `passed`, exit 0.
  6. Not rerun live: accept on a `review_unresolved` item, a conflicting catch-up, P6 parity — covered by tests (see the slice's walkthrough).

## 20261005

### Release 0.19.0

- **Contents:** slice 196 (branch enter/merge steps, scoped pipeline commits, `tasks-plan` re-review, dependency flagging in batches; delivers #152); unknown model aliases fail before any request; truncated PASS reviews imposed as CONCERNS; narrowed `dispatch_run` resolve catch and shared SDK teardown helper; ai-project-guide v0.20.2 with unused language rules excluded.

### Slice 197: task breakdown complete (Phase 5)

- **Tasks:** `197-tasks.implementation-batch-pipeline-implement-plan.md`, 34 tasks (384 lines, one file), test-with ordering, a commit per task, checkpoints after Parts A, D and G.
  - Order follows the design's Development Approach: catch-up merge, `restore_target()` and `branch: { plan: }` → `existing: keep` on implement → source and ordering → `FlagKind` and `report.json` → `implement-plan` and the single-slice refresh with drift test → reserved params and run lock → item resume → docs and live walkthrough.
  - One work-count helper (`rev-list --no-merges`) serves both the D4 keep check and the D5 catch-up.
  - No merge task; Phase 7 merges.
- **Design review fixes since the design entry below:** per-checkout run lock (D11), atomic per-item `report.json` rewrites, `not_run` records on a halt, `ResumeExit` codes 0–3, a git precondition that returns to the target before item resume, reserved control params (`control_params.py`), post-merge reconcile, and the D12 failure-mode table.
- **Next:** Phase 6 implementation on branch `197-slice.implementation-batch-pipeline-implement-plan` from `main`.

## 20261004

### Slice 197: design complete (Phase 4)

- **Design:** `197-slice.implementation-batch-pipeline-implement-plan.md`.
  - `implement-plan.yaml`: per slice, in dependency order, branch enter → implement (`existing: keep`) → `revise-code` loop (195 thresholds, `on_exhaust: fail`) → devlog → merge.
  - New source `cf.slices_ready_to_implement(plan, accept)`. It returns open, designed slices. Not-ready ones are pre-flagged: no tasks, an unsettled design or tasks review, all tasks checked but still open, or a dependency that isn't designed. Items are topologically ordered, and a cycle fails the run.
  - `existing: keep` on implement skips the dispatch when the slice branch is ahead of the target. That is what makes reruns resume rather than reimplement.
  - `branch enter` merges the target into an existing branch (closes #183). `branch: { plan: }` aligns cf before entering.
  - Structured flags: `FlagKind` StrEnum, `failedStep` and `branch` on records, and `report.json` beside `report.md`.
  - Item resume: `sq run --resume <run_id> --item N --decision retry|accept [--instructions TEXT]`. Instructions ride the existing `override_instructions` plumbing. `accept` is only valid for `review_unresolved`.
  - P6, `implement`, P56 and P456 share the batch body (with `on_exhaust: checkpoint`), and a drift test keeps them identical.
- **Amoeba:** it has no contract for flagged items. Its Runner (120) and Judge (140) aren't started, and its only squadron hook is `sq run --resume <run_id>` for paused runs. The design records squadron's half of the handoff: run ID plus item, a closed `flagKind`, and the CLI decision. Amoeba adopts it when 120 is designed.
- **Next:** Phase 5 task breakdown for 197.

### Slice 196: implementation complete (Phase 6)

- **Delivered:** scoped commits (`pipeline/commit_plan.py`, `commit_message.py`, `loop_commit.py`, `sq _commit`), `branch: {op: enter|merge}` (`pipeline/branch_ops.py`, `git_ops.py`, `steps/branch.py`, `actions/branch.py`, `sq _branch`), the `implement`-needs-enter load rule (`branch_rules.py`), built-in code pipelines reordered to `branch enter → implement → devlog → branch merge`, dependency flags in `each`, `cf.slices_needing_tasks` plus `existing: keep`, and the review-trust fixes #152 (`impose_output_coverage`), #175 (`require_known_model`, classifier takes merged params, resolver backstop) and #179 (`-v` label from the resolver's candidate).
- **Deviations from the design:**
  - `ModelResolver` gained a `profile_source` flag, set from `"profile" in params`; the resolver had no profile knowledge to reuse.
  - The git logic lives in `branch_ops.py`, with `actions/branch.py` and `sq _branch` as thin callers.
  - The slice plan file comes from `get_project().slice_plan`, the same stem `cf list slices` reports.
  - A commit with only supporting files staged reads `docs: update slice N {noun} files` (D2 was silent).
  - `--prompt-only` still doesn't render `loop:` steps (#145), so the loop-round commit render path is `render_loop_round_commit`, ready for the loop renderer.
- **Found by the live walkthrough and fixed:** a re-review archives the previous review under `reviews/archive/` with a timestamped name, and the commit plan left those files out, so the next `branch enter` would have halted on a dirty tree. The plan now matches dirty archive copies of the commit's review stem. Also: a refused merge reported "git refused the merge" because git prints `CONFLICT` on stdout; the reason now carries those lines.
- **Filed:** #183, `branch enter` on an existing slice branch doesn't bring it up to date with the target.
- **Tests:** 5570 passed / 4 skipped; ruff and pyright (src) clean.
- **Live walkthrough** (scratch project, `--model haiku`, dev build via `uv run --project`):
  1. Scoped commit: `P4 103` with a stray `README.md` → `docs: add slice 103 design (review: PASS)`; log line `commit: step design-0 left 3 dirty path(s) out of the commit: README.md, …`. (103 already had a design, so its first run correctly failed the dispatch post-condition; the design was removed and committed first.)
  2. Branch, implement, merge: `P6 107` → `branch enter` on `107-slice.top-words`, `model=haiku` on dispatch and review, code review diff range resolved, `merge: slice 107 — Top Words`, ended on `main`, branch kept. The first attempt on 103 failed with `EmptyDiffError` (already implemented); the devlog step failed once on a frontmatter-less `DEVLOG.md` from my own earlier hand test, and `--from devlog-2` finished the run.
  3. Guards: dirty tree → `working tree not clean: README.md. Commit or remove them, then rerun phase 6 for slice 104; …`; on `scratch-other` → `on scratch-other, expected main or 104-slice.multiple-files-and-totals`. No branch created, tree untouched.
  4. Merge conflict: `P6 106` paused at the FAIL code review (`checkpoint: on-fail` before any merge, as designed), so the conflict came from `sq _branch merge --slice 106` after committing a conflicting `cli.py` edit: `merge failed: …(conflicted: src/tally/cli.py); slice branch 106-slice.json-output left unmerged`; `main` clean, no `MERGE_HEAD`, branch not an ancestor of `main`.
  5. Dependency flags: `tasks-plan 100` with 105 depending on 104 and 104's design review deleted → `item 104 FLAGGED: no design review found`, `item 105 FLAGGED: dependency 104 flagged`; 106 ran.
  6. Re-review gap: 107 (tasks file, no tasks review) was selected; `dispatch: step tasks-1 keeps existing artifact […107-tasks.top-words.md]`; committed `review: add slice 107 tasks review (CONCERNS)`; tree clean after the run.
  7. Unknown alias: `run review 103 --model haiku.`, `run P4 103 -p review-model=haiku.` and `review slice 103 --model haiku.` all exit 1 with `unknown model alias 'haiku.'; did you mean: haiku? If this is a literal model ID, set a profile.`; no review file changed.
  8. Truncated PASS: not run live (needs a global `models.toml` alias); the unit tests are the gate.
  9. Prompt-only: `P6 106` renders `sq _branch enter --slice 106`, `sq _commit --subject code --slice 106 --template code`, `sq _commit --subject devlog --slice 106`, `sq _branch merge --slice 106`. Running them by hand gave `on 106-slice.json-output (created from main)`, `feat: implement slice 106`, `docs: add DEVLOG entry for slice 106` (stray file untouched), and `merged … into main`; a second merge reported `already`.
- **Next:** code review of the slice (Phase 6 gate), then Phase 7 merge to `main`; then slice 197.

### Slice 196: task breakdown complete (Phase 5)

- **Tasks:** `196-tasks.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md`, 38 tasks (380 lines, one file), test-with ordering, a commit after each part.
  - Order: #175/#179 → #152 → scoped commits → branch steps → dependency flags → tasks re-review → docs and live walkthrough.
  - `pipeline/git_ops.py` is built at the start of the scoped-commit part, not the branch part: the commit action needs its error classes and strict target reader (D6 timeout, D8 target guard).
  - No merge task; Phase 7 merges.
- **Next:** Phase 6 implementation on branch `196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches` from `main`.

### Slice 196: design complete (Phase 4)

- **Design:** `196-slice.pipeline-branch-steps-scoped-commits-and-dependency-aware-batches.md`.
  - Scoped commits come from one `build_commit_plan()` that both the SDK executor and prompt-only (`sq _commit`) call. Messages are derived from the staged set (`docs:` / `review:` / `feat:`).
  - New `branch: {op: enter|merge}` step type. It reads the integration target strictly, refuses a dirty tree or a foreign branch, aborts a conflicting merge back to a clean target, and accepts an already-merged branch. P6, implement, P456 and P56 gain the steps.
  - `each` flags dependents of flagged items, with dependencies read from design frontmatter.
  - `tasks-plan` re-selects slices whose tasks review is missing or below threshold (source renamed `cf.slices_needing_tasks`, phase step `existing: keep`).
  - #152: a budget-truncated PASS is imposed to CONCERNS.
  - #175: unknown aliases fail in the pre-run classifier, with close matches, and in the resolver as a backstop.
  - #179: the `-v` label comes from the classifier's cascade candidate.
- **Effort:** raised to 4/5. #152 is closed on GitHub without a fix; 196 delivers it.
- **Next:** Phase 5 task breakdown for 196.

### Release 0.18.4

- **Contents:** pipeline fixes found running every built-in pipeline live against a scratch project. Classification no longer demands a model for model-less `compact` or `summary: restore` steps, and `SummaryStepType.expand` keeps `restore`. `implement.yaml` wires its `model` param. `sq run` exits 1 on FAILED. Judge reviews take their verdict only from their score (`score_decides_verdict`). judge-cycle and findings-addressed-cycle review before revising, and their loop max is the `max-revisions` param. Built-in `max-revisions` defaults to 2. P2 is initiative-scoped (`plan`, `resolve_arch_file`, arch post-condition). P0 removed. Only final summaries copy to the clipboard; interim ones in P456 and P56 write to a file only. New `tests/pipeline/test_builtin_pipelines.py` loads, validates and classifies every built-in pipeline without `--model`. Code-implementing pipelines still fail at the code review with no slice branch, which slice 196(b) fixes. Filed #179 (in 196 scope) and #180 (slow metrology tests).

## 20261003

### Release 0.18.3

- **Contents:** slice 928 (Codex parity for skill packs and provider access; fixes #125, #127): `sq skills install|uninstall|list --ide codex [--local]`, per-target doctor rows, auto-written `~/.codex/rules/squadron.rules` for `sq review|run|pr|metrology|auth|skills`, sandbox-rejection hint in the sq-review/sq-run/sq-pr Codex skills, `sq models list` doc fix, README restructure. Patch per PM (improves existing commands).

### Slice 928: Codex Parity for Skill Packs and Provider Access — Complete

- **Skill packs:** `sq skills install|uninstall|list` take `--ide {claude|agents|codex|openai}` and `--local`. New `skills/pack_layouts.py` (`PACK_LAYOUTS`) is the one place that knows where a pack lands per target; install, `skills list` and doctor all read it. A Codex install requires the pack to ship `agents/<prefix>-<name>/SKILL.md` (or `sq-<dispatch_file>/`), validated before anything is written (all problems listed). Receipts are `<pack>[-agents][-local].toml`; pre-928 receipts still read. `remove_receipt_files` is shared with `uninstall-commands`. The bundled analysis pack's agents skills moved to `commands/analysis/agents/`. Doctor shows `<pack> (codex)` rows where Codex is on PATH, with "pack ships no Codex content" (no fix hint) when the source has no `agents/`; github sources never clone in doctor.
- **Codex sandbox rule:** design said document it for the user to add; reversed in implementation (PM: users should never write rule files). `sq install-commands --ide codex` writes `~/.codex/rules/squadron.rules` whole on every install; machine-scope uninstall deletes it; `default.rules` is never touched. An interim version on this branch (sq-pipelines agent) appended to `default.rules`; replaced because ownership of appended lines was unknowable. Rule allows `sq review|run|pr|metrology|auth|skills`.
- **Probe (`codex sandbox`, real terminal):** `--version`, `models list`, `auth status` ran. `pr show` → `HostUnreachableError`. `review` → blocked writing `~/.codex` state. `run --prompt-only` → `PermissionError` on `~/.config/squadron/runs` (filesystem, not network). `metrology audit run` → failed, no audit written. `auth login` → blocked writing `~/.codex`. `skills install` (github) not re-probed; included because it clones. Agent-management commands (experimental) excluded.
- **Live check:** `codex execpolicy check` allows each listed subcommand, none for `models list`. In a Codex session `$sq-pr show 119` ran with no prompt; with the rule file moved away it was blocked (at `git fetch` writing `.git/FETCH_HEAD`) and the skill's D12 hint named Codex's sandbox and the install command.
- **Also:** `sq model list` → `sq models list` (6 sites); README gained a skill-packs section (since folded into the README restructure); 340-arch amended.
- **Tests:** 5303 passed / 4 skipped; ruff + pyright clean. Three metrology tests sleep through a 120s default cooldown each (~6 of the suite's ~9.5 min) — pre-existing, not addressed.

### Release 0.18.2

- **Contents:** model alias update — `astra`/`sol`/`luna` on `openai-oauth` (API-equivalent pricing kept for comparison), `luna-r` and `ling-flash` on OpenRouter; `codex-agent`, `codex-spark`, `gpt54-nano` removed with tests and docs updated. `sq auth` reference added to docs/COMMANDS.md.

### Release 0.18.1

- **Contents:** everything in 0.18.0, plus `fix(auth)`: `sq auth` built its Rich console at import, so it captured the hostile-env job's `FORCE_COLOR=1` before the suite scrubbed it, and three `tests/cli/test_auth.py` assertions saw ANSI codes. The v0.18.0 tag run failed in `hermetic`, so 0.18.0 never published. The console is now built per call, like every other command; `scripts/test-hostile-env` passes locally.

### Release 0.18.0

- **Contents:** slice 129 (Codex provider on the official `openai-codex` SDK as a core dependency; `sq auth login`/`logout` for `openai-oauth` with browser and device-code flows; Codex rows in `sq doctor` and `sq setup`; Codex effort and token usage, #171), split-review verdict fold fix (#176), and review fixes: Rich markup in finding text, fenced code in finding bodies, `project-documents/` docs-root note, named textless transport errors, excluded-directory walk pruning, tool-error argument logging.

## 20261002

### Slice 129: Codex SDK Becomes a Core Dependency (code review pending)

- **Why:** the `codex` extra was fragile. `uv tool install --upgrade squadron-ai` (the usual upgrade command) replaces the saved install spec and silently uninstalls the SDK; only `uv tool upgrade` keeps an extra (both verified, uv 0.11.2). The original design also said `pip install`, which lands outside a `uv tool` environment.
- **Change:** `openai-codex>=0.159.3,<1` moved to core dependencies. Removed: the `codex` extra, `providers/codex/runtime.py` (install hint, bundled/PATH resolution, `CodexExtraMissingError`), the `ExtraRequirement` protocol and `loader.missing_extra_hint()`, the `sq models list` marker, the install hint in `sq auth status`, the CI extras leg, and the pyright exclude for `agent.py`/`login.py`, which now type-check against the real SDK. The doctor row reports SDK version and login state; the `sq setup` step is now "Sign in to Codex".
- **Cost:** the bundled runtime adds 302 MB (the Claude SDK already bundles 223 MB); wheels cover macOS, Linux glibc/musl and Windows on x86 and ARM. pydantic floor rises to 2.12 via the SDK.
- **Tests:** 5226 passed / 4 skipped; `test_sdk_surface.py` now always runs. ruff + pyright clean.

## 20261001

### Slice 129: Codex Provider on the Official SDK — Implementation Complete (code review pending)

- Branch `129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login`, 29 commits `ba0b689a`…`9a9478f0` plus closeout docs. Not merged: `cf check` requires the slice code review, which diffs the branch against `main`, so the merge waits for it. Closes #171.
- **Part 0:** the real-runtime check showed the Codex runtime ignores `OPENAI_API_KEY` (401), so `OAuthFileStrategy` dropped the key fallback; the setup hint points to `sq auth login openai-oauth` or the `openai` profile.
- **Part A:** `codex = ["openai-codex>=0.159.3,<1"]` extra (lock resolves 0.160.0; `packaging` 26.0→26.3 is required by it). `providers/codex/runtime.py` is the single source of the install hint and resolves the bundled binary (`codex_cli_bin`) before PATH; `CodexExtraMissingError` distinguishes package-missing from no-binary. The agent uses `thread.turn()` + `handle.run()` (same SDK path as `thread.run`) so a turn timeout can `interrupt()`; startup/transport/busy/RPC errors map to `ProviderError`, a closed transport resets the client; effort maps by value to `ReasoningEffort`; `TurnResult.usage.last` → `TokenUsage` on `metadata["usage"]`/`["turns"]`. Three `codex.*_timeout_s` config keys; `account_timeout_s` also bounds the post-timeout interrupt and login cancel.
- **Part B:** `ExtraRequirement` protocol; `providers/loader.missing_extra_hint()` serves doctor, `sq models list` (marker in the Profile cell) and `sq auth status`. Doctor `codex provider` row (WARN rows show under `-v`), `sq setup` step, README/QUICKSTART rewritten.
- **Part C:** `InteractiveLogin` protocol (`login(device_code, timeout_s, notify)` — `timeout_s` because ruff ASYNC109 rejects `timeout`), `providers/codex/login.py` (pyright-excluded beside `agent.py`), `sq auth login --device-code --timeout`, `sq auth logout`, account in `sq auth status`.
- **Tests:** default env 5255 passed / 5 skipped (incl. `test_sdk_surface.py`); codex env 5260 passed / 4 skipped (`uv sync --dev --extra codex`) with the drift test running. ruff + pyright clean. CI gained a `test` matrix leg (3.12, `extras: codex`) that fails on a broken install before pytest; its first GitHub run is at the next push.
- **Surprises:** Rich parsed `squadron-ai[codex]` as a markup tag and dropped it — fixed in doctor, setup, auth and review error output; the other ~76 unescaped exception prints are #177. Walkthrough step 1 (`sq review … --model codex-agent` without the extra) writes a provider-failure artifact over the slice's committed review (prior one archived) — existing `ProviderError` behavior; restore with `git checkout`.
- **Pending (PM):** walkthrough steps 3, 4, 6, 8 — browser login, device-code login, a real `codex-agent` review with `OPENAI_API_KEY` unset, logout. `sq auth status` with the real SDK was verified live (account and plan shown).

### Slice 129: Task Breakdown Complete

- **Tasks:** `project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md` — 27 tasks, Part 0 (API-key fallback check) then A/B/C, test-with ordering, commit per group.
- **Gate:** Task 1 needs a real `openai-codex` runtime plus an `OPENAI_API_KEY`; if the agent cannot arrange it, it stops and asks the PM. Browser/device-code/real-review smoke tests are PM-run, listed outside the checklist.
- **Pyright:** `login.py` joins `agent.py` in the pyright exclude list (Task 20); `runtime.py` stays type-checked.

### Slice 129: Codex Provider on the Official SDK — Design Complete

- **Design:** `project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md`. Validator PASS. Slice-plan entry already carried the `(129)` index.
- **SDK surface checked against `openai-codex` 0.159.3** (installed in a throwaway venv, not the project): `login_chatgpt`/`login_chatgpt_device_code` handles, `account()` → `ChatgptAccount(email, plan_type)`, `thread.run(effort=ReasoningEffort)`, `TurnResult.usage.last`, bundled binary via `codex_cli_bin`.
- **Decisions:** `InteractiveLogin` as a separate runtime-checkable Protocol (no `AuthStrategy` change); one `CodexRuntime` resolver shared by agent/provider/doctor; `Effort` → `ReasoningEffort` by value, no table; sandbox validated via `Sandbox` enum.
- **Open for PM:** upper version cap on `openai-codex` (0.x SDK); whether `OAuthFileStrategy`'s `OPENAI_API_KEY` fallback works with the app-server (unverified, to be checked during implementation).