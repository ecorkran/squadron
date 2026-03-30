---
docType: architecture
layer: project
project: squadron
archIndex: 140
component: pipeline-foundation
dateCreated: 20260221
dateUpdated: 20260328
status: draft
---

# Architecture: Pipeline Foundation

## Overview

The Pipeline Foundation initiative establishes squadron's pipeline execution system — the machinery for defining, running, and resuming automated workflows that combine Context Forge context assembly, model dispatch, review gates, compaction, and human checkpoints into managed sequences.

This is not a new product. It is a capability within squadron that consumes Context Forge as a service and composes squadron's existing primitives (reviews, model aliases, agent dispatch, CF integration layer) into orchestrated workflows.

### Origin

The `/sq:run-slice` command (slice 118) proved the concept: a single command that chains phase transitions, context builds, reviews, and compaction into a managed flow. But run-slice is a markdown prompt — Claude Code interprets it, not squadron. The pipeline system moves this logic into squadron proper, with typed actions, declarative definitions, state persistence, and a proper execution model.

### Initiative Structure

This work is split across two initiatives:

**140: Pipeline Foundation** (this document) — Everything needed for `sq run` to work. Action protocol, pipeline definitions with model resolution, executor, basic loops, state/resume, CLI, built-in pipelines. Ships a working replacement for run-slice that is substantially more capable.

**160: Pipeline Intelligence** (future) — The things that make pipelines smart. Weighted review convergence loops, model pools with selection strategies, escalation behaviors, conversation persistence across pipeline steps. Builds on 140's abstractions.

The split is along the foundation/intelligence boundary. 140 is independently shippable and useful. 160 layers sophistication on top.

### Relationship to Other Components

**100-band (Orchestration v2):** Complete. Pipeline Foundation consumes: agent registry, provider protocol, model alias registry, review system, CF integration layer, CLI framework. These are all stable interfaces.

**Context Forge:** Consumed as a service via `ContextForgeClient` (slice 126). Pipeline actions call CF for context assembly, phase transitions, project state queries. CF is not modified by this initiative.

**ai-project-guide:** The built-in pipelines encode the guide's phase methodology as executable definitions. The guide remains the source of truth; pipelines are a runtime implementation.

**Run-slice (slice 118):** Superseded by this initiative. The markdown command continues to work but the pipeline system is the primary path forward.

---

## Command Surface

```
sq run <pipeline> [options]       # run a pipeline
sq run --resume <run-id>          # resume from checkpoint or interruption
sq run --status [run-id]          # show pipeline run status
sq run --list                     # show available pipelines
sq run --validate <pipeline>      # check a pipeline definition for errors
```

**Pipeline identification:** Built-in pipelines by short name (`slice-lifecycle`, `review-only`, `design-batch`). Custom pipelines by path or by name if registered in the project's pipeline directory.

**Common options:**
- `--slice <index>` — target slice (most pipelines need this)
- `--model <alias>` — runtime model override (applies as highest-priority default)
- `--from <step>` — start at a specific step (mid-process adoption)
- `--dry-run` — show what would execute without running

### Phase Command (TBD)

```
sq phase <phase-name> [--slice <index>] [--model <alias>]
```

A convenience that runs a single-step pipeline: set phase → build context → dispatch. Whether this earns its keep or is just `sq run single-phase --phase implement` with fewer keystrokes is an open question. Defer until real usage clarifies.

---

## Core Abstraction: Actions

Every meaningful thing a pipeline does is a first-class **Action** behind a protocol. Actions are the atomic units of pipeline execution. Pipeline steps compose actions. This is the SOLID foundation — each action has one home, one interface, and is independently testable.

### Action Protocol

```python
class Action(Protocol):
    """A discrete, typed operation that a pipeline can execute."""

    @property
    def action_type(self) -> str:
        """Identifier for this action type (e.g., 'dispatch', 'review')."""
        ...

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute the action. Returns typed result."""
        ...

    def validate(self, config: dict) -> list[ValidationError]:
        """Check configuration before execution. Called during --validate."""
        ...
```

`ActionContext` is a typed struct (not a service object) carrying data that actions may need: pipeline state, resolved parameters, model resolver reference, CF client reference, and output from prior steps. Each action pulls what it needs and ignores the rest — the struct avoids deep dependency injection while keeping a single, predictable interface. `ActionResult` carries: success/failure, output artifacts (files, structured data), and metadata for downstream steps.

