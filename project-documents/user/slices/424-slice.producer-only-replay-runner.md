---
docType: slice-design
slice: producer-only-replay-runner
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [421, 422, 423]
interfaces: [425, 426]
dateCreated: 20261104
dateUpdated: 20261105
status: not_started
---

# Slice Design: Producer-Only Replay Runner

## Overview

This slice turns a qualified case set into implementations from each config, under a stated spend limit. It adds two layers:

1. **Producer-only mode on `sq run`** (`--producer-only`). It runs only the pipeline's producer step (`implement` in `P6`, the `fix` step in `fix`), with the step's embedded review stripped: same prompt, same dispatch, same commit, no review action and no verdict. Then the run stops. No pipeline YAML or prompt is copied.
2. **The benchmark runner** (`sq benchmark run`). It takes a case set × configs × sample count. For each run it opens a sandbox at the start commit, runs the producer in the scrubbed environment, scans the runtime's transcript for leaks, and writes one replay record with the diff in a content-addressed sidecar file. It refuses to start without both caps, states its dollar bound before any dispatch, stops at the run-level cap, and resumes by skipping runs that already have records.

Nothing here grades a replay. After this slice, replays produce records and diffs. 425 grades them.

## Value

Developer value: configs produce comparable implementations of identical work, under a spend limit stated up front. Each record says what the producer did (committed, crashed, capped, committed nothing, blocked), whether the scan saw a leak, and what it cost. Each one points to a diff that 425 can grade and a person can read.

Producer-only mode is also useful on its own: `sq run P6 <slice> --producer-only` gets one implementation commit with no review spend, which is handy when a PM wants to look at a raw implementation first.

## Technical Scope

**Included**

- `--producer-only` on `sq run`, for both the SDK executor and prompt-only mode. Implemented as a transform of the loaded pipeline definition (D1, D2).
- A `ProducerStep` capability on step types. `PhaseStepType` and 423's `FixStepType` implement it.
- In-dispatch cost enforcement on the SDK path through `max_budget_usd` (D9).
- The `BenchmarkRun` and `ImplementationReplay` record types, and diff sidecars in the metrology store.
- `TranscriptSource` per agent profile (Claude Code, Codex), and the leak scan.
- The benchmark runner: scheduling, re-qualification through 422, the fix-case producer invocation, cap enforcement, resume and interruption marking.
- CLI `sq benchmark run` and `sq benchmark replay-show`, with matching `/sq:benchmark` subcommands. A cross-benchmark `status` view is left to 425, whose report is the first consumer of one. `/sq:run` accepts `--producer-only`.

**Excluded**

