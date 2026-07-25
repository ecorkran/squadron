---
docType: tasks
slice: agreement-dispersion-reporting
project: squadron
lld: ../slices/321-slice.agreement-dispersion-reporting.md
dependencies:
  - 320 metrology-data-layer-sample-capture-keystone (complete) — MetrologyStore (list_samples/count_samples/load_record), SampleVerdict/JudgeResultRef/JudgeConfigId/ProjectId models, resolve_store_dir, identity.read_review_frontmatter + derive_result_ref + SOURCE_DOC_KEY, config keys, cli/commands/metrology.py sub-app
projectState: "Initiative 320 keystone complete: user-level metrology store at ~/.config/squadron/metrology/ (flat per-record JSON, StateManager shape — atomic write, schema version, glob-and-filter, no DB). SampleVerdict records carry human_verdict, result_ref (project_id/relative_review_path/content_hash), judge_config (JudgeConfigId), captured_at, blind, and an always-None artifact_level hook. The judge's own verdict is NOT on the sample — it lives in the referenced 300 review file (read via identity.read_review_frontmatter). 300 multi-sample judging (Future Work #1) has NOT shipped: one ReviewResult per review file, so no repeated same-config judgments exist. sq metrology sample/list CLI ships; report commands do not. Slice design PASS-reviewed (321-review.slice.*, 8/8 findings PASS)."
dateCreated: 20260723
dateUpdated: 20260723
status: not_started
---

## Context Summary

- **Working on:** slice 321, the human oracle's headline analysis over the sample 320 accumulates. Build a **pure read-and-aggregate layer** over 320's `MetrologyStore` that reports **agreement** (judge-vs-human), **dispersion** (judge-vs-judge), and **trend**, always at the **per-artifact-level / per-judge-configuration** grain, every figure carrying its **n**. No new store engine, no capture change, no judging-path change.
- **Two load-bearing facts from the LLD (do not re-guess):**
  1. **`SampleVerdict.artifact_level` is always `None` today** (320 left it a reserved hook; no vocabulary exists). 321 defines an `ArtifactLevel` enum and derives it **at report time** from each sample's recorded `reviewType` — backfilling historical `None` records with **no store migration**. Unmappable types → an explicit `UNCLASSIFIED` bucket, never dropped.
  2. **The judge's verdict is not on the sample.** Agreement joins each sample back to the judge verdict by **re-reading the referenced review file** (`result_ref.relative_review_path`) via 320's `read_review_frontmatter`, and **verifying `result_ref.content_hash`**: match ⇒ admissible; mismatch/missing/malformed ⇒ excluded as `stale-judge-result` (counted, never joined to a stale verdict).
- **Two distinct join keys (LLD "Artifact identity vs. result-file identity", slice-review F001):**
  - **Agreement / trend** group on `(ArtifactLevel, JudgeConfigId)` and bind to the exact result via `result_ref`.
  - **Dispersion** groups on **artifact identity** `(project_id, source_document, ArtifactLevel)` — *not* `result_ref` (which differs per config). `source_document` is the review's `sourceDocument` frontmatter (`identity.SOURCE_DOC_KEY`), read in the same pass as the agreement join.
