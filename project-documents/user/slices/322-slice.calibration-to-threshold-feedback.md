---
docType: slice-design
slice: calibration-to-threshold-feedback
project: squadron
parent: ../architecture/320-slices.judge-calibration-quality-metrology.md
dependencies: [320, 321]
interfaces: []
dateCreated: 20260725
dateUpdated: 20260725
status: not-started
---

# Slice Design: Calibration-to-Threshold Feedback

## Overview

This slice closes the loop the initiative exists to close. 321 made judge reliability a **measured, per-level quantity**; 322 turns that measurement into an **advisory threshold recommendation** against 300's judge-threshold config, and installs the safeguards that keep the loop honest once a judge graduates.

Four things ship together because each is load-bearing for the others:

1. **The recommendation path** — read `AgreementReport` (321), emit a typed, evidence-floored recommendation for a `(template, model)` pairing at an artifact level. Advisory only: **nothing mutates threshold config automatically.**
2. **The minimum-evidence floor, enforced** — 321 *reports* `below_floor`; 322 *refuses to recommend loosening* below it and **states the floor it applied**.
3. **Residual sampling on graduated judges** — graduation removes an artifact from the escalation flow, which is where spot-checks came from. 322 ships a residual-sampling policy plus an **offer-selection core** so a graduated judge keeps producing sampled human-verdict data.
4. **The version-keying resolution** — the plan's open question, resolved here: the **content-hash-at-capture fallback** is canonized as the comparability key, with one contained correction to what the hash covers (see Technical Decisions).

This slice adds **no gating mechanism, no automatic config write, and no change to the judging path**. It reads 321's report models and 300's threshold config surface, and writes nothing but its own advisory output.

## Value

Operator value. 300's escalate-vs-auto-gate decision was made *configurable* but is set by guess; 321 made the evidence visible but stopped short of acting on it. 322 is where an operator can ask "has `judge-tasks-vs-slice` on model X earned a lower escalation rate at this level?" and get an answer that either says *yes, here is the pairing and the evidence*, or says *no, and here is exactly how much evidence is missing*. The refusal is as valuable as the recommendation — it is what stops thresholds moving on noise.

## Technical Scope

**Included:**
- A **recommendation core** (`squadron.metrology.calibration`): pure functions over `AgreementReport` → typed `ThresholdRecommendation` models.
- **Evidence-floor enforcement**: a recommendation to *loosen* (raise trust / lower escalation) is refused below `metrology.min_evidence_n`; the applied floor and the observed n are always stated in the output.
- **Direction asymmetry**: loosening is floor-gated; **tightening is not** (see Technical Decisions — a weak judge should be flagged on whatever evidence exists).
- **Recommendation targets**: resolve the `(template, model)` calibration key onto 300's two real threshold surfaces — the template's `judge:` block (`pass_floor` / `concerns_floor`) and a step's `judge` override — and surface the **(template,model) ↔ (template,step) dimensional mismatch** as first-class output, not a caveat.
- **Residual sampling**: a `metrology.residual_sample_rate` config key, a **graduated-config registry** (which `(template, model)` pairings the operator has moved toward auto-gate), and an **offer-selection function** producing sampling targets drained through 320's existing pull-based capture.
- **The comparability key, canonized**: the content-hash fallback becomes *the* version identity, with `_template_content_hash` corrected to exclude the `judge:` threshold block (see Technical Decisions — this is the self-defeating-loop fix).
- CLI: `sq metrology recommend` and `sq metrology offers`, thin Typer shells over the surface-agnostic core (parity by construction, matching 320/321).