- Grading, hidden-test injection, tool-config restoration and the paired report (425). The slice plan and architecture put injection in the grader. The earlier notes in 421 and 422 that assigned it to 424 are corrected there.
- Slice cases and cf registration of benchmark sandboxes (426). 424 schedules by case kind through a `CaseKindRunner` seam and implements only `fix`. That is the only case kind 422 produces. 421 assigned cf registration to 424, and that line moves to 426, which is the first slice that needs a cf project in a sandbox.
- Measuring the sample count (425).
- Concurrent replays (#146) and OS sandboxing (#213).
- Producers on OpenAI-compatible profiles (`openai`, `openrouter`, `gemini`, `local`). Their runtime writes no transcript, so no leak scan is possible. The runner refuses them (D6).

## Dependencies

### Prerequisites

- **421:** `BenchmarkSandbox`, `HistoryFreeSandbox`, `ScrubbedEnvironment` with `CredentialGrant.for_profiles`, `EnvironmentIdentity`, `BenchmarkRecordStore` with its `write_record`/`iter_records` primitives, the benchmark orphan sweep, and a yes from `sq benchmark auth-check` for each profile a benchmark uses.
- **422:** qualified fix cases, versioned case sets, `qualification_for` and `qualify_candidate`, and each case's provenance issue ref.
- **423:** the `fix` pipeline with `issue-file`, `commit-to: current` and `--io-dir`, and `FixStepType`.
- **420:** `effort_sent` on usage records, read into each replay's config ref.
- **947 / #241:** `read_cost_cap`, `RunSpend`, `FailureKind.COST_CAP`.

### Interfaces Required

- `PipelineDefinition`, `StepConfig`, the step-type registry and the `StepType` protocol (`pipeline/models.py`, `pipeline/steps/`).
- Reserved run params (`pipeline/control_params.py`) and `_load_run_definition` for resume.
- `StateManager(runs_dir=…)` and `RunState` (`pipeline/state.py`). A producer run's state lives in the scrubbed home.
- 177's replay plumbing: `run_sq_subprocess`, and the outcome helpers in `replay/outcome.py` that read cost, effort sent and prompt identity from run state.
- `ProducerConfigRef` and `PromptIdentity` (`metrology/replay_models.py`), and model alias resolution.
- `SDKExecutionSession` option construction (`pipeline/sdk_session.py`).

## Architecture

### Component Structure

```
src/squadron/
  pipeline/
    producer_only.py          ProducerStep protocol, select_producer_step, producer_only_definition
    steps/phase.py            + producer_only_config (drops review, checkpoint)
    steps/fix.py              + producer_only_config (unchanged config)  [file from 423]
    control_params.py         + RUN_PRODUCER_ONLY
    sdk_session.py            + max_budget_usd from the run's cap (D9)
  metrology/
    benchmark_models.py       + BenchmarkRun, ImplementationReplay, ProducerOutcome,
                                AbsenceClass, LeakScanResult, LeakHit, DiffRef
    benchmark_store.py        + run and replay records; DiffSidecars
  benchmark/
    transcripts.py            TranscriptSource protocol, registry by ProfileName, ToolCall
    transcript_claude.py      Claude Code JSONL under <home>/.claude/projects/
    transcript_codex.py       Codex rollouts under <home>/.codex/sessions/
    leak_scan.py              LeakRules, scan(tool_calls, rules) -> LeakScanResult
    case_runners.py           CaseKindRunner protocol (requalify, run); FixCaseRunner
    replay_one.py             one (case, config, sample): sandbox -> producer -> scan -> record
    bench_runner.py           plan, bound, schedule, cap, resume, interruption
    bench_plan.py             BenchmarkPlan, bound arithmetic
  cli/commands/
    run.py                    + --producer-only
    benchmark.py              + run, replay-show
commands/sq/benchmark.md      + the same subcommands
commands/sq/run.md            + --producer-only
```

`bench_runner.py` reaches the fix pipeline only through `FixCaseRunner`, and it reaches transcript formats only through the `TranscriptSource` registry. Each module stays under 300 lines.

### Data Flow

**Producer-only `sq run`:**

```
sq run P6 424 --producer-only
  load definition → producer_only_definition(def)
      exactly one top-level step implements ProducerStep → that step
      its config → producer_only_config (implement: drop review, checkpoint)
      definition.steps = [stripped step]; skipped = names of every other step
  params[RUN_PRODUCER_ONLY] = true          (kept for --resume)
  executor runs the one step: [cf-ops] → dispatch → commit (no review verdict)
  CLI: "producer-only: stopped after implement (commit abc1234); skipped: branch, close-out, revise-code, devlog, branch, summary"
```

**Benchmark run:**

```
sq benchmark run --set fixes --model opus --model sol --samples 3 --max-cost 40
  resolve: case set version, configs (alias → model, profile), per-replay cap
  refuse: missing cap | profile without TranscriptSource | auth not checked
  benchmark_id = hash(set name, set version, config keys, samples)
  take benchmark lock; if record says running and no owner → mark interrupted
  sweep orphan sandboxes (421), report the count
  plan: pending = every (case, sample, config) without a replay record
  print bound (D8) ─── nothing dispatched before this line
  write BenchmarkRun(status=running)
  for case in set:                      case-major, then sample, then config
     for sample in 1..k:
        for config in configs:
           if spent ≥ run cap → status=partial, stop
           replay_one(case, config, sample):
              BenchmarkSandbox(start_sha) → EnvironmentIdentity
              runner.requalify(case, env) → drop case if rejected
              FixCaseRunner: write <id>.out/issue.md; run installed sq by absolute path:
                 sq run fix <n> -m <alias> --producer-only --max-cost <per-replay cap>
                    -p issue-file=issue.md -p commit-to=current --io-dir <id>.out --run-id <rid>
                 cwd=<tree>, env=ScrubbedEnvironment(grant=config's profile)
              read run state from <id>.home/.config/squadron/runs/
              HEAD vs start_sha → diff → sidecar
              TranscriptSource(profile).tool_calls(<id>.home) → leak scan
              write ImplementationReplay
           spent += replay cost
  status = complete | partial; print summary
```

### State Management

- **Store records** (persistent, in `~/.config/squadron/metrology/`): one `benchmark_run` per benchmark id, overwritten as its status changes, and one `implementation_replay` per (benchmark, case, config, sample). Both are optional sibling payloads on `MetrologyRecord`. No migration is needed.
- **Diff sidecars** (persistent): `<store>/sidecars/diffs/<sha256>.diff`. They are written once and never rewritten. The store's `*.json` glob is top-level only, so sidecars are never read as records.
- **Sandboxes** (transient): 421's `<id>/`, `<id>.home/`, `<id>.out/`. They are removed after each replay unless `--keep` is given. A replay that fails to write its record keeps its sandbox and stops the benchmark, as 177 does.
- **Benchmark lock:** `<benchmark root>/<benchmark_id>.lock`, the same process lock 177's sandboxes use. A second invocation of the same benchmark refuses while the first is alive.

## Technical Decisions

### D1 — Producer-only is a definition transform, not an executor mode
Status: decided
- `producer_only_definition(definition) -> ProducerOnlySelection` returns a copy of the definition whose `steps` hold only the producer step, with its config passed through `producer_only_config`. It also returns the names of the skipped steps. The executor, the prompt-only renderer and the dry run all receive the transformed definition and need no producer-only branch.
- The **producer step** is the single top-level step whose step type implements `ProducerStep`. No such step, or more than one, refuses the run before anything executes, naming the candidates. Steps nested inside `loop` or `each` are not candidates.
- Why a transform: the architecture forbids copying the step or the prompt. Removing the other steps and the review key from the real config is the smallest change that keeps the prompt, dispatch and commit byte-identical. A test asserts that the expanded actions of the stripped `implement` step equal the full step's actions minus `review` and `checkpoint`, with the commit config minus `REVIEW_TEMPLATE_PARAM`.
- `existing: keep` and the cf-ops before the dispatch (`set_slice`, `check_decisions`, `set_phase`, `build_context`) stay as configured. They are part of the production step.
- Rejected: an executor flag that skips actions by type at run time. It puts a step-type detail (which action is the embedded review) into the executor.

### D2 — The `ProducerStep` capability
Status: decided
- A `runtime_checkable` protocol beside `StepType`:

```python
class ProducerStep(Protocol):
    def producer_only_config(self, config: StepConfig) -> StepConfig: ...
```

- `PhaseStepType` returns the config without `review` and `checkpoint`. Its expansion already adds the review, the checkpoint and the commit's review template only when `review` is set, so nothing else changes. `design` and `tasks` steps qualify as producers too. That is harmless: `P4` and `P5` each have one such step.
- `FixStepType` returns its config unchanged. It has no embedded review (423 D1).
- Each step type knows its own review key. The executor and the CLI never name one.

### D3 — Producer-only on the CLI and in run state
Status: decided
- Flag: `--producer-only`. It sets the reserved param `RUN_PRODUCER_ONLY`, which joins `RESERVED_PARAMS` so `-p` cannot set it. `--resume` re-applies the transform when the param is present, so a resumed producer-only run never grows its other steps back.
- Refused combinations, each with an error naming both flags: `--from` (the run has one step), `--item` and `--flagged` (batch resume addresses steps that were removed).
- The stop is reported in two places:
  - The run state carries `producer_only: {step, skipped}`.
  - The CLI prints `producer-only: stopped after <step> (commit <sha>)` with the skipped steps.
  - The exit code is the ordinary one for the run's status.
- `--prompt-only --producer-only` emits the transformed pipeline's instructions, so `/sq:run P6 424 --producer-only` runs the same single step. `commands/sq/run.md` documents and passes the flag.

### D4 — Benchmark identity, record ids and resume
Status: decided
- **Config key** (scheduling): `alias`, resolved `model`, `profile`, and the alias's configured effort. The record also stores `effort_sent` from the run's usage records (420). A report (425) groups by effort sent, as 420 requires.
- **`benchmark_id`**: `bench-` followed by the first 16 hex digits of the sha256 of the canonical JSON of `(case set name, set version, sorted config keys, samples)`. Caps are not part of the identity. Raising the cap and rerunning continues the same benchmark.
- **Replay record id**: `implreplay-<benchmark_id[6:18]>-<case_id[5:17]>-<sha256(config key)[:8]>-s<n>`. Resume is a lookup: a (case, config, sample) with a record is skipped, whatever its outcome. A record with a harness-caused absence is skipped too. Rerunning it takes `--retry-harness`, which deletes those records first and reports how many.
- **Interrupted**: on start, a `BenchmarkRun` with `status=running` whose lock is free is set to `interrupted`. That is reported before planning. The new invocation then sets it back to `running`.
- **Orphaned sandboxes**: 421's benchmark sweep runs before planning. The runner prints how many it removed. Each one is logged at WARNING by the sweep.

### D5 — Fix-case producer invocation
Status: decided
- `FixCaseRunner` writes the case's `task_text` to `<id>.out/issue.md`. It then runs the installed `sq` by absolute path. That path is resolved once at harness start, as 421's auth check does, because the scrubbed `PATH` cannot reach it:

  `sq run fix <issue-number> -m <alias> --producer-only --max-cost <per-replay cap> -p issue-file=issue.md -p commit-to=current --io-dir <id>.out --run-id <replay record id>`

  It runs with `cwd=<tree>` and `env=ScrubbedEnvironment(CredentialGrant.for_profiles([config.profile]))`, and with no wall-clock bound, as in 177. Existing bounds end a hang: the SDK dispatch stall bound (`FailureKind.STALL`, slice 174) and Codex's `codex.turn_timeout_s`. Either one fails the run, which records `producer_failed` with the failure kind (D10).
- The issue number comes from the case's provenance issue ref. A fix case with no issue ref fails at planning, naming the case. 422 always records one for a qualified case.
- `--max-cost` is passed on every invocation. The scrubbed home's seeded `config.toml` may carry its own `pipeline.max_cost_usd`, and the flag wins over it (#241 precedence). The per-replay cap is therefore exactly what the bound assumed.
- Run state is read through `StateManager(runs_dir=<id>.home/.config/squadron/runs)`. 423's `fix-context` outputs must show `issue_source: file` and the sha256 of `issue.md`. A mismatch is a harness error, because the run did not use the frozen text.
- **Prompt identity** is read from the dispatch metadata, as 177 does. It is joined by `instruction_files`: path and sha256 for each `CLAUDE.md`, `AGENTS.md` and `.claude/rules/**` file in the tree at the start commit. The scrubbed home carries no user-level instructions (421 D7), so these files are all the instructions in effect.
- `CaseKindRunner` is keyed by 421's `CaseKind` and has two methods: `requalify(case, environment)` and the replay run. `FixCaseRunner.requalify` calls 422's `qualification_for` / `qualify_candidate`; `replay_one` calls only `runner.requalify`, so 426 adds slice-case requalification without editing `bench_runner.py`. A case set that contains a kind with no runner refuses at planning. In 424 that is `slice`, until 426 adds its runner.

### D6 — Transcripts come from the agent runtime's own files in the scrubbed home
Status: decided
- The scrubbed home belongs to exactly one replay, so every transcript file under it belongs to that run. The runtimes write their full transcripts there, including subagent transcripts. That is more than squadron's message stream sees.
- `TranscriptSource` protocol, with a registry keyed by `ProfileName`:
  - `sdk` → `ClaudeTranscriptSource`: every `*.jsonl` under `<home>/.claude/projects/`, recursively, which includes subagent files. It extracts `tool_use` blocks (`name`, `input`).
  - `openai-oauth` → `CodexTranscriptSource`: every `rollout-*.jsonl` under `<home>/.codex/sessions/`. It extracts function and shell call items (name and arguments or command).
- Parsing is lenient about layout and strict about meaning. Unknown entry types are skipped. A file that does not parse as JSONL, or no transcript file at all, makes the scan `scan_unavailable` with the reason. If the run's usage records report a nonzero tool-call count while the transcript yields no tool calls, the scan is `scan_unavailable` as well. An empty result is never read as clean.
- A config whose profile has no registered source is refused at planning: `profile <p> has no transcript source; its replays cannot be leak-scanned`. That covers the OpenAI-compatible profiles, where squadron runs the tools itself and no runtime writes a transcript.
- Implementation step 1 is a spike. It confirms that each runtime writes its transcript into the redirected home. A runtime that does not is a no for that profile, written as `BLOCKED:` in the task file for the PM, the same way 421's auth spike works.
- Rejected: logging tool calls from squadron's dispatch stream. Codex reports only the final turn result, and squadron's stream may not include subagent tool calls. Rejected: scanning the user's real `~/.claude/projects`, where concurrent sessions would mix in.

### D7 — Leak scan rules
Status: decided
- `LeakRules` is built per replay from facts the harness knows: the sandbox's three directories, the user's real `HOME`, the user's checkout (`repo_root`), the harness's own install location (the directory holding the installed `squadron` package), the output of `uv cache dir`, the project's distribution name (`[project].name` at the start commit), and its code host repository (owner and name from the case's issue ref).
- **Path rule.** These paths are collected from tool inputs:
  - file-tool path fields
  - absolute and `~`-prefixed tokens in shell commands (tokenized with `shlex`, falling back to a token regex when quoting is unbalanced)
  - relative tokens containing `..`, resolved against the tree
  A path is a hit when it lies under the real `HOME`, the harness install location or the uv cache, and outside the sandbox's own three directories. That covers the checkout, the store, other sandboxes, user tool installs and package caches.