- **Dispersion scope:** ships **cross-configuration** dispersion (distinct model/template on one artifact — data the store already holds). The **same-configuration** repeated-measurement path is built and tested against fixtures but **inert until 300 FW#1 lands**. **No 180 `fan_out` dependency** is introduced (asserted by test).
- **Comparability:** group on the whole `JudgeConfigId`; unversioned records (`template_content_hash is None`) are **flagged/segregated**, never pooled with hash-bearing same-name records.
- **Small-n honesty:** naive percent agreement with **n always shown** and a `below_floor` flag when `n < metrology.min_evidence_n` — *not* a chance-corrected coefficient that misbehaves at small n. The floor is **reported** here; 322 consumes it.
- **Store backend:** the LLD-inherited SQLite-vs-flat-file revisit resolves to **keep flat-file** (in-memory group-by over a small sample doesn't strain glob-and-filter). No engine change in this slice.
- **Parity:** a surface-agnostic core (`squadron.metrology.report`, `levels`, `report_models`) with **no Typer imports**; the CLI `report` sub-group is a thin shell (the `config.py`/320 pattern).
- **Discipline:** read-only over the store and review files — enforced by test (store bytes unchanged after every report command). 300/320 behavior unchanged; strict pyright + ruff; config values centralized in `CONFIG_KEYS`; the `ArtifactLevel` vocabulary defined **once**.
- **Task ordering note:** config keys (`metrology.min_evidence_n`, `metrology.trend_bucket`) are added **before** the report-computation tasks that read them (T5/T6), so no report task hard-codes a temporary default (slice-review F004).
- **Dependencies:** 320 — complete. **Next slice:** 322 (Calibration-to-Threshold Feedback), which consumes `AgreementReport` (with `below_floor` + `ExclusionSummary`) and finalizes the version key.

---

## Tasks

### T1: Artifact-level vocabulary and derivation

- [ ] **Add `src/squadron/metrology/levels.py`** — the single definition of the artifact-level vocabulary (CLAUDE.md: comparison values defined once)
  - [ ] `ArtifactLevel(StrEnum)` with members `TASKS_VS_SLICE`, `SLICE_DESIGN_VS_ARCH`, `ARCH_VS_CONCEPT`, `UNCLASSIFIED`
  - [ ] `derive_artifact_level(review_type: str) -> ArtifactLevel` mapping the review types the code actually produces (per the LLD table): `judge.tasks-vs-slice` / `tasks` → `TASKS_VS_SLICE`; `judge.slice-vs-arch` / `slice` → `SLICE_DESIGN_VS_ARCH`; `arch` → `ARCH_VS_CONCEPT`; anything else / empty → `UNCLASSIFIED`
  - [ ] The mapping is a module-level constant dict (not scattered conditionals); `UNCLASSIFIED` is the explicit fallthrough, never a silent drop or a raised error
- [ ] Success: `derive_artifact_level("judge.slice-vs-arch") == ArtifactLevel.SLICE_DESIGN_VS_ARCH`; an unknown string returns `UNCLASSIFIED`; `uv run pyright` passes

**Commit:** `feat(metrology): add ArtifactLevel vocabulary and derivation`

---

### T2: Tests for artifact-level derivation

- [ ] **Add `tests/metrology/test_levels.py`**
  - [ ] Each known review type (both the `judge.*` and bare forms) maps to its expected `ArtifactLevel` (parametrized)
  - [ ] An unknown / empty review type maps to `ArtifactLevel.UNCLASSIFIED` (not an error)
  - [ ] `arch-vs-concept` has no judge template today, but `arch` maps to `ARCH_VS_CONCEPT` (the vocabulary is complete for future arch-concept judging)
- [ ] Success: `uv run pytest tests/metrology/test_levels.py` passes

**Commit:** `test(metrology): cover artifact-level derivation and UNCLASSIFIED fallthrough`

---

### T3: Report models (the typed shape 322 consumes)

- [ ] **Add `src/squadron/metrology/report_models.py`** (Pydantic, the stable interface 322 reads — not console text)
  - [ ] `GroupKey`: `artifact_level: ArtifactLevel`, `judge_config: JudgeConfigId`
  - [ ] `AgreementCell`: `group: GroupKey`, `n: int`, `match_rate: float`, `below_floor: bool`
  - [ ] `ArtifactKey`: `project_id: str`, `source_document: str`, `artifact_level: ArtifactLevel` (dispersion's group key — the artifact, not the review-file instance)
  - [ ] `DispersionCell`: `artifact: ArtifactKey`, `judge_configs: list[JudgeConfigId]`, `n: int`, `disagreement_rate: float`
  - [ ] `ExclusionSummary`: `total_excluded: int`, `stale_judge_result: int`, `unversioned: int`
  - [ ] `AgreementReport`: `cells: list[AgreementCell]`, `excluded: ExclusionSummary`
  - [ ] `DispersionReport`: `cells: list[DispersionCell]`, `excluded: ExclusionSummary`
  - [ ] `TrendReport`: `bucket: str`, `series: list[...]` of `(bucket_label, AgreementReport | DispersionReport)`
- [ ] Success: each model round-trips `model_dump(mode="json")` → `model_validate`; `uv run pyright` passes

**Commit:** `feat(metrology): add agreement/dispersion/trend report models`

---

### T4: Tests for report models

- [ ] **Add `tests/metrology/test_report_models.py`**
  - [ ] Every report model round-trips through JSON unchanged
  - [ ] `ExclusionSummary` counts are non-negative ints; `AgreementReport`/`DispersionReport` always carry an `excluded` field (never absent)
  - [ ] `ArtifactKey` distinguishes two artifacts with the same level but different `source_document` (equality / hashing suitable for use as a group key)
- [ ] Success: `uv run pytest tests/metrology/test_report_models.py` passes

**Commit:** `test(metrology): cover report model round-trip and grouping keys`

---

### T5: Config keys (floor and trend bucket)

*Sequenced before the report-computation tasks so those tasks read real keys, never a hard-coded temporary default (slice-review F004).*

- [ ] **Add two keys to `CONFIG_KEYS` in `src/squadron/config/keys.py`** (centralized, never hard-coded at a call site)
  - [ ] `metrology.min_evidence_n` (int, small default e.g. a handful) — the minimum-evidence floor; a cell with `n < min_evidence_n` is marked `below_floor`. Reported here; consumed by 322
  - [ ] `metrology.trend_bucket` (str, default e.g. `month`) — default time-bucket grain for `report trend` (`--bucket` overrides)
- [ ] Success: `sq config list` shows both keys with descriptions and defaults; `uv run pyright` passes

**Commit:** `feat(metrology): register min-evidence-floor and trend-bucket config keys`

---

### T6: Tests for config keys

- [ ] **Extend `tests/metrology/test_config.py`** (the file 320 created)
  - [ ] Both keys present in `CONFIG_KEYS` with correct types and defaults
  - [ ] `metrology.min_evidence_n` reads back as an int; `metrology.trend_bucket` reads back as a str; project-level override via `.squadron.toml` is honored (consistent with 320's config tests)
- [ ] Success: `uv run pytest tests/metrology/test_config.py` passes

**Commit:** `test(metrology): cover report config keys`

---

### T7: Sample enrichment (join + classify, single pass)

- [ ] **Add `src/squadron/metrology/report.py`** with the shared enrichment pass (surface-agnostic; no Typer imports)
  - [ ] Define an internal `EnrichedSample` (`@dataclass`) carrying: the `SampleVerdict`, derived `ArtifactLevel`, the joined judge `Verdict | None`, the resolved `source_document: str | None`, and an admissibility flag (`admissible` / `stale-judge-result` / `unversioned`)
  - [ ] `enrich_samples(samples: list[SampleVerdict], cwd: str) -> list[EnrichedSample]`: for each sample, **one** frontmatter read of the referenced review file (`read_review_frontmatter` on `result_ref.relative_review_path` resolved under `cwd`) that yields **both** the judge verdict (agreement) and `sourceDocument` (dispersion key)
  - [ ] **Content verification:** re-derive the result hash (`derive_result_ref`) and compare to `result_ref.content_hash`. Mismatch, missing file, or unparseable/verdict-less frontmatter → mark `stale-judge-result`, judge verdict `None`, and log WARNING naming the path — never join a stale/absent verdict
  - [ ] Derive `ArtifactLevel` from the sample's recorded review type (via `levels.derive_artifact_level`)
  - [ ] Mark `unversioned` when `judge_config.template_content_hash is None`
- [ ] Success: an admissible sample enriches with its judge verdict + `source_document` + level; a sample whose review file was changed since capture enriches as `stale-judge-result` with verdict `None`; a missing `sourceDocument` leaves `source_document=None` (still admissible for agreement)

**Commit:** `feat(metrology): add sample enrichment with content-verified judge join`

---

### T8: Tests for enrichment (the load-bearing join)

- [ ] **Add `tests/metrology/test_report_enrich.py`** (build on `tests/metrology/conftest.py` fixtures — `write_review_file`, `make_sample_verdict`)
  - [ ] Admissible: sample + unchanged review file → enriched with the correct judge verdict, `source_document`, and derived level
  - [ ] **Stale (overwritten):** re-write the referenced review file so its content hash changes → sample enriches as `stale-judge-result`, verdict `None`, WARNING logged
  - [ ] **Missing file:** referenced review file absent → `stale-judge-result`, verdict `None`, WARNING
  - [ ] **Malformed / verdict-less frontmatter:** referenced file present but frontmatter unparseable or missing the verdict field → `stale-judge-result`, verdict `None`, WARNING (Failure Modes "unparseable frontmatter" row — slice-review F005)
  - [ ] **Missing `sourceDocument`:** review file present but no `sourceDocument` → `source_document=None`, still admissible for agreement (WARNING per the failure-mode row)
  - [ ] **Unversioned:** `judge_config.template_content_hash is None` → flagged `unversioned`
- [ ] Success: `uv run pytest tests/metrology/test_report_enrich.py` passes

**Commit:** `test(metrology): cover enrichment join, staleness, malformed, and exclusion flags`

---

### T9: Agreement report

- [ ] **Extend `report.py`** with `agreement_report(samples: list[SampleVerdict], cwd: str) -> AgreementReport`
  - [ ] Enrich (T7), then keep only **admissible** samples (exclude `stale-judge-result` from the match computation; count them in `ExclusionSummary.stale_judge_result`)
  - [ ] Group admissible samples by `GroupKey(ArtifactLevel, JudgeConfigId)`; **never** collapse to a single blended cell
  - [ ] Per group: `n` = count; `match_rate` = fraction where `sample.human_verdict == joined judge verdict` (exact `Verdict` equality, no partial credit); `below_floor` = `n < metrology.min_evidence_n` (read via `config.manager`, `cwd`-aware — the key exists from T5)
  - [ ] Comparability: distinct `JudgeConfigId`s are distinct groups; `unversioned` records are grouped by `(template_name, model)` but **segregated/flagged** from hash-bearing same-name records (counted in `ExclusionSummary.unversioned`), never pooled
  - [ ] Populate `ExclusionSummary` (`total_excluded`, `stale_judge_result`, `unversioned`); an empty sample list yields an empty-cells report with a zeroed summary (honest, not an error)
- [ ] Success: a multi-level, multi-config fixture store yields **multiple** `AgreementCell`s (never one aggregate), each with its n; low-n cells carry `below_floor=True`; a stale/overwritten sample is excluded and counted; a zero-sample store yields an empty report, not a crash

**Commit:** `feat(metrology): add per-level/per-config agreement report`

---

### T10: Tests for agreement report

- [ ] **Add `tests/metrology/test_report_agreement.py`**
  - [ ] **No blended metric:** a store with two levels × two configs yields ≥ (levels×configs) cells, never a single "agreement" number
  - [ ] `match_rate` and `n` correct for a hand-built fixture (agree/disagree mix)
  - [ ] `below_floor` set exactly when `n < metrology.min_evidence_n`
  - [ ] Stale sample (overwritten review file) excluded from `match_rate`, counted in `excluded.stale_judge_result`
  - [ ] Unversioned record segregated from a hash-bearing same-name+model record, counted in `excluded.unversioned` — not pooled
  - [ ] **Empty store:** zero samples → `AgreementReport` with no cells and a zeroed `ExclusionSummary`, no exception (Failure Modes "empty evidence" row — slice-review F006)
- [ ] Success: `uv run pytest tests/metrology/test_report_agreement.py` passes

**Commit:** `test(metrology): cover agreement grouping, floor, exclusions, empty store`

---

### T11: Dispersion report (artifact-identity keyed)

- [ ] **Extend `report.py`** with `dispersion_report(samples: list[SampleVerdict], cwd: str) -> DispersionReport`
  - [ ] Enrich (T7); group admissible samples by **artifact identity** `ArtifactKey(project_id, source_document, ArtifactLevel)` — **not** `result_ref`
  - [ ] A sample with no resolvable `source_document` is **excluded from dispersion** (no stable artifact key), logged WARNING; it still counts for agreement (T9)
  - [ ] Keep only artifacts graded by **≥2 distinct `JudgeConfigId`s** (this is the cross-config dispersion the slice ships)
  - [ ] Per artifact: `judge_configs` = the distinct configs; `n` = number of distinct configs (or judgments) contributing; `disagreement_rate` = fraction of judge-config pairs whose judge verdicts differ (categorical)
  - [ ] **Same-config path (dormant):** structure the grouping so repeated judgments under one identical `JudgeConfigId` on one artifact would also produce a dispersion measurement — but this cannot occur until 300 FW#1 persists repeated same-config results. Do **not** import from `pipeline.steps.fan_out`; do **not** add a 300/180 dependency
  - [ ] An empty sample list (or no multi-config artifact) yields an empty-cells report with a zeroed summary — honest, no fabricated zero
- [ ] Success: two configs' review files for one artifact (same `sourceDocument`) land in **one** `DispersionCell` with both configs; a single-config artifact produces no dispersion cell; nothing imports `fan_out`

**Commit:** `feat(metrology): add artifact-identity-keyed dispersion report`

---

### T12: Tests for dispersion report

- [ ] **Add `tests/metrology/test_report_dispersion.py`**
  - [ ] **Cross-config on one artifact:** two samples, same `sourceDocument`, distinct `JudgeConfigId` (different model) → one `DispersionCell` listing both configs with a disagreement rate + n
  - [ ] **Result-file identity is NOT the key (regression for slice-review F001):** the two review files have different `result_ref`s yet still share one dispersion cell (asserts artifact identity, not file identity, is the group key)
  - [ ] Single-config artifact → no dispersion cell
  - [ ] Missing `source_document` → excluded from dispersion, counted
  - [ ] **Empty store / no multi-config artifact:** yields an empty report rendered honestly (no fabricated zero) — Failure Modes "empty evidence" row (slice-review F006)
  - [ ] **No fan_out dependency:** assert `report.py` (and the metrology report core) import nothing from `squadron.pipeline.steps.fan_out`
- [ ] Success: `uv run pytest tests/metrology/test_report_dispersion.py` passes

**Commit:** `test(metrology): cover cross-config dispersion and artifact-identity key`

---

### T13: Trend report

- [ ] **Extend `report.py`** with `trend_report(samples: list[SampleVerdict], cwd: str, bucket: str) -> TrendReport`
  - [ ] Bucket enriched samples by `captured_at` into time windows (`bucket` = e.g. `month`, default from `metrology.trend_bucket`, key exists from T5)
  - [ ] Within each bucket, compute the agreement (and, where multi-config data exists, dispersion) figures on the **same per-level / per-config grain** as T9/T11 — reuse those functions per bucket, do not re-derive grouping
  - [ ] `TrendReport.series` is ordered oldest→newest with a human-readable `bucket_label`; an empty store yields an empty series (honest, no error)
- [ ] Success: samples spanning two months produce two series entries on the same grain, each an `AgreementReport` (and `DispersionReport` where applicable)

**Commit:** `feat(metrology): add trend report on the per-level/per-config grain`

---

### T14: Tests for trend report

- [ ] **Add `tests/metrology/test_report_trend.py`**
  - [ ] Samples in two distinct time buckets → two ordered series entries
  - [ ] Each series entry carries the same per-level/per-config cell shape as the standalone agreement report (grain preserved)
  - [ ] `bucket` override changes the windowing; the default comes from `metrology.trend_bucket`
  - [ ] Empty store → empty series, no exception
- [ ] Success: `uv run pytest tests/metrology/test_report_trend.py` passes

**Commit:** `test(metrology): cover trend bucketing and grain preservation`

---

### T15: CLI `report` sub-group (thin shell)

- [ ] **Extend `src/squadron/cli/commands/metrology.py`** with a `report` sub-group (thin shell, all logic in `squadron.metrology.report`; the `config.py`/320 pattern)
  - [ ] `report agreement [--project ID] [--level LEVEL] [--json] [--cwd .]` — render a table of `(artifact_level, judge_config) → match_rate (n)`, `below_floor` cells marked; the `excluded` summary line always prints ("N excluded: M stale-judge-result, K unversioned")
  - [ ] `report dispersion [--project ID] [--level LEVEL] [--json] [--cwd .]` — render `(artifact, judge_configs) → disagreement_rate (n)`; when no multi-config artifact exists, print an explanatory line, **not** a fabricated zero
  - [ ] `report trend [--project ID] [--level LEVEL] [--bucket B] [--json] [--cwd .]` — render the figures per time bucket on the same grain
  - [ ] `--json` emits the Pydantic report model verbatim (the machine interface 322 reads), including the `excluded` summary
  - [ ] Reuse 320's `--cwd` / `--project` / store-construction + `MetrologyStoreError` handling (formatted error, clean exit — no traceback), consistent with `sample`/`list`. *(Note: the report commands take `--project`/`--level`/`--json`/`--cwd` plus `--bucket` for trend; the store's `--judge-config` filter is a `list`-command convention, not a report flag — matches the LLD API contract.)*
  - [ ] All three commands are **read-only** — never write the store or a review file
- [ ] Success: `sq metrology report --help` lists `agreement`, `dispersion`, `trend`; `report agreement` on a fixture store prints per-level rows with n and no blended number; `--json` emits a valid `AgreementReport`

**Commit:** `feat(cli): add sq metrology report agreement/dispersion/trend`

---

### T16: CLI + read-only invariance tests

- [ ] **Add `tests/metrology/test_report_cli.py`** using Typer's `CliRunner`
  - [ ] `report agreement` prints per-level/per-config rows with n; low-n rows marked; `--json` parses back to `AgreementReport`
  - [ ] `report dispersion` on a single-config store prints the explanatory "no multi-config artifacts yet" line (no fake zero); on a two-config artifact prints the cell
  - [ ] `report trend` prints ordered buckets; `--bucket` override honored
  - [ ] **Empty store:** each report command on an empty store prints an honest "no evidence" result and exits 0 (slice-review F006 at the CLI level)
  - [ ] Store-init failure → the shared `MetrologyStoreError` handler (formatted error, clean exit, no traceback)
  - [ ] **Corrupt sibling tolerance (report path):** a corrupt/unreadable record file alongside good records → the report is still produced over the good records with a WARNING (320's tolerant-skip behavior, re-asserted through the report path — slice-review F007)
  - [ ] **Read-only invariance:** snapshot the store dir (and a referenced review file) bytes before and after each report command → **unchanged**
  - [ ] **Surface-agnostic core:** assert `squadron.metrology.report` / `levels` / `report_models` import no Typer (mirror 320's parity test)
- [ ] Success: `uv run pytest tests/metrology/test_report_cli.py` passes; store bytes unchanged after every report command

**Commit:** `test(metrology): cover report CLI, --json, empty store, corrupt sibling, read-only`

---

### T17: Full validation and read-only regression gate

- [ ] **Run the full suite:** `uv run pytest` (entire repo) — 300 judging path, 320 capture path, and all existing tests pass unchanged
- [ ] **Run static checks:** `uv run pyright` and `uv run ruff check` — zero errors on new code; `uv run ruff format` before commit
- [ ] **Walkthrough smoke:** execute the LLD Verification Walkthrough steps 1–7 (accumulate agreement evidence across two levels → `report agreement` shows separate per-level rows with n and no blended number → overwrite a review file and confirm the sample is excluded as `stale-judge-result` → two-config artifact appears as one dispersion cell → `report trend` buckets on the same grain → comparability segregation of an unversioned record → store/review files byte-unchanged by any report command)
- [ ] Success: full suite green, static checks clean, walkthrough steps pass; if this completes the slice, mark the slice-plan entry `(321)` `[x]` and the slice-design frontmatter `status: complete`

**Commit:** `test(metrology): full validation pass for 321 reporting`

---

## Coverage Check (design → tasks)

- Artifact-level vocabulary + derivation → T1/T2 · Report models (incl. `ArtifactKey`, `ExclusionSummary`) → T3/T4 · Config keys (floor, trend bucket) → T5/T6 (**sequenced before the report tasks that read them** — slice-review F004) · Enrichment + content-verified judge join → T7/T8 · Agreement (per-level/per-config, floor, comparability) → T9/T10 · Dispersion (artifact-identity keyed, cross-config, dormant same-config, no fan_out) → T11/T12 · Trend (grain preserved) → T13/T14 · CLI `report` thin shell + `--json` + parity → T15/T16 · Full validation + read-only regression + walkthrough → T17.
- **Failure Modes table (all rows)** → missing review file / overwritten / **malformed-unparseable frontmatter** (T8, F005) → `stale-judge-result`; missing `sourceDocument` → excluded-from-dispersion (T8/T12); unversioned flag + segregation (T8/T10); **empty evidence honest render** (T10/T12/T14 core + T16 CLI, F006); artifact-level `UNCLASSIFIED` bucket (T2); **corrupt-sibling store-read tolerance re-asserted on the report path** (T16, F007); read-only invariance (T16).
- **Slice-review (design) fix carried into tasks:** F001 (dispersion keyed on artifact identity, not `result_ref`) → T11 core + T12's explicit regression assertion.
- **Tasks-review fixes applied:** F004 (config keys resequenced to T5/T6, before report computation) · F005 (malformed-frontmatter enrichment test, T8) · F006 (explicit empty-store tests across agreement/dispersion/trend, T10/T12/T14/T16) · F007 (corrupt-sibling report-path regression, T16) · F008 (CLI `--judge-config` clarified as a `list` convention, not a report flag — T15 note; design prose reconciled).
- Deferred by design, correctly absent here: threshold recommendation / graduation + version-key canonicalization + evidence-floor *consumption* (322), audit-oracle reporting (323), pre-emption delta (324), same-config dispersion *data source* (300 FW#1), any SQLite engine change, any store/capture/judging-path write.
