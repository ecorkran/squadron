---
docType: guide
title: Pipeline Authoring Guide
dateCreated: 20260410
dateUpdated: 20260714
---

# Pipeline Authoring Guide

Pipelines let you compose multi-step AI workflows and run them with a single command.

```bash
sq run slice 152          # run the built-in slice lifecycle pipeline
sq run example --list     # list all available pipelines
```

---

## Quick Start

Three commands to verify the system works before reading further:

```bash
sq run --list                         # show all available pipelines with descriptions
sq run slice 152                      # run the full slice lifecycle for slice 152
sq run example 152 --dry-run          # show the step plan without executing anything
```

---

## YAML Grammar Reference

Each pipeline is a YAML file with a fixed top-level structure:

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Pipeline name (case-insensitive, used in `sq run <name>`) |
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
`cf-op(set_phase)` → `cf-op(set_slice)` → `cf-op(build_context)` → `dispatch` → [`review` → `checkpoint`] → `commit`

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `phase` | int | yes | Context Forge phase number |
| `model` | string | no | Model alias for the dispatch action |
| `review` | string or dict | no | Review template name, or `{template, model}` dict |
| `checkpoint` | string | no | When to pause: `always`, `on-concerns`, `on-fail`, `never` (default: `never`) |

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

**Example:**

```yaml
- dispatch:
    prompt: "Address any findings from the prior review."
    model: sonnet
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
| `checkpoint` | string | no | Same triggers as phase steps |

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
| `max` | int | yes | The bound — maximum number of iterations. Always explicit; there is no unbounded form |
| `until` | string | no | Exit condition, evaluated after each iteration completes: `review.pass`, `review.concerns_or_better`, `action.success` |
| `on_exhaust` | string | no | What happens if `max` is reached without `until` passing: `fail` (mark the step FAILED, default), `checkpoint` (pause for a human), `skip` |
| `commit_each_iteration` | bool | no | Commit after each iteration's body completes, before `until:` is evaluated. Default `false`. Rejected at validation time if the body already commits — see [`commit_each_iteration` and per-round history](#commit_each_iteration-and-per-round-history) |
| `steps` | list | yes | Body — an ordered list of step definitions, using any registered step type except `loop` itself |

**Post-test semantics:** `until` is evaluated only *after* an iteration's body finishes, against that iteration's own results — never before the first iteration runs. A `loop` cannot use a pre-loop check to skip iteration 1.

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

---

### `devlog`

**Purpose:** Write a DEVLOG entry capturing pipeline state.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `mode` | string | `auto` — generate entry automatically |

Prefer scalar shorthand:

```yaml
- devlog: auto
```

---

### `each`

**Purpose:** Iterate inner steps over a collection, running them once per item.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | Collection source expression |
| `as` | string | yes | Loop variable name |
| `steps` | list | yes | Inner step definitions using `{variable.field}` placeholders |

**Source options:**

| Expression | Returns |
|---|---|
| `cf.unfinished_slices("{plan}")` | All unfinished slices in a Context Forge plan — the only registered source |

Item fields are accessed as dotted references: `{slice.index}`, `{slice.title}`, etc.

**Example:**

```yaml
- each:
    source: cf.unfinished_slices("{plan}")
    as: slice
    steps:
      - design:
          phase: 4
          slice: "{slice.index}"
          model: opus
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

Each loop-appended commit's message is `chore: loop-{step name} (iteration N)`, so consecutive rounds are distinguishable in `git log` rather than emitting byte-identical subject lines. A round that changes nothing still no-ops at the git level (nothing to commit), but squadron logs a WARNING naming the pipeline, step, and iteration — a byte-identical round is now observable in the run log, not silent. `--dry-run` shows `commit_each_iteration` on the loop's summary line when set.

Staging is unscoped (`git add -A`) — the same behavior a phase-emitted commit already has. Pipeline runs assume a clean working tree; an unrelated in-progress change in the working tree gets swept into the round's commit.

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

