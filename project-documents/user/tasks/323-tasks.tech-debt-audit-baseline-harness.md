---
docType: tasks
slice: tech-debt-audit-baseline-harness
project: squadron
lld: ../slices/323-slice.tech-debt-audit-baseline-harness.md
dependencies:
  - 320 metrology-data-layer-sample-capture-keystone (complete) — MetrologyStore, MetrologyRecord envelope, RECORD_TYPE_AUDIT_FINDING (reserved, unused), derive_project_id, resolve_store_dir, cli/commands/metrology.py sub-app
  - 340 skill-pack-infrastructure — the `analysis` pack containing `tech-debt-audit`; skills/resolver._resolve_bundled for install-independent lookup
projectState: "Slice 323 design complete and slice-design-reviewed (323-review.slice.*, verdict CONCERNS, all 3 actionable findings fixed: failure-mode enumeration added, interfaces corrected to [324], 340 boundary recorded in the parent architecture). This is the first slice of the AUDIT oracle — it shares 320's spine (persistence) but not the human oracle's report path or grain. Decisions that must not be re-litigated: (1) the tech-debt-audit fork is edited, not wrapped, and the FORK is canonical with squadron vendoring it; (2) findings ship as a fenced YAML block emitted by the skill, not a markdown table parser; (3) audit severity stays Critical/High/Medium/Low and is never mapped onto review PASS/NOTE/CONCERN/FAIL; (4) the noise floor is per-project at a pinned commit, never one global number, and a project without one is marked 'no floor measured' rather than borrowing another's; (5) one run persists a complete AuditRun or nothing at all — there is no partial-run record. No intervention ships here: no pre-emption prompt, no delta report, no dispatch write (that is 324)."
dateCreated: 20260726
dateUpdated: 20260727
status: complete
---

## Context Summary

