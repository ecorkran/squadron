---
docType: devlog
project: squadron
dateCreated: 20260218
dateUpdated: 20261119
---

# Development Log

A lightweight, append-only record of development activity. Newest entries first.

Older entries: project-documents/user/archive/devlog/ (one file per quarter).

## 20261119

### Slice 434: Recipe Reviews in Pipelines — Tasks Complete (Phase 5)

- Tasks: `project-documents/user/tasks/434-tasks.recipe-reviews-in-pipelines.md` (23 tasks, 256 lines, effort 5/5). Not committed; no review run.
- Design gaps found against the code, written into the design by Task 1: eight benchmark recipe files stay (not six); `RECIPES_DIR` moves to `benchmark/recall/recipe_dirs.py`; the moved stage-config function takes the template hash (today's `live_stage_config` hardcodes `code`); `ReviewResult.recipe: RecipeReviewInfo` carries the recipe name, completeness and stage section to persistence; reviewer and "not combed" marks are a line in each finding's description; the save→record→abort flow lives once in `recipes/recipe_review.py`; `report --set` becomes optional with `--real-work`.
- The package is `recipes/` (design), not `review/recipe/` as the 20261118 entry said; recipes are searched project → built-in only.
- Task 23 runs live walkthrough steps 4, 5, 7; it needs `OPENROUTER_API_KEY` and Codex credentials.

## 20261118

### Slice 434: Recipe Reviews in Pipelines — Design Complete (Phase 4)

- Design: `project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md`; `cf validate design` passes. Not committed; no review run.
- A review model name is classified once as alias or recipe (`sq review`, pipeline pre-run check, review action). Recipes are searched project → user → built-in; the recipe model, comb call and decisions parser move from `benchmark/recall/` to `review/recipe/`.
- Stages run one at a time (concurrency is #372). Combs run in process on the real tree and need a diff. Pool recipes, judge templates and an explicit profile are refused.
- Verdict is `verdict_from_findings` over kept findings. An incomplete recipe (a failed reviewer or comb) cannot pass: nothing kept gives UNKNOWN and the review fails; kept CONCERN/FAIL findings give their verdict and the loop goes on.
- One `recipe_review` metrology record per review, from the CLI and the pipeline; `sq benchmark recall report --real-work` reads them.
- Shipped `review-model` defaults do not change; that stays with #369.
- Next: Phase 5 task breakdown.

### Release 0.24.34

- **Contents:** slice 430 `sq benchmark recall` (real-bug code-review recall: case files, hand-run import, recipe runs with cost bound and caps, labels, report), plus the gate-review fixes on it (non-finite cost limits refused, empty combs neither capped nor charged, UNKNOWN-verdict reviews recorded as config failures); `sol-r` alias (sol through OpenRouter); `/sq:monitor` no longer saves a session summary for paused or failed runs. Issues filed: #370, #371.


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: FAIL)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: FAIL
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: FAIL
- revise-code:commit-5: PASS

### Slice 430: Real-Bug Review Recall — Complete

- **Commits:** 04f4cff8 import; 30b05fc2 hit rule, scoring, report; 7af17ed2 comb template and `_stage`; 7c12f30e stage identity, runner, leak scan; 13f4932e run plan and loop; c5531b7a `run`; d3308861 `label`; 6ae85bbf docs; plus the closing commit (walkthrough, `--cwd` fix, status).
- **Delivered:** `sq benchmark recall` with `cases add/list`, `import`, `run`, `label`, `report` and the hidden `_stage`. The import loads 696 reviews, 480 combs and 51 run records, and the four passes plus overrides as 56 label records. On those records the report reproduces RESULTS.md section 1 (16/12/7/4 of 42; 13 of 39 without u103) and section 5 known kept (opus-high 14, luna-r 14, sol 10, sonnet-high 8). All 86 imported HIT labels pass the location gate, so no case needed `extra_locations`. Tests: 1,635 pass in `tests/benchmark/recall tests/benchmark/test_config_keys.py tests/cli`; ruff and pyright clean.
- **Walkthrough on the real store (steps 1–6):** four case sets at v1, import done, sections 1 and 4 reproduced, live `luna` and `luna-r` runs on the fixture (`no_leak_detected` and `confined`), plan-cap stop with exit 2, resume, `--retry-harness`, labelling. Real store now holds the 17 cases, the import and the `fixture` set's live entries, with a `person:claude-walkthrough` label on two fixture findings.
- **Decisions and surprises (all in the design):**
  - Only CONCERN/FAIL findings are scored. The design example's 7.8 findings/run is that count.
  - A live `effort_sent` is read from the output's `effort` field.
  - Codex `tools_given: null` imports as `unknown`.
  - `_stage` takes `--model` and `--diff`.
  - Plan-billed means the `openai-oauth` provider.
  - Found in step 5: the user's `config.toml` `cwd` key, seeded into the scrubbed home, sent `sq review code` outside the sandbox. The code kind now passes `--cwd .`.
- **For step 7 (PM):** it needs `--call-cost` (no live cost observed yet) as well as `--max-plan-calls 14`. Until a release ships the recall group, run it via `uv run sq` from the checkout.

## 20261117

### Release 0.24.33

- **Contents:** the 0.24.32 changes. 0.24.32's CI failed on 8 setup errors in `test_slice_pipeline_end_to_end.py`: its module-scoped `world` fixture ran before the function-scoped hermetic git config and had no git identity on the runner. The fixture now pins `GIT_CONFIG_GLOBAL` itself.

### Release 0.24.32

- **Contents:** benchmark slice cases (`sq benchmark slice-cases build`, slice-case `run`, pairwise `judge`, report tables); pipeline defaults from the review benchmark (haiku-xhigh review, fable-medium designs, opus-high architecture/tasks); alias set trimmed to a default plus one effort variant, with hy4, hy4-flash, minimax31-flash and terra added; review recall RESULTS sections 16–20; fixes #335 (grade review sees toml/yaml edits) and #330 (Codex fix step can write).

## 20261116

### Slice 430: Real-Bug Review Recall — Tasks Complete

- **Delivered:** `project-documents/user/tasks/430-tasks.real-bug-review-recall.md` (31 tasks, 245 lines, 16 commit markers). Order: records and store, case files and `cases add`, decisions parser, recipes, import, hit rule/scoring/report with the section 1 and 5 reproduction tests, then `_stage`, stage runner, `run`, `label`, docs.
- **Design gaps for Task 1 to write into the design:** recall payload models go in `metrology/recall_*_models.py` (`MetrologyRecord` never imports `benchmark/`); the lock is `BenchmarkLock.acquire(..., "recall", ...)`, not `bench_lock`; timeout refusal uses `check_review_timeout`; a recipe matches imported entries by alias and live entries by `entry_key`; overrides live in `user/reference/review-recall-overrides.yaml`; `commands/sq/benchmark.md` gets the recall subcommands; stale "PM to confirm" text removed.
- **Next:** PM approval, then Phase 6 on branch `430-slice.real-bug-review-recall`.

## 20261115

### Slice 430: Real-Bug Review Recall — Design Complete

- **Delivered:** `project-documents/user/slices/430-slice.real-bug-review-recall.md` (`cf validate design` PASS). `sq benchmark recall` group: `cases add/list`, `import`, `run`, `grade`, `label`, `report`. Four new store record types (`recall_case`, `recall_case_set`, `recall_stage`, `recall_label`).
- **Key decisions:** cases are committed YAML files, with bug files defaulting to the proof commit's non-test files. Combs run on each reviewer's output, never on a union, so comb records are reused across recipes. Fan-out is scored as a union and a pool as the member mean. Hit rule is a file-level location gate plus stored labels (person > import > agent); an unlabeled candidate is listed and not counted, and no model grades hits. Agent grading of real share is a separate `grade` command. The code-review input assembly moves out of the CLI so recall reviews use the `sq review code` path with tools. `HistoryFreeSandbox` gains `history_from` (head plus ancestry back to base). Bound/cap/exit 2/resume reuse 425's `ReviewBudget`; `--jobs` adds bounded concurrency. The first live recipe runs on the 14 non-squadron cases.
- **Checked while designing:** the committed grade files reproduce RESULTS.md section 1 exactly (bug-hits 16/12/7/4 of 42, 13/9/4/1 without u103, runs with a hit 14/12/7/4) and section 5 known-kept (opus-high 14, luna-r 14, sol 10, sonnet-high 8). 307 B1's graded hits cite `cutover_304_first_purchase.py`, which the case text does not list. That is why bug files default to the fix commit's files.
- **PM decisions (20261116):** D7 approved (recall sandbox holds head plus ancestry back to base; architecture amended). D11 approved (first live recipe is committed with the slice and run by the PM after it; plan criterion rewritten). D13 approved (`git show --name-only` on four squadron commits is outside the no-squadron-history rule). The plan's wrong "sections 10–13" citation was corrected to RESULTS.md section 5.



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

### Slice 426: Slice Cases — complete

- **Delivered:** `sq benchmark slice-cases build` (discovery over 403's `slice_ranges`, fork task text, two-sandbox qualification, case set, yield rows), `SliceCaseRunner` on 424's seam (cf registration in the scrubbed home, producer-only `P6`), `sq benchmark judge` (normalized diffs, sample-matched pairs, forfeits, over-size rule, bound, per-call cap, lock, resume) and the report's per-kind tables with a pairwise section (Bradley-Terry strengths, paired interval per config pair, counts). Extractions: `judge_pair`, `CfRegistration`, public artifact patterns; two config keys (`benchmark.judge_model`, `benchmark.judge_max_prompt_chars`); `/sq:benchmark` mirrors.
- **PM decision 20261115:** no task runs against squadron's history or calls a model. One suite run at slice 400's fork exceeded 400 s, a candidate needs three at its tip and 9 of the record's 15 slices pass the pre-sandbox checks, so the live build and replay were deleted and replaced by fixture end-to-end tests (Tasks 23, 26, 41). Task 23's earlier probe wrote real records to the user's store (`multiple_landings` for 172 and 305, `harness_error` for 400; a rerun overwrites it). Discovery over squadron's 15 recorded slices sorted them: 3 `multiple_landings` (172, 305, 940), 1 `branch_contains_merges` (422), 1 `no_tasks_at_fork` (402), 9 reach the sandboxes (400, 401, 403, 420, 421, 423, 424, 425, 946, 947); their case counts are not known.
- **End-to-end tests, fixture project `tests/benchmark/fixtures/slice_project/`** (uv project, 3 tests; history built by `slice_project_history`: a code slice 511 and a docs-only slice 512, both merge-landed). Real sandboxes, git, uv, pytest and, for replays, cf registration under the scrubbed home; no model is called.
  - Task 23, `test_slice_build_end_to_end.py` (5 tests): slice 511 qualifies (3 regression nodes, `start_sha` the fork, `reference_sha` the tip, task text = design then task file as of the fork), 512 is `no_code_change`, case set v1, a second build runs no suite and keeps v1, the yield row counts 2 candidates / 1 qualified / 1 `no_code_change`.
  - Task 26, `test_slice_pipeline_end_to_end.py` (replays): three configs through the real `SliceCaseRunner`; only the `sq run P6 511 --producer-only` call is scripted. Two commit (one the reference change, one breaking `test_sub`) with diffs against the fork, one commits nothing (`no_commit`, config absence); `cf project list` names are identical before and after. The fixture needed a `500-arch.*` file because `cf set arch 500` resolves against it; the registry check compares names only because other sessions move the slice column while the test runs. The leak scan reports a transcript with no tool calls as unavailable (harness absence), so the scripted transcript holds one harmless command.
  - Task 41, same file (grade, judge, report): reference `pass`, good replay pass, breaking replay fail (1 regression, `tests/test_calc.py::test_sub`); 6 pairs, the 3 with the silent replay are forfeits with no dispatcher call, the other 3 are judged (6 calls); the report has the `slice cases` table, the pairwise section, the reference line marked not ranked, `opus vs sol d +1.00 too few cases (1)` and the count line. Only the grading review and the judge's model are scripted.
  - Observation, not changed: a config with no graded replay has no table label, so the pairwise section labels it with its model name (`m-astra`) beside the other configs' aliases.
- **Task 10 spike:** a `BenchmarkSandbox` at slice 403's fork, the scrubbed home with `cf` and `node` linked, `CfRegistration(...).register(...)`, then under that environment: `cf set slice 403`, `cf set phase 6`, `cf build --json`, `sq run P6 403 --producer-only --dry-run`, `cf project list`. Every command exit 0 with `HOME` redirected; `cf init` wrote its registry to `<home>/.config/context-forge/projects.json`; the dry run listed `implement-1`. Corrections found: `CF_TOOLS` is `("cf", "node")` (cf is a node script), and `--producer-only` refuses a branch that does not parse as `{index}-slice.{name}`, so a detached tree gets `{index}-slice.` + `SLICE_BRANCH_SUFFIX` + the sandbox id; the extra tools are linked into an existing home. Leak-scan coverage: 424's protected roots (real home, checkout, installed package, uv cache) cover every real path of `cf`, `node` and the cf registry directory (all under the real home), and the scan over all five commands' output was clean. A `cf` installed outside the user's home would not be covered.
- **Defects and gaps found by implementing** (details in the design's last section): cf needs `node`; `--producer-only` needs a slice-named branch; `P6` has no frozen text to classify against; a slice case needs its leak-rule owner from the checkout's remote; the judge's cap is per call. The real 424 seam differs from the task text in names (`run`, not `invoke`; `requalify` returns a union; `AbsenceClass` is `harness`/`config`).
- **Gates:** `uv run ruff format --check .`, `ruff check .`, `pyright` clean. Full suite by directory: all pass except the two tests that fail on main before this slice (#336: the report golden's grader digest, `test_grade_ids [bumped grader version]`) and `tests/cli/test_review_pr.py::test_pr_review_no_longer_reports_persistence_unavailable`, which failed in one chunk and passes alone. Files over 300 lines added or changed by the slice: none new (`yield_report.py` was split into `yield_measured.py`; `keys.py`, `planning_docs.py` and `benchmark_grade.py` were over before; `tests/benchmark/slice_repos.py` is a test helper at 369).
- **Next:** 427.

### Release 0.24.31

- **Contents:** (0.24.29 and 0.24.30 were tagged but never published: CI's repo-wide `ruff check` failed on the archived review-recall scripts, now excluded, then two benchmark help tests failed under CI's forced colour, now read from the command.) slice 425 (grading and paired report) with its round-4 review fixes; slice 424; #325 (SDK API-error replies), #142 (review slice/tasks save by file name), #192 and its liveness follow-up (`sq runs list --json`), #320 (`/sq:monitor`).


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
- revise-code:review-1: PASS (verdict: FAIL)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: FAIL)
- revise-code:commit-5: PASS

### Slice 425: Grading and Paired Report — Complete

- **Delivered:** `sq benchmark grade` (planned bound, run cap with exit 2, lock, resume, `--retry-harness`, `--keep`, `--review-model`), `sq benchmark report [--json]` and the `/sq:benchmark` grade and report mirrors; `PythonGradingAdapter` (hidden-test injection as sibling modules, tool-config restoration by section, dependency-change reinstall, test-edit and suppression counts); the fixed grading review with its noise floor; the paired bootstrap and measured sample-count estimate (`paired_stats.py`); the measured line in `sq benchmark yield`. Branch `425-slice.grading-and-paired-report`; `ContentSidecars`, `measure_snapshot` and `is_within_floor(float)` were generalized on the way (D11–D13).
- **Task 31 live result:** reference of `2101361510f4` (`case-85c975f100d51ec1`) passed: hidden 1/1, regressions 0, `reinstalled` false, injected `tests/providers/test_sqhidden_test_capabilities.py`. Two live failures were fixed with tests (the failed-reference detail did not name ids; the baseline node ids must keep collection order, not sorted).
- **Walkthrough (one case; squadron qualified 1 of 95):** 10 replay records over two benchmarks (opus/sol k=3; opus-high/opus-medium k=2, three of its replays rerun after leaks). Reference `pass`; every committed, non-leaked opus replay `pass`; `sol` made no commit (#330). The report printed all sections with n and k, the unmeasured-reviewer flag and `too few cases (1)`; the cap stopped after one review with exit 2 and resumed over the stored grades; the kept tree held the hidden test beside the producer's and no `pyproject.toml` change. Full steps in the slice design.
- **Measured estimate:** not producible: five included cases are needed and one exists. Its live check is #333; yield shows no measured line until then.
- **Defects found by the walkthrough, fixed with tests:** (1) the SDK sent the Claude Code preset even with `no_tools`, so models wrote tool calls as text and the grading review returned nothing (`review_failed`, most reviews); (2) the `code` template's "confirm the working directory" still led haiku and sonnet to write tool markup; a `NO_TOOLS_NOTICE` is appended to no-tools reviews, after which 4 of 4 haiku-xhigh reviews succeeded (about half before). Both also change `sq review --no-tools` (CHANGELOG); (3) a failed grading review logged no cause: it now logs the first 1500 characters of the model's output; (4) `yield_report._needed_at` fell back silently to the largest projected k; it raises now.
- **Surprises:** `ruff format` run on the whole repository rewrites ten unrelated scripts under `project-documents/user/reference/review-recall-results/`; format `src` and `tests` only. The first 600 s foreground limit moves long grades to the background; a grade is minutes per subject (sandbox build and install). Squadron's own history is a poor case source: opus replays leaked the checkout in 4 of 10 runs (harness absence, rerun with `sq benchmark run --retry-harness`). `.venv is out of sync with uv.lock` in a sandbox's snapshot environment check leaves the type total "not measured" (400's check).
- **Gates:** `uv run ruff format --check src tests`, `ruff check`, `pyright` clean; full suite 10835 passed, 6 skipped. `grade_models.py` (308), `python_injection.py` (302) and `benchmark_grade.py` (313) are slightly over ~300 lines.
- **Code review (CONCERNS) answered:** a failed grading review is charged to the run cap (its reported cost, else the per-review figure); a git timeout reading a tree is `reference_unreadable`; the review's rules come from the start commit, not the producer's edit; regression and producer-new counts treat an unreported id as `not_run`; the three "minimum 2" constants collapsed onto `REVIEW_FLOOR_RUNS_MINIMUM`, `MIN_SAMPLES_FOR_VARIANCE` and a new `MIN_COMPARED_CONFIGS` (one was compared against the wrong quantity); the no-tools notice is built inside `assemble_system_prompt`; a producer-deleted `pyproject.toml` stays deleted instead of becoming a partial file. LF endings of restored files deferred to #334.
- **Code review round 2 (CONCERNS) answered:** the report reads this benchmark's own estimate (`estimate_for`), not the newest one for the case set; a sample recorded twice for one config is an error, not an overwrite; a failed review's spend is on the grade record as well as the budget; non-UTF-8 bytes in a producer's `pyproject.toml` are `producer_env_unresolvable` and in a producer's test file or conftest record no clash; the `type: ignore[no-untyped-def]` comments on this slice's test helpers are replaced by annotations; `read_review_floor_runs` (unused) removed; one `_profile_and_effort` formats a config name for the report and the yield line; estimate pairs with no report row are named readably; `GRADER_VERSION` moved to `grade_models` so the planner no longer imports the executor; `BenchmarkSandbox.reinstall()` returns nothing (nothing used the identity; the grade records `reinstalled`).
- **Next:** 426 (slice cases), which registers its case-kind table in `report_tables.py`; 427 changes `review_flag` alone.

## 20261114


**p6: devlog-4**
- branch-0:branch-0: PASS
- implement-1:cf-op-0: PASS
- implement-1:cf-op-1: PASS
- implement-1:cf-op-2: PASS
- implement-1:cf-op-3: PASS
- implement-1:dispatch-4: PASS
- implement-1:review-5: PASS (verdict: FAIL)
- implement-1:checkpoint-6: PASS
- implement-1:commit-7: PASS
- close-out:dispatch-0: PASS
- revise-code:dispatch-0: PASS
- revise-code:review-1: PASS (verdict: CONCERNS)
- revise-code:commit-2: PASS
- revise-code:dispatch-3: PASS
- revise-code:review-4: PASS (verdict: CONCERNS)
- revise-code:commit-5: PASS

### Slice 424: Producer-Only Replay Runner — Complete

- **Delivered:** `sq run <pipeline> <slice> --producer-only` (also `--prompt-only`, and `/sq:run`); the `ProducerStep` capability on the phase and fix steps; SDK in-dispatch cost enforcement (`max_budget_usd`, `error_max_budget_usd` → `cost_cap`); `BenchmarkRun` / `ImplementationReplay` records with content-addressed diff sidecars; per-profile `TranscriptSource`s (Claude Code, Codex) and the leak scan; `FixCaseRunner`, `replay_one`, the benchmark runner (lock, bound, caps, resume, interruption sweep, `--retry-harness`); `sq benchmark run` and `sq benchmark replay-show`, mirrored in `/sq:benchmark`. Nothing here grades (425).
- **Branch** `424-slice.producer-only-replay-runner`, commits `c53814c5` … `f70d0d4c`, closing commit after them.
- **Issues:** #329 (in-dispatch cost enforcement for Codex and OpenAI-compatible runs, filed in Task 2); #330 (the `fix` step's dispatch is not write-required, so a Codex `fix` run is read-only); #331 (`--keep` sandboxes are swept by the next benchmark command).
- **Transcript spike answers:** see the Task 13 entry below: both runtimes write their transcript into the scrubbed home; layouts and entry types are recorded there and in `tests/benchmark/fixtures/transcripts/`. The scan does not use `turns`; zero extracted tool calls is `scan_unavailable`.
- **Verification (real runs, squadron's own `fix-squadron` set):** producer-only on a scratch slice: one implementation commit, run state `cf-op ×4, dispatch, commit`, no review, no merge; the three refusals; both cap refusals; `opus` replay `committed` ($0.50, 4-file diff, `no_leak_detected`); run cap `partial` exit 2 then resume to `complete`; a SIGKILLed run reported `interrupted`, swept its orphaned sandbox and resumed; the kept transcript's distinct `tool_use` count equals the record's `tool calls seen`. Gates: pyright 0 errors, 10351+ tests pass; `ruff format --check` and `ruff check` fail only in `project-documents/user/reference/review-recall-results/` (already on `main`).
- **Surprises:**
  - The sandbox tree is a detached HEAD and `fix` refuses one, so every real replay ended `frozen_text_mismatch` until `BenchmarkSandbox.checkout_branch` put the tree on a branch at the start commit (the tree stays history-free). The unit tests with doubles could not see it.
  - The harness runs the `sq` on `PATH`; a released `sq` without `--producer-only` makes every replay `no_run_state`. The record's detail names the missing option.
  - `unpriced_replays` was carried across invocations, so `--retry-harness` left deleted records counted; it is now counted from the stored records.
  - The global `ruff` on PATH (0.17) formats differently from the project's pinned 0.15; use `uv run ruff`.
  - `sol` (Codex) ends `no_commit` until #330 is fixed, so a benchmark that includes it measures that bug.
- **Design changes:** the producer environment is `sandbox.producer_env(profile)` passed to an invoker that replaces the child's environment; `scan(source, home, rules)`; the replay enums live in `metrology/benchmark_replay_enums.py`; `bench_caps.py` was not needed (the caps are in `bench_plan.py`). The slice design lists the final modules.
- **Review fixes (verdict FAIL answered):** spend persisted after each replay; lock written before it is linked; leak scan sees `timeout`/`nice`/`xargs`/`eval`/backtick commands; `--keep` warning says copies; auth reminder at each profile's first `no_run_state`; load test takes the cap from the built options; `ReplaySandbox` protocol; instruction-file symlinks that dangle or leave the tree are skipped with a WARNING. `max_budget_usd` exists in the SDK at the declared minimum, so that finding changed nothing. Deferred: #332 (benchmark tests' type ignores), #297 (no bound before dispatch).
- **Review fixes, round 2 (CONCERNS answered):** JSONL split on `\n` only; flock guard around lock take-over; no silent SDK profile; the case-kind seam now owns classification and the record's pipeline and step names (`ReplayFields`); instruction files that cannot be hashed carry a marker; `build_production_services` split; one copy of the action helpers; typed test doubles; `MetrologyStore.delete_record`; only the `squadron` package directory is protected. The producer timeout stays deferred to #297.
- **Next:** 425 (grader and paired report). Before a Codex benchmark: #330.

### Slice 424 Task 13: transcript spike

One-step `dispatch` runs per profile in a scrubbed home (`ScrubbedEnvironment` with the profile's credential grant), home kept. Both runtimes wrote their transcript into the redirected home, so the D6 gate holds. Fixtures: `tests/benchmark/fixtures/transcripts/<profile>/`, layout kept, message text replaced by `scrubbed`, tool names and path/command inputs kept, home rewritten to `/home/user`.

- **`sdk`** (alias `haiku`; Claude Code 2.1.319, claude-agent-sdk 0.2.179, `entrypoint: sdk-py`)
  - Files: `<home>/.claude/projects/<cwd with / as ->/<session>.jsonl`; a subagent run adds `<session>/subagents/agent-<id>.jsonl` (entries `isSidechain: true`). Paths in tool inputs are realpaths (`/private/tmp/...` on macOS).
  - Entry types: `queue-operation`, `user`, `attachment`, `atis-latch`, `api-request-shape`, `api-request-blob`, `api-request`, `last-prompt`, `ai-title`, `tools-used`, `assistant`, `cost-state`.
  - Tool call: `type: assistant`, `message.content[]` block `{type: "tool_use", id, name, input, caller}`. `Read` input `{file_path}`; `Bash` input `{command, description}`; `Agent` input `{description, prompt, subagent_type}`. The subagent file's `Read` call is a `tool_use` block in an `assistant` entry like any other.
  - `turns` in the run state's usage record: 3 for a `Read` + `Bash` run, 3 for the subagent run (informational).
- **`openai-oauth`** (alias `luna`; Codex `cli_version` 0.160.0; the `codex` on PATH reports 0.163.0)
  - File: `<home>/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl`; entries `{timestamp, ordinal, type, payload}`.
  - Entry types (`type` / `payload.type`): `session_meta`, `turn_context`, `world_state`, `event_msg` (`task_started`, `item_completed`, `token_count`, `task_complete`), `response_item` (`message`, `custom_tool_call`, `custom_tool_call_output`), `token_usage_record`.
  - Tool call: `type: response_item`, `payload.type: custom_tool_call`, `payload.name: exec`, `payload.input` a JavaScript snippet such as `const r = await tools.exec_command({cmd:"ls", max_output_tokens:2000});`. There is no `command` field: the command is the `cmd:"…"` string inside that source text, so the parser must read it from there. This run issued two `custom_tool_call` items (`cat hello.txt`, `ls`) and no file tool.
  - `turns` in the run state's usage record: 1 although the transcript holds two tool calls, so `turns` cannot corroborate extraction (PM decision: the scan does not use it).
- Scratch homes under `/tmp/sq424/spike-root` hold copied credentials and are deleted after capture; scripts are in `/tmp/sq424/`.

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
