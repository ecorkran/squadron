---
docType: slice-plan
parent: 180-arch.pipeline-intelligence.md
project: squadron
dateCreated: 20260411
dateUpdated: 20260412
status: not_started
---

# Slice Plan: Pipeline Intelligence

## Parent Document
`180-arch.pipeline-intelligence.md` — Architecture: Pipeline Intelligence

---

## Overview

Pipeline Intelligence layers judgment-based behaviors onto the Pipeline Foundation (initiative 140). Where 140 is deterministic machinery — run step, check condition, proceed or pause — 180 is probabilistic: model pools with selection strategies, parallel fan-out for multi-branch dispatch, weighted convergence across review iterations, cross-boundary finding triage, and within-step conversation persistence.

Every capability registers through extension points 140 already defines; no 140 code is modified.

The initiative follows its own dependency graph — model pools and fan-out deliver standalone value with no intelligence dependencies and land first. Review convergence intelligence follows. Conversation persistence comes last because nothing else depends on it.

---

## Foundation Work

1. [x] **(180) Model Pool Infrastructure and Strategies** — Pool definition schema, `ModelPool` data model, `PoolStrategy` protocol, and `SelectionContext`. Four built-in strategies: `random` (uniform default), `round-robin` (deterministic rotation with per-pool state in `~/.config/squadron/pool-state.toml`), `cheapest` (uses `cost_tier` from alias metadata), `weighted-random` (per-model weights). Ships with default pools in `src/squadron/data/pools.toml` (e.g. `review`, `high`, `cheap`) using the same data directory convention as model aliases and review templates; users layer overrides in `~/.config/squadron/pools.toml`. Pool loader validates entries are alias references (not other pools) at load time. No dependency on any other 180 slice. Dependencies: [141 configuration externalization, 142 model resolver]. Risk: Low. Effort: 3/5

---

## Feature Slices (in implementation order)

2. [x] **(191) Dispatch Summary Context Injection** — Non-SDK summary models (e.g. minimax via openrouter) receive a one-shot call with instructions but zero pipeline context, producing empty summaries. Assembles prior step results — including generated artifact contents (slice designs, review findings, dispatch outputs) — into the message sent to `capture_summary_via_profile`. SDK-session summaries are unaffected; this targets only the dispatch/one-shot path. Logic lives in a single `pipeline/summary_context.py` module. Dependencies: [161, 164]. Risk: Low. Effort: 2/5

3. [x] **(181) Pool Resolver Integration and CLI** — Extends 140's model resolver cascade with `pool:` prefix handling; resolution is recursive (pool → alias → provider/model_id) and transparent to the rest of the pipeline system. Every pool selection is logged into run state for debugging. CLI: `sq pools` (list), `sq pools show <name>` (details + recent selections), `sq pools reset <name>` (clear round-robin state), `sq run ... --model pool:<name>` (CLI override). Dependencies: [180]. Risk: Low. Effort: 2/5

4. [ ] **(182) Fan-Out / Fan-In Step Type** — General-purpose parallel branch infrastructure. New `fan_out` step type dispatches N copies of an inner step config concurrently (each with its own resolved model, drawn from a pool or an explicit list), waits for all via `asyncio.gather`, and feeds the collected results through a `fan_in` reducer. Core infrastructure for ensemble review (slice 189) and any future multi-model consensus pattern. Full pool support requires slice 181 — pool-specified model lists resolve transparently through the pool resolver. **Relocated from 140 future work item 10.** Fan-out is the infrastructure ensemble review depends on, and it shares model-pool plumbing with 180 — splitting across initiatives would fragment one coherent feature. Dependencies: [149 executor, 181]. Risk: High. Effort: 3/5

5. [ ] **(183) Findings Ledger and Matcher** — Cross-iteration finding tracking infrastructure. Implements `LedgerEntry` (finding, first_seen, last_seen, times_seen, weight, status, matched_by) and `FindingsLedger` (entries, add_iteration, active_weighted_findings, resolved_findings, serialization). `FindingMatcher` performs category + fuzzy location matching with a configurable line-drift tolerance window. Extensible category taxonomy seeded from review templates. Ledger serializes into 140's pipeline state file so convergence survives checkpoint/resume. Foundation for weighted-decay convergence and for ensemble finding merge. No dependency on any other 180 slice — can proceed in parallel with slices 180-182. Dependencies: [143 structured findings, 150 pipeline state]. Risk: Medium. Effort: 3/5

6. [ ] **(184) Weighted-Decay and Strict Convergence Strategies** — Primary review-loop intelligence. Implements the `ConvergenceStrategy` protocol + `ConvergenceDecision` and registers two concrete strategies with 140's strategy registry: `weighted-decay` (configurable `decay` 0.8, `threshold` 0.5, `max_iterations` 4, `persist_weight` 1.0 — novel findings decay across iterations, persisting findings hold full weight) and `strict` (no decay, baseline for comparative calibration). Produces a convergence report summarizing resolved, persisting, and dismissed findings; report is consumed by 140's DEVLOG action. Configurable via `loop.strategy` block in pipeline YAML. Dependencies: [183]. Risk: Medium. Effort: 3/5

