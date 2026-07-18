---
docType: slice-design
slice: metrology-data-layer-sample-capture-keystone
project: squadron
parent: ../architecture/320-slices.judge-calibration-quality-metrology.md
dependencies: [100, 140, 300]
interfaces: [321, 322, 323, 324]
dateCreated: 20260718
dateUpdated: 20260718
status: not_started
---

# Slice Design: Metrology Data Layer & Sample Capture (keystone)

## Overview

This slice builds the durable, user-level home for oracle verdicts and the low-friction human-sample capture surface that writes into it. It is the keystone of initiative 320: every subsequent slice (agreement/dispersion reporting, calibration-to-threshold feedback, the audit baseline harness, and pre-emption delta measurement) reads from this store, keys on the project identity it defines, and depends on its blind-capture guarantee. This slice ships **no reporting, no agreement math, no threshold feedback** — it de-risks the three load-bearing decisions the architecture named (store locality, stable project identity, blind-capture ergonomics) plus the one the architecture surfaced only obliquely and this design must confront head-on: **the persisted judge result has no stable identifier to key against**.

## Value

Architectural enablement. Human agreement data begins accumulating with a verifiable, unambiguous link to the judge result it grades, in a store that aggregates across every project the operator runs. Nothing downstream can be built until this store, its identity keys, and its capture surface exist and are proven in isolation. The value is realized when: a human verdict persists, joins back to the exact judge result it graded, and a cross-project query returns samples from more than one project.

## Technical Scope

**Included:**
- A user-level/central metrology store at `~/.config/squadron/metrology/`, following the `StateManager` precedent (Pydantic records at the file boundary, schema versioning, atomic write, glob-and-filter query surface).
- Pydantic record models for a **human sample verdict** and the store's **judge-result reference** and **judge-configuration identity**.
- A **stable, explicit project identity** derivation (repo-derived, not a filesystem path), introduced here because none exists in squadron today.
- A **stable judge-result reference** — a content-addressed pointer to the specific persisted 300 review result being graded, introduced here because 300 results have no id and are overwritten on re-run.
- A **blind, inline, non-blocking, budgeted** capture command (`sq metrology sample`) that presents an artifact and its ground truth for an independent human verdict with the judge's output withheld until after the human commits, then records that verdict against the referenced judge result.
- A shared **core module** (`squadron.metrology`) that both the CLI (now) and the future MCP surface (later) call, preserving interface parity by construction.
- Config keys for the sampling budget and store location.

**Explicitly excluded (deferred to named slices):**
- Agreement, dispersion, or trend computation → 321.
- Version-keying *resolution* (coordinated 300 write-path field vs. content-hash-at-capture as the shipped strategy) and the minimum-evidence floor → 322. This slice *persists* a judge-configuration identity and a content hash; it does not decide which becomes the comparability key or build the recommendation that depends on it.
- Audit-findings records and the noise-floor harness → 323. The store's schema is designed to *admit* a second record type later without migration pain, but no audit record ships here.
- Any change to the 300 judging path. This slice reads 300's output; it does not modify the parser, the result models' write semantics, or the gate mechanics.
- The MCP tool itself (the MCP surface does not exist yet — `mcp/__init__.py` is a stub). Parity is guaranteed structurally via the shared core module, not by shipping an MCP tool now.

## Dependencies

### Prerequisites
- **100 (foundation)**, **140 (executor/config/CLI infrastructure)** — the Typer CLI app, the `~/.config/squadron/` user-dir convention, the `squadron.config.manager` config system, and the `StateManager` store precedent all land here.
- **300 (numeric scoring foundation)** — the persisted `ReviewResult` (its `template_name`, `model`, `score`, `criteria`, and the reserved `provenance` field) is the judge result this slice references and grades. Persistence lives in `review/persistence.py`.

### Interfaces Required
- `squadron.review.models.ReviewResult` and its `to_dict()` serialization — the shape of what is being graded.
- `squadron.review.persistence` — where 300 writes review results (`project-documents/user/reviews/{index}-review.{type}.{slice}.{ext}`), the files this slice must reference stably.
- `squadron.config.manager` / `config.keys.CONFIG_KEYS` — to register metrology config keys.
- `squadron.review.git_utils.find_git_root` — the existing git entry point; this slice adds a remote-URL helper alongside it.
- The Typer app in `cli/app.py` — registration point for the new sub-app.

