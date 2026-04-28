---
docType: slice-plan
parent: 900-arch.maintenance-and-refactoring.md
project: squadron
dateCreated: 20260325
dateUpdated: 20260427
status: in-progress
---

# Slice Plan: Maintenance and Refactoring

## Parent Document
`900-arch.maintenance-and-refactoring.md` — Architecture: Maintenance and Refactoring

## Guidelines
- Slices are added as maintenance needs are identified
- No strict implementation order — pick up based on priority
- Each slice should be small, focused, and independently deliverable

---

## Maintenance Slices

1. [x] **(901) Pipeline Code-Review Diff Injection and UNKNOWN-Fails-Closed**
Fixes [issue #11](https://github.com/ecorkran/squadron/issues/11): pipeline
code reviews silently produce UNKNOWN/no-findings because the diff is never
injected into the review prompt. Three coordinated changes:

1. Forward `slice` explicitly from phase / review step `expand()` into the
   review action config (deterministic key, not merged-params side channel).
2. Replace per-template `match` in `_resolve_slice_inputs` with a declarative
   template-input registry, so any template that declares it consumes a
   diff gets one resolved automatically.
3. Treat verdict `UNKNOWN` as `FAIL` for `on-fail` checkpoint triggers (fail
   closed) so dead reviewers and parser misses can't silently wave through.

**Status:** complete · **Risk:** Low · **Effort:** 2/5 · **Dependencies:** [149]

2. [x] **(902) Pipeline Verbosity Passthrough (`-v`/`-vv`) + Step-Type Registration Bootstrap**
Fixes [issue #9](https://github.com/ecorkran/squadron/issues/9): pipeline review
commands hard-code `-v`, and `/sq:run` swallows trailing flags into the target
string. Two coordinated changes:

1. Thread the existing `sq run -v/-vv` count into `PromptRenderer` and replace
   the hard-coded `cmd_parts.append("-v")` in `_render_review`
   ([prompt_renderer.py:174](src/squadron/pipeline/prompt_renderer.py#L174))
   with conditional emission based on runtime verbosity. Default 0 (no flag);
   `-v` and `-vv` opt in. This is a deliberate behavior change — current runs
   always emit `-v` to sub-reviews; new default is silent.
2. Update `/sq:run` slash command to peel trailing `-v`/`-vv`/`--verbose`
   tokens off `$ARGUMENTS` before splitting pipeline/target, and pass them
   through to `sq run`.

**Slice design:** `user/slices/902-slice.pipeline-verbosity-passthrough-v-vv.md`
Branch: `902-pipeline-verbosity-passthrough`, close issue on merge.

**Status:** complete · **Risk:** Low · **Effort:** 1/5 · **Dependencies:** none

**Follow-up (20260427):** extract `bootstrap_step_types()` into
[steps/__init__.py](src/squadron/pipeline/steps/__init__.py) to eliminate
triple-registration across executor / loader / prompt_renderer, and close the
prompt_renderer gap (missing `loop`/`collection`/`fan_out`) as a one-line
consequence. Tracked as T14–T17 in the 902 task file.

3. [ ] **(904) Review-Finding Location Required**
Fixes [issue #10](https://github.com/ecorkran/squadron/issues/10): review
findings inconsistently cite a code location, and PASS findings almost never
do. Load-bearing for ensemble review (slices 182, 189) where merged-finding
deduplication keys on location. Four coordinated changes:

1. Update all four review-template prompts ([code.yaml](src/squadron/data/templates/code.yaml),
   [slice.yaml](src/squadron/data/templates/slice.yaml),
   [arch.yaml](src/squadron/data/templates/arch.yaml),
   [tasks.yaml](src/squadron/data/templates/tasks.yaml)) to require
   `location:` on every finding (PASS included), with `unverified` as
   the explicit "I don't know" token.
2. Soft-fail in [parsers.py](src/squadron/review/parsers.py): missing
   `location:` becomes `unverified` with a WARNING log; existing `-`,
   `global`, and empty values are normalized to `unverified`.
3. Diff-membership WARNING for code reviews (cited path must appear in
   the diff); WARNING-only.
4. Path-existence WARNING for all template types (cheap `Path.exists()`
   per finding); primary defense against hallucinated filenames in
   non-code reviews.

`task_ref:` field deferred to future slice (likely under 189 ensemble
review).

**Slice design:** `user/slices/904-slice.review-finding-location-required.md`
Branch: `904-review-finding-location-required`, close issue on merge.

**Status:** design complete · **Risk:** Low–Medium · **Effort:** 2.5/5 · **Dependencies:** none


