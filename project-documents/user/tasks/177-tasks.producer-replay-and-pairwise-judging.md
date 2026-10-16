---
docType: tasks
slice: producer-replay-and-pairwise-judging
project: squadron
lld: user/slices/177-slice.producer-replay-and-pairwise-judging.md
dependencies: [175, 176, 320]
projectState: >
  Slice 177 design approved after review (20261016). 176 shipped `sq stats producers` (observed
  producer effectiveness), per-round run state and `GitHistory`; 320 shipped the metrology store.
  This slice adds controlled replays (`sq replay run|judge|report`), two metrology record types,
  and prompt identity on every dispatch. Controlled half of #210.
dateCreated: 20261016
dateUpdated: 20261016
status: not_started
---

## Context Summary

- Working on **177 producer-replay-and-pairwise-judging**. Each producer config regenerates a past slice design or task breakdown in a history-free sandbox at the original start point, under a fixed reviewer; a blind order-swapped pairwise judge compares first drafts; a Bradley-Terry report combines quality, cost, time and failure rate per phase.
- Decisions D1–D10, the API contracts, the D7 report shape, the UI layout and the D10 failure table live in the slice design. Tasks reference them and do not repeat them. Use the design's texts (errors, footer lines, notes) verbatim.
- Key files: new `replay/{start_point,sandbox,runner,judge,bradley_terry,report}.py`, `data/replay/pairwise-judge.md`, `cli/commands/replay.py`, `cli/replay_views.py`, `commands/sq/replay.md`; changed `metrology/{models,store}.py`, `pipeline/actions/{cf_op,dispatch}.py`, `pipeline/state.py`, `cli/commands/run.py`, `stats/producer_report.py`, `cli/stats_producer_views.py`, `codehost/worktree.py`, `config/keys.py`.
- Implementation choices not spelled out in the design, fixed here so no task has to decide them:
  - **Record payloads in a new module.** `metrology/models.py` is 294 lines. `ProducerReplay`, `PairwiseJudgment`, `ReplayPhase`, `ReplayOutcome`, `PairOutcome`, `ProducerConfigRef`, `ModelRef`, `JudgeRef`, `PromptIdentity` and `JudgeCall` go in new `metrology/replay_models.py`. The `RECORD_TYPE_*` constants and the optional sibling fields on `MetrologyRecord` stay in `models.py` (320's pattern).
  - **One list loop in the store.** `metrology/store.py` (357 lines) repeats the glob / skip-unreadable-with-WARNING loop in four `list_*` methods. Extract a private `_iter_records()` first, move the existing methods onto it with unchanged behavior, then build the new methods on it.
  - **Shared process lock.** `WorktreeLock`, `_process_start_time`, `_current_process_start_time`, `_read_lock` and `_is_orphan` in `codehost/worktree.py` do not depend on `PullRequestRecord`, but they are private. Move them to new `core/process_lock.py` under public names (`ProcessLock`, `read_lock`, `is_orphan`, `current_process_lock`); `worktree.py` imports them. No copy.
  - **Split task files.** For `tasks`, an original artifact split as `{index}-tasks.{name}-1.md`, `-2.md`, … is one artifact: the first draft is every matching file in the adding commit, concatenated in suffix order; `slice_name` drops the `-N` suffix. Replayed first drafts are read the same way.
  - **Subprocess injection.** Sandbox git/cf/`ps` calls go through the existing `core.process_runner.ProcessRunner`. The `sq run` child has no wall-clock bound (D10: 174's stall bounds end a hang), so the runner takes a separate injected `SqRunInvoker` callable `(argv, cwd) -> ProcessResult`; production wraps `subprocess.run` with captured output and no timeout.
  - **Config reads only in the CLI.** `metrology.min_evidence_n` and `metrology.judge_timeout_s` are read with `get_typed_config` in `cli/commands/replay.py` and passed into the cores.
  - **CLI module sizes.** `cli/commands/run.py` is 1361 lines; this slice adds only the hidden option and the `new_run_id` plumbing there. Replay rendering lives in `cli/replay_views.py`, not in the command module.
- Every task ends with `ruff format`, `ruff check`, `pyright` (zero errors), the touched tests, and a commit on the slice branch with the subject the task names.
- Effort: 4/5. Last entry in the 140 slice plan; no next slice is planned there. #210 can close when this slice merges (Phase 7).

## Tasks

### Spike: slice resolution at a design start point (D2 risk)

- [x] **Task 1: Run `sq run P4 176` in a hand-built sandbox** (effort 2)
  - [x] Read the target (`cf config get git.integration_branch`, empty means `main`) and create `177-slice.producer-replay-and-pairwise-judging` from it
  - [x] Find the commit that first added `project-documents/user/slices/176-slice.*.md` (`git log --diff-filter=A --format=%H -- <path>`) and its first parent
  - [x] Build the sandbox by hand with the four D3 git commands in a scratch directory under `/tmp`; register it with `cf init --lite --no-ide --name replay-spike`
  - [x] In the sandbox, run `sq run P4 176 -m <cheapest alias in models.toml> -p review-model=<same> -p max-revisions=1` (the loop rejects 0: `loop.max must be a positive integer`, `pipeline/loop_config.py:108`)
  - [x] Record in this task, under a `Result:` line: the start sha, whether the slice resolved, and the exact error text if it did not
  - [x] Also record which step resolves the slice (the `set_slice` cf operation or earlier) and the cheapest command that reproduces that resolution without a dispatch. Task 21 runs it as its pre-dispatch check
  - [ ] Clean up: `cf project rm replay-spike`, delete the directory (cf project removed; /tmp/replay-spike directory deletion left to PM)
  - [x] If the slice did not resolve: STOP and return the evidence to the Project Manager. Do not start Task 2.
  - [ ] Commit (task file only): `docs: record slice 177 start-point resolution spike`
  - **Result:** start sha `bca771926e89d9ac7c753d9c88a84aa4b1f83ac7` (first parent of `f3d652e0`, the commit that first added the 176 design). `sq run P4 176 -m haiku -p review-model=haiku -p max-revisions=1` **resolved the slice and completed** (design-0 PASS, loop-1, summary-2) once two sandbox settings were in place. The 176 plan entry exists at the start point, so cf resolves `176` from the plan and the missing design file does not matter. Two failures on the bare sandbox, each fixed by one setting:
    1. `cf set slice 176: No file matching index '176' for field 'fileSlice'. No slice plan is set.` — a fresh `cf init --lite` project has no slice plan. Fix: `cf set arch 140` (the initiative index) before the run.
    2. `planning commit for slice 176 on replay/spike; expected main` — the git-environment guard compares the branch to `git.integration_branch`. Fix: `cf config set git.integration_branch replay/<id>` in the sandbox.
  - **Resolving step:** the `set_slice` cf operation (`cf set slice <index>`). Dispatch-free pre-check for Task 21, run in the sandbox after `cf set arch <initiative>`: `cf set slice <index>`; exit 0 means resolved (cf prints its `Updated slice =` confirmation on stderr, not stdout). Neither setting is in the slice design (D3/D4); Task 15 adds both to the sandbox setup. The initiative index comes from the slice plan file name (`<initiative>-slices.*`) at the start point.
  - **Success:** `Result:` line records a resolved slice at slice 176's real start point

### Prompt identity (D8)

- [x] **Task 2: `cf_version` and `guide_version` in `build_context` outputs** (effort 2)
  - [x] The cf client reads `cf --version` once per client instance and caches it; a failed read is an error, not `None`
  - [x] In `pipeline/actions/cf_op.py`, the `build_context` operation adds `cf_version` and `guide_version` to its outputs; `guide_version` is the stripped content of `<cwd>/project-documents/ai-project-guide/.context-forge-guide-version`, or `None` when absent
  - [x] Define the guide-version relative path once, as a constant
  - [x] Commit: `feat: record cf and guide versions on build_context`
  - **Success:** a `build_context` action's outputs carry both keys; other cf operations are unchanged

- [x] **Task 3: Test `build_context` version keys** (effort 1)
  - [x] Version file present → its stripped content; absent → `None`
  - [x] `cf --version` runs once across two `build_context` calls on one client
  - [x] Commit: `test: cover build_context version keys`
  - **Success:** tests pass, zero pyright errors

- [x] **Task 4: `metadata["prompt"]` on every dispatch** (effort 3)
  - [x] Add a `PromptSource` enum (`build_context`, `feedback`, `explicit`, `review_findings`) in `pipeline/actions/dispatch.py` (lives in pipeline/actions/prompt_identity.py)
  - [x] `_resolve_prompt` (`dispatch.py:621`) returns the delivered prompt and its `PromptSource` (a small frozen dataclass); update both callers (`dispatch.py:571`, `dispatch.py:841`)
  - [x] Each dispatch writes `metadata["prompt"]` per D8: `sha256` over the text after `_apply_override` and `_apply_pre_emption_fragment`, `source`, `squadron_version` (from `squadron.__version__`), and `cf_version` / `guide_version` copied from the latest `build_context` outputs only when the source is `build_context`, else `None`
  - [x] No run state schema version bump
  - [x] Commit: `feat: record prompt identity on every dispatch`
  - **Success:** every dispatch's metadata carries the five D8 fields

- [x] **Task 5: Test prompt identity** (effort 2)
  - [x] One test per `PromptSource` branch asserts `source` and that `sha256` equals the hash of the delivered text
  - [x] An override or pre-emption fragment changes `sha256`
  - [x] Non-`build_context` sources carry `cf_version` and `guide_version` as `None`
  - [x] Existing dispatch tests pass unchanged apart from the added key
  - [x] Commit: `test: cover dispatch prompt identity`
  - **Success:** tests pass, zero pyright errors

- [x] **Task 6: Prompt-identity footer in `sq stats producers`** (effort 2)
  - [x] `ProducerReport` (`stats/producer_report.py:72`) gains `prompt_identified: int` (units whose dispatch carries `metadata["prompt"]`), `units: int`, and `guide_versions: int` (distinct non-`None` guide versions)
  - [x] `cli/stats_producer_views.py` prints the D8 footer line `k of n units carry prompt identity; m guide versions`; `--json` carries the three fields
  - [x] The producer key is unchanged (D8: still pooled)
  - [x] Commit: `feat: report prompt identity coverage in sq stats producers`
  - **Success:** the footer appears; existing rows are unchanged

- [x] **Task 7: Test the prompt-identity footer** (effort 1)
  - [x] Mixed run set (units with and without `metadata["prompt"]`, two guide versions) → correct k, n, m in text and JSON
  - [x] Pre-177 runs only → `0 of n`
  - [x] Commit: `test: cover sq stats producers prompt identity footer`
  - **Success:** tests pass, zero pyright errors

### Metrology record types (D9)

- [x] **Task 8: Replay and judgment payload models** (effort 2)
  - [x] Create `metrology/replay_models.py` with the D9 `ProducerReplay` fields and the `PairwiseJudgment` fields listed under D9; `ReplayPhase` (`DESIGN`, `TASKS`), `ReplayOutcome` (`ACCEPTED`, `EXHAUSTED`, `FAILED`) and `PairOutcome` (`A`, `B`, `TIE`, `INCONSISTENT`, `INVALID`) are enums (ProjectId/ProjectIdSource moved to metrology/project_id.py, re-exported from models.py, to avoid an import cycle; PairwiseJudgment also carries project_id, which list_judgments filters on)
  - [x] `JudgeCall` holds one call's pick (`A`, `B`, `TIE`, `INVALID`) and raw tail; `JudgeRef` holds alias, model, prompt hash
  - [x] Contestant references in `PairwiseJudgment.a` / `.b` are a replay record id or `original:<sha>`; define the `original:` prefix once
  - [x] Add `RECORD_TYPE_PRODUCER_REPLAY` and `RECORD_TYPE_PAIRWISE_JUDGMENT` and two optional sibling fields to `MetrologyRecord` in `models.py`; `_SCHEMA_VERSION` stays 1
  - [x] Commit: `feat: add producer_replay and pairwise_judgment record models`
  - **Success:** models validate; `models.py` stays near 300 lines

- [x] **Task 9: Extract the store's list loop** (effort 1)
  - [x] Add private `MetrologyStore._iter_records()` yielding `(record_id, MetrologyRecord)` and skipping unreadable files with the existing WARNING
  - [x] Move `list_graduations`, `list_audit_runs`, `list_noise_floors` and `list_samples` onto it with unchanged behavior
  - [x] Run `pytest tests/metrology -q`
  - [x] Commit: `refactor: share the metrology store record scan`
  - **Success:** existing metrology tests pass unchanged

- [x] **Task 10: Replay and judgment store methods** (effort 2)
  - [x] Add `generate_replay_id` (`replay-{YYYYMMDD}-{uuid8}`) and `generate_judgment_id` (`pair-{YYYYMMDD}-{uuid8}`) beside the existing id generators
  - [x] Add `write_replay`, `list_replays(project_id, phase=None, replay_set=None)`, `write_judgment`, `list_judgments(project_id, phase=None, judge=None)` on `_iter_records`; `judge` matches on the full `JudgeRef` (alias, model, prompt hash) (list_replays returns (record_id, ProducerReplay) pairs because judgments reference replay ids; list_judgments returns PairwiseJudgment values; both take project_id as a required str)
  - [x] Commit: `feat: store producer replays and pairwise judgments`
  - **Success:** records round-trip through the store

- [x] **Task 11: Test the new record types** (effort 2)
  - [x] Write/list round-trip for both types, including every filter
  - [x] A judgment with a different prompt hash is excluded by the `judge` filter
  - [x] An unreadable sibling is skipped with a WARNING (`caplog`)
  - [x] An existing metrology fixture file (no new fields) loads unchanged
  - [x] Commit: `test: cover replay and judgment records`
  - **Success:** tests pass, zero pyright errors

### Start point (D2)

- [x] **Task 12: `resolve_start_point`** (effort 2)
  - [x] Create `replay/start_point.py` with `StartPoint` and `resolve_start_point(phase, index, history)` per the API contract; the D2 path patterns are defined once, keyed by `ReplayPhase` (the adding commit is the earliest one adding a matching file directly in the artifact directory, found by scanning commits_touching oldest-first rather than GitHistory.first_added, so an archive/ copy can never be chosen)
  - [x] Original first draft from `GitHistory.show` at the adding commit; split task files per the Context Summary rule
  - [x] `slice_name` from the original file name
  - [x] Errors per D10 rows 1–2 (`StartPointError` subclasses carrying the pattern or sha)
  - [x] Commit: `feat: resolve replay start points from git history`
  - **Success:** returns the adding commit, its first parent and the first-draft text

- [x] **Task 13: Test start-point resolution** (effort 2)
  - [x] Fixture repo (in `tmp_path`): adding commit found, first parent returned, first draft is the content at the adding commit even after later edits
  - [x] A later file under `user/slices/archive/` with the same index is not matched
  - [x] Split task files `-1` and `-2` → concatenated draft, suffix-free slice name
  - [x] No adding commit → error naming the pattern; root commit → error
  - [x] Real history: slice 176 design resolves to the start sha recorded in Task 1
  - [x] Commit: `test: cover replay start-point resolution`
  - **Success:** tests pass, zero pyright errors

### Sandbox (D3)

- [x] **Task 14: Extract the process lock to `core/process_lock.py`** (effort 2)
  - [x] Move the five helpers named in the Context Summary to `core/process_lock.py` under public names; `codehost/worktree.py` imports them; no behavior change (public names: ProcessLock, process_start_time, current_process_lock, read_lock, is_orphan, plus write via ProcessLock.to_json(); worktree.py keeps a thin _current_process_lock that re-raises the core ProcessIdentityUnresolvable as the codehost ProcessIdentityUnresolvableError; WorktreeLock is removed in favor of ProcessLock; helper tests live in tests/core/test_process_lock.py and the worktree tests were updated for the new names)
  - [x] Move their existing tests beside the new module if they test the helpers directly
  - [x] Run `pytest tests/codehost tests/core -q`
  - [x] Commit: `refactor: extract process lock liveness to core`
  - **Success:** existing worktree and lock tests pass unchanged

- [x] **Task 15: `ReplaySandbox` and `sweep_orphans`** (effort 3)
  - [x] Create `replay/sandbox.py`: `ReplaySandbox(start_sha, replay_id, repo_root, runner)` context manager running the D3 git commands, then `cf init --lite --no-ide --name replay-<replay_id>`, with the `<dir>.lock` written first; root `~/.config/squadron/replays/` defined once
  - [x] After `cf init`, the sandbox runs `cf config set git.integration_branch replay/<replay_id>` (the planning-commit guard otherwise halts `sq run`) and `cf set arch <initiative>`, the initiative index is the file-name prefix of the slice plan (`planning_docs.plan_file_for`) that lists the slice at the start point, since a project has many plans; no plan lists it → `SandboxError` naming the slice and start sha, before anything is registered with cf. Both from the Task 1 spike, defined once as the sandbox's cf setup. `ReplaySandbox` therefore also takes `slice_index`
  - [x] A start point containing `.gitmodules` raises an error naming it (D10). Refined: only a `.gitmodules` that declares a `[submodule` entry raises, because squadron tracks an empty `.gitmodules` and a bare file check would refuse every squadron replay
  - [x] Failed `git fetch` / `cf init` raises `SandboxError` carrying the command's stderr; the partial sandbox is removed
  - [x] On exit (normal, error, `KeyboardInterrupt`): `cf project rm`, delete the directory and lock; a cleanup failure logs WARNING naming the path or project and does not raise
  - [x] A `keep()` method suppresses cleanup (used by the runner on store-write failure, D4)
  - [x] `sweep_orphans(runner)` per D3: removes dirs with a missing or dead lock and `replay-*` cf projects whose path is gone; skips live locks; never raises; WARNING per removal or failed removal
  - [x] Commit: `feat: add history-free replay sandbox with orphan sweep`
  - **Success:** a sandbox holds exactly one commit and is gone after exit

- [x] **Task 16: Test the sandbox** (effort 2)
  - [x] Against a real fixture repo with a fake `cf` via the injected runner: the sandbox has one commit, `git log --all` shows nothing later, the branch is `replay/<replay_id>`
  - [x] Cleanup runs on normal exit, on a raised error, and on `KeyboardInterrupt`; `keep()` leaves the directory
  - [x] `.gitmodules` at the start point → error; failed fetch → `SandboxError` with stderr, no directory left
  - [x] Failed `cf project rm` → WARNING, no raise
  - [x] Sweep: dead lock removed, missing lock removed, live lock kept, stale `replay-*` project removed, each with a WARNING
  - [x] Commit: `test: cover replay sandbox and orphan sweep`
  - **Success:** tests pass, zero pyright errors

### Hidden `--run-id` (D4)

- [x] **Task 17: Fresh run under a chosen id** (effort 2)
  - [x] `StateManager.init_run` (`pipeline/state.py:332`) raises `FileExistsError` when a file for the given `run_id` exists
  - [x] `_run_pipeline` (`cli/commands/run.py:263`) gains `new_run_id`, passed to `init_run` on the fresh-run path; both `new_run_id` and `run_id` → `ValueError`
  - [x] Add hidden `--run-id` to `sq run`; combining it with `--resume` is a usage error (the Typer parameter is named new_run_id and the flag is --run-id; a FileExistsError from a taken id exits 1 with the message)
  - [x] Commit: `feat: add hidden --run-id to sq run`
  - **Success:** `sq run ... --run-id X` writes run state `X`; a second use of `X` fails

- [x] **Task 18: Test `--run-id`** (effort 1)
  - [x] `init_run` with an existing id → `FileExistsError`; without an id → unchanged
  - [x] `_run_pipeline` with `new_run_id` creates that file; with both ids → `ValueError`
  - [x] CLI: `--run-id` with `--resume` → non-zero exit; `--run-id` absent from `--help`
  - [x] Commit: `test: cover sq run --run-id`
  - **Success:** tests pass, zero pyright errors

### Runner (D4)

- [x] **Task 19: Read a replay outcome from run state** (effort 3)
  - [x] In `replay/runner.py`, a pure `read_outcome(state, sandbox_git, artifact_pattern)` maps run state to the D4 table's `outcome`, `rounds`, `failure_class` and `first_verdict`; acceptance uses `LoopCondition.REVIEW_CONCERNS_OR_BETTER`, not a verdict literal (lives in replay/outcome.py as read_outcome(state) -> OutcomeReading, with no sandbox_git or pattern arguments, because it is pure over run state; failure kinds come from a new failure_kind stamp, commit 5ff784c3, since failures had no structured signal; this task also found and fixed a stats defect, commit bf636819)
  - [x] Failure classes (`dispatch_error`, `stall`, `no_artifact`, `other`, `no_run_state`) are an enum or constants defined once
  - [x] First draft from the sandbox commit that first added the artifact; final text from the working file. Moved to Task 21: it needs git and the sandbox files, and `read_outcome` is pure over run state (done in Task 21 as replay/drafts.py read_drafts, tested in tests/replay/test_drafts.py)
  - [x] Cost, priced k of m and LLM-action counts from `action_usage_row` / `usage_totals` over every round of the phase and loop steps
  - [x] Prompt identity and `task_prompt` (`build_context` stdout) from the run state; effort sent from the producer dispatch's `UsageRecord.effort`
  - [x] Commit: `feat: read replay outcomes from run state`
  - **Success:** each D4 table row maps to the right outcome

- [x] **Task 20: Test outcome reading** (effort 2)
  - [x] One test per D4 table row, including paused-at-exhaust-checkpoint → `exhausted` with rounds = cap + 1
  - [x] Failed step with a stall error → `stall`; 945 post-condition failure → `no_artifact`
  - [x] Cost sums every round; an unpriced model gives `priced` k < m and no $0
  - [x] Commit: `test: cover replay outcome reading`
  - **Success:** tests pass, zero pyright errors

- [x] **Task 21: `run_replay_set`** (effort 3)
  - [x] Read the drafts (moved from Task 19): the first draft is the artifact's text at the sandbox commit that first added it, via `resolve_start_point(phase, index, <GitHistory of the sandbox>)`; the final text is the same file(s) in the sandbox working tree, split task files concatenated in numeric suffix order. Missing → `None`, never an empty string (run_replay_set takes the request, the StartPoint and ReplayDeps, plus confirm and new_replay_id callables; build_plan is separate)
  - [x] Compute `replay_set` per D9; choose a run id per config
  - [x] Sweep orphans, then build the plan (start commit, configs, reviewer, cap, LLM-call bound = configs × 2 × (1 + cap), per design D4); the caller confirms it before any sandbox is created
  - [x] Per config, in order: `ReplaySandbox`; invoke `sq run P4|P5 <index> -m <alias> -p review-model=<reviewer> -p max-revisions=<n> --run-id <id>` with `cwd` = sandbox via the injected `SqRunInvoker`, using `sys.argv[0]` resolved; time it; `read_outcome`; write the record; then leave the sandbox (the `sq` executable is an injected ReplayDeps.sq_executable; the Task 23 command passes the resolved sys.argv[0])
  - [x] Phase-to-pipeline mapping (`DESIGN`→`P4`, `TASKS`→`P5`) defined once
  - [x] Before the first config's `sq run`, run the resolution check recorded in Task 1 inside the first sandbox; the slice does not resolve → fail before any dispatch with the D10 error naming slice and start sha (D2); the runner never edits the plan
  - [x] No run file → `failed` / `no_run_state` record with exit code and stderr tail, WARNING
  - [x] Sandbox setup failure → ERROR with stderr, config skipped, set continues, reported in the summary
  - [x] Store write failure → stop the set, `keep()` the sandbox, error naming its path
  - [x] Return a summary: records written, configs skipped
  - [x] Commit: `feat: run producer replay sets`
  - **Success:** one record per config that ran; failures follow D10

- [x] **Task 22: Test the runner** (effort 3)
  - [x] Fakes for sandbox, invoker and store; no git, cf or model
  - [x] Two configs → two records in order, argv as specified, `cwd` = each sandbox
  - [x] First config fails → `failed` record, second still runs
  - [x] Each D10 runner row has a named test: slice does not resolve at the start point (no invoker call, error names slice and start sha), no run file, sandbox setup failure, store write failure (sandbox kept, path in error), cleanup failure (set continues)
  - [x] LLM-call bound in the plan equals configs × 2 × (1 + cap)
  - [x] Commit: `test: cover replay runner`
  - **Success:** tests pass, zero pyright errors

- [x] **Task 23: `sq replay run` command** (effort 2)
  - [x] Create `cli/commands/replay.py` with a `replay_app` Typer registered in `cli/app.py`; `run` takes the API-contract options, `--reviewer` and `--max-revisions` with no defaults (rendering is in cli/replay_views.py; the command is a thin shell over run_replay_set; --max-revisions has min 1 because loop.max rejects 0)
  - [x] Resolve aliases (model, profile) for configs and reviewer; unknown alias → error before any work
  - [x] Print the plan and confirm; `--yes` skips; non-interactive without `--yes` → exit 1 (D10)
  - [x] Print each config's outcome as it finishes, then the summary; exit 0 when every config produced a record, exit 1 when any was skipped or the set stopped
  - [x] Commit: `feat: add sq replay run`
  - **Success:** `sq replay run --help` shows the contract; exits follow D4/D10

- [x] **Task 24: Test `sq replay run`** (effort 2)
  - [x] CliRunner with the runner core faked: missing `--reviewer` / `--max-revisions` → usage error; non-interactive without `--yes` → exit 1, nothing run
  - [x] Exit codes for all-recorded (including all `failed`), skipped config, stopped set
  - [x] Commit: `test: cover sq replay run`
  - **Success:** tests pass, zero pyright errors

### Judge (D5)

- [x] **Task 25: `metrology.judge_timeout_s` config key** (effort 1)
  - [x] Define it in `config/keys.py` beside `metrology.audit_timeout_s`, same pattern, `int`, default 600 in the definition only
  - [x] Test: the key resolves to its default and accepts an override
  - [x] Commit: `feat: add metrology.judge_timeout_s config key`
  - **Success:** `sq config get metrology.judge_timeout_s` shows 600

- [x] **Task 26: Judge prompt, verdict parser and pair outcome** (effort 2)
  - [x] Write `data/replay/pairwise-judge.md`: compare two drafts of the same task for quality, short rationale, final line `WINNER: A`, `WINNER: B` or `WINNER: TIE`. No example verdicts outside that instruction. Confirm the file ships in the wheel like `data/pipelines/`
  - [x] In `replay/judge.py`: `judge_prompt_hash()` (SHA-256 of the packaged file); `parse_verdict(reply) -> JudgeCall` per D5 (last matching line, case-insensitive, tolerant of whitespace and markdown emphasis; otherwise `INVALID` with the raw tail); `combine(first, second_swapped) -> PairOutcome` per the D5 order-swap table (strip_frontmatter and the verdict logic live in replay/judge.py; combine(first, second_swapped) takes the second call's pick as the judge made it, with swapped labels, and swaps it back itself)
  - [x] `strip_frontmatter(text)` removes a leading YAML block
  - [x] Commit: `feat: add pairwise judge prompt and verdict parsing`
  - **Success:** parser and combiner cover every D5 table row

- [x] **Task 27: Test verdict parsing and pair outcome** (effort 2)
  - [x] `parse_verdict`: plain, `**WINNER: B**`, lowercase, trailing whitespace, `winner = tie`, an earlier matching line superseded by the last, no verdict → `INVALID` with tail
  - [x] Do not invent "real" replies; captured replies are added in Task 37
  - [x] `combine`: one test per D5 table row, remembering the second call's labels are swapped
  - [x] `strip_frontmatter`: with and without frontmatter
  - [x] Commit: `test: cover judge verdict parsing and order swap`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 28: `judge_replay_set`** (effort 3)
  - [ ] Contestants per D5: non-`failed` replays in the set plus `original:<original_sha>` (draft from the replay record's start point, re-read via `resolve_start_point`)
  - [ ] Pairs without a judgment from this `JudgeRef`; count calls for the caller's confirmation
  - [ ] Per pair: two calls through an injected dispatcher (production: `one_shot_dispatch_with_telemetry`, tools off), each wrapped in `asyncio.wait_for(timeout)`; inputs per D5 (judge prompt, `task_prompt`, frontmatter-stripped first drafts as `A` / `B`)
  - [ ] Both returned → write one `pairwise_judgment` with both `UsageRecord`s
  - [ ] A call raises or times out → ERROR naming the pair (and the bound for a timeout); pair not recorded; other pairs continue. If the first call had returned, WARNING with its tokens and cost (D5 half-recorded pairs)
  - [ ] Return a summary: pairs judged, pairs failed
  - [ ] Commit: `feat: judge replay pairs with order swap`
  - **Success:** two calls per new pair; a re-run makes none

- [ ] **Task 29: Test the judge** (effort 3)
  - [ ] Fake dispatcher and store; no model calls
  - [ ] Two replays + `original` → 3 pairs, 6 calls, second call has drafts swapped; a second invocation → 0 calls
  - [ ] Adding a third replay → only its new pairs are judged
  - [ ] `failed` replays are not contestants; frontmatter is stripped from what the dispatcher receives
  - [ ] D10 judge rows: dispatch raises, timeout (fake that sleeps past a small bound), second-call failure after first returned (WARNING with tokens and cost, no record), no verdict line → `INVALID` record
  - [ ] Commit: `test: cover pairwise judge`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 30: `sq replay judge` command** (effort 2)
  - [ ] Options per the API contract; `--judge` has no default; reads `metrology.judge_timeout_s`
  - [ ] Confirms the number of judge calls like `run` (`--yes`, non-interactive rule); 0 pairs → message, exit 0
  - [ ] Exit 1 when any pair failed, with the count
  - [ ] Commit: `feat: add sq replay judge`
  - **Success:** `sq replay judge --help` shows the contract

- [ ] **Task 31: Test `sq replay judge`** (effort 1)
  - [ ] Missing `--judge` → usage error; 0 pairs → exit 0 with message; a failed pair → exit 1; non-interactive without `--yes` → exit 1
  - [ ] Commit: `test: cover sq replay judge`
  - **Success:** tests pass, zero pyright errors

### Report (D6, D7)

- [ ] **Task 32: Bradley-Terry fit** (effort 2)
  - [ ] `replay/bradley_terry.py`: `fit(outcomes) -> BTFit` per D6 (Hunter MM, tie = half a win each, tolerance 1e-9, cap 10,000 with WARNING, geometric-mean normalization, per connected component, zero-win contestants get `None` with a reason). Tolerance and cap are module constants
  - [ ] `INCONSISTENT` counts as a tie; `INVALID` is excluded
  - [ ] `BTFit` carries strengths, components, iterations, converged
  - [ ] Commit: `feat: add Bradley-Terry fit`
  - **Success:** pure function, no new dependency

- [ ] **Task 33: Test Bradley-Terry** (effort 2)
  - [ ] Hand-computed three-contestant case (show the expected values in a comment)
  - [ ] Zero-win contestant → `None` with reason; disconnected graph → two components each normalized
  - [ ] Iteration cap hit (cap patched low) → WARNING, `converged` false
  - [ ] Commit: `test: cover Bradley-Terry fit`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 34: `replay_report` core** (effort 3)
  - [ ] `replay/report.py`: `replay_report(phase, judge, store, min_n) -> ReplayReport`, one table per (phase, reviewer, judge) per D7
  - [ ] Rows keyed per D1 (alias, model, profile, effort sent); every D7 column with its n; `original` row with BT, W-L-T and pairs only; `below floor` when judged pairs < `min_n` (no rank)
  - [ ] Footer data: slices covered, position consistency (consistent pairs / non-invalid pairs, with counts), prompt identities seen, BT cap note, self-preference flag when the judge's model equals a contestant's model
  - [ ] No replays → empty report
  - [ ] Commit: `feat: build replay report`
  - **Success:** report data covers every D7 column and footer item

- [ ] **Task 35: Test the report core** (effort 2)
  - [ ] Fixture records across two slices: medians, rates and k of m priced match hand values; `rounds` uses accepted replays only
  - [ ] Two reviewers → two tables; a judgment from another prompt hash is excluded
  - [ ] `below floor` marking; self-preference flag on and off; empty store → empty report
  - [ ] Commit: `test: cover replay report`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 36: `sq replay report` command and views** (effort 2)
  - [ ] `cli/replay_views.py` renders the D7 / UI Specifications layout, reusing `stats_views` cells (count, cost) rather than copying; `—` with the reason for `None` strengths; self-preference warning line
  - [ ] `report` subcommand with `--phase`, `--judge`, `--json` (mirrors the table); reads `metrology.min_evidence_n`; empty → message, exit 0
  - [ ] Test: rendered text contains each column header, `below floor`, the `original` row and the footer; `--json` keys match the table; empty store message
  - [ ] Commit: `feat: add sq replay report`
  - **Success:** tests pass, zero pyright errors; touched CLI modules stay near 300 lines

### Docs and verification

- [ ] **Task 37: Verification walkthrough** (effort 3)
  - [ ] Run the design's Verification Walkthrough steps 1–7 with real dispatches; record each step's result under this task
  - [ ] Save one real judge reply per design variant as a parser fixture in the Task 27 test file: plain, markdown-bold, lowercase, trailing whitespace, no verdict
  - [ ] For a variant the walkthrough does not produce, make a real judge call with an instruction that provokes it, and note under this task which fixtures were provoked
  - [ ] Any defect found: fix it, add a test, then continue
  - [ ] Each defect fix found here gets its own `fix:` commit naming the defect, before the fixture commit
  - [ ] Commit: `test: add captured judge replies to verdict parser tests`
  - **Success:** all seven steps match the walkthrough's expectations

- [ ] **Task 38: Docs and slash command** (effort 1)
  - [ ] Add `commands/sq/replay.md` passing `$ARGUMENTS` to `sq replay`, in the pattern of `commands/sq/stats.md`
  - [ ] README: a `sq replay` section (run, judge, report; cost bound; aliases are user-chosen)
  - [ ] CHANGELOG: one user-facing bullet for `sq replay` and one for prompt identity in `sq stats producers`
  - [ ] Commit: `docs: document sq replay`
  - **Success:** slash command installs with the others; docs describe the shipped options

- [ ] **Task 39: #210 comment and follow-on issues** (effort 1)
  - [ ] File issues for the downstream-outcome scorer and for the human blind check of pairwise picks (design Excluded); record their numbers here
  - [ ] Comment on #210 with the walkthrough's report table and the two issue numbers
  - [ ] Final pass: `ruff format`, `ruff check`, `pyright`, full `pytest`
  - [ ] Commit: `docs: link slice 177 follow-on issues`
  - **Success:** issues exist and are linked; full suite green, zero pyright errors