- **Git and code-host rule.** Each of these is a hit:
  - any `gh` invocation
  - `git` with `-C` or `--git-dir` or `--work-tree` outside the tree
  - `git clone`, `git fetch`, `git pull` and `git remote add`
  - a URL fetch whose host and path name the case's repository
- **Own-package rule.** An install or run of the project's distribution name through `pip install`, `uv pip install`, `uv add`, `uvx`, `uv tool` or `pipx` is a hit. That is the network route 421 recorded as out of the scrub's reach.
- **Result:** `leaked` with up to 20 `LeakHit`s (rule, tool, input excerpt of at most 300 characters), or `no_leak_detected`, or `scan_unavailable` (D6). Never "not leaked".
- `LEAK_RULES_VERSION` is an int constant in `leak_scan.py`, recorded on every replay and bumped whenever a rule changes.
- Known gaps, written into the module docstring: file access inside scripts the model writes and runs, paths built at run time, and network reads outside the code host.

### D8 — Caps and the stated bound
Status: decided
- **Run-level cap:** `--max-cost USD`, required, flag only. A benchmark's total is a decision made for each invocation, so it has no config default. It applies to the invocation, as `sq run --max-cost` does on a resume.
- **Per-replay cap:** `--max-cost-per-replay USD`, otherwise `pipeline.max_cost_usd` read from the harness config. When neither is set, the run refuses. Both refusals name the missing cap and the flag or key that sets it. Values are checked with 947's `_positive_usd` rules.
- **Bound**, printed before the first dispatch:

