---
docType: tasks
slice: slice-cases
project: squadron
lld: user/slices/426-slice.slice-cases.md
dependencies:
- 177
- 403
- 421
- 422
- 424
- 425
projectState: Slices 421–425 have tasks written, not implemented (src/squadron/benchmark
  does not exist at the time of writing). Slice 426 design written. main is the target
  unless cf config get git.integration_branch says otherwise.
dateCreated: 20261106
dateUpdated: 20261106
status: not_started
turns: 18
promptTokens: 1352542
cachedTokens: 1253268
cacheWriteTokens: 99242
completionTokens: 30491
durationSeconds: 208.2
costUsd: 0.827585
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.8275853000000001
    completionTokens: 30491
---

## Context Summary
- Working on slice 426: slice cases, `sq benchmark slice-cases build`, `sq benchmark judge`, and the slice-case report tables. Design: `user/slices/426-slice.slice-cases.md`; its D-numbers (D1–D17) are cited below instead of repeating them.
- Delivers: three extractions (`judge_pair`, `CfRegistration`, public artifact patterns) and two config keys; `ScrubbedEnvironment.with_tools`; the slice records and store methods; `normalize`; slice discovery, task text and qualification; the `slice-cases build` command; `SliceCaseRunner`; the diff judge (pairing, forfeits, over-size, bound, cap, resume) and its command; per-kind report tables with the pairwise section; yield rows; slash-command mirrors. 424 and 425 are not edited beyond the seam they already give this slice.
- Order: branch and design corrections (Task 1); the extractions and config keys (Tasks 2–5) and the fixtures and `normalize` (Tasks 6–7), which need nothing from 421–425; the precondition gate (Task 8); `with_tools` and the cf spike (Tasks 9–10); records and store (Tasks 11–12); discovery and task text (Tasks 13–14); qualification (Tasks 15–19); build, its command, yield rows and a live build (Tasks 20–23); runner and a live replay (Tasks 24–26); diff judge and its command (Tasks 27–35); report (Tasks 36–39); slash commands (Task 40); walkthrough (Task 41); final validation (Task 42).
- **Preconditions (Task 8):** Tasks 2–7 touch only `replay/` (177), config code, git fixtures and the pure `normalize` function, and are committed before the gate. Tasks 9 onward need something 421–425 create. At the time of writing those names do not exist, so Task 8 stops with `BLOCKED:` and Tasks 9 onward wait. Every 421–425 name below is the name those task files give; read the real module before using one, and if a name differs use the real one and say so in the DEVLOG entry.
- Design gaps found while reading the code (Task 1 writes each into the design; these tasks follow the corrections):
  - **`judge_pair` must keep 177's call count (D12).** `_call` increments `JudgeSummary.calls`, and `_judge_pair` stops after a failed first call. The design signature has no counter, so `judge_pair` gets an `on_call: Callable[[], None]` parameter, called once per dispatched call; `judge_replay_set` passes a callable incrementing `summary.calls` (Task 3).
  - **Slice plan at the fork (D3).** `plan_file_for(index, root)` reads `*-slices.*.md` under a working tree, and discovery has no tree at the fork. Task 14 writes the fork's slice-plan files (`git ls-tree` and `git show` on `ARCHITECTURE_DIR/*-slices.*.md`) into a temporary directory with the same layout and calls `plan_file_for` there; the directory is removed afterwards.
  - **Task file order (D3).** "Task files sorted by name" would put `-10` before `-2`. The public patterns module also exports the numeric `suffix_order` (today `_suffix_order`), and `task_text` uses it (Task 2).
  - **`CfRegistration` cleanup state (D9).** `ReplaySandbox._registered` is set after `cf init` succeeds so cleanup removes a half-registered project. `CfRegistration` exposes a `registered` property, and raises `CfRegistrationError` (message: the command and its stderr); `ReplaySandbox` re-raises it as `SandboxError` (Task 4).
  - **Registration branch (D9).** `register` takes a `branch`, which the design leaves undefined. cf's branch guard compares the checkout to `git.integration_branch`, so the branch is the one the sandbox tree is on (`git branch --show-current`); on a detached HEAD the runner first creates `SLICE_BRANCH_PREFIX + <sandbox id>`, as `ReplaySandbox` does for its own branch. 424 reads the diff as `start..HEAD`, so the branch does not change it (Task 24).
  - **`--keep` (API Contracts).** The design lists the flag and no behavior. It leaves the fork and tip qualification sandboxes in place and prints their paths; without it they are removed (Tasks 16, 21).
  - **Over-size count (D14, D15).** A stale `OverSizeCase` stays after the limit is raised and the case is judged. The report counts a case as over size only when the judge has an `OverSizeCase` for it and no `DiffJudgment` for that case (Tasks 34, 38).
  - **Build stop (D6, API Contracts).** A harness error stops the build, but every index in the record still gets a line: the stopping candidate is recorded `harness_error`, and later ones print `not attempted` with no record (Task 20).
  - **Edits to 424 (Scope).** The design says no edits to 424 or 425, but D8 and Patterns and Conventions require two to 424: widening `CaseDrop.reason` (Task 11) and removing the slice-case planning refusal (Task 25). The design's Scope line names them; 425 is not edited.
  - **Implementation order (Implementation Notes).** The design puts the cf spike first. It needs 421's sandbox, so Tasks 2–7, which need none of 421–425, come first, and the spike is the first task after the gate (Task 10).
- Shared names (defined once): `SliceCandidateRejection` only in the slice models module (Task 11); `SLICE_RULE_VERSION` only in `slice_qualify.py`; `CF_TOOLS` and `SLICE_BRANCH_PREFIX` only in `slice_runner.py`; dropped-path constants only in `diff_normalize.py`; the two config key names only in `config/keys.py`. Never compare against a literal.
- Failure modes (review rule): each new I/O path has a test that asserts an observable signal (a log at WARNING or above plus a recorded outcome): a failing `git` call in discovery or qualification (`harness_error`); a failing or timed-out cf step (harness absence); a hung, timed-out or failing judge call (pair left unrecorded, summary count); a `tip_sha` missing from `--repo` (refusal naming case and sha); a store write failure; the judge lock held; a run stopped by the cap (exit 2, records kept).
- Load tests: two small ones where this slice adds paths 421's load test does not cover: the environment layer (concurrent `SliceCaseRunner.invoke` calls under distinct scrubbed homes, Task 24) and the network layer (a long plan with a slow and a hung dispatcher double, Task 33). Building adds no concurrency of its own; sandbox and install paths are covered by 421's load test.
- Pyright covers `src` only (`[tool.pyright] include`), so tests are held to `ruff` and a passing run, and every source module to zero pyright errors.
- Tests live in `tests/benchmark/`, `tests/replay/`, `tests/metrology/`, `tests/config/` and `tests/cli/`. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Nothing here pushes or merges. Defects found in this slice's own code are part of the slice, so their commits are `feat:`.
- Effort 3/5. Next planned slice: 427.