7. [ ] **(185) Escalation Behavior** — Single-step retry with a stronger model on review FAIL. `EscalationBehavior` + `EscalationConfig` (trigger: `on-fail`, `to:` model, `re-review: true`, `max: 1`) registered as a 140 action behavior hook. Fires *after* the convergence loop exhausts (escalation is outer, convergence is inner); resets the convergence ledger on re-dispatch. If the escalation target is a `pool:` reference, each attempt draws a fresh pool selection. Depends on pool resolver only if escalation targets are expressed as `pool:` references; otherwise only needs 140's executor. Dependencies: [140 executor; 181 for pool targets]. Risk: Low. Effort: 2/5

8. [ ] **(186) Finding Triage and Scope Classification** — Adds a `scope` field to `ReviewFinding` (`code`, `slice`, `architecture`, `process`, `external`). Triage classifier runs as a step in the review loop between review execution and auto-fix, inspecting each finding via explicit scope metadata (preferred), document references, constraint language ("violates", "contradicts", "conflicts with"), and scope-mismatch heuristics. Cross-boundary findings pause the pipeline at a checkpoint with a structured PM-escalation message instead of auto-fixing the wrong artifact. No dependency on any other 180 slice. Dependencies: [143 structured findings]. Risk: Medium. Effort: 3/5

9. [ ] **(187) ConversationStore Protocol and SQLite Backend** — Storage layer for within-step conversation persistence: `ConversationStore` protocol (save, load, list, delete), SQLite-backed implementation, per-run conversation directory `~/.config/squadron/runs/{run-id}/conversations/`. Handles message + tool-use serialization with a compact on-disk schema. **Absorbs the deferred scope of 100-band slice 125 (Conversation Persistence & Management).** No other 180 slice depends on this — it sequences immediately before its sole consumer, slice 188. Dependencies: [150 pipeline state directory layout]. Risk: Medium. Effort: 3/5

10. [ ] **(188) Conversation Persistence in Convergence Loop** — Within-step persistence across retries. When a step declares `persistence: true`, the retry agent receives the prior conversation — it knows what it already tried and why it failed. Includes between-retry compaction (`persistence_compact: true`, default on when persistence is enabled) that preserves findings + stated approach + failure reason and discards tool-use details and verbose output. Reuses 140's `compact` action parameterized for the retry context. Scope is strictly within-step; cross-step persistence is out of scope. Dependencies: [187, 184]. Risk: Medium. Effort: 3/5

11. [ ] **(189) Ensemble Review and Unanimous Convergence** — Multi-model review via fan-out: run a review template against N models in parallel, merge findings through `FindingMatcher` (the same identity system used for iteration matching), and apply the `unanimous` convergence strategy — continue only if all models agree on PASS, boost weight for findings flagged by multiple models. Ensemble configuration in pipeline YAML (`review.ensemble.models`, `review.ensemble.agreement`, `review.ensemble.boost`). Reuses the findings ledger from slice 183 as merge infrastructure. Dependencies: [182, 183, 184]. Risk: High. Effort: 3/5

---

## Integration Work

12. [ ] **(190) Pipeline Intelligence Documentation and Examples** — Authoring guide covering model pools, fan-out, convergence strategies, escalation, finding triage, conversation persistence, and ensemble review. Example pipelines in `examples/`: weighted-decay review loop, pool-based model selection, escalation + convergence combined, ensemble review with fan-out. Configuration reference (`pools.toml` schema, convergence parameter matrix, escalation config). Observability and tuning notes: how to read the ledger, how to calibrate decay/threshold from logged data, how to debug pool selections. Dependencies: [all feature slices]. Risk: Low. Effort: 2/5

---

## Implementation Order

```
Foundation:
  180. Model Pool Infrastructure and Strategies      (after 140-band complete)

Feature Slices:
  191. Dispatch Summary Context Injection            (after 140-band; no 180 deps)
  181. Pool Resolver Integration and CLI             (after 180)
  182. Fan-Out / Fan-In Step Type                    (after 181)
  183. Findings Ledger and Matcher                   (parallel with 180-182; after 140-band)
  184. Weighted-Decay and Strict Convergence         (after 183)
  185. Escalation Behavior                           (after 181 for pool targets; else after 140)
  186. Finding Triage and Scope Classification       (parallel with 180-185; after 143)
  187. ConversationStore Protocol and SQLite Backend  (just before 188; no earlier consumer)
  188. Conversation Persistence in Convergence Loop  (after 187, 184)
  189. Ensemble Review and Unanimous Convergence     (after 182, 183, 184)

Integration:
  190. Pipeline Intelligence Documentation           (after all prior)
```

### Parallelization Notes