```
benchmark bench-3f9c…  set fixes v2  configs opus, sol  samples 3
pending 54 of 60 replays (6 already recorded)
bound: 54 × $1.50 per replay = $81.00, capped at run cap $40.00
       + one replay of overshoot $1.50 → at most $41.50 for opus
       not bounded: sol (openai-oauth) — cost is checked only after each dispatch
```

- The headline figure covers only configs whose replays are capped inside the dispatch (the SDK path, D9). Every other config is listed under `not bounded`, with the reason: checked only after the dispatch, or reports no cost. Its replays still count toward the run cap when they report a cost.

- **Enforcement:** before starting each replay, the runner stops when the invocation's known spend is at or over the run cap. A replay already running can therefore overshoot by up to one per-replay cap, and the bound includes that.
  - When the cap is hit, the run gets `status=partial`. Every record already written is kept, and the CLI exits 2.
- **Unpriced replays** (no `cost_usd`) add nothing to the tally, the same as 947's `RunSpend`. They are counted in the summary, and their configs are listed as not bounded.
- Grading is bounded by `sq benchmark grade`'s own cap (425 D9). 424's bound covers producer dispatches only, because they are all 424 spends.

### D9 — In-dispatch enforcement on the SDK path
Status: decided
- 947 checks the cap after each action. A producer-only run is one dispatch, so on its own that check cannot stop a replay partway. On the SDK path, `open_pipeline_session` now sets `max_budget_usd` to the run's remaining cap when the session opens. The SDK's `error_max_budget_usd` result maps to `FailureKind.COST_CAP`. A producer-only run has one dispatch, so per-query and per-connection budgeting give the same limit for a replay. For a run with several dispatches, 947's check after each action still applies as it does today.
- This changes every capped SDK `sq run`, not only replays. The intended behavior was already "stop at the cap". The change makes it hold inside a dispatch too. A CHANGELOG bullet records it.
- Codex runs a dispatch as one turn and has no dollar budget option in squadron's use, so its replays are checked after the dispatch. The bound says so (D8). An issue is filed for in-dispatch enforcement on the Codex and OpenAI-compatible paths, and its number goes in the slice's task file.