### Core Action Types

| Action | Responsibility | Owns |
|--------|---------------|------|
| `dispatch` | Resolve model alias via the model resolver, create an agent via the agent provider registry, send assembled context through `agent.handle_message()`, capture output | Model resolution, agent lifecycle, output capture, token tracking |
| `review` | Run a review template against an artifact | Verdict parsing, finding extraction, file persistence, output format (prose + structured JSON) |
| `compact` | Issue parameterized compaction instructions | Instruction templates, context preservation rules |
| `checkpoint` | Pause for human decision | State serialization, presentation, resume token |
| `cf-op` | Context Forge operation (set phase, build, summarize, query) | CF client calls, response parsing |
| `commit` | Git commit at a boundary | Message conventions, scope detection |
| `devlog` | Write structured DEVLOG entry | Entry templates, phase/slice metadata |

Each action implementation lives in `src/squadron/pipeline/actions/`. The executor resolves action types through a registry — same pattern as the agent provider registry.

### Action Extensibility

Users (and future squadron slices) can register custom action types. The action registry is open. This is how 160's convergence loop strategy will plug in — as a specialized action type that wraps the review action with iteration logic.

---

## Model Resolution

Model selection cascades through a resolution chain. First non-null value wins, top to bottom:

```
1. Runtime CLI override        sq run ... --model gemini-pro
2. Action-level specification  review.model: minimax2.7
3. Step-level default          step.model: opus
4. Pipeline-level default      pipeline.model: sonnet
5. System config default       ~/.config/squadron/config.toml → default_model
```

Every model reference is an **alias** resolved through the model alias registry (slice 120). `opus`, `sonnet`, `minimax2.7`, `gpt54-nano` — all valid anywhere a model is specified.

### In Pipeline Definitions

```yaml
model: sonnet                    # pipeline-level default

steps:
  - design:
      model: opus                # step-level override
      review:
        model: minimax2.7        # action-level override

  - implement:
      # model: not specified → cascade to pipeline default (sonnet)
      review:
        # model: not specified → cascade to step, then pipeline (sonnet)
```

### Model Pools (160 — designed for, not built)

Anywhere a model alias appears, a pool reference can appear instead:

```yaml
review:
  model: pool:review             # resolve from the "review" pool
```

Pool definitions live in configuration:

```toml
# ~/.config/squadron/pools.toml
[pools.review]
strategy = "random"              # random | round-robin | cheapest
models = ["minimax2.7", "sonnet", "gemma3"]

[pools.high]
strategy = "random"
models = ["opus", "gpt54-codex", "gemini-pro"]
```

The model resolver sees the `pool:` prefix, looks up the pool, applies the selection strategy. Pipeline definitions don't change — only what the alias resolves to.

Pool categories (future vision):
- **By tier:** `pool:high`, `pool:medium`, `pool:low` — capability-based selection
- **By task:** `pool:review`, `pool:code`, `pool:design` — task-optimized selection
- **By experiment:** `pool:experiment-a` — for comparative evaluation across models

The abstraction boundary is the model resolver interface. It takes a string (alias or `pool:` reference) and returns a resolved `(provider, model_id)` tuple. Everything above that boundary — pipeline definitions, action configs — is unaware of whether the string resolved to a fixed model or a pool selection.

---

## Pipeline Definitions

Pipeline definitions are declarative data (YAML). They describe *what* to do, not *how*. The executor interprets them.

### Design Principles

1. **Structure-derived, not path-specified.** `slice: 191` is sufficient. The executor queries CF for arch doc path, slice plan path, design file path, task file path, slice name. You never type a path in a pipeline definition.

2. **Aliases everywhere.** Models use aliases. Review templates use short names. Phases use names not numbers. Nothing requires looking up an ID.

3. **Cascading defaults.** Specify once at the top, override where needed. The common case (use the same model for everything) should be one line.

4. **Minimal required fields.** A step needs a type and maybe a phase number. Everything else has sensible defaults.

### Grammar