## Tasks

### Task 1: Create the slice branch and correct the design
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file as modified or untracked, commit it there by path as `docs: add slice 426 tasks`; planning work commits to the target. Stage every later commit by path
  - [ ] Success: `git status --short` does not list the task file
- [ ] Edit `user/slices/426-slice.slice-cases.md` so it states each design-gap bullet in the Context Summary (those bullets are the spec): D12 (`judge_pair` signature with `on_call`), D3 (plan files materialized from the fork; numeric task-file order), D9 (`CfRegistration.registered`, `CfRegistrationError`, the registration branch), D14 and D15 (the over-size count rule), the `--keep` and build-stop lines in API Contracts, the API Contracts block, the Scope line (the two edits to 424 named in the gap bullets) and Implementation Notes (order)
  - [ ] Success: D3, D9, D12, D14, D15, API Contracts, Scope and Implementation Notes agree with the gap bullets

**Commit**: `docs: correct slice 426 design for judge_pair counting, fork plan files, registration branch, keep and over-size counts`

- [ ] `git checkout -b 426-slice.slice-cases <target>` (or switch to it if it exists)
  - [ ] Success: `git branch --show-current` prints the slice branch

### Task 2: Public artifact patterns (D3)
- [ ] Read `replay/start_point.py` and `tests/replay/test_start_point.py` first. Rename `_ArtifactKind` to `ArtifactKind`, `_KINDS` to `ARTIFACT_KINDS` and `_suffix_order` to `suffix_order`, with docstrings; update every use in the file. Add one helper `artifact_pattern(phase, index) -> str` returning `{directory}/{index}-{stem}.*.md`, and use it in `resolve_start_point` and `artifact_files` so the pattern is built once
  - [ ] Success: `grep -rnwE '_KINDS|_ArtifactKind|_suffix_order' src tests` finds nothing; `tests/replay/` passes unchanged
- [ ] Tests in `tests/replay/test_start_point.py`: `artifact_pattern` for `DESIGN` and `TASKS`; `suffix_order` puts `-2` before `-10` for split task files
  - [ ] Success: tests pass; pyright is clean

**Commit**: `refactor: make artifact path patterns public in start_point`

### Task 3: Extract `judge_pair` (D12)
- [ ] Read `replay/judging.py` first. Add `judge_pair(prompt_a_first, prompt_b_first, dispatcher, timeout_s, label, on_call) -> tuple[JudgeReply, JudgeReply] | None` holding `_call` and `_judge_pair`'s loop: first order, then the second, each bounded by `asyncio.wait_for`; a timeout or `JudgeCallError` logs at ERROR and gives `None`; a failed second call logs the first call's spend at WARNING (`_spent`) and gives `None`. `on_call` runs once before each dispatch. If `judging.py` would pass ~300 lines, put `judge_pair` and `_spent` in `replay/judge_pair.py` and import it
- [ ] `judge_replay_set` builds its two prompts, calls `judge_pair` with an `on_call` that increments `summary.calls`, and keeps its own behavior; delete `_call` and `_judge_pair`
  - [ ] Success: `tests/replay/` passes unchanged