### D10 — Producer outcomes and absence classes
Status: decided

Rows are checked top to bottom, and the first match wins.

| `ProducerOutcome` | When | `AbsenceClass` |
|---|---|---|
| `environment_failed` | sandbox or environment resolution failed | harness |
| `no_run_state` | `sq` exited with no readable run state, or with run state still `running` (killed by a signal) | harness |
| `frozen_text_mismatch` | `fix-context` did not use the given file (D5) | harness |
| `cost_cap` | `failure_kind: cost_cap` | config |
| `blocked` | run paused with `awaits_human` | config |
| `committed` | run completed, HEAD moved | none |
| `no_commit` | run completed or refused (for example `fix_report`), HEAD unchanged | config |
| `producer_failed` | any other failed run status, including a stall or turn timeout | config |

- `failure_detail` carries the run's failure kind and the stderr tail, so each config absence says why.
- A failure after the producer exits, in `git diff` or in the sidecar write, is a store write failure: it is logged at ERROR, the sandbox is kept, and the benchmark stops (State Management).
- The leak verdict is a separate field. A `leaked` or `scan_unavailable` result makes the replay a harness absence whatever its producer outcome, so 425 drops the case from every config. Its diff is still stored, for inspection.
- A case whose re-qualification fails is not a replay outcome. It is a `CaseDrop` on the `BenchmarkRun` with the rejection reason. No replay of it is attempted in that invocation, and it is reported.
- A paused (`blocked`) producer run is never resumed by the benchmark. Its sandbox is removed like any other.

