---
docType: slice-design
slice: per-action-model-override-convention
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: []
interfaces: []
dateCreated: 20260414
dateUpdated: 20260414
status: not_started
---

# Slice Design: Per-Action Model Override Convention

## Overview

Today `sq run` exposes one privileged flag for model selection —
`--model` — which feeds the 5-level cascade inside `ModelResolver` and
sets the pipeline-wide default. Every other pipeline parameter goes
through `--param key=value`, which writes into `context.params` and is
read by whatever action cares about it.

That split is correct. The problem is that action implementations do
not follow a consistent rule for reading *action-specific* model
overrides out of `context.params`. `ReviewAction` reads only
`params["model"]`, so there is no way — short of adding a special-case
CLI flag for every action type — to say "use opus for dispatch but
sonnet for review" on a single `sq run` invocation.

The fix is a convention, not new machinery: each action that resolves
its own model checks `params["{purpose}_model"]` first, falling back
to `params["model"]`. The slot name matches the pipeline YAML key.
Anything the YAML can set, `--param` can override, with the same key.

This slice establishes and documents the convention, applies it to
`ReviewAction` (the first action that needs it), and seeds a test
pattern future action authors can copy.

## Motivation

- **Scales to N actions, zero new CLI flags.** `--review-model`,
  `--summary-model`, `--critique-model`, etc. would each be a new
  special case in `run.py`. `--param review_model=X` covers all of
  them uniformly.
- **Preserves the YAML/CLI invariant.** Pipeline YAML already supports
  per-action model config (e.g., `review: model: opus`). Today that
  value cannot be overridden from the CLI. After this slice, the YAML
  key and the `--param` key are the same string, so override is
  mechanical.
- **Works with aliases and pools identically.** The override value
  flows through `resolve_model_alias()` and the pool resolver exactly
  like `--model` does — `--param review_model=sonnet` (SDK),
  `--param review_model=minimax-m3` (OpenRouter), and
  `--param review_model=pool:reviewers` (pool) all work.
- **Single documented pattern for action authors.** Right now there is
  no guidance on how actions should read their own model override.
  New action types would diverge. A documented convention prevents
  that.

## User-Provided Concept

The invariant: pipeline YAML and `--param` are two sides of the same
slot. Anything YAML can set, `--param` must override using the exact
same key, and action implementations must read from that key
consistently.

`--model` stays special — it is the one flag every pipeline needs, and
it feeds `ModelResolver`'s cascade directly. Everything else —
including `review_model`, `summary_model`, and any future
`{purpose}_model` — flows through `--param`.

The anti-pattern to avoid: a generic "auto-resolve any `*_model` param
through the cascade" system that introspects param names for magic
suffixes or requires the resolver to enumerate action types. Only the
action knows its own semantics; the action is the right place to
check its own override key.

## Scope

### In Scope

- Document the convention in the pipeline authoring guide: action
  authors check `params["{purpose}_model"]` before falling back to
  `params["model"]`.
- Apply the convention to `ReviewAction` using the key `review_model`.
- Ensure the override value flows through `context.resolver.resolve()`
  so alias resolution and pool handling work uniformly.
- Tests: `--param review_model=X` overrides a pipeline-wide
  `--model Y` for the review action only.
- Tests: alias resolution works (sonnet → SDK; minimax-m3 →
  OpenRouter).
- Tests: pool resolution works (`pool:reviewers`).

### Out of Scope

- Applying the convention to `SummaryAction` or any other action —
  those follow in their own slices when needed.
- Adding `--review-model` (or any other action-specific) CLI flag —
  explicitly rejected in favor of `--param`.
- Changing `ModelResolver`'s cascade structure.
- Code review usability work (bulk review, directory-level review,
  review sweep pipelines) — separate follow-up slice.

## Design

### The Convention

An action that supports a per-action model override reads the override
from `context.params` using the key `{purpose}_model`, where
`{purpose}` matches the pipeline YAML field name for that action. If
the key is absent, the action falls back to `params["model"]`.

The override value is a plain string — model alias, concrete model ID,
or `pool:<name>`. It is passed to `context.resolver.resolve()` as the
`action_model` argument, so the 5-level cascade, alias resolution, and
pool handling apply uniformly.

### ReviewAction Change

Current (`src/squadron/pipeline/actions/review.py`, lines 80–88):

```python
action_model = (
    str(context.params["model"]) if "model" in context.params else None
)
step_model = (
    str(context.params["step_model"])
    if "step_model" in context.params
    else None
)
model_id, alias_profile = context.resolver.resolve(action_model, step_model)
```

After:

```python
action_model = (
    str(context.params["review_model"])
    if "review_model" in context.params
    else str(context.params["model"])
    if "model" in context.params
    else None
)
step_model = (
    str(context.params["step_model"])
    if "step_model" in context.params
    else None
)
model_id, alias_profile = context.resolver.resolve(action_model, step_model)
```

The review action now prefers `review_model` over `model` when
resolving its own model. If the pipeline YAML sets `review.model: X`,
the loader should continue to map that into `params["review_model"]`
(verify during implementation — may already be the case, or may
require a loader tweak).

### CLI Surface

No CLI changes. `--model` keeps its current behavior (feeds
`ModelResolver._cli_override`, stored in `params["model"]`). Users
override a specific action's model via `--param`:

```
sq run p4 123 --model opus --param review_model=sonnet
sq run p4 123 --param review_model=pool:reviewers
sq run p4 123 --param review_model=minimax-m3
```

### Authoring Guide Addition

Add a section to the pipeline authoring guide titled "Per-Action Model
Overrides" that:

- States the convention (`{purpose}_model` key).
- Shows the `ReviewAction` reference implementation.
- Notes that the override flows through the resolver — so aliases and
  pools work without additional code in the action.
- Lists the slots in use today (start: `review_model`; expand as
  adopted).

## Risks & Mitigations

- **Loader may not already expose `review.model` as
  `params["review_model"]`.** Verify during implementation; if not,
  extend the pipeline loader to flatten nested action-level model
  config into the conventional param key. Tests cover both paths.
- **Convention drift.** Future action authors may invent new slot
  names. Mitigated by the authoring-guide section and by a short
  comment at the top of `ReviewAction` pointing to the guide.

## Success Criteria

- `sq run p4 123 --model opus --param review_model=sonnet`
  dispatches with opus and reviews with sonnet.
- `--param review_model=pool:reviewers` selects the review model via
  pool resolution.
- `--param review_model=<openrouter-alias>` routes review through the
  OpenRouter profile.
- Pipeline authoring guide documents the convention with the
  `ReviewAction` reference implementation.
- All existing review tests continue to pass; new tests cover the
  override, fallback, alias, and pool cases.