```yaml
# Pipeline metadata
name: slice-lifecycle
description: Full slice lifecycle — design through implementation

# Parameters: what the caller provides
params:
  slice: required                # slice index — structure provides the rest
  model: opus                    # pipeline-level default model

# Steps: ordered sequence of operations
steps:
  - design:
      phase: 4
      review: arch               # review template short name
      checkpoint: on-concerns    # pause on CONCERNS or FAIL

  - tasks:
      phase: 5
      review: tasks
      checkpoint: on-fail        # only pause on FAIL

  - compact:
      keep: [design, tasks]      # what to preserve
      summarize: true            # update CF project summary

  - implement:
      phase: 6
      model: sonnet              # step-level override
      review:
        template: code
        model: minimax2.7        # action-level override for the review
      checkpoint: on-fail

  - devlog: auto                 # auto-generate from pipeline state
```

### Step Types

Step types are the bridge between the terse YAML and the action sequences that actually execute. Each step type expands into a sequence of actions:

**`design` / `tasks` / `implement`** (phase steps):
```
cf-op(set phase N) → cf-op(build) → dispatch(model) → review(template) → checkpoint(trigger) → commit
```

**`compact`**:
```
compact(instructions translated from step params)
```

The compact *step type* translates high-level params (`keep: [design, tasks]`, `summarize: true`) into CF-compatible compaction instructions. The compact *action* sends those instructions to CF via `ContextForgeClient`. The step type is the policy layer (what to preserve); the action is the execution layer (how to invoke CF).

**`checkpoint`** (standalone):
```
checkpoint(present state, await human)
```

**`devlog`**:
```
devlog(content from step type)
```

The devlog *step type* decides what to log by inspecting pipeline state (completed steps, review verdicts, model used, outputs produced). `auto` means the step type auto-generates all content from state. The devlog *action* handles formatting and file write using entry templates. Users can provide explicit content via the step config as a future enhancement.

**`review`** (standalone — for review-only pipelines):
```
review(template, against artifact) → checkpoint(trigger)
```

Custom step types can be registered, following the same pattern: a step type is a named expansion into an action sequence.

### Built-in Pipelines

**`slice-lifecycle`** — Full design → tasks → implementation. The primary pipeline.

**`review-only`** — Run reviews against existing artifacts. No implementation. Useful for quality gates.

**`implementation-only`** — When design and tasks already exist. The inner loop during active development.

**`design-batch`** — Run phase 4 design for every unfinished slice in a plan. Produces designs for human review while freeing the human to do other work. Uses collection loop.

### Custom Pipelines

Users place YAML files in the project's pipeline directory (conventionally `project-documents/user/pipelines/` or a config-specified location). `sq run --list` discovers them alongside built-ins.

### Validation

`sq run --validate <pipeline>` checks a pipeline definition without executing:
- All step types are known (registered)
- Model aliases resolve
- Required params are documented
- Review templates exist
- No obvious structural errors (orphan gotos, missing labels)

The validator calls each action's `validate()` method with the step config. Actions know their own constraints.

---

## Loops

### Basic Loops (140 scope)

Fixed iteration with a max count. Useful for retry patterns and simple repetition.

```yaml
steps:
  - implement:
      phase: 6
      model: sonnet
      review: code
      loop:
        max: 3                   # maximum iterations
        until: review.pass       # stop when review passes
        checkpoint: on-exhaust   # if max reached without pass, pause for human
```

Semantics: execute the step, check the `until` condition against the step's output, repeat or proceed. If `max` is reached without the condition being met, the `on-exhaust` behavior fires (checkpoint, fail, or skip).

**[DEFERRED → 149]** The condition grammar (`until: review.pass`) is illustrative syntax. The formal definition — whether conditions are field paths into `ActionResult`, named properties, or a structured expression — is a 149 design decision. The validator and executor both depend on this being resolved before implementation.

### Collection Loops (140 scope)

Iterate over a set of items from a known source. The primary use case: batch operations across a slice plan.

```yaml
name: design-batch
description: Run phase 4 design for every unfinished slice in the plan

params:
  plan: required                 # slice plan index (e.g., 140)
  model: opus

steps:
  - each:
      source: cf.unfinished_slices("{plan}")  # query CF for the collection
      as: slice
      steps:
        - design:
            phase: 4
            slice: "{slice.index}"
            review: arch
            checkpoint: always   # human reviews every design
```

