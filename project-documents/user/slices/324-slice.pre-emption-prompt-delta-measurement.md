---
docType: slice-design
slice: pre-emption-prompt-delta-measurement
project: squadron
parent: ../architecture/320-slices.judge-calibration-quality-metrology.md
dependencies: [323, 140]
interfaces: []
dateCreated: 20260728
dateUpdated: 20260728
status: not-started
---

# Slice Design: Pre-Emption Prompt & Delta Measurement

See [`320-reference...md`](../architecture/320-reference.judge-calibration-quality-metrology.md) for this initiative's glossary and current-state index.

## Overview

323 shipped the audit oracle's data half: a cross-project tech-debt-audit baseline with a measured, per-project noise floor. This slice is the audit oracle's **intervention** — the only slice in the initiative that closes the loop from measurement back into what dispatch actually does.

Two things ship together because neither is credible alone:

1. **The pre-emption fragment.** A short, static text block generated from a project's persisted baseline — "avoid these issue classes, which the audit found repeatedly" — that reaches dispatch prompts. Generated once from the store, then **frozen as static text**; dispatch never queries the metrology store at runtime.
2. **The before/after delta report.** Re-run the audit, compare the new finding count to the baseline, and report the difference **relative to the measured noise floor** from 323 — not in isolation. 323's own walkthrough measured spreads of 35-111% of the mean on unchanged code; a delta report that ignores this reads a noise draw as an effect.

Both existed already as slice-plan success criteria. What this document adds is the concrete mechanism for (1), which the slice plan explicitly left open ("Pre-emption fragment format and regeneration cadence (324, slice-design)") and which turned out to be the substantial design question: **no static-prompt-injection point exists anywhere in dispatch today.**

## Value

Operator value — proves the metrology can detect an intervention's effect, not just accumulate numbers. This is the initiative's proof-of-value that measurement closes a loop on code quality, and the last of the five anticipated slices.

## Technical Scope

**Included:**
- A **fragment generator** (`squadron.metrology.preemption`): reads a project's `ProjectBaseline` (323's `baseline_report`), selects issue classes worth front-loading, and renders a short static text block.
- A **new optional dispatch param** (`pre_emption_fragment`) threaded through `DispatchAction._resolve_prompt`, `PhaseStepType.expand()`, and `DispatchStepType.expand()` — opt-in, absent by default, prepended the same way `_apply_override` already prepends checkpoint text.
- A **regeneration command** (`sq metrology preempt generate <project-path>`) that reads the current baseline and writes the fragment to a file on disk. Regeneration is an explicit, operator-triggered step — not automatic, not on a schedule.
- A **delta command** (`sq metrology audit delta <project-path>`) that re-runs the audit harness (323), compares the new run's counts to the stored baseline's counts, and reports the difference per category against the stored `FloorStat`.
- Two new config keys (fragment output path, and whether pre-emption is active for a pipeline) registered in `config/keys.py`.

