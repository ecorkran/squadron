---
docType: slice-design
slice: tech-debt-audit-baseline-harness
project: squadron
parent: ../architecture/320-slices.judge-calibration-quality-metrology.md
dependencies: [320, 340]
interfaces: []
dateCreated: 20260726
dateUpdated: 20260726
status: not-started
---

# Slice Design: Tech-Debt-Audit Baseline Harness

See [`320-reference...md`](../architecture/320-reference.judge-calibration-quality-metrology.md) for this initiative's glossary and current-state index.

## Overview

This slice stands up the initiative's **second oracle**. 320/321/322 built the human oracle — sampled verdicts, agreement/dispersion reporting, and the calibration feedback loop — on a metrology spine. 323 reuses that spine for a different oracle with a different grain: the **tech-debt-audit**, run across projects, normalized into persistable findings, and reported as a **cross-project code-quality baseline**.

The audit oracle has **no agreement dimension**. Nothing compares it to a human. Its headline is a count at the project/issue-class grain, and 324's headline is a *delta* against that count. Which means the entire value of this slice rests on one thing being true: **a later delta must be interpretable.** A findings-count that moved from 47 to 41 means nothing unless you know what the audit does when *nothing changes at all*.

So this slice ships variance first, in the strong sense the architecture requires (*Variance, then baseline, then intervention*):

1. **The harness** — run `tech-debt-audit` against a project programmatically, capture structured findings.
2. **The normalization** — prose-and-table audit output → typed, comparable `AuditFinding` records, keyed on the stable project identity from 320.
3. **The noise floor** — repeated audits on *unchanged* code, per project, persisted as an explicit measured quantity.
4. **The baseline report** — cross-project, project/issue-class grain, with the floor attached to every figure.

This slice adds **no intervention**. It does not generate a pre-emption prompt, does not touch dispatch config, and does not report a before/after delta — all of that is 324, which ships only after this slice's floor exists.

## Value

Developer/operator value. "Squadron produces good code" is currently an anecdote. After this slice it is a measured, cross-project baseline with a known error bar.

The error bar is the actual deliverable. A baseline without a noise floor is worse than no baseline, because it invites exactly the overclaiming the architecture forbids — reading a 6-finding drop as an improvement when the audit's own run-to-run spread is ±9. The floor is what converts 324 from storytelling into a credible directional signal, and it is why this slice exists separately from 324 rather than as its first half.

## Technical Scope

**Included:**
- An **audit harness** (`squadron.metrology.audit`): run the `tech-debt-audit` skill against a given project cwd via a provider profile, capture output.
- **Finding normalization**: structured audit output → `AuditFinding` records with a **closed category vocabulary**, severity, location, and honest handling of anything that does not normalize.
- **Fork edits to the `tech-debt-audit` skill** (see Technical Decisions): a machine-readable findings block, a closed category vocabulary, and an independent-run mode that suppresses repeat-run diffing. Landed in the canonical fork (`github:ecorkran/tech-debt-audit`) and vendored into `commands/analysis/tech-debt-audit.md`, with the sync enforced by test.
- **Noise-floor measurement**: N repeated audits at a pinned commit, per project, reduced to a persisted `AuditNoiseFloor` record.
- **Persistence** on the 320 spine: new `audit_finding` and `audit_noise_floor` record types behind the existing envelope discriminator.
- **Baseline reporting**: cross-project, per project/issue-class, every figure carrying the applicable floor.
- CLI: `sq metrology audit run`, `sq metrology audit variance`, `sq metrology report baseline` — thin Typer shells over a surface-agnostic core, matching 320/321/322.

**Explicitly excluded:**
- **The pre-emption prompt and any delta report** → 324. Shipping either here would violate variance-before-intervention.
- **Any write to dispatch config** → 324, and even there the flow is down-only.
- **A project registry / auto-discovery of "squadron-managed projects"** → none exists (verified); the harness takes an explicit project list. Building a registry is not this slice's problem.
- **Agreement or human-comparison figures for the audit** → the audit oracle has no human counterpart. The report must not fabricate one.
- **Migrating the store to SQLite** → the 321 revisit already declined it and left a measured trip-wire. This slice adds records, not an engine.
- **Auto-remediation of findings** → the audit reports; nobody acts automatically.

