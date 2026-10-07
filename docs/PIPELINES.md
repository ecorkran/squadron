---
docType: guide
title: Pipeline Authoring Guide
dateCreated: 20260410
dateUpdated: 20260714
---

# Pipeline Authoring Guide

Pipelines let you compose multi-step AI workflows and run them with a single command.

```bash
sq run P456 152           # run the built-in slice lifecycle pipeline
sq run example --list     # list all available pipelines
```

---

## Quick Start

Three commands to verify the system works before reading further:

```bash
sq run --list                         # show all available pipelines with descriptions
sq run P456 152                       # run the full slice lifecycle for slice 152
sq run example 152 --dry-run          # show the step plan, and the items each "each" step would select, without executing
```

---

## YAML Grammar Reference

Each pipeline is a YAML file with a fixed top-level structure. The pipeline's name is its file name: `sq run my-loop` runs `my-loop.yaml` (case-insensitive), and that name is what `sq run --list`, commit messages, DEVLOG entries, batch reports and summary files use.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | no | A label for people reading the file. Ignored by squadron; the file name is the pipeline's name |
| `description` | string | yes | One-line description shown in `sq run --list` |
| `params` | map | no | Parameter declarations (`name: required` or `name: default-value`) |
| `model` | string | no | Pipeline-level default model alias |
| `steps` | list | yes | Ordered list of step definitions |

### Parameter placeholders

Parameters declared in `params` can be referenced anywhere inside step configs using `{param_name}` syntax.

**Required vs default params:**
- `param: required` — caller must supply the value positionally or with `--param param=value`
- `param: sonnet` — default applied automatically when caller does not override

**YAML quoting — mandatory:**

When a placeholder is the entire field value, it must be quoted:

```yaml
# CORRECT
model: "{model}"

# WRONG — bare braces parse as a YAML flow mapping and cause a load error
model: {model}
```

This applies whenever `{...}` is the full value of a scalar field. If the placeholder is embedded in a longer string (`"Reviewing slice {slice}"`) no quoting is needed.

### Step syntax

Each step is a single-key YAML map. The key is the step type; the value is the step config:

```yaml
steps:
  - design:          # step type: design
      phase: 4       # step config
      model: opus
```

### Scalar shorthand

For steps that accept a single string config, you can use the `key: value` shorthand:

```yaml
steps:
  - devlog: auto     # equivalent to: devlog: {mode: auto}
```

---

## Step Type Catalog

### Phase steps: `design`, `tasks`, `implement`

**Purpose:** Run a Context Forge phase — build context, dispatch to the LLM, optionally review the output, and commit the result.

**Expansion sequence:**
[`cf-op(set_arch)`] → `cf-op(set_slice)` → `cf-op(set_phase)` → `cf-op(build_context)` → `dispatch` → [`review` → `checkpoint`] → `commit`