### D11 — Diff sidecars
Status: decided
- After the producer exits, the runner runs `git diff --binary <start_sha> HEAD` in the tree. `.venv/` is excluded by 421 D5's `info/exclude`. Uncommitted changes are not part of the diff, because the producer's result is its commit.
- `DiffSidecars.put(bytes) -> DiffRef(sha256, bytes, files_changed)` writes `<store>/sidecars/diffs/<sha256>.diff` atomically when it is absent. When the file already exists, its content is checked against the hash. `get(sha256)` reads the file and verifies the hash, raising `MetrologyStoreError` on a mismatch or a missing file.
- An empty diff with a moved HEAD is still `committed` with a `DiffRef` of zero bytes. 425 grades it as it is.

### Technology Choices

- No new dependencies. `shlex` and `json` from the standard library for the scan, `git` through `ProcessRunner`.
- The Claude Agent SDK's existing `max_budget_usd` option (D9).

### Patterns and Conventions

- `ProducerOutcome`, `AbsenceClass`, `LeakVerdict`, `LeakRule` and `BenchmarkStatus` (`running`, `complete`, `partial`, `interrupted`) are `StrEnum`s defined once in `benchmark_models.py`. Reports group by these values, never by message text.
- Every collaborator of `bench_runner` and `replay_one` is injected (sandbox factory, invoker, store, state reader, transcript registry, clock), as in 177's runner. Tests run no model and no git outside fixtures.
- Harness failures are logged at ERROR with the command's stderr tail and recorded with their class. A store write failure stops the benchmark and keeps the sandbox.

## Implementation Details

### API Contracts

**`sq run <pipeline> [target] --producer-only`** (see D1–D3).

**`sq benchmark run --set NAME [--set-version N] --model ALIAS [--model ALIAS …] [--samples K] --max-cost USD [--max-cost-per-replay USD] [--case CASE_ID …] [--retry-harness] [--keep]`**

