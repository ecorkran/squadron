---
docType: slice-design
slice: tech-debt-audit-baseline-harness
project: squadron
parent: ../architecture/320-slices.judge-calibration-quality-metrology.md
dependencies: [320, 340]
interfaces: [324]
dateCreated: 20260726
dateUpdated: 20260726
status: complete
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

### Failure modes of the agent-execution path

The precedent supplies **no** failure handling to inherit, and this must not be assumed otherwise. [review_client.py:134-156](src/squadron/review/review_client.py#L134-L156) wraps the agent stream in a bare `async for` with only `finally: await agent.shutdown()`. There is **no timeout and no exception handling around the agent call**; every `try/except` in that module guards file and git I/O, not the stream. An exception propagates to the caller; a hang hangs indefinitely.

That is acceptable for an interactive, human-watched review. It is **not** acceptable here: the audit is unattended, runs 12+ times per variance campaign, targets an arbitrary external `cwd`, and may fan out into Task subagents ([:97](commands/analysis/tech-debt-audit.md#L97)) whose failures surface as a stalled or truncated parent stream. So this slice specifies handling rather than deferring to a precedent that has none.

The governing rule is Decision 9 — **one run is one persisted unit** — which makes the policy simple and uniform: *a run either persists a complete `AuditRun` or persists nothing and is skipped.* There is no partial-run record. A skipped run reduces the series' `n_runs`; it never corrupts the floor.

| Failure mode | Detection | Response | Observable signal |
|---|---|---|---|
| **Hang / no progress** | `metrology.audit_timeout_s` wall-clock cap on the whole run (default `3600`) | Abort the run, `agent.shutdown()` in `finally`, persist nothing | `WARNING` naming project, run index, elapsed |
| **Timeout mid-generation** | same cap | Same — a truncated audit is discarded, never parsed | `WARNING` with bytes received |
| **Peer disconnect / API error mid-stream** | exception from `handle_message` | Catch, shut down, persist nothing, continue the series | `WARNING` with exception type and message |
| **Findings block absent or malformed** | `parse_audit_findings` boundary (Decision 2) | Persist nothing — a run with no parseable findings is not a zero-finding run | `WARNING` distinguishing *absent* from *malformed* |
| **Subagent tool permission denied** | surfaces as reduced/absent findings, not an exception | No special handling; the run persists if it parsed | `INFO` on tool-narration filtering only |
| **Project cwd unreadable / not a git repo** | pre-flight, before any token spend | Fail that project fast; other projects continue | `ERROR` naming the path |
| **Identity underivable** | `MetrologyIdentityError` from `derive_project_id` | Fail that project fast, pre-flight | `ERROR` with the `sq config set` remediation |
| **Dirty worktree (variance only)** | pre-flight `git status --porcelain` | Refuse the series (Decision 6) | `ERROR`; refusal, not a warning |

Four properties follow, and each is separately assertable:

- **Pre-flight checks precede token spend.** cwd validity, git-repo-ness, identity derivation, and worktree cleanliness are all checked before the agent is created. A campaign misconfigured across four projects fails in seconds, not after hours of audits.
- **A failed run never silently becomes a data point.** Because nothing is persisted, a hung or truncated run cannot masquerade as a low-finding-count sample — which would bias the floor downward, the same direction Fact 2 warns about.
- **Series degrade rather than abort.** One failed run out of three leaves two persisted; `reduce_noise_floor` records the actual `n_runs` it reduced. A series that falls below 2 usable runs is **refused**, not reduced, since a spread needs at least two points.
- **Every failure is observable at `WARNING` or above**, per the project's failure-mode-enumeration rule, and at least one test asserts each of the top three modes emits its signal. `_logger` follows the module convention established in `store.py`.

One new config key follows: `metrology.audit_timeout_s` (`int`, default `3600`). One hour is deliberately generous — a fanned-out audit of a 64k-LOC repo is slow — and it exists to bound pathology, not to pace normal runs.

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
| `metrology.audit_timeout_s` | `int` | `3600` | Wall-clock cap per audit run; bounds pathology, does not pace normal runs |

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
- [ ] Each of hang/timeout, mid-stream disconnect, and absent-or-malformed findings block persists **nothing** and emits a `WARNING` — asserted by a test per mode, so a failed run can never enter the floor as a low-count sample.
- [ ] Pre-flight checks (cwd, git repo, identity, worktree cleanliness) run **before** the agent is created — asserted by a test that a misconfigured project spends no tokens.
- [ ] A series reduced with fewer runs than requested records its actual `n_runs`; a series with fewer than 2 usable runs is refused.
- [ ] The full existing suite passes; no judging-path or dispatch-path behavior changes.

## Verification Walkthrough

Executed 2026-07-27 against `migratory-viewer @5788a99a`. Commands and
observed output below; deviations from the Phase 5 draft are noted where they
occurred.

**Pre-requisite: audits cannot be driven from inside a Claude Code session.**
The SDK profile spawns its own CLI process, and that process refuses to launch
inside another (`Claude Code cannot be launched inside another Claude Code
session`). Every command below was run from a plain terminal.

**1. The instrument is well-formed.**
```
uv run sq metrology audit run /Users/manta/source/repos/manta/migratory-viewer
```
```
ok github.com/ecorkran/migratory-viewer @5788a99a  27 findings
Campaign: 1 succeeded, 0 failed.
```
Findings carried populated `category` values from the closed vocabulary, a
`location`, and a `severity`, with `unnormalized_count: 0`. Confirms harness →
skill → parse end-to-end.

**2. Findings actually persisted, keyed on stable identity.**
```
jq '.record_type, .audit_run.project_id' ~/.config/squadron/metrology/audit-*.json
```
```
"audit_finding"
{"value": "github.com/ecorkran/migratory-viewer", "source": "remote"}
```
Identity is the git remote, not a filesystem path, as required.

**3. The noise floor, on unchanged code.**
```
uv run sq metrology audit variance /Users/manta/source/repos/manta/migratory-viewer --runs 3
```
Three audits at one pinned SHA reduced to one floor record: **19, 22, 27
findings — mean 22.7, sd 4.04, spread 8**. The dirty-worktree refusal was
verified incidentally rather than by `touch`: the audit's own output file
(`analysis/940-analysis.*.md`) initially caused a series to refuse itself,
which is what motivated the artifact exemption in `_is_audit_artifact`.

**4. The floor is visible in the baseline, and its absence is honest.**
```
uv run sq metrology report baseline
```
```
github.com/ecorkran/migratory-viewer @5788a99a  22 findings  floor 19-27 (sd 4.04, n=3)
  architectural-decay                 7  (floor 7-7)
  consistency-rot                     4  (floor 2-4)
  type-contract-debt                  2  (floor 1-3)
  test-debt                           3  (floor 3-4)
  dependency-config-debt              2  (floor 1-6)
  ...
0 group(s) without a measured floor; 1 project(s) span multiple instruments
and are reported separately.
```
Per-category floors are the more useful output: `architectural-decay` was
perfectly stable across all three runs (7-7-7, sd 0) while
`dependency-config-debt` swung 1-6. Dispersion is **not** uniform across
categories, so some are gate-worthy and others are not.

**5. Cross-project.**
```
uv run sq metrology audit variance /Users/manta/source/repos/manta/migratory --runs 3
```
```
  run 1/3  ok github.com/ecorkran/migratory @2a2d1e4c  82 findings
  run 2/3  ok github.com/ecorkran/migratory @2a2d1e4c  60 findings
  run 3/3  ok github.com/ecorkran/migratory @2a2d1e4c  49 findings
floor github.com/ecorkran/migratory @2a2d1e4c  total 49-82 (mean 63.7, sd 16.80, n=3)
```
`migratory` is 44,359 LOC across 9 top-level directories, so it clears the
skill's fan-out condition (>50k LOC **or** >5 top-level modules) where
`migratory-viewer` did not. Run 1 made **360 tool calls** against 60-80 for a
viewer run, consistent with subagent dispatch.

The `other` share was 2/49 (~4%), so the ten-value vocabulary fits a second,
much larger codebase without becoming a dumping ground.

```
uv run sq metrology audit variance /Users/manta/source/repos/manta/squadron --runs 3
```
```
  run 1/3  ok github.com/ecorkran/squadron @ad1706f2  79 findings
  run 2/3  ok github.com/ecorkran/squadron @ad1706f2  17 findings
  run 3/3  ok github.com/ecorkran/squadron @ad1706f2  71 findings
floor github.com/ecorkran/squadron @ad1706f2  total 17-79 (mean 55.7, sd 33.72, n=3)
```
The 17-finding run was checked for damage and is **valid**: all seven required
sections present, findings table and YAML block in exact agreement (17/17), a
coherent executive summary with cited locations. A SIGTERM traceback appeared
in the terminal during that run's teardown, but the run had already completed
and persisted — the SDK terminates its own subprocess during `close()`, and the
error surfaces from an unawaited reader task (#38). It is genuinely a much less
exhaustive audit of the same code, not a truncated one.

`context-forge` remains deferred. See Future Work.

**6. Comparability is enforced.** Confirmed, and not by a contrived edit. Two
real instrument changes occurred mid-campaign: pinning the model
(`metrology.audit_model`, previously unset so the CLI chose its own) and
adding the `model:` frontmatter requirement to the skill, which moved
`audit_prompt_hash` from `d17ac6bf` to `a5bc5b31`. The baseline report split
the two generations into separate groups rather than pooling them, exactly as
designed.

**7. Nothing else moved.**
```
uv run pytest -q && uv run pyright && uv run ruff check .
```
```
2546 passed, 2 skipped
0 errors, 0 warnings, 0 informations
All checks passed!
```

### What the walkthrough established

**1. The dispersion is a property of the instrument, not of a model.**

| Instrument | Runs | Mean | Spread | % of mean |
|---|---|---|---|---|
| Opus, hash `d17ac6bf` | 22, 25, 27, 30 | 26.0 | 8 | 31% |
| Sonnet 5, hash `a5bc5b31` | 19, 22, 27 | 22.7 | 8 | 35% |

Two models, two sessions, two prompt hashes — the same absolute spread of 8
findings and near-identical relative dispersion. Neither series could establish
that alone.

**2. Dispersion widens with codebase size, and worse than proportionally.**

| Project | LOC | Runs | Mean | Spread | % of mean |
|---|---|---|---|---|---|
| migratory-viewer | 3.2k | 19, 22, 27 | 22.7 | 8 | **35%** |
| migratory | 44.4k | 49, 60, 82 | 63.7 | 33 | **52%** |
| squadron | large | 17, 79, 71 | 55.7 | 62 | **111%** |

On squadron the spread **exceeds its own mean**: the same audit of the same
unchanged commit returned 17 findings once and 79 another time. Note also that
squadron's mean (55.7) is *lower* than the smaller `migratory` (63.7) purely
because one run landed at 17 — with three samples, a single low draw moves the
mean more than the underlying difference between the codebases does. That is
itself a caution about n=3.

This confirms the design's stated risk: subagent fan-out is itself a variance
source, and because the >50k-LOC / >5-module condition is a prompt instruction
rather than enforced code, fan-out can vary *within* a series. **This is the
concrete justification for the per-project floor decision** — a single global
noise threshold would understate large repos by a wide margin and is not a
defensible simplification.

It is also a caution about the floor's own precision. Three runs is enough to
demonstrate that dispersion is large and size-dependent; it is not enough to
state any project's floor tightly. `metrology.audit_variance_runs` exists so
that number can be raised where a tighter floor is worth the cost.

**3. Per-category dispersion is where the usable signal is.**

| Category | viewer floor | migratory floor |
|---|---|---|
| `architectural-decay` | 7-7 (sd 0) | 8-11 |
| `consistency-rot` | 2-4 | 7-11 |
| `type-contract-debt` | 1-3 | 4-12 |
| `dependency-config-debt` | 1-6 | 4-9 |

`architectural-decay` was the most stable category on both projects — perfectly
stable on the small one and moving by only 3 on a 14x larger codebase with
fan-out. `type-contract-debt` tripled. So some categories are plausibly
gate-worthy today and others are not, which is the distinction 324 needs and
could not have been guessed from the totals.

**4. The category vocabulary holds.** `other` was 0/22 on viewer and 2/49
(~4%) on migratory — a 14x size difference and a different language mix, with
no dumping-ground bucket.

Practical consequence: a gate that treats "the audit found N issues" as a
stable signal is reading 35-111% noise on unchanged code, and the figure grows
with codebase size. **Totals are not gate-worthy at any size, and are
worthless on a large repo.** Specific stable categories may be — that is what
324 has to work with.

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