The `each` construct iterates, binding each item to a variable. The inner steps reference the bound variable. `source` is a typed query — initially just CF queries, extensible later.

### Convergence Loops (160 — designed for, not built)

Loops with evolving state and a convergence criterion. The pipeline grammar reserves the syntax; the execution logic is 160 work.

```yaml
steps:
  - implement:
      phase: 6
      review:
        template: code
        loop:
          strategy: weighted-review    # 160: convergence strategy
          max: 4
          decay: 0.8                   # finding weight multiplier per iteration
          threshold: 0.5               # stop when max weighted new finding < this
          checkpoint: on-exhaust
```

In 140, a step with `loop.strategy` is treated as a basic loop with `max` iterations — the strategy field is acknowledged but the convergence logic is a no-op stub. When 160 lands, it registers the `weighted-review` strategy and the executor delegates to it.

This is the key architectural boundary: **140 defines the loop construct and strategy extension point. 160 fills in the strategies.**

---

## Review Output: Structured Findings

For the weighted convergence loop (160) to work, reviews must produce structured findings — not just prose with a verdict. This is a 140 deliverable because it's foundational.

Current review output: markdown prose with a PASS/CONCERNS/FAIL verdict in frontmatter.

Enhanced review output: a single markdown file with structured findings in the frontmatter (machine-readable index) and full prose in the body (human-readable detail). No companion files.

```yaml
---
verdict: CONCERNS
model: minimax/minimax-m2.7
findings:
  - id: F001
    severity: concern           # concern | fail | note
    category: error-handling    # structural tag for matching
    summary: "Missing error handling in parse_config"
    location: src/squadron/pipeline/executor.py:45
  - id: F002
    severity: note
    category: naming
    summary: "Variable name 'x' is unclear"
    location: src/squadron/pipeline/actions/dispatch.py:12
---

## Findings

### [CONCERN] Missing error handling in parse_config
category: error-handling
Full description with references, code samples, and rich markdown formatting...

### [NOTE] Variable name 'x' is unclear
category: naming
Full description...
```

The frontmatter is the structured index: compact, machine-parseable, what the pipeline reads for programmatic access. The prose body is unchanged from current output — rich formatting, backticks, bullet points, references. Finding identity (`category` + `location`) enables 160's cross-iteration matching. A finding in iteration 2 at the same category and location as iteration 1 is a **persisting** finding (full weight). A finding at a new location or category is **novel** (decayed weight).

The review action in 140 produces this structured output. The pipeline in 140 doesn't use the structure beyond the verdict. 160's convergence strategy does.

---

## Pipeline State & Resume

Pipeline execution produces a state file that enables resume after interruption, checkpoint, or crash.

### State File

```json
{
  "schema_version": 1,
  "run_id": "run-20260327-191-slice-lifecycle",
  "pipeline": "slice-lifecycle",
  "params": { "slice": 191, "model": "opus" },
  "started_at": "2026-03-27T14:30:00Z",
  "status": "paused",
  "current_step": "implement",
  "completed_steps": [
    {
      "step": "design",
      "status": "complete",
      "outputs": { "design_file": "191-slice.some-feature.md" },
      "review_verdict": "PASS",
      "completed_at": "2026-03-27T14:35:00Z"
    },
    {
      "step": "tasks",
      "status": "complete",
      "outputs": { "tasks_file": "191-tasks.some-feature.md" },
      "review_verdict": "CONCERNS",
      "completed_at": "2026-03-27T14:42:00Z"
    },
    {
      "step": "compact",
      "status": "complete",
      "completed_at": "2026-03-27T14:42:30Z"
    }
  ],
  "checkpoint": {
    "reason": "review returned FAIL",
    "step": "implement",
    "review_verdict": "FAIL",
    "paused_at": "2026-03-27T15:01:00Z"
  }
}
```

### Storage Location

`~/.config/squadron/runs/` — one JSON file per active/recent run. Old runs can be pruned.

### Resume Modes

- **`sq run --resume <run-id>`** — continue from the checkpoint or last completed step
- **`sq run <pipeline> --slice 191 --from implement`** — mid-process adoption, explicit start point
- **Implicit resume:** `sq run slice-lifecycle --slice 191` detects existing state and asks: "Found an in-progress run. Resume from step 'implement'?" (configurable: ask, auto-resume, or fresh-start)

