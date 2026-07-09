---
docType: slice-design
slice: pipeline-phase-step-correctness
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [149]
interfaces: []
dateCreated: 20260709
dateUpdated: 20260709
status: not_started
---

# Slice Design: Pipeline Phase-Step Correctness

## Overview

Three independent pipeline/CLI correctness bugs, all surfaced during slice 303
planning, bundled into one maintenance slice because each is small and all three
sit on the phase-step / review-command correctness path. Each part fails the
same way in spirit — a silent-success path where an operation *appears* to
succeed but produced no valid result — and each fix installs an explicit
fail-fast guard where one is currently missing.

- **Part A (issue #15, Medium)** — a phase-step `dispatch` that is supposed to
  write an artifact returns `success=True` even when no file was written.
- **Part B (issue #16, Low)** — review frontmatter hardcodes `project: squadron`
  regardless of the actual project.
- **Part C (issue #17, Medium)** — `sq review code` with a missing or malformed
  slice index silently runs an unscoped, hallucination-prone review instead of
  erroring.

## Value

Developer-facing reliability. All three bugs share a failure signature that is
worse than a crash: a plausible-but-wrong result with no error signal. Part A
lets a stalled planning agent masquerade as a completed phase; the failure
surfaces one step later with a misleading message pointing at the wrong step.
Part B mislabels every review file run outside squadron, corrupting provenance
for any downstream tooling that keys on the `project:` field. Part C emits a
fully-formed, confident code review citing files that do not exist in the target
repo. Fixing all three converts three silent-success paths into explicit,
observable failures — the "fail fast, never silent-fallback" principle applied
three times.

## Technical Scope

**Included:**
- Part A: an artifact post-condition for phase-step dispatch, plus a
  non-silent outcome when an unattended agent ends its turn without writing the
  expected file.
- Part B: a `name` field on `ProjectInfo`, threaded through `SliceInfo` and
  `resolve_slice_info`, replacing the hardcoded `project: squadron` literal in
  `format_review_markdown`.
- Part C: a scope guard in `review_code` requiring at least one of a *valid*
  slice number, `--diff`, or `--files`; covering both the missing-argument and
  malformed-non-digit-argument cases.

**Excluded:**
- Any redesign of the generic `DispatchAction` success contract for non-phase
  dispatch (a bare `dispatch` step with no expected artifact stays as-is).
- Per-iteration commit mechanics in loop bodies (tracked separately as 300
  slice-plan Future Work item 5).
- The broader "review misfiles findings against a valid scope" bug (issue #14) —
  distinct from Part C, which is about accepting an *invalid* scope in the first
  place.

## Dependencies

### Prerequisites
- **[149]** — the pipeline phase-step / review-action infrastructure that all
  three fixes modify. No new external dependencies.

### Interfaces Required
- Part A reads the resolved phase name and the project's document layout to
  compute the expected artifact path. This information is available at expansion
  time (`PhaseStepType` knows its phase name) and at execution time (the
  `ActionContext`). No new data contract with Context-Forge is required.
- Part B relies on `cf get --json` returning a `name` field. **Verified**: the
  response includes `"name": "squadron"` alongside `projectPath`, `fileArch`,
  etc. This is a real source, not an assumed one.

## Architecture

### Part A — Dispatch artifact post-condition

**Current behavior.** `PhaseStepType.expand()`
([phase.py:96](../../../src/squadron/pipeline/steps/phase.py#L96)) emits a fixed
action list:

```
cf-op(set_phase) → cf-op(set_slice) → cf-op(build_context)
  → dispatch → [review → checkpoint] → commit
```

The `dispatch` action is emitted as a bare `("dispatch", {"model": model})` with
no notion of an expected output. `DispatchAction.execute`
([dispatch.py:105](../../../src/squadron/pipeline/actions/dispatch.py#L105))
returns `ActionResult(success=True)` on both success paths
(`_dispatch_via_session` at
[dispatch.py:198](../../../src/squadron/pipeline/actions/dispatch.py#L198),
`_dispatch_via_agent` at
[dispatch.py:284](../../../src/squadron/pipeline/actions/dispatch.py#L284))
whenever the agent turn completes without raising. Its only failure paths are
model-resolution errors, the SDK-session guard, and unexpected exceptions
(caught at [dispatch.py:114-128](../../../src/squadron/pipeline/actions/dispatch.py#L114)),
plus a text-scan for CLI-formatted errors in the response
(`_check_cli_error`). There is **no check that the expected file was written.**

**Key design decision — where does the post-condition live?**

The phase→artifact mapping (a `design` phase writes a design file, a `tasks`
phase writes a task file) is *conceptually* known but is **not currently
materialized anywhere**. Two candidate homes:

1. **Generic `DispatchAction`** — rejected. Generic dispatch has no notion of an
   expected artifact and must stay usable for bare `dispatch` steps that write
   nothing. Pushing artifact-awareness into it would violate SRP and break the
   no-artifact case.
2. **`PhaseStepType`** — chosen. The phase step *is* the component that knows
   "this phase produces an artifact of this type." The post-condition belongs at
   the phase-step level, not in generic dispatch.

**Approach.** `PhaseStepType` resolves the expected artifact path for its phase
(from the phase name + the project's document layout, the same information CF
exposes via `fileSlice`/`fileTasks`/etc.) and the pipeline verifies, after the
dispatch action completes, that the file exists and was written/modified by this
run. The expected-path resolution is a single mapping defined once (phase →
artifact-kind), consistent with the "define comparison values once" rule — not a
scattered set of string checks. On a missing artifact, the phase step produces a
**failed** outcome with a clear message ("phase `tasks` completed dispatch but
no task file was written for slice N"), which the existing checkpoint/on-fail
machinery then routes — rather than the current silent `success=True`.

**Second sub-problem — the unattended-question path.** An agent that ends its
turn by asking "how would you like me to proceed?" completes its dispatch
without raising and without writing a file. Under the post-condition above this
now registers as a failure (no artifact) rather than a success. The design routes
this to the existing checkpoint/escalation mechanism so an unattended run stops
observably instead of proceeding to a downstream step that then fails with a
misleading message. (The concrete "detect a trailing question" heuristic is a
task-level decision; the *contract* this design fixes is: no-artifact ⇒ not
success.)

### Part B — Review frontmatter project name

**Current behavior.** `format_review_markdown`
([persistence.py:119](../../../src/squadron/review/persistence.py#L119)) emits
the string literal `"project: squadron"` on every review file, in every project.
Directly adjacent, `slice_name` and `slice_index` (lines 119-120) *are* derived
from `slice_info` with an `"unknown"` / `0` fallback — the literal is an
inconsistency in an otherwise data-driven block.

**Data flow of the fix.**

```
cf get --json  ──►  ContextForgeClient.get_project()  ──►  ProjectInfo.name (NEW)
                                                                    │
                                          resolve_slice_info()  ◄───┘
                                          (already calls get_project()
                                           at persistence.py:66)
                                                    │
                                            SliceInfo["project"] (NEW)
                                                    │
                                      format_review_markdown()
                                       emits  f"project: {slice_info['project']}"
                                       fallback  "unknown"  (never "squadron")
```

Both review write paths converge on `format_review_markdown` — the pipeline path
via `save_review_result`
([actions/review.py:193](../../../src/squadron/pipeline/actions/review.py#L193))
and the CLI path via
[persistence.py:268](../../../src/squadron/review/persistence.py#L268). A
single-point fix in `format_review_markdown` therefore covers both paths by
construction, satisfying interface-parity without duplicated logic.

### Part C — Review-code scope guard

**Current behavior.** `review_code`
([review.py:604-607](../../../src/squadron/cli/commands/review.py#L604))
declares `slice_number: str | None = typer.Argument(None, ...)` — fully optional.
At [review.py:641](../../../src/squadron/cli/commands/review.py#L641) the guard
is `if slice_number is not None and slice_number.isdigit()`, so **both** a
missing argument *and* a malformed non-digit argument silently skip scope
resolution. `_run_review_command`'s required-inputs check
([review.py:302-308](../../../src/squadron/cli/commands/review.py#L302)) is a
no-op because the `code` template declares `required_inputs: []`. With no diff
and no files, `code_review_prompt`
([builders/code.py:40-44](../../../src/squadron/review/builders/code.py#L40))
substitutes an unconstrained "survey the project structure" instruction, which is
still sent to a live model.

**The pattern to mirror already exists.** `review_slice`
([review.py:408-410](../../../src/squadron/cli/commands/review.py#L408)) and
`review_tasks` (review.py:551-553) both hard-guard: `if not against: raise
typer.Exit(code=1)`. `review_code` has no equivalent guard on its own
scope-defining inputs.

**Approach.** After scope resolution, add a guard: if none of
{resolved `slice_info`, `diff`, `files`} is present, `rprint` a clear error and
`raise typer.Exit(code=1)`. Because the malformed case falls through the
`isdigit()` check to leave `slice_info is None`, this single post-resolution
guard covers both the missing and malformed cases. Optionally distinguish the
malformed case with a more specific message ("slice number 'abc' is not
numeric") for a better error, but the load-bearing behavior is: no scope ⇒ exit
non-zero, never run.

## Technical Decisions

### Patterns and Conventions
- **Fail fast, never silent-fallback** (all three parts) — replace a
  silent-success or silent-degrade path with an explicit error.
- **Define the mapping once** (Part A) — the phase→artifact-kind mapping is a
  single lookup, not scattered string comparisons.
- **Single-point fix for interface parity** (Part B) — fix at the shared
  `format_review_markdown` seam so CLI and pipeline paths get the fix together.
- **Mirror the existing guard** (Part C) — reuse the `review_slice`/`review_tasks`
  guard shape rather than inventing a new validation style.

## Implementation Details

### Part A files
- [steps/phase.py](../../../src/squadron/pipeline/steps/phase.py) — resolve the
  expected artifact path for the phase; attach/verify as a post-condition.
- [actions/dispatch.py](../../../src/squadron/pipeline/actions/dispatch.py) —
  unchanged contract for generic dispatch; the post-condition lives above it.
- Checkpoint/on-fail routing — reuse existing machinery for the no-artifact
  outcome.

### Part B files
- [integrations/context_forge.py](../../../src/squadron/integrations/context_forge.py#L52)
  — add `name: str` to `ProjectInfo`; populate from `data.get("name")` in
  `get_project` (context_forge.py:165).
- [review/persistence.py](../../../src/squadron/review/persistence.py) — add
  `project` to the `SliceInfo` TypedDict (line 20); set it from `project.name`
  in `resolve_slice_info` (line 66 already fetches `project`); replace the
  `"project: squadron"` literal (line 119) with `slice_info["project"]` and an
  `"unknown"` fallback.

### Part C files
- [cli/commands/review.py](../../../src/squadron/cli/commands/review.py) — add a
  scope guard in `review_code` after line 645, mirroring review.py:408-410.

## Success Criteria

### Functional Requirements
- **Part A:** A phase-step dispatch that completes without writing the expected
  artifact yields a failed step outcome (not `success=True`), with a message that
  names the phase, the expected artifact, and the slice. An unattended agent that
  ends its turn asking a question routes to checkpoint/escalation rather than
  completing silently.
- **Part B:** A review file's frontmatter carries the *actual* project name
  (`context-forge`, `squadron`, …) sourced from `cf get --json`; a resolution
  failure yields `project: unknown`, never `project: squadron`. Both CLI and
  pipeline review paths produce identical `project:` values for the same run.
- **Part C:** `sq review code` with no slice number and no `--diff`/`--files`
  exits non-zero with a clear message and does **not** call the model. The same
  holds for a malformed non-numeric slice argument.

### Technical Requirements
- No new silent-fallback values introduced; every new branch either succeeds
  with a real value or fails observably (log at WARNING+ / non-zero exit).
- Part B fix is single-point (`format_review_markdown`); no duplicated
  project-resolution logic across the two write paths.
- Tests use real-world shapes: Part B's test fixture uses an actual `cf get
  --json` response shape (with a `name` field); Part C's test drives the CLI with
  a missing and a malformed argument.

### Verification Walkthrough

**Part C (most directly observable):**
```
# Missing slice index — must exit non-zero, must NOT produce a review
sq review code -v --model glm51
# expect: error "provide a slice number, --diff, or --files"; exit code 1;
#         no model call, no fabricated findings.

# Malformed (non-digit) slice index — same behavior
sq review code abc -v
# expect: error; exit 1.

# Valid scope still works
sq review code 909 -v
# expect: a real, scoped review of slice 909's diff.
```

**Part B:**
```
# Run a review from a NON-squadron project (e.g. context-forge) and inspect
# the saved review file's frontmatter.
cd /path/to/context-forge && sq review code 910 -v
grep '^project:' project-documents/user/reviews/<latest>.md
# expect: project: context-forge   (NOT project: squadron)
```
Confirm the pipeline path agrees: run a pipeline whose phase step includes a
review, and grep the emitted review file's `project:` field — it must match the
CLI value for the same project.

**Part A:**
```
# Reproduce the original failure, then confirm the new guard fires.
# Original repro: a Phase-5 dispatch agent that asks a question instead of
# writing the task file (run-20260707-p5a-73bbffc0.json).
sq run p5 909      # or a crafted pipeline whose dispatch writes no artifact
# expect (after fix): the phase step fails at the DISPATCH step with a message
#         naming the missing task file — NOT a success that fails one step later
#         at the review action with "prior step may not have created the
#         expected file."
```

## Risk Assessment

### Technical Risks
- **Part A behavior change.** Making "no artifact" a failure is a deliberate
  behavior change: pipelines that previously limped past a no-op dispatch will
  now stop at it. This is the intended fix, but any pipeline relying on a
  dispatch that legitimately writes nothing must use a bare `dispatch` step, not
  a phase step — the post-condition is scoped to phase steps only, which
  mitigates this.

### Mitigation Strategies
- Scope Part A's post-condition to `PhaseStepType` (phases that *do* produce
  artifacts), leaving generic `dispatch` untouched.

## Implementation Notes

### Development Approach
Suggested order — cheapest and most isolated first:
1. **Part C** — self-contained CLI guard, mirrors an existing pattern, easy to
   test.
2. **Part B** — small data-threading change through a verified source; single
   test fixture with the real `cf get --json` shape.
3. **Part A** — the genuine design work (post-condition home + unattended-question
   routing); do last so the two easy wins land regardless.

Each part is independently committable and independently testable; a stall on
Part A does not block Parts B and C.