## Architecture

### Component Structure

A new package `src/squadron/metrology/` — the shared core all surfaces call:

- **`identity.py`** — project-identity and judge-result-reference derivation.
  - `derive_project_id(cwd) -> ProjectId`: repo-derived stable identity. Primary source: the git remote URL (`git config --get remote.origin.url`), normalized (strip credentials, trailing `.git`, normalize scp-vs-https form) to a canonical string. Fallback when no remote exists: a recorded project id read from `.squadron.toml` (`metrology.project_id`); if neither is present, the derivation **fails explicitly** rather than silently substituting a path — a project with neither a remote nor a recorded id cannot be sampled until the operator records one (a one-line `sq config` write, surfaced in the error). This honors the architecture's "stable, explicit, never a mutable path" constraint and its "fail explicitly, no silent fallback values" project rule.
  - `derive_result_ref(review_file_path) -> JudgeResultRef`: a content-addressed reference to the specific persisted judge result. Because 300 results carry no id and are overwritten on re-run, the reference is `(project_id, relative_review_path, content_hash)` where `content_hash` is a SHA-256 over the canonical judge fields of the result (verdict, score, criteria, template_name, model, timestamp, findings) — stable for a given result, distinct after a re-run overwrites the file. This is what makes "attaches unambiguously to one persisted judge result" real against a file-based, id-less source.
  - `derive_judge_config_id(result) -> JudgeConfigId`: the judge-configuration identity, `(template_name, model, template_content_hash)`. The template content hash is computed at capture time from the resolved template (the content-hash-at-capture material 322 may adopt). This slice *records* it; 322 *decides* whether it or a coordinated 300 write-path field becomes the comparability key.
- **`models.py`** — Pydantic records at the file boundary: `SampleVerdict`, `JudgeResultRef`, `JudgeConfigId`, `ProjectId`, plus a `MetrologyRecord` envelope carrying `schema_version` and a `record_type` discriminator (`"sample"` now; `"audit_finding"` reserved for 323).
- **`store.py`** — `MetrologyStore`, modeled directly on `StateManager`: constructed with a `store_dir` (default `~/.config/squadron/metrology/`), one JSON file per record keyed by a unique `sample_id` (`sample-{date}-{uuid}`), atomic write-then-rename, `_SCHEMA_VERSION` with a supported-versions set and a `SchemaVersionError`. Query surface is glob-and-filter in memory (`list_samples(project_id=None, judge_config=None, ...)`), matching the established `StateManager.list_runs` convention — **no new database dependency**.
- **`capture.py`** — the blind-capture orchestration: given a target review result, present the artifact + ground truth, withhold judge output, collect the independent verdict, then persist. This is pure core logic; the CLI is a thin shell over it.

CLI wrapper: **`cli/commands/metrology.py`** — a `typer.Typer()` sub-app registered in `app.py` via `app.add_typer(metrology_app, name="metrology")`, following the `config` sub-app pattern exactly (thin shell, all logic delegated to `squadron.metrology`).

Config: new entries in `config.keys.CONFIG_KEYS` (see Technical Decisions).

### Data Flow

