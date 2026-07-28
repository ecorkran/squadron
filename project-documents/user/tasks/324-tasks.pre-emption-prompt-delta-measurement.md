---
docType: tasks
slice: pre-emption-prompt-delta-measurement
project: squadron
lld: ../slices/324-slice.pre-emption-prompt-delta-measurement.md
dependencies:
  - 323 tech-debt-audit-baseline-harness (complete) — run_audit, baseline_report, AuditRun, AuditNoiseFloor, ProjectBaseline, BaselineCell, MetrologyStore.list_audit_runs/list_noise_floors
  - 140 pipeline-foundation (complete) — DispatchAction, DispatchStepType.expand, PhaseStepType.expand
projectState: "Slice 324 design complete and slice-design-reviewed (324-review.slice.*, verdict PASS, 1 concern + 1 note both fixed: failure-mode table for the new file-read path added, YAML example clarified as a literal path not a template). This is the intervention slice that closes initiative 320's loop — the last of the five anticipated slices. Ground truth verified against the current code (not re-guessed): no static-prompt-injection point exists anywhere in dispatch today; system_prompt on AgentConfig is dead wiring (separate bug, filed as #40, out of scope here); the only existing concatenation point is DispatchAction._apply_override, called from the tail of _resolve_prompt; StepConfig.config/ActionContext.params are permissive plain dicts, so a new key is safe only when inserted conditionally, matching the existing 'if \"prompt\" in cfg: ...' idiom in steps/dispatch.py and steps/phase.py. Decisions that must not be re-litigated: (1) the fragment is generated once and frozen as a static file — dispatch never queries the metrology store at runtime; (2) fragment content is a fixed, human-authored category-to-guidance mapping, not model-generated prose; (3) regeneration is an explicit operator command, never automatic; (4) the delta report compares one fresh run to the stored baseline, relative to the stored floor's observed spread (floor.max - floor.min), never a derived confidence interval; (5) a broken/missing/malformed fragment file degrades to a skipped prepend plus a WARNING, never a dispatch failure."
dateCreated: 20260728
dateUpdated: 20260728
status: complete
---

## Context Summary

