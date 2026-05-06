---
docType: slice-design
slice: auth-classification-diagnostics-cli
project: squadron
parent: 240-slices.pipeline-auth-boundary-flexibility.md
dependencies:
  - 243-resolution-pre-scan
interfaces:
  - 247-documentation-pipeline-authoring-guide-updates
  - 248-adversarial-test-matrix
dateCreated: 20260505
dateUpdated: 20260506
status: complete
---

# Slice Design: Auth-Classification Diagnostics CLI

## Overview

This slice surfaces the pipeline classification produced by slice 243 (`classify_pipeline`) as a
human-readable CLI report via `sq run --explain <pipeline>`. The command prints each model-dispatching
step's resolved alias, model ID, profile, and classification, the aggregate pipeline shape, and the
pool-uncertainty policy that will apply — without executing any step.

The primary user need is "I got an unexpected Claude auth prompt. What does this pipeline actually
need?" The secondary need is documentation examples: `--explain` output gives pipeline authors a
ground-truth view of how their pipeline is classified.

## Value

- **User-facing:** Developers can diagnose auth surprises ("why does my review-only pipeline require
  Claude auth?") without running the pipeline or reading the YAML resolver cascade.
- **Documentation enablement:** Slice 247 will use `--explain` output as authoritative examples for
  the pipeline authoring guide. The three pipeline shapes become concrete rather than prose.
- **Architectural completeness:** Closes the diagnostic gap named in the arch doc (§Envisioned State,
  point 6): "A user can confirm 'this pipeline does / does not need Claude auth' without running it."

## Technical Scope

**In scope:**
- New `--explain` flag on `sq run`.
- `_handle_explain` helper in `cli/commands/run.py` that loads the pipeline, builds a resolver, calls
  `classify_pipeline`, and renders the result via Rich.
- Mutual-exclusivity guard: `--explain` cannot be combined with execution options (`--resume`,
  `--dry-run`, `--from`, `--prompt-only`, `--validate`). It can accept `--param`, `--model`, and
  `--strict` because those affect the resolver used for classification.
- Rich-formatted table for per-step output; summary line for pipeline shape and policy.

**Out of scope:**
- Changes to `classify_pipeline` or `PipelineClassification` — those are complete and stable.
- Adversarial end-to-end tests for the classification matrix (slice 248).
- Pipeline authoring guide updates (slice 247).
- Any changes to the executor, session construction, or pool policy.

## Dependencies

### Prerequisites
- **Slice 243 (Resolution Pre-Scan)** — complete (commit `e838898`). `classify_pipeline`,
  `PipelineClassification`, `StepClassification`, `PipelineShape`, `StepClass`,
  `PoolClassificationPolicy`, and `ClassificationError` are all available in
  `squadron.pipeline.classification`.
- **Slice 244 (Conditional Persistent Session Construction)** — complete (commit `c939fb2`).
  `_run_pipeline_sdk` already builds the resolver with the right inputs; this slice replicates
  that resolver-construction pattern for the explain path.
- **Slice 245 (Pool Policy and Mid-Run Session Construction)** — complete (commit `be0138c`).
  `PoolClassificationPolicy.LAZY` / `STRICT` and the `--strict` flag are wired. The explain path
  must honor `--strict` (and the pipeline's `auth_policy` key) so the displayed policy matches
  what a real `sq run` would use.

### Interfaces Required

From `squadron.pipeline.classification` (all stable, no changes needed):
- `classify_pipeline(definition, resolver, pool_backend, policy) -> PipelineClassification`
- `PipelineClassification` with `.steps`, `.shape`, `.needs_persistent_session`,
  `.needs_one_shot_claude`, `.policy`
- `StepClassification` with `.step_name`, `.step_index`, `.action_type`, `.resolved_alias`,
  `.resolved_model_id`, `.profile`, `.classification`, `.rationale`, `.pool_name`
- `PipelineShape` (three values: `CLAUDE_REQUIRED_PERSISTENT`, `CLAUDE_REQUIRED_ONE_SHOT`,
  `CLAUDE_FREE`)
- `StepClass` (three values: `SDK_REQUIRED`, `NON_SDK`, `POOL_UNCERTAIN`)
- `PoolClassificationPolicy` (`LAZY`, `STRICT`)
- `ClassificationError`

From `squadron.pipeline.resolver`: `ModelResolver`
From `squadron.pipeline.loader`: `load_pipeline`, `validate_pipeline`
From `squadron.pipeline.models`: `PipelineDefinition`
From `squadron.pipeline.intelligence.pools.backend`: `DefaultPoolBackend`

## Architecture

### Component Structure

No new module. All changes are in `cli/commands/run.py`:

1. **`--explain` flag** added to the `run()` typer command signature.
2. **`_handle_explain(pipeline, model_override, param, strict, verbose)`** — new private helper that
   loads the pipeline, builds the classification resolver, calls `classify_pipeline`, and renders
   the output. Mirrors the resolver-building pattern already in `_run_pipeline_sdk`.
3. **Mutual-exclusivity guard** in the `run()` command body, placed alongside the existing guards
   for `--dry-run`, `--validate`, etc.
4. **Dispatch branch** in `run()` that calls `_handle_explain` and exits before reaching any
   execution path.

### Data Flow

```
sq run --explain <pipeline> [--model M] [--param k=v] [--strict]
  └─ run() [typer]
       ├─ mutual-exclusivity check  (explain ∧ execute_options → error)
       └─ _handle_explain(pipeline, model, param, strict)
            ├─ load_pipeline(pipeline)
            ├─ validate_pipeline(definition)   (fail fast on bad YAML)
            ├─ _assemble_params(...)            (to extract model override for resolver)
            ├─ resolve effective policy         (YAML auth_policy < --strict, same as _run_pipeline_sdk)
            ├─ DefaultPoolBackend()
            ├─ ModelResolver(cli_override, pipeline_model, pool_backend)
            ├─ classify_pipeline(definition, resolver, pool_backend, policy)
            └─ _render_explain(classification)  (Rich output, stderr for shape, stdout for table)
                 ├─ Rich Table: per-step rows
                 └─ Summary panel: shape label, policy, needs_persistent_session, needs_one_shot_claude
```

### Output Design

**Per-step table (Rich):**

| Step | Action | Alias | Model ID | Profile | Classification | Rationale |
|------|--------|-------|----------|---------|----------------|-----------|
| design | dispatch | sonnet | claude-sonnet-4-6 | sdk | sdk_required | alias 'sonnet' → profile 'sdk' (SDK) |
| review | review | minimax | minimax-01 | openrouter | non_sdk | alias 'minimax' → profile 'openrouter' (non-SDK) |
| expand | dispatch | pool:reviewers | — | — | pool_uncertain | pool mixes SDK and non-SDK aliases |

Color coding:
- `sdk_required` → yellow (caution: needs auth)
- `non_sdk` → green
- `pool_uncertain` → magenta

**Summary panel (below the table):**

```
Pipeline shape:          Claude-required (persistent)
Pool policy:             lazy (default)
Needs persistent session: yes
Needs one-shot Claude:   no
```

Shape labels map as:
- `CLAUDE_REQUIRED_PERSISTENT` → `"Claude-required (persistent)"`
- `CLAUDE_REQUIRED_ONE_SHOT` → `"Claude-required (one-shot only)"`
- `CLAUDE_FREE` → `"Claude-free"`

For pool-uncertain steps, the rationale column names the pool (`pool: reviewers`) and the pool member
aliases that caused the uncertainty are available in `step.pool_name`. The rationale field from
`StepClassification` is already populated by the classifier with a human-readable string; the
renderer uses it directly without additional logic.

### Resolver Construction in `_handle_explain`

The explain resolver is constructed identically to the `_classify_resolver` in `_run_pipeline_sdk`:

```python
pool_backend = DefaultPoolBackend()
cli_override = _extract_model_override(model, param)  # same logic as _assemble_params
_classify_resolver = ModelResolver(
    cli_override=cli_override,
    pipeline_model=definition.model,
    pool_backend=pool_backend,
)
classification = classify_pipeline(definition, _classify_resolver, pool_backend, policy=policy)
```

`cli_override` is the effective model override: `--model` takes precedence over `--param model=...`,
mirroring `_assemble_params` behavior. This ensures `sq run --explain p5 --param model=minimax`
shows the same classification that `sq run p5 --param model=minimax` would use at runtime.

The effective policy resolution is identical to `_run_pipeline_sdk`:
```python
policy = PoolClassificationPolicy.LAZY
if definition.auth_policy == PoolClassificationPolicy.STRICT:
    policy = PoolClassificationPolicy.STRICT
if strict:
    policy = PoolClassificationPolicy.STRICT
```

This duplication is intentional: the classify-only path should not call `_run_pipeline_sdk` (which
has executor side effects). A future refactor could extract `_build_classification_resolver` as a
shared helper, but that belongs in a maintenance task, not this slice.

## Technical Decisions

### Flag Name: `--explain`

The arch document (§Envisioned State, point 6) deferred the exact name to slice design with
"sq run --explain or equivalent." `--explain` is chosen because:

- It is unambiguous about intent (not "show plan", not "describe", not "classify").
- It matches the user mental model: "explain to me why this pipeline needs Claude auth."
- It is short, consistent with CLI conventions (`EXPLAIN` in SQL, `git explain` in tools, etc.).

Alternative considered: `--classify` — accurate but more technical; `--dry-classify` — too wordy;
`--auth-check` — too narrow (the output covers more than auth).

### Output Destination

The per-step table and summary panel go to stdout (for pipe-friendliness — users may want to redirect
to a file for documentation). Pipeline loading errors go to stderr. This matches the convention in
the existing `--dry-run` handler.

### No `--json` Flag in This Slice

Machine-readable output (`--json` emitting the `PipelineClassification` as JSON) is useful but not
in scope. The data structure is rich enough to support it trivially, and a `--json` flag can be
added in a maintenance task without touching this slice's design. This avoids scope creep.

### Rich vs. Plain Text

The existing CLI uses Rich throughout (`rprint`, `Panel`, `Table`). The explain output follows
suit. No new dependency; no alternative considered.

## Integration Points

### Provides to Other Slices
- **Slice 247 (Documentation):** `sq run --explain <pipeline>` is the authoritative command for the
  three pipeline shape examples in the pipeline authoring guide. The output format defined here is
  what the docs will use.
- **Slice 248 (Adversarial Test Matrix):** The test matrix may use `--explain` output as a secondary
  assertion source (what classification does the CLI report vs. what does the executor do?).

### Consumes from Other Slices
- **Slice 243:** `classify_pipeline`, all dataclasses and enums. No changes required.
- **Slice 245:** `PoolClassificationPolicy` and the policy-resolution precedence rule (YAML < CLI).

## Success Criteria

### Functional Requirements

1. `sq run --explain <pipeline>` prints a per-step table and a summary panel, then exits 0, without
   executing any step.
2. The per-step table contains exactly one row per model-dispatching step (`dispatch`, `review`,
   `summary`, `compact`) in pipeline order; non-model steps (`checkpoint`, `cf-op`, `commit`,
   `devlog`) are absent.
3. Each row shows: step name, action type, resolved alias (or `—` for pool steps), resolved model
   ID (or `—` for pool-uncertain), profile (or `—`), classification, and rationale.
4. The summary panel shows: pipeline shape label, pool policy (`lazy` or `strict`),
   `needs_persistent_session` (yes/no), `needs_one_shot_claude` (yes/no).
5. `--model` and `--param model=<alias>` override the classification exactly as they override
   execution (same resolver cascade, same cascade_candidates ordering).
6. `--strict` changes the policy shown and the `needs_persistent_session` result for pool-uncertain
   steps, consistent with how `--strict` affects `_run_pipeline_sdk`.
7. `--explain` combined with `--resume`, `--dry-run`, `--from`, `--prompt-only`, or `--validate`
   prints an error and exits 1.
8. `--explain` combined with `--model`, `--param`, `--strict`, and `--verbose` is valid.
9. Pipeline not found → clear error, exit 1.
10. Pipeline YAML invalid → validation errors printed, exit 1.
11. `ClassificationError` (misconfigured step, pool backend missing) → clear error, exit 1.

### Technical Requirements

- `ruff format` / `ruff check` / `pyright` clean.
- Full pytest suite green; no executor behavior change.
- `_handle_explain` is ≤50 lines of substantive logic; rendering is in `_render_explain` (separate
  function) to keep responsibilities clear.

### Verification Walkthrough

**Note:** `test-compact-compose` has a misconfigured `summary-2` step with no model at any cascade
level; `--explain` correctly returns a `ClassificationError` for it. Use `p6` (non-SDK summary step)
or `implement` (no model-dispatching steps) for walkthrough verification.

**Step 1 — Basic explain on a Claude-free pipeline.**

```
uv run sq run p6 --explain
```

Actual output:

```
                                  Pipeline: P6
┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Step      ┃ Action  ┃ Alias   ┃ Model ID            ┃ Profile    ┃ Classification ┃ Rationale                                 ┃
┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ summary-1 │ summary │ minimax │ minimax/minimax-01   │ openrouter │ non_sdk        │ alias 'minimax' resolves to profile       │
│           │         │         │                     │            │                │ 'openrouter' (non-SDK)                    │
└───────────┴─────────┴─────────┴─────────────────────┴────────────┴────────────────┴───────────────────────────────────────────┘
Pipeline shape:           Claude-free
Pool policy:              lazy (default)
Needs persistent session: no
Needs one-shot Claude:    no
```

Exit code: 0. No step executed (no run-state file created).

**Step 2 — Override model to a non-SDK alias.**

```
uv run sq run p6 --explain --param model=minimax
```

Expected: same output as Step 1 (already non-SDK). Pipeline shape remains `Claude-free`.

**Step 3 — Strict mode on a pipeline with a pool step.**

_(No pool-step pipeline currently exists in the built-in set. Exercised via unit tests `test_strict_flag_passed_to_classify`.)_

**Step 4 — Mutual-exclusivity rejection.**

```
uv run sq run test-compact-compose --explain --dry-run
```

Output: `Error: --explain cannot be combined with --dry-run.` Exit code: 1.

```
uv run sq run test-compact-compose --explain --resume run-123
```

Output: `Error: --explain cannot be combined with --resume.` Exit code: 1.

**Step 5 — Unknown pipeline.**

```
uv run sq run no-such-pipeline --explain
```

Output: `Error: Pipeline 'no-such-pipeline' not found.` Exit code: 1.

**Step 6 — Quality gates.**

```
uv run ruff format src/ tests/   # 300 files unchanged
uv run ruff check src/ tests/    # All checks passed
uv run pyright                   # 3 pre-existing errors (not in run.py or test_run.py)
uv run pytest                    # 1863 passed, 2 pre-existing failures in test_compact_compose_integration.py
```

## Risks

One risk worth naming: the resolver construction in `_handle_explain` is a second copy of the logic
in `_run_pipeline_sdk`. If the resolver cascade ever adds a new tier, both sites need updating. The
mitigation is a shared `_build_classification_resolver` helper. This is deferred intentionally (YAGNI
until a third call site appears) but noted here so the next engineer who touches this doesn't
duplicate further.
