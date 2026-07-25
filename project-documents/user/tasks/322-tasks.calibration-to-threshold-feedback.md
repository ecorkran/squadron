---
docType: tasks
slice: calibration-to-threshold-feedback
project: squadron
lld: ../slices/322-slice.calibration-to-threshold-feedback.md
dependencies:
  - 320 metrology-data-layer-sample-capture-keystone (complete) — MetrologyStore, JudgeConfigId, derive_judge_config_id, identity._template_content_hash, config keys, cli/commands/metrology.py sub-app
  - 321 agreement-dispersion-reporting (complete) — AgreementReport/AgreementCell/GroupKey/ExclusionSummary, ArtifactLevel, metrology.min_evidence_n
projectState: "Slice 322 design complete and slice-design-reviewed (322-review.slice.*, 1 PASS / 1 CONCERN fixed / 1 NOTE declined with rationale). This is the terminal slice of the human-oracle chain 320 -> 321 -> 322 (interfaces: []). Three open questions from the 320 plan are resolved in the design and must not be re-litigated: (1) version identity ships as the content-hash-at-capture fallback, no 300 write-path change; (2) the template content hash is narrowed to exclude the judge: threshold block -- a correctness fix, not a preference, since the current hash resets accumulated n every time an operator acts on a recommendation; (3) residual sampling ships as a policy + offer-selection core, CLI-drained through 320's existing pull-based capture. GraduatedConfig is version-scoped: it carries the full JudgeConfigId (including template_content_hash), not just (template_name, model, artifact_level) -- this is what makes a graduation survive a threshold edit but lapse on a prompt/model edit."
dateCreated: 20260725
dateUpdated: 20260725
status: not_started
---

## Context Summary