- `--samples` defaults to `benchmark.planned_samples` (422's key).
- `--case` limits the run to the named cases, for debugging. It does not change `benchmark_id`, so its records count toward the full benchmark.
- Output: the plan and bound (D8), then one line per replay, then a summary of counts by outcome, absence class and leak verdict, plus total spend.
- Exit codes: 0 complete, 2 partial (run cap), 1 refusal or harness stop.

**`sq benchmark replay-show RECORD_ID [--diff]`** prints the record, including any leak hits. With `--diff` it prints the sidecar diff.

`/sq:benchmark` mirrors both, with the same arguments and output.

### Database / Storage Schema

```python
class LeakHit(BaseModel, frozen=True):
    rule: LeakRule
    tool: str
    excerpt: str                         # ≤ 300 chars

class LeakScanResult(BaseModel, frozen=True):
    verdict: LeakVerdict                 # leaked | no_leak_detected | scan_unavailable
    rules_version: int
    tool_calls_seen: int
    hits: tuple[LeakHit, ...]            # ≤ 20
    detail: str                          # reason when scan_unavailable

class DiffRef(BaseModel, frozen=True):
    sha256: str
    bytes: int
    files_changed: int

class ImplementationReplay(BaseModel, frozen=True):
    benchmark_id: str
    case_id: str
    case_set: str
    case_set_version: int
    sample: int
    config: ProducerConfigRef            # effort_sent, tool_use, max_output_tokens (420 D6)
    pipeline: str                        # "fix"
    producer_step: str
    run_id: str
    outcome: ProducerOutcome
    absence: AbsenceClass | None
    failure_detail: str | None
    leak: LeakScanResult | None          # None only when the producer never ran
    diff: DiffRef | None
    commit_sha: str | None
    environment: EnvironmentIdentity | None
    prompt: PromptIdentity | None
    instruction_files: tuple[tuple[str, str], ...]
    cost_usd: float | None
    turns: int | None
    wall_seconds: float
    squadron_version: str
    created_at: datetime

class CaseDrop(BaseModel, frozen=True):
    case_id: str
    reason: CandidateRejection | str     # 422's enum, or harness detail
    environment_digest: str

class BenchmarkRun(BaseModel, frozen=True):
    benchmark_id: str
    case_set: str
    case_set_version: int
    configs: tuple[ProducerConfigRef, ...]
    samples: int
    status: BenchmarkStatus
    run_cap_usd: float                   # latest invocation's
    per_replay_cap_usd: float
    spent_usd: float                     # known, across invocations
    unpriced_replays: int
    case_drops: tuple[CaseDrop, ...]
    started_at: datetime
    updated_at: datetime
```

`MetrologyRecord` gains `benchmark_run` and `implementation_replay`, with `RECORD_TYPE_*` constants. `BenchmarkRecordStore` gains `write_run`, `get_run`, `list_runs`, `write_replay`, `get_replay`, `replays_for(benchmark_id)` and `delete_replays(ids)` (for `--retry-harness` only), plus a `diffs: DiffSidecars` attribute.

## Integration Points

### Provides to Other Slices

- **425:**
  - `ImplementationReplay` records with outcome, absence class, leak verdict, environment identity, prompt identity and usage
  - `DiffSidecars.get` for the producer's diff
  - `benchmark_id` for grouping
  - `bench_plan` arithmetic, which 425 extends with grading terms
  - the rule that a harness absence drops the case from every config
  425 grades in the same kind of sandbox. It rebuilds the tree from `start_sha` plus the diff. It does not keep the replay sandbox alive. This departs from the architecture's "in the same sandbox" wording, on purpose: keeping every replay's sandbox until grading would hold cases × configs × samples environments on disk. `git diff --binary` keeps mode bits, and the producer's result is its commit, so the rebuilt tree is the graded subject. 425 D1 takes the cost: a reinstall per grade, and the `environment_changed` absence when the rebuilt environment differs.
- **426:** the `CaseKindRunner` seam for a slice-case runner, and producer-only `P6` (D1–D3) for that runner to invoke, plus the cf sandbox registration it adds.

### Consumes from Other Slices

- **421:** the sandbox, environment identity, scrubbed environment and sweep, used as specified. A profile whose auth check answered no fails its first replay with `no_run_state`, carrying the probe-like stderr. The runner prints a reminder to run `sq benchmark auth-check` when the first replay of a profile ends that way.
- **422:** `qualification_for` / `qualify_candidate`. Re-qualification is run at most once per (case, environment digest) per invocation, and the result is cached in memory.
- **423:** `sq run fix` flags exactly as 423's Integration Points state. No 423 behavior changes except the added `producer_only_config` method.
- **947:** `read_cost_cap` precedence and `RunSpend` semantics, unchanged. D9 adds in-dispatch enforcement on the SDK path.

## Success Criteria

### Functional Requirements

- `sq run P6 <slice> --producer-only` runs the `implement` step's cf-ops, dispatch and commit, and stops. The run state shows no review, checkpoint, close-out, loop, DEVLOG, merge or summary action. The CLI prints the stop line with the skipped steps.
- The stripped step's expanded actions equal the full step's actions without `review` and `checkpoint`, and the commit config without the review template. The prompt identity matches a normal `P6` run's dispatch on the same inputs. No pipeline YAML or prompt file is added.
- A pipeline with no producer step, or more than one, refuses `--producer-only` with the candidate names. `--from`, `--item` and `--flagged` with `--producer-only` are refused. `--resume` of a producer-only run stays producer-only.
- `/sq:run P6 <slice> --producer-only` renders the same single step.
- `sq benchmark run` with `--max-cost` missing, or with no per-replay cap from either source, refuses and names the missing cap. A config on an OpenAI-compatible profile is refused with the transcript-source message.
- The bound appears before the first dispatch, and the invoker test double confirms nothing was dispatched before it was printed. Reaching the run cap stops dispatching, keeps every record, sets `status=partial` and exits 2.
- A test transcript containing a `Read` of a file in the user's checkout marks the replay `leaked`, a harness absence, with the hit recorded. So does each of these: a `gh` call, a `git -C <outside>`, and a `uvx <project name>`. A clean transcript records `no_leak_detected`. A missing or unparseable transcript records `scan_unavailable`.
- Diffs are written as sidecar files referenced by sha256. A replay record serializes under 8 KB without the diff. `replay-show --diff` prints the diff, and a tampered sidecar fails with a hash mismatch.
- Killing a benchmark mid-replay, then rerunning: the earlier run is reported `interrupted`, its orphaned sandbox is reported and removed, completed replays are skipped, and the remaining ones run.
- Each `ProducerOutcome` in D10 is produced by a test double for its condition, with its absence class. The doubles include a stalled run, a run killed by a signal, a `fix_report` refusal, and a `git diff` failure after a successful run (benchmark stops, sandbox kept).

### Technical Requirements

- `ruff format`, `ruff check` and `pyright` (zero errors) are clean.
- Transcript parsers are tested against real transcript files captured in the D6 spike (scrubbed of content, layout kept) under `tests/benchmark/fixtures/transcripts/`, not only against synthetic lines.
- Leak rules have a parametrized test per rule with hitting and non-hitting inputs, including a path inside the tree's `.venv` that must not hit and a `..` escape that must.
- The D9 change has a test that `error_max_budget_usd` maps to `cost_cap`, and one that an uncapped run passes no budget.
- `tests/replay/` and existing `sq run` tests pass unchanged.

### Integration Requirements

- 425 can load a benchmark's replay records, fetch each diff, and tell which cases to drop for every config, with no further harness work.
- 426 can register a slice-case runner without editing `bench_runner.py`.

### Verification Walkthrough

These are draft commands. `--producer-only` and the `sq benchmark run/replay-show` commands do not exist until this slice is implemented. Steps 3–7 need a case set from 422 (`sq benchmark fix-cases build --set fixes`) and yes answers from `sq benchmark auth-check` for the aliases used.

1. **Producer-only on `P6`.** On a slice branch with a design and task file and no commits ahead of the target:
   ```bash
   sq run P6 <slice> --producer-only --dry-run
   sq run P6 <slice> --producer-only --max-cost 5
   sq runs show <run-id>
   git log -1 --format='%s'
   ```
   The dry run lists `set_slice → check_decisions → set_phase → build_context → dispatch → commit`, with no review or checkpoint. The run prints `producer-only: stopped after implement (commit …)` and names the skipped steps. The run state has no review action. The commit is the implementation commit. No DEVLOG commit and no merge follow it.

2. **Refusals.**
   ```bash
   sq run P6 <slice> --producer-only --from close-out    # refused
   sq run slice <slice> --producer-only                   # refused if it has several producer steps; names them
   ```

3. **Caps are required.**
   ```bash
   sq benchmark run --set fixes --model opus --samples 1
   sq benchmark run --set fixes --model opus --samples 1 --max-cost 5   # with pipeline.max_cost_usd unset
   ```
   The first is refused for `--max-cost`. The second is refused for the per-replay cap, naming `--max-cost-per-replay` and `pipeline.max_cost_usd`.

4. **A small run.**
   ```bash
   sq benchmark run --set fixes --model opus --model sol --samples 1 --max-cost 10 --max-cost-per-replay 2 --case <case-id>
   ```
   The bound prints first. Two replay lines follow, each with outcome, leak verdict and cost. Then:
   ```bash
   sq benchmark replay-show <record-id> --diff
   ```
   The diff is the producer's fix commit against the case's start commit. The record shows the environment digest, the prompt identity, `instruction_files` and `effort_sent`.

5. **Run cap stops the run.** `sq benchmark run --set fixes --model opus --samples 2 --max-cost 1 --max-cost-per-replay 1` stops after the first replay that brings spend to $1 or more. Status is `partial`, and the exit code is 2. Rerunning with `--max-cost 10` skips the recorded replays and continues.

6. **Interruption.** Start step 5's rerun, then press Ctrl-C during a replay. Run it again: `interrupted` is reported, one orphaned sandbox is reported and removed, and the run resumes.

7. **Leak detection.** `uv run pytest tests/benchmark/test_leak_scan.py -v` covers the planted reads. For a live check, run step 4 with `--keep`, then inspect `<id>.home/.claude/projects/` to see the transcript the scan read.

## Risk Assessment

### Technical Risks

- **Runtime transcripts under a redirected home.** Whether Claude Code (through the SDK) and Codex write their session transcripts into the scrubbed home, and in what layout, is not yet checked. The layouts are external formats and can change between runtime versions.
- **Leak scan coverage.** The scan sees tool inputs only. A producer that writes and runs a script reading the checkout goes undetected.

### Mitigation Strategies

- The D6 spike runs first. A runtime that writes no transcript into the scrubbed home becomes a `BLOCKED:` line for the PM before the runner is built. Parsers fail into `scan_unavailable` rather than "clean", and they cross-check tool-call counts.
- Records say `no_leak_detected`, never "not leaked". `LEAK_RULES_VERSION` lets 425 exclude results scanned under older rules.

## Implementation Notes

### Development Approach

1. **Transcript spike.** In a 421 scrubbed sandbox, run one small dispatch per profile (`sdk`, `openai-oauth`). Confirm where each transcript lands, capture fixtures, and record the answer in the DEVLOG.
2. `ProducerStep`, `producer_only_definition`, `--producer-only`, and the reserved param and resume handling, with tests over `P6`, `implement` and `fix`. Add prompt-only rendering and `commands/sq/run.md`.
3. D9: SDK `max_budget_usd` and the `error_max_budget_usd` mapping, with the CHANGELOG bullet. File the Codex/OpenAI-compatible enforcement issue.
4. Records, `DiffSidecars` and the store methods.
5. Transcript sources and the leak scan, against the spike fixtures.
6. `FixCaseRunner` and `replay_one`, with injected doubles for every outcome in D10.
7. `bench_plan` and `bench_runner`: identity, lock, interruption, sweep, bound, cap, resume, `--retry-harness`.
8. CLI and slash command. Run walkthrough steps 1–7 on squadron.

Effort: 4/5.

### Special Considerations

- The harness runs the installed, current `sq`. The producer's tools see only the start commit's `sq` inside the tree. That split is deliberate: the pipeline under test is the current production pipeline, and the code under change is the start commit.
- `--keep` leaves the scrubbed home in place, and it holds symlinks to the user's auth files (421 D8). The CLI prints that warning beside the kept paths.
- Benchmark replays write no run state to the user's runs directory, so `sq stats producers` never sees them. `--replay` is not needed.