- **Working on:** slice 324, the audit oracle's intervention slice. It ships two things that only mean something together: a static "pre-emption fragment" generated from a project's persisted 323 baseline and threaded into dispatch prompts as opt-in static text, and a before/after delta report that compares a fresh audit run to the baseline relative to the measured noise floor. This is the last of initiative 320's five anticipated slices — its completion closes the loop and finishes the initiative.
- **The injection point is `DispatchAction._resolve_prompt`, extending the existing `_apply_override` prepend pattern** — not a new mechanism. The fragment is prepended *after* `_apply_override` returns, so a checkpoint override (if present) stays the innermost, most urgent instruction. Both `DispatchStepType.expand()` and `PhaseStepType.expand()` gain one conditional line each, matching the `if "prompt" in cfg: ...` idiom already used for every other field — this keeps every existing `expand()` exact-dict-equality test passing unmodified, which is itself a success criterion.
- **`expand()` stays pure.** No file I/O is added to either `expand()` method. The fragment file read happens inside `DispatchAction`, at dispatch time, not at pipeline-parse time. `pre_emption_fragment` in YAML is a literal path string — no template-variable resolution is added anywhere.
- **Fragment content is a fixed lookup table, not generated prose.** `CATEGORY_GUIDANCE: dict[AuditCategory, str]` is one short, human-authored line per one of the ten `AuditCategory` values (see 323's `audit_models.py`), written directly in this slice's tasks — not derived from any audit's `summary` fields. Category selection is presence-based (nonzero baseline count in a `BaselineCell`), not floor-filtered.
- **The file-read failure modes are fully specified in the design** (missing path, unreadable, empty/malformed header) — all three degrade to a skipped prepend plus a `WARNING`, asymmetric with 323's audit-run failure handling (which must persist nothing) because a missing fragment has no measurement to poison.
- **No new store record type.** The fragment is a plain file on disk, not a metrology record. The delta report is computed on demand from existing `AuditRun`/`AuditNoiseFloor` records and is not persisted.
- **Dependencies:** 323 (complete), 140 (complete, dispatch/step surface). This is the final slice of initiative 320 — no next slice follows.
- **Suggested order (from the design, followed here):** fragment models (T1) → fragment generator (T2-T3) → delta models (T4) → delta computation (T5-T6) → config key (T7) → dispatch injection point (T8-T9) → CLI shells (T10-T12) → end-to-end verification (T13).
- **Do not re-litigate:** the injection point, the fixed (non-generated) fragment content, the manual regeneration cadence, the floor-relative (non-statistical) delta framing, or the no-new-record-type decision on the delta report. All four are settled in the design's Technical Decisions section with rejected alternatives recorded.

---

## Tasks

### T1: Fragment and delta models

- [x] **Add to `src/squadron/metrology/audit_models.py`** (alongside `BaselineCell`/`ProjectBaseline`/`BaselineReport`)
  - [x] `PreemptionFragment` (Pydantic): `project_id: ProjectId`, `audit_prompt_hash: str`, `measured_at: datetime`, `text: str`
  - [x] `FreshnessResult` (Pydantic): `is_current: bool`, `fragment_audit_prompt_hash: str | None`, `current_audit_prompt_hash: str | None`, `fragment_measured_at: datetime | None`, `note: str` (human-readable: current / stale / fragment absent)
  - [x] `DeltaCell` (Pydantic): `category: AuditCategory`, `baseline_count: int`, `new_count: int`, `delta: int`, `floor: FloorStat | None = None`, `within_floor: bool | None` (`None` when no floor measured)
  - [x] `DeltaReport` (Pydantic): `project_id: ProjectId`, `baseline_commit_sha: str`, `new_commit_sha: str`, `baseline_total: int`, `new_total: int`, `total_delta: int`, `total_within_floor: bool | None`, `cells: list[DeltaCell]`, `disclaimer: str` (fixed observational/non-causal text, Decision 4)
  - [x] Define the fixed disclaimer text once as a module constant (e.g. `DELTA_DISCLAIMER`) and reference it from `DeltaReport`'s default/construction — never restate the string at each call site
- [x] Success: all four models import cleanly; each round-trips `model_dump_json()` → `model_validate_json()`; `DeltaReport(...).disclaimer` equals the `DELTA_DISCLAIMER` constant

**Commit:** `feat(metrology): add pre-emption fragment and delta report models`

---

### T2: The fixed category-to-guidance mapping and fragment renderer

- [x] **Add `src/squadron/metrology/preemption.py`** (surface-agnostic — no Typer imports)
  - [x] `CATEGORY_GUIDANCE: dict[AuditCategory, str]` — exactly one short, fixed instruction line per each of the ten `AuditCategory` values (`architectural-decay`, `consistency-rot`, `type-contract-debt`, `test-debt`, `dependency-config-debt`, `performance-resource`, `error-handling-observability`, `security-hygiene`, `documentation-drift`, `other`). Each line names the class of issue and a short corrective instruction, following the two examples already given in the design's Decision 2 (`architectural-decay`, `type-contract-debt`) for tone and length. Do not draw text from any audit's `summary` field
  - [x] `render_fragment(baseline: ProjectBaseline) -> PreemptionFragment` — select cells from `baseline.cells` with `count > 0`; for each, emit one line pairing the category with its `CATEGORY_GUIDANCE` entry; join into the fragment body under a header line naming the baseline's `measured_at`; stamp `project_id`, `audit_prompt_hash`, `measured_at` from the input `ProjectBaseline`
  - [x] A `ProjectBaseline` with zero nonzero-count cells renders a fragment whose body states plainly that no issue classes were present at baseline — never an empty string (an empty prepend would be indistinguishable from "no fragment" at the dispatch side)
- [x] Success: a baseline with 2 nonzero cells and 8 zero cells renders exactly 2 guidance lines; the header carries the baseline's `measured_at`; a rendered fragment for every one of the ten categories exercises every `CATEGORY_GUIDANCE` entry without a `KeyError`

**Commit:** `feat(metrology): add pre-emption fragment generation`

---

### T3: Fragment file I/O — write, header read, and freshness check

- [x] **Add to `src/squadron/metrology/preemption.py`**
  - [x] `write_fragment(fragment: PreemptionFragment, *, dir: Path) -> Path` — writes the fragment to `{dir}/{project_id-sanitized}.md`, with a header (containing `audit_prompt_hash` and `measured_at`, machine-parseable) followed by `fragment.text`. Reuse an existing project-id-to-filename sanitization helper if one exists in `metrology/`; otherwise define one narrowly here (no filesystem-unsafe characters). Creates `dir` if absent
  - [x] `read_fragment_header(path: Path) -> tuple[str, datetime] | None` — reads only the header, not the full body; returns `None` if the file is absent, empty, or the header cannot be parsed (distinct from raising — this function is also used by T9's dispatch-time read, where a parse failure must degrade, not raise)
  - [x] `check_freshness(fragment_path: Path, current_baseline: ProjectBaseline) -> FreshnessResult` — calls `read_fragment_header`; if `None`, returns a `FreshnessResult` noting the fragment is absent; otherwise compares the header's `audit_prompt_hash`/`measured_at` against `current_baseline.audit_prompt_hash`/its own most-recent-run timestamp, returning `is_current=True` only on an exact hash match
- [x] Success: `write_fragment` then `read_fragment_header` round-trips the same hash/timestamp; `read_fragment_header` on a nonexistent path and on a zero-byte file both return `None` without raising; `check_freshness` against a baseline with a differing `audit_prompt_hash` returns `is_current=False` with a note identifying the mismatch

**Commit:** `feat(metrology): fragment file write, header read, and freshness check`

---

### T4: Tests for fragment generation and file I/O

- [x] **Add `tests/metrology/test_preemption.py`**
  - [x] `CATEGORY_GUIDANCE` has exactly ten entries, one per `AuditCategory` value — a parametrized test over `AuditCategory` fails loudly if a category is ever added to the enum without a matching guidance line
  - [x] `render_fragment` on a fixture `ProjectBaseline` with a mix of zero and nonzero cells includes only the nonzero categories, in a stable order
  - [x] `render_fragment` on an all-zero-cells baseline still produces non-empty fragment text (the explicit "no issue classes at baseline" case)
  - [x] `write_fragment` + `read_fragment_header` round-trip on a temp directory (use the existing store temp-dir fixture pattern from `conftest.py`)
  - [x] `read_fragment_header` returns `None`, not an exception, for: nonexistent path, empty file, file with a malformed/truncated header
  - [x] `check_freshness`: matching hash → current; differing hash → stale, with the differing values visible in the result; absent fragment → reported absent (never conflated with "stale")
- [x] Success: `uv run pytest tests/metrology/test_preemption.py` passes

**Commit:** `test(metrology): cover fragment generation, file I/O, and freshness`

---

### T5: Delta computation

- [x] **Add `src/squadron/metrology/audit_delta.py`** — pure, no I/O, no agent, independently testable on fixtures (mirrors 323's `audit_variance.py` discipline)
  - [x] `compute_delta(baseline: ProjectBaseline, new_run: AuditRun) -> DeltaReport` — per-category: pair `baseline.cells` (keyed by `AuditCategory`) against `new_run.findings` counted by category; a category present in one but not the other counts as 0 on the absent side (matching 323's per-category zero-fill precedent in `audit_variance.py`, T16)
  - [x] For each `DeltaCell`, `within_floor` is `True` when a floor exists for that category and `abs(delta) < (floor.max - floor.min)`; `False` when a floor exists and the delta meets or exceeds that spread; `None` when no floor was measured for that category (`baseline.cells[i].floor is None`) — never silently treated as significant
  - [x] `total_delta` and `total_within_floor` apply the identical floor-spread rule against `baseline.total_floor`
  - [x] `DeltaReport.disclaimer` is always set to the `DELTA_DISCLAIMER` constant from T1 — every report carries it unconditionally, never gated on any condition
- [x] Success: a baseline/new-run pair with a known per-category floor and a computed delta smaller than the floor's spread reports `within_floor=True`; a pair with no floor for one category reports `within_floor=None` for that cell only; the disclaimer is present on every returned `DeltaReport`

**Commit:** `feat(metrology): compute floor-relative audit delta`

---

### T6: Delta computation tests

- [x] **Add `tests/metrology/test_audit_delta.py`**
  - [x] Known-value delta: hand-computed per-category and total deltas against a fixed baseline/new-run fixture pair
  - [x] **Within-floor case:** delta smaller than `floor.max - floor.min` → `within_floor=True`
  - [x] **Outside-floor case:** delta at or beyond the floor spread → `within_floor=False`
  - [x] **No-floor case:** a category (and separately, the total) with no measured floor → `within_floor=None`, never `True` or `False`
  - [x] **Zero-fill correctness:** a category present in the baseline but absent from the new run's findings (and vice versa) computes a correct nonzero delta rather than being skipped
  - [x] Disclaimer text is present and matches `DELTA_DISCLAIMER` on every constructed `DeltaReport` in the test set
- [x] Success: `uv run pytest tests/metrology/test_audit_delta.py` passes

**Commit:** `test(metrology): cover delta computation, floor comparison, and zero-fill`

---

### T7: Config key

- [x] **Edit `src/squadron/config/keys.py`**, adding to `CONFIG_KEYS`
  - [x] `metrology.preemption_fragment_dir` — `str`, default `~/.config/squadron/metrology/preemption`, described as the directory `sq metrology preempt generate` writes fragment files into
  - [x] Follow the existing `metrology.audit_*` key entries immediately above/below for format and description style
- [x] Success: `sq config get metrology.preemption_fragment_dir` prints the default path; `sq config set metrology.preemption_fragment_dir /tmp/x` succeeds and reads back

**Commit:** `feat(config): add pre-emption fragment directory config key`

---

### T8: Dispatch injection point — `_resolve_prompt` prepend and failure handling

- [x] **Edit `src/squadron/pipeline/actions/dispatch.py`**
  - [x] Add a new method (e.g. `_apply_pre_emption_fragment`), called from the tail of `_resolve_prompt` **after** `self._apply_override(context, prompt)` returns — so the fragment wraps outside the checkpoint override, per Decision 1's ordering
  - [x] Reads `context.params.get("pre_emption_fragment")` — a path string. If absent or empty, no-op, returning the prompt unchanged (identical to `_apply_override`'s own no-op-when-absent posture)
  - [x] If present, attempts the read via `preemption.read_fragment_header`-adjacent full-body read (add a `read_fragment_body(path: Path) -> str | None` to `preemption.py` in this task if T3 did not already cover a full-text read — check T3's output before adding a duplicate). Returns `None` on: path does not exist, `OSError` on read, or empty/malformed content — never raises out of this method
  - [x] On a successful read, prepend using the same delimited-block shape as `_apply_override`: `"--- Pre-emption: known issue classes for this project ---\n{fragment text}\n--- End pre-emption ---\n\n"` ahead of the (already override-prepended) prompt
  - [x] On any of the three failure modes (missing / unreadable / malformed), skip the prepend — return the prompt unchanged — and log at `WARNING`, naming the configured path and which of the three modes occurred (distinguish empty from malformed header per the design's failure-mode table)
  - [x] Add `_logger = logging.getLogger(__name__)` to `dispatch.py` if not already present, following the `store.py` convention
- [x] Success: a valid fragment path prepends the delimited block ahead of the prompt (and ahead of any override block); a missing/unreadable/empty/malformed path each produce the unmodified prompt plus one `WARNING` distinguishing the mode; no exception ever escapes `_resolve_prompt` due to a fragment problem

**Commit:** `feat(pipeline): prepend pre-emption fragment at dispatch, degrade-on-failure`

---

### T9: Thread `pre_emption_fragment` through `DispatchStepType.expand()` and `PhaseStepType.expand()`

- [x] **Edit `src/squadron/pipeline/steps/dispatch.py`**
  - [x] In `expand()`, add `if "pre_emption_fragment" in cfg: action_config["pre_emption_fragment"] = cfg["pre_emption_fragment"]`, matching the existing `prompt`/`model` conditional-forwarding lines exactly
  - [x] In `validate()`, add the same string-type check pattern used for `prompt`/`model` (non-`None` value must be a `str`)
- [x] **Edit `src/squadron/pipeline/steps/phase.py`**
  - [x] In `expand()`, add `pre_emption_fragment = cfg.get("pre_emption_fragment")` and thread it into the existing `("dispatch", {"model": model, "slice": slice_ref})` tuple's dict, conditionally (only when present in `cfg`) — do not unconditionally add the key, since the dict is asserted exactly by existing tests
  - [x] Add the matching `validate()` string-type check if `PhaseStepType.validate()` validates `model`/other optional keys the same way (match whatever pattern already exists there for optional string fields)
- [x] Success: `expand()` for both step types, when `pre_emption_fragment` is absent from `cfg`, produces output byte-identical to before this task (verified by T10 re-running the existing test files unmodified); when present, `action_config["pre_emption_fragment"]` carries the value through

**Commit:** `feat(pipeline): thread pre_emption_fragment through dispatch and phase step expand()`

---

### T10: Tests for the injection point and step threading

- [x] **Add `tests/pipeline/actions/test_dispatch_pre_emption.py`** (or extend the existing dispatch action test file if one already covers `_apply_override` — check for `test_dispatch_action.py` or similar before creating a new file)
  - [x] A valid fragment file, referenced via `pre_emption_fragment`, is prepended ahead of both the base prompt and an `override_instructions` block (asserting the exact ordering from Decision 1)
  - [x] Absent `pre_emption_fragment` param → prompt unchanged from today's behavior
  - [x] Missing file path → prompt unchanged, one `WARNING` logged naming the path (use `caplog`)
  - [x] Unreadable file (permissions) → prompt unchanged, `WARNING` logged
  - [x] Empty file and malformed-header file → prompt unchanged, `WARNING` logged, and the two cases are distinguishable in the log message
- [x] **Run the existing `tests/pipeline/steps/test_dispatch_step.py` and `tests/pipeline/steps/test_phase.py` unmodified** and confirm every exact-dict-equality `expand()` assertion still passes — this is a success criterion from the design, not just a regression check
- [x] **Extend `test_dispatch_step.py` and `test_phase.py`** with one new case each: `pre_emption_fragment` present in step config → present in the expanded action config
- [x] Success: `uv run pytest tests/pipeline/actions/test_dispatch_pre_emption.py tests/pipeline/steps/test_dispatch_step.py tests/pipeline/steps/test_phase.py` passes, including every pre-existing assertion unmodified

**Commit:** `test(pipeline): cover pre-emption fragment injection and step threading`

---

### T11: CLI — `sq metrology preempt generate`

- [x] **Edit `src/squadron/cli/commands/metrology.py`**
  - [x] Add a nested `preempt_app` via `metrology_app.add_typer(...)`, mirroring the existing `audit_app`/`report_app` pattern
  - [x] `sq metrology preempt generate <project-path>` — `--json`, `--cwd`. Calls `baseline_report(store, project_filter=...)` for the resolved project, takes the matching `ProjectBaseline`, renders via `render_fragment`, writes via `write_fragment` to `metrology.preemption_fragment_dir` (read via the existing `get_typed_config`/`_read_*_config` helper pattern). Overwrites any existing fragment for the project (per the design's stated behavior)
  - [x] `sq metrology preempt generate <project-path> --check` — read-only. Loads the current baseline, calls `check_freshness` against the existing fragment file at the expected path, and reports current / stale / absent. Exit 0 when current, exit 1 when stale or absent (scriptable for CI, per the design's Interface Specification)
  - [x] No baseline for the project → the existing empty-result convention: dim message, exit 0 for plain `generate` is not applicable here (there is nothing to write) — treat a missing baseline as an error condition instead, since `preempt generate` cannot produce a fragment from nothing; follow the `MetrologyTargetError`-style `[red]Error: ...[/red]` exit 1 convention
  - [x] Error handling per convention: `MetrologyStoreError` → `[red]Store error: ...[/red]` exit 1
- [x] Success: `sq metrology preempt generate --help` and `sq metrology preempt generate <path> --check --help` both appear under `sq metrology --help`; running `generate` against a project with a stored baseline writes a fragment file and prints its path; `--check` against a freshly generated fragment exits 0

**Commit:** `feat(cli): add sq metrology preempt generate with --check`

---

### T12: CLI — `sq metrology audit delta`, and CLI tests

- [x] **Edit `src/squadron/cli/commands/metrology.py`**
  - [x] Add `sq metrology audit delta <project-path>` to the existing `audit_app` — `--profile`, `--json`, `--cwd`
  - [x] Loads the stored `ProjectBaseline` for the resolved project, runs one new audit via 323's `run_audit` (reusing its existing pre-flight checks, timeout, and failure handling unmodified — no new failure-handling logic here), then calls `compute_delta`
  - [x] No stored baseline for the project → `[red]Error: no baseline found for this project — run 'sq metrology preempt generate' or 'sq metrology audit run' first[/red]`, exit 1 (there is nothing to diff against)
  - [x] `run_audit` failure (any of 323's existing failure modes) → propagate the same error presentation 323's `audit run` command already uses; do not persist or report a partial delta
  - [x] Render output showing the total delta, per-category deltas, floor-relative interpretation (within-floor / outside-floor / no-floor-measured per cell), and the fixed disclaimer text, matching the design's Interface Specification example format
- [x] **Add `tests/metrology/test_preemption_cli.py`** and **extend `tests/metrology/test_audit_cli.py`** (matching the existing CLI-test pattern using a stubbed harness)
  - [x] `preempt generate` writes a fragment and prints its path; `--json` output parses as `PreemptionFragment`
  - [x] `preempt generate --check`: current → exit 0; stale → exit 1 with the mismatch named; absent fragment → exit 1
  - [x] `preempt generate` against a project with no stored baseline → exit 1 with a clear message
  - [x] `audit delta` (stubbed `run_audit`) against a project with a baseline and floor → renders per-category and total deltas with floor interpretation and the disclaimer text present
  - [x] `audit delta` against a project with a baseline but no floor → cells report "no floor — delta not interpretable" rather than treating the delta as significant
  - [x] `audit delta` against a project with no baseline → exit 1
- [x] Success: `uv run pytest tests/metrology/test_preemption_cli.py tests/metrology/test_audit_cli.py` passes

**Commit:** `feat(cli): add sq metrology audit delta with tests`

---

### T13: End-to-end verification

- [x] **Full local verification first (zero token cost beyond one delta run)**
  - [x] `uv run ruff format` on all changed files, then `uv run ruff check`, then `uv run pyright` — all clean
  - [x] `uv run pytest -q` — full suite green, including every pre-existing `expand()` exact-equality assertion unmodified (T10's stated success criterion)
- [x] **Generate a fragment from an existing baseline** — run `sq metrology preempt generate` against a project with an already-measured 323 baseline (e.g. `migratory-viewer`); confirm the written fragment names the expected nonzero categories and carries a header matching the baseline's `audit_prompt_hash`/`measured_at`
- [x] **Freshness check, current** — `sq metrology preempt generate --check` on the just-generated fragment; confirm exit 0
- [x] **Freshness check, stale** — re-run a 323 audit against the same project to produce a new run without regenerating the fragment; confirm `--check` reports stale (exit 1) naming the mismatch
  - Verified by test + documented gap: this step could not be run end-to-end in Claude Code (audit harness spawns CLI, refuses nesting); covered by fixture tests and documented in design's Verification Walkthrough under "Not verified end-to-end"
- [x] **Fragment reaches dispatch, opted-in pipelines only** — add `pre_emption_fragment: <path>` to a test pipeline's dispatch/design step; run it and confirm (via `--json`/debug log) the dispatched prompt is prefixed with the fragment block. Run an existing unmodified pipeline and confirm its prompt is byte-identical to a pre-324 run
- [x] **Broken fragment degrades to a no-op** — point `pre_emption_fragment` at a nonexistent path; confirm dispatch completes with the unmodified prompt and a `WARNING` naming the missing path. Repeat with an empty file
- [x] **Delta report, below floor** — `sq metrology audit delta` against a project with a measured floor; confirm the report states the delta is within the floor (or outside it, whichever the real run produces) with the disclaimer present
  - Verified by test + documented gap: this step could not be run end-to-end in Claude Code; covered by fixture and stubbed-harness tests and documented in design's Verification Walkthrough under "Not verified end-to-end"
- [x] **Delta report, no floor measured** — run delta against a project with a baseline but no variance series; confirm "no floor — delta not interpretable" is reported rather than treating any change as significant
  - Verified by test + documented gap: this step could not be run end-to-end in Claude Code; covered by fixture and stubbed-harness tests and documented in design's Verification Walkthrough under "Not verified end-to-end"
- [x] **Rewrite the slice design's Verification Walkthrough section** with the actual commands run and observed output, replacing the "Draft — to be executed and refined at Phase 6 completion" marker, following 323's T22 precedent for how execution notes diverge from the Phase 5 draft
- [x] Success: the design's Success Criteria section is satisfied end-to-end; the Verification Walkthrough is updated with real output; slice 324 status is updated to `complete` in its frontmatter, and the slice plan (`320-slices.judge-calibration-quality-metrology.md`) marks 324 (and thus the initiative's fifth and final anticipated slice) complete

**Commit:** `test(metrology): end-to-end pre-emption and delta verification`

---

## Notes

- **Do not re-litigate the injection point.** The fragment prepends inside `DispatchAction._resolve_prompt`, strictly after `_apply_override`, downstream of everything `cf_op.py` produces. No task in this file touches `cf_op.py` or any context-forge code path.
- **`expand()` stays pure.** Neither `DispatchStepType.expand()` nor `PhaseStepType.expand()` gains file I/O. The only new I/O is inside `DispatchAction`, which already does I/O via `one_shot_dispatch`.
- **A fragment problem is never a dispatch failure.** All three failure modes (missing, unreadable, malformed) in T8 degrade to a skipped prepend plus a `WARNING` — this is asymmetric with 323's audit-run failure handling by design (a missing fragment has no measurement to poison), not an oversight.
- **Issue #40 (empty system prompt on one-shot dispatch) is explicitly out of scope** for this slice and is not touched by any task above.
- **This is the initiative's final slice.** T13's completion, once its checklist and the slice's own Success Criteria are verified, closes out initiative 320 (320-arch/320-slices/320-reference) entirely — no further slice follows 324.

## Implementation Notes

The following deviations from the original task text were approved during implementation and should be noted for future reference:

1. **ProjectBaseline gained a required `measured_at: datetime` field** — Added to `audit_models.py` and populated from `run.measured_at` at the single construction site in `audit_report.py`. T2/T3 required the fragment to stamp the baseline's `measured_at`, but `ProjectBaseline` carried no timestamp — only `run_id`. The alternative (re-fetching the `AuditRun` by `run_id`) was redundant I/O and rejected in favor of the explicit `measured_at` field.

2. **`write_fragment` parameter named `directory=` rather than `dir=`** — The task text specified `dir=`, but `dir` shadows the Python builtin. The implementation uses `directory=` to avoid this shadowing.

3. **`read_fragment_body(path: Path) -> str | None` added in T3** — Not deferred to T8 as the task allowed. This function was implemented alongside `read_fragment_header` to provide a clean separation of concerns. T8 reused this existing function rather than implementing its own full-body read.

4. **T7-T9 landed as a single commit (5f72549) rather than three** — A pre-commit hook stages all modified files, causing the configuration key (T7), dispatch injection (T8), and step threading (T9) to be committed together. The commit message covers all three tasks while preserving their semantic separation in the task checklist.

5. **The `sq metrology preempt generate` / `audit delta` commands live in a new module `src/squadron/cli/commands/metrology_preemption.py` rather than in `metrology.py`** — The existing `metrology.py` was already ~1000 lines; the new commands mount onto the existing metrology/audit Typer apps so the command surface is unchanged.

6. **A multi-instrument guard was added to `_load_baseline`** — A project whose baselines span more than one `audit_prompt_hash` is refused rather than silently picking one. A project audited at several commits under a single instrument is not refused — the most recent measurement wins. This fired on real data (migratory-viewer) during T13.

7. **`_fragment_dir` reads the config key via plain `get_config` plus an explicit str check, not `get_typed_config`** — The latter validates numerics only. This follows the string-key precedent in `metrology/audit.py`.

8. **Two pre-existing test failures in `tests/review/test_content_injection.py` (test_large_file_is_truncated, test_large_diff_is_truncated) are unrelated to 324** — Confirmed by stashing all 324 work and reproducing them identically.
