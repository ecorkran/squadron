---
docType: tasks
slice: per-action-model-override-convention
project: squadron
lld: user/slices/167-slice.per-action-model-override-convention.md
dependencies: []
projectState: v0.4.0 released on main at 61c0c7f. Working tree clean. Slice 181 (pool resolver integration) complete; pools work through the ModelResolver cascade. ReviewAction reads only params["model"] for its own model, so there is no way to override the review model per-run without adding action-specific CLI flags. This slice establishes a convention — {purpose}_model via --param — as the general answer.
dateCreated: 20260414
dateUpdated: 20260414
status: not_started
---

## Context Summary

- Working on slice 167: Per-Action Model Override Convention.
- Goal: establish and document a convention for action-specific model
  overrides via `--param {purpose}_model=X`, apply it to
  `ReviewAction`, and avoid the alternative of special-casing a new
  CLI flag per action type.
- Convention: each action that resolves its own model checks
  `params["{purpose}_model"]` first, falling back to `params["model"]`.
  The slot name matches the pipeline YAML key.
- `--model` remains the one privileged CLI flag and feeds the
  5-level `ModelResolver` cascade unchanged.
- Override values flow through `context.resolver.resolve()` →
  `resolve_model_alias()` so aliases, concrete model IDs, and
  `pool:<name>` all work uniformly.
- First adopter: `ReviewAction` at
  `src/squadron/pipeline/actions/review.py` (lines 80–88). No other
  actions are in scope for this slice.
- Before coding, verify whether the pipeline loader already maps
  YAML `review.model: X` into `params["review_model"]`. If not,
  extend the loader; otherwise, only the action read path changes.

---

## Tasks

### Phase 6: Implementation

- [ ] **T1 — Verify loader behavior for nested action-level model config**
    - [ ] Trace how `review.model: X` in pipeline YAML currently lands in
          `context.params` (read `src/squadron/pipeline/loader.py` and
          any step/action expansion in `src/squadron/pipeline/steps/`).
    - [ ] Determine whether the loader already exposes it as
          `params["review_model"]`, as `params["model"]` scoped to the
          review action, or somewhere else.
    - [ ] Record the finding in this tasks file under "Implementation
          Notes" so T2 can proceed with the right assumption.

- [ ] **T2 — Update `ReviewAction` to honor the convention**
    - [ ] In `src/squadron/pipeline/actions/review.py`, change the
          model read in `_review()` (lines 80–88) to prefer
          `params["review_model"]` over `params["model"]`.
    - [ ] Add a one-line comment pointing readers to the authoring
          guide section (name the convention: "per-action model
          override").
    - [ ] If T1 showed the loader does not expose `review_model`,
          extend the loader here to flatten `review.model` into
          `params["review_model"]`.

- [ ] **T3 — Tests for ReviewAction override**
    - [ ] `--param review_model=X` overrides a pipeline-wide `--model Y`
          for the review action only (dispatch still uses Y).
    - [ ] Fallback: with no `review_model`, the review action uses
          `params["model"]` (existing behavior preserved).
    - [ ] Alias: `--param review_model=<SDK-alias>` resolves to the SDK
          profile.
    - [ ] Alias: `--param review_model=<openrouter-alias>` resolves to
          the OpenRouter profile.
    - [ ] Pool: `--param review_model=pool:<name>` resolves via the
          pool backend (use the same fixtures slice 181 introduced).

- [ ] **T4 — Document the convention in the authoring guide**
    - [ ] Add a "Per-Action Model Overrides" section to the pipeline
          authoring guide (locate it via `guide.ai-project.process` or
          the existing pipeline docs in
          `project-documents/ai-project-guide/` /
          `src/squadron/data/docs/`).
    - [ ] State the convention: action authors check
          `params["{purpose}_model"]` before falling back to
          `params["model"]`.
    - [ ] Show the `ReviewAction` reference snippet.
    - [ ] Note that aliases and pools work without additional code in
          the action because resolution flows through
          `context.resolver.resolve()`.
    - [ ] List slots currently in use (seed: `review_model`).

- [ ] **T5 — Smoke test end-to-end via CLI**
    - [ ] `sq run p4 <target> --model opus --param review_model=sonnet`
          succeeds; check logs/state confirm the two models resolved
          as expected.
    - [ ] `sq run p4 <target> --param review_model=pool:reviewers`
          selects the review model via pool resolution.
    - [ ] Record the commands and observed model IDs in
          "Implementation Notes."

### Phase 7: Ship

- [ ] **T6 — Format, type-check, test**
    - [ ] `ruff format` the changed files.
    - [ ] `pyright` clean on changed files.
    - [ ] `pytest` full suite green.

- [ ] **T7 — Commit and update changelog**
    - [ ] Semantic commit: `feat: per-action model override via --param`.
    - [ ] Append a bullet to `CHANGELOG.md` under `[Unreleased]`.
    - [ ] Append a note to `DEVLOG.md`.

---

## Implementation Notes

_(Populate during implementation — T1 finding, T5 smoke-test commands,
and any loader changes made.)_

---

## Open Questions

- [ ] If the loader does not currently flatten `review.model` into
      `params["review_model"]`, is there a reason to keep it nested
      (e.g., avoiding key collisions across nested actions)? If yes,
      the convention may need a namespacing rule —
      `{step_name}.{purpose}_model` or similar. Decide in T1.
