---
docType: slice-design
slice: agreement-dispersion-reporting
project: squadron
parent: ../architecture/320-slices.judge-calibration-quality-metrology.md
dependencies: [320]
interfaces: [322]
dateCreated: 20260722
dateUpdated: 20260725
status: complete
---

# Slice Design: Agreement & Dispersion Reporting

See [`320-reference...md`](../architecture/320-reference.judge-calibration-quality-metrology.md) for this initiative's glossary and current-state index.

## Overview

This slice is the human oracle's **headline analysis** over the sample 320 accumulates. It reads the metrology store and reports three figures, always at the **per-artifact-level / per-judge-configuration** grain and never as one blended global number:

- **Agreement** — judge-vs-human: how often the judge's verdict matched the operator's blind verdict, per artifact level and judge configuration.
- **Dispersion** — judge-vs-judge: how much distinct judge configurations disagree on the *same* artifact.
- **Trend** — the same two figures over time, on the same grain.

Every reported figure **carries its sample size (n)** and refuses to imply precision it lacks. Reports **refuse to pool measurements across incompatible judge configurations** (version/hash-keyed on whatever identity 320 recorded).

This slice adds **no new store engine, no new capture path, and no change to the judging path**. It is a pure read-and-aggregate layer over 320's `MetrologyStore`, plus the reporting CLI (and shared core the future MCP surface will call). It is the first slice whose workload is *aggregation*, so it is also the **store-backend revisit point** the 320 slice plan named — resolved here (see Technical Decisions) by **keeping flat-file** because this workload does not strain it.

## Value

Developer / operator value. The trust gradient 300 *asserts* (high for tasks-vs-slice, weak for arch-vs-concept) becomes a **measured, per-level quantity**, and systematic cross-model bias ("X overreaches, Y rubber-stamps") becomes **visible** as dispersion. Agreement carries its n so the operator can see when a level has too little evidence to act on — which is exactly the minimum-evidence signal 322 consumes to decide whether a judge may graduate. Dispersion and trend are the **human-free continuous monitors**: they maintain a graduated judge's standing between scarce human samples, and rising dispersion flags where the human sample budget should be spent.

## Technical Scope

**Included:**
- A canonical **artifact-level vocabulary** (an `ArtifactLevel` enum) and a **read-time derivation** that maps each stored sample's recorded review type to an artifact level — because 320 left `SampleVerdict.artifact_level` a reserved, currently-always-`None` hook (see Dependencies → *State of the 320 store*).
- An **agreement** computation: judge-verdict-vs-human-verdict match rate, grouped by `(artifact_level, judge_config)`, carrying n. Metric is naive **percent agreement with its n exposed** (small-n honesty is "show the n and a wide-interval flag," not a chance-corrected statistic that misbehaves at small n — see Technical Decisions).
- A **dispersion** computation: judge-vs-judge disagreement on the *same artifact* across **distinct judge configurations**, grouped by **artifact identity** `(project_id, source_document, artifact_level)` — not by review-file `result_ref` (see *Artifact identity vs. result-file identity*) — carrying n.
- A **trend** view: the agreement and dispersion figures bucketed over time on the same grain.
- **Configuration comparability enforcement:** the aggregation groups by judge-configuration identity and never pools measurements from incompatible configs; un-version-keyable records are **flagged and segregated**, never silently blended.
- A **minimum-evidence floor** value, *representable and reported* here (a figure below the floor is marked low-confidence); 322 *consumes* it to gate recommendations. This slice defines the config key and surfaces the flag; it does not make a graduation decision.
- A reporting CLI: `sq metrology report agreement | dispersion | trend`, thin Typer shells over a surface-agnostic `squadron.metrology.report` core (interface parity by construction, matching 320).

**Explicitly excluded (deferred to named slices):**
- Any **threshold recommendation** or graduation decision → 322. This slice reports; it does not recommend loosening a gate. The minimum-evidence floor is *reported* here and *acted on* in 322.
- **Resolution of the version-keying tension** (coordinated 300 write-path version field vs. content-hash-at-capture as the shipped comparability key) → 322. This slice **enforces non-blending on whatever key 320 already recorded** (`JudgeConfigId`), and flags records that cannot be version-keyed; it does not decide which key becomes canonical.
- **Same-configuration repeated-measurement dispersion** (running one judge config N times on one artifact) → this needs **300 Future Work #1 (multi-sample judging), which has NOT shipped** (see Dependencies and Future Work). 321 designs and tests the same-config dispersion path but it is **dormant until 300 FW#1 lands** — 321 does not introduce a 300 dependency or a 180 `fan_out` dependency to force it. Cross-configuration dispersion (distinct model/template on the same artifact) ships fully and is demo-able today from data the store already holds.
- Audit-oracle reporting (project/issue-class grain, no agreement dimension) → 323. This slice is the *human*-oracle report path only; the two oracles share the spine (320), not the report path.
- Any new store backend (SQLite) — see Technical Decisions.