The `commit` stages only the files the step produced — see [Commits](#commits).

The cf calls follow Context Forge's switching rule: arch (which switches the initiative and sets its slice plan), then slice (which must be in that plan), then phase, then build. `set_arch` runs only when the step has a `plan:` key.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `phase` | int | yes | Context Forge phase number |
| `plan` | string | no | Architecture index of the slice plan to work in (e.g. `"900"`). Switches cf to the arch that owns that plan (read from the plan file's `parent:`) before setting the slice. Never runs `cf set plan` |
| `model` | string | no | Model alias for the dispatch action |
| `review` | string or dict | no | Review template name, or `{template, model}` dict |
| `checkpoint` | string | no | When to pause: `always`, `on-concerns`, `on-fail`, `never` (default: `never`) |
| `existing` | string | no | `create` (default) — the dispatch always writes the artifact. `keep` — skip the model call and go straight to the review (and any revise loop) when there is already something to review: for a slice's `design` or `tasks` step, its file exists; for `implement`, the slice branch has commits of its own ahead of the target (merge commits don't count, so a branch that was only caught up still gets implemented). Not valid on an initiative-scoped step. `tasks-plan` uses it to re-review existing tasks; the code pipelines use it so a rerun re-reviews a slice's work instead of reimplementing it |

**Example:**

```yaml
- design:
    phase: 4
    model: opus
    review:
      template: slice
      model: minimax
    checkpoint: on-concerns
```

---

### `compact`

**Purpose:** Reduce the current session's context. Dispatches the best available mechanism per environment — no configuration required.

| Environment | Mechanism |
|---|---|
| `sq run` (true CLI) | Session-rotate: capture summary → disconnect → new session → restore |
| IDE / Claude Code CLI (prompt-only) | Dispatches `/compact` via `claude_agent_sdk.query()`, awaits `compact_boundary` |

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `model` | string | no | Model alias used for summary capture in the true-CLI rotate path |
| `instructions` | string | no | Passed to `/compact` as prompt body (prompt-only) or summary instructions (true CLI) |

**Note:** `compact:` no longer implicitly captures a summary artifact. If you need a summary artifact around a compaction, use the explicit compose pattern:

```yaml
- summary:
    emit: [file]       # capture artifact before compacting

- compact:             # reduce context in place

- summary:
    restore: true      # re-inject the captured summary
```

**Migration:** pipelines that relied on `compact:` producing a summary (via the old `emit: [rotate]` expansion) must add an explicit `summary:` step before `compact:`.

**Example:**

```yaml
- compact:
    model: minimax
    instructions: Keep the most recent branch results verbatim; drop tool-use details.
```

---

### `summary`

**Purpose:** Generate a session summary and route it to one or more destinations; or re-inject a previously captured summary (`restore: true`).

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `template` | string | no | Compaction template name (default: `default`) |
| `model` | string | no | Model alias for summary generation |
| `emit` | list | no | Destination list — see options below |
| `restore` | bool | no | If `true`, re-inject the most recent prior summary instead of generating a new one |
| `checkpoint` | string | no | Same triggers as phase steps |

**Restore mode:** `restore: true` reads the most recent `summary` result from prior steps and seeds it back into the session via `sdk_session.seed_context()`. Use after `compact:` to preserve a summary artifact across context reduction.

```yaml
- summary:
    restore: true
```

**Emit destinations:**

| Destination | Effect |
|---|---|
| `stdout` | Print to terminal |
| `clipboard` | Copy to system clipboard |
| `rotate` | Inject as compacted context and rotate the session |
| `{file: path}` | Write to file (relative to project root) |

A step whose only destination is `rotate` is skipped, with no model call, when the run has no SDK session (a non-SDK model, or prompt-only mode): there is no session context to reset. `rotate` combined with any other destination still requires an SDK session.

**Example:**

```yaml
- summary:
    template: minimal-sdk
    model: minimax
    emit: [stdout, clipboard]
```

---

### `dispatch`

**Purpose:** Send a prompt to an LLM as a standalone step, outside a phase build. Used as the fix leg of a loop body (see [Judge-Gated Cycles](#judge-gated-cycles)) or any time you need a one-off model call.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `prompt` | string | no | Prompt text. When absent, falls back to the most recent `build_context` output (same behavior as the dispatch action inside phase steps) |
| `model` | string | no | Model alias for the dispatch |
| `feedback` | string | no | `review` — revise against the most recent review in scope. The prompt becomes the step's `prompt` (if any), then that review's findings, then `Revise `<file>` in place; do not create a new file.` naming the file the review read. Takes precedence over a prior `build_context` output, which inside a batch item is the original "create a design" prompt. With no review in scope the step fails: `feedback: review but no prior review in scope` |

**Example:**

```yaml
- dispatch:
    prompt: "Address any findings from the prior review."
    model: sonnet
```

A revise round inside a loop:

```yaml
- dispatch: { name: revise, model: "{model}", feedback: review }
```

---

### `review`

**Purpose:** Standalone review outside a phase build.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `template` | string | yes | Review template name (`arch`, `slice`, `tasks`, `code`, or a `judge.*` template such as `judge.slice-vs-arch` — see [Judge-Gated Cycles](#judge-gated-cycles)) |
| `model` | string | no | Model alias for the review. If omitted and no other cascade level (CLI/step/pipeline/config) supplies one, falls back to the template's own `model:` default (e.g. `judge.slice-vs-arch` defaults to `opus`) — but prefer setting this explicitly via a named `params` entry; see the `loop` example below |
| `slice` | — | no | Not a step field — set `slice` in the pipeline's top-level `params:` block instead. `judge.*` and other slice-aware templates auto-resolve `input`/`against` from the pipeline's `slice` param |
| `judge` | dict | no | Step-level threshold override for judge templates, e.g. `{pass_floor: 90}` — merges over the template's default thresholds |
| `profile` | string | no | Provider profile. Without it the step picks one the way `sq review` does: the model alias's own profile, then the template's `profile:`, then `default_review_profile`, then `sdk`. The same cascade serves both, so a review gives the same profile either way |
| `checkpoint` | string | no | Same triggers as phase steps |

A `template` name that is not registered fails before the first step runs, naming close matches (`unknown review template 'cod'; did you mean: code?`), not at the step that uses it.

**Example:**

```yaml
- review:
    template: code
    model: minimax
```

---

### `gate`

**Purpose:** Decide one verdict from named prior results, then optionally gate on it. The gate is *where* a decision happens; a judge — a model rendering judgment — is *who* a policy may consult to make it. See [Composing a judge and a review at one gate](#composing-a-judge-and-a-review-at-one-gate) and [Requiring that findings were addressed](#requiring-that-findings-were-addressed).

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `policy` | string | no | How the gate decides: `most-severe` (default) or `findings-addressed` |
| `judge_from` | string | policy-dependent | Name of a prior `review` step whose result is the judge leg |
| `review_from` | string | yes | Name of a prior `review` step whose result is the review leg |
| `judge` | mapping | no | Model layer for policies that have one — `model:` only |
| `checkpoint` | string | no | Same triggers as phase/`review` steps — fires on the *reduced* verdict |

Which reference fields apply depends on the policy, and the wrong one is an error rather than an ignored key:

| Policy | Requires | Forbids | `judge:` block |
|---|---|---|---|
| `most-severe` | `judge_from`, `review_from` | — | rejected — no model layer |
| `findings-addressed` | `review_from` | `judge_from` | accepted |

Named steps must appear **earlier** than the `gate` step. At the top level the loader validates this at load time; inside a loop body the loop step type does, since the loader does not descend into bodies. Either way a misspelled or forward reference fails fast rather than degrading to a runtime `UNKNOWN`.

**Example:**

```yaml
- gate:
    judge_from: judge-slice
    review_from: review-slice
    checkpoint: on-concerns
```

---

### `loop`

**Purpose:** Repeat a body of steps until a condition passes or a bound is reached. The primary use is the [judge-gated cycle](#judge-gated-cycles): fix, then re-review, until a judge's score clears a floor.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `max` | int | yes | The bound — maximum number of iterations. Always explicit; there is no unbounded form. May be a `{param}` placeholder; the resolved value must be a positive integer |
| `until` | string | no | Exit condition, evaluated after each iteration completes: `review.pass`, `review.concerns_or_better`, `action.success` |
| `accept_if` | string | no | A second, lower threshold (same values as `until`, except `action.success`), applied only when `max` is reached without `until` passing. If the final round's results meet it, the step completes and is marked *accepted*; otherwise `on_exhaust` applies. Requires `until` |
| `skip_if_met` | bool | no | Before round 1, check `until` against the most recent verdict already in scope (e.g. the review a preceding phase step ran). If it passes, the loop runs zero rounds. Requires `until`. Default `false` |
| `on_exhaust` | string | no | What happens if `max` is reached without `until` (or `accept_if`) passing: `fail` (mark the step FAILED, default), `checkpoint` (pause for a human), `skip` |
| `commit_each_iteration` | bool | no | Commit after each iteration's body completes, before `until:` is evaluated. Default `false`. Rejected at validation time if the body already commits — see [`commit_each_iteration` and per-round history](#commit_each_iteration-and-per-round-history) |
| `steps` | list | yes | Body — an ordered list of step definitions, using any registered step type except `loop` and `each` |

`max`, `until` and `accept_if` may all come from pipeline params (`"{max-revisions}"`, `"{pass-threshold}"`); load-time validation skips placeholder values and checks them once they resolve.

**Post-test semantics:** `until` is evaluated only *after* an iteration's body finishes, against that iteration's own results. The one exception is `skip_if_met`, which checks the verdict already in scope before round 1 — so a phase step's own review can settle an artifact without a wasted revise round.

**Example:**

```yaml
params:
  model: sonnet
  review-model: minimax

steps:
  - loop:
      max: 3
      until: review.pass
      on_exhaust: checkpoint
      steps:
        - dispatch:
            prompt: "Fix findings from the prior review."
            model: "{model}"
        - review:
            template: judge.slice-vs-arch
            model: "{review-model}"
```

Give each model role its own named `params` entry (as above) rather than leaving a step's `model:` unset — every built-in pipeline follows this convention so a caller can retarget any model by overriding one param, without editing step bodies. See [Judge-Gated Cycles](#judge-gated-cycles) for why the review step needs an explicit model even though its judge template declares its own default.

**Resume semantics — a checkpoint pausing inside the body resumes *into* the loop.** A `checkpoint:` on a step inside a `loop` body (e.g. `on-fail`/`on-concerns` on the `review` step above) pauses the run mid-iteration. `sq run --resume` (explicit or implicit) re-enters that same loop at the paused round rather than skipping past it to the next top-level step — the round is not silently abandoned.

- **Rounds are counted per loop, not per invocation.** A loop paused at round 2 of `max: 3` resumes at round 2 and runs at most rounds 2–3. Resume never restarts the count at round 1, and never grants rounds beyond `max`.
- **A resumed round has no memory of the round before it.** `prior_iteration_step_outputs` — the prior round's inner-step results, used by e.g. a `dispatch` step's findings feedback — is empty on the first round after a resume. Only the persisted round number survives a pause; the in-memory results of round *N-1* do not. A pipeline author relying on round-to-round feedback should treat a resumed round the same as round 1: no prior-round context.
- **Every pause is logged.** When a loop's body pauses on an inner checkpoint, this is logged at WARNING — naming the pipeline, the step, the paused round, and how many rounds were not run — so an abandoned loop is never silent. Re-entering a loop above round 1 on resume is logged at INFO.
- **A `FAILED` step resumes the same way a `PAUSED` one does** — no checkpoint required. Resume returns to a failed step rather than treating it as done.

**Known limitation — `each`/`fan_out` bodies resume by restart, not re-entry.** Neither `each:` nor `fan_out:` records a per-branch round the way `loop` does, so a checkpoint pausing inside either causes resume to re-run that step's branches from the start rather than continuing from where it paused.

---

### `devlog`

**Purpose:** Write a DEVLOG entry capturing pipeline state, then commit it. The commit stages only `DEVLOG.md`, as `docs: add DEVLOG entry for slice N`.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `mode` | string | `auto` — generate entry automatically |

Prefer scalar shorthand:

```yaml
- devlog: auto
```

---

### `branch`

**Purpose:** Move the checkout onto a slice's branch, or merge that branch back. Code pipelines wrap `implement` in the pair.

```yaml
- branch: { op: enter }                       # slice defaults to "{slice}"
- branch: { op: enter, plan: "{plan}", slice: "{slice.index}" }
- branch: { op: merge, slice: "{slice.index}" }
```

| Field | Type | Required | Description |
|---|---|---|---|
| `op` | string | yes | `enter` or `merge` |
| `slice` | string | no | Slice index (default `{slice}`; use `{slice.index}` inside an `each`) |
| `plan` | string | no | `enter` only. Architecture index; cf is switched to it (`set_arch`) before entering, as phase steps do, so the slice resolves even when cf's active plan is another one. A failed `set_arch` fails the item |

Any other key is rejected.

**`enter`** puts the checkout on `{index}-slice.{name}`, creating it from the integration target (`git.integration_branch`, else `main`) or checking out the existing branch. It stops the run, naming the problem, when:

- the checkout is on a branch that is neither the target nor a slice branch;
- the working tree is not clean (it lists the paths; commit or remove them, then rerun phase 6 — the design and tasks commits from the run are kept);
- cf cannot be read, the checkout is an unregistered `cf worktree`, or the branch is checked out in another worktree.

If an earlier item ended on its own unmerged slice branch, `enter` commits that branch's leftovers (`chore: preserve uncommitted work on flagged slice N`), returns to the target with a WARNING, and carries on. A slice with no design file fails only that item.

**Catch-up.** When the slice branch already exists and the target has moved on, `enter` brings the branch up to date before any work runs (#183): a branch with no commits of its own fast-forwards; otherwise the target is merged in (`merge: main into slice N`). It never rebases, resets or forces. A conflicting catch-up is aborted, the checkout stays on the clean slice branch, and the item is flagged `branch_conflict` with the conflicted paths — resolve it on the branch and retry. The code review still diffs the branch against its merge base, so the catch-up merge isn't reviewed as slice work.

**`merge`** merges the slice branch into the target with a merge commit (`merge: slice N — name`). If the branch is already merged (an agent merged it itself), it succeeds without doing anything. A merge that fails — a conflict, or git refusing — is aborted so the target is never left mid-merge; the item is flagged and the branch stays unmerged for you. Branches are never deleted or pushed.

**Validation:** an `implement` step must come after a `branch: {op: enter}` step — earlier in its own step list, or earlier in an enclosing list than the `loop:` or `each:` that contains it. Otherwise loading fails with `implement step … needs a preceding branch: {op: enter}`. **This is a deliberate break for custom pipelines with an `implement` step:** add the enter before it, and a merge after its review. There is no compatibility flag; without the enter, `implement` would run on whatever is checked out and its commit would refuse to stage.

Built-in code pipelines (`P6`, `implement`, `P456`, `P56`) run `branch enter → implement (existing: keep) → revise-code loop → devlog → branch merge`, the same steps as each item of [`implement-plan`](#implement-plan). The revise loop revises against the code review until `pass-threshold`; if its rounds run out it accepts at `accept-threshold`, and otherwise pauses at a checkpoint before the merge. A test keeps these four in step with `implement-plan`.

---

### Commits

Phase steps, `devlog`, and loops with `commit_each_iteration` commit through one plan: only the files that step produced are staged, and the message says what they are.

**What is staged.** For a design, tasks or architecture step: the artifact, its review file, the slice plan file and `DEVLOG.md` — but only those that git shows as changed. Anything else dirty in the tree is left alone and named in a WARNING (`commit: step … left N dirty path(s) out of the commit`). The `devlog` step stages only `DEVLOG.md`. An `implement` commit stages everything, and refuses to unless the checkout is on that slice's `{index}-slice.*` branch.

**Where it commits.** Design, tasks, architecture and loop-round commits must be on the integration target; a `devlog` commit may also be on its own slice branch. Anywhere else the run stops: `planning commit for slice N on {branch}; expected {target}`.

**Messages.**

| Staged | Message |
|---|---|
| new design or tasks file (+ review) | `docs: add slice 105 design (review: CONCERNS)` |
| changed file, loop round n | `docs: revise slice 105 design, round 2 (review: PASS)` |
| review only, step's own commit | `review: add slice 105 tasks review (CONCERNS)` |
| review only, loop round n | `review: re-review slice 105 tasks, round 2 (CONCERNS)` |
| `implement` | `feat: implement slice 105 (review: PASS)` |
| architecture | `docs: revise initiative 180 architecture (review: PASS)` |
| `devlog` | `docs: add DEVLOG entry for slice 105` |

The verdict is read from the review file's frontmatter. The review clause is left out when no review file is committed. Nothing staged means no commit and a WARNING.

---

### `each`

**Purpose:** Iterate inner steps over a collection, running them once per item.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | Collection source expression |
| `as` | string | yes | Loop variable name |
| `steps` | list | yes | Inner step definitions using `{variable.field}` placeholders. Any step type except `each`; a `loop:` step runs its rounds per item |
| `on_item_failure` | string | no | `stop` (default) — a failed item fails the `each` step, as before. `continue` — a failed item is recorded as FLAGGED with its error and the next item runs; the `each` step completes |

**Source options:** each `plan` argument is an architecture index (`"900"`), passed to cf as `archIndex` so the source reads that plan without changing cf state. Anything other than digits fails the step: `plan must be an architecture index, got …`.

| Expression | Returns |
|---|---|
| `cf.unfinished_slices("{plan}")` | Slices in the plan whose status is not `complete` |
| `cf.undesigned_slices("{plan}")` | Slices that are not `complete` or `deferred` and have no design file |
| `cf.slices_needing_tasks("{plan}", "<threshold>")` | Slices that are not `complete` or `deferred`, have a design file, and either have no task file or have one whose tasks review (`{index}-review.tasks.{name}.md`) is missing, has no readable verdict, or falls below the threshold. `<threshold>` is `review.pass` or `review.concerns_or_better`. A slice whose design review (`{index}-review.slice.{name}.md`) is missing, has no readable verdict, or falls below the threshold is returned *pre-flagged* |
| `cf.slices_ready_to_implement("{plan}", "<threshold>")` | Every open slice with a design file, **in dependency order** (a stable sort; ties keep plan order; a cycle fails the run before any item, naming it). Slices that aren't ready are returned pre-flagged `not_ready`, first hit wins: design review missing or below the threshold, `no task file`, tasks review missing or below the threshold, `all tasks checked but slice not marked complete`. A dependency on an open, undesigned slice in the plan pre-flags `dependency N not designed`; a dependency outside the plan is not checked (WARNING) |

Item fields are accessed as dotted references: `{slice.index}`, `{slice.name}`, `{slice.status}`, `{slice.design_file}`.

**Per-item behavior:**

- **Isolation.** Each item runs in its own scope: it sees the outputs of steps before the `each` plus its own inner steps, and nothing from other items. Item 2's revise dispatch never reads item 1's review.
- **Pre-flagged items.** An item carrying `flag_reason` (e.g. `no design review found`) is recorded as FLAGGED with that reason and its body never runs, under either policy.
- **Dependency flags.** Slice items carry `dependencies`, read from the `dependencies:` list in the slice's design frontmatter (each element's leading number, so `195` and `"195-slice.foo"` both mean slice 195; an element with no number is dropped with a WARNING). An item whose dependency was flagged earlier in the same run is flagged too (`dependency 195 flagged`) and its body never runs, under either policy — so one failure doesn't build a broken slice on top of it. This is transitive in run order. A dependency outside the run, already complete, or later in the run flags nothing, and the order is never changed.
- **Pauses.** A checkpoint pause inside an item stops the run under either policy, so `sq run --resume` can pick it up. Batch pipelines use `checkpoint: never`.
- Every flagged item is logged at WARNING with its reason.

**Batch report.** Every `each` step writes `{run_id}.{step_name}.report.md` and `{run_id}.{step_name}.report.json` next to the run state file (`~/.config/squadron/runs/` by default). Both are rewritten after every item and on every exit, each through a temp file and a rename, so a reader never sees a partial file and a batch killed outright still leaves a report of every item it finished. The Markdown frontmatter carries `docType: batch-report`, `pipeline`, `runId`, `plan` (when the source had one) and the `passed` / `accepted` / `flagged` / `not_run` counts; the body lists flagged items first, each with its flag kind, failed step, reason, last verdict, branch and review file. An item is **FLAGGED** if it was pre-flagged, failed, or paused; **ACCEPTED** if a loop in it exhausted but met `accept_if`; otherwise **PASSED**. When a git environment fault halts the batch, the item in flight is flagged `step_failed` and every item not reached is **NOT_RUN**, both with the fault as the reason. `sq run` prints the counts, the flagged items and both report paths at the end of the run. See [Batch reports and the flag handoff](#batch-reports-and-the-flag-handoff) for the JSON.

**Example:**

```yaml
- each:
    name: slices
    source: cf.undesigned_slices("{plan}")
    as: slice
    on_item_failure: continue
    steps:
      - design:
          phase: 4
          plan: "{plan}"
          slice: "{slice.index}"
          model: "{model}"
```

---

## Judge-Gated Cycles

**The convention:** a bounded `loop` whose body is `[dispatch, review]` — fix, then re-review — gated by a `judge.*` template's score-derived verdict, with `until: review.pass` and `on_exhaust: checkpoint`. When the exit condition needs more than a fresh verdict, the body becomes `[dispatch, review, gate]` — see [Requiring that findings were addressed](#requiring-that-findings-were-addressed).

| Element | Role |
|---|---|
| Loop body step 1 (`dispatch`) | The fix leg. Prompt does double duty: address prior judge findings if any exist, otherwise perform an initial improvement pass |
| Loop body step 2 (`review`) | The judge leg — a `judge.*` template (e.g. `judge.slice-vs-arch`) that scores the artifact and derives a PASS/CONCERNS/FAIL verdict from the score |
| `until: review.pass` | Exit condition — the loop stops as soon as an iteration's judge review passes |
| `max` | Always explicit — there is no unbounded pattern anywhere in this convention |
| `on_exhaust: checkpoint` | If `max` is reached without a passing review, the run PAUSES for a human — the outcome is *undecided*, not wrong, so escalation (not failure) is the default |

The built-in `judge-cycle` pipeline (see [Built-in Pipelines](#built-in-pipelines)) is the reference implementation of this convention. It declares `model` and `review-model` as named `params` (fix-leg model and judge-leg model respectively) rather than leaving either step's `model:` unset — see the [`loop`](#loop) example. A judge template does carry its own `model:` default as a last-resort fallback, but don't rely on it: an explicit param keeps the model visible and overridable in one place, consistent with every other built-in pipeline.

### Two gating modes

- **Auto-advance (default):** use the judge template's default thresholds (e.g. `judge.slice-vs-arch`'s `pass_floor: 82`). A high-confidence score clears the floor and the loop exits automatically — no human involvement needed for the common case.
- **Advisory-only / always-escalate:** when the judge's ground truth is weak (e.g. an early-stage template, or a domain the judge is known to score unreliably), force every iteration to escalate by setting a step-level override that no score can clear:

  ```yaml
  - review:
      template: judge.slice-vs-arch
      judge:
        pass_floor: 101
  ```

  **This is the entire mechanism** — there is no separate `advisory:` flag or field. `resolve_thresholds` does not clamp threshold values, so a `pass_floor` above 100 is a *sanctioned* value: no score (0–100) can ever clear it, so the loop always exhausts to `checkpoint` and a human always makes the final call. If thresholds are ever clamped to a strict 0–100 range in a future slice, that change must preserve some "never passes" sentinel or this convention breaks.

### Escalation observability

When a loop exhausts, the step's result carries the last iteration's judge review — its score and findings are present in `action_results`, reachable by whoever picks up the checkpoint. Exhaustion is never silent.

### First-iteration shape: fix-first

The recommended body is **fix-first** — `[dispatch, review]`, no pre-loop judge. The executor's loop is post-test (see [`loop`](#loop)): `until` is evaluated only after an iteration's body completes. A judge placed *before* the loop is purely informational — it cannot short-circuit iteration 1, because the loop hasn't started evaluating its exit condition yet. Don't design a judge-gated cycle expecting a pre-loop check to skip the first pass.

### `commit_each_iteration` and per-round history

`commit` is an action emitted by phase steps, not a registered step type — it cannot appear as a bare step inside a loop body. A judge-gated cycle's body is `[dispatch, review]`, or `[dispatch, review, gate]` when the decision is a gate's (see [Requiring that findings were addressed](#requiring-that-findings-were-addressed)).

- **Phase-shaped body** (`design`, `tasks`, `implement`): the phase step already commits once per iteration automatically, as the last action in its expansion. Do not also set `commit_each_iteration: true` on such a loop — validation rejects it, naming the offending step, because it would attempt to commit twice per round.
- **Non-phase body** (e.g. `[dispatch, review]`, the judge-gated-cycle convention): commits nothing by default. Set `commit_each_iteration: true` to have squadron commit once after each iteration's body completes, before the `until:` check — this gives a dispatch-bodied loop the same per-round git history a phase-bodied loop already has.

Each loop-appended commit follows the [Commits](#commits) rules, so consecutive rounds read differently in `git log` (`docs: revise slice 105 design, round 2 (review: PASS)`). What a round commits is decided by the last `review` in the loop body: its template picks the subject (`slice` → design, `tasks` → tasks, `code` → implement, `arch` → architecture) and its `slice` or `plan` picks the target. A loop with `commit_each_iteration` and no `review` in its body fails that round's commit with `commit scope unknown: no review in round N`. A round that changes nothing still no-ops at the git level (nothing to commit), with a WARNING naming the step. `--dry-run` shows `commit_each_iteration` on the loop's summary line when set.

Staging is scoped: only the files the round produced are committed. Unrelated changes in the working tree stay where they are.

### `revision_number:` — per-round artifact provenance

Squadron stamps a plain integer `revision_number:` into the frontmatter of the artifact a loop-iteration dispatch produces (the design or tasks file), and onto the review file it authors itself, immediately after confirming the dispatch actually wrote that artifact this run.

| Question | Answer |
|---|---|
| What does it count? | The number of times **squadron** has stamped this file. Nothing else. |
| Who writes it? | Squadron's loop-iteration stamping path, only — never a hand-edit, never the dispatched agent. |
| Is it semver? | No. Not major/minor/patch, no ordering relationship to any release, no compatibility meaning. |
| Is it the loop's iteration index? | No. It counts revisions of the document, not position in a loop — three rounds in one run then two in a later run gives `5`, not `2`. |
| What does absent mean? | "Never stamped by squadron." Explicitly **not** round 1 — readers must treat absent as *no information*, not a default. |
| Which docTypes? | `slice-design` and `tasks` (the artifacts a phase-step dispatch produces), plus `review` (which squadron authors itself). Undefined elsewhere. |
| Can it decrease or reset? | No. Monotonic per file. A file that has lost its `revision_number:` has been hand-edited, not reset. |
| What is it for? | Naming a round so a reader can say which revision they are looking at. It is an identifier for display and diff-labeling — nothing should branch on its value. |

### Clean regeneration — what survives a round

Each loop iteration regenerates the artifact from the phase prompt. `revision_number:` is the only thing squadron carries across a round — content does not accumulate, and no round-specific scaffolding is injected into the document. Round-over-round history lives in git (via `commit_each_iteration` or a phase step's own commit), not inside the file itself.

### `each` fan-out caveat

If you fan a judge-gated cycle out over multiple slices with `each`, the registered sources are `cf.unfinished_slices`, `cf.undesigned_slices` and `cf.slices_needing_tasks` (see [`each`](#each)) — do not assume other collection sources exist. `slices-plan` and `tasks-plan` are worked examples of a loop inside `each`.

### Alternative: `on_exhaust: fail`

Use `on_exhaust: fail` instead of `checkpoint` only when an artifact that never clears the floor should abort the run outright, rather than wait for a human — e.g. a fully automated pipeline with no one to hand a checkpoint to.

---

## Composing a judge and a review at one gate

A judge-gated cycle (above) uses *one* verdict to gate — a judge's score-derived PASS/CONCERNS/FAIL, or a standard review's model-produced verdict, but never both at once. When a gate needs to reflect **both** an independent judge's opinion and a standard review's opinion of the same artifact, use a `gate` step.

### The composition shape

Two `review` steps producing two named results, followed by a `gate` step that reduces them:

```yaml
# Two independent judgments of the same artifact, reduced to one gate.
- review:
    name: judge-slice
    template: judge.slice-vs-arch
    slice: "{slice}"
- review:
    name: review-slice
    template: slice
    slice: "{slice}"
- gate:
    name: compose-gate
    judge_from: judge-slice
    review_from: review-slice
    policy: most-severe          # the only policy today — keep the key explicit
    checkpoint: on-concerns      # fires on the REDUCED verdict
```

`judge_from` / `review_from` name the two prior **steps** (not the colliding `review-0` action key both review steps would otherwise write). A `gate` step expands to `[gate, checkpoint?]` — same as a `review` step's own optional `checkpoint:` — so the reduced verdict and the checkpoint land in the same step, and the checkpoint's existing read path sees the gate's output with no changes to checkpoint code. See the built-in `compose-gate-example` pipeline for the full reference shape.

### The reduction rule: most-severe-wins

```
severity order (most severe first):  UNKNOWN  >  FAIL  >  CONCERNS  >  PASS
None verdict  →  normalized to UNKNOWN  (before comparison)
reduced verdict = the more severe of (judge_verdict, review_verdict)
```

- Two `PASS` → `PASS` — the gate advances only when *both* judgments clear.
- Any `FAIL` or `UNKNOWN` on either leg dominates — a broken judge (or review) leg never lets the other leg auto-advance the gate.
- **A verdict-less leg (`None`) is normalized to `UNKNOWN` before ranking, not skipped.** A named source step that ran a non-review action, or a review that produced no verdict, is a leg that *could not be judged* — treating it as most-severe (rather than silently dropping it, as the checkpoint's own `_find_review_verdict` does for a `None` verdict) means it can never let the other leg pass the gate unchallenged. This is logged at WARNING+ so a verdict-less source is never silent.
- Both raw verdicts are preserved on the gate result's `metadata` (`judge_verdict`, `review_verdict`) regardless of the reduced outcome, so the composition is always auditable.

### When you need 140 instead

The gate reduces **exactly two** named sources to **one** verdict, upstream of an unmodified checkpoint. That is sufficient as long as a single reduced verdict is all the checkpoint needs to see. It is **not** sufficient — and the need becomes a **140 (pipeline-foundation) concern**, not something to force through a gate — when:

- A required policy needs the checkpoint to branch on **which** leg produced the severity (e.g. "pause only if the judge leg specifically failed"). The gate's metadata preserves both raw verdicts for a human to read, but the checkpoint's trigger evaluation never reads `metadata` — only the single reduced `.verdict`. Distinguishing *which* leg failed at the checkpoint requires extending the checkpoint itself to weigh multiple verdicts (option b) — out of this slice's scope.
- You need more than two sources, or N-way composition. The gate is intentionally not generalized past two named legs.

Don't reach for a gate to solve either of these — raise it as a 140 dependency instead.

### Requiring that findings were addressed

`until: review.pass` exits on a fresh verdict alone. A reviewer that simply fails to re-notice a prior concern ends the loop — the work looks done because nobody looked. The `findings-addressed` policy closes that hole: the loop exits only when fresh eyes are satisfied **and** the prior round's CONCERN+ findings are accounted for.

**The shape** (the bundled `findings-addressed-cycle` pipeline):

```yaml
- loop:
    max: 3
    until: review.pass
    commit_each_iteration: true      # the policy's evidence source
    steps:
      - dispatch:
          name: revise               # producer
      - review:
          name: fresh-review         # assessor — blind to prior rounds
      - gate:
          name: settled              # decider — sees both rounds
          review_from: fresh-review
          policy: findings-addressed
          judge:
            model: "{judge-model}"
          checkpoint: on-concerns
```

`until:` reads the **gate's** verdict, not the review's: the gate is the last verdict-bearing action in the body, and loop validation counts only *unconsumed* verdicts — a step a gate names is an input to that decision, not a competing answer. Two reviews with no gate is still rejected, for the same reason it always was.

**How the decision is made** — deterministic layers first, a model only for what cannot be measured:

| Layer | Settles | Cost |
|---|---|---|
| Screen 0 — no prior round | First iteration: addressed leg `PASS`, annotated `noPriorRound`. A *later* iteration with no prior result is a different state — see below | free |
| Screen 1 — byte-identical round | The round changed nothing, so every prior finding is `unaddressed`; leg `FAIL` | free |
| Screen 2 — exact match | A prior finding recurring at the same `location` + `category` is `unaddressed` — the reviewer re-found it | free |
| Judge | Only the residue the screens could not settle, one status per finding | one model call |

The judge emits `addressed`, `unaddressed`, `moved` (which must name a successor finding), or `disputed`, and nothing else — the outcome is **derived** from those statuses, never taken from the model. A `moved` whose successor is not in the fresh findings, and an `addressed` over a file the round never touched, are downgraded to `disputed` with a WARNING.

**`UNKNOWN` means the check could not run, and the run stops** — it is never the disposition for a state whose right action is knowable. A `findings-addressed` gate in a loop with no per-round commit source is rejected at *validation* time with the fix named, rather than emitting `UNKNOWN` every round. At runtime four things produce `UNKNOWN`: a git failure that makes the round diff uncomputable, a judge that could not be reached or read, a `disputed` status, and a round past the first whose *prior* round produced no verdict at all (its review failed, was skipped, or emitted nothing) — there is no evidence to compare against, which is not the same as a legitimate first round. All four reach a human through the checkpoint.

**Each round sees only its own round.** Inside a loop body, a step name resolves to the steps that ran before the loop plus the steps that have run in *this* iteration — never a previous iteration's result under the same name. A round whose review fails therefore leaves nothing standing for the gate to mistake for this round's evidence, and body step names stop resolving once the loop exits.

**A gate must follow the steps it names.** Any gate inside a loop body — whatever its policy — is rejected at validation time if it names a body step that runs at or after its own position, because `until:` would then gate on that step's raw verdict and the gate's decision would be discarded. A `findings-addressed` gate is held to more: its `review_from` must name a step *in the body*, since the policy compares one round against the previous one and a step outside the body would hand it identical evidence every round.

**Cost:** round 1 never consults a judge, byte-identical rounds never consult a judge, and mechanically-settled findings never reach one. The judge's model comes from the `judge:` block, or from the standard cascade — never the dispatch model.

**Evidence artifact.** Every decision writes `{index}-gate.{policy}.{name}-r{revision}.md` into `project-documents/user/reviews/`, carrying `docType: gate-evidence`, the per-finding statuses with the screen that settled each, both leg verdicts, the prior round's SHA, and the judge model when one was consulted. It is written before the round's commit, so it lands in that round's history. The filename deliberately sits outside the `*-review.*` namespace: metrology sweeps that pattern for judge samples, and a gate decision is decider evidence, not an assessment. `ActionResult.metadata` carries the same record in-process.

The prior round's SHA is recorded; round N's own is not, and cannot be — the artifact is written before the commit that contains it. Round N's commit is the one containing the artifact.

### Gate vs. fan-in: don't confuse the two

The `fan_out` / `FanInReducer` machinery (`collect`, `first_pass`, and richer reducers) looks similar to a gate — both "reduce results to one verdict" — but they reduce along different axes:

| | **Gate** | **Fan-in** (`fan_out` + `FanInReducer`) |
|---|---|---|
| Reduces | **2 heterogeneous** judgments of one artifact | **N homogeneous** branch results from a fan-out |
| Sources differ in | *kind* — a judge verdict vs. an independent review verdict | *sample* — the same kind of review run across several models/prompts |
| Answers | "do a judge **and** a review agree this gate should open?" | "does the **consensus/median** of N samples clear the gate?" |

If you're running the *same* judge or review N times and want a consensus (e.g. median score across samples to bound variance), that's a fan-in job — reach for `fan_out` and a `FanInReducer`, not a `gate` step. A gate is for combining two *different kinds* of judgment on one artifact, not for converging repeated samples of the same kind.

---

## Action Type Catalog

Actions are the internal execution units that step types expand into. Pipeline authors don't write actions directly — they appear in `--dry-run` and `--prompt-only` output.

| Action | Emitted by | What it does |
|---|---|---|
| `cf-op` | phase steps | Runs a Context Forge CLI operation (`set_phase`, `set_slice`, `build_context`) |
| `dispatch` | phase steps | Sends assembled context to an LLM; performs the phase work |
| `review` | phase steps, standalone review step | Runs `sq review <template>` and captures verdict and findings |
| `gate` | `gate` step | Reduces a named judge result and review result to one verdict (most-severe-wins) |
| `checkpoint` | phase steps (when `checkpoint:` is set), `gate` step (when `checkpoint:` is set) | Pauses pipeline; user decides to continue or abort |
| `commit` | phase steps, `devlog`, loops with `commit_each_iteration` | Stages only the files the step produced and commits them — see [Commits](#commits) |
| `branch` | `branch` step | Enters or merges a slice's branch |
| `compact` | compact step | Reduces context (session-rotate in true CLI; `/compact` dispatch in prompt-only) |
| `summary` | summary step | Generates summary text and routes to emit destinations |
| `devlog` | devlog step | Writes a DEVLOG entry (the step then commits it) |

---

## Model Resolution

Squadron resolves the active model for each action through a 5-level cascade, highest priority first:

1. **CLI override** — `sq run P456 152 --model haiku`
2. **Action-level model** — `review.model` inside a phase step's review config
3. **Step-level model** — `model:` on a phase, compact, summary, or review step
4. **Pipeline-level model** — top-level `model:` in the pipeline definition
5. **Config default** — `sq config get model.default`

If all levels are `None`, the run fails with an explicit error. There is no hidden global fallback.

Model values are **aliases** (e.g. `opus`, `sonnet`, `minimax`, `glm5`, `haiku`), not raw model IDs. Alias resolution happens at execution time. Aliases are defined in `src/squadron/data/models.toml` (built-in) and can be extended or overridden in `~/.config/squadron/models.toml`.

A name that is neither an alias nor a known model id is rejected **before step 1**, listing close matches, unless a profile is set to justify a literal id. That check also runs under `sq run <pipeline> --dry-run`, so a typo fails the preview instead of rendering a plan that cannot run. For a `review` step, the profile that justifies a literal id is the step's own: its `profile`, its template's `profile:`, or `default_review_profile`; for other steps it is `--param profile=…`.

**Parameter-driven model example:**

```yaml
params:
  model: opus          # default; caller can override with --param model=sonnet

steps:
  - design:
      phase: 4
      model: "{model}"  # quotes required — bare {model} is a YAML parse error
```

---

## Configuration Surface

### Built-in defaults

Installed with the package at `src/squadron/data/`:

- `models.toml` — built-in model alias definitions
- `pipelines/*.yaml` — built-in pipeline definitions
- `compaction/*.yaml` — compaction templates (used by `compact` and `summary` steps)
- `review/templates/builtin/*.yaml` — review templates

### User overrides

`~/.config/squadron/`:

- `models.toml` — additional or overriding model aliases
- `pipelines/*.yaml` — additional or overriding pipeline definitions
- `compaction/*.yaml` — additional or overriding compaction templates
- `squadron.toml` — general config (`model.default`, `compact.template`, etc.)

### Project overrides

`<project-root>/project-documents/user/pipelines/`:

- `*.yaml` — project-local pipeline definitions (highest priority)

**Pipeline lookup order (first match wins):** project → user → built-in.

Built-in and user files use **identical formats** — copy any built-in file to the corresponding user or project directory to override or extend it.

---

## Built-in Pipelines

```bash
sq run --list    # shows all available pipelines with descriptions
```

| Name | Description | Key params |
|---|---|---|
| `P2` | Phase 2 (architecture) for an initiative, with arch review | `plan`, `model`, `review-model`, `summary-model` |
| `P4` | Phase 4 (slice design), revised until the review passes; checkpoints if it never does | `slice`, `model`, `review-model`, `max-revisions`, `summary-model` |
| `P5` | Phase 5 (tasks), revised until the review passes; checkpoints if it never does | `slice`, `model`, `review-model`, `max-revisions`, `summary-model` |
| `P6` | Phase 6: `branch enter` → implement with code review → `revise-code` loop → devlog → `branch merge` → summary | `slice`, `model`, `review-model`, `max-revisions`, `pass-threshold`, `accept-threshold`, `summary-model` |
| `P456` | Full slice lifecycle: design and tasks (each revised like `P4`/`P5`) → compact → `branch enter` → implement → `revise-code` loop → devlog → `branch merge` | `slice`, `design-model`, `model`, `review-model`, `max-revisions`, `summary-model` |
| `P56` | Tasks (revised like `P5`) → compact → `branch enter` → implement → `revise-code` loop → devlog → `branch merge` | `slice`, `model`, `review-model`, `max-revisions`, `summary-model` |
| `slices-plan` | Design and review every undesigned slice in a plan; flags failures and writes a batch report — see [Plan batch pipelines](#plan-batch-pipelines) | `plan`, `model`, `review-model`, `max-revisions` |
| `tasks-plan` | Task breakdown for every designed slice in a plan whose design review is acceptable, and a re-review of slices whose tasks review is missing or below the threshold — see [Plan batch pipelines](#plan-batch-pipelines) | `plan`, `model`, `review-model`, `max-revisions` |
| `implement` | Implementation only (design and tasks already exist): `branch enter` → implement → `revise-code` loop → devlog → `branch merge` | `slice`, `model`, `review-model`, `max-revisions`, `pass-threshold`, `accept-threshold` |
| `implement-plan` | Implement every ready slice in a plan, in dependency order; flags failures, writes a batch report — see [`implement-plan`](#implement-plan) | `plan`, `model`, `review-model`, `max-revisions` |
| `review` | Standalone review against existing artifacts | `slice`, `template`, `model` |
| `judge-cycle` | Judge-gated review-fix-review cycle — reference implementation of the [judge-gated cycle convention](#judge-gated-cycles) | `slice`, `model`, `review-model`, `max-revisions` |
| `compose-gate-example` | Reduces a judge result and a review result into one checkpoint gate — reference implementation of [gate composition](#composing-a-judge-and-a-review-at-one-gate) | `slice`, `model`, `review-model` |
| `findings-addressed-cycle` | Fix-review cycle that exits only when fresh eyes pass *and* the prior round's findings were accounted for — see [Requiring that findings were addressed](#requiring-that-findings-were-addressed) | `slice`, `model`, `review-model`, `judge-model`, `max-revisions` |
| `example` | Annotated reference — all available options | `slice` |

The `example` pipeline (`src/squadron/data/pipelines/example.yaml`) is the primary authoring reference. It includes inline comments explaining every field and option. Read it before writing a custom pipeline.

> **Note on naming:** Phase pipelines are named for the phases they run: `P4` is phase 4, `P456` runs phases 4 through 6. The full slice lifecycle was previously named `slice`, and tasks-through-implementation was `tasks`.

---

## Plan Batch Pipelines

`slices-plan` and `tasks-plan` walk a whole slice plan unattended, flag what they can't finish, and end with one [batch report](#each) for the PM.

```bash
sq run slices-plan 900                     # design + review every undesigned slice in plan 900
sq run tasks-plan 900                      # break down every designed slice whose design review is acceptable
sq run slices-plan 900 -p max-revisions=1 -p review-model=minimax
```

Per slice, `slices-plan`:

1. starts a fresh SDK session (`summary` with the `item-reset` template and `emit: [rotate]`), so nothing from the previous slice is in context; skipped when the model is non-SDK;
2. switches cf to plan 900's arch, then the slice, then phase 4 (see [Phase steps](#phase-steps-design-tasks-implement));
3. writes the design and reviews it, committing both;
4. stops there if that review already meets `pass-threshold` (`skip_if_met`) — **PASSED**;
5. otherwise runs up to `max-revisions` revise rounds: a `feedback: review` dispatch that revises the design in place against the findings, then a fresh review, committing each round;
6. on a passing round — **PASSED**; if the rounds run out but the last review meets `accept-threshold` — **ACCEPTED**; otherwise — **FLAGGED**, and the next slice starts.

A design step that writes no design, a provider failure, or any other step failure also flags the slice and moves on.

`tasks-plan` is the same shape over `cf.slices_needing_tasks`, with the `tasks` phase (5) and `tasks` review template. It selects slices with no tasks file, and also slices that have tasks but whose tasks review is missing, unreadable or below `accept-threshold`. For a slice that already has tasks the step is `existing: keep`: no model call, just a review, and the revise loop only if the review finds problems — a slice whose tasks pass costs one review. A slice whose design review is missing or below `accept-threshold` is flagged without running.

| Param | Default | Meaning |
|---|---|---|
| `plan` | required | Architecture index of the slice plan |
| `model` | `sonnet` | Design / tasks and revise model |
| `review-model` | `minimax` | Review model |
| `max-revisions` | `2` | Revise rounds **after** the first design, so a slice gets at most `max-revisions + 1` reviews |
| `pass-threshold` | `review.pass` | Stops revising |
| `accept-threshold` | `review.concerns_or_better` | Accepts a slice whose rounds ran out (and gates `tasks-plan` selection) |

**Things to know before running one:**

- **Batches change cf state and don't restore it.** Afterwards cf points at the batch's arch and plan, the last slice, and the batch's phase. Don't run any other cf-consuming command (`sq review slice`, another pipeline, `cf build`) in the project while a batch is running — it would resolve against whichever slice the batch set last.
- **Commits land on the integration target.** Planning commits (design, tasks, loop rounds, devlog) are refused anywhere else, so start the batch from the target branch (`main`, or `git.integration_branch`). A batch started on another branch stops at its first commit.
- **Rerun, don't resume.** Selection is by artifact presence, so rerunning a stopped batch picks up only what's left. A slice flagged after its design was written is not re-selected by `slices-plan`; `tasks-plan` then flags it for "design review below threshold", so it keeps appearing in reports until someone deals with it.
- **Run from a terminal.** `sq run` refuses inside a Claude Code session (#144), and these pipelines dispatch through an SDK session.
- **Cost is unattended.** Every slice can take `max-revisions + 1` design-and-review calls. Keep `max-revisions` small on a large plan.
- `--prompt-only` doesn't render `each` or `loop:` steps yet (#145).
- **One mutating run per checkout.** See [Run lock](#run-lock).

### `implement-plan`

`implement-plan` runs Phase 6 over every ready slice of a plan with no one watching:

```bash
sq run implement-plan 180 --model sonnet
sq run implement-plan 180 -p review-model=minimax -p max-revisions=1
```

Items come from `cf.slices_ready_to_implement`, in dependency order. Per slice: fresh session (`item-reset`) → `branch enter` (with `plan:`, and a catch-up if the branch exists) → implement (`existing: keep`) → code review → `revise-code` loop → devlog → `branch merge`. The run ends on the target with one `merge: slice N — …` commit per merged slice.

- A slice whose rounds run out below `accept-threshold` is flagged `review_unresolved` at `revise-code` (the loop has `on_exhaust: fail`). Its branch stays unmerged with all its work committed, its dependents are flagged `dependency`, and independent slices carry on.
- A rerun keeps work: an implement step whose slice branch already has commits of its own skips the model call and goes straight to the code review. The only way to start a slice over is to delete or rename its branch yourself; squadron never deletes branches.
- If you fix a flagged slice by hand on its branch and commit, a retry re-reviews it, and a passing review merges it.
- An implement dispatch that commits nothing fails its code review (no diff to review), so the item is flagged `step_failed`, not merged.
- Same params as the plan batches above, except `review-model` defaults to `minimax`, matching `P6`.
- Git, not cf's checkboxes, says a slice is merged. A slice whose branch is merged into the target counts as complete even when cf still reports it open (its tasks were never checked off): it is skipped, its dependents are not flagged, and a WARNING names the slice, branch and target. Fast-forwarded branches and branches with no commits of their own are not treated as merged. If git cannot be read, the batch fails before any item runs.

### Item resume

A flagged item is fixed by a decision, applied to that item of that run:

```bash
sq run --resume <run_id> --item 196 --decision retry --instructions "Use the existing CommitPlan."
sq run --resume <run_id> --item 196 --decision accept
```

- `retry` reruns the item's body once, from the top, with the run's own pipeline, params and models (`--model` and `-p` apply on top). Work already on the slice branch is kept, so a retry re-reviews it and revises it. `--instructions` is put at the head of every dispatch prompt in the item, in the "Instructions from checkpoint resolution" block.
- `accept` does the same, except the revise loop counts as met with no rounds: one code review runs (so the report shows what was accepted), then devlog and merge, and the item is recorded **ACCEPTED**. Only items flagged `review_unresolved` can be accepted. A conflict still flags the item; accept overrides the review, not git.
- Works on `flagged` and `not_run` items (`not_run` takes `retry` only), on a completed run, and on any pipeline with exactly one `each` step — `slices-plan` and `tasks-plan` too.
- Before anything reads the tree, item resume commits a flagged slice branch's leftovers and returns to the target. It refuses to start on another branch or on a dirty target.
- An item that is no longer selected (deferred, now undesigned) is refused, naming its status. A slice already merged and complete on the target — an earlier resume that died before rewriting the report — is reconciled to PASSED (`reconciled: merged before the report was updated`) without running.
- A lone item whose in-plan dependency is not complete is flagged `dependency N not complete` without running. A dependency merged into the target counts as complete even if cf still reports it open. A merged item that cf still reports open is reconciled to PASSED the same way.
- The item's record is replaced, with `decision` and `resumedAt`, and both report files are rewritten. The new record and the report path are printed.

| Exit | Meaning |
|---|---|
| 0 `RESOLVED` | the item ended passed or accepted |
| 1 `FLAGGED` | the decision was applied and the item was flagged again; the record says why |
| 2 `REJECTED` | refused, nothing ran: a bad request, the git precondition, or a busy run lock |
| 3 `HALTED` | an environment fault or an unknown git state ended it mid-item; needs a human |

`override_instructions` and `accept_decision` are reserved: they're rejected as `-p` keys (`'accept_decision' is reserved; use --decision accept`) and in a pipeline's `params:`, and dropped (with a WARNING) from the stored params of the run being resumed.

### Run lock

Any `sq run` whose pipeline commits or moves cf state (a phase step, `devlog`, `branch`, or a loop with `commit_each_iteration`, at any depth) and every item resume hold an exclusive lock on `{git dir}/squadron-run.flock` for the whole run. A second one in the same checkout exits 2 at once with `another squadron run holds the project lock (…); one mutating run per project at a time`; it never waits. Separate registered worktrees have separate git dirs, so they still run in parallel. A killed run releases the lock with its process. Review-only and summary pipelines don't take it. POSIX only.

### Batch reports and the flag handoff

This is squadron's half of the contract with an unattended caller (Amoeba, amoeba#1). Squadron doesn't decide what to do with a flag; it reports it precisely and acts on a decision.

- **Event.** A batch run completes and its `{run_id}.{step}.report.json` has items with `outcome: flagged` or `not_run`. The report sits beside the run's `runs/{run_id}.json`.
- **Versioning.** Check `schemaVersion` (currently `1`) before reading the items. It goes up whenever the record shape or the `flagKind` set changes. Squadron refuses to load any other version, naming both.
- **Routing input**, per item: `flagKind`, `failedStep`, `reason` (text for humans; never route on it), `finalVerdict`, `reviewFile`, `branch`.

| `flagKind` | Meaning |
|---|---|
| `not_ready` | the source pre-flagged it (no task file, a review below the threshold, all tasks checked but not closed) |
| `dependency` | a dependency was flagged, isn't designed, or isn't complete |
| `review_unresolved` | the revise loop ran out below `accept-threshold` |
| `branch_conflict` | a catch-up or merge stopped on a git conflict |
| `step_failed` | any other failed step (implement dispatch, devlog, a refused merge, `set_arch`, a halt) |
| `paused` | a checkpoint paused the item (not used by `implement-plan`) |

```json
{
  "docType": "batch-report",
  "schemaVersion": 1,
  "pipeline": "implement-plan",
  "runId": "3f9c2a1b7d10",
  "stepName": "slices",
  "plan": "180",
  "counts": {"passed": 3, "accepted": 1, "flagged": 2, "not_run": 0},
  "items": [
    {"index": "196", "name": "…", "outcome": "flagged",
     "flagKind": "review_unresolved", "failedStep": "revise-code",
     "reason": "loop exhausted at FAIL (accept: review.concerns_or_better)",
     "finalVerdict": "FAIL", "reviewFile": "project-documents/user/reviews/196-review.code.….md",
     "unsavedParts": [], "branch": "196-slice.…", "decision": null, "resumedAt": null}
  ]
}
```

- **Decision back.** `sq run --resume <run_id> --item <index> --decision retry|accept [--instructions TEXT]`, with non-TTY stdin. A free-text resolution maps to `--instructions`.
- **Result.** Exit 0 resolved (merged), 1 flagged again — the rewritten record says why — 2 rejected and nothing ran (bad request, git precondition, or the lock is busy: try again later), 3 halted on the environment or an unknown git state, which needs a human.
- **Concurrency.** One item resume per checkout at a time.
- **Not covered by squadron:** abandoning or deferring a slice (a cf status change), and fixing `not_ready` or `dependency` flags, which are fixed upstream (design, tasks, or the dependency) before the item is retried or the batch rerun.

## Writing a Custom Pipeline

1. Create `<project-root>/project-documents/user/pipelines/<name>.yaml`
2. Use `example.yaml` as a template (`sq run example --validate` to see the reference pipeline, then copy `src/squadron/data/pipelines/example.yaml`)
3. Validate: `sq run <name> --validate`
4. Dry-run: `sq run <name> <target> --dry-run`

**Minimal custom pipeline:**

```yaml
name: my-review-loop
description: Design a slice, review it, and pause for human decision

params:
  slice: required
  model: sonnet

steps:
  - design:
      phase: 4
      model: "{model}"
      review:
        template: slice
        model: minimax
      checkpoint: on-concerns

  - devlog: auto
```

---

## Prompt-Only Mode

When running inside a Claude Code session (VS Code extension or terminal), `sq run` cannot execute LLM dispatch directly. Use `--prompt-only` to get step-by-step instructions instead:

```bash
sq run P4 152 --prompt-only                           # returns first step as JSON
sq run --prompt-only --next --resume <run-id>          # subsequent steps
sq run --step-done <run-id>                            # mark current step complete
```

The `/sq:run` slash command (installed via `sq install-commands`) wraps this loop automatically — you don't need to manage run IDs manually.

Branch and commit steps render as the hidden `sq _branch enter|merge --slice N` and `sq _commit --subject … --slice N` commands, which run the same code the in-process executor does.

`--step-done` also runs every bound `post-action` event action (the same
ones the in-process executor fires after each action) before marking the
step complete — see [Events Guide](EVENTS.md#prompt-only-parity).

---

## User-Definable Actions on Events

A project can bind its own Python callable to a commit or run a check after
every pipeline action, without forking squadron. See the
[Events Guide](EVENTS.md) for the `EventAction` contract, the
`events.yaml` manifest format, and the authority/failure model.