**Capture (write path):**
1. Operator invokes `sq metrology sample <target>` (target identifies a persisted 300 review result — see API Contracts for target resolution).
2. Core resolves `project_id` (identity.py), `result_ref` and `judge_config_id` over the target result file.
3. Core loads the graded **artifact and its ground truth** (the reviewed document and its source, from the review result's `input_files` / `sourceDocument`) — **but not** the judge's score/verdict/findings.
4. Capture surface presents artifact + ground truth and prompts for an independent verdict. Judge output is not read into the presented text at all until after commit (blindness is enforced by *what the core loads and passes to the surface*, not merely by UI ordering — see Patterns).
5. Operator commits a verdict (or skips — skipping records nothing and exits cleanly).
6. Core constructs a `SampleVerdict` record (`sample_id`, `project_id`, `result_ref`, `judge_config_id`, human verdict, timestamp, capture context) and the store writes it atomically.
7. Post-commit only, the surface may reveal the judge's output for optional annotation (no effect on the recorded verdict).

**Query (read path, exercised by tests and later slices):**
- `MetrologyStore.list_samples(...)` globs the store dir, loads and validates each record, filters in memory by project / judge-config / record-type, and returns typed records. A cross-project query (no project filter) returns records from multiple `project_id`s.

### State Management

- All state lives in `~/.config/squadron/metrology/` (user-level, central — the architecture's store-locality commitment). This aggregates across every project the operator runs, which per-repo storage cannot do.
- Schema versioning mirrors `StateManager`: `_SCHEMA_VERSION` constant, `_SUPPORTED_SCHEMA_VERSIONS` set, `SchemaVersionError` on unknown versions. The `record_type` discriminator lets 323 add audit records without a migration.
- No shared-mutable-state concurrency concern beyond `StateManager`'s: one record per file, atomic write-then-rename; concurrent captures write distinct `sample_id` files.

## Technical Decisions

### Technology Choices
- **File-based store, no database.** Follows the established squadron convention (`StateManager`, config TOML, JSON run state) and the CLAUDE.md "resist complexity" principle. `sqlite3` is stdlib-available and reconsiderable in 321 if the query surface proves inadequate, but the keystone must not be the slice that introduces the project's first DB — the join and aggregation this slice needs are satisfied by glob-and-filter over per-record JSON. **Deferring to a DB now would be over-engineering for current needs.**
- **Pydantic at the file boundary** (per python.md and the `StateManager` precedent), `@dataclass` for internal identity value objects.
- **SHA-256 content hashing** (stdlib `hashlib`) for the judge-result reference and the template-content hash.
- **Git remote via subprocess**, alongside the existing `git_utils` subprocess pattern (no new dependency).

### Patterns and Conventions
- **Blindness is enforced at the data layer, not the UI.** The core loads artifact + ground truth into the capture-surface payload and *does not include* the judge's score/verdict/findings in that payload. This makes blindness a property of the interface contract (assertable by a test on the payload the surface receives), not a fragile "don't render this field yet" UI convention — matching the architecture's insistence that blindness is an architectural constraint on the capture surface, not slice-level ergonomics.
- **Blindness is scoped to designated calibration samples.** This command is the calibration-sampler surface. It is distinct from the escalated-gate review flow (which stays judge-assisted and is untouched here). A verdict formed after seeing judge output is anchored; the capture command never records such a verdict as blind agreement data.
- **Non-blocking, budgeted, pull-based.** The command is operator-initiated and never sits in any pipeline/gate/dispatch path — nothing in the executor waits on it. Skipping an offered sample succeeds and records nothing. Offered-sample volume is governed by a configured budget (a rate/ceiling config key); this slice *stores and respects* the budget as a ceiling on what the command offers, and defines the key — the *selection policy* for which results are offered (random / disagreement-triggered / escalation-triggered) is 321 slice-design detail, with the architecture's constraint that escalation-triggered offering may enqueue but never blinds the escalation review itself.
- **Fail-fast on ambiguous targets.** A capture target that resolves to zero or more than one judge result, or a project with no derivable identity, raises an explicit error — never records against a placeholder or the wrong result (the architecture's "mis-target fails explicitly" criterion).
- **Exception handling** per project rules: identity/target-resolution failures raise typed errors with actionable messages; no bare excepts, no silent defaults.

## Implementation Details

### API Contracts

**CLI (the surface that ships):**

```
sq metrology sample <target> [--type REVIEW_TYPE] [--verdict V] [--note TEXT] [--skip]
                                   # blind-capture a human verdict for one judge result
sq metrology list [--project ID] [--judge-config KEY]   # inspect stored samples (verification aid)
```

- **`<target>` resolution.** The target names a persisted 300 review result. Accepted forms (resolved by the core, fail-fast on ambiguity):
  - a **path** to a review file under `project-documents/user/reviews/` — used alone, `--type` is ignored; or
  - a **slice index** (integer) combined with `--type REVIEW_TYPE` (e.g. `slice`, `code`, `arch`) — resolved against the reviews dir in the current project to the file `{index}-review.{type}.{slice}.{ext}`. `--type` is **required** when the target is a bare index and there is more than one review type for that index; if omitted and the index is ambiguous, the command fails explicitly listing the candidate types.
  The core resolves the target to exactly one review file, derives `result_ref`, and proceeds. Zero or multiple matches → explicit error.
- **`sample` interaction (blind):** prints the artifact and its ground truth, prompts `Your verdict [PASS/CONCERNS/FAIL]:` (reusing the `Verdict` enum from `review.models`), optionally a one-line note, commits, then offers post-commit reveal. Non-interactive/`--verdict` form supported for scripted tests. Skipping (empty input / `--skip`) records nothing and exits 0.
- **`list`** is a verification/inspection aid this slice ships so the store is observable; it is *not* the reporting surface (that is 321) — it prints raw stored records, no agreement math.

Both commands are thin Typer shells delegating to `squadron.metrology`. The identical core is what a future `mcp` tool will call — parity by shared core, matching the `config.py` pattern.

### Failure Modes

Per the project's Failure-Mode Enumeration rule, each new I/O boundary this slice introduces has an enumerated failure mode, an explicit handling decision, and an observable signal (error/log at WARNING+ — never silent). Each row below gets at least one test asserting the observable outcome.

| Boundary | Failure | Handling | Observable signal | Test |
| --- | --- | --- | --- | --- |
| **git remote subprocess** (`git config --get remote.origin.url`) | git not installed / not a repo / command hangs | bounded `timeout` on the subprocess (following the existing `git_utils` subprocess pattern, which uses `check=False`); on any non-zero/empty/timeout result, treat remote as *absent* and fall through to the recorded-id path — **not** a hard error (missing remote is a normal case) | if it then also falls through to no recorded id, the identity error below fires | identity resolves via recorded id when remote absent; timeout does not hang the command |
| **project identity** (remote absent **and** no `.squadron.toml` `metrology.project_id`) | no stable identity derivable | **fail fast**, write nothing; error names the fix (`sq config set metrology.project_id <id>` at project level) | `MetrologyIdentityError` at ERROR; non-zero exit | error raised, actionable message, store unchanged |
| **read 300 review result** | file missing | fail fast, write nothing | `MetrologyTargetError` at ERROR naming the resolved path | missing target → explicit error, no record |
| **read 300 review result** | file present but malformed / unparseable / missing required judge fields (score, template, model) | fail fast, write nothing — never hash a partial result into a `result_ref` | `MetrologyTargetError` at ERROR naming what could not be parsed | malformed target → explicit error, no record |
| **target resolution** (bare index) | zero matches | fail fast | `MetrologyTargetError` listing where it looked | zero-match → error |
| **target resolution** (bare index) | multiple matches (several review types) | fail fast; do **not** guess | `MetrologyTargetError` listing candidate types and prompting `--type` | multi-match → error naming candidates |
| **store write** (atomic write-then-rename) | store dir not creatable / not writable / rename fails | fail fast, surface the OSError; the `.tmp` sibling is left for inspection or cleaned, never a partial record at the final path | `MetrologyStoreError` (wrapping OSError) at ERROR | unwritable store dir → error, no partial `{sample_id}.json` |
| **interactive capture** | non-TTY / piped stdin with no `--verdict` | do not block waiting on a human that isn't there; require `--verdict` in non-interactive mode | error instructing to pass `--verdict` (exit non-zero) | non-TTY without `--verdict` → explicit error, no hang |
| **interactive capture** | SIGINT / EOF during the verdict prompt | treat as a skip: record nothing, exit cleanly (skipping is always free and safe) | INFO "sample skipped", exit 0 | interrupt at prompt → nothing written |
| **interactive capture** | invalid verdict input (not a `Verdict` value) | re-prompt in interactive mode; reject with an error in `--verdict` mode | inline re-prompt / error on bad `--verdict` | bad `--verdict` value → error, no record |

The store-write and identity/target errors are distinct typed exceptions (`MetrologyStoreError`, `MetrologyIdentityError`, `MetrologyTargetError`) so callers — and the future MCP surface — can distinguish "your input was wrong" from "the store is broken." No boundary swallows its failure; the closest thing to a silent path (absent git remote) is deliberately *not* an error because it is a normal, expected case with a defined fallback, and it still surfaces loudly if the fallback also yields nothing.

### Storage Schema

One JSON file per record in `~/.config/squadron/metrology/`, filename `{sample_id}.json`. Record envelope (Pydantic):

```
MetrologyRecord (envelope)
  schema_version: int
  record_type: "sample"            # "audit_finding" reserved for 323
  sample: SampleVerdict

SampleVerdict
  sample_id: str                   # "sample-{YYYYMMDD}-{uuid8}"
  project_id: ProjectId            # stable, repo-derived
  result_ref: JudgeResultRef       # (project_id, relative_review_path, content_hash)
  judge_config: JudgeConfigId      # (template_name, model, template_content_hash)
  human_verdict: str               # Verdict enum value
  human_note: str | None
  artifact_level: str | None       # e.g. tasks-vs-slice — recorded if resolvable, for 321's per-level grain
  captured_at: datetime (UTC)
  blind: bool                      # True — this surface; recorded so anchored verdicts can never masquerade as blind
```

`ProjectId`, `JudgeResultRef`, `JudgeConfigId` are Pydantic sub-models. The `blind` flag is always `True` for records this command writes; it exists so that if a future non-blind capture path is ever added, blind and anchored data are distinguishable at the record level and 321 can exclude anchored records from agreement.

### Config Keys (added to `CONFIG_KEYS`)

- `metrology.store_dir` (str, default `None` → `~/.config/squadron/metrology/`) — store location override, mainly for tests.
- `metrology.sample_budget` (int, default a small non-zero ceiling, e.g. offered-samples-per-period) — the configured budget the capture surface respects. Representation (rate vs. ceiling, per-project vs. global) is finalized here as a simple global ceiling; per-project budgeting is a 321/322 refinement if needed. Value is centralized in config, never hard-coded at a call site (CLAUDE.md rule).
- `metrology.project_id` (str, default `None`, **project-level** via `.squadron.toml`) — the recorded fallback identity for repos with no git remote.

## Integration Points

### Provides to Other Slices
- **The metrology store** (`MetrologyStore`, write + queryable/joinable read, cross-project) — consumed by 321 (agreement/dispersion), 322 (calibration input), 323 (audit records via the reserved `record_type`), 324 (baseline/delta).
- **Project-identity derivation** (`derive_project_id`) — the stable key every later slice joins on.
- **Judge-result reference and judge-configuration identity** (`derive_result_ref`, `derive_judge_config_id`) — 321 groups agreement by judge-config; 322 consumes the judge-config identity and the template-content hash as candidate version keys.
- **The human-sample capture command** — the ongoing data source; 322's residual-sampling policy drives continued use of it post-graduation.

### Consumes from Other Slices
- **300's persisted `ReviewResult`** (via `review/persistence.py` files) — read-only. If a target review file is absent or malformed, the capture command fails explicitly; it never fabricates a result.
- **140's config + CLI + user-dir infrastructure** — extended, not modified.
- Degraded behavior: with no metrology store present (fresh user), the store initializes empty on first write; a judge run with no metrology involvement behaves exactly as before (the judging path is untouched).

## Success Criteria

### Functional Requirements
- A human sample verdict persists, keyed to (a) the specific 300 judge result it grades (via `result_ref`) and (b) the judge-configuration identity, and can be queried and joined back to that result.
- The store keys on a stable, explicit project identifier invariant across runs and machines (git-remote-derived or recorded id — never a filesystem path); a cross-project query returns samples from more than one project.
- The store is user-level/central at `~/.config/squadron/metrology/` and stands alone — it neither reads from nor writes to 280; its absence for a fresh user yields an empty store, not an error in the judging path.
- The capture surface is blind: the judge's score/verdict/findings are not in the payload presented before the human commits (asserted by a test on the capture payload), and reveal, if offered, is post-commit only.
- Blindness is scoped to designated calibration samples: the escalated-gate review flow is unchanged, and no escalated-gate verdict is recorded as blind agreement data.
- Capture never blocks execution: no pipeline/gate/dispatch waits on a human sample verdict; skipping an offered sample succeeds cleanly and records nothing; offered-sample volume respects the configured budget.
- Capture attaches unambiguously to one persisted judge result; a mis-target or absent target fails explicitly rather than recording against the wrong result or a placeholder.
- A project with neither a git remote nor a recorded `metrology.project_id` fails explicitly with an actionable message, never falling back to a path-derived identity.

### Technical Requirements
- The judging path (300) is unmodified: the full existing test suite passes, and a judge run with no metrology store present behaves exactly as before.
- New code passes strict pyright and ruff (per python.md); Pydantic at file boundaries, schema versioning with `SchemaVersionError`.
- Core logic (`squadron.metrology`) is surface-agnostic; the CLI is a thin shell — verified by the core having no Typer imports.
- Test coverage modeled on `tests/pipeline/test_state.py` (store round-trip, atomic write, schema-version rejection, cross-project query) and `tests/review/test_persistence.py` (record parse-back).
- Every row in the Failure Modes table has at least one test asserting its observable signal (typed error at ERROR / clean skip at INFO / no partial record) — silent failure paths are not acceptable.

### Integration Requirements
- 321 can, against this store, retrieve samples grouped by project and judge-configuration with the artifact-level field present — without any schema change.
- 323 can add an `audit_finding` record type behind the same envelope discriminator without a store migration.

### Verification Walkthrough

This is the demo script proving the slice delivers. Commands marked *(new)* are introduced by this slice.

1. **Produce a judge result to grade.** In a git repo with a remote, run an existing judge review (e.g. `sq review slice <n>`), which writes `project-documents/user/reviews/<n>-review.slice.<name>.md` with a `score:` field. *(existing)*

2. **Capture a blind human verdict.** *(new)*
   ```
   sq metrology sample <n> --type slice
   ```
   Confirm the output shows the reviewed artifact and its ground-truth source **and does not show the judge's score, verdict, or findings**. Enter a verdict at the prompt. Confirm it accepts the verdict and reports the stored `sample_id`. Optionally accept the post-commit reveal and confirm the judge's output appears only *after* the verdict was committed.

3. **Confirm the store and the join.** *(new)*
   ```
   sq metrology list
   ```
   Confirm one record is listed with a `project_id`, a `result_ref` pointing at the review file just graded, a `judge_config` of `(template, model, hash)`, and the human verdict. Inspect `~/.config/squadron/metrology/sample-*.json` and confirm the `result_ref.content_hash` matches a hash over the graded review file's judge fields.

4. **Confirm cross-project aggregation.** *(new)* Repeat steps 1–2 in a *second* git repo with a different remote, then from either location run:
   ```
   sq metrology list
   ```
   Confirm records from **both** `project_id`s are returned — proving user-level/central storage aggregating across projects.

5. **Confirm fail-fast on ambiguous / missing target.** *(new)* Run `sq metrology sample 999 --type slice` for a nonexistent review; confirm an explicit error, no record written.

6. **Confirm explicit identity failure.** *(new)* In a git repo with **no remote** and no `metrology.project_id` set, run `sq metrology sample ...`; confirm an explicit error naming the fix (record `metrology.project_id`), and that nothing was written under a path-derived identity.

7. **Confirm the judging path is untouched.** *(existing)* Run the full test suite and a normal judge review with no metrology involvement; confirm identical behavior to before this slice.

## Risk Assessment

### Technical Risks
- **The id-less join.** 300 results have no stable id and re-runs overwrite the file. If the content-hash reference is defined over volatile fields (e.g. absolute paths, non-deterministic finding ordering), the reference could be unstable. Mitigation: hash a canonical projection of the judge fields with sorted findings and relative paths; a test asserts the same result file yields the same hash and that a materially different result yields a different one.
- **Blindness leakage.** If the capture core loads the full review file (which contains judge output) and relies on the surface to hide it, blindness is one refactor away from breaking. Mitigation: the core constructs the presented payload from artifact + ground truth only and never places judge output in it; a test asserts judge fields are absent from the pre-commit payload.

### Mitigation Strategies
- Both risks are covered by explicit tests listed in Success Criteria; neither requires new infrastructure.

## Implementation Notes

### Development Approach
Suggested order within the slice:
1. `identity.py` (project id, result ref, judge-config id) + tests — the hardest decisions, and everything else keys on them.
2. `models.py` + `store.py` (modeled on `StateManager`) + store tests — round-trip, atomic write, schema-version rejection, cross-project query.
3. `capture.py` blind-capture core + tests asserting the pre-commit payload excludes judge output.
4. `cli/commands/metrology.py` thin shell + `app.py` registration + config keys.
5. End-to-end verification walkthrough.

### Special Considerations
- **Parity is structural.** No MCP tool ships here, but the core module is the single source of truth both surfaces call — the same pattern that keeps `config` in parity today. When the MCP surface lands (its own slice), the metrology tool wraps `squadron.metrology` with zero logic duplication.
- **Relative effort:** 4/5 (the keystone; identity and the id-less join are genuinely new territory for the codebase).
