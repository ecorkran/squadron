---
docType: architecture
layer: project
project: squadron
archIndex: 160
component: pipeline-intelligence
dateCreated: 20260327
dateUpdated: 20260327
status: draft
---

# Architecture: Pipeline Intelligence

## Overview

Pipeline Intelligence layers sophisticated behaviors onto the Pipeline Foundation (initiative 140). Where 140 provides the machinery — actions, definitions, executor, state, basic loops — this initiative provides the judgment: convergence-based review loops that resist AI hallucination drift, model pools that abstract provider selection, escalation behaviors that automatically retry with stronger models, and conversation persistence that gives agents memory across retries.

These capabilities are distinct from the foundation because they involve heuristics, tuning, and experimentation. The foundation is deterministic: run step, check condition, proceed or pause. Intelligence is probabilistic: score findings, apply discount factors, estimate convergence, select models from pools. The boundary between "always works the same way" and "requires calibration" is the initiative split.

### Why This Matters

The single most common failure mode in AI-assisted development pipelines is the **infinite review loop**. An agent implements something. A reviewer finds concerns. The agent addresses them. The reviewer finds *new* concerns. The agent addresses those. The reviewer invents more. This continues until the context window fills, the operator intervenes, or the code is worse than when it started.

Every team using AI agents for development hits this. Most solve it with `max_iterations: 3` and hope. That works until the third iteration's concerns are legitimate and the pipeline stops prematurely, or the first iteration's concerns are trivial and the pipeline wastes two more cycles addressing them.

The weighted convergence strategy is a principled solution: trust decays for novel findings across iterations, persists for recurring findings, and the loop terminates when the expected value of continuing is below a threshold. It's the same intuition behind discount factors in RL, applied to the specific domain of iterative code review.

### Relationship to 140 (Pipeline Foundation)

Every capability in this initiative plugs into extension points defined in 140:

| 160 Capability | 140 Extension Point |
|---|---|
| Convergence strategies | `loop.strategy` field on review steps |
| Model pools | `pool:` prefix in model resolver |
| Escalation behaviors | `escalation` field on review actions |
| Conversation persistence | `persistence` field on steps |
| Finding matching | Structured findings JSON from review action |

No 140 code is modified. 160 registers new strategies, new resolver backends, and new action behaviors through the registries 140 establishes.

---

## Weighted Review Convergence

### The Problem

When a review iteration finds concerns and the implementing agent addresses them, the subsequent review is operating in a subtly different context. It has been primed — by the pipeline's instructions — to look for problems. It will find them whether they exist or not. This is not a model deficiency; it's an inherent property of directed search. Ask anyone to find flaws and they will, eventually fabricating them.

The problem is asymmetric: **real issues persist across iterations, fabricated issues appear and disappear.** A function that genuinely lacks error handling will be flagged in iteration 1 and, if not fixed, iteration 2. But "this variable name could be more descriptive" tends to appear in iteration 2 about different variables than iteration 1 flagged — the reviewer is generating new opinions, not detecting stable defects.

### The Model

Each review iteration produces a set of findings. Each finding has:
- **Identity:** A structural fingerprint (category + location) that enables cross-iteration matching
- **Severity:** concern, fail, or note (from the existing `ReviewFinding` model)
- **Iteration of origin:** When this finding first appeared
- **Weight:** Starts at 1.0, decayed for novel findings in later iterations

The convergence loop maintains a **findings ledger** across iterations:

```
Iteration 1 (weight = 1.0):
  F1: [error-handling, parser.py:45]    severity=concern  weight=1.0
  F2: [naming, utils.py:12]            severity=note      weight=1.0

Agent addresses F1, F2

Iteration 2 (novel weight = w, e.g. 0.8):
  F1: [error-handling, parser.py:45]    → PERSISTS (not fixed properly)
                                          weight stays 1.0
  F3: [logging, parser.py:60]           → NOVEL finding
                                          weight = 0.8
  F4: [docstring, utils.py:12]          → NOVEL (different category, same file)
                                          weight = 0.8

Agent addresses F1, F3, F4

Iteration 3 (novel weight = w² = 0.64):
  F5: [type-hints, executor.py:30]      → NOVEL
                                          weight = 0.64
  F6: [naming, executor.py:35]          → NOVEL
                                          weight = 0.64

Convergence check:
  max(novel_weighted_severity) = 0.64 * concern = 0.64
  threshold = 0.7
  0.64 < 0.7 → CONVERGED, stop loop
```