- [ ] Tests `tests/replay/test_judge_pair.py`: both calls succeed (two replies, `on_call` twice); first call times out (`None`, ERROR logged, `on_call` once); first call raises `JudgeCallError` (`None`, ERROR logged); second call fails (`None`, WARNING names the first call's spend); a hung dispatcher is cut at `timeout_s`
  - [ ] Success: tests pass; pyright is clean

**Commit**: `refactor: extract judge_pair from judge_replay_set`

### Task 4: Extract `CfRegistration` (D9)
- [ ] Read `replay/sandbox.py` and `tests/replay/test_sandbox.py` first. New `replay/cf_registration.py`: `CfRegistrationError`, and `CfRegistration(runner, env)` with `register(tree, name, branch, slice_index)` running the three steps `_register_with_cf` runs (`cf init --lite --no-ide --name`, `cf config set git.integration_branch`, `cf set arch <initiative>`), each with `cwd=tree` and `env=env`. The initiative comes from `plan_file_for(slice_index, tree)`, resolved before `cf init` as `_register_with_cf` does, so a slice in no plan leaves nothing registered; `UnknownSliceError` becomes `CfRegistrationError`. `registered` is true once `cf init` succeeded. A non-zero exit, a process failure or a timeout raises `CfRegistrationError` carrying the command and stderr, logged at ERROR
- [ ] `ReplaySandbox` composes `CfRegistration(runner, None)` in place of `_register_with_cf` and `_initiative`, sets `_registered` from `registration.registered` even when `register` raised, and re-raises `CfRegistrationError` as `SandboxError` with the message it gave before. Cleanup behavior is unchanged
  - [ ] Success: `tests/replay/test_sandbox.py` passes unchanged
- [ ] Tests `tests/replay/test_cf_registration.py` with a recording runner: the three commands in order with the given `cwd` and `env`; `registered` false before and true after; a failing `cf set arch` leaves `registered` true and raises with the stderr; a failing `cf init` leaves it false; a slice in no plan raises with `registered` false and no cf command run; a timeout raises; ERROR is logged on each failure
  - [ ] Success: tests pass; pyright is clean

**Commit**: `refactor: extract CfRegistration from ReplaySandbox`

### Task 5: Config keys (D12, D14)
- [ ] `config/keys.py`: add a slice-case group with a constant, a `CONFIG_KEYS` entry and a description for each key (421, 422 and 425 add their benchmark keys in the same file; keep this group together and do not depend on theirs): `benchmark.judge_model` (alias string, no default) and `benchmark.judge_max_prompt_chars` (positive int, default 400000). Read the limit with `get_positive_int_config`
- [ ] Tests in the existing keys test file under `tests/config/` (grep for `metrology.judge_timeout_s`): `judge_model` reads as unset, never as a value; the limit defaults to 400000; 0 and a negative value are rejected with the error type `get_positive_int_config` raises; a set value is returned
  - [ ] Success: tests pass

**Commit**: `feat: add slice-case judge config keys`

### Task 6: Fixture repositories and real landings (Technical Requirements)
- [ ] Read `tests/metrology/slice_range_repos.py` first and reuse its helpers. New `tests/benchmark/slice_repos.py` with one builder per history shape, each returning the repo path and the shas tests assert on, written with design, task and slice-plan files at the fork where the shape needs them: a landing with a two-parent landing commit; a fast-forward landing; two landings of one slice; a branch carrying a two-parent commit from the target (the `branch_contains_merges` shape); no task file at the fork; no design at the fork; no slice plan at the fork; a docs-only slice (DEVLOG, task and review files only); a slice whose every test changed and one whose regression selection would be empty (the test files are all rewritten)
  - [ ] Success: each builder produces a repo whose `git rev-list` and `git diff --name-status` shows the shape; one parametrized smoke test over the builders asserts it
- [ ] Real landings (the design requires fixtures from squadron's own landings; 403 is implemented, so no 426 code is needed): run `sq metrology slice-ranges <indices>` for squadron's 400-initiative slices, read the stored record with `get_slice_ranges`, and save one two-parent landing and one fast-forward landing (every `SliceLanding` field) with their slice indices as `tests/benchmark/fixtures/real_landings.json`. Tests read this data only, never the user's checkout
  - [ ] Success: the file holds one landing of each method and validates as `SliceRanges`; a test loads it

**Commit**: `test: add slice-case fixture repositories and real landings`

### Task 7: `normalize` (D11)
- [ ] New `benchmark/diff_normalize.py`: `NormalizedDiff(text, dropped_paths, binary_paths)` and `normalize(diff: bytes)`. Dropped paths are constants defined once: root `DEVLOG.md` and `CHANGELOG.md`, prefixes `{DOCS_ROOT}/user/tasks/`, `{DOCS_ROOT}/user/reviews/` and `{DOCS_ROOT}/user/slices/`, and `uv.lock`. Split on `diff --git` headers; read old and new paths leniently from the header, `rename from`/`rename to` and `---`/`+++` lines, including quoted paths; keep a section unless both its paths are dropped; a binary section becomes one line `Binary file <path> changed`; a diff that normalizes to nothing becomes `(no changes outside dropped paths)`. `is_dropped(path) -> bool` (true when the path is in the dropped set) is exported and `normalize` uses it. Pure functions, no I/O
- [ ] Synthetic tests `tests/benchmark/test_diff_normalize.py`: `is_dropped` is true for each dropped path and false for a code file; each dropped path removed; a nested `docs/user/tasks/` file kept when not under the repo's `DOCS_ROOT`; a rename with one side kept is kept and with both dropped is dropped; a binary section becomes the marker line and is listed in `binary_paths`; the empty result text; a quoted path with spaces; CRLF content survives unchanged
  - [ ] Success: tests pass
- [ ] Real fixture: from the landings saved in Task 6 (or another landing in the stored record) choose a small slice whose `fork..tip` touches DEVLOG, a task file and review files (`git diff <fork> <tip>` under 200 KB, else choose another), store it as `tests/benchmark/fixtures/slice_diff.diff`, and add a test that the output has none of the dropped paths, keeps every code and test file, and keeps hunk bodies byte-identical to the input
  - [ ] Success: the test reads the real file and passes; pyright is clean

**Commit**: `feat: add diff normalization for the slice-case judge`

### Task 8: Preconditions
- [ ] Confirm by grep in `src/squadron` that these exist. 421: `BenchmarkCase` with `CaseKind.SLICE`, `CaseSet`, `BenchmarkRecordStore`, `BenchmarkSandbox`, `HistoryFreeSandbox`, `EnvironmentIdentity`, `ScrubbedEnvironment` and `HARNESS_TOOL_ALLOWLIST`, `run_suite`, the adapter registry (`benchmark/registry.py`), `CaseProvenance`, `ProcessRunner` (`core/process_runner.py`). 422: `test_sets`, `QualificationOutcome`, `TestRejection`, `FixCaseAdapter` (`is_test_side`, `collect`, `grader_commands`), `benchmark.qualification_repeats`, `benchmark/yield_report.py` and its separability bound. 424: `CaseKindRunner` with `invoke` and `requalify`, `ImplementationReplay`, `replay_one`, `replays_for`, `CaseDrop`, `BenchmarkRun`, `AbsenceClass` and the absence values `no_commit`, `blocked`, `cost_cap` and `producer_failed`, the leak-scan path list and scan function, the benchmark lock helper, `sq run --producer-only`, and the production wiring of `sq benchmark run` (the module that builds its collaborators). 425: `grade_one`, `GradingAdapter`, `ContentSidecars`, `paired_stats`, `bootstrap_mean_interval`, `bench_report.py` and its case-kind table registry, `PairVerdict`, `GradeAbsence` with `reference_failed_grade`, the grade command's cap and bound code and its `--keep`. 177: `parse_verdict`, `combine`, `judge_prompt` and `judge_prompt_hash` (`replay/judge.py`), `one_shot_judge_dispatcher`, `JudgeReply`, `JudgeCallError`, `bradley_terry.fit`, `JudgeRef`, `JudgeCall`, `PairOutcome`. 403: `get_slice_ranges`, `SliceLanding`, `sq metrology slice-ranges`. `commands/sq/benchmark.md`. `cf` runs (`cf --version`). If any is missing write `BLOCKED: <name> is not implemented (slice <n>)` under this task, leave it unchecked, and stop (Tasks 2–7 are already committed)
- [ ] Run `uv run pytest tests/metrology tests/replay tests/benchmark -q` once and record the pass count in a comment under this task, so later tasks can tell their failures from existing ones
  - [ ] Success: all names found; no `BLOCKED:` line

### Task 9: `ScrubbedEnvironment.with_tools` (D9)
- [ ] Read 421's `ScrubbedEnvironment` and its tests first. Add `with_tools(tools: Sequence[str]) -> ScrubbedEnvironment`: a copy whose `<id>.home/bin` also links each named tool as resolved on the harness's `PATH`. An unresolvable tool raises the error type the class already uses for a missing allowlisted tool, naming the tool. The default tool list, `SCRUB_SPEC_VERSION` and `EnvironmentIdentity` are unchanged
- [ ] Tests: the copy links `cf` (a stub executable on a fake `PATH`) and the original does not; a missing tool raises naming it; the identity digest of the copy equals the original's; 421's scrub tests pass unchanged
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: let a scrubbed environment link extra tools`

### Task 10: cf spike (D9, Implementation Notes 1)
Scratch work goes in new directories under `/tmp`; nothing is pushed. LLM spend and live runs are pre-authorized.
- [ ] Pick one landing from `get_slice_ranges` for squadron whose fork has a design, a task file and a slice plan. Build a `BenchmarkSandbox` at its `fork_sha`, take its `ScrubbedEnvironment(...).with_tools(("cf",))`, and with `CfRegistration(runner, env).register(...)` under that environment (branch: the tree's current branch from `git branch --show-current`, or on a detached HEAD a throwaway branch `spike-<index>` created by hand) run: `cf set slice <index>`, `cf set phase 6`, `cf build` (read `cf --help` for the exact subcommands P6's cf-ops run) and `sq run P6 <index> --producer-only --dry-run` with `cwd=<tree>` and `env=<scrubbed>`
  - [ ] Success: each command exits 0 with `HOME` redirected, which shows cf needs nothing from the real home to run them; the dry run lists the `implement` step
- [ ] Leak-scan coverage, in a script under `/tmp` (not in the repo): (a) print the real path of the `cf` executable and its directory (`realpath "$(command -v cf)"`) and the real-home directory `cf project list` reads its registry from (read `cf project list --help`); (b) import 424's leak-scan path list and scan function and print, for each path in (a), whether the list covers it; (c) run the scan function over the captured stdout and stderr of every command in the first bullet. Record the output in the DEVLOG. If cf fails to register, set the slice or build context under the scrubbed home, a path in (a) is not covered, or (c) is not clean, write `BLOCKED: cf under a scrubbed home: <command and stderr, or the uncovered path>` under this task, leave it unchecked, and stop
  - [ ] Success: the DEVLOG states what ran, what each command printed, that every path in (a) is covered and that the scan in (c) was clean

### Task 11: Slice enums and records (D6, D12, D14, Database Schema)
- [ ] Read `metrology/benchmark_models.py` first. Add `SliceCandidateRejection` (`StrEnum`, the seven values of Patterns and Conventions), `SliceQualification`, `DiffJudgment` and `OverSizeCase` exactly as the design's Database Schema gives them. If `benchmark_models.py` would pass ~300 lines, put them in `metrology/slice_case_models.py` and say so in the DEVLOG. Widen 424's `CaseDrop.reason` to accept `SliceCandidateRejection`
  - [ ] Success: 424's drop tests pass unchanged
- [ ] Tests `tests/benchmark/test_slice_case_models.py`: the rejection values match the design's seven names exactly; each record round-trips through JSON; `SliceQualification` with `outcome=qualified` requires a `case_id` and no rejection, with `rejected` requires a rejection, with `harness_error` has neither; `DiffJudgment` with `forfeit=True` has no calls and an outcome, and a non-forfeit has both calls; a realistic `DiffJudgment` (two 2 KB raw tails) serializes under 4096 bytes; `CaseDrop` accepts a `SliceCandidateRejection` value
  - [ ] Success: tests pass; pyright is clean

### Task 12: Record ids and store methods (D6, D16, Database Schema)
- [ ] Add pure functions for the three record ids exactly as D6 and D16 give them (`slice_qualification_id`, `diff_judgment_id`, `over_size_case_id`; sorted refs, sha256, never `hash()`). `MetrologyRecord` gains optional `slice_qualification`, `diff_judgment` and `over_size_case` payloads with `RECORD_TYPE_*` constants. `BenchmarkRecordStore` gains `write_slice_qualification`, `get_slice_qualification(project_id, index, after_sha, env_digest)` (`env_digest=None` addresses the pre-sandbox record, key `pre`), `list_slice_qualifications(project_id=None)`, `write_diff_judgment`, `diff_judgments_for(benchmark_id, judge_alias=None)`, `write_over_size_case` and `over_size_cases_for(benchmark_id, judge_alias=None)`. A write that fails raises the store's error, logged at ERROR. If `benchmark_store.py` would pass ~300 lines, put these in a sibling store mixin as 425 does for grades
- [ ] Tests `tests/benchmark/test_slice_case_store.py`: ids are stable across ref order and change with judge prompt hash, alias and `pre` versus a digest; round-trip each record; a newer qualification under the same key overwrites; `get_slice_qualification` returns `None` for another digest; `diff_judgments_for` filters by alias; an over-size record is replaced when written again under the same id; a store file written without the new payloads still loads (no migration); a failing write raises and logs ERROR
  - [ ] Success: tests pass; 421's store tests pass unchanged

**Commit**: `feat: add slice qualification, diff judgment and over-size records`

### Task 13: Discovery and the no-code check (D1, D2, D4)
- [ ] New `benchmark/slice_discovery.py`: `SliceCandidate` (project, slice index, the single landing) and `discover(store, project_id, runner, repo) -> DiscoveryResult` holding candidates and `SliceCandidateRejection`s with detail. No `slice_ranges` record raises a refusal whose message names `sq metrology slice-ranges`. A slice with more than one landing is `multiple_landings`; `git rev-list --merges fork..tip` non-empty is `branch_contains_merges`; a failed or timed-out `git` call is a `harness_error` entry (ERROR logged), never a rejection. Uses `ProcessRunner`, injected
- [ ] In the same module add `has_code_change(fork, tip, repo, runner)`: `git diff --name-status fork tip` in the user's checkout, with both sides of a rename considered; true unless every path is one `diff_normalize`'s dropped-path rule drops (reuse `is_dropped` from `diff_normalize` (Task 7); do not copy the constants). A failed `git` call is a harness error
- [ ] Tests `tests/benchmark/test_slice_discovery.py` on Task 6's repos: a two-parent landing and a fast-forward landing yield candidates; two landings and a two-parent commit on the branch are rejected with their values; no record raises naming the command; a runner double whose `git` fails gives `harness_error` and an ERROR log; every index in the record appears once in the result. On Task 6's real landings (a `SliceRanges` loaded from the JSON, a runner double answering `rev-list`): one candidate per landing method. `has_code_change`: a docs-only slice is false; one code file among dropped files is true; a rename from a dropped path to a code path is true; a git failure raises the harness error and logs ERROR
  - [ ] Success: tests pass; pyright is clean

### Task 14: Task text at the fork (D3)
- [ ] New `benchmark/slice_task.py`: `task_text_at(fork_sha, index, repo, runner) -> TaskText | rejection`. Find the design and task files at `fork_sha` with `git ls-tree` using `artifact_pattern` and `ARTIFACT_KINDS`; task files in `suffix_order`; `task_text` is each file's `git show` content verbatim, design first, each preceded by a line `## File: <path>`. Rejections: `no_design_at_fork`, `no_tasks_at_fork`, and `no_slice_plan_at_fork`, checked by writing the fork's `ARCHITECTURE_DIR/*-slices.*.md` files into a temporary directory with the same layout and calling `plan_file_for` there (removed afterwards, also on error). A failed `git` call is a harness error, as in Task 13
  - [ ] Success: after a call (accepted, rejected or failing) the temporary directory no longer exists
- [ ] Tests `tests/benchmark/test_slice_task.py`: text is design then tasks with the `## File:` lines and verbatim content including frontmatter; split task files `-2` before `-10`; each of the three rejections on Task 6's repos; the temporary directory is gone after a rejection and after a git failure; the same inputs give the same string (it feeds the case id)
  - [ ] Success: tests pass

**Commit**: `feat: add slice discovery, fork task text and the no-code check`

### Task 15: Qualification, reuse lookup and pre-sandbox checks (D4, D6)
- [ ] New `benchmark/slice_qualify.py` with `SLICE_RULE_VERSION` (int, bumped when any check changes), `slice_qualification_for(store, case, environment) -> SliceQualification | None` (the record only when the key (project, index, landing, fork digest) and rule version match) and `can_skip(record, digest)` (true when the rule version matches, the outcome is not `harness_error`, and either the record is a pre-sandbox record, `start_environment is None`, key `pre`, which needs no digest because its checks read only git at fixed shas, or its fork environment digest equals `digest`)
- [ ] Add `qualify_slice_candidate(...)` with every collaborator injected (sandbox factory, adapter registry, store, runner, clock). Its first stage reads the pre-sandbox record (`env_digest=None`) and returns it when `can_skip(record, None)`; otherwise it runs the Task 14 task-text checks and the Task 13 no-code check, and writes a `rejected` `SliceQualification` with `start_environment=None` for any failure, before any sandbox exists
- [ ] Tests `tests/benchmark/test_slice_qualify_checks.py`: matching record returned; another digest, landing or rule version returns `None`; `can_skip` is false for `harness_error` or another rule version, true for a pre-sandbox record with no digest, and for a keyed record only when the digest matches; a stored pre-sandbox rejection is returned with the sandbox factory double never called; each of `no_design_at_fork`, `no_tasks_at_fork`, `no_slice_plan_at_fork` and `no_code_change` produces a record with `rejection` set and the sandbox factory double never called
  - [ ] Success: tests pass

### Task 16: Qualification, sandboxes and test sets (D5, D7)
- [ ] In `qualify_slice_candidate` add the second stage: `BenchmarkSandbox` at the fork first; with its environment digest look up the keyed record and return it when `can_skip(record, digest)`, building and running nothing further; then the tip sandbox (`keep` leaves both in place, Task 21), the environment identity keyed on the fork digest, `collect` on both through the adapter registry, and 422's `test_sets`. `superseded` = fork-only nodes and nodes at both with different closure digests; tip-only nodes are ignored; hidden is always empty
- [ ] Tests `tests/benchmark/test_slice_qualify_sets.py` with adapter and sandbox doubles: superseded from both rules; tip-only nodes appear nowhere on the case; hidden is empty; a matching keyed record is returned and `collect` is never called, a record under another digest is not; with `keep` the sandboxes are not removed and their paths are returned, without it they are removed
  - [ ] Success: tests pass

### Task 17: Qualification, repeats and exclusions (D5)
- [ ] In `qualify_slice_candidate` add the third stage: run the full suite `benchmark.qualification_repeats` times at the tip; nodes whose outcome differs across runs go on `excluded_tests` as `flaky`, nodes failing every run as `fails_at_reference`; the reasons are kept on the record's `excluded_with_reasons`
- [ ] Tests `tests/benchmark/test_slice_qualify_repeats.py`: a flaky node and an always-failing node are excluded with their reasons; a node that passes every run is not excluded; the suite runs exactly `qualification_repeats` times
  - [ ] Success: tests pass

### Task 18: Qualification, regression selection and the case (D5, D6)
- [ ] An empty regression selection (fork nodes − superseded − excluded) is `no_regression_signal`. Otherwise write the `BenchmarkCase` (`kind=slice`, `start_sha=fork_sha`, `reference_sha=tip_sha`, `task_text`, empty hidden set, `CaseProvenance` with `source_ref = "slice:<index>@<landing_after_sha>"` and the slice name) and a `qualified` `SliceQualification`
- [ ] Tests `tests/benchmark/test_slice_qualify_case.py`: an empty selection is `no_regression_signal`; a qualified case has the fields above and a stable case id; `source_ref` is not part of the id (same id for another landing sha with the same inputs); the qualification record carries both environments
  - [ ] Success: tests pass; pyright is clean

### Task 19: Qualification, harness errors (D6)
- [ ] Wrap every stage of `qualify_slice_candidate`: a suite timeout, `SuiteRunError`, sandbox error or failed `git` call is logged at ERROR and recorded as `harness_error` with its detail, never as a rejection that blames the slice, and writes no case
- [ ] Tests `tests/benchmark/test_slice_qualify_errors.py`: each of the four failures gives a `harness_error` record, an ERROR log naming the slice, and no case; a later successful run under the same key overwrites the record
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add slice-case qualification`

### Task 20: `slice_case_build` (D1, D6)
- [ ] New `benchmark/slice_case_build.py`: `build_slice_cases(..., keep)` runs discovery, calls `qualify_slice_candidate` for each candidate (it reuses a stored record that satisfies `can_skip` without re-running, Tasks 15–16), writes the case set (`--set`, qualified case ids, existing members of the set kept) and returns one result line per candidate (`slice 403 qualified case-… (412 regression nodes, 3 superseded, 1 excluded)` or the rejection value and detail). A harness error stops the build: that candidate is recorded `harness_error`, every later index in the record gets the line `slice <index> not attempted (build stopped at slice <n>)` and no record, and the result carries the stop. Every index in the record has a line
- [ ] Tests `tests/benchmark/test_slice_case_build.py` with doubles: one line per index in the record; a second build with the real `qualify_slice_candidate` reuses unchanged candidates (adapter and suite doubles not called) and re-runs a `harness_error` one; the case set holds exactly the qualified ids; a harness error on the second of three indexes gives a recorded `harness_error`, a `not attempted` line for the third and no record for it
  - [ ] Success: tests pass

### Task 21: `sq benchmark slice-cases build` (API Contracts)
- [ ] New `cli/commands/benchmark_slice.py`: `slice-cases build --set NAME [--repo PATH] [--keep]`, registered under `sq benchmark`; one line per candidate, then the slice-case yield rows for the project (Task 22 supplies them; until then print the lines only). `--keep` leaves the fork and tip qualification sandboxes in place and prints their paths, as 425's `grade --keep` does; without it they are removed. Exit 0 when the build finished, whatever the yield; exit 1 when no `slice_ranges` record exists (message names `sq metrology slice-ranges`) or a harness failure stopped it
- [ ] Production wiring: a `build_deps()` function in the same module constructs the real collaborators (`BenchmarkRecordStore`, the adapter registry, the `BenchmarkSandbox` factory, `ProcessRunner`, the clock) the way 424's `sq benchmark run` module constructs its own (read it first), and the command calls it
- [ ] Tests `tests/cli/test_benchmark_slice_build.py`: output and exit 0 for a stored fixture; exit 1 with the command named when there is no record; exit 1 on a harness failure; with `--keep` the sandbox factory double is told to keep and the paths print; `build_deps()` returns the real store, a registry holding the Python adapter and the real runner types without running a process; `--help` exits 0 and lists the options (check `option.hidden` on the command, not the rendered help text)
  - [ ] Success: tests pass

### Task 22: Yield rows for slice cases (Technical Scope)
- [ ] `benchmark/yield_report.py`: add slice-case rows for the project beside the fix-case rows: qualified count and one count per `SliceCandidateRejection` value and `harness_error`, grouped by value. Text and JSON both carry them; with no slice qualifications the output is unchanged
- [ ] Tests: rows appear with counts from stored `SliceQualification`s; every rejection value is listed when nonzero; no slice records leaves the existing golden output byte-identical; 422's yield tests pass unchanged
  - [ ] Success: tests pass; Task 21's command prints the rows

**Commit**: `feat: add sq benchmark slice-cases build and slice-case yield rows`

### Task 23: Live build on squadron (walkthrough steps 1–2)
Scratch work goes in new directories under `/tmp`; nothing is pushed. LLM spend and live runs are pre-authorized.
- [ ] `sq metrology slice-ranges` for squadron's completed slices (the 400-initiative slices, at least one two-parent landing and one fast-forward), then `sq benchmark slice-cases build --set slices` and `sq benchmark yield`
  - [ ] Success: every index in the record has a line (qualified, a named rejection, `harness_error`, or `not attempted` after a stop); `yield` shows slice-case rows beside fix-case rows; at least one case qualified, or the rejection counts are recorded in the DEVLOG as the yield finding
- [ ] Any defect found in Tasks 6–7 and 13–22 is fixed here with a test and recorded in the DEVLOG. If no file changed there is nothing to commit and the marker below is skipped

**Commit**: `feat: correct slice-case build after the live run`

### Task 24: `SliceCaseRunner` invoke (D8, D9)
- [ ] New `benchmark/slice_runner.py`: `CF_TOOLS = ("cf",)`, `SLICE_BRANCH_PREFIX` and `SliceCaseRunner`, a `CaseKindRunner` for `CaseKind.SLICE` with injected collaborators (registration factory, invoker, installed-`sq` path resolved once at harness start). `invoke`: read the tree's branch with `git branch --show-current`, and on a detached HEAD create and switch to `SLICE_BRANCH_PREFIX + <sandbox id>`; `ScrubbedEnvironment(grant=profile).with_tools(CF_TOOLS)`; `CfRegistration(runner, env).register(tree, name=<sandbox id>, branch, slice index)`; then `<installed sq> run P6 <index> -m <alias> --producer-only --max-cost <per-replay cap> --run-id <replay record id>` with `cwd=<tree>`, `env=<scrubbed>`. The replay's `pipeline` is `P6` and `producer_step` is `implement`. A `CfRegistrationError` or a failed branch step is a harness absence (424 D10) logged at ERROR with the step and stderr; the producer never ran. No `cf project rm` is called and the user's cf registry is never touched
- [ ] Tests `tests/benchmark/test_slice_runner.py`: the exact argv, cwd and env (scrubbed home, `cf` linked, `HOME` redirected); registration happens before the producer and under the same env; a tree on a branch registers that branch and creates none; a detached tree gets the prefixed branch and registers it; a failing `cf set arch` gives a harness absence, an ERROR log, and the invoker double is never called; no `cf project rm` is ever issued; fix-case runners never receive `with_tools`; eight concurrent `invoke` calls with distinct sandbox ids each register under their own scrubbed home, with no shared branch or registry path
  - [ ] Success: tests pass; pyright is clean

### Task 25: Re-qualification routing and planning (D8)
- [ ] `SliceCaseRunner.requalify(case, environment)` calls `slice_qualification_for` and otherwise `qualify_slice_candidate`. Register the runner for `CaseKind.SLICE` on 424's seam where the fix runner is registered, constructing it with its real collaborators there (`CfRegistration`, the process runner, the installed `sq` path). A case set with slice cases now plans instead of refusing (424 D5): remove only that refusal and its test's expectation, keeping every other 424 refusal
- [ ] Tests: matching record returns without qualifying again (qualify double not called); a mismatched digest qualifies again; the production construction returns a runner registered for `CaseKind.SLICE`; a mixed fix and slice set plans, each case routed to its kind's runner; the seam refuses a kind with no registered runner; 424's tests pass unchanged except the removed slice-case refusal
  - [ ] Success: tests pass

**Commit**: `feat: add the slice-case runner on the case-kind seam`

### Task 26: Live replay of one slice case (walkthrough step 3)
Scratch work goes in new directories under `/tmp`; nothing is pushed. LLM spend and live runs are pre-authorized.
- [ ] `cf project list > /tmp/<dir>/cf-before.txt`; `sq benchmark run --set slices --model <alias> --model <alias> --samples 1 --max-cost 20 --max-cost-per-replay 8 --case <case-id>` using two aliases that answered yes in `sq benchmark auth-check`; `cf project list | diff` against the saved file; `sq benchmark replay-show <record-id> --diff`
  - [ ] Success: each of the two replay lines shows its outcome (`committed` or its absence class), the leak verdict and cost; the cf project list is unchanged; a committed replay's record shows `pipeline P6`, `producer_step implement` and a diff against the fork commit. If no replay committed, the absence classes are recorded in the DEVLOG, only the record's `pipeline` and `producer_step` are checked, and the diff check is skipped
- [ ] Any defect found in Tasks 24–25 is fixed here with a test and recorded in the DEVLOG. If no file changed there is nothing to commit and the marker below is skipped

**Commit**: `feat: correct slice-case runner after the live replay`

### Task 27: Contestants, pairing and forfeits (D13, D15)
- [ ] New `benchmark/diff_judge.py`: `Contestant` (ref, replay or reference, config key, sample number, diff bytes or absence) and `contestants_for(case, replays, reference_diff)` giving each replay plus `reference:<tip_sha>`; `pairs_for(contestants)` giving, for each pair of configs and each sample number, A's sample against B's, plus each replay against the reference; none within one config. Config keys are 425 D13's row keys. Pure; no I/O
- [ ] Add `forfeit_for(pair)`: a pair where one side is a replay with a config absence (`no_commit`, `blocked`, `cost_cap`, `producer_failed`) is a forfeit won by the other side; both sides absent is a forfeit `TIE`; an absent reference raises. `case_judgeable(replays)` is false when any replay carries a harness absence, and returns the reason for the report count. Forfeit judgments carry no calls, usage or diff sidecar for the absent side
- [ ] Tests `tests/benchmark/test_diff_judge_pairs.py`: two configs at k = 3 give 9 pairs; three configs at k = 2 give `k·C(C−1)/2 + k·C` pairs; no same-config pair; each replay appears against the reference once; pair order is deterministic; a config with a missing sample number pairs only the samples that exist; each of the four config absences forfeits to the other side; both absent gives `TIE`; a harness absence on any replay makes the case not judgeable and names the reason; a forfeit validates as a `DiffJudgment` with `forfeit=True` and no calls
  - [ ] Success: tests pass; pyright is clean

### Task 28: Judge prompt and prompt building (D12)
- [ ] Add `data/benchmark/pairwise-diff-judge.md` (frontmatter per `file-naming-conventions`) framing the pair as two implementations of one task given as diffs against the same start commit and asking which better implements the design and task file: correctness, completeness against the tasks, fit with the existing code, tests. It ends with 177's `WINNER: A|B|TIE` instruction. Add `diff_prompt(task_text, diff_a, diff_b)`: packaged prompt, `## Task`, `## Implementation A`, `## Implementation B`. Load the prompt as `replay/judge.py` loads its own (`judge_prompt()` reads `data_dir().joinpath("replay", "pairwise-judge.md")`; read it first) and hash it the same way (`judge_prompt_hash()`); that sha256 is the `JudgeRef.prompt_hash`. The `data/` directory is inside the `squadron` package, so no packaging change is needed
- [ ] Tests `tests/benchmark/test_diff_prompt.py`: sections appear in order with the task and both diffs verbatim; swapping A and B swaps the sections; the hash differs from `judge_prompt_hash()`; a reply ending `WINNER: A` is read by `parse_verdict` unchanged; the packaged file is found through `data_dir()`
  - [ ] Success: tests pass

### Task 29: Over-size rule (D14)
- [ ] In `diff_judge.py` add `check_size(case, pairs, limit)`: build every pair's longer prompt (both orders have equal length) and return `OverSize(longest_chars, contestant)` when the longest exceeds `benchmark.judge_max_prompt_chars`, else `None`. The whole case is excluded; no prompt is ever truncated. A pair with a forfeit has no prompt and is skipped
- [ ] Tests `tests/benchmark/test_diff_judge_size.py`: a prompt at the limit passes and one char over fails; the longest contestant is named; one oversized contestant excludes the whole case; no pair prompt is shortened (assert every built prompt equals the untruncated build); forfeit pairs are ignored
  - [ ] Success: tests pass

### Task 30: Judge loop and `DiffJudgment` (D12, D15)
- [ ] In `diff_judge.py` add the async per-case loop: normalize every contestant diff, store the normalized text through the injected `sidecars` (`ContentSidecars("diffs")`, passed in and never built in the loop), build both prompts, call `judge_pair` with the injected `one_shot_judge_dispatcher`-shaped dispatcher and `metrology.judge_timeout_s`, and write a `DiffJudgment` (hashes of the sidecars, `parse_verdict` calls, `combine` outcome, usage, the limit in effect). Forfeits are written without a call. A failed pair is logged at ERROR, left unrecorded and counted in the summary; the loop goes on. The cap check (Task 33) is an injected callable run before each pair's calls
- [ ] Tests `tests/benchmark/test_diff_judge_loop.py` with a dispatcher double: a pair writes one judgment with both calls and the sidecar hashes; the sidecar holds exactly the normalized diff the prompt contained (read it back and compare); a failed or timed-out pair is unrecorded, ERROR logged, counted, and later pairs still run; a forfeit makes no dispatch; an absent diff gives `None` for its hash; an empty normalized diff is judged with the `(no changes outside dropped paths)` text
  - [ ] Success: tests pass; pyright is clean

**Commit**: `feat: add the slice-case diff judge`

### Task 31: Judge plan, inputs and refusals (D16, API Contracts)
- [ ] New `benchmark/diff_judge_runner.py`: `plan_judge(...)` loads the `BenchmarkRun`, its slice cases and replays (`replays_for`); resolves the judge (`benchmark.judge_model` or `--judge-model`) into a `JudgeRef` with the diff prompt hash; resolves the per-call figure (the largest observed judge-call cost among stored `DiffJudgment`s with the same alias, or `--judge-cost`); and reads each reference diff `start..tip` from `--repo` through `ProcessRunner`. It raises a refusal naming what is missing for: no run cap, no judge alias (naming both the key and the flag), no per-call figure (naming `--judge-cost`), a case's project with no `--repo`, and a `tip_sha` absent from `--repo` (naming the case and the sha). Nothing is dispatched or written here
- [ ] Tests `tests/benchmark/test_diff_judge_refusals.py`: each refusal message names its case, sha, flag or key; the per-call figure is the largest observed cost for the same alias, another alias's judgments are ignored, and `--judge-cost` is used when none exist
  - [ ] Success: tests pass

### Task 32: Judge plan, pairs and counts (D13–D15)
- [ ] In `plan_judge` apply Task 27's contestants, pairing, forfeits and `case_judgeable` and Task 29's `check_size` per case. The plan holds the pairs needing calls (a recorded pair under the same judge is excluded), the forfeits, the over-size cases with their length and contestant, and the not-judgeable cases with their reasons
- [ ] Tests `tests/benchmark/test_diff_judge_plan.py`: the plan counts match a hand-built run (judged, over size, harness-absent, forfeits); a recorded pair is excluded from the pairs needing calls; a case whose limit now fits is planned for judging
  - [ ] Success: tests pass

### Task 33: Bound and cap (D16)
- [ ] In `diff_judge_runner.py` add the bound printed before any call in D16's format (calls × per-call figure, capped at the run cap, plus one call of overshoot) and the cap check before each call (hitting it stops judging, keeps every record, signals exit 2). Nothing is dispatched before the bound line
- [ ] Tests `tests/benchmark/test_diff_judge_bound.py`: the bound's arithmetic on a hand-computed plan; the bound is emitted before the first dispatch (ordering asserted against the dispatcher double); the cap stops after the call that crosses it and keeps earlier records. Network-layer load test: a 200-pair plan with a slow dispatcher double runs the calls one at a time and stops at the cap; a hung dispatcher is cut at `timeout_s`, its pair is left unrecorded with an ERROR log, and the run finishes
  - [ ] Success: tests pass; pyright is clean

### Task 34: Lock, resume and over-size records (D14–D16)
- [ ] In `diff_judge_runner.py` add the judge lock `<benchmark root>/<benchmark_id>.judge.lock` via 424's lock helper (a held lock refuses, naming it, and logs a WARNING), `OverSizeCase` writes (replaced when the limit changes), and resume by id lookup (a recorded pair is never judged again under the same judge)
- [ ] Tests `tests/benchmark/test_diff_judge_resume.py`: a rerun skips judged pairs and judges the rest; a held lock refuses naming the lock file and logs at WARNING or above; an over-size record is replaced when the limit changes; a case that fits after the limit rises is judged on the rerun; a store write failure stops the run with an ERROR log
  - [ ] Success: tests pass; pyright is clean

### Task 35: `sq benchmark judge` (API Contracts)
- [ ] In `cli/commands/benchmark_slice.py` add `judge BENCHMARK_ID --max-cost USD [--judge-model ALIAS] [--judge-cost USD] [--repo PATH …]`: the bound, one line per pair (`case-… opus s1 vs sol s1: A` or `forfeit B`), then a summary (judged, forfeits, failed, over size, harness-absent, spend). Exit 0 complete, 2 run cap reached, 1 refusal or harness stop. A `judge_deps()` function in the module constructs the real collaborators (store, `ProcessRunner`, `one_shot_judge_dispatcher(alias)` for the resolved alias, `ContentSidecars("diffs")`, the lock helper, the clock) in the style of Task 21's `build_deps()`, and the command calls it
- [ ] Tests `tests/cli/test_benchmark_judge.py`: output for a stored fixture with a dispatcher double; exit 2 on the cap; exit 1 with the missing item named for each refusal of Task 31; unknown benchmark id exits 1 naming it; `judge_deps()` returns the real store, runner types and a dispatcher for the alias without dispatching; `--help` lists every option
  - [ ] Success: tests pass

**Commit**: `feat: add sq benchmark judge`

### Task 36: Report grouped by case kind (D17)
- [ ] Read 425's `bench_report.py` and its case-kind table registry first. Group included cases by `CaseKind` and render 425's sections once per kind under a `fix cases` or `slice cases` heading. Fix-case output is unchanged. In slice tables the hidden column is omitted and the pass column is headed `no regressions`. Register the slice kind through the registry, not by editing a switch. If `bench_report.py` would pass ~300 lines, put the slice tables in `benchmark/slice_report.py`
- [ ] Tests `tests/benchmark/test_bench_report_kinds.py`: a fix-only benchmark's text and JSON are byte-identical to 425's golden; a slice-only benchmark shows one `slice cases` table with the renamed column and no hidden column; a mixed benchmark shows both, fix first
  - [ ] Success: tests pass; 425's report tests pass unchanged

### Task 37: Pairwise reduction (D17)
- [ ] New `benchmark/pairwise_report.py` (pure): per config, `bradley_terry.fit` pooled over included cases with contestants as config row keys and `reference`; wins, losses, ties, inconsistent, invalid, forfeits and pair count per config; a strength with no finite value carries 177's reason. Per pair of configs, per case `w(c)` over its sample-matched pairs (win 1, tie 0.5; inconsistent and invalid left out), `d(c) = 2·w(c) − 1`, and the verdict from 425's `bootstrap_mean_interval(values, seed)` mapped to `PairVerdict` (`a_ahead`, `b_ahead`, `not_distinguishable`, `too_few_cases`), seeded as 425 seeds its pairs. Cases dropped at grading (425's harness absences, `reference_failed_grade`) are excluded here
- [ ] Hand-computed tests `tests/benchmark/test_pairwise_report.py`: a case with wins, ties and one inconsistent pair gives the `w(c)` and `d(c)` computed by hand in the test comment; a pair of configs whose interval spans zero is `not_distinguishable`; one case is `too_few_cases`; a case dropped at grading is excluded; the reference is fitted but never ranked; forfeits count in the config's tallies
  - [ ] Success: tests pass; pyright is clean

### Task 38: Pairwise rendering and counts (D17)
- [ ] Render the pairwise section after the review findings for slice cases only, for the latest judge with others listed: the table and the reference line marked `reference`, the pair line with `d` and interval and verdict, and the count line (judged, over size with the limit in effect, harness-absent, failed pairs pending). A case counts as over size only when the judge has an `OverSizeCase` for it and no `DiffJudgment` for that case. Text and JSON both carry it; the reference is never ranked and no composite is computed
- [ ] Tests `tests/benchmark/test_pairwise_render.py`: output matches the design's example layout for a stored fixture; two judges list the latest first; over-size and harness-absent counts and the limit appear; a case with an `OverSizeCase` and later judgments is counted as judged, not over size; the existing "no composite field" test is extended to the pairwise JSON; a fix-only report has no pairwise section
  - [ ] Success: tests pass

### Task 39: Mixed fix and slice integration (Integration Requirements)
- [ ] One test `tests/benchmark/test_mixed_kinds.py` with doubles: a case set holding one fix case and one slice case runs (each routed to its runner), grades, judges (the fix case is not judged) and reports with each kind in its own tables; 422's yield output shows both kinds' rows for the project
  - [ ] Success: the test passes and asserts no pairwise rows for the fix case

**Commit**: `feat: report slice cases per kind with a pairwise section`

### Task 40: Slash-command mirrors (API Contracts)
- [ ] `commands/sq/benchmark.md`: add `slice-cases build` and `judge` with the same arguments and no interpretation, so output is identical to the CLI (the form 424 gave `run`)
- [ ] Tests: the existing slash-command sync test (grep `benchmark.md` under `tests/`) covers the new subcommands; add one if none exists
  - [ ] Success: the file lists both subcommands with the options of the Typer commands (read against `sq benchmark slice-cases build --help` and `sq benchmark judge --help`) and holds no behavior text beyond running `sq benchmark $ARGUMENTS`

**Commit**: `feat: add slice-case slash commands`

### Task 41: Verification walkthrough (design Verification Walkthrough steps 4–8)
Scratch work goes in new directories under `/tmp`; nothing is pushed. LLM spend and live runs are pre-authorized. Needs `benchmark.grading_review_model` and `benchmark.judge_model` set to aliases that answered yes in `sq benchmark auth-check`; a missing prerequisite no task here can produce is written as `BLOCKED:` with the evidence.
- [ ] Step 4: `sq benchmark grade <bench-id> --max-cost 5 --review-cost 0.25` on Task 26's benchmark
  - [ ] Success: the reference line prints `pass`; each replay prints pass or fail with its regression count
- [ ] Step 5: `sq benchmark judge <bench-id> --max-cost 3 --judge-cost 0.05`
  - [ ] Success: the bound prints first with the limit and pair count (1 cross-config pair and 2 reference pairs for two configs at k = 1); each pair prints its outcome
- [ ] Step 6: `sq benchmark report <bench-id>`
  - [ ] Success: a `slice cases` table appears apart from any fix-case table, then the pairwise section with strengths, the reference line marked not ranked, the pair verdict (`too few cases (1)` at this size) and the count line
- [ ] Step 7: `sq config set benchmark.judge_max_prompt_chars 1000`, create a fresh benchmark with Task 26's `sq benchmark run` command and `--samples 2` (it prints the new benchmark id), run step 5 on it, then unset the key
  - [ ] Success: the case is reported `over_size` with its length, no judge call is made, the report counts it; the key is unset afterwards
- [ ] Step 8: `uv run pytest tests/benchmark/test_diff_normalize.py -v`
  - [ ] Success: the real-slice fixture passes
- [ ] Any defect found in this slice's code is fixed here with a test and recorded in the DEVLOG; run the gates in Task 42's first bullet before the commit below. If no file changed there is nothing to commit and the marker below is skipped

**Commit**: `feat: correct slice-case judging and report after the walkthrough`

### Task 42: Final validation, design names and DEVLOG
- [ ] Run the gates on the whole branch: `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite once; fix any failure at its cause
  - [ ] Success: all clean, or failures recorded as already failing on the target with the test names; `tests/replay/` and `tests/benchmark/` pass unchanged except where D8, D12 and D17 changed call sites
- [ ] Confirm no source file added or changed by this slice exceeds ~300 lines (`wc -l`; likeliest: `diff_judge.py`, `slice_qualify.py`, `bench_report.py`, `benchmark_store.py`); split by concern where one does
- [ ] Update the slice design with the names the implementation added (`CfRegistrationError`, `ARTIFACT_KINDS`, `artifact_pattern`, `suffix_order`, `SLICE_BRANCH_PREFIX`, `OverSize`, `DiscoveryResult`, `build_deps`, `judge_deps`, any split modules). The gaps were corrected in Task 1; add any further gap the implementation found
- [ ] DEVLOG: implementation entry per the Session State Summary guidance (what was done, the Task 10 spike result, Task 23's yield finding, walkthrough results, next: 427); mark the slice design `status: complete` and tick its slice-plan entry when every task above is checked, dropped items `[x]` with a note
  - [ ] Success: slice design and slice plan reflect completion; every task above is checked

**Commit**: `feat: complete slice cases slice`
