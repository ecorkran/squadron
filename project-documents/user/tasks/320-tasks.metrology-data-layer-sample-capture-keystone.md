---
docType: tasks
slice: metrology-data-layer-sample-capture-keystone
project: squadron
lld: ../slices/320-slice.metrology-data-layer-sample-capture-keystone.md
dependencies:
  - 100 orchestration-v2 (complete) — CLI app, ReviewResult, review persistence
  - 140 pipeline-foundation (complete) — config system (config/manager.py, config/keys.py), StateManager store precedent (pipeline/state.py), user-dir convention ~/.config/squadron/
  - 300 numeric-scoring-foundation (complete) — persisted ReviewResult (score/criteria/provenance), review/persistence.py file layout
projectState: "Initiatives 100/140/300 complete. 300 review results are id-less flat files written by review/persistence.py to project-documents/user/reviews/{index}-review.{type}.{slice}.{ext}, overwritten on re-run — no run-id, no DB, no query surface over scores. Config system: config/manager.py (TOML, ~/.config/squadron/config.toml), keys in config/keys.py CONFIG_KEYS. Store precedent: pipeline/state.py StateManager (Pydantic + schema version + atomic write + glob-filter). CLI: Typer, sq entrypoint, cli/app.py, cli/commands/. MCP surface is a stub. No DB dependency. No project identity exists in the codebase."
dateCreated: 20260718
dateUpdated: 20260718
status: not_started
---

## Context Summary

- **Working on:** the keystone slice of initiative 320. Build the user-level/central **metrology store** and the **blind, non-blocking human-sample capture** command that writes into it. No reporting, no agreement math, no threshold feedback, no audit records, no MCP tool.
- **Central reality (from the LLD):** 300 judge results are id-less flat files, overwritten on re-run. This slice must *introduce* two things squadron has today: a **stable project identity** (git-remote-derived, `.squadron.toml` fallback, explicit failure — never a path) and a **content-addressed judge-result reference** so a sample attaches unambiguously to one result.
- **Store shape (from the LLD):** follow `StateManager` (`pipeline/state.py`) exactly — user-level `~/.config/squadron/metrology/`, Pydantic records at the file boundary, `_SCHEMA_VERSION` + `SchemaVersionError`, atomic write-then-rename, one JSON file per record, glob-and-filter query. **No new DB dependency.** A `record_type` envelope discriminator (`"sample"` now, `"audit_finding"` reserved) lets 323 extend without migration.
- **Blindness (from the LLD):** enforced at the *data layer* — the capture core builds the presented payload from artifact + ground truth only and never places judge output in it. Assertable by a test on the payload, not a UI convention. Scoped to designated calibration samples; escalated-gate review flow is untouched.
- **Parity (from the LLD):** a surface-agnostic core package `squadron.metrology`; the CLI is a thin Typer shell delegating to it (the `config.py` pattern). The future MCP tool wraps the same core with zero logic duplication.
- **Failure modes (from the LLD):** every new I/O boundary has an enumerated mode with an observable signal and a required test — three typed exceptions (`MetrologyIdentityError`, `MetrologyTargetError`, `MetrologyStoreError`). Absent git remote is a *normal* fallback case, not an error.
- **Discipline:** the 300 judging path is unmodified — full existing test suite passes; a judge run with no metrology store present behaves exactly as before. Strict pyright + ruff on all new code. Config values centralized in `CONFIG_KEYS`, never hard-coded.
- **Dependencies:** 100, 140, 300 — all complete. **Next slice:** 321 (Agreement & Dispersion Reporting), which reads this store grouped by project + judge configuration.

---

## Tasks

### T1: Package scaffold and typed exceptions

- [ ] **Create the `src/squadron/metrology/` package** with `__init__.py` exporting the public surface (filled in as later tasks land)
- [ ] **Add `src/squadron/metrology/errors.py`** defining three exceptions, each subclassing a common `MetrologyError(Exception)` base:
  - [ ] `MetrologyIdentityError` — no stable project identity derivable
  - [ ] `MetrologyTargetError` — target review result missing / malformed / zero-or-multi match
  - [ ] `MetrologyStoreError` — store write/dir failure (wraps the underlying `OSError`)