### Interaction with Conversations

Pipeline steps use fresh agents by default — no conversation state carries between steps. The pipeline state file is the continuity mechanism, not conversation history.

Slice 125 (Conversation Persistence) is deferred to initiative 160. When implemented, a pipeline step could opt into persistent conversations:

```yaml
- implement:
    persistence: true            # 160: maintain conversation across retries
```

In 140, every step is stateless. Context is fully assembled from CF + pipeline state + prior step outputs.

---

## Component Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     CLI: sq run                               │
│              (parse args, load definition, start executor)    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│                   Pipeline Executor                           │
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │  Definition   │  │  Step        │  │  State            │  │
│  │  Loader &     │  │  Sequencer   │  │  Manager          │  │
│  │  Validator    │  │              │  │  (persist/resume) │  │
│  └──────────────┘  └──────┬───────┘  └───────────────────┘  │
│                           │                                   │
│  ┌────────────────────────┼──────────────────────────────┐   │
│  │              Step Type Registry                        │   │
│  │  design │ tasks │ implement │ compact │ review │ each  │   │
│  └────────────────────────┼──────────────────────────────┘   │
│                           │ expands to                        │
│  ┌────────────────────────┼──────────────────────────────┐   │
│  │              Action Registry                           │   │
│  │  dispatch │ review │ compact │ checkpoint │ cf-op │ …  │   │
│  └────────────────────────┼──────────────────────────────┘   │
│                           │                                   │
│  ┌────────────────────────┼──────────────────────────────┐   │
│  │              Model Resolver                            │   │
│  │  alias → (provider, model_id)                          │   │
│  │  cascade: action → step → pipeline → config            │   │
│  │  [160: pool: prefix → pool selection strategy]         │   │
│  └───────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────┘
         │                              │
         │ CF operations                │ Agent dispatch
         ▼                              ▼
┌─────────────────┐            ┌─────────────────┐
│  Context Forge  │            │  Agent Provider  │
│  (via CF Client)│            │  Registry        │
└─────────────────┘            └─────────────────┘
```

### Package Structure

```
src/squadron/pipeline/
├── __init__.py
├── executor.py              # Pipeline executor — runs step sequences
├── state.py                 # State manager — persist, load, resume
├── models.py                # Core data models (PipelineDefinition, StepConfig, etc.)
├── resolver.py              # Model resolver with cascade chain
├── loader.py                # YAML loading and validation
├── registry.py              # Step type + action type registries
├── actions/
│   ├── __init__.py
│   ├── protocol.py          # Action protocol definition
│   ├── dispatch.py          # Send context to model
│   ├── review.py            # Run review template
│   ├── compact.py           # Parameterized compaction
│   ├── checkpoint.py        # Human pause point
│   ├── cf_op.py             # Context Forge operations
│   ├── commit.py            # Git commit
│   └── devlog.py            # DEVLOG entry
├── steps/
│   ├── __init__.py
│   ├── protocol.py          # Step type protocol
│   ├── phase.py             # design/tasks/implement step type
│   ├── compact.py           # compact step type
│   ├── review.py            # standalone review step type
│   ├── collection.py        # each/collection loop step type
│   └── devlog.py            # devlog step type

src/squadron/data/
└── pipelines/               # built-in pipeline definitions (slice 141 establishes this)
    ├── slice-lifecycle.yaml
    ├── review-only.yaml
    ├── implementation-only.yaml
    └── design-batch.yaml