- **Working on:** slice 322, the terminal slice of the human-oracle calibration chain. It reads 321's `AgreementReport` and emits an **advisory** `ThresholdRecommendation` per `(ArtifactLevel, JudgeConfigId)` cell — direction plus evidence, never a computed floor. Nothing mutates 300's threshold config automatically. It also ships **residual sampling**: a `GraduatedConfig` registry plus an offer-selection function so a graduated judge keeps producing spot-check data.
- **The hash-narrowing fix must land first.** `identity._template_content_hash` ([identity.py:298-323](../../../src/squadron/metrology/identity.py#L298-L323)) currently hashes `{name, description, system_prompt, model, prompt_template, judge}`. Because `judge` *is* `pass_floor`/`concerns_floor`, acting on a `GRADUATE` recommendation today would change the hash, mint a new `JudgeConfigId`, and reset accumulated `n` to zero — the calibration loop destroying its own evidence every time it succeeds. T1 narrows the hash to `{name, description, system_prompt, model, prompt_template}`. This is a one-time, deliberate re-key of historical records (321's `unversioned`/segregation reporting makes it visible, not silent).
- **Two real threshold surfaces, neither model-keyed.** [judge.py:41-57](../../../src/squadron/pipeline/actions/judge.py#L41-L57) merges per-key: step override → template default (`ReviewTemplate.judge` dict, e.g. `judge-tasks-vs-slice.yaml` → `pass_floor: 78`) → module constants (`_DEFAULT_PASS_FLOOR = 75.0`, `_DEFAULT_CONCERNS_FLOOR = 50.0`). Calibration is `(template, model)`-keyed; config is `(template, step)`-keyed. Every recommendation carries a `model_dimension_note` stating this — never a footnote.
- **Direction bands are asymmetric.** `n < floor` or an unversioned config (`template_content_hash is None`) → `INSUFFICIENT_EVIDENCE`, never `GRADUATE` (floor-gated). `TIGHTEN` is **not** floor-gated — a weak judge is worth flagging on thin evidence. `graduate_floor` / `tighten_ceiling` are config keys (`metrology.graduate_match_rate`, `metrology.tighten_match_rate`), never scattered literals. `metrology.min_evidence_n` is reused from 321, not redefined.
- **Graduation is version-scoped.** `GraduatedConfig` persists the full `JudgeConfigId` (not just `template_name`+`model`), keyed with `artifact_level`, behind 320's `record_type` discriminator (new value `"graduated_config"`, no store migration). `select_residual_offers` matches on that exact identity — a prompt/model edit since graduation means **no offers** under the stale graduation, reported as an explanatory lapse line, never silent.
- **Nothing is written by `recommend` or `offers`.** The only write path in this slice is `sq metrology graduate`, and it writes exactly one record, refusing (non-zero exit) if the named pairing's current recommendation is not `GRADUATE`.
- **Parity + discipline:** `calibration.py` / `graduation.py` / `calibration_models.py` are surface-agnostic (no Typer imports, matching 320/321's pattern verified by test). Strict pyright, ruff clean. No pipeline/gate/dispatch path is touched — 300's judging path and 320's capture path are otherwise unmodified.
- **Dependencies:** 320, 321 — both complete. **Next slice:** none — 322 is terminal for this chain (323/324 are the audit oracle, sharing only 320's spine).
- **Suggested order (from the design, followed here):** hash narrowing first (T1/T2) so everything else accumulates evidence under the corrected key, then models (T3/T4), then config keys (T5/T6), then calibration core (T7-T10), then graduation registry + judge-result discovery + offers (T11-T15), then CLI shells (T16/T17), then end-to-end verification (T18).

---

## Tasks

### T1: Narrow the template content hash to exclude thresholds

- [x] **Edit `src/squadron/metrology/identity.py`, function `_template_content_hash`** ([identity.py:298-323](../../../src/squadron/metrology/identity.py#L298-L323))
  - [x] Remove `"judge": template.judge` from the `behavior` dict that gets hashed
  - [x] Update the function's docstring to state the hash now covers only the judged behavior (`name`, `description`, `system_prompt`, `model`, `prompt_template`) and deliberately excludes the threshold block — thresholds are calibration's output, not part of the instrument
  - [x] Do not touch `derive_result_ref` / `_canonical_projection` (the judge-*result* hash) — this change is scoped to the judge-*configuration* hash only
- [x] Success: `_template_content_hash` for two templates differing only in `judge.pass_floor` returns the **same** hash; for two templates differing in `system_prompt` returns **different** hashes

**Commit:** `fix(metrology): narrow template content hash to exclude threshold block`

---

### T2: Tests for the hash-narrowing regression

- [x] **Extend `tests/metrology/test_identity.py`** (or add if 320 didn't create a dedicated file — check first)
  - [x] **Threshold-only edit does not re-key:** two `ReviewTemplate` fixtures identical except `judge={"pass_floor": 78}` vs `judge={"pass_floor": 85}` → `_template_content_hash` returns the same value for both
  - [x] **Prompt or model edit does re-key:** a fixture differing in `system_prompt` (holding `judge` constant) → different hash; a fixture differing in `model` → different hash
  - [x] **`derive_judge_config_id` end-to-end:** a review file's `JudgeConfigId.template_content_hash` is unchanged after a template's threshold-only edit, and changes after a prompt edit — the actual regression this slice fixes, exercised through the public entry point, not just the private helper
  - [x] **Missing template unchanged:** a `reviewType` that doesn't map to a known template still returns `None` (verify no accidental behavior change from removing the `judge` key)
- [x] Success: `uv run pytest tests/metrology/test_identity.py` passes

**Commit:** `test(metrology): cover hash-narrowing regression on both edit directions`

---

### T3: Calibration and graduation output models

- [x] **Add `src/squadron/metrology/calibration_models.py`** (Pydantic, the stable interface — not console text; mirrors 321's `report_models.py` pattern)
  - [x] `RecommendationDirection(StrEnum)`: `GRADUATE`, `HOLD`, `TIGHTEN`, `INSUFFICIENT_EVIDENCE`
  - [x] `EvidenceSnapshot`: `n: int`, `match_rate: float`, `floor_applied: int`, `below_floor: bool`
  - [x] `ThresholdTarget`: `template_name: str`, `current: JudgeThresholds | None` (absent when the template is unresolvable — never fabricated), `model_dimension_note: str`
  - [x] `ThresholdRecommendation`: `group: GroupKey` (321's), `direction: RecommendationDirection`, `evidence: EvidenceSnapshot`, `target: ThresholdTarget`, `rationale: str`
  - [x] `RecommendationReport`: `cells: list[ThresholdRecommendation]`, `excluded: ExclusionSummary` (321's — pass through verbatim), `floor_applied: int`
  - [x] `GraduatedConfig`: `judge_config: JudgeConfigId`, `artifact_level: ArtifactLevel`, `evidence: EvidenceSnapshot`, `graduated_at: datetime` — carries the **full** `JudgeConfigId` (template_name + model + template_content_hash), per the design's version-scoping decision. Note: defined in `models.py` (not `calibration_models.py`) as a `MetrologyRecord` envelope payload, mirroring the `SampleVerdict` precedent.
  - [x] `OfferTarget`: `review_path: str`, `judge_config: JudgeConfigId`, `reason: Literal["residual-sampling"]`
  - [x] Note: `JudgeThresholds` is a `@dataclass` in `pipeline/actions/judge.py`, not currently a Pydantic model. Either import and use it as-is inside `ThresholdTarget` (dataclasses nest fine in Pydantic v2 models) or wrap it — do not duplicate its fields into a second type
- [x] Success: each model round-trips `model_dump(mode="json")` → `model_validate`; `uv run pyright` passes

**Commit:** `feat(metrology): add calibration and graduation output models`

---

### T4: Tests for calibration/graduation models

- [x] **Add `tests/metrology/test_calibration_models.py`**
  - [x] Every model round-trips through JSON unchanged, including `GraduatedConfig` and `OfferTarget`
  - [x] `ThresholdTarget.current` is `None`-able and the model still validates (the "template no longer registered" case)
  - [x] `RecommendationReport.excluded` is always present (never absent), matching 321's `ExclusionSummary` convention
  - [x] `GraduatedConfig.judge_config` carries `template_content_hash` (not just `template_name`/`model`) — assert the field exists and round-trips, since this is the version-scoping the design requires
- [x] Success: `uv run pytest tests/metrology/test_calibration_models.py` passes

**Commit:** `test(metrology): cover calibration/graduation model round-trip`

---

### T5: Config keys (graduate/tighten/residual rates)

*Sequenced before the calibration-core tasks that read them (matches 321's F004 lesson — no report/calibration task hard-codes a temporary default).*

- [x] **Add three keys to `CONFIG_KEYS` in `src/squadron/config/keys.py`**
  - [x] `metrology.graduate_match_rate` (float) — agreement at/above which, and at/above the evidence floor, a config is recommended `GRADUATE`
  - [x] `metrology.tighten_match_rate` (float) — agreement at/below which a `TIGHTEN` warning is emitted regardless of n
  - [x] `metrology.residual_sample_rate` (float) — fraction of a graduated config's unsampled results offered for continued spot-checking
  - [x] Do **not** redefine `metrology.min_evidence_n` — reuse 321's key as-is (one floor, one definition)
- [x] Success: `sq config list` shows all three keys with descriptions and defaults; `uv run pyright` passes

**Commit:** `feat(metrology): register graduate/tighten/residual-sample config keys`

---

### T6: Tests for the new config keys

- [x] **Extend `tests/metrology/test_config.py`** (320/321's file)
  - [x] All three keys present in `CONFIG_KEYS` with correct types (`float`) and defaults
  - [x] Each reads back as a float; a project-level `.squadron.toml` override is honored (consistent with 320/321's config tests)
- [x] Success: `uv run pytest tests/metrology/test_config.py` passes

**Commit:** `test(metrology): cover graduate/tighten/residual-sample config keys`

---

### T7: Recommendation core — direction classification and current-threshold read

- [x] **Add `src/squadron/metrology/calibration.py`** (surface-agnostic; no Typer imports)
  - [x] `classify_direction(match_rate: float, n: int, floor: int, *, versioned: bool, graduate_rate: float, tighten_rate: float) -> RecommendationDirection` — the floor gates **loosening only** (`GRADUATE`); `TIGHTEN` is checked before the floor applies and fires regardless of `n`. Implement in this literal top-to-bottom precedence (a naive if-elif ordered any other way will make `TIGHTEN` unreachable below the floor — this exact ordering matters, not just the band definitions):
    1. `not versioned` (i.e. `template_content_hash is None`) → `INSUFFICIENT_EVIDENCE` (never graduate on un-keyable evidence, regardless of n or match rate)
    2. `match_rate <= tighten_rate` → `TIGHTEN` (checked **before** the floor test — this is what makes tightening non-floor-gated: a below-floor cell with a low match rate must reach this case, not fall into case 3)
    3. `n < floor` → `INSUFFICIENT_EVIDENCE` (the floor gates only what's left: graduating or holding)
    4. `n >= floor and match_rate >= graduate_rate` → `GRADUATE`
    5. otherwise → `HOLD`
  - [x] Re-read the design's Direction Bands table before implementing — the floor gates **loosening** (`GRADUATE`) only; `TIGHTEN` fires regardless of evidence volume, so the precedence above must let a low-n, low-match-rate cell reach `TIGHTEN` rather than stopping at `INSUFFICIENT_EVIDENCE`
  - [x] `read_current_thresholds(template_name: str) -> JudgeThresholds | None`: look up the template via `squadron.review.templates.get_template`, call `resolve_thresholds(template.judge, None)` (step-level override is not knowable outside a specific step context, so pass `None` — this reads the *template's* configured floor, which is what the recommendation is a delta from); return `None` if the template is not registered — never fabricate a threshold, log WARNING naming the template name. Malformed judge block (non-numeric threshold values) is handled via a local try/except around `resolve_thresholds`, returning `None` + WARNING, rather than propagating a raised exception from `resolve_thresholds` itself.
- [x] Success: each band's boundary condition (`n` exactly at `floor`, `match_rate` exactly at `graduate_rate`/`tighten_rate`) resolves per the precedence rules above; a below-floor cell with low match rate returns `TIGHTEN`, not `INSUFFICIENT_EVIDENCE`; an unresolvable template returns `None` from `read_current_thresholds` with a WARNING logged, never raises

**Commit:** `feat(metrology): add direction classification and current-threshold read`

---

### T8: Tests for direction classification and threshold read

- [x] **Add `tests/metrology/test_calibration.py`**
  - [x] Parametrized test over every direction band, including boundary values (`n == floor`, `match_rate == graduate_rate`, `match_rate == tighten_rate`)
  - [x] **Loosening is floor-gated:** `n < floor` with a high match rate never returns `GRADUATE`
  - [x] **Tightening is not floor-gated:** `n < floor` with a low match rate returns `TIGHTEN`, not `INSUFFICIENT_EVIDENCE` (the regression this task's design explicitly calls out)
  - [x] **Unversioned refusal:** `versioned=False` with `n >= floor` and a high match rate still returns `INSUFFICIENT_EVIDENCE`, never `GRADUATE`
  - [x] `read_current_thresholds` for a registered template returns the template's actual `pass_floor`/`concerns_floor` (via `resolve_thresholds`); for an unregistered template name returns `None` and logs a WARNING (assert via `caplog`)
  - [x] **Malformed judge block:** a template whose `judge` dict has a non-numeric `pass_floor` (e.g. a string) — `read_current_thresholds` delegates to a local try/except around `resolve_thresholds`, catching any raised exception from malformed input, and returns `None` + WARNING — no raised exception surfaces to the caller (assert via `caplog`, matching the slice design's Failure Modes treatment: degraded-to-warning behavior, not escalated error)
- [x] Success: `uv run pytest tests/metrology/test_calibration.py` passes

**Commit:** `test(metrology): cover direction bands, floor asymmetry, unversioned refusal`

---

### T9: `recommend_thresholds` — the full recommendation report

- [x] **Extend `calibration.py`** with `recommend_thresholds(agreement: AgreementReport, *, floor: int, graduate_rate: float, tighten_rate: float) -> RecommendationReport`
  - [x] For each `AgreementCell` in `agreement.cells`: classify its direction (T7), read its template's current thresholds, build a `ThresholdRecommendation` carrying the cell's `GroupKey`, an `EvidenceSnapshot` (`n`, `match_rate`, `floor_applied=floor`, `below_floor` from the cell), the `ThresholdTarget` (current thresholds + `model_dimension_note`), and a short `rationale` string naming the direction and evidence
  - [x] `model_dimension_note` states plainly that the recommendation holds for **this template paired with this model**, and that acting on it means choosing model and threshold together at config time — this is not optional per-cell text, every cell gets one
  - [x] Pass `agreement.excluded` through verbatim into `RecommendationReport.excluded` (321's convention — exclusions are never mistaken for absence of evidence)
  - [x] An empty `agreement.cells` list yields an empty `RecommendationReport` with the `excluded` summary and `floor_applied` still stated — honest, not an error
  - [x] **No mutation:** this function reads `AgreementReport` and template state; it must not write to the store, a template file, or config — this is asserted by test (T10) and is the architecture's core discipline for this slice
- [x] Success: a fixture `AgreementReport` with cells at multiple levels/configs yields one `ThresholdRecommendation` per cell, each with a non-empty `model_dimension_note`; an empty agreement report yields an empty `RecommendationReport`, not a crash

**Commit:** `feat(metrology): add recommend_thresholds producing per-cell advisory recommendations`

---

### T10: Tests for `recommend_thresholds`, including the no-mutation assertion

- [x] **Add `tests/metrology/test_calibration_recommend.py`**
  - [x] Multi-cell fixture → one `ThresholdRecommendation` per `AgreementCell`, never a single blended recommendation
  - [x] Every recommendation carries a non-empty `model_dimension_note`
  - [x] A cell whose template is unregistered → `ThresholdTarget.current is None`, no exception, WARNING logged naming the template
  - [x] **No-mutation assertion:** snapshot the template YAML file, any `.squadron.toml` config, and the metrology store directory (bytes) before and after calling `recommend_thresholds` → byte-identical (the architecture's Non-Goal, verified by test per the slice design's explicit call for this)
  - [x] Empty `AgreementReport` → empty `RecommendationReport`, `excluded` zeroed, `floor_applied` still set
- [x] Success: `uv run pytest tests/metrology/test_calibration_recommend.py` passes

**Commit:** `test(metrology): cover recommendation report shape and no-mutation invariant`

---

### T11: Graduated-config registry — record type and store integration

- [x] **Add `src/squadron/metrology/graduation.py`** (surface-agnostic; no Typer imports)
  - [x] Add `RECORD_TYPE_GRADUATED_CONFIG = "graduated_config"` alongside 320's `RECORD_TYPE_SAMPLE` / `RECORD_TYPE_AUDIT_FINDING` constants in `models.py` (extend that module, do not redefine the discriminator pattern elsewhere)
  - [x] Extend `MetrologyRecord` in `src/squadron/metrology/models.py` with an optional `graduated_config: GraduatedConfig | None = None` field, matching the existing `sample: SampleVerdict | None` pattern — this is 320's reserved extension point, so no schema version bump. Note: `GraduatedConfig` is defined in `models.py` (not `calibration_models.py`) to avoid circular imports, since `calibration_models.py` already imports from `models.py` and `GraduatedConfig` is a `MetrologyRecord` envelope payload.
  - [x] `write_graduation(store: MetrologyStore, graduated: GraduatedConfig) -> str`: envelope and persist via the store's existing atomic-write path (extend `MetrologyStore` with this method, mirroring `write_sample`); returns a generated record id
  - [x] `find_graduation(store: MetrologyStore, judge_config: JudgeConfigId, level: ArtifactLevel) -> GraduatedConfig | None`: scan stored `graduated_config` records for one matching **the exact `JudgeConfigId`** (including `template_content_hash`) and `artifact_level` — used for both the idempotent-update path and `select_residual_offers`
  - [x] `list_graduations(store: MetrologyStore) -> list[GraduatedConfig]`: all graduated-config records, tolerantly skipping unreadable siblings with a WARNING (mirrors `list_samples`' existing tolerance — do not duplicate that skip logic, extract a shared helper if `MetrologyStore` doesn't already expose one)
- [x] Success: writing then listing a `GraduatedConfig` round-trips; `find_graduation` matches only on the full `JudgeConfigId` (a differing `template_content_hash` with identical `template_name`/`model` does **not** match); an unreadable sibling record does not sink `list_graduations`

**Commit:** `feat(metrology): add graduated-config registry with version-scoped matching`

---

### T12: Tests for the graduated-config registry

- [x] **Add `tests/metrology/test_graduation_registry.py`**
  - [x] Write then read back a `GraduatedConfig` — round-trips through the store unchanged
  - [x] `find_graduation` matches a config with identical `JudgeConfigId` + `artifact_level`
  - [x] **Version-scoping regression:** two `JudgeConfigId`s sharing `template_name`+`model` but differing `template_content_hash` → `find_graduation` for one does **not** return the other's record (the F002 review-fix regression: a graduation must not silently transfer across a prompt edit)
  - [x] `list_graduations` tolerates a corrupt sibling file (WARNING, skipped, other records still returned) — mirrors 320's store tolerance test
- [x] Success: `uv run pytest tests/metrology/test_graduation_registry.py` passes

**Commit:** `test(metrology): cover graduated-config round-trip and version-scoped matching`

---

### T13: Judge-result discovery surface (dependency resolution)

*Confirmed gap, not a runtime judgment call: 320 has no whole-project "enumerate persisted judge results" surface. `capture.resolve_target` only resolves one target given an already-known slice index (a `reviews_dir.glob(f"{index}-review.*")` scoped to one index); there is no function that lists every judge review file across `project-documents/user/reviews/` so residual sampling can diff against what's already been sampled. This task builds that surface before T14 needs it, rather than leaving the choice to the implementer.*

- [x] **Add `discover_judge_results(cwd: str) -> list[Path]` to `src/squadron/metrology/discovery.py`** (new file, since `capture.py` was already at 256 lines — close enough to the task's own ~300-line threshold that a new file was the safer choice)
  - [x] Glob `project-documents/user/reviews/` (using the public `REVIEWS_SUBDIR` constant, renamed from private `_REVIEWS_SUBDIR` in `capture.py` for reuse) for all review files, not just one index's candidates
  - [x] For each candidate, read frontmatter (`read_review_frontmatter`) and keep only files that are **judge** results — i.e. whose `reviewType`'s resolved template `is_judge` (has a `judge:` block) — skip non-judge reviews (arch/tasks/code reviews with no judge template) without erroring
  - [x] Malformed / unreadable frontmatter → skip that file, log WARNING naming the path (mirrors `store.list_samples`' tolerant-skip convention) — one bad review file must not sink the whole discovery pass
  - [x] Return the file paths only; deriving each one's `JudgeConfigId` is `select_residual_offers`' job (T14), not this function's — keep this surface a pure enumeration
- [x] Success: a fixture reviews directory with a mix of judge and non-judge review files returns only the judge ones; a corrupt sibling file is skipped with a WARNING, not an exception

**Commit:** `feat(metrology): add judge-result discovery surface for residual sampling`

---

### T13b: Tests for judge-result discovery

- [x] **Add `tests/metrology/test_capture_discovery.py`**
  - [x] Mixed fixture (judge + non-judge review files) → only judge results returned
  - [x] Corrupt/unreadable review file → skipped, WARNING logged, other results still returned
  - [x] Empty reviews directory → empty list, no exception
- [x] Success: `uv run pytest tests/metrology/test_capture_discovery.py` passes

**Commit:** `test(metrology): cover judge-result discovery enumeration and tolerance`

---

### T14: `select_residual_offers` — offer selection over unsampled results

- [x] **Extend `graduation.py`** with `select_residual_offers(store: MetrologyStore, graduated: list[GraduatedConfig], *, rate: float, cwd: str) -> list[OfferTarget]`
  - [x] Call `discover_judge_results(cwd)` (T13) to enumerate persisted judge review files; for each, derive its `JudgeConfigId` (`identity.derive_judge_config_id`) and compare against each `GraduatedConfig`'s exact identity
  - [x] A matching result is **unsampled** when no `SampleVerdict` in the store has a `result_ref` pointing at it (cross-reference `store.list_samples()`); select a `rate` fraction of the unsampled matches as `OfferTarget`s (`reason="residual-sampling"`)
  - [x] **Lapsed graduation:** if a `GraduatedConfig`'s `JudgeConfigId` no longer matches any current judge result (the underlying template/model has since changed), it contributes **zero** offers and this must be distinguishable from "config not yet due for sampling" at the CLI layer (T16) — return enough information (or have the CLI re-derive it via `find_graduation` against current results) to report the lapse explicitly, never silently
  - [x] **Testable guarantee:** given a `GraduatedConfig` with unsampled matching results, this function returns a **non-empty** offer set — the architecture's explicit "agreement data does not freeze" commitment
  - [x] An exhausted config (no unsampled results, but still current) yields an empty list for that config — distinct from the lapsed case above
- [x] Success: a graduated config with 3 unsampled matching results at `rate=1.0` yields 3 `OfferTarget`s; a graduated config with a since-edited template yields zero offers distinguishably from an exhausted one; the non-empty-offers guarantee holds under a passing test

**Commit:** `feat(metrology): add residual-offer selection with lapsed-graduation detection`

---

### T15: Tests for residual-offer selection

- [x] **Add `tests/metrology/test_graduation_offers.py`**
  - [x] **Non-empty guarantee:** a graduated config with unsampled matching results → `select_residual_offers` returns at least one `OfferTarget` (the architecture commitment, asserted directly)
  - [x] **Exhausted config:** all matching results already sampled → empty offer list, no error
  - [x] **Lapsed graduation:** template edited post-graduation (new `JudgeConfigId`, prompt/model dimension differs) → zero offers under the stale graduation, and the lapse is distinguishable from the exhausted case (assert on whatever signal T14 produces for this — a return-value field, a paired lookup, or a logged WARNING naming the config-identity change)
  - [x] **Pruned review file:** a matching judge result's review file has been deleted since graduation → that target is skipped, counted (not silently dropped), WARNING logged naming the path
  - [x] `rate` fraction is honored (e.g. `rate=0.5` over 4 unsampled results selects 2, not all 4)
- [x] Success: `uv run pytest tests/metrology/test_graduation_offers.py` passes

**Commit:** `test(metrology): cover offer selection guarantee, lapse, and pruned-file cases`

---

### T16: CLI — `recommend`, `graduate`, `offers`

- [ ] **Extend `src/squadron/cli/commands/metrology.py`** with three new commands (thin shells, all logic in `calibration.py`/`graduation.py`, matching the existing `report` sub-group pattern)
  - [ ] `sq metrology recommend [--project ID] [--level LEVEL] [--json] [--cwd .]`: build the store's `AgreementReport` (reuse `agreement_report`, do not re-aggregate), call `recommend_thresholds` with rates read from `metrology.graduate_match_rate` / `metrology.tighten_match_rate` / `metrology.min_evidence_n`, render one row per cell (direction, match rate + n, floor applied, current thresholds, model-dimension note); `INSUFFICIENT_EVIDENCE` cells state both n and floor, never render blank; `--json` emits `RecommendationReport` verbatim
  - [ ] `sq metrology graduate --template T --model M --level L [--cwd .]`: look up the pairing's current recommendation (re-derive via the same path as `recommend`, filtered to this template/model/level); if the direction is not `GRADUATE`, exit non-zero with a message naming the observed n and floor — **write nothing**; otherwise construct a `GraduatedConfig` (full `JudgeConfigId` including `template_content_hash`, the `EvidenceSnapshot` that justified it, `graduated_at=now`) and call `write_graduation`; if a `GraduatedConfig` for this exact identity already exists, update its evidence snapshot in place (idempotent — one record, not two, log INFO)
  - [ ] `sq metrology offers [--project ID] [--json] [--cwd .]`: `list_graduations`, call `select_residual_offers` with `rate` from `metrology.residual_sample_rate`, render each `OfferTarget`; when a graduated config yields zero offers **because it has lapsed**, print an explanatory line naming the config-identity change — never a silent empty result indistinguishable from "nothing due"
  - [ ] All three commands follow the existing `--cwd`/`--project`/store-construction + `MetrologyStoreError`/`MetrologyTargetError` handling already used by `sample`/`list`/`report *` — no new error-handling pattern
  - [ ] `recommend` and `offers` are read-only; `graduate` writes exactly one record
- [ ] Success: `sq metrology --help` lists `recommend`, `graduate`, `offers`; `recommend` on a fixture store prints per-cell rows including the model-dimension note; `graduate` on a non-`GRADUATE` pairing exits non-zero and writes nothing; `offers` reports a lapsed graduation with an explanatory line, not silence

**Commit:** `feat(cli): add sq metrology recommend/graduate/offers`

---

### T17: CLI tests — commands, `--json`, refusal, idempotence, no-mutation

- [ ] **Add `tests/metrology/test_calibration_cli.py`** using Typer's `CliRunner` (mirrors 321's `test_report_cli.py`)
  - [ ] `recommend` prints per-cell rows with n, floor, and model-dimension note; `--json` parses back to `RecommendationReport`
  - [ ] `graduate` on a pairing below the floor exits non-zero, message names n and floor, **store record count unchanged**
  - [ ] `graduate` on a pairing meeting `GRADUATE` succeeds, writes exactly one `graduated_config` record
  - [ ] **Idempotent re-graduate:** running `graduate` again for the same pairing updates the evidence snapshot without creating a second record (assert record count stays at 1)
  - [ ] `offers` on a store with a graduated config and unsampled matches lists at least one offer; on a lapsed graduation prints the explanatory line and zero offers for that config
  - [ ] **No-mutation regression at the CLI layer:** SHA-1 the template YAML, `.squadron.toml`, and store dir before/after a `recommend` run → byte-identical (mirrors T10's unit-level assertion, re-verified through the CLI entry point)
  - [ ] **Surface-agnostic core:** assert `squadron.metrology.calibration` / `graduation` / `calibration_models` import no Typer (mirrors 320/321's parity test)
- [ ] Success: `uv run pytest tests/metrology/test_calibration_cli.py` passes

**Commit:** `test(metrology): cover recommend/graduate/offers CLI, refusal, idempotence, no-mutation`

---

### T18: Full validation, regression gate, and verification walkthrough

- [ ] **Run the full suite:** `uv run pytest` (entire repo) — 300 judging path, 320 capture path, 321 reporting path, and all existing tests pass unchanged except the deliberate hash-narrowing re-key (T1/T2)
- [ ] **Run static checks:** `uv run pyright` and `uv run ruff check` — zero errors on new code; `uv run ruff format` before commit
- [ ] **Execute the LLD Verification Walkthrough** (slice design, steps 1-9) end-to-end in a scratch repo and paste the actual output back into the slice design or a companion note:
  1. Accumulate agreement evidence *(existing)*
  2. `recommend` below the floor → `INSUFFICIENT_EVIDENCE` stating n and floor
  3. `recommend` above the floor → `GRADUATE` with match rate, n, floor, current thresholds, model-dimension note
  4. SHA-1 template/config/store before and after `recommend` → byte-identical
  5. **The self-defeating-loop regression:** edit `judge.pass_floor` → same `JudgeConfigId`, same n (re-run `report agreement`); edit `system_prompt` → new `JudgeConfigId`, evidence separates
  6. `graduate` then `offers` → graduation recorded, residual targets listed; drain one via `sq metrology sample`, confirm n increased for the graduated judge
  7. **Version-scoping regression:** edit `system_prompt` post-graduation, produce a new judge review under it, `offers` → no offers drawn against the new config under the old graduation, lapse reported
  8. `graduate` on a below-floor pairing → non-zero exit naming n/floor, no store record written
  9. Full suite green, 300/320/321 behavior unchanged
- [ ] Success: all nine walkthrough steps pass with pasted output; full suite green; static checks clean; mark this slice-design's frontmatter `status: complete` and update the 320 slice-plan's `(322)` entry to `[x]` if this completes it

**Commit:** `test(metrology): full validation pass for 322 calibration-to-threshold feedback`

---

## Coverage Check (design → tasks)

- Hash-narrowing correctness fix (the self-defeating-loop fix) → T1/T2, re-verified at CLI/walkthrough level (T17, T18 step 5).
- Calibration/graduation output models (`RecommendationDirection`, `EvidenceSnapshot`, `ThresholdTarget`, `ThresholdRecommendation`, `RecommendationReport`, `GraduatedConfig`, `OfferTarget`) → T3/T4.
- New config keys (`graduate_match_rate`, `tighten_match_rate`, `residual_sample_rate`), sequenced before the tasks that read them → T5/T6.
- Direction classification (floor-gated loosening, non-floor-gated tightening — precedence corrected per tasks-review F001: unversioned, then tighten, then the floor gates only graduate/hold — unversioned refusal, malformed judge block) + current-threshold read → T7/T8.
- Full recommendation report, per-cell model-dimension note, exclusion pass-through, no-mutation discipline → T9/T10.
- Graduated-config registry, version-scoped matching (full `JudgeConfigId`, not the looser triple — the slice-review F002 fix) → T11/T12.
- Judge-result discovery surface (dependency resolved per tasks-review F003: 320 had no whole-project judge-result enumeration, so this task builds one rather than leaving the gap to the implementer) → T13/T13b.
- Residual-offer selection, the non-empty-offers architecture guarantee, lapsed-graduation detection, pruned-file handling → T14/T15.
- CLI `recommend`/`graduate`/`offers` shells, `--json`, graduate refusal + idempotence → T16/T17.
- Full validation, static checks, and the nine-step verification walkthrough (including both hash-narrowing-direction and version-scoping regressions) → T18.
- **Failure Modes table (all rows)** covered: empty evidence (T9/T10); floor refusal (T7/T8); unversioned refusal (T7/T8); unresolvable template (T7/T9/T10); malformed judge block (T7, tested explicitly in T8 per tasks-review F002); graduate refusal / idempotence (T16/T17); exhausted / pruned / lapsed offers (T14/T15); hash-narrowing one-time re-key (T1/T2, T18 step 5).
- Deferred by design, correctly absent here: any automatic threshold mutation; a new gating mechanism; the coordinated 300 write-path version field (320-plan Future Work #1, still open); persisting the judge verdict onto the sample (321 Future Work #2); audit-oracle work (323/324); any change to 300's judging path or 320's capture path beyond the T1 hash narrowing.
- **Tasks review (20260725, kimi-k2.7-code) fixes applied:** F001 (T7 precedence corrected so `TIGHTEN` is reachable below the evidence floor) · F002 (T8 malformed-judge-block test added) · F003 (T13/T13b added: judge-result discovery surface built explicitly rather than left as an implementer's runtime choice).
