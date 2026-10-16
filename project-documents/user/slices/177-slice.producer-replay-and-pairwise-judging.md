---
docType: slice-design
slice: producer-replay-and-pairwise-judging
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [176, 320]
interfaces: []
dateCreated: 20261016
dateUpdated: 20261016
status: not_started
---

# Slice Design: Producer Replay and Pairwise Judging

## Overview

Slice 176 answers "which producer config does better?" from runs that already happened (`sq stats producers`). That answer is observational: each config saw different slices, so slice difficulty is a confound. This slice is the controlled half of [#210](https://github.com/ecorkran/squadron/issues/210). It gives every config the same inputs and scores the outputs with methods that are not biased toward one model.

- **`sq replay run`** regenerates one phase artifact (a slice design or a task breakdown) for each producer config. Each config runs in an isolated, history-free checkout of the repo at the parent of the commit that first added the original artifact, so it sees exactly what the original producer saw. Every config is reviewed under the same fixed reviewer, which gives rounds-to-accept.
- **`sq replay judge`** compares the replayed first drafts in pairs with a blind LLM judge, running each pair in both orders.
- **`sq replay report`** reports, per phase, each config's quality (Bradley-Terry strength from the pairwise results, and rounds-to-accept), cost, time and failure rate, each with n.
- Every dispatch now records **prompt identity**, which 176 had to pool.

Replays and judgments are stored in the 320 metrology store as two new record types.

## Value

- **Model choice per phase becomes a controlled comparison.** For P4, "does sonnet beat haiku at slice design?" is answered on the same slices, under the same reviewer and judge, with n on every number.
- **Quality and cost in one table.** Rounds-to-accept and cost come from the replay's own pipeline run, and quality comes from the judge. A cheap config that writes worse drafts and a strong one that costs five times as much can be compared directly.
- **The project's own history is the replay set.** Every past slice design and task file is a ready-made test case. No curated dataset is needed, which matches 320's principle.
- **Prompt identity on every dispatch.** Future observed reports can tell template revisions apart, instead of pooling them silently.

## Technical Scope

**Included:**

1. **Start-point resolution (D2).** For a phase and slice index, find the commit that first added the original artifact, its parent (the start point), and the original first draft.
2. **Replay sandbox (D3).** A depth-1 fetch of the start point into a fresh directory under `~/.config/squadron/replays/`, registered as a temporary cf project, and removed afterwards. Stale sandboxes are swept on the next run.
3. **Replay runner (D4).** For each config, run the phase pipeline (`P4` for design, `P5` for tasks) as an `sq run` subprocess inside the sandbox, with the config's model, the fixed reviewer and a revision cap. Then read the run's outcome, rounds, cost, wall time and the first and final artifact text, and write a `producer_replay` record.
4. **Pairwise judge (D5).** For every pair of contestants in a replay set, two judge calls (A then B, and B then A), comparing first drafts with frontmatter stripped. One `pairwise_judgment` record per pair.
5. **Bradley-Terry aggregation and report (D6, D7).** `sq replay report` with `--json`.
6. **Prompt identity (D8).** Dispatch metadata records the delivered prompt's SHA-256 and source, the squadron version, and the cf and guide versions reported by `build_context`. `sq stats producers` reports how much of its data carries this.
7. **Hidden `--run-id` option on `sq run`**, which creates a fresh run under a chosen id and refuses an existing one. It is distinct from `--resume`. The runner uses it to know which run state file is its own (D4).
8. **Config key `metrology.judge_timeout_s`**, a wall-clock bound on each judge call (D5).
9. A `/sq:replay` slash command that passes its arguments through, in the same pattern as `/sq:stats`.

**Excluded:**

- **The downstream-outcome scorer** (#210: did the design lead to code that passed review?). It is slow and every later phase is a confound. #210 lists it as a long-term check.
- **The human blind sample of judge picks.** 320's blind capture applies to judge results, and a pairwise pick is not a `JudgeResultRef`. Checking the pairwise judge against a human is a follow-on issue, filed when this slice lands.
- **Varying the prompt template as a config dimension.** A replay always uses the guide and cf prompts present at the start point and on this machine. A config is a model alias (D1).
- **An `--effort` flag.** Effort comes from the alias, so an effort variant is a separate alias in `~/.config/squadron/models.toml` ([#220](https://github.com/ecorkran/squadron/issues/220)). The SDK session path does not send effort ([#216](https://github.com/ecorkran/squadron/issues/216)). The report shows the effort actually sent.
- **Concurrent replays.** Configs run one after another ([#146](https://github.com/ecorkran/squadron/issues/146) covers concurrency).
- **Phases other than design and tasks.** P6 replays need code execution and tests in the sandbox, which is a different problem.
- **The `sol` alias as judge or reviewer** until [#224](https://github.com/ecorkran/squadron/issues/224) is fixed. Nothing in the design picks a model: judge and reviewer are required arguments.
- **An eval tool.** Decided in 176 D1 and not reopened: the method is borrowed, no tool is adopted.

## Dependencies

### Prerequisites

- **176** (complete): `GitHistory` (`stats/git_history.py:91`, `first_added` at 155, `Commit.parents`), `ProducerKey` and `extract_units` (`stats/producer_units.py`), `action_usage_row` and `usage_totals` (`stats/usage_report.py:184,99`), per-round run state (`StepState.prior_round_results`, `accepted`, `exhausted`), and the `metrology.min_evidence_n` floor.
- **320** (complete): `MetrologyStore` (`metrology/store.py:106`) and its pattern for adding a record type with no migration: a `RECORD_TYPE_*` constant, a payload model, an optional sibling field on `MetrologyRecord`, and `write_*` / `list_*` methods (`metrology/models.py:28-31,278-294`). Also `ProjectId` and `derive_project_id` (`metrology/identity.py:131`).
- **175** (complete): `UsageRecord` in `ActionResult.metadata["usage"]`, and `one_shot_dispatch_with_telemetry` for the judge call.
- The `P4` and `P5` built-in pipelines (`data/pipelines/`), with their `review-model`, `max-revisions` and loop `commit_each_iteration` behavior.

### Interfaces Required

- `sq run <pipeline> <slice> -m <alias> -p review-model=<alias> -p max-revisions=<n>`, run as a subprocess with `cwd` set to the sandbox. A subprocess is required: the cf client and the SDK session both use the process cwd (`integrations/context_forge.py:112-133`, `pipeline/sdk_session.py:568-578`).
- `StateManager.init_run(..., run_id=...)` (`pipeline/state.py:332`) already creates a run under a caller-chosen id. `_run_pipeline`'s `run_id` parameter is the resume path (`cli/commands/run.py:284-308`: it skips `init_run` and claims an existing file), so it is not used for this (D4).
- cf: `cf init --lite --no-ide --name <n>` to register the sandbox, and `cf project rm <n>` to remove it.
- `StateManager.load(run_id)` (`pipeline/state.py:630`).
- `LoopCondition.REVIEW_CONCERNS_OR_BETTER` (`pipeline/loop_config.py`), the single definition of an accepted verdict.

## Architecture

### Component Structure

| Component | Location | Role |
|---|---|---|
| Start point | `replay/start_point.py` (new) | `resolve_start_point(phase, index, history) -> StartPoint` |
| Sandbox | `replay/sandbox.py` (new) | `ReplaySandbox` context manager: create, cf register, remove; `sweep_orphans()` |
| Runner | `replay/runner.py` (new) | `run_replay_set(...)`: per config, subprocess `sq run`, collect outcome, write record |
| Judge | `replay/judge.py` (new) | prompt assembly, the two-order call, verdict parsing |
| Judge prompt | `data/replay/pairwise-judge.md` (new) | the packaged judge instructions, hashed for judge identity |
| Aggregation | `replay/bradley_terry.py` (new) | pure function over win/loss/tie counts |
| Report core | `replay/report.py` (new) | `replay_report(phase, judge, store, min_n) -> ReplayReport` |
| Records | `metrology/models.py`, `metrology/store.py` | `producer_replay` and `pairwise_judgment` types and their store methods |
| Prompt identity | `pipeline/actions/cf_op.py`, `pipeline/actions/dispatch.py` | `build_context` outputs gain `cf_version` and `guide_version`; dispatch metadata gains `prompt` |
| CLI | `cli/commands/replay.py`, `cli/replay_views.py` (new); `cli/commands/run.py` | `run`, `judge` and `report` subcommands; the hidden `--run-id` |
| Slash command | `commands/sq/replay.md` (new) | passthrough |

`replay/` depends on `metrology/` (store and records) and `stats/` (git history, usage rows). Nothing in `metrology/` or `stats/` depends on `replay/`. The cores take the store, the history and a subprocess runner as parameters, so tests run them without git or a model.

### Data Flow

```
sq replay run --phase design --slice 176 --config A --config B --reviewer R --max-revisions N
  │
  ├─ GitHistory ─► StartPoint(original_sha, start_sha, original first draft)
  ├─ for each config:
  │    ReplaySandbox(start_sha) ── depth-1 fetch, cf init --lite
  │      └─ subprocess: sq run P4 176 -m A -p review-model=R -p max-revisions=N --run-id X
  │    read run state X ─► outcome, rounds, first verdict, cost, prompt identity
  │    read sandbox git ─► first-draft text, final text
  │    MetrologyStore.write_replay(ProducerReplay)
  │    sandbox removed (cf project rm, directory deleted)
  ▼
sq replay judge --phase design --slice 176 --judge J
  │  contestants = replays in the set + the original first draft
  │  for each unjudged pair: J(A, B) and J(B, A) ─► MetrologyStore.write_judgment
  ▼
sq replay report --phase design --judge J
     list_replays + list_judgments ─► Bradley-Terry ─► table / --json
```

### State Management

Replays and judgments persist as metrology records (D9). Everything derived from them (Bradley-Terry strength, medians, rates) is computed when the report is read and never stored, as in 175 and 176. A sandbox exists only while its config runs. The only other persistent change is additive metadata in run state: dispatch `metadata["prompt"]` and two `build_context` output keys, with no schema version bump.

## Technical Decisions

### D1 — A producer config is a model alias

A config is one alias. The alias fixes model, profile and, optionally, effort. The record stores what the alias resolved to (`model`, `profile`) and the effort actually sent (from the dispatch's `UsageRecord.effort`; `None` when not sent). The report keys rows on (alias, model, profile, effort sent), which is 176's `ProducerKey` without the reviewer: the reviewer is fixed per replay set, so it is a report heading, not a key.

Prompt template is not a config dimension here. Within one replay set every config gets the same start point and the same prompts. Across sets the prompt identity is recorded (D8) and shown, not keyed.

### D2 — Start point from git history

| Phase | Original artifact path pattern |
|---|---|
| `design` | `project-documents/user/slices/{index}-slice.*.md` |
| `tasks` | `project-documents/user/tasks/{index}-tasks.*.md` |

`GitHistory.first_added(pattern)` gives the commit that added the artifact. Paths under `archive/` do not count. The start point is that commit's first parent. The original first draft is the file's content at the adding commit (`GitHistory.show`), which is the original producer's first draft. Comparing it with the replays' first drafts gives a fixed historical baseline contestant (`original`) at no dispatch cost.

The slice name comes from the original file name, and the runner passes it explicitly. For a design, the slice plan entry at the start point may not carry the `(index)` prefix yet: Phase 4 adds it in the same commit as the design. Whether `sq run P4 <index>` resolves the slice in that state is the first implementation task, verified against slice 176's real start point. If it does not resolve, the runner fails before any dispatch, with an error naming the slice and the start commit. It does not edit the plan entry to make it work.

Errors: no adding commit found means exit 1, naming the pattern. A root commit (no parent) means exit 1.

### D3 — A history-free sandbox, not a git worktree

The slice plan says "throwaway worktrees". A git worktree shares the repository's refs and objects, so a tool-using producer can read the original artifact from `main` (`git show main:…`, `git log --all`). That leaks the answer. The sandbox is a fresh repository instead:

```
git init <dir>
git -C <dir> fetch --depth 1 <repo_root> <start_sha>
git -C <dir> checkout --detach FETCH_HEAD
git -C <dir> switch -c replay/<replay_id>
```

It contains exactly one commit and no refs to later history. The directory is `~/.config/squadron/replays/<replay_id>/`.

The sandbox is registered with cf as `replay-<replay_id>` (`cf init --lite --no-ide --name …`), because cf resolves the project from the cwd and `P4`/`P5` run cf operations. On exit, which includes errors and Ctrl-C, the sandbox runs `cf project rm` and deletes the directory.

**Lock and orphans.** The design borrows the codehost scratch-worktree pattern (`codehost/worktree.py`: `WorktreeLock`, `_is_orphan`, `sweep_orphans`) and does not invent a new one. On creation the sandbox writes `<dir>.lock` beside its directory, holding the owning process's pid and start time, the same fields `WorktreeLock` records. A lock is live while a process with that pid exists and has the same start time, so a recycled pid does not count as the owner. `sq replay run` first sweeps:
- sandbox directories whose lock is missing or not live;
- cf projects named `replay-*` whose path no longer exists.

A sandbox with a live lock, such as one belonging to a concurrent `sq replay` process, is left alone. The sweep never raises, and each removal or failed removal is logged at WARNING. If the shared helpers in `codehost/worktree.py` are tied to `PullRequestRecord`, the lock and liveness check are extracted into a shared module rather than copied.

A start point with a `.gitmodules` file fails with an error naming it. Submodule replay is out of scope; squadron has none.

### D4 — Runner: one `sq run` subprocess per config

The runner chooses the run id, then runs:

```
sq run P4 <index> -m <alias> -p review-model=<reviewer> -p max-revisions=<n> --run-id <run_id>
```

It runs with `cwd=<sandbox>`, using the same `sq` executable as the parent (`sys.argv[0]` resolved). A subprocess keeps the executor, the cf client and the SDK session unchanged: all three use the process cwd.

The hidden `--run-id` option is new, and it is distinct from `--resume`. `_run_pipeline` today treats any `run_id` as a resume. It skips `init_run` and claims an existing file, so passing the id there would create no run state. The change: `_run_pipeline` gains a `new_run_id` parameter, which goes to `init_run(..., run_id=new_run_id)` on the fresh-run path. Passing both `new_run_id` and `run_id` is a `ValueError`. `init_run` gains a check that fails with `FileExistsError` when a file with that id already exists, so a chosen id never overwrites a run. No caller in `src/` passes an id to `init_run` (`run.py:308,727`), and the two tests that do use fresh directories, so the check changes nothing for existing code.

Before any dispatch, the runner prints the plan (start commit, configs, reviewer, revision cap, upper bound on LLM calls = configs × 2 × (1 + cap): the phase step's dispatch and review, then one dispatch and one review per loop round) and asks for confirmation. `--yes` skips the prompt. A non-interactive session without `--yes` exits 1.

After the subprocess exits, the runner reads run state `<run_id>`:

| Run state | `outcome` | Notes |
|---|---|---|
| completed, loop `accepted` | `accepted` | `rounds` = rounds to acceptance |
| completed with `exhausted` and not accepted, or paused at the loop's exhaust checkpoint | `exhausted` | `rounds` = the cap + 1 |
| failed | `failed` | `failure_class` from the failed step: `dispatch_error`, `stall`, `no_artifact` (945 post-condition), or `other` with the error text |
| no run file | `failed` | `failure_class = no_run_state`, subprocess exit code and stderr tail recorded |

The first draft is the artifact's content in the sandbox commit that added it (`commit_each_iteration` commits every round). The final text is the working file. Cost and LLM-action counts come from `action_usage_row` over every round of the phase and loop steps, with priced k of m. Wall time is measured around the subprocess.

Order of operations: the record is written before the sandbox is removed. A store write failure stops the set with an error and keeps the sandbox for inspection, with its path in the error.

Configs run in the order given. A failed config does not stop the set; the failure is the data. The command's exit code is 0 when every config produced a record, whatever the outcomes.

### D5 — Pairwise judge with order swap, on first drafts

**What is compared.** First drafts. The final text has the reviewer's fingerprints on it, and rounds-to-accept already measures the loop. The first draft is the producer's unaided work. YAML frontmatter is stripped before judging.

**Inputs to the judge.** The packaged judge prompt, the task the producer was given (the `build_context` stdout recorded in the first replay's run state, re-read from the store record), and the two drafts labeled `A` and `B`. The judge dispatches through `one_shot_dispatch_with_telemetry` with tools off, as a text-only comparison.

**Verdict.** The prompt asks for a short rationale and a final line `WINNER: A`, `WINNER: B` or `WINNER: TIE`. The parser takes the last line that matches `winner\s*[:=]\s*(a|b|tie)`, case-insensitive with any surrounding whitespace or markdown emphasis. Anything else is `invalid`, and the raw tail is stored.

**Order swap.** Each pair runs twice, once with the drafts swapped. The pair outcome is:

| First call | Second call (swapped) | Outcome |
|---|---|---|
| X wins | X wins | X wins |
| tie | tie | tie |
| X wins and tie, in either order | | tie |
| X wins | Y wins | `inconsistent`, counted as a tie for aggregation and reported separately as the judge's position-consistency rate |
| either call `invalid` | — | `invalid`, excluded from aggregation and counted |

**Contestants.** Every `producer_replay` in the set whose outcome is not `failed` (a failed run has no draft), plus `original`. `sq replay judge` judges only pairs that do not yet have a judgment from that judge, so re-running after adding a config costs only the new pairs. Pairs: k(k−1)/2 for k contestants, two calls each.

**Time bound.** `one_shot_dispatch_with_telemetry` has no wall-clock bound of its own, and 174's stall bounds cover SDK session turns, not this path. Each judge call is therefore wrapped in `asyncio.wait_for`, bounded by a new config key `metrology.judge_timeout_s` (`int`). The key is defined in `config/keys.py` beside `metrology.audit_timeout_s`, whose pattern it copies (`metrology/audit.py:610,682`). Its default is 600 and lives only in that definition. A timeout cancels the call and is treated the same as a call that raises.

**Half-recorded pairs.** A pair is recorded only when both calls return. If the first call returns and the second raises or times out, the first call's usage is logged at WARNING, giving the pair, tokens and cost, so the money spent stays visible. The pair stays unjudged, and the next `sq replay judge` repeats both calls. Recording a half pair would need a second outcome model for one-sided picks, and those are exactly what order swap exists to discard.

**Judge identity.** Alias, resolved model, and the SHA-256 of the packaged judge prompt. Judgments from a different prompt hash are a different judge.

**Self-preference.** When the judge's resolved model equals a contestant's model, the report prints a warning on that table. It does not exclude anything.

### D6 — Bradley-Terry, not Elo

Elo depends on the order games are played. Bradley-Terry fits all comparisons at once and handles an incomplete comparison graph, which is what pooling pairs across slices gives. The fit is Hunter's MM iteration over win counts, with a tie counted as half a win to each side. It stops when the largest change in strength is below 1e-9, or after 10,000 iterations (logged at WARNING if it hits the limit). Strengths are normalized so their geometric mean is 1. The fit is a pure function in `replay/bradley_terry.py`, about forty lines, with no new dependency.

A contestant with zero wins has no finite maximum-likelihood strength. The report shows `—` for it and states why, rather than forcing a number with a prior. A comparison graph that is not connected is fitted per connected component, and the report says so.

### D7 — Report shape

`sq replay report [--phase design|tasks] [--judge ALIAS] [--json]` prints one table per (phase, reviewer, judge):

| Column | Meaning |
|---|---|
| config | alias (model, profile, effort sent) |
| n | replays of this config |
| failed | failed / n |
| accepted | accepted / (n − failed) |
| rounds | median rounds to accept (accepted replays only) |
| cost | median cost per replay, `k of m priced` |
| time | median wall time |
| BT | Bradley-Terry strength |
| W-L-T | pairwise record after order swap |
| pairs | judged pairs, with `invalid` and `inconsistent` counts |

The `original` contestant appears as a row with only BT, W-L-T and pairs. A config with fewer judged pairs than `metrology.min_evidence_n` is marked `below floor` and gets no rank. The footer gives the slices covered, the judge's position-consistency rate, and the prompt identities seen (D8).

`--json` mirrors the table. Its keys are not a stable contract.

### D8 — Prompt identity on every dispatch

`build_context` adds two output keys: `cf_version`, from `cf --version` (read once per client), and `guide_version`, from `<cwd>/project-documents/ai-project-guide/.context-forge-guide-version`, or `None` when the file is absent.

Every dispatch adds `metadata["prompt"] = {"sha256": …, "source": "build_context" | "feedback" | "explicit" | "review_findings", "squadron_version": …, "cf_version": …, "guide_version": …}`. This applies to all dispatches, not only replays.
- **`sha256`** is computed over the prompt actually delivered: the text `_resolve_prompt` returns after `_apply_override` and `_apply_pre_emption_fragment` (`pipeline/actions/dispatch.py:671`). Two dispatches that told the model different things never share a hash.
- **`source`** names the branch `_resolve_prompt` took.
- **`squadron_version`** is always set, because squadron composes part of every prompt (revise guidance, rules blocks, pre-emption fragments).
- **`cf_version`** and **`guide_version`** are copied from the latest `build_context` when the source is `build_context`, and are `None` otherwise.

The prompt hash differs across days, because `cf build` embeds the date. So it identifies a prompt, not a template. Template revision is identified by the tuple `(squadron_version, cf_version, guide_version)`. A release that changes how squadron composes prompts therefore shows up as a different identity instead of being pooled silently.

`sq stats producers` keeps pooling across template revisions. Splitting its key by guide version would push most cells below the floor, since the guide changes weekly. Its footer gains a line: `k of n units carry prompt identity; m guide versions`. The replay report lists the identities each table covers.

### D9 — Two metrology record types

Both are added with 320's pattern (no migration, `_SCHEMA_VERSION` stays 1). They replace the single `producer_score` named in 176 D1: a replay outcome and a judgment are different facts with different lifetimes, and a "score" is derived.

`producer_replay` (id `replay-{YYYYMMDD}-{uuid8}`):

```python
class ProducerReplay(BaseModel):
    replay_set: str            # sha256 of (project_id, phase, slice_index, start_sha, reviewer alias, max_revisions)
    project_id: ProjectId
    phase: ReplayPhase         # enum: DESIGN, TASKS
    slice_index: int
    slice_name: str
    original_sha: str
    start_sha: str
    config: ProducerConfigRef  # alias, model, profile, effort_sent
    reviewer: ModelRef         # alias, model
    max_revisions: int
    run_id: str
    outcome: ReplayOutcome     # enum: ACCEPTED, EXHAUSTED, FAILED
    failure_class: str | None
    rounds: int | None
    first_verdict: str | None
    cost_usd: float | None
    priced: tuple[int, int]
    wall_seconds: float
    prompt: PromptIdentity | None
    task_prompt: str | None    # build_context stdout, for the judge
    first_draft: str | None
    final_text: str | None
    squadron_version: str
    created_at: datetime
```

`pairwise_judgment` (id `pair-{YYYYMMDD}-{uuid8}`): `replay_set`, `phase`, `judge` (alias, model, prompt hash), `a` and `b` (a replay record id or `original:<sha>`), `first_call` and `second_call` (pick and raw tail), `outcome` (`A`, `B`, `TIE`, `INCONSISTENT`, `INVALID`), the two `UsageRecord`s, and `created_at`.

New store methods: `write_replay`, `list_replays(project_id, phase=None, replay_set=None)`, `write_judgment`, `list_judgments(project_id, phase=None, judge=None)`. They follow the existing list pattern: glob, skip unreadable files with a WARNING, filter in memory.

Drafts live inside the record. A slice design is tens of kilobytes, and one file per record is the store's existing shape. If `list_*` cost becomes visible, an index is a later change.

### D10 — Failure modes

| Failure | Behavior | Signal |
|---|---|---|
| No commit added the original artifact | nothing run | error naming the pattern, exit 1 |
| Adding commit is a root commit | nothing run | error, exit 1 |
| Slice does not resolve at the start point (D2) | nothing run | error naming slice and start sha, exit 1 |
| Start point has `.gitmodules` | nothing run | error, exit 1 |
| Not interactive and no `--yes` | nothing run | error, exit 1 |
| `git fetch` or `cf init` fails in the sandbox | that config not run, sandbox removed, next config runs | ERROR with the command's stderr; summary line; exit 1 at the end |
| `sq run` hangs | the pipeline's own stall bounds (174) end the dispatch and the run fails; Ctrl-C ends the set and the sandbox is cleaned up | stall recorded as `failure_class = stall` |
| `sq run` exits with no run file | record with `failure_class = no_run_state` | WARNING with the exit code and stderr tail |
| Store write fails | set stops; sandbox kept | error naming the sandbox path, exit 1 |
| Sandbox cleanup fails (cf rm or delete) | set continues | WARNING naming the path or project; next run's sweep retries |
| Judge dispatch raises | that pair not recorded; other pairs continue | ERROR naming the pair; summary count; exit 1 at the end |
| Judge call hangs | cancelled after `metrology.judge_timeout_s`; handled as a raise | ERROR naming the pair and the bound |
| Second call of a pair fails after the first returned | pair not recorded; both calls repeat on the next run | WARNING with the first call's tokens and cost |
| Judge reply has no verdict line | pair recorded as `INVALID` with the raw tail | counted in the report's `pairs` column |
| A record file is unreadable | skipped | WARNING (store's existing behavior) |
| BT fit hits the iteration cap | strengths reported as fitted | WARNING; footer note |
| No replays for the phase | empty report | message, exit 0 |

## Implementation Details

### API Contracts

```
sq replay run --phase design|tasks --slice INDEX --config ALIAS [--config ALIAS ...]
              --reviewer ALIAS --max-revisions N [--yes]
sq replay judge --phase design|tasks --slice INDEX --judge ALIAS [--yes]
sq replay report [--phase design|tasks] [--judge ALIAS] [--json]
sq run ... --run-id ID          (hidden)
```

`--reviewer`, `--judge` and `--max-revisions` have no defaults. `sq replay judge` confirms the number of judge calls before it starts, in the same way as `run`.

```python
# replay/start_point.py
@dataclass(frozen=True)
class StartPoint:
    phase: ReplayPhase
    slice_index: int
    slice_name: str
    artifact_path: str
    original_sha: str
    start_sha: str
    original_first_draft: str

def resolve_start_point(phase: ReplayPhase, index: int, history: GitHistory) -> StartPoint: ...

# replay/bradley_terry.py
def fit(outcomes: Sequence[PairOutcome]) -> BTFit: ...  # strengths per contestant, components, iterations, converged
```

### UI Specifications

```
Producer replay — design   reviewer: opus   judge: opus (prompt 3f9a1c)
config                          n  failed  accepted  rounds  cost (priced)    time     BT    W-L-T   pairs
sonnet (claude-sonnet-5-5, sdk) 3  0/3     3/3       1       $0.41 (3 of 3)   6m12s    1.42  4-1-1   6
haiku  (claude-haiku-5-5, sdk)  3  1/3     1/2       3       $0.09 (3 of 3)   4m40s    0.61  1-4-1   6  below floor
original                        —  —       —         —       —                —        1.15  3-3-0   6
slices: 175, 176, 321 · position consistency 83% (10 of 12) · prompt identity: cf 0.19.11, guide v0.20.12, v0.21.0
⚠ judge model equals a contestant's model (sonnet)
```

The values are illustrative.

## Integration Points

### Provides to Other Slices

- **#210 decision**: the per-phase table #210 asks for. #210 can close when this slice lands; the downstream-outcome scorer and the human check of pairwise picks become their own issues.
- **Prompt identity** in dispatch metadata, for any later report that wants to separate template revisions.
- **`producer_replay` and `pairwise_judgment` records** in the shared store, available to 321's dispersion approach if a second judge is added later.

### Consumes from Other Slices

- **176**: `GitHistory` and the usage-row readers. Pre-176 run state has no per-round data, but replays are always new runs, so this does not apply.
- **320**: the store and `ProjectId`. A store directory override (`metrology.store_dir`) applies to replays as well.
- **175**: usage records. An unpriced model shows `k of m priced`, never $0.

## Success Criteria

### Functional Requirements

1. `sq replay run --phase design --slice 176 --config A --config B --reviewer R --max-revisions 1 --yes` writes one `producer_replay` record per config with outcome, rounds, cost, wall time, prompt identity and both texts. The sandbox repository contains one commit and no ref to later history.
2. After the run, no directory remains under `~/.config/squadron/replays/` and no `replay-*` project remains in `cf project list`.
3. A config whose pipeline fails produces a `failed` record with a failure class, and the remaining configs still run.
4. `sq replay judge` makes two calls per unjudged pair, writes one `pairwise_judgment` per pair with the order-swap outcome, and on a second invocation with the same judge makes no calls.
5. `sq replay report` shows the D7 table with n on every cell, `below floor` marking, the `original` row, position consistency, and prompt identities. `--json` carries the same fields.
6. Every dispatch in a new pipeline run carries `metadata["prompt"]`. `build_context` outputs carry `cf_version` and `guide_version`. `sq stats producers` shows the prompt-identity footer line.

### Technical Requirements

- The Bradley-Terry fit is tested against a hand-computed three-contestant case, a contestant with zero wins, and a disconnected graph.
- The verdict parser is tested with real judge replies captured during verification: plain, markdown-bold, lowercase, trailing whitespace, and a reply with no verdict.
- Start-point resolution is tested on a fixture repo, and once against slice 176's real history.
- Runner and judge tests use an injected subprocess runner and dispatcher; no test makes a model call.
- Every D10 row has a named test.
- ruff, ruff format and pyright are clean.
- README gets a `sq replay` section; CHANGELOG gets a bullet; `commands/sq/replay.md` is added.

### Integration Requirements

- Existing pipelines run unchanged apart from the added metadata keys. The run state schema version is unchanged.
- Older metrology files load unchanged.

### Verification Walkthrough

These commands do not exist yet. Model aliases are examples from this repo's `models.toml`; pick any, except `sol` until #224 is fixed. The run makes real dispatches.

1. Replay slice 176's design with two configs, one revision allowed:
   ```
   sq replay run --phase design --slice 176 --config sonnet --config haiku --reviewer opus --max-revisions 1
   ```
   The plan prints the start commit (the parent of the commit that added `176-slice.effort-calibration-and-producer-model-effectiveness.md`) and the dispatch bound, then asks for confirmation. Each config prints its outcome when it finishes.
2. Confirm cleanup: `ls ~/.config/squadron/replays/` is empty, and `cf project list | grep replay-` prints nothing.
3. Inspect a record: `ls ~/.config/squadron/metrology/replay-*.json`, then open one and confirm `start_sha`, `outcome`, `rounds`, `cost_usd`, `prompt` and a non-empty `first_draft`.
4. Judge: `sq replay judge --phase design --slice 176 --judge opus`. With two configs plus `original` there are 3 pairs and 6 calls. Run it again: it reports 0 pairs to judge.
5. Report: `sq replay report --phase design`. Expect the table with three rows, `below floor` on every row (n is below 5), and the self-preference warning absent (opus is not a contestant).
6. Prompt identity: `sq stats run <latest run id> --json` shows `metadata.prompt` on the dispatch actions, and `sq stats producers` shows the prompt-identity footer.
7. Failure path: replay with an alias that has no credentials configured. The record shows `outcome: failed` with a failure class, and the other config still runs.

## Risk Assessment

### Technical Risks

- **Slice resolution at a design's start point.** The plan entry gets its index in the same commit as the design (D2). If `sq run P4 <index>` cannot find the slice there, design replays fail for every slice made by the current process.
- **Cost.** Each config can make up to 2 × (1 + cap) LLM calls, plus judge calls that grow with k².

### Mitigation Strategies

- The first implementation task runs D2's resolution against slice 176's real start point, before any runner code is written. If it fails, the design comes back to the Project Manager with the evidence.
- Confirmation before every `run` and `judge`, with the bound printed, and `--max-revisions` required.

## Implementation Notes

### Development Approach

1. Spike: create a sandbox at slice 176's design start point by hand and run `sq run P4 176` there with the cheapest alias. Record the result in the task file. This settles the D2 risk.
2. Prompt identity (D8): `build_context` keys, dispatch metadata, the `sq stats producers` footer. Independent of everything else, and it starts collecting data on normal runs at once.
3. Record types and store methods (D9).
4. Start point and sandbox, including the orphan sweep and the hidden `--run-id`.
5. Runner and `sq replay run`.
6. Judge, verdict parser and `sq replay judge`.
7. Bradley-Terry and `sq replay report`.
8. Docs, slash command, verification walkthrough, and the #210 comment and follow-on issues.

### Special Considerations

- The sandbox runs the installed squadron against old inputs. Pipelines and prompts behave as they do today; only the repository content is historical. That is the intended comparison: today's tooling, the same inputs, different models.
- Judge calls send whole drafts to the judge's provider, as reviews already do. Nothing new leaves the machine.
- Effort is 4/5, raised from the plan entry's 3/5: two new record types, a sandbox with cleanup guarantees, a subprocess runner, a judge and a report. The plan entry is updated to match.