## Dependencies

### Prerequisites
- **320 (metrology data layer & sample capture, keystone)** — `status: complete`. Provides `MetrologyStore` (`list_samples`, `count_samples`, `load_record`), the `SampleVerdict` / `JudgeResultRef` / `JudgeConfigId` / `ProjectId` models, `resolve_store_dir`, and the project-identity derivation. This slice is a **pure read consumer** of that store.

### Interfaces Required
- `squadron.metrology.store.MetrologyStore` — `list_samples(project_id=None, judge_config=None)` is the aggregation input. Note the current query surface filters by *one* project and *one* judge_config; grouping/faceting is done **in this slice** in memory over the full `list_samples()` result (the store stays a thin glob-and-filter; the report layer owns the group-by).
- `squadron.metrology.models.SampleVerdict` — fields consumed: `human_verdict` (`Verdict`), `result_ref`, `judge_config` (`JudgeConfigId`), `captured_at`, `blind`, `artifact_level` (currently `None` — derived here), `project_id`.
- `squadron.review.models.Verdict` — the verdict vocabulary (`PASS`/`CONCERNS`/`FAIL`) both the judge and the human use; agreement compares two `Verdict`s.
- The **judge verdict itself** — to compute agreement, the report must join each `SampleVerdict` back to the *judge's* verdict on that same result. See *State of the 320 store* below — this is the one join the design must get right.
- `squadron.config.manager` / `config.keys.CONFIG_KEYS` — register the floor/report config keys.
- The Typer app in `cli/app.py` and the existing `metrology` sub-app in `cli/commands/metrology.py` — the report commands register under the same sub-app.

### State of the 320 store (facts this design is built on — verified against the code)

Two facts materially shaped this design and must not be re-guessed at task time:

1. **`SampleVerdict.artifact_level` is a reserved, always-`None` hook.** 320's `record_sample` accepts it defaulting to `None` and the sole CLI caller never passes it (`cli/commands/metrology.py`), so **every stored sample today carries `artifact_level = None`**. There is **no enum or constant** for the vocabulary anywhere. 321 therefore (a) defines the `ArtifactLevel` enum and (b) derives the level **at report time** from the sample's recorded review type — which backfills historical `None` records with **no store migration**.