### Finding Identity and Matching

Two findings match across iterations if they share the same **(category, location)** tuple. This is intentionally coarse:

- **Category** is a structural tag: `error-handling`, `naming`, `security`, `test-coverage`, `documentation`, etc. The review action in 140 produces these. The set of categories is extensible but starts with a curated default list.
- **Location** is a file reference, normalized to `file:line` or just `file` when line numbers shift between iterations (as they will after the agent modifies code).

Exact string matching on finding summaries is deliberately avoided. The same defect described differently across iterations ("missing null check" vs. "no validation for None input") would fail string matching but shares category and location.

#### Fuzzy Location Matching

Line numbers shift as code changes between iterations. The matcher uses a tolerance window:

```python
def locations_match(loc_a: str, loc_b: str, tolerance: int = 10) -> bool:
    """Match file:line locations with tolerance for line drift."""
    file_a, line_a = parse_location(loc_a)
    file_b, line_b = parse_location(loc_b)
    if file_a != file_b:
        return False
    if line_a is None or line_b is None:
        return True  # file-level match
    return abs(line_a - line_b) <= tolerance
```

This is good enough for iteration matching. If a finding moves from `parser.py:45` to `parser.py:48` after the agent adds three lines above it, the tolerance catches it. If the finding moves to a different file, it's a novel finding — which is correct, because the agent likely refactored.

### Convergence Strategies

The convergence logic is a **strategy** registered with the pipeline executor. 140 defines the extension point (`loop.strategy` field). 160 provides concrete strategies.

#### Strategy Protocol

```python
class ConvergenceStrategy(Protocol):
    """Determines whether a review loop should continue or terminate."""

    def should_continue(
        self,
        iteration: int,
        current_findings: list[ReviewFinding],
        ledger: FindingsLedger,
        config: ConvergenceConfig,
    ) -> ConvergenceDecision:
        """Evaluate whether another iteration is warranted."""
        ...
```

`ConvergenceDecision` carries: continue/stop, reason (for logging/DEVLOG), the updated ledger, and an optional recommendation (e.g., "escalate to human — persisting FAIL findings after 3 iterations").

#### Built-in Strategies

**`weighted-decay`** — The primary strategy described above. Parameters:
- `decay`: Weight multiplier per iteration (default 0.8)
- `threshold`: Weighted severity below which novel findings are ignored (default 0.5)
- `max_iterations`: Hard cap (default 4)
- `persist_weight`: Weight for persisting findings (default 1.0, i.e., no discount)

```yaml
# In a pipeline definition
- implement:
    phase: 6
    review:
      template: code
      loop:
        strategy: weighted-decay
        decay: 0.8
        threshold: 0.5
        max: 4
```

**`strict`** — No decay. Every iteration's findings are at full weight. Loop runs until PASS or max iterations. This is the "just loop N times" baseline — equivalent to what most people do now, but with the structured findings infrastructure. Useful as a control when evaluating whether weighted-decay actually improves outcomes.

**`unanimous`** — Run the review with N different models. Continue only if all agree on PASS. Finding weight is boosted when multiple models flag the same issue. This is an ensemble strategy — a bridge to the multi-agent review work in initiative 180. Not in first delivery of 160 but architecturally accounted for.

### Findings Ledger

The ledger is the cross-iteration memory. It tracks every finding across all iterations, with provenance:

```python
@dataclass
class LedgerEntry:
    finding: ReviewFinding
    first_seen: int              # iteration number
    last_seen: int               # most recent iteration where it appeared
    times_seen: int              # number of iterations it appeared in
    weight: float                # current effective weight
    status: str                  # active | resolved | dismissed
    matched_by: str | None       # identity key used for matching

@dataclass
class FindingsLedger:
    entries: list[LedgerEntry]
    iteration_count: int
    
    def add_iteration(self, findings: list[ReviewFinding], config: ConvergenceConfig) -> None:
        """Integrate a new iteration's findings into the ledger."""
        ...
    
    def active_weighted_findings(self) -> list[tuple[LedgerEntry, float]]:
        """Return active findings with their effective weights."""
        ...
    
    def resolved_findings(self) -> list[LedgerEntry]:
        """Findings that appeared in prior iterations but not the latest."""
        ...
    
    def to_dict(self) -> dict:
        """Serialize for pipeline state persistence."""
        ...
```

The ledger is serialized into the pipeline state file (from 140) so convergence survives checkpoint/resume.

### Convergence Reporting

When a convergence loop terminates, the pipeline produces a summary:

```
Convergence report: 3 iterations
  Resolved: 4 findings (addressed by agent)
  Persisting: 1 finding (error-handling @ parser.py:45) — weight 1.0
  Dismissed: 3 findings (below threshold after decay)
  Verdict: CONCERNS (1 persisting finding)
  Recommendation: Human review of parser.py error handling
```

This integrates with the DEVLOG action — the convergence summary becomes part of the automated DEVLOG entry.

---

## Model Pools

### Concept

A model pool is a named collection of model aliases with a selection strategy. Anywhere a pipeline definition specifies a model, it can specify a pool instead. The model resolver handles the `pool:` prefix transparently — the rest of the pipeline system doesn't know whether a model came from a fixed alias or a pool selection.

### Pool Definition

```toml
# ~/.config/squadron/pools.toml

[pools.review]
strategy = "random"
models = ["minimax2.7", "sonnet", "gemma3", "gpt54-nano"]

[pools.high]
strategy = "random"
models = ["opus", "gpt54-codex", "gemini-pro"]

[pools.cheap]
strategy = "cheapest"
models = ["haiku", "gemma3", "minimax2.7"]
# cheapest strategy uses cost_tier from model alias metadata

[pools.experiment-a]
strategy = "round-robin"
models = ["opus", "sonnet", "gpt54-codex"]
# round-robin for systematic comparison across runs
```

### Selection Strategies

| Strategy | Behavior | Use Case |
|---|---|---|
| `random` | Uniform random selection | Default. Varied model exposure. |
| `round-robin` | Deterministic rotation, tracked per pool | Systematic comparison across runs |
| `cheapest` | Prefer lowest `cost_tier` from alias metadata | Cost-conscious default pool |
| `weighted-random` | Random with per-model weights | Prefer certain models while maintaining variety |
| `capability-match` | Select based on task type affinity (future) | Right model for right task |

The strategy protocol:

```python
class PoolStrategy(Protocol):
    def select(
        self,
        pool: ModelPool,
        context: SelectionContext,   # task type, prior selections, etc.
    ) -> str:
        """Return a model alias from the pool."""
        ...
```

`SelectionContext` carries: the action type requesting the model (review, dispatch, etc.), the pipeline run ID (for round-robin state), and optionally the task description (for future capability-match). The strategy is stateless across pipeline runs — round-robin state is tracked in a small file alongside pool config.

### Pool in Pipeline Definitions

```yaml
model: pool:high                # pipeline-level: draw from high pool

steps:
  - design:
      # inherits pool:high from pipeline
      review:
        model: pool:review      # action-level: use review pool

  - implement:
      model: sonnet             # fixed model, ignores pipeline pool
      review:
        model: pool:review
```

### Integration with Model Resolver

The 140 model resolver cascade gains one additional check at each level:

```python
def resolve_model(spec: str) -> tuple[str, str]:
    """Resolve a model specification to (provider, model_id).
    
    spec can be:
      - A model alias: "opus" → resolved via alias registry
      - A pool reference: "pool:review" → select from pool, then resolve alias
      - A full model ID: "claude-opus-4-6" → looked up directly
    """
    if spec.startswith("pool:"):
        pool_name = spec[5:]
        pool = load_pool(pool_name)
        selected_alias = pool.strategy.select(pool, context)
        return resolve_model(selected_alias)  # recursive — pool selects an alias
    return alias_registry.resolve(spec)
```

The recursion is safe because pool entries are aliases (not pool references). Validation at pool load time rejects circular references.

### CLI Support

```
sq pools                      # list configured pools
sq pools show review          # show pool details and recent selections
sq run ... --model pool:high  # use pool via CLI override
```

---

## Escalation Behaviors

### Concept

When a review returns FAIL, the pipeline can automatically retry with a more capable model before pausing for human review. This is a single-retry pattern — not an infinite escalation chain.

```
Step runs with model=sonnet → review returns FAIL
  → escalation fires: retry with model=opus
  → re-review
  → if PASS: proceed (escalation succeeded)
  → if still FAIL: checkpoint (human reviews)
```

### Configuration

Escalation is a property of the review action within a step, not the step itself:

```yaml
- implement:
    model: sonnet
    review:
      template: code
      model: minimax2.7
      escalation:
        trigger: on-fail         # when to escalate
        to: opus                 # model for retry
        re-review: true          # re-review after retry (default true)
        max: 1                   # escalation attempts (default 1)
```

### Interaction with Convergence Loops

Escalation and convergence are orthogonal. Escalation applies to the *dispatch* model (the agent implementing the work). Convergence applies to the *review loop* (how many review iterations and how findings are weighted).

A step can have both:

```yaml
- implement:
    model: sonnet
    review:
      template: code
      loop:
        strategy: weighted-decay
        max: 3
      escalation:
        trigger: on-fail
        to: opus
```

Execution order:
1. Dispatch with sonnet
2. Review loop runs (up to 3 iterations with weighted decay)
3. If the convergence loop's final verdict is FAIL → escalation fires
4. Re-dispatch with opus
5. Review loop runs again (fresh ledger — new implementation, new findings)
6. If still FAIL → checkpoint

Escalation resets the convergence loop because the implementation is substantially different after re-dispatch with a stronger model.

### Escalation Chain (future consideration)

For now, escalation is a single step: model A → model B. A chain (sonnet → opus → human) is expressible as `max: 2` with a list of models:

```yaml
escalation:
  chain: [opus, "pool:high"]    # try opus, then draw from high pool
  trigger: on-fail
```

This is a natural extension but not in first delivery. Single-step escalation covers the common case.

---

## Conversation Persistence

### Concept

By default (140), every pipeline step dispatches a fresh agent with assembled context. No conversation state carries between steps or between retry iterations within a step.

Conversation persistence gives an agent memory across retries. When a step with `persistence: true` fails and retries, the retry agent receives the prior conversation — it knows what it already tried and what went wrong.

### Scope

Persistence applies **within a step's retry/convergence loop**, not across steps. Cross-step persistence creates coupling that makes resume, mid-process adoption, and step reordering fragile.

```yaml
- implement:
    model: sonnet
    persistence: true            # agent remembers across retries
    review:
      template: code
      loop:
        strategy: weighted-decay
        max: 3
```

Without persistence: each retry starts from scratch with CF-assembled context. The agent might try the same failing approach twice.

With persistence: each retry includes the prior conversation. The agent knows "I tried approach X and it failed because Y" and can try a different approach.

### Storage

Conversations are stored in the pipeline state directory alongside run state:

```
~/.config/squadron/runs/
  run-20260327-191/
    state.json                   # pipeline state (from 140)
    conversations/
      implement-iter-1.json      # conversation from first attempt
      implement-iter-2.json      # conversation from second attempt (includes iter-1)
```

### Interaction with Compaction

Long conversations hit context limits. Between retry iterations with persistence enabled, an automatic compaction can run:

```yaml
- implement:
    persistence: true
    persistence_compact: true    # compact between retries (default true when persistence is on)
```

The compaction preserves: what was attempted, what failed, what the review found. It discards: the full implementation conversation, tool use details, verbose output. This is the same `compact` action from 140, parameterized for the retry context.

### Dependency: Slice 125

Conversation persistence depends on slice 125 (Conversation Persistence & Management) from the 100-band, which was deferred. The `ConversationStore` protocol and SQLite backend from 125 provide the storage layer. If 125 is not yet complete when 160 begins, it moves into 160 as a prerequisite slice.

---

## Finding Severity and Weights (Future Vision)

Beyond the iteration-based weight decay, individual review rules can carry weights:

```yaml
# In a review template or rules file
rules:
  - name: error-handling
    weight: 1.5                  # more important than default
    description: Functions must handle errors explicitly

  - name: naming-conventions
    weight: 0.5                  # less important than default
    description: Variable and function names should be descriptive

  - name: security-input-validation
    weight: 2.0                  # critical
    description: All external input must be validated
```

A finding's effective weight becomes: `rule_weight × iteration_decay × severity_multiplier`.

This means a security finding at iteration 3 (decay 0.64) with rule weight 2.0 has effective weight 1.28 — still above the default threshold. A naming finding at iteration 2 (decay 0.8) with rule weight 0.5 has effective weight 0.4 — below threshold, dismissed.

Rule weights are **not in first delivery** of 160. The architecture accounts for them by making the weight calculation a composable function rather than a hardcoded formula. When rule weights arrive, they plug into the calculation without changing the convergence strategy protocol.

---

## Ensemble Review (Designed For, Not Built)

Multiple models review the same artifact. Findings that appear from multiple models are higher confidence; findings from only one model are lower confidence.

```yaml
- implement:
    review:
      template: code
      ensemble:
        models: [opus, sonnet, minimax2.7]
        agreement: majority      # majority | unanimous | any
        boost: 1.5               # weight multiplier for multi-model findings
```

This interacts with convergence: ensemble findings start at boosted weight, making them harder to dismiss through decay. A finding flagged by 3/3 models at weight 1.5 requires significant decay before dropping below threshold.

Ensemble review is architecturally a convergence strategy variant (`unanimous` strategy in the convergence section above). It runs multiple reviews in parallel (or sequential — model pool makes this transparent) and merges findings using the identity matching system.

This connects to the multi-agent work in initiative 180 (multi-agent communication). Ensemble review is a specific case of "multiple agents evaluate the same artifact and synthesize consensus." The finding identity and ledger systems from 160 provide the merge infrastructure; 180 provides the communication topology.

**Not in first delivery of 160.** Documented here because the finding identity system and convergence strategy protocol must accommodate it.

---