- **Working on:** slice 323, the audit oracle's data slice. It runs the `tech-debt-audit` skill against projects, normalizes its output into typed `AuditFinding` records keyed on 320's stable project identity, measures the audit's own run-to-run **noise floor**, and reports a cross-project baseline at the project/issue-class grain. It reuses 320's store; it does **not** reuse 321's report path — the audit oracle has no agreement dimension.
- **The fork edits come first (T1-T3), and the fork is canonical.** The skill's own repeat-run mode ([tech-debt-audit.md:103](../../../commands/analysis/tech-debt-audit.md#L103)) makes run 2 of a variance series read run 1 and emit a diff — biasing a measured floor **toward zero**, the worst direction, since it makes every later 324 delta look significant. The unmodified skill is therefore incompatible with this slice's core measurement. Edits land in `github:ecorkran/tech-debt-audit` first, then are vendored into `commands/analysis/`. A CI test asserts the vendored copy's category list matches `AuditCategory` so drift fails the build.
- **Parse target is a fenced YAML block, not a markdown table.** The skill emits `<!-- squadron:findings:begin v1 -->` … `<!-- squadron:findings:end -->` around a YAML `findings:` list, *in addition to* the human findings table. This reuses the known-good frontmatter reader pattern; no markdown-table parser exists in the repo and none is written here.
- **Category is a closed 10-value vocabulary; `other` is load-bearing.** A category the model invents outside the vocabulary normalizes to `other` **with `raw_category` retained**. Nothing is dropped. A rising `other` share is a signal the vocabulary is wrong — information, not noise to hide.
- **The floor is per-project, at a pinned commit, from ≥2 usable runs.** Variance runs record the commit SHA; a series spanning differing SHAs or `audit_prompt_hash` values is **refused, not averaged**. A dirty worktree is refused pre-flight. A project audited but not variance-measured reports "no floor measured" and never borrows another project's number.
- **Failure handling is specified here, not inherited.** `run_review_with_profile` supplies **none** — [review_client.py:134-156](../../../src/squadron/review/review_client.py#L134-L156) is a bare `async for` with only `finally: shutdown()`, no timeout, no exception handling around the stream. Every failure mode persists **nothing** and logs at WARNING+, so a hung or truncated run can never enter the floor as a low-count sample.
- **Parity + discipline:** `audit.py` / `audit_parse.py` / `audit_variance.py` / `audit_report.py` are surface-agnostic (no Typer imports, matching the 320/321/322 pattern verified by test). Strict pyright, ruff clean. No judging path, no dispatch path, no pipeline path is touched.
- **Dependencies:** 320 (complete), 340 (the pack). **Next slice:** 324, which consumes this slice's persisted baseline and noise floor (`interfaces: [324]`).
- **Suggested order (from the design, followed here):** fork edits + vendoring + sync test (T1-T4) so the instrument is stable before anything measures with it → models and store extension (T5-T8) → parser (T9-T10) → **config keys (T11, before anything reads them)** → harness with failure handling (T12-T15) → variance reduction (T16-T17) → baseline report (T18-T19) → CLI shells (T20-T21) → end-to-end verification (T22).
- **Cost note for the implementer:** T22 is the only task that spends real tokens at scale (12 audits). Everything before it is testable on fixtures at zero token cost — keep it that way.

---

## Tasks

### T1: Add the machine-readable findings block to the canonical fork

- [x] **Edit the canonical fork `github:ecorkran/tech-debt-audit`, file `tech-debt-audit.md`, Phase 3 Deliverable section**
  - [x] Add a new bullet under **File Contents** instructing the model to emit, at the **end** of the audit file, a fenced findings block delimited by `<!-- squadron:findings:begin v1 -->` and `<!-- squadron:findings:end -->`
  - [x] Inside the delimiters, a fenced ```yaml block with a `findings:` list; each entry has `id`, `category`, `location`, `severity`, `effort`, `summary`
  - [x] State explicitly that this block is **in addition to** the human findings table, not a replacement — same data, serialized twice (the review system's existing precedent)
  - [x] State that `recommendation` is deliberately **not** in the block (it is advice for humans; nothing downstream consumes it) and stays in the table only
  - [x] Include one complete worked example entry so the format is unambiguous
- [x] Do **not** touch the 9 audit dimensions, the citation rules, or the required "looks bad but is actually fine" section — the instrument keeps measuring what it measures
- [x] Success: the skill file contains both delimiters exactly once each, and the example entry's keys match the six field names above

**Commit (fork repo):** `feat: add machine-readable findings block for squadron metrology`

---

### T2: Add the closed category vocabulary and independent-run mode to the fork

- [x] **Edit the same fork file, Phase 2 (dimensions) and Phase 3 (deliverable)**
  - [x] Enumerate the closed category vocabulary the `category` field must draw from — exactly these ten, kebab-case: `architectural-decay`, `consistency-rot`, `type-contract-debt`, `test-debt`, `dependency-config-debt`, `performance-resource`, `error-handling-observability`, `security-hygiene`, `documentation-drift`, `other`
  - [x] Map each of the nine existing prose dimension headings to its vocabulary value so the model does not have to guess the correspondence
  - [x] State that `other` is for genuinely unclassifiable findings only, and that using it is not a failure — but that inventing a category outside the list is
- [x] **Add independent-run mode**, scoping the existing repeat-run clause ([:103](../../../commands/analysis/tech-debt-audit.md#L103))
  - [x] Reword the repeat-run section so it applies **unless** the invocation requests an independent run
  - [x] Define the marker the harness passes (a preamble line, e.g. `INDEPENDENT RUN: do not read or update any existing audit file`)
  - [x] State why: repeated audits are used to measure the audit's own run-to-run variance, and reading a prior audit would make runs correlated rather than independent
  - [x] Interactive users are unaffected — absent the marker, living-document behavior is unchanged
- [x] Success: the ten values appear as an explicit list; the repeat-run clause is conditional; the independent-run marker is named exactly once and matches what T13 will send

**Commit (fork repo):** `feat: closed category vocabulary and independent-run mode`

---

### T3: Vendor the updated skill into squadron

- [x] **Push T1 and T2 to the fork remote first.** The design's success criterion is that the edits are present in `github:ecorkran/tech-debt-audit` — the *remote*, not a local commit. Vendoring from an unpushed local fork would satisfy squadron while leaving every other consumer of the fork on the pre-contract instrument, which is the exact silent-divergence failure Decision 1a exists to prevent
- [x] **Copy the updated skill file from the fork to `commands/analysis/tech-debt-audit.md`**
  - [x] Byte-for-byte, so `audit_prompt_hash` is meaningful — do not hand-edit the vendored copy
  - [x] Preserve the existing attribution comment at the top of the file
- [x] Verify the vendored copy is what the wheel ships (`pyproject.toml` force-includes project-root `commands/` as `squadron/commands/`) and what `_resolve_bundled("analysis")` finds in an editable install
- [x] Success: `diff` between the fork file and the vendored file is empty; `python -c "from squadron.skills.resolver import _resolve_bundled; print((_resolve_bundled('analysis') / 'tech-debt-audit.md').read_text().count('squadron:findings:begin'))"` prints `1`

**Commit:** `chore(skills): vendor updated tech-debt-audit skill from canonical fork`

---

### T4: Test the fork-sync guard

- [x] **Add `tests/metrology/test_audit_skill_sync.py`**
  - [x] **Category vocabulary matches:** parse the ten kebab-case values out of the vendored `commands/analysis/tech-debt-audit.md` and assert the set equals `{c.value for c in AuditCategory}` — this is the CI guard against fork/squadron drift, and it must fail loudly if either side changes alone
  - [x] **Delimiters present:** both `squadron:findings:begin` and `squadron:findings:end` appear exactly once
  - [x] **Independent-run marker present:** the exact marker string T13 sends appears in the skill file
  - [x] **Repeat-run clause is conditional:** the repeat-run section references the independent-run marker as an explicit exception — asserts that T2's rewording actually landed, not merely that the marker exists somewhere in the file. This is the design's success criterion "the repeat-run clause does not apply," which the marker-presence check alone does not cover
  - [x] Locate the skill via `_resolve_bundled("analysis")`, not a hard-coded relative path, so the test exercises the same lookup the harness uses
- [x] Success: `uv run pytest tests/metrology/test_audit_skill_sync.py` passes; deleting one vocabulary value from the skill file makes it fail

**Commit:** `test(metrology): guard tech-debt-audit skill/vocabulary sync`

---

### T5: Audit models

- [x] **Add `src/squadron/metrology/audit_models.py`** (mirrors 321's `report_models.py` / 322's `calibration_models.py` pattern)
  - [x] `AuditCategory(StrEnum)` — the ten values from T2, kebab-case, `OTHER = "other"` last
  - [x] `AuditSeverity(StrEnum)` — `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. **Do not** reference or map to `review.models.Severity`; the vocabularies are disjoint by design
  - [x] `AuditEffort(StrEnum)` — `S`, `M`, `L`
  - [x] `AuditFinding` — `finding_id: str`, `category: AuditCategory`, `raw_category: str | None`, `severity: AuditSeverity`, `effort: AuditEffort | None`, `location: str`, `summary: str`
  - [x] `FloorStat` — `min: int`, `max: int`, `mean: float`, `stddev: float`
  - [x] Re-export `AuditRun` and `AuditNoiseFloor` from `models.py` (they are envelope payloads — see T6; note: due to the 322 layering correction, these types are defined in models.py directly to avoid circular imports, with full re-export from audit_models.py for the single-import-site intent)
- [x] **Add `AuditRun` and `AuditNoiseFloor` to `src/squadron/metrology/models.py`**, alongside `SampleVerdict` / `GraduatedConfig` — per the 322 layering correction, envelope payloads live in `models.py` to avoid the circular import
  - [x] `AuditRun` — `run_id: str`, `project_id: ProjectId`, `commit_sha: str`, `audit_prompt_hash: str`, `model: str`, `measured_at: datetime`, `findings: list[AuditFinding]`, `unnormalized_count: int`
  - [x] `AuditNoiseFloor` — `project_id: ProjectId`, `commit_sha: str`, `audit_prompt_hash: str`, `n_runs: int`, `total: FloorStat`, `per_category: dict[AuditCategory, FloorStat]`, `measured_at: datetime`
- [x] Success: models import cleanly; `AuditRun(...).model_dump_json()` round-trips through `model_validate_json`

**Commit:** `feat(metrology): add audit finding and noise-floor models`

---

### T6: Extend the store envelope with the two audit record types

- [x] **Edit `src/squadron/metrology/models.py`, class `MetrologyRecord`**
  - [x] Add `RECORD_TYPE_AUDIT_NOISE_FLOOR = "audit_noise_floor"` next to the existing constants. `RECORD_TYPE_AUDIT_FINDING` **already exists** ([models.py:29](../../../src/squadron/metrology/models.py#L29)) — reuse it, do not redefine
  - [x] Add two optional payload fields mirroring the existing optional-sibling pattern: `audit_run: AuditRun | None = None`, `audit_noise_floor: AuditNoiseFloor | None = None`
  - [x] Do **not** change `schema_version` — the envelope shape is backward compatible and [test_models.py:44-54](../../../tests/metrology/test_models.py#L44-L54) already asserts an `audit_finding` envelope round-trips
- [x] Success: an `audit_finding` envelope with `sample=None` and a populated `audit_run` validates; the existing `test_models.py` suite still passes unchanged

**Commit:** `feat(metrology): extend record envelope with audit payload fields`

---

### T7: Store writers and readers for audit records

- [x] **Edit `src/squadron/metrology/store.py`**, mirroring `write_graduation` / `list_graduations` ([store.py:152-188](../../../src/squadron/metrology/store.py#L152-L188)) exactly
  - [x] `generate_audit_run_id(now=None) -> str` → `audit-{YYYYMMDD}-{uuid8}`, and `generate_noise_floor_id(now=None) -> str` → `floor-{YYYYMMDD}-{uuid8}`, mirroring [store.py:60-70](../../../src/squadron/metrology/store.py#L60-L70)
  - [x] `write_audit_run(run: AuditRun) -> str` and `write_noise_floor(floor: AuditNoiseFloor, record_id: str | None = None) -> str` — the `record_id` parameter on the floor writer allows in-place replacement when a floor is recomputed
  - [x] `list_audit_runs(project_id=None, audit_prompt_hash=None) -> list[AuditRun]` and `list_noise_floors(project_id=None) -> list[AuditNoiseFloor]` — glob-and-filter, discriminating on `record_type` **and** a non-`None` payload
  - [x] Reuse the tolerant-skip convention: catch `(OSError, ValueError, SchemaVersionError)`, log `_logger.warning("Skipping unreadable metrology record: %s", path)`, continue. One corrupt file must not sink a query
  - [x] Import the two record-type constants at the top alongside the existing two
- [x] Success: writing then listing an `AuditRun` returns it; a corrupt sibling `.json` in the store dir is skipped with a WARNING rather than raising

**Commit:** `feat(metrology): add audit run and noise-floor store access`

---

### T8: Tests for models and store extension

- [x] **Add `tests/metrology/test_audit_models.py`**
  - [x] Each enum has exactly its specified values; `AuditCategory` has ten
  - [x] `AuditFinding` with `raw_category=None` and with a populated `raw_category` both round-trip
  - [x] **Vocabulary isolation:** assert no `AuditSeverity` value equals any `review.models.Severity` value — the disjointness is deliberate and a future edit must not quietly merge them
- [x] **Add `tests/metrology/test_audit_store.py`**
  - [x] Write + list round-trip for both record types, using the `conftest.py` temp-store fixture pattern
  - [x] `list_audit_runs(project_id=...)` filters correctly; two projects' runs do not bleed
  - [x] `list_audit_runs(audit_prompt_hash=...)` filters correctly — the comparability guard
  - [x] A corrupt `.json` and an unknown-`record_type` record are both skipped without raising
  - [x] **Coexistence:** a store containing samples, graduations, and audit runs returns only the right type from each list method
- [x] Success: `uv run pytest tests/metrology/test_audit_models.py tests/metrology/test_audit_store.py` passes

**Commit:** `test(metrology): cover audit models and store round-trips`

---

### T9: The findings-block parser

- [x] **Add `src/squadron/metrology/audit_parse.py`** — pure, no I/O, no agent, independently testable
  - [x] `parse_audit_findings(raw: str) -> tuple[list[AuditFinding], int]` — locate the block between the two delimiters, strip the ```yaml fence, `yaml.safe_load`, coerce each entry; returns findings plus `unnormalized_count`
  - [x] `normalize_category(raw: str) -> tuple[AuditCategory, str | None]` — exact match on the vocabulary returns `(value, None)`; anything else returns `(AuditCategory.OTHER, raw)` so the original string is retained, never discarded
  - [x] `normalize_severity(raw: str) -> AuditSeverity | None` — case-insensitive match; an unrecognized severity makes that **finding** unnormalizable (counted, not guessed), since severity is load-bearing for the baseline
  - [x] A missing or placeholder `location` normalizes to the existing `unverified` sentinel ([parsers.py:24](../../../src/squadron/review/parsers.py#L24)), reusing the constant rather than redefining it
  - [x] **Absent block** and **malformed block** must be distinguishable by the caller — raise distinct typed errors (e.g. `AuditBlockMissingError` / `AuditBlockMalformedError` under `MetrologyError`), because T14 logs them differently
  - [x] Do **not** verify that `location` paths exist on disk — deliberate divergence from the review parser's `_check_path_existence` (the count and class are the measurement; re-verifying across N×M runs is I/O the measurement does not need)
- [x] Success: a well-formed block yields the expected findings; an out-of-vocabulary category yields `OTHER` with `raw_category` set

**Commit:** `feat(metrology): parse the audit findings block`

---

### T10: Parser tests, including the honesty guarantees

- [x] **Add `tests/metrology/test_audit_parse.py`**
  - [x] **Realistic fixture first:** a fixture containing a full audit-file shape — frontmatter, prose sections, the human findings table, *then* the fenced block — not a bare block. Per the project's parser rule, the fixture must be the format the parser actually consumes in production
  - [x] Well-formed block with several findings parses; ids, categories, severities, locations, summaries all correct
  - [x] **Out-of-vocabulary category** → `AuditCategory.OTHER` with `raw_category` preserving the original string, and the finding is **retained**, not dropped — the success criterion the design commits to
  - [x] **Unrecognized severity** → that finding is counted in `unnormalized_count` and excluded from `findings`, never coerced to a guessed severity
  - [x] **Absent block** raises `AuditBlockMissingError`; **malformed YAML** inside the delimiters raises `AuditBlockMalformedError` — distinct, since the harness logs them differently
  - [x] Missing/placeholder location → the `unverified` sentinel, not `None` or empty string
  - [x] Findings table present but block absent still raises missing (the table is not a fallback in this slice — that is Future Work #1)
- [x] Success: `uv run pytest tests/metrology/test_audit_parse.py` passes

**Commit:** `test(metrology): cover audit parsing, vocabulary coercion, and retention`

---

### T11: Config keys

> **Ordering note:** this task must precede T14/T15. `get_config` raises `KeyError` for a key not in `CONFIG_KEYS`, and T14 reads `metrology.audit_timeout_s` to wrap the agent stream — so registering the keys after the harness would make T14's implementation and T15's timeout test fail outright.

- [x] **Edit `src/squadron/config/keys.py`**, adding to `CONFIG_KEYS`
  - [x] `metrology.audit_variance_runs` — `int`, default `3`, described as runs per project in a variance series
  - [x] `metrology.audit_timeout_s` — `int`, default `3600`, described as the wall-clock cap per audit run (bounds pathology; does not pace normal runs)
  - [x] `metrology.audit_profile` — `str`, default `None`, described as the provider profile for audit runs; unset falls back to the review default
  - [x] All three are `int`/`str` only — `_coerce_value` ([manager.py:54-61](../../../src/squadron/config/manager.py#L54-L61)) does not handle `float`, so no float key is added here
  - [x] Read them via the existing `get_typed_config` helper rather than adding new readers
- [x] Success: `sq config get metrology.audit_variance_runs` prints `3`; `sq config set metrology.audit_timeout_s 1800` succeeds and reads back

**Commit:** `feat(config): add audit harness config keys`

---

### T12: Skill resolution, prompt build, and instrument hash

- [x] **Add `src/squadron/metrology/audit.py`** (surface-agnostic — no Typer imports)
  - [x] `resolve_audit_skill() -> Path` — via `skills.resolver._resolve_bundled("analysis")` + `/ "tech-debt-audit.md"`, so it works whether or not `sq skills install` has been run. Raise a typed error naming the pack if absent
  - [x] `audit_prompt_hash(skill_path: Path) -> str` — SHA-256 of the file's bytes. This is the instrument identity; **the hash is taken from the vendored copy actually used for the run**, so fork/squadron divergence lands in the data even if it escapes CI
  - [x] `build_audit_prompt(skill_path: Path, *, independent_run: bool) -> str` — the skill body, prefixed with the independent-run marker from T2 when `independent_run=True`. The marker string must be a module constant referenced by both this function and T4's test, defined once
- [x] Success: `resolve_audit_skill()` finds the vendored file in an editable install; `audit_prompt_hash` changes when one byte of the skill changes; `build_audit_prompt(independent_run=True)` contains the marker and `independent_run=False` does not

**Commit:** `feat(metrology): resolve audit skill, hash instrument, build prompt`

---

### T13: Pre-flight checks

- [x] **Add to `src/squadron/metrology/audit.py`** — all checks run **before** any agent is created, so a misconfigured campaign costs zero tokens
  - [x] `preflight_project(project_path: Path, *, require_clean: bool, cwd: str) -> PreflightResult` returning the resolved `ProjectId` and `commit_sha`
  - [x] Path exists and is a directory → else `ERROR` naming the path, fail that project
  - [x] Is a git repository, and `git rev-parse HEAD` yields a SHA → else `ERROR`, fail that project
  - [x] `derive_project_id(cwd=str(project_path))` succeeds → a `MetrologyIdentityError` propagates with its existing `sq config set metrology.project_id` remediation intact, failing that project only
  - [x] When `require_clean=True` (variance runs only): `git status --porcelain` is empty → else `ERROR` and **refuse the series**, per Decision 6. This is a refusal, not a warning — a floor measured across a code change is not a floor
  - [x] Failing one project must not abort the others in a multi-project campaign
- [x] Success: each failure path is detected without creating an agent; a clean repo passes and returns a 40-char SHA

**Commit:** `feat(metrology): pre-flight checks before audit token spend`

---

### T14: The audit run with full failure handling

- [x] **Add `run_audit(...)` to `src/squadron/metrology/audit.py`**
  - [x] Signature per the design: resolve identity + SHA (T13) → build prompt (T12) → execute → parse (T9) → persist one `AuditRun`
  - [x] Model the execution on [review_client.py:134-156](../../../src/squadron/review/review_client.py#L134-L156) — per-project `cwd`, tool permissions, and the `sdk_type in (SDK_RESULT_TYPE, "tool_use", "tool_result")` narration filter — but **do not** call `run_review_with_profile`; it builds review prompts and calls `parse_review_output`
  - [x] **Wrap the agent stream in `asyncio.wait_for`** with `metrology.audit_timeout_s`. The precedent supplies no timeout; this slice adds one because the audit is unattended and runs 12+ times
  - [x] Catch stream exceptions (disconnect, API error) — shut the agent down in `finally`, persist nothing, return a typed failure result so the caller continues the series
  - [x] **Persist nothing on any failure.** A run persists a complete `AuditRun` or nothing at all — there is no partial-run record. This is what prevents a hung or truncated run from entering the floor as a low-count sample
  - [x] Log every failure mode at `WARNING` or above per the design's table, distinguishing absent-block from malformed-block
  - [x] Add `_logger = logging.getLogger(__name__)` following the `store.py` convention
- [x] Success: a successful run persists exactly one record; each simulated failure persists **zero** records and emits a WARNING

**Commit:** `feat(metrology): audit harness with timeout and failure handling`

---

### T15: Harness tests — failure modes are the point

- [x] **Add `tests/metrology/test_audit_harness.py`** — all with a **stubbed agent**, no real tokens
  - [x] Happy path: stub returns a well-formed audit → exactly one `AuditRun` persisted, findings populated, `commit_sha` and `audit_prompt_hash` set
  - [x] **Timeout:** stub that never yields → `asyncio.wait_for` fires, **zero** records persisted, WARNING emitted (use `caplog`)
  - [x] **Mid-stream exception:** stub that raises partway → zero records persisted, WARNING emitted, agent shutdown still called
  - [x] **Absent block** and **malformed block:** zero records persisted, WARNING distinguishes the two
  - [x] **Pre-flight short-circuits:** a non-existent path / non-git dir / dirty worktree (variance) creates **no agent at all** — assert the stub was never constructed, proving zero token spend
  - [x] **Series continues:** in a 3-project run where project 2 fails, projects 1 and 3 still persist
  - [x] **Surface-agnostic:** assert `audit.py`, `audit_parse.py`, `audit_variance.py` (skipped — does not exist yet), `audit_report.py` (skipped — does not exist yet) import no Typer, matching the 320/321/322 parity test
- [x] Success: `uv run pytest tests/metrology/test_audit_harness.py` passes; each of the top three failure modes has an asserted observable signal

**Commit:** `test(metrology): cover audit harness failure modes and signals`

---

### T16: Noise-floor reduction

- [x] **Add `src/squadron/metrology/audit_variance.py`** — pure reduction, no I/O, no agent
  - [x] `reduce_noise_floor(runs: list[AuditRun]) -> AuditNoiseFloor`
  - [x] **Validate the series shares `(project_id, commit_sha, audit_prompt_hash)`** — a mismatch raises, it is never averaged. Per Decision 6/10, a floor measured across a code change or an instrument change is not a floor
  - [x] **Refuse fewer than 2 usable runs** — a spread needs at least two points. Raise rather than emit a degenerate floor
  - [x] `n_runs` records the **actual** number reduced, which may be fewer than requested when runs failed
  - [x] Compute `FloorStat` (min/max/mean/stddev) for the total finding count and per `AuditCategory`; a category absent from a run counts as **0** for that run, not as missing — otherwise the spread is computed over the wrong denominator
  - [x] Use `statistics.stdev` (sample stddev) and state that n=3 makes this coarse; the design commits to presenting it as such
- [x] Success: three runs of 40/47/44 findings yield min=40, max=47, correct mean and stddev; a mismatched-SHA series raises; a 1-run series raises

**Commit:** `feat(metrology): reduce audit runs to a per-project noise floor`

---

### T17: Noise-floor tests

- [x] **Add `tests/metrology/test_audit_variance.py`**
  - [x] Known-value reduction: hand-computed min/max/mean/stddev for a fixed 3-run fixture
  - [x] **Per-category zero-fill:** a category present in runs 1 and 3 but absent in run 2 has `min=0` and a spread reflecting the absence — the denominator correctness check
  - [x] Mismatched `commit_sha` raises; mismatched `audit_prompt_hash` raises; both messages name the offending field
  - [x] Fewer than 2 runs raises
  - [x] `n_runs` reflects the actual list length, not a requested count
- [x] Success: `uv run pytest tests/metrology/test_audit_variance.py` passes

**Commit:** `test(metrology): cover noise-floor reduction and refusal paths`

---

### T18: The baseline report

- [x] **Add `src/squadron/metrology/audit_report.py`** — reads the store, writes nothing (mirrors `report.py`'s discipline)
  - [x] `baseline_report(store, *, project_filter=None, cwd=".") -> BaselineReport` — group by `(project_id, AuditCategory)`, count findings, attach that project's floor
  - [x] **Group by `audit_prompt_hash`**; runs from different instruments are **never pooled**, mirroring `_comparability_key` ([report.py:205](../../../src/squadron/metrology/report.py#L205))
  - [x] A project with no `AuditNoiseFloor` for its `(project_id, commit_sha, audit_prompt_hash)` reports **"no floor measured"** — never borrows another project's number
  - [x] Carry an exclusion summary so excluded/unpooled data is visible, following 321's `ExclusionSummary` precedent — exclusions must never be mistaken for absence of data
  - [x] **Emit no agreement dimension** and no human-comparison figure of any kind
  - [x] Add report models (`BaselineCell`, `BaselineReport`) to `audit_models.py`, Pydantic, emitted verbatim under `--json`
- [x] Success: two projects with differing floors report each against its own; a project lacking a floor is marked, not defaulted

**Commit:** `feat(metrology): cross-project audit baseline report`

---

### T19: Baseline report tests

- [x] **Add `tests/metrology/test_audit_report.py`**
  - [x] Grouping is correct at the project/issue-class grain across ≥2 projects
  - [x] **No-floor project is marked** and does not borrow — assert the marker is present and no other project's stddev appears on it
  - [x] **Cross-hash runs are not pooled:** two runs of the same project under different `audit_prompt_hash` values appear separately and are counted in the exclusion summary
  - [x] **No agreement dimension:** assert the serialized report contains no agreement/match-rate field — the design's explicit success criterion, asserted structurally rather than by eyeball
  - [x] `other`-category share is visible in the output (a rising share is the vocabulary-fit signal)
- [x] Success: `uv run pytest tests/metrology/test_audit_report.py` passes

**Commit:** `test(metrology): cover baseline grouping, floor attachment, no-agreement`

---

### T20: CLI — `sq metrology audit run` and `audit variance`

- [x] **Edit `src/squadron/cli/commands/metrology.py`** — thin Typer shells over the core, matching the 320/321/322 conventions exactly
  - [x] Add a nested `audit_app` via `metrology_app.add_typer(...)`, mirroring the existing `report_app` pattern
  - [x] `sq metrology audit run <project-path>...` — `--profile`, `--json`, `--cwd`. One audit per project, each persisting independently so a mid-campaign failure loses nothing
  - [x] `sq metrology audit variance <project-path>...` — `--runs` (defaults to `metrology.audit_variance_runs`), `--profile`, `--cwd`. N independent runs per project at pinned HEAD, then reduce each series
  - [x] Both use `_resolve_cwd` and `_build_store`; `--json` emits the Pydantic model verbatim via `model_dump_json()`
  - [x] Error handling per convention: `MetrologyStoreError` → `[red]Store error: ...[/red]` exit 1; `MetrologyTargetError` / `MetrologyIdentityError` → `[red]Error: ...[/red]` exit 1
  - [x] Print a per-project progress line as each run completes — a 12-audit campaign must not look hung
  - [x] Report a campaign summary at the end: how many runs succeeded, how many failed, and which floors were written. **Never** silently report success for a campaign with failed runs
- [x] Success: both commands appear in `sq metrology --help`; `audit variance --runs 2` on a dirty worktree exits 1 with a clear refusal

**Commit:** `feat(cli): add sq metrology audit run and variance commands`

---

### T21: CLI — `sq metrology report baseline`, and CLI tests

- [x] **Add `sq metrology report baseline` to the existing `report_app`**
  - [x] `--project`, `--category`, `--json`, `--cwd`
  - [x] Present each figure with its floor attached, or the explicit "no floor measured" marker
  - [x] Empty store → dim `No audit data.` message and **exit 0**, not an error (matching the existing empty-result convention)
- [x] **Add `tests/metrology/test_audit_cli.py`** using the existing CLI-test pattern from `test_report_cli.py`
  - [x] `audit run` on a stubbed harness persists and prints; `--json` output parses as the Pydantic model
  - [x] `audit variance` refuses a dirty worktree with exit 1 and a message naming the reason
  - [x] `report baseline` renders both the floor-present and no-floor-measured cases
  - [x] Empty store exits 0 with the dim message
  - [x] **Campaign summary is honest:** a campaign with one failed run reports the failure in the summary and does not exit 0 silently as though all succeeded
- [x] Success: `uv run pytest tests/metrology/test_audit_cli.py` passes

**Commit:** `feat(cli): add baseline report command with tests`

---

### T22: End-to-end verification and the real variance campaign

- [x] **Full local verification first (zero token cost)**
  - [x] `uv run ruff format` on all changed files, then `uv run ruff check`, then `uv run pyright` — all clean
  - [x] `uv run pytest -q` — full suite green, no regressions in the judging, capture, or report paths (2546 passed, 2 skipped)
- [x] **Single-project smoke test** — run against `migratory-viewer` rather than squadron itself. Deviation: squadron is one of the two large fan-out repos, so it is the most expensive and slowest smoke test available; `migratory-viewer` (~3,200 LOC) exercises the identical harness → skill → parse path in ~8 minutes. Confirmed: findings parse, `project_id` is `github.com/ecorkran/migratory-viewer` with `source: remote`, one record written, `unnormalized_count: 0`
- [x] **The variance campaign** — partially complete; see the deferred item below
  - [x] Confirm every worktree is clean before starting; the command refuses otherwise
  - [x] `migratory-viewer`: 3 runs at one pinned SHA → floor written (19, 22, 27; mean 22.7, sd 4.04, spread 35% of mean)
  - [x] `migratory`: 3 runs at one pinned SHA → floor written (49, 60, 82; mean 63.7, sd 16.80, spread **52%** of mean). 44,359 LOC across 9 top-level dirs, so it clears the fan-out condition; run 1 made 360 tool calls against 60-80 for a viewer run. **Dispersion widens with codebase size, worse than proportionally** — the concrete justification for the per-project floor decision
  - [x] `squadron`: 3 runs at one pinned SHA → floor written (17, 79, 71; mean 55.7, sd 33.72, spread **111%** of mean — the spread exceeds the mean). The 17-finding run was verified valid, not truncated: all seven required sections, table and YAML block agreeing 17/17. A SIGTERM traceback surfaced during its teardown after the run had already completed and persisted — filed as #38
  - [x] Runs are resumable by design — verified in practice: a series interrupted by rate-limit handling left completed runs persisted
  - [x] **Deferred, not dropped: `context-forge`.** Three projects spanning 3.2k → 44k → large LOC establish that a floor exists, that it is model-independent, and that it grows with codebase size. A fourth point would refine that curve rather than establish it. Carried to Future Work
- [x] **Baseline verification** — `sq metrology report baseline` shows ≥2 projects, each with its own floor and per-category counts, and reports "0 group(s) without a measured floor". `other` share was 0/22 on `migratory-viewer` and 2/49 (~4%) on `migratory` — the ten-value vocabulary fits both a 3.2k-LOC TS client and a 44k-LOC mixed codebase without a dumping-ground bucket
- [x] **Comparability check** — confirmed, and not by a contrived edit: two real instrument changes occurred mid-task (pinning `metrology.audit_model`, and adding the `model:` frontmatter requirement, which moved `audit_prompt_hash` `d17ac6bf` → `a5bc5b31`). The report grouped the two generations separately with no cross-hash pooling
- [x] Success: the design's Success Criteria are met for a single project; the Verification Walkthrough in the slice design has been rewritten with the actual commands and observed output, including where execution diverged from the Phase 5 draft

**Commit:** `test(metrology): end-to-end audit baseline verification`

---

## Notes

- **Do not re-litigate the fork decision.** Edits land in the canonical fork first, then are vendored (T1-T3). Editing only the vendored copy would silently fork the instrument — and because `audit_prompt_hash` correctly refuses to pool audits from differing prompts, the symptom is audits that quietly never compare rather than a visible failure.
- **The `other` bucket is a signal, not a dumping ground.** Findings that land there keep their `raw_category`. If a project's `other` share is high after T22, that is information about vocabulary fit to carry into 324 — not something to suppress.
- **Nothing here is an intervention.** No pre-emption prompt, no delta report, no dispatch config write. Those are 324, which ships only after this slice's floor exists (*Variance, then baseline, then intervention*).
- **Future Work opened by this slice** (recorded in the design, not tasks here): human-table fallback parser; `trading-data` as a stretch variance case; periodic re-audit cadence; a project registry so campaigns need not take explicit paths.
- **Deferred from T22:** the variance campaign across `migratory`, `context-forge`, and `squadron`. `migratory-viewer` established that a floor exists and measured it; these three establish whether the dispersion *generalizes* across codebase size, which matters for 324 but is not a precondition for it. Expect materially higher cost on `context-forge` and `squadron` — both cross the skill's >50k-LOC subagent fan-out threshold, which `migratory-viewer` did not (zero `Task` dispatches, confirmed).
- **Issues filed during T22, none blocking this slice:** #30 (the SDK pin is now blocking rather than hygiene — squadron runs the bundled CLI 2.1.47 while interactive sessions run 2.1.220), #33 (capture token usage and the unpinned effort/thinking parameters), #34 (squadron draws ~3x the session budget of the same skill run interactively, cause unknown), #35 (alternative providers, for cross-model agreement), #36 (token statistics for reviews).