If you fan a judge-gated cycle out over multiple slices with `each`, the only registered source is `cf.unfinished_slices("{plan}")` — do not assume other collection sources exist.

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
| Screen 0 — no prior round | First iteration: addressed leg `PASS`, annotated `noPriorRound`, never `UNKNOWN` | free |
| Screen 1 — byte-identical round | The round changed nothing, so every prior finding is `unaddressed`; leg `FAIL` | free |
| Screen 2 — exact match | A prior finding recurring at the same `location` + `category` is `unaddressed` — the reviewer re-found it | free |
| Judge | Only the residue the screens could not settle, one status per finding | one model call |

The judge emits `addressed`, `unaddressed`, `moved` (which must name a successor finding), or `disputed`, and nothing else — the outcome is **derived** from those statuses, never taken from the model. A `moved` whose successor is not in the fresh findings, and an `addressed` over a file the round never touched, are downgraded to `disputed` with a WARNING.

**`UNKNOWN` means the check could not run, and the run stops** — it is never the disposition for a state whose right action is knowable. A `findings-addressed` gate in a loop with no per-round commit source is rejected at *validation* time with the fix named, rather than emitting `UNKNOWN` every round. At runtime only three things produce `UNKNOWN`: a git failure that makes the round diff uncomputable, a judge that could not be reached or read, and a `disputed` status. All three reach a human through the checkpoint.

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
| `commit` | phase steps | Runs `git add -A && git commit` |
| `compact` | compact step | Reduces context (session-rotate in true CLI; `/compact` dispatch in prompt-only) |
| `summary` | summary step | Generates summary text and routes to emit destinations |
| `devlog` | devlog step | Writes a DEVLOG entry |

---

## Model Resolution

Squadron resolves the active model for each action through a 5-level cascade, highest priority first:

1. **CLI override** — `sq run slice 152 --model haiku`
2. **Action-level model** — `review.model` inside a phase step's review config
3. **Step-level model** — `model:` on a phase, compact, summary, or review step
4. **Pipeline-level model** — top-level `model:` in the pipeline definition
5. **Config default** — `sq config get model.default`

If all levels are `None`, the run fails with an explicit error. There is no hidden global fallback.

Model values are **aliases** (e.g. `opus`, `sonnet`, `minimax`, `glm5`, `haiku`), not raw model IDs. Alias resolution happens at execution time. Aliases are defined in `src/squadron/data/models.toml` (built-in) and can be extended or overridden in `~/.config/squadron/models.toml`.

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
| `slice` | Full lifecycle: design → tasks → compact → implement → compact → devlog | `slice`, `review-model` |
| `tasks` | Task breakdown through implementation | `slice`, `model`, `review-model` |
| `implement` | Implementation only (design and tasks already exist) | `slice`, `model` |
| `review` | Standalone review against existing artifacts | `slice`, `template`, `model` |
| `design-batch` | Phase 4 for every unfinished slice in a plan | `plan`, `model` |
| `judge-cycle` | Judge-gated review-fix-review cycle — reference implementation of the [judge-gated cycle convention](#judge-gated-cycles) | `slice` |
| `compose-gate-example` | Reduces a judge result and a review result into one checkpoint gate — reference implementation of [gate composition](#composing-a-judge-and-a-review-at-one-gate) | `slice`, `model`, `review-model` |
| `findings-addressed-cycle` | Fix-review cycle that exits only when fresh eyes pass *and* the prior round's findings were accounted for — see [Requiring that findings were addressed](#requiring-that-findings-were-addressed) | `slice`, `model`, `review-model`, `judge-model` |
| `P1` | Phase 1 (project vision) with arch review and checkpoint | `slice` |
| `P2` | Phase 2 (architecture) with arch review and checkpoint | `slice` |
| `P4` | Phase 4 (slice design) with slice review and checkpoint | `slice`, `model`, `review-model` |
| `P5` | Phase 5 (tasks) with tasks review | `slice`, `model`, `review-model` |
| `P6` | Phase 6 (implement) with code review | `slice`, `model`, `review-model` |
| `example` | Annotated reference — all available options | `slice` |

The `example` pipeline (`src/squadron/data/pipelines/example.yaml`) is the primary authoring reference. It includes inline comments explaining every field and option. Read it before writing a custom pipeline.

> **Note on naming:** The architecture document used placeholder names (`slice-lifecycle`, `review-only`, `implementation-only`). The shipped names (`slice`, `review`, `implement`) are the canonical user-facing names.

---

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