## Component Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                    Pipeline Executor (140)                      │
│                                                                │
│  step declares:            action receives:                    │
│  loop.strategy: X    →     ConvergenceStrategy.should_continue │
│  model: pool:Y       →     PoolStrategy.select                 │
│  escalation: {...}   →     EscalationBehavior.evaluate         │
│  persistence: true   →     ConversationStore.save/load         │
└───────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
┌─────────────────────┐        ┌─────────────────────┐
│  160 Registrations   │        │  140 Registries      │
│                      │        │  (unchanged)         │
│  Strategies:         │        │                      │
│   weighted-decay     │───────▶│  Strategy Registry   │
│   strict             │        │                      │
│   unanimous          │        │  Pool Registry       │
│                      │        │                      │
│  Pool Strategies:    │───────▶│  Model Resolver      │
│   random             │        │  (gains pool:)       │
│   round-robin        │        │                      │
│   cheapest           │        │  Action Registry     │
│   weighted-random    │───────▶│  (gains behaviors)   │
│                      │        │                      │
│  Behaviors:          │        └─────────────────────┘
│   escalation         │
│   persistence        │
│                      │
│  Infrastructure:     │
│   FindingsLedger     │
│   FindingMatcher     │
│   ConversationStore  │
└─────────────────────┘
```

### Package Structure

```
src/squadron/pipeline/
├── intelligence/                  # new — all 160 code lives here
│   ├── __init__.py
│   ├── convergence/
│   │   ├── __init__.py
│   │   ├── protocol.py            # ConvergenceStrategy protocol
│   │   ├── weighted_decay.py      # primary strategy
│   │   ├── strict.py              # baseline strategy
│   │   └── config.py              # ConvergenceConfig
│   ├── ledger/
│   │   ├── __init__.py
│   │   ├── ledger.py              # FindingsLedger
│   │   ├── matcher.py             # FindingMatcher (identity, fuzzy location)
│   │   └── models.py              # LedgerEntry, MatchResult
│   ├── pools/
│   │   ├── __init__.py
│   │   ├── protocol.py            # PoolStrategy protocol
│   │   ├── strategies.py          # random, round-robin, cheapest, weighted-random
│   │   ├── models.py              # ModelPool, SelectionContext
│   │   └── loader.py              # Load pools.toml
│   ├── escalation/
│   │   ├── __init__.py
│   │   ├── behavior.py            # EscalationBehavior
│   │   └── config.py              # EscalationConfig
│   └── persistence/
│       ├── __init__.py
│       ├── store.py               # ConversationStore protocol + SQLite impl
│       └── compactor.py           # Between-retry compaction logic
```

---

## Prerequisites

### From Initiative 140 (Pipeline Foundation)

Everything. Specifically:
- Action protocol and registry (strategy extension point)
- Review action producing structured findings JSON
- Pipeline executor with loop constructs (stub convergence)
- Model resolver with cascade chain (pool: prefix acknowledged)
- Pipeline state persistence (ledger serialization)
- Step configuration schema (escalation, persistence fields parsed but stubbed)

### From 100-band (Complete)

- Review system with `ReviewFinding` model (severity, title, description, file_ref)
- Model alias registry with metadata (cost_tier for cheapest pool strategy)
- Provider protocol (multi-provider for pools)
- Agent registry (dispatch through providers)

### To Be Resolved

- **Slice 125 (Conversation Persistence):** If not completed before 160 begins, the `ConversationStore` protocol and SQLite implementation move into 160 as a prerequisite slice. The protocol is small; the question is whether it's already done.

---

## Scope Boundaries

### In Scope (initiative 160)

- **Convergence strategies:** `weighted-decay` and `strict` implementations
- **Findings ledger:** Cross-iteration finding tracking with identity matching
- **Finding matcher:** Category + fuzzy location matching
- **Model pools:** Pool definitions, selection strategies (random, round-robin, cheapest, weighted-random)
- **Pool resolver:** Integration with 140's model resolver
- **Escalation behavior:** Single-step model escalation on review failure
- **Conversation persistence:** Within-step persistence across retries
- **Convergence reporting:** Summary output for DEVLOG and human review
- **CLI:** `sq pools`, pool management commands
- **Configuration:** `pools.toml` schema and loading

### Designed For, Not Built (future)

- **Ensemble review:** Multi-model parallel review with finding merge (connects to 180)
- **Rule weights:** Per-rule severity multipliers in review templates
- **Capability-match pool strategy:** Task-type-aware model selection
- **Escalation chains:** Multi-step escalation (model A → B → C)
- **Cross-step persistence:** Conversation memory spanning multiple pipeline steps
- **Pool analytics:** Track model performance by pool for informed strategy tuning

### Out of Scope

- Changes to 140's pipeline grammar (only registration of new strategies/behaviors)
- Changes to the review system's core models (builds on existing `ReviewFinding`)
- Multi-agent communication topology (that's initiative 180)
- GUI for convergence visualization (useful but separate)

---

## Risks and Mitigations

### Risk: Convergence Tuning

The decay factor (0.8), threshold (0.5), and tolerance window (10 lines) are educated guesses. Real-world calibration will be needed.

**Mitigation:** Ship with configurable parameters and the `strict` strategy as a known-behavior baseline. Log detailed convergence data (full ledger, per-iteration scores) so calibration can be done empirically. Consider a "calibration run" mode that runs both strict and weighted-decay and compares outcomes.

### Risk: Finding Identity is Hard

Matching findings across iterations by (category, location) is a heuristic. False positives (different findings at the same location treated as persisting) and false negatives (same finding at a shifted location treated as novel) will occur.

**Mitigation:** The fuzzy tolerance window handles line drift. Category matching is coarse enough to be robust. When uncertain, treat as novel (apply decay) — this errs on the side of dismissing rather than persisting, which is the safer direction (persisting findings get full weight and block convergence). Log match decisions for tuning.

### Risk: Pool Complexity

Pools add indirection to model selection. Debugging "why did this step use model X?" becomes harder.

**Mitigation:** Every pool selection is logged with the run state. `sq run --status` shows which model was selected at each step. `sq pools show <name>` shows recent selections. The indirection is always one level deep (pools reference aliases, not other pools).

### Risk: Feature Interaction Complexity

Convergence + escalation + persistence + pools can all apply to the same step. The interaction space is large.

**Mitigation:** Clear precedence rules:
1. Persistence applies within the convergence loop (retries remember prior attempts)
2. Escalation fires after the convergence loop exhausts (escalation is outer, convergence is inner)
3. Pools resolve at dispatch time (orthogonal to convergence and escalation)
4. Each feature is independently disableable — a step can use convergence without pools, escalation without persistence, etc.

Document the interaction matrix explicitly in the slice designs. Test combinatorially.

---

## Open Questions

1. **Convergence calibration data:** Should the pipeline log enough data to retroactively score different decay/threshold values? This would enable "what if decay was 0.7 instead of 0.8?" analysis without re-running. Likely yes — the ledger already contains the raw data; adding iteration-level scoring metadata is cheap.

2. **Pool state persistence:** Round-robin needs state (which model was last selected). Where does this live? Alongside `pools.toml`? In the pipeline run state? Shared across runs (global rotation) or per-run? Likely per-pool global state in `~/.config/squadron/pool-state.toml`, reset-able via `sq pools reset`.

3. **Escalation and pool interaction:** If a step uses `model: pool:medium` and escalation specifies `to: pool:high`, does the escalation re-select from the high pool each time, or lock to the first selection? Likely re-select (each escalation attempt gets a fresh pool draw).

4. **Conversation compaction strategy:** Between retries with persistence, what exactly is kept? The full prior conversation is too large. A summary is too lossy. Likely: keep the review findings (structured JSON), the agent's stated approach, and the failure reason. Discard: tool use details, file contents, verbose output. This needs experimentation.

5. **Finding categories:** Who defines the category taxonomy? Is it fixed in code, configurable per review template, or emergent from the model's output? Likely: ship a default taxonomy, allow review templates to extend it, and have the finding parser map model output to the closest category. Fuzzy category matching (model says "null safety" → maps to `error-handling`) is a natural extension.

---

## Notes

- **Numbering:** This initiative claims the 160-band. Pipeline Foundation is 140. Multi-agent communication has been reindexed to 180.
- **Incremental delivery:** Model pools and convergence strategies are independently useful. Pools can ship before convergence. Escalation can ship before persistence. The slice plan should reflect this — features that don't depend on each other shouldn't be sequenced unnecessarily.
- **Experimentation surface:** This initiative is more experimental than 140. Decay factors, thresholds, matching heuristics — all need tuning against real review data. The first implementation should prioritize observability (detailed logging, ledger inspection) over optimization.
- **Connection to 180 (multi-agent):** Ensemble review is the bridge between 160 and 180. The finding ledger and identity matching from 160 become the merge infrastructure for multi-agent consensus in 180. Design the ledger with multiple concurrent reviewers in mind even though 160 only uses sequential single-reviewer iteration.