- [ ] Each exception message is actionable (names the fix or the offending path); no bare messages
- [ ] Success: `from squadron.metrology.errors import MetrologyError, MetrologyIdentityError, MetrologyTargetError, MetrologyStoreError` imports; `uv run pyright` passes

**Commit:** `feat(metrology): add package scaffold and typed exceptions`

---

### T2: Project identity derivation

- [ ] **Add `src/squadron/metrology/identity.py`** with `derive_project_id(cwd: str) -> ProjectId`
  - [ ] Primary source: git remote URL via subprocess `git config --get remote.origin.url`, following the existing `git_utils` subprocess pattern (`check=False`, bounded `timeout`)
  - [ ] Normalize the URL: strip credentials, strip trailing `.git`, normalize scp-vs-https form to one canonical string
  - [ ] Fallback: read `metrology.project_id` from project config (`.squadron.toml`) via `config.manager`
  - [ ] If neither is present → raise `MetrologyIdentityError` naming the fix (`sq config set metrology.project_id <id>`); **never** derive from a filesystem path
- [ ] `ProjectId` is a Pydantic model (canonical string + a marker of its source: `remote` | `recorded`)
- [ ] Success: with a fake remote, returns a normalized id; with no remote but a recorded id, returns the recorded id marked `recorded`; with neither, raises `MetrologyIdentityError`; a hung/absent git call does not hang the function (timeout honored)

**Commit:** `feat(metrology): add stable project identity derivation`

---

### T3: Tests for project identity

- [ ] **Add `tests/metrology/conftest.py`** with fixtures: a `tmp_path` git repo (remote set / no remote), and a project-config writer for `.squadron.toml`
- [ ] **Add `tests/metrology/test_identity.py`**
  - [ ] Remote URL variants normalize to the same canonical id (https, scp, trailing `.git`, embedded credentials)
  - [ ] No remote + recorded `metrology.project_id` → returns recorded id, source `recorded`
  - [ ] No remote + no recorded id → raises `MetrologyIdentityError` with an actionable message
  - [ ] git absent / non-repo → treated as remote-absent (falls through), not a crash
- [ ] Success: `uv run pytest tests/metrology/test_identity.py` passes

**Commit:** `test(metrology): cover project identity derivation`

---

### T4: Judge-result reference and judge-config identity

- [ ] **Extend `identity.py`** with `derive_result_ref(review_file_path, project_id) -> JudgeResultRef` and `derive_judge_config_id(result) -> JudgeConfigId`
  - [ ] `JudgeResultRef` = `(project_id, relative_review_path, content_hash)`; `content_hash` is SHA-256 (stdlib `hashlib`) over a **canonical projection** of the judge fields (verdict, score, criteria, template_name, model, timestamp, findings) with findings sorted and paths relative — stable for a given result, distinct after a re-run overwrites the file
  - [ ] `JudgeConfigId` = `(template_name, model, template_content_hash)`; `template_content_hash` computed at capture time from the resolved template content
  - [ ] Both are Pydantic models
  - [ ] Reading the review file: missing → `MetrologyTargetError` naming the path; malformed / missing required judge fields (score, template, model) → `MetrologyTargetError` naming what could not be parsed; never hash a partial result
- [ ] Success: same result file → same `content_hash`; a materially different result → different hash; missing/malformed file → `MetrologyTargetError`

**Commit:** `feat(metrology): add content-addressed result ref and judge-config id`

---

### T5: Tests for result ref and judge-config identity

- [ ] **Add `tests/metrology/test_result_ref.py`**
  - [ ] Identical review-result content yields an identical `content_hash` (stability)
  - [ ] A changed score / verdict / findings yields a different `content_hash` (sensitivity)
  - [ ] Finding order in the file does not change the hash (canonical projection)
  - [ ] Missing review file → `MetrologyTargetError`; malformed file (no score/template/model) → `MetrologyTargetError`
  - [ ] `derive_judge_config_id` returns `(template_name, model, template_content_hash)` from a sample result
- [ ] Success: `uv run pytest tests/metrology/test_result_ref.py` passes

**Commit:** `test(metrology): cover result ref stability and target failures`

---