2. **The judge's own verdict is not stored on the `SampleVerdict`.** The sample records the *human* verdict and a `result_ref` (`project_id`, `relative_review_path`, `content_hash`) pointing at the persisted 300 review file. Agreement needs the *judge's* verdict for the same result. Two ways to get it, and the design picks the robust one:
   - **Chosen — re-read the judge verdict from the referenced review file** via `result_ref.relative_review_path`, using 320's existing `read_review_frontmatter` (the only reader of persisted reviews). The `content_hash` on the ref is compared against a freshly-derived hash of the current file: **match ⇒ the judge verdict is admissible** and joined; **mismatch ⇒ the file was re-run/overwritten since capture** — the judge verdict at grading time is no longer recoverable, so the sample is **flagged `stale-judge-result` and excluded from agreement** (counted and reported, never silently dropped or joined against the wrong verdict). This preserves 320's content-addressed guarantee end-to-end.
   - *Rejected — assume a future 320 field carries the judge verdict.* That is a 320 write-path change this slice is not entitled to make; the content-hash re-read works against the store as it exists.

   **Coordination note:** re-reading works while review files persist alongside the store. If a future slice prunes review files, agreement loses its judge-side join for pruned results. Surfaced in Future Work so it is tracked, not discovered later. (322's preferred write-path version field would *also* be the natural home for persisting the judge verdict onto the sample at capture — noted for 322, not assumed here.)

## Architecture

### Component Structure

A new reporting core under the existing `src/squadron/metrology/` package (surface-agnostic; no Typer imports), plus thin CLI shells:

- **`levels.py`** — the `ArtifactLevel` enum and `derive_artifact_level(review_type: str) -> ArtifactLevel`. The enum is the **single definition** of the vocabulary (CLAUDE.md: comparison values defined once). Mapping from the review types the code actually produces:

  | recorded review type (from `reviewType` frontmatter) | `ArtifactLevel` |
  | --- | --- |
  | `judge.tasks-vs-slice`, `tasks` | `TASKS_VS_SLICE` |
  | `judge.slice-vs-arch`, `slice` | `SLICE_DESIGN_VS_ARCH` |
  | `arch` | `ARCH_VS_CONCEPT` |
  | anything else / unresolvable | `UNCLASSIFIED` |

  `UNCLASSIFIED` is an explicit bucket, never a silent drop — a review type the map doesn't know is reported under `UNCLASSIFIED` with its n, so a new judge template surfaces as "unclassified evidence" rather than vanishing. (`arch-vs-concept` has **no judge template today** — the row exists so the vocabulary is complete and future arch-concept judging classifies correctly; it will simply carry n=0 until such reviews exist.)

- **`report.py`** — the aggregation core. Pure functions over `list[SampleVerdict]` + the judge-side join:
  - `agreement_report(samples, cwd) -> AgreementReport` — groups admissible samples by `(ArtifactLevel, JudgeConfigId)`, computes match rate + n per group.
  - `dispersion_report(samples, cwd) -> DispersionReport` — groups by **artifact identity** `(project_id, source_document, ArtifactLevel)` — *not* by `result_ref` — finds artifacts graded by ≥2 **distinct** judge configs, computes pairwise verdict disagreement + n per group. See *Artifact identity vs. result-file identity* below for why the group key must be the artifact, not the review-file instance.
  - `trend_report(samples, cwd, bucket) -> TrendReport` — the above bucketed by `captured_at` into time windows.
  - A shared join/classify pass produces an internal `EnrichedSample` (`sample` + derived `ArtifactLevel` + joined judge verdict + resolved `source_document` + admissibility flag) so agreement/dispersion/trend all consume one enriched list. The `source_document` is read in the **same** frontmatter read the agreement join already does, so dispersion's artifact key costs no extra I/O.

- **`report_models.py`** — Pydantic report models: `GroupKey(artifact_level, judge_config)`, `AgreementCell(group, n, match_rate, below_floor: bool)`, `DispersionCell(group, judge_configs, n, disagreement_rate)`, `AgreementReport`/`DispersionReport`/`TrendReport` (a list of cells + an `excluded` summary carrying counts of `stale-judge-result` / `unversioned` records so exclusions are always visible). These are the **interface 322 consumes** — a stable, typed report shape, not console text.

- **`cli/commands/metrology.py`** (extended) — add a `report` sub-group: `sq metrology report agreement | dispersion | trend`, each a thin shell rendering the corresponding report model. Reuses the `--cwd` / `--project` conventions 320 established (the report commands also take `--level`, `--json`, and `--bucket` for trend — see API Contracts; `--judge-config` is a `list`-command filter, not a report flag). Rendering is a table; `--json` emits the report model verbatim for scripting and for 322's consumption.

Config: new entries in `config.keys.CONFIG_KEYS` (see Technical Decisions).

### Artifact identity vs. result-file identity (the two distinct join keys)

Agreement and dispersion group on **different** identities, and conflating them is a correctness bug (this was caught in slice review F001):

- **`result_ref` identifies one review-file instance** — `(project_id, relative_review_path, content_hash)`. Both the path (its filename embeds the review *type*) and the hash (over `template_name` + `model`) differ per judge configuration. This is the right key for the **agreement** judge-side join, where the point is to bind a human verdict to *the exact judge result it graded blind* and detect if that file changed since.
- **Dispersion needs the underlying artifact**, which is invariant across which config judged it. Two configs grading the same artifact write two different review files → two different `result_ref`s → they could **never** land in one dispersion group if keyed on `result_ref`. The stable artifact identity is **`(project_id, source_document)`** where `source_document` is the review frontmatter's `sourceDocument` field (the graded artifact's path) — already exposed by 320 as `identity.SOURCE_DOC_KEY`. Dispersion groups by `(project_id, source_document, ArtifactLevel)` and then collects the **distinct `JudgeConfigId`s and their judge verdicts** captured against that artifact.

The `EnrichedSample` (below) therefore carries **both** the sample's `result_ref` (for the agreement join) and the resolved `source_document` (for the dispersion group key), read from the same one-pass frontmatter read the agreement join already performs — no extra I/O.

### Data Flow

**Report (read-only):**
1. Operator invokes `sq metrology report agreement [--project ID] [--level L] [--json] [--cwd .]`.
2. Core loads `store.list_samples(project_id=...)` — all matching samples across the (optionally filtered) grain.
3. **Enrich** each sample: derive `ArtifactLevel` from its review type (`levels.py`); re-read + hash-verify the referenced review file to join the judge verdict and read its `sourceDocument` (`read_review_frontmatter` + `derive_result_ref`); flag admissibility (`stale-judge-result`, `unversioned`).
4. **Group** admissible enriched samples by `(ArtifactLevel, JudgeConfigId)` (agreement/trend) or by **artifact identity** `(project_id, source_document, ArtifactLevel)` (dispersion).
5. **Compute** match rate / disagreement rate + n per group; mark `below_floor` where n < the configured minimum-evidence floor.
6. **Render** — table (human) or JSON (report model, for 322). The `excluded` summary always prints: "N samples excluded (M stale-judge-result, K unversioned)."

No write path. No pipeline/gate/dispatch interaction. This slice never mutates the store or a review file.