**Explicitly excluded:**
- **Any automatic threshold mutation** → a Non-Goal of the architecture, permanently out of scope. The recommendation prints; the operator edits config.
- **A new gating mechanism** → 300 owns gating. 322 emits configuration advice, nothing more.
- **Solving the runtime-drawn-model limitation** → inherited and documented, not solved (see Technical Decisions). A step whose model comes from a 180 pool cannot vary its threshold with the model actually drawn.
- **The coordinated 300 write-path version field** → *not* chosen (see Technical Decisions); remains 320-plan Future Work #1, still open.
- **Persisting the judge verdict onto the sample** (321 Future Work #2) → rides with the 300 write-path change; not taken here, so 321's content-verified re-read join stands unchanged.
- **Audit-oracle work** (323/324) → different oracle, different grain.

## Dependencies

### Prerequisites
- **321 (agreement & dispersion reporting)** — `status: complete`. Provides `AgreementReport` / `AgreementCell` / `GroupKey` / `ExclusionSummary`, the `ArtifactLevel` vocabulary, and `metrology.min_evidence_n`.
- **320 (metrology data layer & sample capture)** — `status: complete`. Provides `MetrologyStore`, `JudgeConfigId`, `derive_judge_config_id`, and the pull-based capture flow residual offers drain through.

### Interfaces Required
- `squadron.metrology.report.agreement_report` + `report_models.AgreementReport` — the recommendation input. **Consumed as-is; no 321 change.**
- `squadron.metrology.levels.ArtifactLevel` — recommendations are reported per level.
- `squadron.pipeline.actions.judge` — `JudgeThresholds`, `resolve_thresholds`, and the module defaults. **Read-only**: 322 reads current effective thresholds to express a recommendation as a *delta from what is configured now*, and never calls into the enforcement path.
- `squadron.review.templates.get_template` / `ReviewTemplate.judge` — the template-level threshold block that is one recommendation target.
- `squadron.metrology.identity._template_content_hash` — corrected here (scope narrowed); see Technical Decisions.
- `squadron.config.manager` / `config.keys.CONFIG_KEYS` — new config keys.
- The `metrology` Typer sub-app in `cli/commands/metrology.py`.

### State of the threshold config (facts verified against the code)

Three facts shaped this design and must not be re-guessed at task time:

1. **There are exactly two threshold surfaces, and neither has a model dimension.** [judge.py:41-57](src/squadron/pipeline/actions/judge.py#L41-L57) merges per-key: **step override → template default → module constant** (`_DEFAULT_PASS_FLOOR = 75.0`, `_DEFAULT_CONCERNS_FLOOR = 50.0`). The template default is the `judge:` block in the template YAML (e.g. [judge-tasks-vs-slice.yaml](src/squadron/data/templates/judge-tasks-vs-slice.yaml) → `pass_floor: 78`, `concerns_floor: 55`); the step override is `context.params["judge"]` ([review.py:226](src/squadron/pipeline/actions/review.py#L226)). **Neither is keyed by model.** This is the architectural mismatch, confirmed in code: calibration is `(template, model)`-keyed, config is `(template, step)`-keyed.

2. **The template content hash currently covers the `judge:` block.** [identity.py:298-323](src/squadron/metrology/identity.py#L298-L323) hashes `{name, description, system_prompt, model, prompt_template, judge}`. Since `judge` *is* `pass_floor`/`concerns_floor`, **acting on a recommendation changes the hash and resets accumulated n to zero** — the calibration loop would destroy its own evidence every time it succeeds. This is the plan's named "churn perpetually resets n and starves graduation" failure, and the loop's own action is the churn. Corrected here.

3. **There is no offer queue.** [capture.py:190-241](src/squadron/metrology/capture.py#L190-L241) enforces `sample_budget` as a ceiling on *captures written*, and 320's design explicitly deferred the offer/selection policy. Residual sampling therefore needs a **selection** surface, which is what 322 adds — not a change to how capture writes.

## Architecture

### Component Structure

New surface-agnostic core under `src/squadron/metrology/` (no Typer imports), plus thin CLI shells:

- **`calibration.py`** — the recommendation core:
  - `recommend_thresholds(agreement: AgreementReport, *, floor: int, current: ThresholdSnapshot) -> RecommendationReport` — one recommendation per `(ArtifactLevel, JudgeConfigId)` cell, each carrying its evidence, the floor applied, and its direction.
  - `classify_direction(match_rate, n, floor) -> RecommendationDirection` — the decision function (see Technical Decisions for the bands).
  - `read_current_thresholds(template_name) -> JudgeThresholds` — reads the *currently configured* template-level floors via `resolve_thresholds(template.judge, None)` so a recommendation is expressed as a delta from reality, not from a constant.

- **`graduation.py`** — the graduated-config registry and residual-offer selection:
  - `GraduatedConfig` — a persisted record of a graduation, keyed on the **full `JudgeConfigId`** (not just template+model) plus the artifact level, with the evidence snapshot that justified it and when. Carrying the whole config identity — including `template_content_hash` — is what makes a graduation **version-scoped**: see *Graduation is version-scoped* below.
  - `select_residual_offers(store, graduated, *, rate, cwd) -> list[OfferTarget]` — for each graduated config, identify persisted judge results **matching that exact `JudgeConfigId`** which are **not yet sampled**, and select a `rate` fraction as offers. Results whose config identity differs (a prompt/model edit since graduation) are **not** offered under that graduation — they belong to a different instrument.
  - Offers are **advisory targets**, not a mutation: the operator drains them with the existing `sq metrology sample <target>`.

- **`calibration_models.py`** — Pydantic output shapes (the typed interface, not console text):

```
RecommendationDirection   enum: GRADUATE | HOLD | TIGHTEN | INSUFFICIENT_EVIDENCE
EvidenceSnapshot          n: int; match_rate: float; floor_applied: int;
                          below_floor: bool
ThresholdTarget           template_name: str; current: JudgeThresholds;
                          model_dimension_note: str
ThresholdRecommendation   group: GroupKey; direction: RecommendationDirection;
                          evidence: EvidenceSnapshot; target: ThresholdTarget;
                          rationale: str
RecommendationReport      cells: list[ThresholdRecommendation];
                          excluded: ExclusionSummary; floor_applied: int
GraduatedConfig           judge_config: JudgeConfigId; artifact_level;
                          evidence: EvidenceSnapshot; graduated_at
                          (judge_config carries template_name + model +
                           template_content_hash — graduation is scoped to
                           the exact instrument the evidence measured)
OfferTarget               review_path: str; judge_config: JudgeConfigId;
                          reason: Literal["residual-sampling"]
```

- **`cli/commands/metrology.py`** (extended) — `sq metrology recommend` and `sq metrology offers`, plus `sq metrology graduate` to record a graduation. Same `--cwd` / `--project` / `--json` conventions as 320/321.

- **`identity.py`** (one contained correction) — `_template_content_hash` narrows its scope to exclude the `judge:` block.

### Data Flow

**Recommendation (read-only):**
1. Operator runs `sq metrology recommend [--project ID] [--level L] [--json]`.
2. Core builds the `AgreementReport` via 321's existing `agreement_report` — **no re-implementation of aggregation.**
3. For each agreement cell: read the current configured thresholds for that cell's `template_name`; classify the direction from `(match_rate, n, floor)`.
4. Emit one `ThresholdRecommendation` per cell, each stating **the floor applied**, **the observed n**, the **current** thresholds, and — for every cell — the **model-dimension note** (the recommendation is per-model; the config is not).
5. Render table or `--json`. 321's `ExclusionSummary` passes through verbatim so excluded evidence is never mistaken for absence of evidence.

**Nothing is written.** No config file, no template YAML, no review file, no store record.

**Graduation + residual sampling (the one write path, operator-initiated):**
1. Operator, having read a `GRADUATE` recommendation, edits their 300 threshold config **by hand** (322 does not do it), then records the decision: `sq metrology graduate --template T --model M --level L`.
2. That writes one `GraduatedConfig` record into the metrology store — the only thing this slice persists.
3. `sq metrology offers` reads graduated configs, calls `select_residual_offers`, and lists judge results to spot-check at the configured residual rate.
4. Operator drains offers through 320's existing blind capture. **Agreement data keeps accumulating for a graduated judge** — the guarantee the architecture demands.

No pipeline, gate, or dispatch path is touched. Offers are pull-based and non-blocking; ignoring them is free.

### State Management

Stateless except for `GraduatedConfig` records, which persist in 320's store behind a **new `record_type` discriminator** (`graduated_config`) — exactly the extension point 320's `MetrologyRecord` envelope reserved for 323's `audit_finding`. No store migration, no schema change to existing records.

## Technical Decisions

### Version identity — the content-hash fallback ships (the plan's open question, resolved)

The plan named two ways to resolve version-keying. **Decision: the content-hash-at-capture fallback ships; the coordinated 300 write-path field does not.**

Rationale: 320 **already computes** `template_content_hash` at capture ([identity.py:326-340](src/squadron/metrology/identity.py#L326-L340)), 321 **already enforces** non-blending on it, and every sample in the store already carries it. The preferred write-path field would buy source-side keying and a natural home for the judge verdict — real benefits — at the cost of a cross-initiative 300 change for a capability that already works read-side. The initiative's own principle is *read-side over 300's write path*; this is the option that honors it. The 300 write-path field remains **320-plan Future Work #1, still open**, and 321 Future Work #2 (judge-verdict persistence) stays parked with it.

Consequence, stated honestly: keying is **reliable going forward, not retroactive**. Records captured where the review type resolves to no known template carry `template_content_hash = None`; 321 already flags these `unversioned` and segregates them, and 322's recommendation input inherits that — **an unversioned cell can never produce a `GRADUATE` recommendation** (see the direction bands below).

### The hash must exclude the threshold block — or the loop destroys its own evidence

This is the substantive correction this slice makes, and it is a **correctness fix, not a preference**.

`_template_content_hash` currently hashes `{name, description, system_prompt, model, prompt_template, **judge**}`. The `judge` block *is* `pass_floor`/`concerns_floor` — the very thing a recommendation asks the operator to change. So:

> operator acts on a `GRADUATE` recommendation → edits `judge.pass_floor` → template content hash changes → the new config is a **different `JudgeConfigId`** → accumulated n resets to 0 → the cell drops `below_floor` → no further recommendation is possible until evidence re-accumulates from scratch.

The calibration loop would invalidate its own evidence every single time it worked. The plan flagged "churn perpetually resets n and starves graduation" as a risk from *template editing*; in fact the loop's own success is the dominant source of churn.

**Decision: narrow the comparability hash to the judged behavior, excluding the threshold block.** The hash covers `{name, description, system_prompt, model, prompt_template}`. Rationale: thresholds are the **output** of calibration, not part of the instrument being calibrated. A judge that scores identically but bands differently is *the same measuring instrument with a different readout* — agreement data collected under it remains valid evidence about how that judge scores. Conversely a prompt or model edit changes what the instrument measures and **must** re-key, which this preserves.

This is a contained change to one private function in 320's `identity.py`, plus its tests. It does re-key historical records once (their hash changes), which is correct and one-time: those records were keyed on a value that conflated instrument with readout.

*Rejected — a similarity/inherit policy* (the plan's third framing): more machinery and more judgment calls than the problem needs. Excluding thresholds from the hash solves the actual failure precisely, with no policy layer to tune.

### Graduation is version-scoped — it keys on the whole `JudgeConfigId`

A graduation is a statement about **an instrument**, not about a name. `GraduatedConfig` therefore persists the full `JudgeConfigId` (`template_name`, `model`, `template_content_hash`), not just `(template, model)`.

The failure this prevents: `(template_name, model, artifact_level)` is **invariant across a prompt edit**, while `JudgeConfigId` is not. Keyed on the looser triple, a graduation earned by one prompt would silently carry over to a rewritten one — and `select_residual_offers` would keep drawing spot-checks against it as though the evidence still applied. That is precisely the version-blending the architecture forbids ("metrology records must identify the judge configuration they measured"), occurring at the one point in the initiative where a *trust* decision is recorded rather than a measurement. Residual sampling would then be verifying an instrument nobody calibrated.

With the full identity, a prompt or model edit means the graduation **no longer matches** any new results: those results fall outside the graduated config, produce no offers under it, and the pairing must re-earn its evidence — which is the correct behavior, since the instrument changed.

This composes with the narrowed hash above rather than fighting it. Because the hash **excludes** the threshold block, acting on a recommendation does not invalidate the graduation it justified; because it **includes** prompt and model, a real change to the instrument does. Graduation survives its own consequence and expires on genuine drift — the two decisions are what make each other safe.

Consequence for `sq metrology offers`: a graduated config with no matching current results yields an **empty offer set with an explanatory line** naming the config-identity change, not a silent absence. An operator who edits a judge prompt learns that its graduation has lapsed rather than discovering later that sampling quietly stopped.

### Direction bands — asymmetric, because the risks are asymmetric

`classify_direction(match_rate, n, floor)`:

| Condition | Direction | Floor-gated? |
| --- | --- | --- |
| `n < floor` | `INSUFFICIENT_EVIDENCE` | — (this *is* the floor) |
| unversioned config (`template_content_hash is None`) | `INSUFFICIENT_EVIDENCE` | — (never graduate on un-keyable evidence) |
| `n >= floor` and `match_rate >= graduate_floor` | `GRADUATE` | **yes** |
| `n >= floor` and `match_rate` mid-band | `HOLD` | yes |
| `match_rate <= tighten_ceiling` | `TIGHTEN` | **no** |

**Loosening is floor-gated; tightening is not.** Requiring a large sample before *warning* about a judge that disagrees with the human would suppress exactly the signal most worth having early — a bad judge is worth flagging on thin evidence, while trusting one is not. `TIGHTEN` output always carries its n, so an operator sees the strength of the warning. This asymmetry is the honest reading of the architecture's "refuses to recommend **loosening** below a minimum-evidence floor."

`graduate_floor` and `tighten_ceiling` are **config keys, not literals** (CLAUDE.md: no scattered comparison values).

### Recommendations are advisory *deltas*, and never state a number the operator must accept

A recommendation names a **direction and the evidence for it** — not a computed "correct" `pass_floor`. Deriving a specific numeric floor from agreement data would imply a precision the sample sizes here (*honest statistics at small n*) cannot support, and would edge toward the automatic self-tuning the architecture forbids. Each recommendation shows the **currently configured** thresholds (read via `resolve_thresholds`) so the operator sees what they would be changing from, and decides the magnitude.

### The (template, model) ↔ (template, step) mismatch is surfaced per recommendation, not footnoted

Calibration is keyed by `(template, model)`; 300's config has no model dimension. Rather than mention this once in docs, **every** `ThresholdRecommendation` carries a `ThresholdTarget.model_dimension_note` stating that the recommendation holds **for this template paired with this model**, and that acting on it means choosing model and threshold **together at config time**. Where a step draws its model at runtime (a 180 pool), the note states that the threshold **cannot** track the drawn model — the recommendation does not apply to that step. The limit is inherited, per the architecture; making it per-recommendation output is what stops it being silently ignored at the moment of action.

### Residual sampling — selection, not enforcement

322 ships the **policy and the selection**, drained through 320's existing pull-based capture. It does **not** hook pipelines, gates, or dispatch: the architecture is explicit that sampling is pull-based, budgeted and never blocking, so a "forced" rate means *offers are generated at that rate*, not that anything waits. `metrology.residual_sample_rate` governs what fraction of a graduated config's unsampled results become offers.

The testable guarantee (an architecture commitment, not a nicety): **given a graduated config with unsampled results, `select_residual_offers` returns a non-empty offer set** — a graduated judge keeps producing sampled data, so agreement does not freeze and within-configuration drift stays detectable.

### Config Keys (added to `CONFIG_KEYS`)

- `metrology.graduate_match_rate` (float) — agreement at or above which, *and* at or above the evidence floor, a config is recommended for graduation.
- `metrology.tighten_match_rate` (float) — agreement at or below which a `TIGHTEN` warning is emitted regardless of n.
- `metrology.residual_sample_rate` (float) — fraction of a graduated config's unsampled results offered for continued spot-checking.

`metrology.min_evidence_n` is **reused from 321**, not redefined — one floor, one definition.

## Implementation Details

### API Contracts

```
sq metrology recommend [--project ID] [--level LEVEL] [--json] [--cwd .]
sq metrology graduate  --template T --model M --level L [--cwd .]
sq metrology offers    [--project ID] [--json] [--cwd .]
```

- **`recommend`** — a row per `(artifact_level, judge_config)`: direction, match rate with its n, the floor applied, current thresholds, and the model-dimension note. Never a single blended verdict. Cells below the floor render as `INSUFFICIENT_EVIDENCE` **stating how much evidence is missing** (`n=2, floor=5`), not as a blank.
- **`graduate`** — records the operator's decision after they have edited config by hand. Refuses (non-zero exit, explicit message) if the named pairing's current recommendation is not `GRADUATE` — the floor cannot be bypassed by recording a graduation the evidence does not support.
- **`offers`** — lists residual sampling targets for graduated configs; empty with an explanatory line when none are due (not a fabricated zero).
- `--json` emits the models verbatim. All commands read-only except `graduate`, which writes exactly one store record.

### Failure Modes

Per the Failure-Mode Enumeration rule — each boundary has an enumerated failure, an explicit handling decision, an observable signal, and a test.

| Boundary | Failure | Handling | Observable signal | Test |
| --- | --- | --- | --- | --- |
| **recommendation input** | store empty / no agreement cells | honest empty report, exit 0 | "no evidence" line; `floor_applied` still stated | empty store → empty report, not an error |
| **evidence floor** | `n < min_evidence_n` | `INSUFFICIENT_EVIDENCE`; never `GRADUATE` | direction + `n=X, floor=Y` in output | below-floor cell → refuses to recommend loosening |
| **unversioned config** | `template_content_hash is None` | `INSUFFICIENT_EVIDENCE`; never `GRADUATE` | flagged unversioned; counted in `ExclusionSummary` | unversioned cell → no graduate recommendation |
| **threshold read** | template no longer registered (renamed/removed) | recommendation still emitted; target marked unresolvable | WARNING naming the template; `current` absent, not fabricated | missing template → no crash, no invented floors |
| **threshold read** | malformed `judge:` block (non-numeric floor) | `resolve_thresholds` has no fallback for this — its bare `float()` cast raises `ValueError`/`TypeError`, which is correct for 300's enforcement path; `read_current_thresholds` catches it locally and degrades to the same unresolvable-target signal as an unregistered template — `current` absent, never fabricated | WARNING naming the template | malformed judge block → flagged via `caplog`, `current is None`, no raised exception |
| **graduate** | pairing's evidence does not support `GRADUATE` | refuse; write nothing | non-zero exit + message naming n and floor | unsupported graduate → refused, store unchanged |
| **graduate** | pairing already graduated | idempotent — update the evidence snapshot, no duplicate | INFO; one record, not two | re-graduate → single record |
| **offers** | graduated config has no unsampled results | empty offer list with explanatory line | "no offers due" | exhausted config → honest empty, not fabricated |
| **offers** | referenced review file gone since graduation | skip that target; count it | WARNING naming the path | pruned review → skipped, counted, no crash |
| **offers** | judge config edited since graduation (`JudgeConfigId` no longer matches any current result) | offer nothing under that graduation — the graduation is version-scoped and has lapsed | explanatory line naming the config-identity change; empty offer set, never silent | prompt edit post-graduation → no offers drawn against the new config, lapse reported |
| **hash narrowing** | historical records re-key once | expected and one-time; documented | 321's `unversioned`/segregation reporting unchanged | narrowed hash → threshold edit preserves n; prompt edit re-keys |

No boundary swallows its failure; no path fabricates a threshold, an n, or a graduation.

**On lower-level I/O failures (raised as a review note).** The table above enumerates this slice's *own* boundaries. Store and template reads are local-filesystem operations with no lock and no network: 320's `MetrologyStore.list_samples` already skips an unreadable sibling on `(OSError, ValueError, SchemaVersionError)` with a WARNING and reports over what loaded ([store.py:177](src/squadron/metrology/store.py#L177)), and writes are atomic write-then-rename. 321 inherited that behavior and so does 322 — a corrupt or partially-written record degrades the report by one record, visibly, rather than failing the command. Rows for lock contention or read timeouts are deliberately **not** added: no lock and no timeout-bearing transport exists on these paths, and enumerating failure modes for mechanisms the code does not have would document fiction. If a future slice moves the store off the local filesystem (e.g. the 280 convergence), that transport brings its own failure modes and its own rows.

## Integration Points

### Provides to Other Slices
Nothing downstream in this initiative consumes 322 — hence `interfaces: []`. 323/324 are the *audit* oracle: per 320-arch the two oracles share the **spine** (320's store and trend conventions), not a report or recommendation path. 322 is the terminal slice of the human-oracle chain (320 → 321 → 322).

### Consumes from Other Slices
- **321's `AgreementReport`** and `ArtifactLevel` — read-only, unchanged. 321's claim that 322 consumes it "without any change to this slice" holds.
- **320's `MetrologyStore`** — read, plus one new `record_type` behind the reserved discriminator.
- **300's threshold config surface** — **read-only**, for recommendation targets. Never written automatically; the judging path is untouched.

## Success Criteria

### Functional Requirements
- A documented path takes an agreement report at an artifact level and yields a **threshold-config recommendation** for 300's template/step config; the recommendation is **advisory output** and **nothing mutates threshold config automatically** (asserted: after `recommend`, template YAML and config are byte-identical).
- The recommendation **refuses to suggest loosening** below the minimum-evidence floor and **states the floor it applied** (asserted: a below-floor cell yields `INSUFFICIENT_EVIDENCE` carrying both n and floor, never `GRADUATE`).
- Graduating a judge installs a **continued residual sampling rate**; a graduated config with unsampled results yields a non-empty offer set, so **agreement data does not freeze** (asserted by test, per the architecture's explicit commitment).
- The `(template, model)`-keyed calibration is surfaced as a **config-time model+threshold pairing** on **every** recommendation, and the **runtime-drawn-model limitation is stated where the recommendation is produced** (asserted: the note is present in output, including `--json`).
- **Version identity ships as the content-hash-at-capture fallback**; un-version-keyable data is excluded from graduation and flagged, never pooled (asserted: unversioned cell cannot produce `GRADUATE`).
- **Graduation is version-scoped**: `GraduatedConfig` records the full `JudgeConfigId`, and residual offers are drawn only for results matching that exact identity (asserted: after a prompt edit post-graduation, no offers are drawn under the stale graduation and the lapse is reported — a graduation never silently transfers to a re-written judge).
- **Acting on a recommendation does not reset accumulated evidence**: a threshold-only template edit leaves `JudgeConfigId` unchanged, while a prompt or model edit re-keys it (asserted by test on both directions — the self-defeating-loop regression).

### Technical Requirements
- **The judging path (300) is unmodified** and the capture path (320) is unchanged except the contained `_template_content_hash` scope narrowing; the full existing suite passes.
- Core (`calibration`, `graduation`, `calibration_models`) is **surface-agnostic** — no Typer imports (verified by test, matching 320/321).
- Strict pyright and ruff clean; Pydantic at boundaries; direction bands and floors are **config keys referenced once**, never scattered literals.
- Test coverage: each direction band; the floor refusal; the unversioned refusal; the hash-narrowing regression (both directions); residual-offer selection including the exhausted, pruned-file, and **lapsed-graduation** (config edited post-graduation) cases; `graduate` refusal and idempotence; the no-mutation assertion.

### Integration Requirements
- 321 is consumed **unchanged** — no edit to its report models or aggregation.
- The `graduated_config` record type extends 320's envelope **without a store migration** (existing records load unchanged).

### Verification Walkthrough

Demo script proving delivery. To be executed end-to-end and its actual output pasted back at Phase 6 completion (matching 321's practice). Commands marked *(new)* ship in this slice.

1. **Accumulate agreement evidence.** *(existing, 320/321)* In a scratch repo, blind-capture human verdicts against judge reviews at one artifact level until n is meaningful, then confirm the evidence exists:
   ```
   sq metrology report agreement --cwd <repo>
   ```

2. **Recommend below the floor — the refusal.** *(new)* With n under `metrology.min_evidence_n`:
   ```
   sq metrology recommend --cwd <repo>
   ```
   Expect: the cell reports `INSUFFICIENT_EVIDENCE` **stating both the observed n and the floor applied** — no graduation offered, and the shortfall quantified rather than blank.

3. **Recommend above the floor — the graduation.** *(new)* Capture until n crosses the floor with high agreement, re-run `recommend`. Expect: `GRADUATE`, carrying match rate with n, the floor applied, the **currently configured** thresholds read from the template, and the **model-dimension note** naming the model the recommendation is bound to.

4. **Confirm nothing was mutated.** *(new)* SHA-1 the template YAML, config, and store before and after every `recommend` run; expect byte-identical. This is the architecture's "no automatic threshold mutation" Non-Goal, verified rather than asserted.

5. **Confirm the evidence survives acting on it.** *(new — the self-defeating-loop regression)* Edit the template's `judge.pass_floor` (as the operator would when acting on step 3), then re-run:
   ```
   sq metrology report agreement --cwd <repo>
   ```
   Expect: **the same cell with the same n** — the threshold edit did not re-key the config. Then edit the template's `system_prompt` and re-run: expect the cell to **re-key** (new `JudgeConfigId`, evidence separated). Both directions confirm the hash covers the instrument, not its readout.

6. **Graduate and confirm residual sampling.** *(new)*
   ```
   sq metrology graduate --template judge-tasks-vs-slice --model <M> --level tasks_vs_slice --cwd <repo>
   sq metrology offers --cwd <repo>
   ```
   Expect: graduation recorded (one store record), and `offers` lists residual spot-check targets for that now-graduated config — proving graduation did **not** end sampling. Then drain one with `sq metrology sample <target>` and confirm via `report agreement` that n **increased** for a graduated judge.

7. **Confirm graduation is version-scoped.** *(new)* With the graduation from step 6 in place, edit the template's `system_prompt` (a real change to the instrument), produce a new judge review under the edited template, then:
   ```
   sq metrology offers --cwd <repo>
   ```
   Expect: **no offers drawn against the new config** under the old graduation, and an explanatory line reporting that the graduation has lapsed because the judge configuration changed. Contrast with step 5's threshold edit, which left the graduation intact — together these show graduation surviving its own consequence while expiring on genuine drift.

8. **Confirm the graduate guard.** *(new)* Attempt `sq metrology graduate` for a pairing whose evidence is below the floor. Expect: non-zero exit naming the observed n and the floor, and **no store record written** — the floor cannot be bypassed by recording a graduation by hand.

9. **Confirm read-only invariance and no regression.** *(existing)* Run the full suite and confirm 300/320/321 behavior is unchanged.

## Risk Assessment

### Technical Risks
- **The hash narrowing re-keys historical records once.** Records captured before this slice change hash, so evidence accumulated under the old key separates from new. Mitigation: this is a one-time, correct re-keying (the old key conflated instrument with readout), the volume is small by design (*honest statistics at small n*), and 321's existing segregation/exclusion reporting makes it visible rather than silent. Accepted deliberately, not discovered.
- **Evidence may never cross the floor in practice.** Human sampling is budgeted and slow by design, so real graduations may be rare early. Mitigation: this is the architecture's intended failure mode ("slow evidence means slower graduation and an honest floor refusal, never more interruptions") — the refusal path is therefore the *primary* tested path, not an edge case. The hash narrowing directly improves this by stopping the loop from resetting its own n.

### Mitigation Strategies
Both risks are covered by explicit tests in Success Criteria; neither needs new infrastructure or a store migration.

## Implementation Notes

### Development Approach
Suggested order:
1. `identity.py` hash narrowing + its regression tests (do this **first** — everything else accumulates evidence under the corrected key).
2. `calibration_models.py` — the typed output shapes.
3. `calibration.py` — direction bands, floor enforcement, current-threshold read + tests.
4. `graduation.py` — `GraduatedConfig` record type, `select_residual_offers` + tests.
5. `cli/commands/metrology.py` — `recommend` / `graduate` / `offers` shells; config keys.
6. End-to-end verification walkthrough.

### Special Considerations
- **Parity is structural** (as in 320/321): no MCP tool ships, but the core is the single source of truth both surfaces call.
- **No-mutation discipline** is enforced by test, not convention — `recommend` may not write anything, and `graduate` writes exactly one record.
- **Relative effort:** 3/5 (the dimensional mismatch, the graduation-sampling guarantee, and the hash-scope correction are the substance; no engine change, no new gating).

## Slice review (20260725) — CONCERN addressed

Slice-design review (`322-review.slice.…`, kimi-k2.7-code) returned 1 PASS, 1 CONCERN, 1 NOTE.

- **F001 (PASS, scope)** — feedback stays advisory and read-only over 300's surfaces; no automatic threshold mutation, no new gating mechanism.
- **F002 (CONCERN, data-model) — valid, fixed.** `GraduatedConfig` was keyed on `(template_name, model, artifact_level)`, omitting `template_content_hash`. That triple is **invariant across a prompt edit**, so a graduation earned by one prompt would silently transfer to a rewritten one and `select_residual_offers` would keep drawing spot-checks against it — version-blending at the exact point a *trust* decision is recorded, and residual sampling verifying an instrument nobody calibrated. **Fixed:** `GraduatedConfig` now carries the full `JudgeConfigId`; `select_residual_offers` matches on that exact identity; added the *Graduation is version-scoped* decision (including how it composes with the narrowed hash — graduation survives its own threshold edit but expires on prompt/model drift), a failure-mode row for the lapsed-graduation case (empty offers **with** an explanatory line, never silent), a success criterion, walkthrough step 7, and the test in coverage.
- **F003 (NOTE, failure-handling) — reviewed, deliberately not adopted.** The note asks for rows covering store lock contention and read timeouts. These paths are local-filesystem with no lock and no timeout-bearing transport; 320's `list_samples` already skips unreadable siblings with a WARNING and reports over what loaded, and writes are atomic write-then-rename. Enumerating failure modes for mechanisms the code does not have would document fiction. Recorded the actual inherited behavior under the Failure Modes table instead, and noted that a future off-filesystem store (e.g. 280 convergence) brings its own transport failure modes and its own rows.

## Implementation correction (T7, 20260725) — malformed judge block

The Failure Modes table originally described a malformed `judge:` block (non-numeric `pass_floor`/`concerns_floor`) as falling back to `resolve_thresholds`' "documented merge behavior" with a WARNING. Reading `resolve_thresholds` (judge.py:41-57) during T7 implementation showed no such fallback exists: it does a bare `float(pass_floor)` cast with no `try/except`, so a non-numeric value raises `ValueError`/`TypeError` uncaught — correct for 300's enforcement path, which should fail loudly on a corrupt config rather than silently substitute a default. Confirmed with the Project Manager rather than guessing a resolution. **Fixed:** `read_current_thresholds` (322's read-only recommendation path only) catches the exception locally, logs a WARNING naming the template, and returns `None` — the same "unresolvable target" signal as an unregistered template. 300's `resolve_thresholds` is untouched; the fix is scoped entirely to 322's new code. The Failure Modes table row above reflects this; T8's malformed-judge-block test asserts `None` + `caplog` WARNING, not a raised exception.