### T6: Record models

- [ ] **Add `src/squadron/metrology/models.py`** (Pydantic, file boundary)
  - [ ] `SampleVerdict`: `sample_id`, `project_id: ProjectId`, `result_ref: JudgeResultRef`, `judge_config: JudgeConfigId`, `human_verdict: str` (Verdict enum value), `human_note: str | None`, `artifact_level: str | None`, `captured_at: datetime` (UTC), `blind: bool`
  - [ ] `MetrologyRecord` envelope: `schema_version: int`, `record_type: str` (`"sample"` now; `"audit_finding"` reserved), `sample: SampleVerdict | None`
  - [ ] Reuse `Verdict` from `squadron.review.models` for verdict validation
- [ ] Success: a `MetrologyRecord` round-trips `model_dump_json()` → `model_validate_json()`; `blind` defaults consistent with the capture surface writing `True`; `uv run pyright` passes

**Commit:** `feat(metrology): add sample verdict and record envelope models`

---

### T7: Tests for record models

- [ ] **Add `tests/metrology/test_models.py`**
  - [ ] `SampleVerdict` + `MetrologyRecord` round-trip through JSON unchanged
  - [ ] An invalid `human_verdict` (not a `Verdict` value) is rejected at validation
  - [ ] `record_type` discriminator accepts `"sample"`; envelope with `sample=None` and a non-sample type validates (reserves the 323 path)
- [ ] Success: `uv run pytest tests/metrology/test_models.py` passes

**Commit:** `test(metrology): cover record models and verdict validation`

---

### T8: Metrology store

- [ ] **Add `src/squadron/metrology/store.py`** with `MetrologyStore`, modeled on `StateManager` (`pipeline/state.py`)
  - [ ] Constructor takes `store_dir: Path | None` → default `~/.config/squadron/metrology/` (resolve via the same user-dir helper `config.manager` uses); `mkdir(parents=True, exist_ok=True)`
  - [ ] `_SCHEMA_VERSION` constant + `_SUPPORTED_SCHEMA_VERSIONS` set + `SchemaVersionError` on unknown version (reuse or mirror the state.py exception)
  - [ ] `write_sample(sample: SampleVerdict) -> str`: envelope the record, write `{sample_id}.json` via atomic write-then-rename; wrap `OSError` in `MetrologyStoreError`
  - [ ] `list_samples(project_id=None, judge_config=None) -> list[SampleVerdict]`: glob the dir, load+validate each record, filter in memory, return typed records
  - [ ] `sample_id` generation: `sample-{YYYYMMDD}-{uuid8}` (mirror the `run_id` pattern)
- [ ] Success: writing then listing returns the record; unwritable store dir → `MetrologyStoreError` with no partial file at the final path; an unknown-version file → `SchemaVersionError`

**Commit:** `feat(metrology): add user-level metrology store`

---

### T9: Tests for the store

- [ ] **Add `tests/metrology/test_store.py`** (model on `tests/pipeline/test_state.py`)
  - [ ] Round-trip: `write_sample` then `list_samples` returns the same record
  - [ ] Atomic write: no partial `{sample_id}.json` remains when the write path is made to fail (→ `MetrologyStoreError`)
  - [ ] Schema-version rejection: a record file with an unsupported `schema_version` raises `SchemaVersionError`
  - [ ] **Cross-project query:** records written under two different `project_id`s are both returned by an unfiltered `list_samples`; filtering by one `project_id` returns only its records
  - [ ] Filtering by `judge_config` narrows correctly
- [ ] Success: `uv run pytest tests/metrology/test_store.py` passes

**Commit:** `test(metrology): cover store round-trip, atomicity, cross-project query`

---

### T10: Blind capture core