## Dependencies

### Prerequisites
- **320 (metrology data layer)** — `status: complete`. Provides `MetrologyStore`, the `MetrologyRecord` envelope, `derive_project_id`, and `resolve_store_dir`.
- **340 (skill pack infrastructure)** — provides the `analysis` pack containing `tech-debt-audit`, plus `resolver._resolve_bundled` for locating it install-independently.

### Interfaces Required
- `squadron.metrology.store.MetrologyStore` — extended with audit writers/readers (additive; no migration).
- `squadron.metrology.models.MetrologyRecord` — extended with two optional payload fields. `RECORD_TYPE_AUDIT_FINDING` **already exists** at [models.py:29](src/squadron/metrology/models.py#L29), reserved by 320 for exactly this.
- `squadron.metrology.identity.derive_project_id` — consumed as-is. Every audit record keys on it.
- `squadron.skills.resolver._resolve_bundled` — locates the skill file whether or not `sq skills install` has been run.
- `squadron.review.review_client` — the structural precedent for running a prompt with a per-project `cwd` and tool permissions (see below).
- `squadron.config.keys.CONFIG_KEYS` — new config keys must be registered here or `get_config` raises `KeyError`.

### State of the ground truth (facts verified against the code)

Five facts shaped this design and must not be re-guessed at task time.

1. **The skill writes a file; it does not return findings.** [tech-debt-audit.md:62](commands/analysis/tech-debt-audit.md#L62) instructs the model to create `analysis/nnn-analysis.{project-name}.md` where `nnn` "starts at 940" — a **model-chosen path**. A harness capturing response text gets narration, not the audit.

2. **Repeat-run mode actively destroys variance measurement.** [tech-debt-audit.md:103](commands/analysis/tech-debt-audit.md#L103): *"If audit file already as specified here exists in the repo, read it first. Mark resolved findings as `RESOLVED`... tag new findings with `NEW`."* There is no flag to disable it. Under this behavior, run 2 of a variance series reads run 1's output and emits a **diff**, not an independent sample — biasing the measured floor toward zero, which is the worst direction, since it makes every later 324 delta look significant.

3. **Category is free text.** The 9 audit dimensions at [tech-debt-audit.md:40-56](commands/analysis/tech-debt-audit.md#L40-L56) are prose headings. Nothing constrains the `Category` column to them. Cross-project comparison at the issue-class grain is impossible without a closed vocabulary.

4. **Severity vocabularies do not match.** The audit uses `Critical/High/Medium/Low` ([:68](commands/analysis/tech-debt-audit.md#L68)); the review system uses `PASS/NOTE/CONCERN/FAIL` ([review/models.py:19-25](src/squadron/review/models.py#L19-L25)). These are disjoint and must not be conflated.

5. **No skill-execution function exists.** `sq skills` does install/uninstall/list only. The closest precedent is [review_client.py:54-184](src/squadron/review/review_client.py#L54-L184) (`run_review_with_profile`) — the only existing path that sets a per-project `cwd`, applies tool permissions, filters SDK tool-narration from the text, and hands off to a parser. `one_shot_dispatch` is **not** usable: it hardcodes `cwd=None` ([dispatch.py:61](src/squadron/pipeline/actions/dispatch.py#L61)).

## Technical Decisions

### 1. Fix the fork, do not wrap it

**Decision:** Edit `commands/analysis/tech-debt-audit.md` to emit a machine-readable findings block and honor an independent-run mode. The harness reads the skill file as-is and appends only a small run-mode preamble.

The alternative considered and rejected was composing a prompt in Python — reading the skill file, stripping the Deliverable and repeat-run sections, and appending a squadron-authored output contract. That approach exists to work around a skill you do not control. **We control this one:** `tech-debt-audit` is our fork (`github:ecorkran/tech-debt-audit`, MIT, forked from `ksimback/tech-debt-skill`), already adapted for squadron/cf conventions — the file's own note at [:109](commands/analysis/tech-debt-audit.md#L109) records the output-filename adaptation.

Fixing the fork is strictly less machinery and removes the one hazard prompt-composition could not: **drift between what users run and what the baseline measures.** With the contract in the skill file, `/analysis:tech-debt-audit` and the harness consume the same artifact by construction. A human reading the skill sees the same format the parser expects.

This makes 323's `[340]` dependency a **real coupling, not a read-only one** — the slice modifies a shipped 340-band artifact affecting every user of the pack. Called out explicitly so it is a decision, not a discovery.

**Fork edits (three, all additive to the audit protocol):**

- **A fenced, machine-readable findings block** emitted *in addition to* the human findings table, not replacing it. The table stays because humans read it; the block is what the parser consumes. Same data, serialized twice — this is exactly the precedent [persistence.py:130-186](src/squadron/review/persistence.py#L130-L186) already sets for reviews (structured frontmatter + prose body).
- **A closed category vocabulary** — the 9 dimensions become an enumerated list the `category` field must draw from, plus `other` (see Decision 3).
- **Independent-run mode** — a documented condition under which the repeat-run clause at [:103](commands/analysis/tech-debt-audit.md#L103) does **not** apply, so a variance series produces independent samples. The harness sets it; interactive users keep the living-document behavior they have today.

The audit's 9 dimensions, its citation rules, and its "looks bad but is actually fine" requirement are **not** touched. The instrument keeps measuring what it measures.

**Fan-out is expected on the large repos and is not suppressed.** [:97](commands/analysis/tech-debt-audit.md#L97) dispatches Task subagents when a repo exceeds 50k LOC or 5 top-level modules; squadron (~64k) and context-forge (~61k) clear it, and migratory may clear the module bar. This is a *prompt instruction, not enforced code*, so fan-out may occur on one run of a series and not the next. That inconsistency is left in deliberately: it is genuine run-to-run noise a user of the skill actually experiences, so it belongs **inside** the measured floor rather than being engineered out of it. A large repo whose floor is dominated by fan-out nondeterminism is a real finding about the instrument. Practical consequence for Phase 6: fanned-out runs are slower and heavier than a per-LOC estimate suggests, since each subagent reads independently.

### 1a. Fork sync — the fork is canonical, squadron vendors it

The skill has three homes and an edit that reaches only one of them silently forks the instrument:

1. `github:ecorkran/tech-debt-audit` — the standalone fork, consumed by any project pointing at it
2. `commands/analysis/tech-debt-audit.md` in this repo — bundled into the wheel ([pyproject.toml:68](pyproject.toml#L68)), which is what squadron's `source = "bundled"` manifest entry ([data/skills.toml](src/squadron/data/skills.toml)) serves
3. `~/.claude/commands/analysis/` — installed copies, refreshed by `sq skills install analysis`

**Decision: the fork repo is canonical.** Edits land there first and are synced into squadron's `commands/analysis/` as a vendored snapshot. Installed copies follow from `sq skills install`.

This direction is chosen over developing in squadron and pushing upstream because the skill is a **distributable artifact used beyond squadron**. If squadron were canonical, every other consumer of the fork would run the pre-contract instrument until a push happened — and because `audit_prompt_hash` (Decision 10) correctly refuses to pool audits from differing prompts, the result would be a **silent measurement gap** rather than a loud error: audits that simply never compare, with no failure to notice.

Sync is enforced rather than remembered: the category-vocabulary test (Success Criteria) asserts squadron's vendored copy enumerates exactly `AuditCategory`, so a fork edit that lands without a squadron sync — or a squadron edit that diverges from the fork — fails CI. `audit_prompt_hash` is computed from the **vendored copy actually used for a run**, so any divergence is at minimum recorded in the data even if it escapes CI.

### 2. Findings block format

Emitted at the end of the audit file, delimited so it can be located without depending on surrounding prose:

```
<!-- squadron:findings:begin v1 -->
```yaml
findings:
  - id: F001
    category: architectural-decay
    location: src/payments/processor.ts:1240
    severity: critical
    effort: L
    summary: 1400-line god class handling routing, validation, retry, reconciliation
```
<!-- squadron:findings:end -->
```

YAML inside an HTML-comment-delimited fence, because:
- The repo already parses YAML at a document boundary (`read_review_frontmatter`, [identity.py:162](src/squadron/metrology/identity.py#L162)), so this reuses a known-good reader rather than introducing squadron's first markdown-pipe-table parser — none exists today.
- HTML comment delimiters survive markdown rendering and are unambiguous to locate.
- A malformed block fails *loudly at a boundary* rather than silently half-parsing, matching the all-or-nothing discipline of `_extract_criteria` ([parsers.py:181-184](src/squadron/review/parsers.py#L181-L184)).

`summary` is prose and stays prose. `recommendation` is deliberately **not** in the block: it is advice for humans, it is the longest field, and nothing in the baseline or 324's delta consumes it. It remains in the human table.

### 3. Category vocabulary — closed, with an honest escape hatch

`AuditCategory` is a `StrEnum` mirroring the audit's own 9 dimensions:

```
architectural-decay | consistency-rot | type-contract-debt | test-debt
dependency-config-debt | performance-resource | error-handling-observability
security-hygiene | documentation-drift | other
```

Ten values, not nine. **`other` is load-bearing, not a dumping ground.** The success criterion requires that findings which cannot be normalized are "represented honestly (flagged/retained), not dropped silently." A finding whose category the model invents outside the vocabulary is normalized to `other` **with its raw category string retained** on the record (`raw_category: str | None`). Nothing is discarded, and the baseline report shows the `other` count explicitly — a rising `other` share is a signal the vocabulary is wrong, which is information, not noise to hide.

The enum lives in squadron and the skill file lists the same values. That is duplication across a process boundary (a markdown prompt and a Python enum), which the repo's DRY rule would normally forbid. It is accepted here because the two artifacts are consumed by different runtimes and cannot import from each other; the mitigation is a test asserting the skill file's enumerated values exactly match `AuditCategory`, so drift fails CI rather than silently degrading the baseline.

### 4. Severity: preserve the audit's own vocabulary

`AuditSeverity` is `critical | high | medium | low` — the audit's own scale, **not** mapped onto the review system's `PASS/NOTE/CONCERN/FAIL`. The two vocabularies measure different things on different artifacts, and a mapping would manufacture equivalence that does not exist. Fact 4 above; kept separate deliberately.

### 5. Locations are recorded, not resolved

Findings carry `location` as the audit emitted it (`path/to/file.ext:LINE`). The harness does **not** verify the path exists or the line is meaningful.

This differs from the review parser, which warns on non-existent cited paths (`_check_path_existence`, [parsers.py:263](src/squadron/review/parsers.py#L263)) — and the difference is intentional. For a review, a hallucinated path is a defect in a finding a human will act on. For the baseline, the *count and class* of findings is the measurement; a fabricated location does not corrupt the count, and re-verifying every location across N runs × M projects is I/O the measurement does not need. Location is retained for human follow-up and for 324's issue-class targeting, and its precision is not overclaimed anywhere in the report.

A location that is absent or a placeholder normalizes to the existing `unverified` sentinel convention ([parsers.py:24](src/squadron/review/parsers.py#L24)) rather than to null.

### 6. The noise floor is per-project, measured at a pinned commit

**Decision:** `metrology.audit_variance_runs = 3` (default), run against an **operator-supplied project list**, at a **pinned commit per project**, producing one `AuditNoiseFloor` record per project.

Three runs is enough to observe a spread without pretending to statistical rigor at n=3. The record carries min/max/mean/stddev of total findings and per-category counts, and the report presents it as a coarse floor, stated as such. The config key lets an operator buy more confidence.

**Per-project, not global.** Audit variance plausibly scales with repo size, language, and how well the 9 dimensions fit the codebase. Assuming one project's floor generalizes is exactly the unmeasured assumption this slice exists to eliminate. A baseline for a project with no measured floor is reported as **"no floor measured"** — never silently borrowing another project's number.

**Pinned commit is what makes "unchanged code" true.** Each variance run records the commit SHA it ran against; runs in a series must agree, and the harness refuses to reduce a series whose SHAs differ or whose worktree was dirty. Without this, "repeated audits on unchanged code" is an assumption rather than a verified precondition, and a floor measured across a code change is not a floor.

### 7. The variance set

Four projects, chosen for contrast rather than convenience — the question the floor must answer is whether variance is a stable property of the audit or a property of each codebase.

| Project | Identity | Shape | Why it is in the set |
|---|---|---|---|
| `squadron` | `github.com/ecorkran/squadron` | Python, ~64k LOC, 374 files | This project. Large, long-lived, well-tooled. The reference case. |
| `migratory` | `github.com/ecorkran/migratory` | Python + GPU kernels, ~44k LOC | Mixed-language with GPU sources the audit's stack tooling does not cover. |
| `context-forge` | `github.com/ecorkran/context-forge` | TypeScript, ~61k LOC, 378 files | Large TS repo — different language at comparable scale to squadron, isolating language from size. |
| `migratory-viewer` | `github.com/ecorkran/migratory-viewer` | TypeScript/UI, ~6.2k LOC | Small UI repo. Tests whether the floor holds at an order-of-magnitude smaller size. |

All four resolve identity from a git remote, so `derive_project_id` succeeds with `source=remote` and **no `metrology.project_id` prerequisite** is needed. Two use scp-style remotes; `normalize_remote_url` ([identity.py:100](src/squadron/metrology/identity.py#L100)) folds both forms, so identity is uniform.

`trading-data` (`github.com/manta-digital/trading-data`, Python, ~66k LOC, timescaledb/caggs) is a **noted stretch case, not in the committed set.** It is the most likely of the candidates to expose whether the 9 dimensions even fit a database-heavy codebase, or whether findings pile into one or two categories and make the per-category spread meaningless. That is a genuinely useful thing to learn and a reason to run it — but it is an open question about the *instrument*, so it is recorded in Future Work rather than gating this slice's completion. `context-visualizer` was considered and dropped in favor of `migratory-viewer` as the small/UI case (mixed 13py/4ts vs. a cleaner 27-file TS surface).

Note that `squadron`, `context-forge`, and `trading-data` all exceed the 50k-LOC threshold at which the skill dispatches Task subagents ([:97](commands/analysis/tech-debt-audit.md#L97)). Subagent fan-out is plausibly a **variance source itself** — merge/dedupe across subagent reports is non-deterministic — which is precisely why the small repo is in the set as a contrast.

### 8. Cost is real and is acknowledged, not hidden

The committed variance set is 4 projects × 3 runs = **12 full-repo LLM audits**, plus one baseline run per project. This is the dominant cost of the slice by a wide margin and the reason the harness must be resumable (Decision 9) rather than all-or-nothing.

The floor is **not** continuously refreshed. Re-measurement is warranted when the audit prompt or the model changes — both captured by `audit_prompt_hash` on every record (Decision 10) — not on a schedule.

### 9. One run = one persisted unit; series are reduced separately

`run_audit(project_path, ...)` performs a single audit and persists its findings immediately, tagged with a `run_id`. Variance reduction is a **separate pass** over persisted runs sharing a `(project_id, commit_sha, audit_prompt_hash)` key.

This split matters at 12-audit scale: a series that fails on run 3 does not discard runs 1 and 2, and a floor can be recomputed later — or with more runs added — without re-auditing. It also keeps the expensive I/O-bound step and the pure reduction independently testable, with the reduction unit-testable on fixtures at zero token cost.

### 10. Comparability: audits are only compared under the same instrument

Every audit record carries `audit_prompt_hash` — a content hash of the skill file that produced it — alongside the model id.

This is the same discipline 322 canonized for judge templates ([identity.py:298](src/squadron/metrology/identity.py#L298)) and it exists for the same reason: **an edit to the instrument invalidates comparison across the edit.** Since Decision 1 edits the skill file, and it will be edited again, a baseline taken before an edit and one taken after are not comparable and must not be silently pooled. The baseline report groups by prompt hash and flags cross-hash comparison rather than blending — mirroring `_comparability_key` ([report.py:205](src/squadron/metrology/report.py#L205)).

Records also carry `measured_at`. Your operational note — that the audit is run once, or on adopting a project, and *should* be periodic but is not yet — makes this a **point measurement with a real timestamp**, where the interesting comparison is across months. Periodic re-audit is the intended cadence; automating it is not in this slice.

## Architecture

### Component Structure

New surface-agnostic core under `src/squadron/metrology/` (no Typer imports), plus thin CLI shells — matching 320/321/322.

- **`audit_models.py`** — Pydantic shapes:

```
AuditCategory      StrEnum, 10 values (Decision 3)
AuditSeverity      StrEnum: critical | high | medium | low
AuditEffort        StrEnum: S | M | L
AuditFinding       finding_id: str; category: AuditCategory;
                   raw_category: str | None; severity: AuditSeverity;
                   effort: AuditEffort | None; location: str; summary: str
AuditRun           run_id: str; project_id: ProjectId; commit_sha: str;
                   audit_prompt_hash: str; model: str; measured_at: datetime;
                   findings: list[AuditFinding]; unnormalized_count: int
AuditNoiseFloor    project_id: ProjectId; commit_sha: str;
                   audit_prompt_hash: str; n_runs: int;
                   total: FloorStat; per_category: dict[AuditCategory, FloorStat];
                   measured_at: datetime
FloorStat          min: int; max: int; mean: float; stddev: float
```

  `AuditRun` and `AuditNoiseFloor` are envelope payloads, so per the 322 layering correction they live in **`models.py`** alongside `SampleVerdict` and `GraduatedConfig`; `audit_models.py` re-exports them. `AuditFinding` and the enums may live in `audit_models.py` since nothing in `models.py` needs to import them.

- **`audit.py`** — the harness:
  - `run_audit(project_path, *, profile, cwd_config, store) -> AuditRun` — resolve identity and commit SHA, build the prompt, execute, normalize, persist.
  - `build_audit_prompt(skill_path, *, independent_run: bool) -> str` — skill body plus run-mode preamble.
  - `audit_prompt_hash(skill_path) -> str` — content hash of the instrument.
  - `resolve_audit_skill() -> Path` — via `_resolve_bundled("analysis")`, install-independent.

- **`audit_parse.py`** — normalization, pure and independently testable:
  - `parse_audit_findings(raw: str) -> tuple[list[AuditFinding], int]` — locate the fenced block, YAML-parse, coerce to the closed vocabulary, return findings plus the count that could not be normalized.
  - `normalize_category(raw: str) -> tuple[AuditCategory, str | None]` — closed-vocabulary coercion retaining the raw string.

- **`audit_variance.py`** — reduction:
  - `reduce_noise_floor(runs: list[AuditRun]) -> AuditNoiseFloor` — validates the series shares `(project_id, commit_sha, audit_prompt_hash)`, then computes per-category and total `FloorStat`.

- **`audit_report.py`** — the baseline:
  - `baseline_report(store, *, project_filter=None) -> BaselineReport` — group by `(project_id, AuditCategory)`, attach each project's floor, mark projects lacking one.

### Store extension

Additive, no migration — following the exact 322 precedent. `RECORD_TYPE_AUDIT_FINDING` already exists ([models.py:29](src/squadron/metrology/models.py#L29)) and [test_models.py:44-54](tests/metrology/test_models.py#L44-L54) already asserts an `audit_finding` envelope round-trips with `sample=None`.

- Two record types: `audit_finding` (an `AuditRun`, findings inline) and a new `audit_noise_floor`.
- Two optional payload fields on `MetrologyRecord`, mirroring the existing optional-sibling pattern.
- `write_audit_run` / `list_audit_runs` / `write_noise_floor` / `list_noise_floors` on `MetrologyStore`, mirroring `write_graduation` / `list_graduations` ([store.py:152-188](src/squadron/metrology/store.py#L152-L188)) — including the tolerant-skip-with-WARNING scan convention.
- Id generators `audit-{YYYYMMDD}-{uuid8}` and `floor-{YYYYMMDD}-{uuid8}`, mirroring [store.py:60-70](src/squadron/metrology/store.py#L60-L70).
- Schema version stays `1`; the envelope shape is unchanged.

### Execution path

Modeled on `run_review_with_profile` ([review_client.py:54](src/squadron/review/review_client.py#L54)) — the only existing precedent that sets a per-project `cwd`, applies tool permissions, and filters SDK tool-narration out of the captured text. The audit needs all three: it runs against *another* repo, it must be allowed to run `rg`/`git`/language tooling, and its response contains heavy tool narration around the block we want.

The harness does **not** reuse `run_review_with_profile` itself — that function builds review prompts and calls `parse_review_output`. It is a structural template, not a dependency.

## Data Flow

```
project path ──> derive_project_id ──────┐
             └─> git rev-parse HEAD ─────┤
                                         ├──> AuditRun ──> MetrologyStore
skill file ──> build_audit_prompt ───┐   │                 (audit_finding)
           └─> audit_prompt_hash ────┤   │                        │
                                     ▼   │                        │
                          agent run (cwd=project) ────────────────┘
                                     │
                                     ▼
                          parse_audit_findings
                                     │
       ┌─────────────────────────────┴──────────────────────────┐
       ▼                                                        ▼
reduce_noise_floor (N runs, same commit+hash)          baseline_report
       │                                                        ▲
       └──> MetrologyStore (audit_noise_floor) ─────────────────┘
```

Data flows **into** the store and out to reports. Nothing in this slice reads the store at pipeline runtime — the down-only discipline 324 must honor starts being true here.

## Interface Specification

CLI, matching the 320/321/322 conventions (`--cwd` on every command, `--json` emitting the Pydantic model verbatim, `MetrologyStoreError` → red + exit 1, empty results → dim message + exit 0):

```
sq metrology audit run <project-path>...   [--profile] [--json] [--cwd]
    One audit per project. Persists an AuditRun each. Resumable by design:
    each project persists independently.

sq metrology audit variance <project-path>...  [--runs N] [--profile] [--cwd]
    N independent audits per project at pinned HEAD; refuses a dirty worktree.
    Reduces each series to an AuditNoiseFloor. --runs defaults to
    metrology.audit_variance_runs.

sq metrology report baseline   [--project] [--category] [--json] [--cwd]
    Cross-project baseline at the project/issue-class grain. Every figure
    carries its project's floor, or is marked "no floor measured".
```

### New config keys

Registered in `config/keys.py` (a key absent there raises `KeyError` on read):

| Key | Type | Default | Purpose |
|---|---|---|---|
| `metrology.audit_variance_runs` | `int` | `3` | Runs per project in a variance series |
| `metrology.audit_profile` | `str` | `None` | Provider profile for audit runs; unset → the review default |

Note the existing constraint: `_coerce_value` ([manager.py:54-61](src/squadron/config/manager.py#L54-L61)) handles only `int` and `str`, so both new keys are settable via `sq config set`. No float keys are added.

## Success Criteria

Restating the slice-plan criteria as verifiable conditions:

- [ ] The audit runs against **more than one** project and its findings normalize into persisted records carrying category, location, and severity, keyed on `derive_project_id`.
- [ ] Run-to-run variance is measured on **unchanged code** — verified by a pinned commit SHA per series, with a dirty worktree refused — and persisted as an explicit `AuditNoiseFloor`.
- [ ] The baseline report presents the floor alongside every figure; a project with no measured floor is marked as such and **never** borrows another project's.
- [ ] The report is at the project/issue-class grain and emits **no agreement dimension** — asserted by a test that no report path produces a human-comparison figure.
- [ ] Findings that cannot be normalized are retained and counted (`other` + `raw_category`, `unnormalized_count`), never silently dropped — asserted by a test feeding an out-of-vocabulary category.
- [ ] Persistence reuses the 320 spine: new record types behind the existing envelope discriminator, no new storage engine, schema version unchanged.
- [ ] The vendored skill file's enumerated categories exactly match `AuditCategory` — asserted by a test, so drift between the canonical fork and squadron's copy fails CI.
- [ ] The contract edits are present in the canonical fork (`github:ecorkran/tech-debt-audit`), not only in squadron's vendored copy — otherwise other consumers run a different instrument whose audits silently never pool.
- [ ] Repeated runs in a variance series are **independent** — asserted by a test that the independent-run preamble is present and the repeat-run clause does not apply.
- [ ] A variance series that spans differing commit SHAs or prompt hashes is **refused**, not averaged.
- [ ] The full existing suite passes; no judging-path or dispatch-path behavior changes.

## Verification Walkthrough

Draft — refined when Phase 6 completes.

**1. The instrument is well-formed.**
```
sq metrology audit run . --json | jq '.findings | length, (.[0])'
```
Expect a findings list with populated `category` drawn from the closed vocabulary, a `location`, and a `severity`. Confirms harness → skill → parse end-to-end on this repo.

**2. Findings actually persisted, keyed on stable identity.**
```
ls ~/.config/squadron/metrology/audit-*.json | head
jq '.record_type, .audit_run.project_id' ~/.config/squadron/metrology/audit-*.json | head
```
Expect `"audit_finding"` and `github.com/ecorkran/squadron` with `source: remote` — **not** a filesystem path.

**3. The noise floor, on unchanged code.**
```
git status --porcelain          # must be empty
sq metrology audit variance . --runs 3
```
Expect three audits at one SHA, reduced to one floor record. Then confirm the refusal path:
```
touch scratch.tmp && sq metrology audit variance . --runs 3   # expect refusal, exit 1
```

**4. The floor is visible in the baseline, and its absence is honest.**
```
sq metrology report baseline
```
Expect per-project/per-category counts with the floor attached. A project audited but not variance-measured shows **"no floor measured"**, not a borrowed number.

**5. Cross-project, and the vocabulary holds elsewhere.**
```
sq metrology audit run ../migratory ../../context-forge ../migratory-viewer
sq metrology report baseline --json | jq '.cells | group_by(.project_id) | length'
```
Expect ≥ 2 projects. Inspect the `other` share — a high share on any one project means the vocabulary does not fit that codebase, which is a finding about the instrument.

**6. Comparability is enforced.** Edit the skill file, re-run one audit, and confirm the baseline groups the two runs separately by `audit_prompt_hash` rather than pooling them.

**7. Nothing else moved.**
```
pytest -q && pyright
```

## Risks

- **The model does not reliably emit the fenced block.** Mitigation: the block is specified in the skill file where the model is already following a detailed protocol, and the parser fails loudly at the boundary rather than half-parsing. If drift proves common in practice, the fallback is parsing the human findings table — noted in Future Work rather than built speculatively.
- **Subagent fan-out on >50k-LOC repos is itself a variance source.** Not mitigated — it is *measured*, and expected on squadron and context-forge. Because `:97` is a prompt instruction rather than enforced code, fan-out may vary *within* a series, which widens that project's floor. Correct behavior: it is noise a real user experiences. This is why the set spans an order of magnitude in size.
- **A fork edit that skips the squadron sync (or vice versa) forks the instrument silently.** `audit_prompt_hash` refuses to pool across differing prompts, so the symptom is audits that never compare rather than a visible failure. Mitigated by the category-match test (CI) and by hashing the vendored copy actually used, so divergence is recorded in the data even if it escapes CI.
- **The 9 dimensions may not fit every codebase.** Surfaced via the `other` share rather than hidden; `trading-data` is the named case where this is most likely.

## Future Work

1. [ ] **Human-table fallback parser** — parse the markdown findings table when the fenced block is absent. Deferred: adds a second normalization surface and test matrix for a failure mode not yet observed. Effort: 2/5.
2. [ ] **`trading-data` in the variance set** — run the stretch case (timescaledb/caggs, ~66k LOC Python) to test whether the 9 dimensions fit a database-heavy codebase or collapse into one category. Effort: 1/5.
3. [ ] **Periodic re-audit cadence** — the audit is currently run once or on project adoption; monthly re-audit is the intended cadence and is not automated. Depends on nothing in this slice; the records already carry `measured_at`. Effort: 2/5.
4. [ ] **Project registry** — no enumeration of squadron-managed projects exists; every command here takes explicit paths. A registry would serve this slice and 324. Effort: 2/5.