**Explicitly excluded:**
- **Dispatch querying the metrology store at runtime** — the architecture forbids this (140→320 dependency inversion, a new runtime failure mode). The fragment is generated once, written to a file, and read as plain static text thereafter; the store is touched only by the generation command.
- **Automatic regeneration on a schedule or on every audit run** — regeneration is a defined, deliberate step (Decision 3), not continuous. 323's own baseline is not continuously refreshed either.
- **Touching `cf_op.py` or context-forge's own prompt assembly.** Verified: `cf_op.py` calls `cf build --json` and passes its `"context"` field through unmodified (`cf_op.py:95-111`); the fragment is concatenated entirely downstream of that, inside squadron's own `dispatch.py`. Context-forge is neither read from nor written to.
- **Fixing the pre-existing empty-system-prompt bug** (filed separately as [#40](https://github.com/ecorkran/squadron/issues/40)) — orthogonal to this slice; every current one-shot dispatch sends `--system-prompt ""` regardless of whether 324 ships. Not fixed here.
- **A general "prompt fragment" or "prompt chaining" framework.** Only the one new param this slice needs is added; no speculative extensibility for other future fragment types.
- **Statistical significance testing beyond floor comparison.** "Below the floor" / "at or above the floor" is the entire signal; no p-values, no confidence intervals — 323's own n=3 floors do not support that precision.

## Dependencies

### Prerequisites
- **323 (tech-debt-audit baseline harness)** — `status: complete`. Provides `run_audit`, `baseline_report`, `AuditRun`, `AuditNoiseFloor`, `ProjectBaseline`, `BaselineCell`, `MetrologyStore.list_audit_runs`/`list_noise_floors`.
- **140 (pipeline foundation)** — the dispatch action/step surface this slice adds a param to.

### Interfaces Required
- `squadron.metrology.audit_report.baseline_report(store, project_filter=...)` → `BaselineReport` — the source of both the fragment and the delta comparison.
- `squadron.metrology.audit.run_audit(...)` — re-run for the delta's "after" measurement.
- `squadron.pipeline.actions.dispatch.DispatchAction._resolve_prompt` / `_apply_override` — the exact concatenation point (see Decision 1).
- `squadron.pipeline.steps.dispatch.DispatchStepType.expand` and `squadron.pipeline.steps.phase.PhaseStepType.expand` — both need the new optional key threaded through, following the existing `if "prompt" in cfg: ...` idiom.
- `squadron.config.keys.CONFIG_KEYS` — new keys registered here or `get_config` raises `KeyError`.

### State of the ground truth (facts verified against the code)

Four facts shaped this design and must not be re-guessed at task time.

1. **No static-prompt-injection point exists anywhere in dispatch today.** Searched for "prompt chaining," "prompt fragment," "pre-prompt injection," "addendum," "preamble" — no hits outside this initiative's own architecture prose. `system_prompt` exists as an `AgentConfig` field but is never populated by any step-type `expand()` in the current codebase — it is dead wiring, always resolving to `""` (see Excluded, and issue #40).

2. **The production design/tasks/implement prompt is assembled entirely by an external process.** `cf-op(build_context)` (`cf_op.py:95-111`) runs `cf build --json` as a subprocess and passes its `"context"` field through byte-for-byte as `outputs["stdout"]`. Squadron's own code applies exactly one transformation after that: `DispatchAction._apply_override` (`dispatch.py:291-302`), which conditionally prepends a delimited block. This is the only point, in any current code path, where squadron concatenates additional text onto an assembled prompt without touching context-forge.

3. **The concatenation pattern already exists and is safe to extend.** `_apply_override` prepends `"--- Instructions from checkpoint resolution ---\n{text}\n--- End instructions ---\n\n"` ahead of the resolved prompt, gated on `context.params["override_instructions"]` being a non-empty string (`dispatch.py:292-302`), called from the tail of `_resolve_prompt` (`dispatch.py:253`). That param is populated at runtime by the interactive checkpoint handler — a different data source than this slice's static fragment, but the identical concatenation shape (delimited prefix + prompt).

4. **`StepConfig.config` and `ActionContext.params` are permissive plain dicts, not TypedDict/Pydantic** (`pipeline/models.py:46-71`) — an unknown key is never rejected. The actual constraint is the existing `expand()` tests' exact-dict-equality assertions (`tests/pipeline/steps/test_phase.py`, `tests/pipeline/steps/test_dispatch_step.py`): a new key is safe only if it is inserted **conditionally**, when explicitly present in step config — matching the `if "prompt" in cfg: action_config["prompt"] = cfg["prompt"]` idiom already used for every other field (`steps/dispatch.py:53-56`).

## Technical Decisions

### 1. Injection point: prepend at `_resolve_prompt`, gated by a new opt-in param, downstream of `cf build`

**Decision:** Add `pre_emption_fragment: str | None` to `context.params`. `_resolve_prompt` prepends it — using the same delimited-block shape `_apply_override` already establishes — after `_apply_override` runs, so a checkpoint override (if also present) stays the innermost, most urgent instruction and the fragment sits outside it:

```
--- Pre-emption: known issue classes for this project ---
{fragment text}
--- End pre-emption ---

--- Instructions from checkpoint resolution ---
{override text}
--- End instructions ---

{prompt}
```

The param is threaded through the same two `expand()` call sites that already forward `prompt`/`model` conditionally: `DispatchStepType.expand()` (`steps/dispatch.py:53-56`) and `PhaseStepType.expand()` (`steps/phase.py:136`), each adding one `if "pre_emption_fragment" in cfg: action_config["pre_emption_fragment"] = cfg["pre_emption_fragment"]`-shaped line. Absent from a pipeline's YAML, nothing changes — every existing `expand()` test's exact-dict-equality assertion is untouched (Ground-truth fact 4).

**Rejected: a new pipeline-YAML field naming a file path directly, resolved at expand-time.** Would require `expand()` to do file I/O (reading the fragment off disk) at pipeline-parse time, a new kind of side effect neither `expand()` method has today — both are currently pure dict transformations. Keeping `expand()` pure and pushing the file read into `DispatchAction` (which already does I/O via `one_shot_dispatch`) is the smaller, more consistent change.

**Rejected: a compaction-template-style named resource** (`compaction_templates.py` precedent — resolve-by-name from `~/.config/squadron/...` plus a bundled default). Heavier than needed: that mechanism exists for multiple named, hand-authored templates selected by a pipeline author; this slice has exactly one generated artifact per project, addressed by path, with no selection logic to speak of. Reconsider only if a second fragment *type* is ever needed (not anticipated).

**Why this doesn't touch context-forge:** the fragment is concatenated inside `DispatchAction._resolve_prompt`, strictly after the point where `cf_op.py`'s `build_context` output has already been assigned to `prompt` (Ground-truth fact 2). `cf_op.py` itself, the `cf build` subprocess invocation, and everything upstream of it are unmodified — confirmed by inspection, not assumed.

**Blast radius if this mechanism is wrong or the fragment content is bad.** Bounded by construction to pipelines that explicitly set `pre_emption_fragment`: every other pipeline's `expand()` output and resulting prompt is byte-identical to today. A stale or malformed fragment degrades to bad advice prepended to an otherwise-correct prompt for opted-in dispatches only — it cannot corrupt `cf build`'s output, crash dispatch, or affect any non-opted-in pipeline.

### 2. Fragment content: category-scoped, not project-scoped prose

**Decision:** The fragment is generated from a project's `ProjectBaseline.cells` (323's `BaselineCell`, one per `AuditCategory`), filtered to categories whose count is meaningfully present and whose floor (if measured) does not already explain the count as noise. For each surviving category, emit one line naming the category and a short, fixed instruction (not the audit's own prose `summary` fields — those are per-finding and would make the fragment grow unboundedly with the baseline).

```
Known issue classes for this project (from tech-debt-audit baseline, {measured_at}):
- architectural-decay: avoid large multi-responsibility modules; prefer focused, composable units.
- type-contract-debt: keep type contracts explicit at boundaries; avoid loosening types to unblock a change.
```

Category → instruction text is a **fixed mapping in code** (one line per `AuditCategory`, ten total), not model-generated prose — 323's `summary` fields are specific to one finding and not reusable as general guidance, and generating fresh advisory prose per regeneration would reintroduce exactly the non-determinism 323 spent its effort normalizing away. The mapping is a small, static, human-authored lookup table, reviewed alongside the category vocabulary itself (`AuditCategory`, `models.py`).

**Category selection is floor-aware, not a raw top-N.** A category is included only if its baseline count is nonzero. This keeps the fragment honest: a category present only because of noise on a low-floor codebase (323's per-category floors ranged from perfectly stable, e.g. `architectural-decay` sd 0, to swinging 1-6) is still worth naming, since the fragment's job is "avoid this class of issue," not "this count is statistically significant" — that precision belongs to the delta report (Decision 4), not the fragment.

**No per-finding location or severity in the fragment.** Locations and severities are specific to one audit run's snapshot and go stale immediately; the fragment states classes of issue to avoid going forward, not a checklist of current findings to fix. (Fixing current findings is the audit report's job, not this slice's.)

### 3. Regeneration: explicit command, not automatic

**Decision:** `sq metrology preempt generate <project-path>` reads the current baseline via `baseline_report(store, project_filter=project_id)`, renders the fragment (Decision 2), and writes it to a path under `metrology.preemption_fragment_dir` (new config key, default `~/.config/squadron/metrology/preemption/`), named by project id. Regeneration is **operator-triggered**, matching the cadence discipline 323 already established for the baseline itself (not continuously refreshed; re-measurement is warranted when the audit prompt or model changes).

**A stale fragment is detectable, not silently wrong.** The written fragment file carries a header recording the `audit_prompt_hash` and `measured_at` of the baseline it was generated from. `sq metrology preempt generate --check <project-path>` (a read-only mode of the same command) compares the fragment's recorded hash/timestamp against the current baseline and reports whether it is current — this is the "regeneration is a defined step... a stale fragment does not silently diverge from the baseline without the report showing it" success criterion from the slice plan, satisfied by an explicit check rather than automatic regeneration.

### 4. Delta report: observational, floor-relative, never causal

**Decision:** `sq metrology audit delta <project-path>` runs one new audit (via 323's `run_audit`), then compares the new run's per-category and total counts against the stored baseline's counts, presenting each delta alongside the applicable `FloorStat` from the stored `AuditNoiseFloor`:

```
github.com/ecorkran/squadron @<new-sha>  baseline 55 → now 48  delta -7
  floor: 17-79 (mean 55.7, sd 33.72, n=3) — delta within floor: NOT distinguishable from noise
  architectural-decay        baseline 9  → now 6   delta -3   floor 8-11 — within floor: noise
  type-contract-debt         baseline 8  → now 2   delta -6   floor 4-12 — within floor: noise
```

A delta is reported as **indistinguishable from noise** whenever `|delta| < (floor.max - floor.min)` for that cell — the observed spread, not a derived confidence interval, since n=3 floors do not support one (323's own finding: three runs demonstrate dispersion is large and size-dependent, not that any project's floor is tight). A cell with `floor_note = "no floor measured"` reports the delta with an explicit **"no floor — delta not interpretable"** marker rather than silently treating it as significant.

**Framing is fixed text, not tunable.** Every delta report carries a standing disclaimer — "observational directional signal, not causal proof; other changes to the codebase between baseline and this run are not controlled for" — because a handful of projects and n=3 floors cannot support a causal claim, and the architecture explicitly forbids overclaiming at this evidence level.

**The "after" run is a normal `run_audit` call, not a variance series.** One re-run, not three — running a full 3-run variance series for every delta check would triple the cost of routine measurement for no benefit the delta comparison needs (the floor it compares against was already measured at baseline time). If a re-measured floor is ever wanted, `sq metrology audit variance` (323) already does that; `audit delta` composes with it rather than reimplementing it.

## Architecture

### Component Structure

New surface-agnostic core under `src/squadron/metrology/` (no Typer imports), plus thin CLI shells — matching 320-323.

- **`preemption.py`** — fragment generation:
  - `CATEGORY_GUIDANCE: dict[AuditCategory, str]` — the fixed, human-authored instruction-per-category mapping (Decision 2).
  - `render_fragment(baseline: ProjectBaseline) -> PreemptionFragment` — selects nonzero-count categories, renders the text block, stamps `audit_prompt_hash`/`measured_at`.
  - `PreemptionFragment` (Pydantic, in `models.py` per the 322 envelope-payload layering precedent, re-exported from `preemption.py`): `project_id`, `audit_prompt_hash`, `measured_at`, `text: str`.
  - `write_fragment(fragment, *, dir) -> Path` / `read_fragment_header(path) -> tuple[str, datetime] | None` — write with header, and a cheap header-only read for `--check` without re-parsing the whole file.
  - `check_freshness(fragment_path, current_baseline) -> FreshnessResult` — compares recorded vs. current `audit_prompt_hash`/`measured_at`.

- **`audit_delta.py`** — the before/after comparison:
  - `compute_delta(baseline: ProjectBaseline, new_run: AuditRun) -> DeltaReport` — per-category and total count diff against the stored floor; pure, independently testable on fixtures.
  - `DeltaReport` / `DeltaCell` (Pydantic, `models.py`): counts, delta, floor, and a `within_floor: bool | None` (`None` when no floor measured).

- **`dispatch.py` (pipeline action, modified)**:
  - `_resolve_prompt` gains one more prepend step, reading `context.params.get("pre_emption_fragment")`, applied after `_apply_override` returns (Decision 1).

- **`steps/dispatch.py`, `steps/phase.py` (modified)**: one conditional line each in `expand()`, following the existing idiom.

### Store interaction

**None — no new record type.** This slice reads 323's existing `AuditRun`/`AuditNoiseFloor`/`BaselineReport` and writes a plain file (the fragment) to disk, not to the metrology store. The delta report is computed and printed/returned; it is not persisted as a new record type, since nothing downstream needs to query historical deltas — the store already holds every individual `AuditRun`, from which a delta between any two points can be recomputed on demand. Persisting a `DeltaReport` as a record type was considered and rejected as speculative: no consumer needs it, and 320's spine philosophy is "provide what the next slice consumes," not "persist everything computable."

### Execution path

`sq metrology preempt generate` and `sq metrology audit delta` are both read-mostly against the store (list runs/floors) plus, for `delta`, one `run_audit` call — reusing 323's harness and its full failure-mode handling (timeout, disconnect, malformed-findings-block, pre-flight checks) unmodified. No new agent-execution surface is introduced.

### Failure modes of the new file-read path

Decision 1 pushes the fragment file read into `DispatchAction`, at dispatch time — a new I/O boundary in a path that today does no file I/O beyond consuming `cf build`'s already-resolved output string. Per the project's failure-mode-enumeration rule (and following 323's own precedent table), each mode is handled explicitly rather than left to an implicit "cannot crash" claim:

| Failure mode | Detection | Response | Observable signal |
|---|---|---|---|
| **`pre_emption_fragment` path set, file missing** (operator configured the path before running `preempt generate`, or a typo) | `Path.exists()` check before read, inside `_resolve_prompt` | Skip the prepend — dispatch proceeds with the unmodified prompt, exactly as if the param were absent | `WARNING` naming the configured path |
| **File present but unreadable** (permissions) | `OSError` from the read call | Same — skip the prepend, proceed with the unmodified prompt | `WARNING` with the exception message |
| **File present but empty or missing its header** (partial write, corrupted) | Header-parse failure in `read_fragment_header` | Same — skip the prepend, proceed with the unmodified prompt | `WARNING` distinguishing *empty* from *malformed header* |

One governing rule covers all three: **a fragment problem degrades to "no fragment," never to a dispatch failure.** This mirrors `_apply_override`'s own posture — an empty/absent `override_instructions` is silently a no-op, not an error — and keeps the blast-radius claim in Decision 1 true by construction rather than by assertion: the worst case for a broken fragment is the prompt dispatch would have produced anyway, with a `WARNING` telling the operator to re-run `preempt generate`. This is deliberately asymmetric with 323's own table, where a failed *audit run* must persist nothing (a corrupted measurement would poison the floor) — here a missing fragment has no measurement to poison, so degrading to a no-op is the correct, lower-severity response for this boundary.

## Data Flow

```
                    ┌─── generation (operator-triggered) ───┐
MetrologyStore ──> baseline_report ──> render_fragment ──> fragment file (disk)
 (323's runs/                                                     │
  floors, read-only)                                              │
                                                                    ▼
                                            pipeline YAML: pre_emption_fragment: <path>
                                                                    │
                                                                    ▼
                                    PhaseStepType/DispatchStepType.expand()
                                                                    │
                                                                    ▼
                                      DispatchAction._resolve_prompt (prepend)
                                                                    │
                                                                    ▼
                                                          agent dispatch (140)

                    ┌─── delta (operator-triggered) ───┐
MetrologyStore ──> baseline_report (old) ─┐
                                           ├──> compute_delta ──> DeltaReport (printed)
project ──> run_audit (new) ──────────────┘
                │
                ▼
        MetrologyStore (new AuditRun persisted, same as any 323 run)
```

Dispatch reads only the fragment **file**, never the store. The store is touched exclusively by the two operator-triggered commands (`preempt generate`, `audit delta`), never by a pipeline run — the down-only discipline the architecture requires is structural (no code path from `DispatchAction` to `MetrologyStore` exists), not merely observed.

## Interface Specification

CLI, matching 320-323 conventions (`--cwd`, `--json`, `MetrologyStoreError` → red + exit 1, empty results → dim message + exit 0):

```
sq metrology preempt generate <project-path>   [--json] [--cwd]
    Reads the current baseline, writes a pre-emption fragment file.
    Overwrites any existing fragment for this project.

sq metrology preempt generate <project-path> --check   [--json] [--cwd]
    Read-only: reports whether the existing fragment file is current
    against the stored baseline (matching audit_prompt_hash), or stale,
    or absent. Exit 0 (current), 1 (stale/absent) — scriptable for CI.

sq metrology audit delta <project-path>   [--profile] [--json] [--cwd]
    Runs one new audit, compares to the stored baseline, reports the
    delta per category and in total, relative to the measured floor.
```

Pipeline YAML usage (opt-in, additive to existing dispatch/phase step config). `pre_emption_fragment` is a **literal path string**, not a template — no template-variable resolution is added to `expand()` (Decision 1 keeps `expand()` a pure dict transformation), so the operator writes the concrete path `preempt generate` actually wrote to, e.g.:

```yaml
- design:
    phase: 4
    model: opus
    pre_emption_fragment: "~/.config/squadron/metrology/preemption/github.com-ecorkran-squadron.md"
```

### New config keys

| Key | Type | Default | Purpose |
|---|---|---|---|
| `metrology.preemption_fragment_dir` | `str` | `~/.config/squadron/metrology/preemption` | Directory `preempt generate` writes fragment files into |

Only one new key. `audit delta` reuses 323's existing `metrology.audit_profile`/`metrology.audit_model`/`metrology.audit_timeout_s` for its re-run — no new keys needed there.

## Success Criteria

Restating the slice-plan criteria as verifiable conditions:

- [ ] A pre-emption fragment is generated from a project's persisted baseline's actual nonzero issue-class counts (`sq metrology preempt generate`), written as a static file.
- [ ] The fragment reaches dispatch as static prompt material via a new opt-in pipeline-config field (`pre_emption_fragment`), threaded through both `DispatchStepType.expand()` and `PhaseStepType.expand()`; a pipeline that does not set the field produces byte-identical `expand()` output to today (asserted by the existing exact-equality tests continuing to pass unmodified).
- [ ] Dispatch never queries the metrology store at runtime — asserted by inspection/test that no code path from `DispatchAction` reaches `MetrologyStore`; the store's absence at dispatch time produces no error (only fragment *generation*, a separate command, touches the store).
- [ ] `sq metrology audit delta` compares a fresh audit run's counts to the stored baseline and reports the delta relative to the stored `AuditNoiseFloor`, per category and in total.
- [ ] A delta smaller than the floor's observed spread (`floor.max - floor.min`) is reported as indistinguishable from noise; a delta report for a category/project with no measured floor states so explicitly rather than treating the delta as significant.
- [ ] Every delta report carries the fixed observational/non-causal disclaimer text.
- [ ] `sq metrology preempt generate --check` detects a stale fragment (baseline's current `audit_prompt_hash`/`measured_at` differs from the fragment's recorded header) and reports it, rather than the fragment silently diverging.
- [ ] Each of missing/unreadable/malformed fragment file at dispatch time degrades to a skipped prepend (dispatch proceeds with the unmodified prompt) and emits a `WARNING` — asserted by a test per mode, so a broken fragment can never fail or silently corrupt a dispatch.
- [ ] The full existing test suite passes, including every current `expand()` test unmodified — no judging-path, dispatch-path, or cf-op-path behavior changes for pipelines that do not opt in.

## Verification Walkthrough

Draft — to be executed and refined at Phase 6 completion.

**1. Generate a fragment from an existing baseline.**
```
uv run sq metrology preempt generate /Users/manta/source/repos/manta/migratory-viewer
```
Expect a written fragment file naming nonzero categories from 323's already-measured migratory-viewer baseline (e.g. `architectural-decay`, `consistency-rot`) with the fixed guidance text, and a header recording the baseline's `audit_prompt_hash`/`measured_at`.

**2. Freshness check, current.**
```
uv run sq metrology preempt generate /Users/manta/source/repos/manta/migratory-viewer --check
```
Expect exit 0, "current."

**3. Freshness check, stale.** Re-run a variance/audit series on the same project (changing `audit_prompt_hash` via a skill edit, or simply a new baseline run), then re-check without regenerating:
```
uv run sq metrology audit run /Users/manta/source/repos/manta/migratory-viewer
uv run sq metrology preempt generate /Users/manta/source/repos/manta/migratory-viewer --check
```
Expect exit 1, "stale," naming the mismatched hash/timestamp.

**4. Fragment reaches dispatch, opted-in pipelines only.** Add `pre_emption_fragment: <path>` to a test pipeline's `design` step; run it and confirm (via `--json`/debug log) the prompt sent to the agent is prefixed with the fragment block. Run an unmodified existing pipeline (e.g. `slice.yaml`) and confirm its prompt is byte-identical to a pre-324 run — no fragment text present.

**4a. Broken fragment degrades to a no-op, not a dispatch failure.** Point `pre_emption_fragment` at a nonexistent path; confirm the dispatch still runs to completion with the unmodified prompt and a `WARNING` is logged naming the missing path. Repeat pointing at an empty file (simulating a partial write); confirm the same degrade-and-warn behavior rather than an exception propagating from `_resolve_prompt`.

**5. Delta report, below floor.**
```
uv run sq metrology audit delta /Users/manta/source/repos/manta/migratory-viewer
```
Given 323's measured floor (19-27, spread 8) and a plausible new count within that range, expect the report to state the delta is within the floor and not distinguishable from noise, with the standing observational disclaimer present.

**6. Delta report, no floor measured.** Run delta against a project with a baseline but no variance series. Expect the report to state "no floor — delta not interpretable" for that project rather than treating any observed change as significant.

**7. Nothing else moved.**
```
uv run pytest -q && uv run pyright && uv run ruff check .
```
Expect the full suite green, with the existing `test_phase.py`/`test_dispatch_step.py` `expand()` assertions passing unmodified (proving the new field is genuinely additive).

## Risks

- **The fixed category→guidance mapping may be too generic to change model behavior.** Ten short lines of advice competing against a full `cf build` context may have negligible effect. Not mitigated speculatively — this slice's job is to prove the mechanism exists and delivers a fragment + a floor-relative delta; whether the fragment measurably changes subsequent audit counts is itself an empirical question the delta report exists to answer, not something guaranteed by design.
- **A handful of projects and n=3 floors limit what any delta can claim.** Mitigated by design (Decision 4): the report's framing is fixed, non-causal, and floor-relative rather than implying statistical confidence the evidence doesn't support.
- **Regeneration is manual, so a fragment can silently go stale if the operator forgets.** Mitigated by `--check` (Decision 3), which makes staleness detectable on demand; full automation (e.g. a CI gate requiring `--check` to pass) is not built speculatively.

## Future Work

1. [ ] **CI gate on fragment freshness** — wire `sq metrology preempt generate --check`'s exit code into a CI step so a stale fragment fails a build rather than requiring an operator to remember. Depends on nothing in this slice; deferred as a project-specific CI decision, not a squadron mechanism. Effort: 1/5.
2. [ ] **Persisted `DeltaReport` history** — if trend-over-time for deltas (not just baseline-vs-now) becomes a felt need, add a record type and store writer, mirroring 323's `audit_noise_floor` precedent. Not built speculatively (Architecture, Store interaction). Effort: 2/5.
3. [ ] **Model-generated (rather than fixed) per-category guidance text** — if the fixed ten-line mapping proves too generic (Risks), consider generating richer, project-specific guidance from the audit's own finding summaries. Deferred: reintroduces the per-run non-determinism 323 spent effort normalizing away; only worth it if the fixed mapping demonstrably underperforms. Effort: 3/5.