- [ ] **Add `src/squadron/metrology/capture.py`** with the surface-agnostic capture orchestration (no Typer imports)
  - [ ] `resolve_target(target, review_type, cwd) -> Path`: resolve a path or `(index, type)` to exactly one review file; zero matches → `MetrologyTargetError`; multiple matches → `MetrologyTargetError` listing candidate types
  - [ ] `build_capture_payload(review_file, cwd) -> CapturePayload`: load the **artifact and its ground truth** (from the result's `input_files` / `sourceDocument`) and **explicitly exclude** the judge's score/verdict/findings from the payload
  - [ ] `record_sample(payload, human_verdict, note, *, store, blind=True) -> str`: derive identity/ref/config, construct `SampleVerdict`, write via the store
  - [ ] **Budget check:** before writing, count captures already recorded for this `project_id` in the current budget period via `store.list_samples(project_id=...)`; if the count is at or above `metrology.sample_budget`, refuse the write and signal budget-exhausted (do **not** write, do **not** raise a store/target error — this is a normal "ceiling reached" outcome the CLI reports and exits cleanly on). *Scope note:* this slice enforces the budget as a ceiling on **captures written**, because the *offering/selection policy* (which results are proffered) is deferred to 321 — there is no offer queue here to gate. The store sees every write, so the write-ceiling is the enforceable slice of the design's "respects the configured budget" criterion.
  - [ ] A separate `reveal(review_file)` accessor returns the judge output for optional **post-commit** display only — never called before `record_sample`
- [ ] Success: the object returned by `build_capture_payload` contains artifact + ground truth and contains **no** judge score/verdict/findings (this is the load-bearing blindness property); `record_sample` returns a `sample_id` and the store holds the record; at/over `metrology.sample_budget` for the project, `record_sample` refuses and writes nothing

**Commit:** `feat(metrology): add blind, non-blocking capture core`

---

### T11: Tests for capture core (blindness is load-bearing)

- [ ] **Add `tests/metrology/test_capture.py`**
  - [ ] **Blindness:** `build_capture_payload` output contains the artifact + ground truth and does **not** contain the judge's score, verdict, or findings (assert on the payload object/fields directly)
  - [ ] Target resolution: a valid path resolves; a valid `(index, type)` resolves; zero matches → `MetrologyTargetError`; multiple types for one index → `MetrologyTargetError` naming candidates
  - [ ] `record_sample` writes a `blind=True` record joinable back to the target via `result_ref`
  - [ ] **Budget enforcement:** with `metrology.sample_budget = N`, the (N+1)th `record_sample` for the same `project_id` refuses and writes nothing; a capture for a *different* `project_id` under its own budget still succeeds (ceiling is per-project)
  - [ ] `reveal` returns judge output (used only post-commit) — exists and is independent of the blind payload
- [ ] Success: `uv run pytest tests/metrology/test_capture.py` passes

**Commit:** `test(metrology): assert capture payload excludes judge output`

---

### T12: Config keys

- [ ] **Add three keys to `CONFIG_KEYS` in `src/squadron/config/keys.py`**
  - [ ] `metrology.store_dir` (str, default `None` → `~/.config/squadron/metrology/`) — store location override (mainly tests)
  - [ ] `metrology.sample_budget` (int, small non-zero default) — offered-sample ceiling the capture surface respects
  - [ ] `metrology.project_id` (str, default `None`, project-level via `.squadron.toml`) — recorded fallback identity
- [ ] Wire the store and identity code to read these keys (no hard-coded call-site defaults)
- [ ] Success: `sq config list` shows the three keys with descriptions and defaults; identity fallback reads `metrology.project_id`; store honors `metrology.store_dir`

**Commit:** `feat(metrology): register store/budget/project-id config keys`

---

### T13: Tests for config keys

- [ ] **Add `tests/metrology/test_config.py`** (or extend `tests/config/`)
  - [ ] The three keys are present in `CONFIG_KEYS` with correct types and defaults
  - [ ] Setting `metrology.project_id` at project level is read by identity fallback
  - [ ] Setting `metrology.store_dir` redirects where the store writes
- [ ] Success: `uv run pytest` for the config tests passes

**Commit:** `test(metrology): cover metrology config keys`

---

### T14: CLI sub-app (thin shell)

- [ ] **Add `src/squadron/cli/commands/metrology.py`** — a `typer.Typer()` sub-app, following the `config.py` pattern (thin shell, all logic in `squadron.metrology`)
  - [ ] `sample <target> [--type REVIEW_TYPE] [--verdict V] [--note TEXT] [--skip]`:
    - blind flow — print artifact + ground truth (never judge output), prompt `Your verdict [PASS/CONCERNS/FAIL]:`, commit, then offer post-commit reveal
    - non-TTY without `--verdict` → explicit error instructing to pass `--verdict` (no hang)
    - SIGINT / EOF at the prompt → treat as skip: record nothing, exit 0 (INFO "sample skipped")
    - invalid verdict → re-prompt (interactive) or error (`--verdict` mode); `--skip` / empty records nothing, exit 0
    - **budget exhausted** (core refuses per `metrology.sample_budget`) → print a clear "budget reached for this project" message and exit 0 (a ceiling, not an error)
    - `--type` required and enforced only when a bare index is ambiguous
  - [ ] `list [--project ID] [--judge-config KEY]`: print raw stored records (inspection aid, **not** the 321 reporting surface — no agreement math)
- [ ] **Register in `cli/app.py`** via `app.add_typer(metrology_app, name="metrology")`
- [ ] Success: `sq metrology --help` lists `sample` and `list`; `sq metrology sample` on a real review file captures blindly and prints a `sample_id`

**Commit:** `feat(cli): add sq metrology sample/list commands`

---

### T15: CLI + failure-mode tests

- [ ] **Add `tests/metrology/test_cli.py`** using Typer's `CliRunner`
  - [ ] `sample` on a real review file records a blind sample and prints the `sample_id`
  - [ ] `list` shows the stored record
  - [ ] **Budget exhausted:** with `metrology.sample_budget` reached for the project, `sq metrology sample` reports the ceiling and exits 0, writing nothing
  - [ ] **Failure-mode coverage (one assertion per Failure Modes table row):** missing target → `MetrologyTargetError` / non-zero exit; ambiguous bare index → error naming candidate types; non-TTY without `--verdict` → error, no hang; `--skip` / interrupt → nothing written, exit 0; bad `--verdict` value → error, no record; identity absent (no remote, no recorded id) → `MetrologyIdentityError`; unwritable store dir → `MetrologyStoreError`, no partial file
- [ ] Success: `uv run pytest tests/metrology/test_cli.py` passes; every Failure Modes row is asserted

**Commit:** `test(metrology): cover CLI capture and all enumerated failure modes`

---

### T16: Full validation and judging-path regression gate

- [ ] **Run the full suite:** `uv run pytest` (entire repo) — the 300 judging path and all existing tests pass unchanged
- [ ] **Run static checks:** `uv run pyright` and `uv run ruff check` — zero errors on new code; `uv run ruff format` before commit
- [ ] **Manual regression:** a normal `sq review slice <n>` with no metrology involvement behaves exactly as before; a fresh user with no store present sees an empty store on first write, not an error in the judging path
- [ ] **Walkthrough smoke:** execute the LLD Verification Walkthrough steps 1–6 (produce a judge result → blind capture → `list` join → cross-project aggregation across two repos → fail-fast on ambiguous/missing target → explicit identity failure)
- [ ] Success: full suite green, static checks clean, walkthrough steps pass; if this completes the slice, mark the slice plan entry `(320)` and the slice-design frontmatter `status: complete`

**Commit:** `test(metrology): full validation pass for 320 keystone`

---

## Coverage Check (design → tasks)

- Package/exceptions → T1 · Project identity → T2/T3 · Result ref + judge-config id → T4/T5 · Record models → T6/T7 · Store (StateManager shape, cross-project) → T8/T9 · Blind capture core (data-layer blindness) → T10/T11 · Sample-budget enforcement (per-project write ceiling) → T10/T11 core + T14/T15 CLI · Config keys → T12/T13 · CLI thin shell + parity core → T14/T15 · Judging-path regression + walkthrough → T16.
- **Failure Modes table (all rows)** → jointly T3 (git-remote-absent/timeout), T5 (missing/malformed target), and T15 (the remaining rows: zero/multi-match, store-write failure, non-TTY, SIGINT/EOF, invalid input, identity absent). T15's "one assertion per row" bullet covers its rows; T3/T5 cover theirs at the unit level.
- Deferred by design, correctly absent here: agreement/dispersion (321), version-keying resolution + evidence floor (322), audit records (323), MCP tool (later), any 300 write-path change.