- **Slice 191 (Dispatch Summary Context) has no 180 dependencies** and should land first — it fixes a broken user-facing flow (non-SDK summary models produce empty summaries). It depends only on 140-band slices 161 and 164.
- **Pool track and convergence track are independent.** Slices 180-182 (pool infra → resolver → fan-out) and slices 183-184 (ledger → weighted-decay) share no code and can proceed in parallel. They rejoin at ensemble review (189).
- **Slice 183 (Findings Ledger) can begin immediately** alongside the pool track — it depends only on 140-band structured findings, not on any 180 slice.
- **Slice 186 (Finding Triage) is fully independent** — depends only on 143's structured findings. Can proceed in parallel with any other 180 slice.
- **Slice 187 (ConversationStore) is deferred to its point of use.** Only slice 188 consumes it, so it sequences immediately before 188 rather than up front. Nothing earlier in 180 depends on it.
- **Slice 185 (Escalation) is nearly independent.** Only requires 140's executor and model resolver. The `pool:` escalation target feature requires 181 first, but single-model escalation targets can land earlier if desired.

---

## Notes

- **Fan-out / fan-in relocated from 140.** Originally slice 159 in 140's plan, then moved to 140 future work (item 10) once it became clear it shares model-pool plumbing with 180. It now lives as slice 182 in this plan. 140's future-work entry should be updated to reference 182 during the next 140-band cleanup pass.
- **Slice 125 (Conversation Persistence) absorbed into slice 187.** The 100-band scope for a `ConversationStore` protocol and SQLite backend was deferred and reserved for the 160/180 band. It is now materialized as slice 187. It is not treated as up-front foundation work because no earlier slice in this plan depends on it — 188 is its only consumer.
- **Default pools ship with the product.** Slice 180 seeds `src/squadron/data/pools.toml` following the same data-file convention as model aliases. User overrides layer on top via `~/.config/squadron/pools.toml`. Suggested defaults: `review` (varied mid-tier models), `high` (strongest available models), `cheap` (lowest-cost models).
- **Convergence calibration is empirical.** Default decay (0.8), threshold (0.5), and tolerance window (10 lines) are educated guesses. Slice 184 ships with the `strict` strategy as a known-behavior baseline explicitly so weighted-decay can be compared against "just loop N times." Detailed per-iteration logging is a hard requirement on 184, not an optional extra.
- **Pool round-robin state is global, not per-run.** Rotation persists in `~/.config/squadron/pool-state.toml` and is shared across runs; `sq pools reset` clears it. Per-run rotation would defeat the purpose of systematic comparison across runs.
- **Escalation + pool interaction re-draws each attempt.** If a step's escalation target is `pool:high`, each attempt draws a fresh model from the pool rather than locking to the first selection.
- **Ensemble review is in first delivery, not deferred.** Earlier architecture drafts noted ensemble review as "designed for, not built." It is promoted to slice 189 because fan-out (182) is now in scope, and the `unanimous` strategy is a small additional increment once fan-out and the ledger exist.
- **Rule weights are deferred to future work.** The weight calculation in slice 184 is structured as a composable function so rule weights can plug in later without changing the convergence strategy protocol.

---

## Future Work

1. [FUTURE] **Rule Weights** — Per-rule severity multipliers in review templates (`rules: [{name, weight, description}]`). Effective finding weight becomes `rule_weight × iteration_decay × severity_multiplier`. Slice 184's weight calculation is a composable function specifically to accommodate this. Dependencies: [184]. Effort: 2/5

2. [FUTURE] **Escalation Chains** — Multi-step escalation beyond a single model → model retry. Configuration: `escalation.chain: [opus, "pool:high"]` with `max: 2`. Natural extension of single-step escalation in slice 185. Dependencies: [185]. Effort: 2/5

3. [FUTURE] **Cross-Step Conversation Persistence** — Conversation memory spanning multiple pipeline steps, not just retries within a step. Requires careful handling of resume semantics, step reordering, and mid-process adoption. Deliberately out of scope for slice 188. Dependencies: [188]. Effort: 3/5

4. [FUTURE] **Capability-Match Pool Strategy** — Task-type-aware model selection: infer task affinity from action type + context and bias pool selection accordingly. Dependencies: [180]. Effort: 2/5

5. [FUTURE] **Pool Analytics** — Track model performance by pool (success rate, latency, cost, convergence iteration count) for informed strategy tuning. Dependencies: [181]. Effort: 2/5

6. [FUTURE] **Convergence Calibration Tooling** — Retroactive "what-if" scoring: given logged ledger data, compute outcomes under alternate decay/threshold values without re-running the pipeline. Optional "calibration run" mode that runs both `strict` and `weighted-decay` side-by-side and compares verdicts. Dependencies: [184]. Effort: 2/5

7. [FUTURE] **Ensemble Agreement Strategies Beyond Unanimous** — `majority`, `weighted`, and `any-agreement` strategies for ensemble review. Slice 189 ships `unanimous` only. Dependencies: [189]. Effort: 2/5

8. [FUTURE] **Finding Category Auto-Mapping** — Fuzzy mapping from free-form model output ("null safety") to a canonical category (`error-handling`) using an extensible alias table. Currently slice 183 uses exact category matching. Dependencies: [183]. Effort: 1/5