```

---

## Risks and Mitigations

### Risk: Reinventing LangGraph

**The trap:** Adding arbitrary function execution, conditional edge routing, state graphs, and suddenly we've built a worse LangGraph.

**Mitigation:** Constrained vocabulary. Pipeline steps compose from a fixed set of action types. Step types are a fixed set of expansions. The moment we find ourselves wanting "run arbitrary Python in a step," we stop and reconsider. The action registry is open for new action *types*, but each type is a well-defined protocol implementation — not a lambda.

**Test:** Can a non-developer read a pipeline YAML and understand what it does? If yes, we're in the right zone. If it looks like code, we've gone too far.

### Risk: Scope Explosion

**The trap:** This initiative is already large. Model pools, convergence loops, conversation persistence — each is a feature set unto itself.

**Mitigation:** The 140/160 split. 140 ships a working `sq run` with action protocol, basic pipelines, and state/resume. Nothing in 140 depends on 160. Nothing in 160 requires redesigning 140. The extension points (strategy field on loops, pool: prefix on models, persistence flag on steps) are acknowledged syntactically in 140 and implemented in 160.

### Risk: Premature Abstraction

**The trap:** Designing a grammar for N pipelines when we have experience with exactly one (run-slice).

**Mitigation:** Build the second and third built-in pipelines (review-only, design-batch) during 140 implementation. Let the grammar stabilize against three concrete examples before finalizing. The action protocol is less at risk — actions are well-defined operations regardless of how pipelines compose them.

### Risk: Action Granularity

**The trap:** Actions too coarse (one action does everything) or too fine (pipeline definitions become assembly language).

**Mitigation:** The step type layer. Users write `design:` in their pipeline. The step type expands it to `cf-op → dispatch → review → checkpoint → commit`. Users don't see the action layer unless they're building custom step types. Two audiences, two abstraction levels.

---

## Prerequisites

### Complete (from 100-band)

- Agent registry and provider protocol (101-102)
- CLI framework with Typer (103)
- Review workflow templates (105)
- Multi-provider support (111-114)
- Model alias registry with metadata (120-121)
- Context Forge integration layer — `ContextForgeClient` (126)
- Review transport unification (128)
- Review context enrichment (122)
- Scoped code review (127)

### Within This Initiative

- **Structured Review Findings (143, formerly 100-band slice 123)** — Finding extraction is foundational for the review action. Absorbed into this initiative's slice plan.
- **Conversation Persistence (125)** → moved to initiative 160. Pipeline steps are stateless in 140.
- **SDK Client Warm Pool (104)** → remains deferred. Nice-to-have optimization for reducing per-step latency.

### CF Connection Model

The `ContextForgeClient` (slice 126, complete) wraps CF CLI subprocess calls behind a typed interface. Pipeline actions use this client for all CF operations. Subprocess calls run via `asyncio.to_thread` to avoid blocking the async executor. Migration to MCP client transport is a future optimization when CF's HTTP transport is available — the `ContextForgeClient` abstraction isolates this change from action implementations.

### From Context Forge

- MCP server tools: `context_build`, `project_update`, `context_summarize` (complete)
- CLI: `cf set`, `cf build`, `cf get`, `cf list slices --json` (complete)
- CWD-based project resolution (complete)

---

## Scope Boundaries

### In Scope (initiative 140)

- Action protocol and core action implementations (7 action types)
- Step type protocol and core step types (phase, compact, review, collection, devlog)
- Pipeline definition YAML grammar with validation
- Model resolution chain (alias cascade, 5 levels)
- Pipeline executor with sequential step execution
- Basic loops (max iterations, until condition)
- Collection loops (iterate over CF query results)
- Convergence loop syntax (acknowledged, stub execution — strategies are 160)
- Pipeline state persistence and resume
- Mid-process adoption (`--from` flag)
- CLI: `sq run` with subcommands
- Built-in pipelines: slice-lifecycle, review-only, implementation-only, design-batch
- Custom pipeline discovery and loading
- Pipeline validation (`--validate`)
- Structured review findings in frontmatter (single-file format: YAML index + prose body)
- DEVLOG automation
- Review findings extraction (structured output, slice 141)

### Out of Scope (initiative 160: Pipeline Intelligence)

- Weighted review convergence strategies
- Model pools with selection strategies (random, round-robin, cheapest)
- Escalation behaviors (retry with stronger model)
- Conversation persistence across pipeline steps
- Cross-iteration finding matching and identity
- Advanced loop constructs beyond basic/collection
- Finding severity classification and auto-fix routing

### Out of Scope (future, unscheduled)

- GUI/web interface for pipeline monitoring
- Cross-slice parallelism (run multiple slices simultaneously)
- Cost tracking and optimization across providers
- Pipeline sharing/marketplace
- CI/CD integration
- Automated complexity estimation for model selection

---

## Open Questions

1. **Pipeline definition storage for custom pipelines:** Convention is `project-documents/user/pipelines/`. Is this sufficient or should we also support `~/.config/squadron/pipelines/` for cross-project definitions? Likely: both, with project-local taking precedence.

2. **[RESOLVED] Structured findings format:** Single-file format. Structured findings index in YAML frontmatter (id, severity, category, summary, location). Full prose descriptions in the markdown body. Pipeline reads frontmatter for programmatic access; humans read the body for detail.

3. **[RESOLVED] CF connection model:** Use `ContextForgeClient` (slice 126, complete) with subprocess CLI transport. Async compatibility via `asyncio.to_thread`. MCP client transport is a future optimization isolated behind the client abstraction.

4. **[RESOLVED] Model specification in YAML:** Nested form (`review.model: minimax2.7`) rather than map form (`models: { dispatch: opus, review: minimax2.7 }`). The nested form reads more naturally and matches how users think about step configuration.

5. **[DEFERRED → 149] Collection loop item binding:** How does `{slice.index}` resolve inside an `each` block? Simple string interpolation? Template engine? Python f-string semantics? Keep it as simple as possible — likely just dot-path access into the bound item dict. Full semantics (item type/schema, field traversal, missing field behavior, read-only binding) are a 149 design decision. The `design-batch` example in this document uses `{slice.index}` as illustrative syntax only — the binding mechanism is not implemented in 140.

---

## Initiative 160 Preview: Pipeline Intelligence

Documented here for architectural coherence. Not in scope for 140 implementation.

### Weighted Review Convergence

When an agent implements something and a review finds concerns, the agent addresses them. Re-review often finds *new* concerns that weren't there before — some valid, many fabricated. The convergence strategy applies a discount factor to new findings across iterations:

```
Iteration 1: findings weighted at 1.0 (full trust)
Iteration 2: NEW findings weighted at w (e.g., 0.8)
             PERSISTING findings retain original weight