### State Management

Stateless over 320's store. Reports are computed on demand from the current store contents; nothing is cached or persisted by this slice. (If a future scale need arises, caching a derived report is a later concern — not this slice.)

## Technical Decisions

### Store backend — flat-file retained (the 320-inherited revisit point, resolved)

The 320 slice plan named 321 as the SQLite-vs-flat-file revisit point because "**321 is the first slice whose workload is aggregation**." Decision: **keep the flat-file glob-and-filter store; do not adopt `sqlite3`.**

Rationale: the workload is group-by over a **small, user-level, cross-project sample** (a handful of human spot-checks per artifact level — the architecture's *Honest statistics at small n* premise). Loading every record and grouping in memory is trivial at this scale; a query engine buys nothing a Python `defaultdict` group-by doesn't, and adopting the project's first DB for it would be the over-engineering the plan and CLAUDE.md warn against. The **trip-wire** for revisiting (recorded here so it is not re-litigated by feel): if `list_samples()` over the real cross-project store ever becomes the latency or memory bottleneck of a report — concretely, when a single `report` invocation must load enough records that in-memory grouping is noticeably slow — adopt stdlib `sqlite3` then; the migration stays contained because 320's records are schema-versioned Pydantic. Until measured, flat-file stands.

### Agreement metric at small n — naive percent + exposed n, not chance-corrected

Per the architecture (*Honest statistics at small n*) and the open question the plan flags (naive percent vs. chance-corrected): with a handful of samples per level, chance-corrected coefficients (Cohen's/Fleiss' κ) are themselves unstable and can swing wildly or be undefined. The honest presentation at small n is **naive percent agreement with the n always shown and a `below_floor` flag** when n is under the minimum-evidence floor — not a single coefficient that *looks* more precise than the data supports. This is a reporting-honesty decision, not a statistical-sophistication one; the architecture explicitly prefers "carry its n and refuse to imply precision" over a fragile point estimate. (A chance-corrected metric can be added later once per-level n is routinely large enough — noted, not built.)

### Verdict comparison — exact-match agreement over the 3-value `Verdict`

Agreement counts a judge/human pair as agreeing when the two `Verdict` values are equal (`PASS`/`CONCERNS`/`FAIL`). No ordinal "off-by-one" partial credit — the gate decision 322 ultimately cares about is categorical, and partial-credit weighting would be an unjustified modeling choice at this stage. Dispersion likewise measures categorical disagreement (fraction of judge-config pairs that differ) on the same artifact.

### Configuration comparability — group by `JudgeConfigId`, segregate the un-keyable

The store already records `JudgeConfigId(template_name, model, template_content_hash)`. Grouping keys on the **whole configuration identity 320 recorded**; measurements from different configs are **never pooled**. Where `template_content_hash` is `None` (320 records it only when the review type resolves to a known template — otherwise `None`), the record is `unversioned`: it is grouped by `(template_name, model)` but **flagged**, and any report that would pool it with a hash-bearing record of the same name+model instead **segregates and flags** it rather than blending — because a same-name template edit is exactly the silent-invalidation failure the architecture forbids. *Which* key becomes canonical (hash-at-capture vs. a coordinated 300 write-path field) is 322's decision; 321 enforces non-blending on whatever is present.

### Config Keys (added to `CONFIG_KEYS`)

- `metrology.min_evidence_n` (int, small default e.g. a handful) — the minimum-evidence floor: a report cell with `n < min_evidence_n` is marked `below_floor`. **Reported** here (low-confidence flag); **consumed** by 322 to refuse a loosening recommendation. Centralized in config, never hard-coded at a call site (CLAUDE.md rule).
- `metrology.trend_bucket` (str, default e.g. `month`) — the default time-bucket grain for `report trend` (`--bucket` overrides). Kept as a config default so the report grain is not a scattered magic value.

## Implementation Details

### API Contracts

**CLI (the surface that ships):**

```
sq metrology report agreement  [--project ID] [--level LEVEL] [--json] [--cwd .]
sq metrology report dispersion [--project ID] [--level LEVEL] [--json] [--cwd .]
sq metrology report trend      [--project ID] [--level LEVEL] [--bucket B] [--json] [--cwd .]
```

- **`agreement`** — a table of `(artifact_level, judge_config) → match_rate (n)`, with `below_floor` cells marked (e.g. a `*` / "low-n" tag). Never a single blended row.
- **`dispersion`** — a table of `(artifact, judge_configs) → disagreement_rate (n)` keyed on **artifact identity** (`project_id`, `source_document`, `artifact_level`), for artifacts graded by ≥2 distinct configs. Empty (with an explanatory line) when no artifact has been graded by multiple configs yet — the common case until multi-config sampling or 300 FW#1 accumulates.
- **`trend`** — the agreement/dispersion figures per time bucket on the same grain.
- **`--json`** emits the Pydantic report model verbatim — the machine interface 322 reads. Every JSON payload includes the `excluded` summary (stale/unversioned counts) so a consumer never mistakes an exclusion for absence of data.
- All commands are read-only, thin Typer shells over `squadron.metrology.report`. The identical core is what the future MCP report tool will call — parity by shared core, matching 320's `config`/`metrology` pattern.

### Report Models (shape 322 consumes)

```
GroupKey            artifact_level: ArtifactLevel; judge_config: JudgeConfigId
AgreementCell       group: GroupKey; n: int; match_rate: float; below_floor: bool
ArtifactKey         project_id: str; source_document: str; artifact_level: ArtifactLevel
DispersionCell      artifact: ArtifactKey; judge_configs: list[JudgeConfigId];
                    n: int; disagreement_rate: float
ExclusionSummary    total_excluded: int; stale_judge_result: int; unversioned: int;
                    missing_source_document: int = 0
AgreementReport     cells: list[AgreementCell]; excluded: ExclusionSummary
DispersionReport    cells: list[DispersionCell]; excluded: ExclusionSummary
TrendReport         bucket: str; series: list[(bucket_label, AgreementReport|DispersionReport)]
```

### Failure Modes

Per the Failure-Mode Enumeration rule, each new I/O / join boundary has an enumerated failure, an explicit handling decision, and an observable signal (never silent). Each row gets at least one test.

| Boundary | Failure | Handling | Observable signal | Test |
| --- | --- | --- | --- | --- |
| **judge-side join** (re-read referenced review file) | referenced review file missing (moved/pruned since capture) | exclude the sample from agreement; count it | `excluded.stale_judge_result` incremented; WARNING naming the path | missing-review-file → sample excluded, counted, not joined |
| **judge-side join** (hash verify) | `content_hash` mismatch (file re-run/overwritten since capture) | exclude from agreement; the grading-time judge verdict is unrecoverable | `excluded.stale_judge_result` incremented; WARNING | overwritten-review → excluded + flagged, never joined to the new verdict |
| **judge-side join** (parse) | review file present but frontmatter unparseable / no verdict | exclude; count | `excluded.stale_judge_result`; WARNING naming what failed | malformed-review → excluded, counted |
| **artifact-level derivation** | review type not in the map | classify `UNCLASSIFIED` (explicit bucket, reported with n) | cell under `UNCLASSIFIED` | unknown review type → UNCLASSIFIED cell, not dropped |
| **dispersion artifact key** | referenced review file has no `sourceDocument` frontmatter | the sample still counts for *agreement* (which keys on `result_ref`), but is **excluded from dispersion** — it has no stable artifact identity to group cross-config peers by | WARNING naming the path; the sample absent from any dispersion cell (present in agreement) | missing-sourceDocument → excluded from dispersion only, counted, not crashed |
| **configuration comparability** | `template_content_hash is None` (unversioned record) | group by (name, model) but flag; segregate from hash-bearing same-name records | `excluded.unversioned` count; unversioned cells flagged | mixed versioned/unversioned same name+model → segregated, not pooled |
| **empty evidence** | no samples, or all below floor | report renders empty/low-confidence honestly | table prints "no evidence" / cells marked `below_floor`; exit 0 | empty store → honest empty report, not an error |
| **store read** | `list_samples` skips a corrupt sibling (320 behavior) | inherit 320's tolerant-skip-with-WARNING; report over what loaded | 320's WARNING; report unaffected | corrupt sibling → report still produced over good records |

No boundary swallows its failure. The two "exclusion" paths (`stale-judge-result`, `unversioned`) are **counted and reported**, never silent — matching the architecture's insistence that un-keyable data is flagged, not pooled, and that reports carry honest evidence counts.

## Integration Points

### Provides to Other Slices
- **The agreement / dispersion / trend report models** (`squadron.metrology.report_models`) — the typed, sample-size-carrying, per-level/per-config report shape. **322 consumes `AgreementReport` (with `below_floor` and `ExclusionSummary`)** to produce its evidence-floored threshold recommendation.
- **The `ArtifactLevel` enum and `derive_artifact_level`** — the canonical artifact-level vocabulary the whole initiative keys reporting on (322 reports recommendations per level; a future arch-concept judge classifies through it).
- **The `min_evidence_n` floor** — defined and reported here, gating recommendations in 322.

**Relationship to 323/324 (not a provider/consumer edge).** 321's only downstream interface is **322**, so the frontmatter `interfaces` lists `[322]` alone. 323 (audit baseline) and 324 (pre-emption delta) do **not** consume 321's report path: per 320-arch the two oracles *share the metrology spine* (320's store + trend conventions), **not** one report path — the audit oracle reports at the project/issue-class grain with no agreement dimension and builds its own analysis over 320 directly. They relate to 321 only as sibling consumers of the same 320 spine, which is a 320 edge, not a 321 one. (If 322's threshold work later grows a reporting facet 323/324 reuse, that edge is added then, explicitly.)

### Consumes from Other Slices
- **320's `MetrologyStore` and models** — read-only. No schema change, no write.
- **320's `read_review_frontmatter` + `derive_result_ref`** — reused for the judge-side join and its hash verification (no new review reader).
- **300's persisted review files** — read-only, via the stored `result_ref`. Degraded behavior when a file is gone/changed is defined (exclude + flag), not a crash.

## Success Criteria

### Functional Requirements
- Agreement and dispersion are reported **per artifact level and per judge configuration**; **no report path emits a single blended "judge accuracy" number** (asserted by a test that a multi-level/multi-config store yields multiple cells, never one aggregate).
- Every reported figure **carries its n**; a cell with `n < metrology.min_evidence_n` is marked `below_floor`, and the floor value is reported. A report at small n does not present a bare rate without its n.
- **Dispersion** is computed from repeated judgments on the same artifact **across distinct judge configurations**, grouped by **artifact identity `(project_id, source_document, artifact_level)`** — never by review-file/`result_ref` identity (which differs per config and would make cross-config dispersion impossible; asserted by a test that two configs' review files for one artifact land in a single dispersion cell). The same-configuration repeated-measurement path is implemented and unit-tested against fixtures but **inert until 300 FW#1 provides repeated same-config results** — and **no 180 `fan_out` dependency is introduced** (asserted: 321 imports nothing from `pipeline.steps.fan_out`).
- Reports **refuse to pool measurements across incompatible judge configurations**: distinct `JudgeConfigId`s are distinct groups, and unversioned (`template_content_hash is None`) records are flagged/segregated rather than blended with hash-bearing same-name records.
- **Trend** is reported on the same per-level / per-configuration grain.
- The **judge-side join is content-verified**: a sample whose referenced review file is missing or has changed since capture is **excluded from agreement and counted in the exclusion summary**, never joined against the wrong verdict.
- `artifact_level` is **derived at report time** from each sample's review type (existing `None`-valued records classify correctly); an unknown review type lands in `UNCLASSIFIED`, not dropped.

### Technical Requirements
- **The judging path (300) and the capture path (320) are unmodified**: 321 is read-only over the store and review files; the full existing suite passes and a judge run / a `sq metrology sample` behaves exactly as before.
- Report **core (`squadron.metrology.report`, `levels`, `report_models`) is surface-agnostic** — no Typer imports (verified by test, matching 320).
- New code passes strict pyright and ruff; Pydantic at boundaries; the `ArtifactLevel` vocabulary defined **once** as an enum and referenced everywhere (no scattered strings).
- Test coverage: agreement/dispersion/trend over fixture stores (multi-level, multi-config, cross-project); the exclusion paths (missing/overwritten/malformed review file); the unversioned-segregation path; the `UNCLASSIFIED` path; the small-n `below_floor` flag; the no-`fan_out`-import assertion.

### Integration Requirements
- 322 can consume `AgreementReport` (per level, per config, with n, `below_floor`, and `ExclusionSummary`) as its recommendation input **without any change to this slice**.
- Adding 300 FW#1 (multi-sample judging) later makes the same-config dispersion path live **without a 321 change** — the path is built and tested here against fixtures; only the *data source* is missing.

### Verification Walkthrough

Demo script proving delivery. Commands marked *(new)* are introduced by this slice; the prerequisites reuse 320's `sq metrology sample`. Executed end-to-end against a scratch git repo during implementation (20260725); actual output shown below (values will differ per run — sample ids and paths are illustrative).

1. **Accumulate agreement evidence.** *(existing, 320)* In a git repo with a remote, produce a judge review and blind-capture human verdicts for it across more than one artifact level — e.g. capture against a `judge.tasks-vs-slice` review and a `judge.slice-vs-arch` review:
   ```
   sq metrology sample <n> --type judge.tasks-vs-slice --verdict PASS --cwd <repo>
   sq metrology sample <m> --type judge.slice-vs-arch  --verdict CONCERNS --cwd <repo>
   ```
   Caveat: `judge.tasks-vs-slice` and `judge.slice-vs-arch` are recognized review-type *strings* for `ArtifactLevel` derivation regardless of whether a matching `ReviewTemplate` is registered. If no template resolves for the type (common in a scratch/demo repo with no real judge templates configured), the captured record is `unversioned` (`template_content_hash=None`) — this does not block agreement/dispersion, it only routes the record through the unversioned-segregation path (step 6).

2. **Report agreement — per level, with n.** *(new)*
   ```
   sq metrology report agreement --cwd <repo>
   ```
   Confirmed actual output (two levels, one sample each):
   ```
   slice_design_vs_arch  judge.slice-vs-arch/minimax/minimax-m2.7  match_rate=1.00 (n=1) (low-n)
   tasks_vs_slice  judge.tasks-vs-slice/minimax/minimax-m2.7  match_rate=1.00 (n=1) (low-n)
   2 excluded (0 stale-judge-result, 2 unversioned)
   ```
   **Separate rows** per level, each with match rate **and its n** — no single blended "agreement" number. Low-n cells marked `(low-n)` (the `below_floor` flag). The trailing line always reports exclusions, including "0 excluded" on a clean run.

3. **Confirm the content-verified judge join.** *(new)* Re-run the underlying judge review so its file is overwritten (a new `content_hash`), then:
   ```
   sq metrology report agreement --cwd <repo>
   ```
   Confirmed: a WARNING is logged (`Excluding sample <id> from agreement: review file <path> changed since capture (content_hash mismatch)`) and the excluded-count line increments `stale_judge_result` (`2 excluded (1 stale-judge-result, 1 unversioned)` in the executed run) — the previously-captured sample is excluded and counted, never silently joined to the new verdict.

4. **Report dispersion — across distinct configs.** *(new)* Capture human verdicts against the **same artifact graded by two different judge configurations** (e.g. two models producing two review files for the same slice — two different review files, same `sourceDocument`), then:
   ```
   sq metrology report dispersion --cwd <repo>
   ```
   Confirmed actual output:
   ```
   project-documents/user/slices/901-slice.example2.md (slice_design_vs_arch)  disagreement_rate=1.00 (n=2)
   3 excluded (0 stale-judge-result, 3 unversioned)
   ```
   The **one artifact** appears as a **single dispersion cell** listing both judge configs (`n=2`) and a disagreement rate — proving the group key is the artifact (`project_id` + `sourceDocument`), not the per-config review file (whose `result_ref` differs by config; confirmed distinct `content_hash` and `relative_review_path` in the regression test, `test_report_dispersion.py::test_result_ref_identity_is_not_the_key_f001_regression`). With only a single config graded, `dispersion` prints `No multi-config artifacts yet.` — confirmed, **not** a fabricated zero. *(Same-config dispersion is not demo-able until 300 FW#1 ships — see Future Work.)*

5. **Report trend.** *(new)*
   ```
   sq metrology report trend --bucket month --cwd <repo>
   ```
   Confirmed: output is grouped under one `2026-07` header with the same per-level/per-config cell shape as step 2 — agreement/dispersion bucketed over time on the same grain, not re-derived.

6. **Confirm comparability enforcement.** *(new)* With samples from two distinct `JudgeConfigId`s (different model) on the same level, confirmed they appear as **two cells**, never merged (step 4's dispersion output; each `judge_configs` entry distinct). With an unversioned record (`template_content_hash` None) alongside a hash-bearing same-name record, confirmed they are **segregated/flagged**: `test_report_agreement.py::test_unversioned_record_segregated_from_hash_bearing_same_name_model` asserts 2 cells + `excluded.unversioned == 1`, and the executed walkthrough's exclusion lines above show the running `unversioned` count.

7. **Confirm read-only invariance.** *(existing)* Ran the full suite (`uv run pytest`, 2324 passed, 2 pre-existing skips unrelated to metrology) and confirmed the store and review files are byte-for-byte untouched by `report agreement`/`dispersion`/`trend` (SHA-1 snapshot before/after every command matched exactly), and that 300/320 behavior is unchanged (existing 300/320 test files pass unmodified).

## Future Work / Cross-Slice Coordination

Tracked here so the boundaries are explicit, per the PM's request to know *when and where* the dormant pieces land:

1. **(300 FW#1) Multi-Sample Judging — activates same-config dispersion.** 321 builds and unit-tests the same-configuration repeated-measurement dispersion path but it is **inert** because no code produces repeated same-config `ReviewResult`s today (300 Future Work #1 is unchecked; there is one `ReviewResult` per review file). **When 300 FW#1 ships** (a judge config run N times, reduced/persisted as repeated measurements), 321's same-config dispersion becomes live with **no 321 code change** — only the data source appears. This is a **300-side** change, surfaced as a coordination point, *not* a 321 dependency and explicitly *not* a 180 `fan_out` dependency (that boundary stays closed, per the architecture). *Where it goes:* a 300-band slice implementing FW#1; *when:* whenever cross-model dispersion on identical configs becomes a felt need (rising cross-config dispersion in 321 reports is the natural trigger). Mirror this into the 320 slice-plan Future Work list.

2. **Judge-verdict persistence on the sample (322 coordination).** 321's agreement join re-reads the referenced review file and hash-verifies it. This is robust while review files persist, but a sample whose review file is later pruned/overwritten loses its judge-side join (correctly excluded as `stale-judge-result`). If 322 adopts the **preferred coordinated 300 write-path version field**, that write site is also the natural place to **persist the judge verdict onto the sample at capture time**, making agreement independent of the review file's continued existence. Flagged for 322; not assumed or built here.

3. **Chance-corrected agreement metric.** Naive percent + exposed n is the honest small-n presentation now. Once per-level n is routinely large, a chance-corrected coefficient (κ) could be added behind the same report model. Deferred until the evidence supports it.

## Risk Assessment

### Technical Risks
- **The judge-side join is the load-bearing correctness point.** Agreement is only meaningful if each human verdict is compared to the *same judge verdict the human graded blind*. Mitigation: the join re-reads via `result_ref.relative_review_path` and **verifies `content_hash`**; any mismatch excludes the sample rather than joining a stale/wrong verdict. A test overwrites a review file post-capture and asserts exclusion.
- **Dispersion has thin real data at ship time.** Cross-config dispersion needs the same artifact graded by ≥2 configs, which only accumulates as the operator samples across models; same-config dispersion needs 300 FW#1. Mitigation: dispersion is built and tested against fixtures, ships honestly empty when data is thin (explanatory line, not a fake zero), and the activation path for FW#1 is documented (Future Work 1). This is an evidence-availability limit, not a design defect.

### Mitigation Strategies
- Both risks are covered by explicit fixture tests in Success Criteria; neither needs new infrastructure or a store change.

## Implementation Notes

### Development Approach
Suggested order within the slice:
1. `levels.py` — `ArtifactLevel` enum + `derive_artifact_level` + tests (the vocabulary everything groups on; backfills `None` records).
2. `report_models.py` — the typed report shapes (the interface 322 depends on).
3. `report.py` — the enrich/join/group/compute core + tests over fixture stores (agreement first, then dispersion, then trend; include the exclusion and segregation paths and the no-`fan_out`-import assertion).
4. `cli/commands/metrology.py` — the `report` sub-group thin shells + `--json`; config keys (`min_evidence_n`, `trend_bucket`).
5. End-to-end verification walkthrough.

### Special Considerations
- **Parity is structural** (as in 320): no MCP tool ships, but the report core is the single source of truth both surfaces call.
- **Read-only discipline:** no `report` path may write the store or a review file — enforced by test (store bytes unchanged after every report command).
- **Relative effort:** 3/5 (small-n statistics honesty and the content-verified judge-side join are the substance; no engine change, no write path).

## Slice review (20260722) — FAIL addressed

Slice-design review (`321-review.slice.…`, kimi-k2.7-code) returned **FAIL** on one finding, now resolved; the note is also resolved.
- **F001 (FAIL, data-model)** — dispersion grouped by `(ArtifactLevel, result_ref)`, but `result_ref` identifies a *review-file instance* (path + content hash both vary per judge config), so two configs on one artifact could never share a dispersion group — making the cross-config dispersion this slice claims to ship impossible, contradicting walkthrough step 4 and 320-arch's cross-judge-comparability goal. **Fixed:** dispersion now groups by **artifact identity `(project_id, source_document, ArtifactLevel)`** using the review frontmatter's `sourceDocument` (already exposed by 320 as `SOURCE_DOC_KEY`), read in the same pass as the agreement join. Added the *Artifact identity vs. result-file identity* subsection making the two distinct join keys explicit, an `ArtifactKey` report model, a `sourceDocument`-missing failure-mode row (excluded from dispersion only), and a success criterion asserting two configs' files for one artifact land in one dispersion cell. Agreement continues to key on `result_ref` (correct for binding a verdict to the exact result graded).
- **F002 (note, interfaces)** — frontmatter listed `interfaces: [322, 323, 324]` but only 322 was documented. **Fixed:** narrowed to `[322]` and documented that 323/324 relate via the shared 320 spine (a 320 edge), not 321's report path — matching 320-arch's "two oracles, one spine, not one report path."

## Code review (20260722) — F006 addressed

Code review (`321-review.code.…`) returned a CONCERN (F006, error-handling/reporting) resolved during implementation: samples excluded from dispersion for a missing `sourceDocument` (the failure-mode row above, "dispersion artifact key") were not reflected anywhere in `ExclusionSummary` — a reader of `--json` output had no way to distinguish "no cross-config artifacts exist yet" from "some samples were silently dropped for lacking an artifact identity to group by." **Fixed:** added `missing_source_document: int = 0` to `ExclusionSummary` (`report_models.py`), incremented alongside the existing WARNING when `dispersion_report` excludes a sample for this reason. Defaults to `0` so `agreement_report`'s and `trend_report`'s existing `ExclusionSummary` construction sites (which never hit this path) don't need updating. The Report Models table above reflects the shipped shape.
