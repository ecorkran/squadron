---
docType: tasks
slice: producer-only-replay-runner
project: squadron
lld: user/slices/424-slice.producer-only-replay-runner.md
dependencies:
- 421
- 422
- 423
projectState: v0.24.23 released, main is the target (git.integration_branch unset).
  Slices 421, 422 and 423 have tasks written, not implemented. Slice 424 design written.
dateCreated: 20261106
dateUpdated: 20261106
status: not_started
turns: 23
promptTokens: 1621986
cachedTokens: 1498677
cacheWriteTokens: 123275
completionTokens: 33046
durationSeconds: 235.8
costUsd: 0.973813
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.9738131999999999
    completionTokens: 33046
---

## Context Summary
- Working on slice 424: `sq run --producer-only` and the benchmark runner (`sq benchmark run`, `sq benchmark replay-show`). Design: `user/slices/424-slice.producer-only-replay-runner.md`; its D-numbers (D1–D11) are cited below instead of repeating them.
- Delivers: the `ProducerStep` capability and a producer-only definition transform; the `--producer-only` flag; SDK in-dispatch cost enforcement (`max_budget_usd`); `BenchmarkRun` / `ImplementationReplay` records and diff sidecars; `TranscriptSource` per profile and the leak scan; `FixCaseRunner`, `replay_one`, `bench_plan`, `bench_runner`; two CLI commands and their slash-command mirrors. Nothing here grades (425).
- Order: the issue the design calls for (Task 2); producer-only, which needs nothing from 421–423 (Tasks 3–9); the SDK cost cap, D9 (Task 10); the precondition gate for 421–423 (Task 11); the fix step's producer config and the transcript spike (Tasks 12–13); records and sidecars (Tasks 14–15); transcript sources and the leak scan (Tasks 16–21); identity, caps, the bound and planning refusals (Tasks 22–24); the fix-case runner, outcome classification and `replay_one` (Tasks 25–27); the runner (Tasks 28–31); CLI and slash command (Tasks 32–35); walkthrough (Task 36); final validation (Task 37).
- **Preconditions (Task 11):** Tasks 1–10 (producer-only and the D9 cap) need nothing from 421, 422 or 423 and are complete and committed before the gate. Task 11 confirms 421, 422 and 423 are implemented. At the time of writing none is, so Task 11 stops with `BLOCKED:` there and Tasks 12 onward wait; nothing before it is held up. Every 421/422/423 name below (`BenchmarkSandbox`, `ScrubbedEnvironment`, `BenchmarkRecordStore`, `CaseKind`, `qualification_for`, `FixStepType`, `fix_keys.py`) is the name those task files give; read the real module before using one, and if a name differs, use the real one and say so in the DEVLOG entry.
- Design gaps found while reading the code (the design is not edited; these tasks follow the corrections):
  - **`branch: enter` is not run.** `P6`'s first step enters the slice branch, and `implement`'s code commit refuses off it (`_check_placement`), but only after the dispatch has spent. Producer-only keeps D1's single step, so Task 7 adds a preflight: a producer step whose commit subject is `code` refuses before any dispatch unless the current branch is that slice's branch, saying `branch: enter` is not run and naming the branch to check out.
  - **No built-in named `slice`.** The design's walkthrough and refusal example use `sq run slice`. The built-in with several producer steps is `P456` (`design`, `tasks`, `implement`); the tasks use it.
  - **`run.py` size.** `cli/commands/run.py` is ~1560 lines. All new producer-only CLI logic goes in a new module `cli/commands/run_producer_only.py`; `run.py` gets only the flag and calls.
  - **Resume reload.** Every resume path (`--resume`, `--prompt-only --next`, `--step-done`) reloads the definition through `_load_run_definition`. The transform is re-applied there, so no resume path needs its own branch.
  - **Flags the design does not name.** The design refuses `--from`, `--item`, `--flagged`. `--producer-only` is also refused with `--explain`, `--validate`, `--status`, `--step-done` and `--next` on a fresh run (a flag with nothing to transform, or addressing removed steps), each naming both flags. It is accepted with a run, `--dry-run`, `--prompt-only` and `--resume`. (`--prompt-only --next` resumes a run that already has the param, so it needs no flag.)
  - **`sq run --max-cost` and `--io-dir` with `--prompt-only`** are refused today; `--producer-only --prompt-only` keeps that.
  - **`RunState.producer_only`.** Follow how `RunState.replay` is plumbed (optional field with a default, absent in older files, no schema-version bump).
  - **No hidden defaults.** `--samples` defaults to `benchmark.planned_samples` (422's key); Task 32 implements and tests it, and the run refuses naming both when neither is set.
- Shared names (defined once): `ProducerOutcome`, `AbsenceClass`, `LeakVerdict`, `LeakRule`, `BenchmarkStatus` StrEnums live only in `metrology/benchmark_models.py` (Task 14); `RUN_PRODUCER_ONLY` only in `pipeline/control_params.py`. Never compare against a literal.
- Failure modes (review rule): every new I/O path is covered by a test that asserts an observable signal (WARNING+ log or a recorded outcome): transcript missing or unparseable (`scan_unavailable`), `sq` killed or silent (`no_run_state`), stalled run (`producer_failed`), diff or sidecar failure (ERROR, benchmark stops, sandbox kept), store write failure, second invocation while the lock is held (refusal), peer process killed mid-replay (`interrupted`).
- Load test: the SDK budget path (Task 10) is a budget path, so Task 10 adds one test in `tests/load/` and checks CI gates it. The harness itself is sequential (one replay at a time, #146 excluded) and reads files synchronously, so nothing else is on a concurrent or latency-bounded path. Every external call has a bound already (`sq` stall bound, Codex turn timeout, git calls through `ProcessRunner`).
- Tests live in `tests/pipeline/`, `tests/cli/`, `tests/benchmark/` and `tests/metrology/`. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Nothing here pushes, merges or posts to an issue, except Task 2, which files one issue.
- Effort 4/5. Next planned slice: 425.

## Tasks

### Task 1: Create the slice branch
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file as modified or untracked, commit it there by path (`git add <task file>`, then `git commit -- <task file>` as `docs: add slice 424 tasks`); planning work commits to the target. Commit `DEVLOG.md` the same way only if `git diff DEVLOG.md` shows nothing but the slice 424 entry; otherwise leave it unstaged and stage every later commit by path
  - [ ] Success: `git status --short` does not list the task file
- [ ] `git checkout -b 424-slice.producer-only-replay-runner <target>` (or switch to it if it exists)
  - [ ] Success: `git branch --show-current` prints the slice branch

### Task 2: File the Codex / OpenAI-compatible enforcement issue (D9)
- [ ] Run `gh issue create` (as its own Bash call) titled `In-dispatch cost enforcement for Codex and OpenAI-compatible producer runs`. Body: the cap is checked only after a dispatch on those paths (D9); `sq benchmark run` therefore lists them as `not bounded`; the SDK path is enforced through `max_budget_usd`; link slice 424
- [ ] Write the number GitHub returned under this task (the design says it goes in the task file; nowhere else). If the issue cannot be created, write `issue not filed` there instead and say why
  - [ ] Success: `gh issue view <n>` shows the issue, and this task holds its number or `issue not filed`

**Commit**: `docs: record issue for non-SDK in-dispatch cost enforcement`

### Task 3: `ProducerStep` protocol and the reserved param (D2, D3)
- [ ] `pipeline/control_params.py`: add `RUN_PRODUCER_ONLY = "run_producer_only"` with a comment like its neighbors, and an entry in `RESERVED_PARAMS` (`--producer-only`)
- [ ] `pipeline/producer_only.py` (new): `ProducerStep` as a `runtime_checkable` Protocol with `producer_only_config(self, config: StepConfig) -> StepConfig`, per the design's D2 snippet. Beside the module docstring state that each step type owns its review key, so neither the executor nor the CLI names one
- [ ] Tests `tests/pipeline/test_producer_only_protocol.py`: `RUN_PRODUCER_ONLY` is rejected by `reserved_param_error` and by the `-p` path (`_apply_param_overrides` in a CLI test); a dummy class with the method satisfies `isinstance(x, ProducerStep)`; one without it does not
  - [ ] Success: tests pass; `tests/pipeline/test_control_params.py` (or the file that covers `RESERVED_PARAMS`) still passes

### Task 4: `PhaseStepType.producer_only_config` (D1, D2)
- [ ] In `pipeline/steps/phase.py` add `producer_only_config`: returns a new `StepConfig` (same `step_type` and `name`) whose `config` copy has no `review` and no `checkpoint` key. Nothing else is touched; the expansion already adds review, checkpoint and `REVIEW_TEMPLATE_PARAM` only when `review` is set. If `phase.py` would pass ~330 lines, put the method's body in a small helper module beside it
  - [ ] Success: the input config is not mutated
- [ ] Tests `tests/pipeline/steps/test_phase_producer_only.py`: for the `implement` step of the loaded `P6`, `expand(producer_only_config(cfg))` equals `expand(cfg)` minus the `review` and `checkpoint` actions, and the `commit` action's config equals the original's minus `REVIEW_TEMPLATE_PARAM` (the design's byte-identity test); the cf-ops before the dispatch (`set_slice`, `check_decisions`, `set_phase`, `build_context`) and `existing: keep` are unchanged; a `design` step and a `tasks` step (from `P4`, `P5`) also satisfy `ProducerStep`; a step with no `review` key returns an equal config; `isinstance(PhaseStepType(), ProducerStep)`
  - [ ] Success: tests pass; `uv run pytest tests/pipeline/steps -q` passes

**Commit**: `feat: add the ProducerStep capability to phase steps`

### Task 5: `producer_only_definition` (D1)
- [ ] In `pipeline/producer_only.py` add frozen `ProducerOnlySelection` (`definition`, `step_name`, `skipped: tuple[str, ...]`, in definition order) and `producer_only_definition(definition) -> ProducerOnlySelection`. It looks up each top-level step's registered type (`get_step_type`, after `bootstrap_step_types()`); exactly one must satisfy `ProducerStep`; nested steps inside `loop` / `each` are not candidates. The result is a copy of the definition (same params, model, `max_cost_usd`) with `steps = [stripped step]`; the input is not mutated
- [ ] Refusals raise `ProducerOnlyError(ValueError)` naming the pipeline and the candidates: none (the message lists the pipeline's step names and says no step type is a producer), more than one (lists the candidate step names). Both log at WARNING first
- [ ] Tests `tests/pipeline/test_producer_only_definition.py`: `P6` → step `implement`, skipped names exactly the other top-level step names in order; `P4` and `P5` each have one producer; `P456` refuses, naming `design`, `tasks` and `implement`; a pipeline with only `dispatch`/`branch` steps refuses; a producer nested in a `loop` is not a candidate; the input definition's `steps` list is unchanged; refusal logs a WARNING (`caplog`)
  - [ ] Success: tests pass

**Commit**: `feat: add the producer-only definition transform`

### Task 6: Run state record and CLI flag (D3)
- [ ] `pipeline/state.py`: add a frozen model `ProducerOnlyRecord(step: str, skipped: list[str])` and `RunState.producer_only: ProducerOnlyRecord | None = None`, following how `RunState.replay` is plumbed from the CLI through `init_run`. Older files load unchanged; no schema-version bump. Show it in `sq runs show` (find the renderer in `cli/commands/stats.py` or `run_listing.py`) as a `producer-only` line only when set
- [ ] `cli/commands/run_producer_only.py` (new): `check_producer_only_flags(...)` refuses, each with `Error: --producer-only cannot be combined with <other flag>.` on stderr and exit 1: `--from`, `--item`, `--flagged`, `--explain`, `--validate`, `--status`, `--step-done`, `--next`; `apply_producer_only(definition, params) -> ProducerOnlySelection` sets `params[RUN_PRODUCER_ONLY] = True` and returns the selection, catching `ProducerOnlyError` at the CLI boundary (print `Error: …`, exit 1, no stack trace); `stop_line(selection, commit_sha)` returns `producer-only: stopped after <step> (commit <sha>); skipped: <a, b>` (commit part omitted when the run made no commit)
- [ ] In `run.py`: add `--producer-only` (a bool Typer option, help text one line) and, before the existing branches, one call to `check_producer_only_flags`. Wire in Tasks 7–8
- [ ] Tests `tests/cli/test_run_producer_only_flags.py` (Typer `CliRunner`): every refused combination exits 1 and the message names both flags; `RunState` round-trips with and without the field; an old state JSON without the field loads with `producer_only is None`; `sq runs show` prints the line only when set
  - [ ] Success: tests pass; `tests/cli/test_help.py` and `tests/cli/test_command_surface.py` pass

### Task 7: Producer-only on fresh runs and dry runs (D1, D3)
- [ ] In `run.py`'s `--dry-run` branch and the fresh-run path (find where `load_pipeline` feeds `_run_pipeline_sdk`), when `--producer-only` is set call `apply_producer_only` right after validation and use `selection.definition` from there on (`render_steps`, `classify_for_run`, `_run_pipeline_sdk`). The dry run additionally prints one line: `producer-only: step <step>; skipped: <names>`
- [ ] After the run, `_display_result` path prints the stop line (Task 6) once, and the run state's `producer_only` is stamped at state creation (the record is built from the selection and passed down as `replay` is). The exit code stays the ordinary one for the run's status
- [ ] Branch preflight in `run_producer_only.py`, called after `apply_producer_only` on a fresh run and a dry run (Task 8 adds the prompt-only call): resolve the selected step's config with the run's params (`resolve_placeholders`, `pipeline/executor.py`), expand it, and when its `commit` action has `SUBJECT_PARAM` equal to `CommitSubject.CODE`, require `parse_slice_branch(current_branch(cwd)) ==` that action's slice index. Otherwise exit 1 before any dispatch with `Error: --producer-only does not run branch: enter; check out the branch for slice <index> first (on <branch>).` Steps whose commit is not a code commit (`design`, `tasks`, `fix`) are not checked. A `GitEnvironmentError` from `current_branch` ends the run at the CLI boundary with `Error: …`
- [ ] `_load_run_definition`: after `load_pipeline`, when `state.params.get(RUN_PRODUCER_ONLY)` is truthy, apply `producer_only_definition` and return its definition, so `--resume`, `--prompt-only --next` and `--step-done` never grow the other steps back. A `ProducerOnlyError` on reload exits 1 naming the cause (the pipeline changed shape since the run started)
- [ ] Tests `tests/cli/test_run_producer_only.py`: `sq run P6 7 --producer-only --dry-run` lists exactly `set_slice`, `check_decisions`, `set_phase`, `build_context`, `dispatch`, `commit` and no `review`/`checkpoint`; a fresh run on a fake executor registry stops after one step and prints the stop line with the skipped names; the run state has `producer_only` set and `params[RUN_PRODUCER_ONLY]` true; `--resume` of such a run (state paused at `implement`) executes only that step; `_load_run_definition` of a producer-only state returns one step; `sq run P456 7 --producer-only` (the multi-producer case) exits 1 naming candidates; on the target branch (a real temp git repo) `sq run P6 7 --producer-only` exits 1 with the branch message before the fake dispatch is called, and on `7-slice.x` it proceeds
  - [ ] Success: tests pass; `uv run pytest tests/cli -q` passes

**Commit**: `feat: add sq run --producer-only`

### Task 8: Prompt-only producer-only and `/sq:run` (D3)
- [ ] In `_handle_prompt_only_init` apply the transform the same way (after validation, before `_render_prompt_only_step`), set the param, stamp the state and call the Task 7 branch preflight. `--prompt-only --producer-only --max-cost` and `--io-dir` stay refused by the existing checks
- [ ] `commands/sq/run.md`: document `--producer-only` in the argument list and make the command pass it through unchanged to `sq run … --prompt-only`; add one sentence that the run stops after the producer step and prints the stop line
- [ ] Tests (`tests/cli/test_run_producer_only_prompt.py`): `sq run P6 7 --prompt-only --producer-only` emits instructions for the one `implement` step's actions and no other step; the following `--next` returns no further step; on the target branch the init refuses with the branch message; `commands/sq/run.md` mentions `--producer-only` (a plain text check, as 423's `test_run_md_actions.py` does for sections)
  - [ ] Success: tests pass

**Commit**: `feat: add producer-only to prompt-only runs and /sq:run`

### Task 9: Executor-level check on real pipelines (Functional Requirements)
- [ ] `tests/pipeline/test_producer_only_executor.py`: run the transformed `P6` through `execute_pipeline` with fake actions registered for each action type the one step reaches (follow `tests/pipeline/test_guarded_commit.py` and `test_executor_failure_kind.py` for faking and reading state): the saved run state's completed steps are exactly `implement`, with no `review`, `checkpoint`, `devlog`, `branch`, loop or `summary` action; the dispatch received the same prompt a full-`P6` run's `implement` dispatch receives on the same fake `build_context` output (run both and compare the delivered prompt and its sha256); the commit action's config has no review template
  - [ ] Success: tests pass; no pipeline YAML or prompt file was added (`git status --short` lists only code, tests and docs)

**Commit**: `test: verify producer-only runs against the P6 pipeline`

### Task 10: In-dispatch cost cap on the SDK path (D9)
- [ ] Read `pipeline/sdk_session.py` (`open_pipeline_session`, the `is_error` path at about line 441), `pipeline/run_session.py` (line ~75) and `pipeline/executor.py` (the lazy session factory at about line 927, and `cost_cap` at line ~598). Add a keyword `max_budget_usd: float | None = None` to `open_pipeline_session` and pass it to `ClaudeAgentOptions(max_budget_usd=…)` only when not `None` (an uncapped run passes no budget). Thread the run's remaining cap (`cost_cap.usd` minus `RunSpend.known_usd` when the session opens, never below a tiny positive floor defined once as a constant) through both call sites
- [ ] Map the SDK's `error_max_budget_usd` result subtype to `FailureKind.COST_CAP`: where an `is_error` result becomes a provider error, carry the subtype so the dispatch action stamps `FAILURE_KIND_KEY = cost_cap` (follow how `usage_limit_stamp` marks a usage limit in `failure_kind.py`). Other error subtypes are unchanged
- [ ] Tests `tests/pipeline/test_sdk_budget.py`: a capped run's `ClaudeAgentOptions` carries `max_budget_usd` equal to the remaining cap; an uncapped run's does not; a fake client result with subtype `error_max_budget_usd` yields a failed dispatch with `failure_kind: cost_cap` (and the run ends `failed`, not paused); another error subtype is unchanged; `tests/pipeline/test_executor_cost_cap.py` passes unchanged
  - [ ] Success: tests pass; `uv run pytest tests/pipeline -q` passes
- [ ] Load test `tests/load/test_sdk_budget_bound.py` (module docstring in the style of `tests/load/test_grep_timeout.py`): a fake SDK client streams result messages whose cumulative cost crosses a capped session's budget; assert the dispatch ends `cost_cap` and the recorded overshoot stays within one dispatch's cost, and that a ticker coroutine running alongside never stalls longer than a small multiple of the fake's per-message delay (the stop does not block the event loop). No `network` marker
  - [ ] Success: the test passes under `uv run pytest tests/load/test_sdk_budget_bound.py -q`
- [ ] Confirm CI gates it: read `.github/workflows/ci.yml` and `pyproject.toml` `[tool.pytest.ini_options]`; the `uv run pytest` step passes no `-m`, `--ignore` or path that excludes `tests/load`, and `tests/load` is inside `testpaths`
  - [ ] Success: no exclusion found, or the exclusion is recorded in the DEVLOG entry
- [ ] CHANGELOG `[Unreleased]`: one short user-facing bullet (the design's D9 requires it): a capped SDK run now stops at the cap inside a dispatch, not only after each action
  - [ ] Success: the bullet is user-facing, no technical detail

**Commit**: `feat: enforce the run cost cap inside SDK dispatches`

### Task 11: Preconditions
- [ ] Confirm 421, 422 and 423 are implemented: for each of `project-documents/user/tasks/421-tasks.*.md`, `422-tasks.*.md`, `423-tasks.*.md` run `grep -cF -- '- [ ]' <file>` as its own Bash call and read the printed count (it prints `0` when every item is checked, and exits 1 then, so never chain it and never read the exit status); `src/squadron/benchmark/registry.py` and `src/squadron/pipeline/steps/fix.py` exist; `sq pipelines list` shows `fix`. If any check fails, write `BLOCKED: slice <n> is not implemented` under this task, leave it unchecked, and stop (Tasks 12 onward need those slices; Tasks 1–10 are already committed)
- [ ] Confirm the 947 and 420 names the design uses exist, by grep: `read_cost_cap` and `RunSpend` (`pipeline/run_spend.py`), `FailureKind.COST_CAP`, `effort_sent` on `ProducerConfigRef` (`metrology/replay_models.py`), `run_sq_subprocess` (`replay/runner.py`), `replay/outcome.py`. Missing → `BLOCKED:` naming it
- [ ] Run `uv run pytest tests/replay tests/pipeline tests/cli -q` once and record the pass count in a comment under this task, so later tasks can tell their own failures from existing ones
  - [ ] Success: all checks done; no `BLOCKED:` line

### Task 12: `FixStepType.producer_only_config` (D2)
- [ ] In `pipeline/steps/fix.py` (423) add `producer_only_config` returning the config unchanged (copy), with a docstring that `fix` has no embedded review (423 D1)
- [ ] Tests (extend `tests/pipeline/steps/test_fix_step.py`): config equal to the input, a different object; `isinstance(FixStepType(), ProducerStep)`; `expand` of the result equals `expand` of the input
- [ ] Tests for the `fix` pipeline (extend `tests/pipeline/test_producer_only_definition.py`, and `tests/pipeline/test_producer_only_executor.py` in the style of Task 9): `producer_only_definition` of the loaded `fix` pipeline selects step `fix` with nothing skipped and an equal step list; an `execute_pipeline` run of it with a fake dispatch and a valid fix report on a real temp repo (file mode, `commit-to=current`) commits once
  - [ ] Success: tests pass; no pipeline YAML or prompt file was added

**Commit**: `feat: add the ProducerStep capability to the fix step`

### Task 13: Transcript spike (D6 step 1)
- [ ] For each profile that has an `sq benchmark auth-check` yes (421): `sdk` and `openai-oauth`. Use the cheapest alias per profile that `sq models` lists and `sq benchmark auth-check` answered yes for; for `openai-oauth` only an alias on the oauth profile, never an alias on the API-key `openai` profile. Build a `BenchmarkSandbox` (421) on a small fixture project, run `sq run` on a throwaway one-step pipeline file in `/tmp` (`dispatch` step whose prompt asks the agent to read one file in the tree and run `ls` through its shell tool, then reply done) with `cwd=<tree>` and `env=ScrubbedEnvironment(CredentialGrant.for_profiles([profile]))`, `--keep` semantics (do not remove the home)
- [ ] For each profile record in the DEVLOG: the path of every transcript file under `<home>` (`find <home> -name '*.jsonl'`), the entry types and the `tool_use` / function-call item shapes (field names for tool name, input, command), whether subagent files exist (`sdk`: run one prompt that asks for a subagent), and the runtime version
  - [ ] A profile whose runtime wrote no transcript under the redirected home: write `BLOCKED: <profile> writes no transcript into the scrubbed home` and the evidence under this task, leave it unchecked, and stop (the design's D6 gate)
- [ ] Capture the real files into `tests/benchmark/fixtures/transcripts/<profile>/` keeping layout (relative directories, file names, entry order and keys). Scrub content: replace message text and file contents with `scrubbed`, keep every key, tool name and tool input shape; keep tool inputs that name paths, with the user's home replaced by `/home/user`. Include one file with a tool call whose input is a shell command and one with a file-tool path
  - [ ] Success: fixtures exist for both profiles; each parses as JSONL (`python -I -c` over the files); the DEVLOG has the layout facts; no secret or real home path appears (`grep -rn "$HOME" tests/benchmark/fixtures/transcripts` is empty)

**Commit**: `test: capture runtime transcript fixtures for leak scan`

### Task 14: Benchmark replay record models (D7, D10, Database Schema)
- [ ] `metrology/benchmark_models.py` (421 created it for cases; add to it, and split a new `metrology/benchmark_replay_models.py` if the file would pass ~300 lines): `ProducerOutcome`, `AbsenceClass` (`harness`, `config`, `none` is not a value; absence is `None` for `committed`), `LeakVerdict` (`leaked`, `no_leak_detected`, `scan_unavailable`), `LeakRule` (`path`, `git_or_host`, `own_package`), `BenchmarkStatus` (`running`, `complete`, `partial`, `interrupted`) as StrEnums with the design's values (the `ProducerOutcome` values are the D10 table's first column); frozen models `LeakHit`, `LeakScanResult` (`hits` max 20, `excerpt` max 300 chars enforced by validators that raise, never truncate silently), `DiffRef`, `ImplementationReplay`, `CaseDrop`, `BenchmarkRun`, exactly as in the design's Database / Storage Schema
- [ ] `metrology/models.py`: add `RECORD_TYPE_BENCHMARK_RUN`, `RECORD_TYPE_IMPLEMENTATION_REPLAY` and the optional sibling payload fields `benchmark_run`, `implementation_replay` on `MetrologyRecord`, in the pattern the existing payloads use; older records load unchanged
- [ ] Tests `tests/metrology/test_benchmark_replay_models.py`: each model round-trips through JSON; `hits` of 21 and an excerpt of 301 chars raise; `ProducerOutcome` values equal the D10 list; a record with no new payloads (a stored 320 record fixture) loads; a representative `ImplementationReplay` (with 20 hits of 300 chars absent, i.e. a normal one, `environment`, `prompt` and 6 instruction files) serializes under 8 KB
  - [ ] Success: tests pass; `uv run pytest tests/metrology -q` passes

### Task 15: `DiffSidecars` and the store methods (D11, State Management)
- [ ] `metrology/benchmark_store.py` (421 created it): `DiffSidecars(root)` with `put(data: bytes) -> DiffRef` (sha256 of the bytes; atomic write to `<store>/sidecars/diffs/<sha256>.diff` via a temp file and rename when absent; when present, verify the content against the hash and raise `MetrologyStoreError` on a mismatch; `files_changed` counted from `diff --git` header lines) and `get(sha256) -> bytes` (verifies the hash; missing file or mismatch raises `MetrologyStoreError`, logged at ERROR). An empty diff is valid (`bytes=0`, `files_changed=0`)
- [ ] `BenchmarkRecordStore`: `write_run`, `get_run`, `list_runs`, `write_replay`, `get_replay`, `replays_for(benchmark_id)`, `delete_replays(ids) -> int` (used only by `--retry-harness`), and a `diffs: DiffSidecars` attribute. Reuse 421's `write_record`/`iter_records` primitives; a run record is overwritten in place, a replay record written once (a second write of the same id with different content raises). The `*.json` glob stays top-level so sidecars are never read as records
- [ ] Tests `tests/metrology/test_benchmark_store_replays.py`: put/get round trip; the same bytes put twice write once; tampered sidecar → `MetrologyStoreError` on `get` and on a second `put`; missing file raises; empty diff; run overwrite changes status; replays listed per benchmark; `delete_replays` removes only the named ids and returns the count; a sidecar file in the store never appears in `iter_records`; a store write that fails (read-only directory) raises and logs ERROR
  - [ ] Success: tests pass

**Commit**: `feat: add benchmark replay records and diff sidecars`

### Task 16: `TranscriptSource` protocol and registry (D6)
- [ ] `benchmark/transcripts.py`: frozen `ToolCall(tool: str, input: Mapping[str, object])`; `TranscriptResult` (`tool_calls`, `files_read: int`, `problems: tuple[str, ...]`); `TranscriptSource` Protocol with `read(home: Path) -> TranscriptResult`; a registry `transcript_source_for(profile: ProfileName) -> TranscriptSource | None` that returns `None` for an unregistered profile (the caller decides to refuse) and a `register_transcript_source` function. Lenient helpers shared by both parsers: `iter_jsonl(path) -> Iterator[Mapping]` that skips blank lines and reports a line that is not a JSON object into `problems`
- [ ] Tests `tests/benchmark/test_transcripts.py`: registry returns the registered source and `None` for `openai`, `openrouter`, `gemini`, `local`; `iter_jsonl` skips blank lines and records a bad line without stopping
  - [ ] Success: tests pass

### Task 17: `ClaudeTranscriptSource` (D6)
- [ ] `benchmark/transcript_claude.py`: every `*.jsonl` under `<home>/.claude/projects/`, recursively (subagent files included), in sorted path order; extract `tool_use` content blocks (`name`, `input`) using the shapes recorded in the Task 13 DEVLOG entry; unknown entry types are skipped; register for profile `sdk`. No transcript directory, or no files, yields `problems` saying so
- [ ] Tests `tests/benchmark/test_transcript_claude.py` against `tests/benchmark/fixtures/transcripts/sdk/` (copied into `tmp_path` as a fake home): the fixture's tool calls are extracted with the expected tool names and inputs; a subagent file's calls are included; an unknown entry type is skipped; a non-JSON file yields a problem; an empty home yields a problem; a synthetic extra line is also covered, but the fixture test must exist
  - [ ] Success: tests pass

### Task 18: `CodexTranscriptSource` (D6)
- [ ] `benchmark/transcript_codex.py`: every `rollout-*.jsonl` under `<home>/.codex/sessions/`, recursively; extract function and shell call items (tool name and arguments or command) per the Task 13 shapes; a shell call's command is exposed as `input["command"]` so the leak rules read one field name for both runtimes; register for profile `openai-oauth`
- [ ] Tests `tests/benchmark/test_transcript_codex.py` against `tests/benchmark/fixtures/transcripts/openai-oauth/`: calls extracted with names and commands; an unknown item type skipped; missing directory and bad JSONL yield problems
  - [ ] Success: tests pass

**Commit**: `feat: read tool calls from Claude Code and Codex transcripts`

### Task 19: Leak rules and path extraction (D7, path rule)
- [ ] `benchmark/leak_scan.py` (split path extraction into `benchmark/leak_paths.py` if the module nears ~300 lines): `LEAK_RULES_VERSION = 1` (int constant) and the module docstring listing the known gaps verbatim from D7 (scripts the model writes and runs, paths built at run time, network reads outside the code host). Frozen `LeakRules` built per replay from: the sandbox's three directories, the real `HOME`, `repo_root`, the harness install location (directory holding the installed `squadron` package), `uv cache dir` output, the project's distribution name, and the code host owner/name. A factory `build_leak_rules(...)` takes each as a parameter (injected; it runs no command itself)
- [ ] Path collection from a `ToolCall`: file-tool path fields (`file_path`, `path`, `notebook_path`, `pattern` with a leading `/` or `~` only when the tool is a glob/grep, per the Task 13 shapes); for shell commands `shlex.split`, falling back to a token regex when quoting is unbalanced; absolute tokens and `~`-prefixed tokens; relative tokens containing `..` resolved against the tree. A path is a hit when it lies under the real `HOME`, the install location or the uv cache and outside the sandbox's own three directories
- [ ] Tests `tests/benchmark/test_leak_rule_paths.py`, parametrized, hitting and non-hitting: `Read` of `<repo_root>/src/x.py` hits; a path inside the tree's `.venv` does not; a path in the sandbox's `<id>.home` does not; `~/.ssh/config` hits; `cd .. && cat ../../other/file` (a `..` escape that resolves outside the tree) hits and `cat ./a/../b` (stays inside) does not; unbalanced quotes still extract tokens; the uv cache and install location hit; `/tmp/unrelated` does not (outside HOME)
  - [ ] Success: tests pass

### Task 20: Git, code-host and own-package rules (D7)
- [ ] In the same module(s): the git and code-host rule: any `gh` invocation; `git` with `-C`, `--git-dir` or `--work-tree` whose value resolves outside the tree; `git clone`, `fetch`, `pull`, `remote add`; a URL fetch (`curl`, `wget`, a fetch tool's `url` field) whose host and path name the case's repository. Match on parsed tokens (the program name and subcommand), never on substring search of the command line
- [ ] The own-package rule: an install or run of the project's distribution name through `pip install`, `uv pip install`, `uv add`, `uvx`, `uv tool` or `pipx`; match the distribution name as a whole token after normalizing `-`/`_`/case, ignoring version specifiers
- [ ] Tests `tests/benchmark/test_leak_rule_git_package.py`, parametrized: `gh issue view 3` hits; `git -C /elsewhere log` hits and `git -C ./sub log` does not; `git --git-dir=/x` hits; `git clone`, `git fetch`, `git remote add` hit and `git status`, `git diff`, `git log` do not; a `curl` of `https://github.com/<owner>/<repo>/issues/3` hits, a different repository does not; `uvx <dist>`, `pip install <dist>==1.0`, `uv tool install <dist>`, `pipx run <dist>` hit; `pip install requests` does not; a command that merely mentions the distribution name in an `echo` does not
  - [ ] Success: tests pass

### Task 21: `scan` and the verdict (D6, D7)
- [ ] `scan(source: TranscriptSource, home: Path, rules: LeakRules, *, expected_tool_calls: int | None) -> LeakScanResult`: `leaked` with up to 20 hits (rule, tool, excerpt ≤ 300 chars cut explicitly) when any rule hits; `scan_unavailable` with a `detail` when the source reports `problems` and no calls, when no transcript file exists, when a file does not parse, or when `expected_tool_calls` (from the run's usage records) is nonzero while zero calls were extracted; otherwise `no_leak_detected`. The result carries `rules_version = LEAK_RULES_VERSION` and `tool_calls_seen`. An empty result is never clean. Each `scan_unavailable` is logged at WARNING with its detail
- [ ] Tests `tests/benchmark/test_leak_scan.py` (the design's walkthrough step 7 file): a transcript with a `Read` of a file in the user's checkout is `leaked`; so is a `gh` call, a `git -C <outside>` call and a `uvx <project name>` call (each with the hit recorded); a clean transcript (fixture) is `no_leak_detected` with `tool_calls_seen > 0`; no transcript files, an unparseable file, and zero extracted calls with `expected_tool_calls=5` are each `scan_unavailable` with a WARNING; 25 hits record 20; `rules_version` is recorded; the fixture-driven tests use the Task 13 fixtures
  - [ ] Success: tests pass; `uv run pytest tests/benchmark -q` passes

**Commit**: `feat: add the transcript leak scan`

### Task 22: Config key, benchmark id, record ids (D4)
- [ ] `benchmark/bench_plan.py`: frozen `BenchConfig(alias, model, profile, effort_configured)` and `config_key(config) -> str` (canonical JSON of the four fields); `benchmark_id(set_name, set_version, config_keys, samples) -> str` = `bench-` + first 16 hex of sha256 of the canonical JSON of `(set name, set version, sorted config keys, samples)`; `replay_record_id(benchmark_id, case_id, config_key, sample) -> str` = `implreplay-<benchmark_id[6:18]>-<case_id[5:17]>-<sha256(config_key)[:8]>-s<n>`. Caps are not part of the identity
- [ ] Tests `tests/benchmark/test_bench_plan_ids.py`: ids are stable across calls and config order; changing samples, set version, alias, effort or profile changes the benchmark id; changing a cap input is not possible (no cap parameter); record ids have the exact segment lengths; two samples of one case and config differ only in the suffix; a case id shorter than 17 characters raises a clear error rather than slicing silently
  - [ ] Success: tests pass

### Task 23: Caps and the stated bound (D8)
- [ ] `benchmark/bench_caps.py`: `resolve_caps(run_cap_flag, per_replay_flag, config_cap) -> Caps`; the run cap is required (flag only, no config default); the per-replay cap comes from `--max-cost-per-replay` else `pipeline.max_cost_usd`; both through 947's `_positive_usd` rules (import the function; if it is private, add a public alias `positive_usd` in `run_spend.py` and use that). Refusals raise `BenchmarkRefusal(ValueError)` naming the missing cap and the flag or key that sets it
- [ ] `bench_plan.py`: `BenchmarkPlan` (pending replays in case-major, sample, config order; already-recorded count) built from the case set, configs, samples and the set of existing replay ids; `format_bound(plan, caps, bounded_profiles) -> str` producing the design's D8 block: the pending line, the headline `N × $per = $total, capped at run cap $X`, the overshoot line, and one `not bounded:` line per config outside the SDK-bounded set with its reason (`cost is checked only after each dispatch`, or `reports no cost`). The headline covers only SDK-bounded configs; the bounded set is a parameter (profiles with in-dispatch enforcement, defined once as a constant tuple holding `sdk`)
- [ ] Tests `tests/benchmark/test_bench_caps.py`: run cap missing refuses naming `--max-cost`; per-replay cap with neither source refuses naming `--max-cost-per-replay` and `pipeline.max_cost_usd`; zero, negative, bool and NaN values refuse; flag beats config; `format_bound` for the design's example (60 replays, 6 recorded, $1.50, run cap $40, `opus` bounded, `sol` not) matches the expected text exactly; an all-unbounded plan prints no headline figure; a fully recorded plan prints `pending 0`
  - [ ] Success: tests pass

### Task 24: Planning refusals (D5, D6, D8)
- [ ] `benchmark/case_runners.py` (new): the `CaseKindRunner` Protocol (`requalify(case, environment) -> Qualification | CandidateRejection`, `run(case, config, sandbox, caps, record_id) -> ProducerRun`) and a registry keyed by 421's `CaseKind` (`register_case_runner`, `case_runner_for(kind) -> CaseKindRunner | None`). Task 25 adds `FixCaseRunner` to this module
- [ ] `benchmark/bench_refusals.py`: `check_plan(cases, configs, runners, transcript_registry, auth_state)` raises `BenchmarkRefusal` for the first problem found, each message as the design words it: a config whose profile has no `TranscriptSource` (`profile <p> has no transcript source; its replays cannot be leak-scanned`); a profile the auth check has not answered yes for (names `sq benchmark auth-check`); a case kind with no registered `CaseKindRunner` (names the kind and says `slice` has none until 426); a fix case with no provenance issue ref (names the case). `--samples` absent with `benchmark.planned_samples` unset refuses naming both
- [ ] Tests `tests/benchmark/test_bench_refusals.py`: the registry returns a registered runner and `None` for an unregistered kind; one test per refusal with the exact fragment; a valid plan passes; the check never calls a runner or invoker (doubles that raise if called)
  - [ ] Success: tests pass

**Commit**: `feat: add benchmark identity, caps, the stated bound and planning refusals`

### Task 25: `CaseKindRunner` and `FixCaseRunner` invocation (D5)
- [ ] In `benchmark/case_runners.py` (Task 24 created the Protocol and registry) add `FixCaseRunner` and register it for the fix kind. `FixCaseRunner.requalify` calls only 422's `qualification_for` / `qualify_candidate`. `FixCaseRunner.run` writes `case.task_text` to `<id>.out/issue.md`, builds the argv from D5 exactly (absolute path of the installed `sq`, resolved once at harness start and injected; `-m <alias> --producer-only --max-cost <per-replay cap> -p issue-file=issue.md -p commit-to=current --io-dir <id>.out --run-id <record id>`, issue number from the case's provenance issue ref), runs it through the injected invoker with `cwd=<tree>` and `env=ScrubbedEnvironment(CredentialGrant.for_profiles([config.profile]))` and no timeout, and returns the process result
- [ ] `instruction_files(tree) -> tuple[tuple[str, str], ...]`: path (relative) and sha256 of each `CLAUDE.md`, `AGENTS.md` and `.claude/rules/**` file in the tree at the start commit, sorted by path
- [ ] Tests `tests/benchmark/test_fix_case_runner.py` with an injected invoker double: the argv equals the design's command exactly (alias, cap, params, io-dir, run id); `issue.md` holds the case text byte for byte; `cwd` and the scrubbed env are what the invoker received (no `GH_TOKEN`); `--max-cost` is always present; `instruction_files` lists nested rules files sorted with correct hashes and ignores other files; `requalify` delegates to 422 (patched `qualification_for`) and `replay_one` can call it through the Protocol; a second kind registered in a test registry runs without editing `bench_runner.py` imports
  - [ ] Success: tests pass

### Task 26: Outcome classification (D5 state read, D10)
- [ ] `benchmark/replay_outcome.py`: `classify_producer_run(process, state, head_before, head_after, issue_sha256) -> ProducerClassification` (`outcome`, `absence`, `failure_detail`, `run_id`, cost, turns, `effort_sent` and prompt identity read with 177's helpers in `replay/outcome.py`). Rows are checked top to bottom, first match wins, per the D10 table: `environment_failed` is raised before this function runs (caller), `no_run_state` (no readable state, or status still `running`), `frozen_text_mismatch` (the `fix-context` outputs do not show `issue_source: file` and the sha256 of `issue.md`), `cost_cap`, `blocked` (`awaits_human`), `committed`, `no_commit` (completed or refused with HEAD unchanged), `producer_failed`. `failure_detail` carries the failure kind and the stderr tail (bounded length, defined once)
- [ ] Tests `tests/benchmark/test_replay_outcome.py`, one test per row with its absence class using run-state fixtures built with `RunState`/`StepState`: no state; state still `running` (signal kill); sha mismatch; `failure_kind: cost_cap`; `awaits_human`; completed with HEAD moved; completed with HEAD unchanged; a `fix_report` refusal with HEAD unchanged is `no_commit`; a `stall` failure and a turn-timeout failure are `producer_failed` with the kind in the detail; precedence: a cost-capped run whose frozen text mismatched is `frozen_text_mismatch`
  - [ ] Success: tests pass

**Commit**: `feat: add the fix-case runner and producer outcome classification`

### Task 27: `replay_one` (design Data Flow, D10, D11)
- [ ] `benchmark/replay_one.py`: `replay_one(case, config, sample, deps) -> ImplementationReplay | CaseDrop`. Steps: open the sandbox at `start_sha` through the injected factory (a failure here records `environment_failed`, harness); `runner.requalify` (cached per (case, environment digest) in a small injected cache; a rejection returns a `CaseDrop` with the reason and `environment_digest`, nothing dispatched); run the producer; read run state through `StateManager(runs_dir=<id>.home/.config/squadron/runs)` (injected reader); `head_before`/`head_after` through the injected process runner; `git diff --binary <start_sha> HEAD` in the tree (uncommitted changes ignored); `DiffSidecars.put`; transcript scan (Task 21) with `expected_tool_calls` from the usage records; build the record. A leak result other than `no_leak_detected` sets `absence=harness` whatever the outcome, and the diff is still stored. `deps` is a dataclass of injected collaborators (sandbox factory, invoker, store, state reader, transcript registry, process runner, clock)
- [ ] A failure in `git diff` or the sidecar write raises `ReplayStoreError` after logging at ERROR with the stderr tail; the sandbox is kept (`handle.keep()`); `replay_one` does not write a record in that case. Removal of the sandbox after a written record respects `--keep`
- [ ] Tests `tests/benchmark/test_replay_one.py` with doubles (no model, no git outside fixtures): `committed` writes a record with `DiffRef`, commit sha, environment, prompt, instruction files, cost and turns and a record under 8 KB; each other D10 outcome is produced end to end (cost cap, blocked, no_commit via `fix_report`, producer_failed via stall, no_run_state via kill, frozen mismatch, environment failure); a leaked transcript on a `committed` run records harness absence with the diff kept; `scan_unavailable` likewise; re-qualification rejection returns a `CaseDrop` and the invoker double is never called; `git diff` failure after a successful run raises, logs ERROR, keeps the sandbox, writes no record; an empty diff with a moved HEAD is `committed` with a zero-byte `DiffRef`; sandbox is removed after success and kept with `keep=True`
  - [ ] Success: tests pass

**Commit**: `feat: add the single-replay driver`

### Task 28: Benchmark lock, interruption and sweep (D4, State Management)
- [ ] `benchmark/bench_runner.py` part 1: `begin_benchmark(...)`: take `<benchmark root>/<benchmark_id>.lock` (the same process lock 177's sandboxes use; a second live invocation refuses with a message naming the benchmark id and the holder); when the stored `BenchmarkRun` is `running` and the lock was free, set it `interrupted` and report it before planning, then set it back to `running` with the new caps; call 421's benchmark orphan sweep and report how many sandboxes it removed; write `BenchmarkRun(status=running)` only after the bound has been printed (the caller passes the printer; order is asserted)
- [ ] Tests `tests/benchmark/test_bench_runner_begin.py`: second invocation while the lock is held refuses and the first is unaffected; a `running` record with a free lock becomes `interrupted` and is reported, then `running`; a `running` record with a held lock is not touched; the sweep count is reported; the bound is printed before `write_run(running)` and before any invoker call (an ordered event log from doubles)
  - [ ] Success: tests pass

### Task 29: Schedule, spend cap and resume (D4, D8)
- [ ] `bench_runner.py` part 2: `run_benchmark(plan, deps, caps) -> BenchmarkRun`: iterate case-major, then sample, then config; before each replay stop with `status=partial` when known spend of this invocation is at or over the run cap; unpriced replays add nothing and are counted in `unpriced_replays`; a replay with a record is skipped whatever its outcome, including harness absences; final status `complete` or `partial`; `spent_usd` accumulates across invocations
- [ ] Tests `tests/benchmark/test_bench_runner_run.py`: order is case-major, sample, config (assert the invoker call sequence); cap reached after the first replay (spend = cap) stops dispatching, keeps records, `partial`; a replay may overshoot (spend 0.9 then a 1.5 replay with cap 1) and the next replay is not started; rerun with a higher cap skips recorded replays and continues; `committed`, `no_commit` and harness-absent records are all skipped; unpriced replays are counted and add no spend; `spent_usd` adds up across two invocations
  - [ ] Success: tests pass

### Task 30: Case filter, case drops, harness retry and store failure (D4, D10)
- [ ] `--case` filtering in the plan (does not change the benchmark id); `CaseDrop`s from `replay_one` collected on the `BenchmarkRun` once per case and reported, with none of that case's remaining replays attempted; a `ReplayStoreError` stops the benchmark with status `interrupted` and exit 1, logging at ERROR; `--retry-harness`: before planning, `delete_replays` for every recorded replay whose absence is `harness`, and report how many
- [ ] Tests (extend `tests/benchmark/test_bench_runner_run.py`): `--retry-harness` removes only harness records and reports the count; a dropped case is reported once and none of its replays run; `--case` limits the plan and its records count toward the full benchmark id; a store write failure stops the run, logs ERROR and leaves status `interrupted`
  - [ ] Success: tests pass; `uv run pytest tests/benchmark -q` passes

**Commit**: `feat: add the benchmark runner with caps, resume and interruption handling`

### Task 31: Interruption by a real signal
- [ ] `tests/benchmark/test_bench_interrupt.py`: start `run_benchmark` in a child Python process (`python -I`, `subprocess`, with fake deps from a helper module under `tests/benchmark/support.py`) that blocks inside the second replay, kill it with `SIGKILL`, then run `begin_benchmark` in the parent against the same store: the earlier run is reported `interrupted`, the orphaned sandbox directory (created by the child) is swept and counted, and a following `run_benchmark` runs only the remaining replays
  - [ ] Success: the test passes; it leaves no processes or directories behind (`tmp_path` only)

**Commit**: `test: cover benchmark interruption with a killed process`

### Task 32: `sq benchmark run` options, resolution and refusals (API Contracts, D8)
- [ ] `cli/commands/benchmark.py` (421/422 created it; if it passes ~300 lines, put the new command in `cli/commands/benchmark_run.py` and register it from there): `run --set NAME [--set-version N] --model ALIAS (repeatable) [--samples K] --max-cost USD [--max-cost-per-replay USD] [--case CASE_ID …] [--retry-harness] [--keep]`. Resolve the case set version, aliases to models and profiles (model alias resolution), the harness config and the installed `sq` path; call `check_plan`, `resolve_caps`, `begin_benchmark`, `run_benchmark`. Every refusal prints `Error: …` at the process boundary with no stack trace and exits 1
- [ ] `--samples`: when absent, read `benchmark.planned_samples` (422's key, through its constant in `config/keys.py`); when that is unset too, refuse naming `--samples` and `benchmark.planned_samples`; the flag wins over the key; a non-positive value refuses
- [ ] Tests `tests/benchmark/test_benchmark_run_command.py` (Typer `CliRunner`, injected deps through the command's dependency seam): missing `--max-cost` exits 1 naming it; no per-replay cap exits 1 naming both sources; an OpenAI-compatible alias exits 1 with the transcript-source message; `--samples` absent uses the config key (the plan's replay count shows it), the flag wins over the key, neither refuses naming both, `0` refuses; a second `--model` doubles the plan; `--help` lists every option
  - [ ] Success: tests pass; `tests/cli/test_help.py` and `tests/cli/test_command_surface.py` pass

### Task 33: `sq benchmark run` output, exit codes and `--keep` (API Contracts, D8)
- [ ] Print the bound (Task 23) before any dispatch, one line per replay (record id, outcome, leak verdict, cost), then the summary: counts by outcome, absence class and leak verdict, total spend, unpriced count, drops. Exit 0 complete, 2 partial, 1 harness stop. When the first replay of a profile ends `no_run_state`, print a reminder to run `sq benchmark auth-check`, once per profile. With `--keep`, print the kept paths and the warning that the home holds symlinks to the user's auth files (421 D8)
- [ ] Tests (extend `tests/benchmark/test_benchmark_run_command.py`): the bound is on stdout before the first invoker call (event log); a full run exits 0 and prints the summary; a capped run exits 2; a store failure exits 1; `--keep` prints the paths and the warning; the first `no_run_state` prints the auth-check reminder once per profile
  - [ ] Success: tests pass

**Commit**: `feat: add sq benchmark run`

### Task 34: `sq benchmark replay-show` (API Contracts)
- [ ] `replay-show RECORD_ID [--diff]`: prints the record (all fields, leak hits with rule, tool and excerpt, environment digest, prompt identity, `instruction_files`, `effort_sent`); with `--diff` prints the sidecar diff via `DiffSidecars.get`. An unknown id exits 1 naming it; a tampered or missing sidecar exits 1 with the `MetrologyStoreError` message, no stack trace
- [ ] Tests `tests/benchmark/test_replay_show_command.py`: shows a stored record including leak hits; `--diff` prints the stored diff exactly; tampered sidecar exits 1 with the hash mismatch text; unknown id exits 1; a record without a diff (`diff=None`) with `--diff` exits 1 saying there is none
  - [ ] Success: tests pass

**Commit**: `feat: add sq benchmark replay-show`

### Task 35: `/sq:benchmark` subcommands
- [ ] `commands/sq/benchmark.md` (422 created it): add `run` and `replay-show` with the same arguments and no interpretation, so output is identical to the CLI (the form of `commands/sq/replay.md`)
- [ ] Parity test `tests/benchmark/test_benchmark_md_parity.py`: every option of the `run` and `replay-show` Typer commands appears in `benchmark.md`, and the file contains no behavior text beyond running `sq benchmark $ARGUMENTS`
  - [ ] Success: test passes

**Commit**: `feat: add run and replay-show to the /sq:benchmark command`

### Task 36: Verification walkthrough (design Verification Walkthrough)
Scratch work goes in new directories under `/tmp`; nothing is pushed. LLM spend and live runs are pre-authorized. Steps 3–7 need a 422 case set (`sq benchmark fix-cases build --set fixes`) and yes answers from `sq benchmark auth-check` for the aliases used; a missing prerequisite that no task here can produce is written as `BLOCKED:` with the evidence.
- [ ] Gates on the whole branch: `ruff format --check`, `ruff check`, `pyright` (zero errors), `uv run pytest -q`
  - [ ] Success: all clean; failures fixed, or recorded as already failing on the target with the test names
- [ ] Step 1 (producer-only on `P6`), on a scratch slice branch with a design and task file: `sq run P6 <slice> --producer-only --dry-run`, then `--max-cost 5`, `sq runs show <run-id>`, `git log -1 --format='%s'`
  - [ ] Success: the dry run lists `set_slice → check_decisions → set_phase → build_context → dispatch → commit`; the run prints the stop line naming skipped steps; run state has no review action; the commit is the implementation commit; no DEVLOG commit or merge follows
- [ ] Step 2 (refusals): `sq run P6 <slice> --producer-only --from close-out`, `sq run P456 <slice> --producer-only`, and `sq run P6 <slice> --producer-only` from the target branch
  - [ ] Success: all exit 1; the second names `design`, `tasks` and `implement`; the third names the branch to check out and spends nothing
- [ ] Step 3 (caps required): the two refusals from the design's step 3 with `pipeline.max_cost_usd` unset
  - [ ] Success: first names `--max-cost`; second names `--max-cost-per-replay` and `pipeline.max_cost_usd`
- [ ] Step 4 (small run): `sq benchmark run --set fixes --model opus --model sol --samples 1 --max-cost 10 --max-cost-per-replay 2 --case <case-id>` then `sq benchmark replay-show <record-id> --diff`
  - [ ] Success: the bound prints first (with `sol` listed `not bounded`); two replay lines; the diff is the producer's commit against the start commit; the record shows environment digest, prompt identity, `instruction_files` and `effort_sent`
- [ ] Step 5 (run cap): `--samples 2 --max-cost 1 --max-cost-per-replay 1`, then rerun with `--max-cost 10`
  - [ ] Success: first run `partial`, exit 2; rerun skips recorded replays and continues
- [ ] Step 6 (interruption): an agent cannot press Ctrl-C, so use the signal Task 31 uses. Start step 5's rerun with the Bash tool in the background; poll until a new sandbox directory appears under the benchmark root (`ls`), then `kill -KILL` the `sq benchmark run` process and its running `sq run` child (find both with `pgrep -fl 'sq '`); run the command again
  - [ ] Success: `interrupted` reported, one orphaned sandbox reported and removed, the run resumes
- [ ] Step 7 (leak detection): `uv run pytest tests/benchmark/test_leak_scan.py -v`; run step 4 with `--keep` and inspect `<id>.home/.claude/projects/`
  - [ ] Success: planted-read tests pass; the kept transcript is the one the scan read; delete the kept sandbox (`rm -r` of the paths the command printed) afterwards
- [ ] Any defect the walkthrough found in this slice's code is fixed here with a test and recorded in the DEVLOG; there is no commit marker here, so the fixes are committed with Task 37's commit

### Task 37: Final validation and DEVLOG
- [ ] Run `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite once; fix any failure at its cause
  - [ ] Success: all clean; `tests/replay/` and existing `sq run` tests pass unchanged
- [ ] Confirm no source file added or changed by this slice exceeds ~300 lines (`wc -l`; likeliest: `benchmark/leak_scan.py`, `benchmark/bench_runner.py`, `metrology/benchmark_models.py`, `metrology/benchmark_store.py`, `cli/commands/benchmark.py`); split by concern where one does
- [ ] Update the slice design: Component Structure and Patterns with names the tasks added (`case_runners.py`, `ProducerOnlyError`, `ProducerOnlySelection`, `BenchmarkRefusal`, `ReplayStoreError`, `bench_caps.py`, `bench_refusals.py`, `replay_outcome.py`, `leak_paths.py` if created, `run_producer_only.py`); and the design gaps listed in the Context Summary
- [ ] DEVLOG: implementation entry per the Session State Summary guidance (what was done, the transcript spike answers, issue number from Task 2, verification results, next: 425); mark the slice design `status: complete` and tick its slice-plan entry when every task above is checked, dropped items `[x]` with a note
  - [ ] Success: slice design and slice plan reflect completion; every task above is checked

**Commit**: `feat: complete producer-only replay runner slice`