Iteration 3: NEW findings weighted at w² (0.64)
             PERSISTING findings retain original weight

Termination: max(weighted_new_findings.severity) < threshold
             OR iteration_count >= max_iterations
```

**Finding identity** for cross-iteration matching: category + location (file:line). Exact string matching on summaries won't work (wording varies). Structural match on (category, location) is robust enough.

**Persisting vs. novel:** A finding at the same (category, location) across iterations is persisting — something is genuinely wrong. A finding at a new location or category is novel — the agent may be inventing problems. The discount applies to novel findings only.

### Model Pools

Pool definitions in `~/.config/squadron/pools.toml`. Selection strategies: random (uniform), round-robin (deterministic rotation), cheapest (prefer lowest cost_tier from alias metadata), capability-match (future — select based on task type affinity).

Pools slot into the model resolver transparently. A pool reference resolves to a concrete (provider, model_id) at call time. The rest of the system never knows a pool was involved.

### Escalation Behaviors

When a review returns FAIL, optionally retry with a more capable model before checkpointing:

```yaml
review:
  template: code
  escalation:
    to: opus                     # retry with this model
    trigger: on-fail             # when to escalate
    max: 1                       # escalation attempts before checkpoint
```

This is a behavior attached to the review action — not a general pipeline concept. It composes cleanly: review runs → FAIL → escalation fires → review re-runs with stronger model → if still FAIL → checkpoint.

### Conversation Persistence

Optional per-step. When enabled, the agent's conversation state is preserved and restored across retries or loop iterations within the same step. This gives the agent memory of what it already tried.

Not applicable across steps — each step starts fresh with assembled context. Cross-step persistence creates coupling that makes resume and mid-process adoption fragile.

---

## Notes

- **Numbering:** This initiative claims the 140-band in squadron's index space. The 100-band (orchestration v2) is complete. The 160-band is reserved for Pipeline Intelligence. The 160-band is already claimed by multi-agent communication.
- **File naming:** This document is `140-arch.pipeline-foundation.md`. Slice plan will be `140-slices.pipeline-foundation.md`. First slice design at `140-slice.{name}.md`.
- **Supersedes:** This document supersedes the earlier `120-arch.automated-dev-pipeline.md` draft which was written pre-squadron-rename and before the 100-band was complete.
- **Incremental delivery:** Each built-in pipeline is independently useful. Even without custom pipelines or loops, `sq run slice-lifecycle --slice 191` replacing the markdown-based run-slice is a significant improvement.
