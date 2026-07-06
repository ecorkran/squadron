---
docType: tasks
slice: design-phase-judge-templates
project: squadron
lld: ../slices/302-slice.design-phase-judge-templates.md
dependencies:
  - 301 judge-enforcement-layer (complete) — ReviewTemplate.judge/.is_judge, enforce_judge(), resolve_thresholds(), Provenance
projectState: "Slice 301 complete. ReviewTemplate.judge/.is_judge, enforce_judge(), resolve_thresholds(), and Provenance all exist and are exercised only by a synthetic test template — no real judge template exists yet. TEMPLATE_INPUTS in src/squadron/review/template_inputs.py has exactly four entries (slice, tasks, arch, code), each keyed by an existing standard template name. sq review's CLI subcommands (slice/arch/tasks/code) are each pinned to their own template name with no generic template-name argument; judge templates are reachable only via the pipeline review step (arbitrary template: string) or direct API use — this is a corrected finding from Phase 5, not part of the original LLD."
dateCreated: 20260705
dateUpdated: 20260705
status: complete
---

## Context Summary

- **Working on:** authoring the first two real judge templates —
  `judge.tasks-vs-slice` and `judge.slice-vs-arch` — judge-flavored variants of
  the existing `tasks`/`slice` review templates that emit **score + rationale +
  findings** instead of a verdict, exercising slice 301's enforcement contract
  for the first time against real prompts and real ground truth.
- **Current state:** slice 301's enforcement layer (`judge.py`) is complete and
  tested against a synthetic minimal template only. `TEMPLATE_INPUTS` has four
  entries, none for a judge template name. No judge template YAML exists.
- **Key assumptions / discipline (from the LLD):**
  - A judge template is identified **only** by the presence of a `judge:` YAML
    block (`is_judge` property, slice 301) — never by the `judge.` name prefix.
    The prefix is for human readability in pipeline YAML / `sq review list`
    output only.
  - Each judge template reuses its standard counterpart's evaluation-criteria
    list verbatim — only the output contract changes (score+rationale+findings
    instead of verdict+findings). Do not re-derive or drift the criteria list.
  - The judge system prompt must explicitly forbid emitting a `## Summary` /
    verdict line. `enforce_judge()` already ignores `result.verdict`
    unconditionally (301), but a rogue verdict in `raw_output` is confusing to
    a human reading the persisted review file, so the prompt-level
    "don't emit one" instruction is this slice's own belt-and-suspenders.
  - The score-with-rationale shape reuses the existing `criteria:` block (slice
    300 parser) as its structured carrier — no new parser target, no new field.
  - Default thresholds are **not identical** between the two templates:
    `judge.tasks-vs-slice` (stronger ground truth) gets `pass_floor=78`,
    `concerns_floor=55`; `judge.slice-vs-arch` (more interpretive ground truth)
    gets `pass_floor=82`, `concerns_floor=60` — both overridable per step via
    the existing `resolve_thresholds` mechanism, unchanged.
  - `TEMPLATE_INPUTS` needs two new explicit dict entries (reusing the existing
    `_design_file`/`_arch_file`/`_tasks_input` source functions unchanged) —
    never a judge→standard name-stripping fallback, which would reintroduce
    naming-convention dispatch.
  - **Corrected during Phase 5:** the LLD's Verification Walkthrough originally
    assumed a `sq review <judge-template>` CLI invocation exists. It does not —
    `sq review`'s four subcommands are each pinned to one template name.
    Verification for this slice uses `run_review_with_profile()` directly and
    the pipeline `review` step, not a new CLI subcommand (out of scope here).
  - No engine, parser, or action code changes beyond the two new YAML files and
    two new `TEMPLATE_INPUTS` dict entries.
- **Dependencies:** slice 301, complete. Nothing else consumed.
- **What this slice delivers:** two working judge templates
  (`judge.tasks-vs-slice`, `judge.slice-vs-arch`) plus their `TEMPLATE_INPUTS`
  registry entries — the first real exercise of slice 301's enforcement
  contract, unblocking slice 303 (judge-gated cycle conventions).
- **Next slice:** 303 (Judge-Gated Cycle Conventions) — documents how
  `each`/`loop`/`commit` compose with a judge to express review→fix→re-review
  as an unattended pipeline.

---

## Tasks

### T1: Author `judge-tasks-vs-slice.yaml`

- [x] **Create `src/squadron/data/templates/judge-tasks-vs-slice.yaml`**, adapted
  from `src/squadron/data/templates/tasks.yaml`
  - [x] `name: judge.tasks-vs-slice`
  - [x] Reuse `tasks.yaml`'s evaluation-criteria list verbatim (gaps, scope
    creep, sequencing, test-with pattern, NFR/load-test checks, etc.)
  - [x] Replace the `## Summary` / verdict output-contract instructions with:
    require a `## Rationale` section (short justification per criterion before
    its numeric value), a top-level `score: <0-100>` line, a `criteria:` block
    (same shape the parser already extracts per slice 300), and existing
    `## Findings` blocks — and an explicit instruction **not** to emit a
    `## Summary` or PASS/CONCERNS/FAIL line
  - [x] Add a `judge:` block: `pass_floor: 78`, `concerns_floor: 55`
  - [x] Keep `allowed_tools`, `permission_mode`, `model`, `setting_sources`,
    and the `inputs:`/`prompt_template:` shape structurally the same as
    `tasks.yaml` (same required inputs: `input`, `against`; same optional
    `cwd`)
- [x] Success: file is valid YAML; `uv run python -c "from squadron.review.templates import load_template; from pathlib import Path; t = load_template(Path('src/squadron/data/templates/judge-tasks-vs-slice.yaml')); assert t.is_judge and t.judge == {'pass_floor': 78, 'concerns_floor': 55}"` passes with no error

**Commit:** `feat: add judge.tasks-vs-slice template`

---

### T2: Tests for `judge.tasks-vs-slice` template loading

- [x] **Add tests in `tests/review/test_templates.py`** (extend existing)
  - [x] Loading `judge-tasks-vs-slice.yaml` via `load_template()` produces
    `is_judge is True`
  - [x] `.judge == {"pass_floor": 78, "concerns_floor": 55}` (values as parsed,
    coerced or not — assert against the raw YAML-parsed types)
  - [x] Required inputs are `input` and `against` (same as `tasks.yaml`)
  - [x] `load_all_templates()` (built-in discovery) includes
    `judge.tasks-vs-slice` in `list_templates()`
- [x] Success: `uv run pytest tests/review/test_templates.py` passes

**Commit:** `test: cover judge.tasks-vs-slice template loading`

---

### T3: Author `judge-slice-vs-arch.yaml`

- [x] **Create `src/squadron/data/templates/judge-slice-vs-arch.yaml`**, adapted
  from `src/squadron/data/templates/slice.yaml`
  - [x] `name: judge.slice-vs-arch`
  - [x] Reuse `slice.yaml`'s evaluation-criteria list verbatim (architectural
    alignment, boundary violations, scope creep, dependency direction,
    integration points, failure-mode enumeration, NFR restatement, etc.)
  - [x] Same output-contract replacement as T1: `## Rationale` +
    `score:` + `criteria:` + `## Findings`, no `## Summary`/verdict line
  - [x] Add a `judge:` block: `pass_floor: 82`, `concerns_floor: 60`
  - [x] Keep `allowed_tools`, `permission_mode`, `model`, `setting_sources`,
    and the `inputs:`/`prompt_template:` shape structurally the same as
    `slice.yaml` (required inputs: `input`, `against`; optional `cwd`)
- [x] Success: `uv run python -c "from squadron.review.templates import load_template; from pathlib import Path; t = load_template(Path('src/squadron/data/templates/judge-slice-vs-arch.yaml')); assert t.is_judge and t.judge == {'pass_floor': 82, 'concerns_floor': 60}"` passes with no error

**Commit:** `feat: add judge.slice-vs-arch template`

---

### T4: Tests for `judge.slice-vs-arch` template loading

- [x] **Add tests in `tests/review/test_templates.py`** (extend existing)
  - [x] Loading `judge-slice-vs-arch.yaml` via `load_template()` produces
    `is_judge is True`
  - [x] `.judge == {"pass_floor": 82, "concerns_floor": 60}`
  - [x] Required inputs are `input` and `against` (same as `slice.yaml`)
  - [x] `load_all_templates()` includes `judge.slice-vs-arch` in
    `list_templates()`
  - [x] Both judge templates' default thresholds differ from each other
    (`pass_floor` 82 vs. 78) — a direct regression guard for the
    ground-truth-strength differentiation the LLD requires
- [x] Success: `uv run pytest tests/review/test_templates.py` passes

**Commit:** `test: cover judge.slice-vs-arch template loading`

---

### T5: Add `TEMPLATE_INPUTS` entries for both judge templates

- [x] **Update `TEMPLATE_INPUTS` in `src/squadron/review/template_inputs.py`**
  - [x] Add `"judge.tasks-vs-slice"` entry, reusing the exact same
    `TemplateInputSpec` list as the existing `"tasks"` entry
    (`_tasks_input` → `input`, `_design_file` → `against`)
  - [x] Add `"judge.slice-vs-arch"` entry, reusing the exact same
    `TemplateInputSpec` list as the existing `"slice"` entry
    (`_design_file` → `input`, `_arch_file` → `against`)
  - [x] Do not add a name-stripping fallback (`judge.X` → `X`) — two explicit
    entries only, per the LLD's rejected-alternative rationale
- [x] Success: `resolve_template_inputs("judge.tasks-vs-slice", info, cwd, inputs)`
  and `resolve_template_inputs("judge.slice-vs-arch", info, cwd, inputs)`
  populate `input`/`against` identically to their standard counterparts given
  the same `SliceInfo`; `uv run pyright` passes

**Commit:** `feat: add TEMPLATE_INPUTS entries for judge templates`

---

### T6: Tests for judge `TEMPLATE_INPUTS` resolution

- [x] **Update `tests/review/test_template_inputs.py`** (extend existing)
  - [x] Update `test_registry_has_all_templates` to assert the full expected
    keyset now includes `judge.tasks-vs-slice` and `judge.slice-vs-arch`
    alongside the existing four (do not just add a separate weaker assertion —
    replace the exact-set check so it stays a true regression guard)
  - [x] `resolve_template_inputs("judge.tasks-vs-slice", ...)` populates
    `input`/`against` identically to the existing `test_tasks_template_*` cases
  - [x] `resolve_template_inputs("judge.slice-vs-arch", ...)` populates
    `input`/`against` identically to the existing `test_slice_template_*` case
  - [x] `judge.tasks-vs-slice` with empty `task_files` → no `input` key set
    (mirrors `test_tasks_template_no_input_when_task_files_empty`)
- [x] Success: `uv run pytest tests/review/test_template_inputs.py` passes

**Commit:** `test: cover TEMPLATE_INPUTS resolution for judge templates`

---

### T7: Test — rogue model-emitted verdict is discarded for a judge result

- [x] **Add a test in `tests/pipeline/actions/test_review_action.py`** (extend
  existing judge-enforcement tests from slice 301)
  - [x] Using either new judge template (mock or the real loaded template),
    mock `run_review_with_profile` to return a `ReviewResult` with a
    **non-`UNKNOWN` parsed `verdict`** (e.g. `Verdict.FAIL`) alongside a valid,
    in-range `score` that would derive to `PASS` under the template's
    thresholds
  - [x] Assert the resulting `ActionResult.verdict` is the **threshold-derived**
    value (`"PASS"`), not the parsed `"FAIL"` — proving the rogue verdict never
    surfaces, consistent with `enforce_judge()` never reading `result.verdict`
  - [x] This is the LLD's Risk Assessment row "Model emits a verdict summary
    despite the prompt forbidding it" — confirms the existing 301 mechanism
    covers this slice's new templates with no new code required
- [x] Success: `uv run pytest tests/pipeline/actions/test_review_action.py` passes;
  existing tests in this file remain unchanged and passing

**Commit:** `test: cover rogue verdict discarded for judge templates`

---

### T8: Test — `TEMPLATE_INPUTS` resolution failure yields `UNKNOWN`, not a silent skip

- [x] **Add a test in `tests/pipeline/actions/test_review_action.py`** (extend
  existing)
  - [x] Construct a `SliceInfo` missing a field one of the new judge template's
    `TEMPLATE_INPUTS` entries needs (e.g. `arch_file` empty/falsy for
    `judge.slice-vs-arch`, or empty `task_files` for `judge.tasks-vs-slice`
    with no explicit `input` already provided)
  - [x] Drive `ReviewAction` through its slice-based auto-resolution path (as
    `_resolve_slice_inputs` does) with this incomplete `SliceInfo` and confirm
    the missing-required-input `KeyError` path fires
  - [x] Assert the resulting `ActionResult` has `success=False`,
    `verdict="UNKNOWN"`, `provenance=Provenance.JUDGE` — proving the failure
    surfaces as a judge-aware non-pass via `execute()`'s existing exception
    handler (slice 301), not a silent skip
  - [x] This is the LLD's Risk Assessment row "`TEMPLATE_INPUTS` resolution
    fails" — confirms the existing 301 exception-handling mechanism covers
    this slice's new registry lookups with no new code required
- [x] Success: `uv run pytest tests/pipeline/actions/test_review_action.py` passes

**Commit:** `test: cover TEMPLATE_INPUTS resolution failure yields UNKNOWN`

---

### T9: Live-provider verification run — `judge.tasks-vs-slice`

- [x] **Run `judge.tasks-vs-slice` against a real in-repo artifact pair** using
  `run_review_with_profile()` directly (see the LLD's corrected Verification
  Walkthrough step 3) — a real task-breakdown file and its parent slice design
  (e.g. this slice's own `302-tasks...`/`302-slice...` pair, once available, or
  any other completed slice's task/design pair)
  - [x] Confirm the persisted/printed output contains a non-`None` `score` and
    a `criteria` map
  - [x] Confirm `raw_output` contains **no** `## Summary` / verdict line — the
    prompt's no-verdict instruction is actually followed by the model
  - [x] Confirm findings are present and use the expected `### [SEVERITY]
    Title` / `location:` shape
  - [x] If the model does emit a stray verdict line or the score/criteria shape
    deviates, treat this as prompt-tuning feedback and revise
    `judge-tasks-vs-slice.yaml`'s prompt (not the parser or enforcement code)
    before proceeding
- [x] Success: at least one real run produces a valid score + criteria +
  findings with no emitted verdict summary; any prompt revisions are committed
  before moving on

**Commit:** `docs: verify judge.tasks-vs-slice against real artifact pair` (or
a `feat:` commit if the prompt required revision)

---

### T10: Live-provider verification run — `judge.slice-vs-arch`

- [x] **Run `judge.slice-vs-arch` against a real in-repo artifact pair** — this
  slice's own design document (`302-slice.design-phase-judge-templates.md`)
  against its architecture (`300-arch.eval-actions-llm-as-judge-scoring.md`),
  per the LLD's Verification Walkthrough step 3
  - [x] Confirm the same three properties as T9 (non-`None` score + criteria,
    no verdict summary, correctly shaped findings)
  - [x] Sanity-check the score qualitatively against the two committed reviews
    already on file for this slice design
    (`302-review.slice.design-phase-judge-templates.md`) — the judge's score
    should not be wildly inconsistent with the human/model review's verdict
    (e.g. a review verdict of `CONCERNS` should not pair with a judge score
    that clears `pass_floor=82` comfortably)
  - [x] If the model emits a stray verdict or the shape deviates, revise
    `judge-slice-vs-arch.yaml`'s prompt before proceeding
- [x] Success: at least one real run produces a valid score + criteria +
  findings with no emitted verdict summary, and the score is not grossly
  inconsistent with the existing human-facing review of the same artifact

**Commit:** `docs: verify judge.slice-vs-arch against real artifact pair` (or
a `feat:` commit if the prompt required revision)

---

### T11: Full validation pass

- [x] **Run the full suite and static analysis**
  - [x] `uv run pytest` — entire suite green (existing tests unchanged + all
    new tests from T2/T4/T6/T7/T8 pass)
  - [x] `uv run pyright` — 0 errors
  - [x] `uv run ruff check && uv run ruff format --check` — clean
- [x] **Run the LLD's Verification Walkthrough commands 1 and 2** (template
  loading, `TEMPLATE_INPUTS` resolution) from
  `302-slice.design-phase-judge-templates.md` and confirm the printed `PASS:`
  lines
- [x] **Confirm `sq review list` shows both new templates** alongside the
  existing four (Integration Requirements)
- [x] **Confirm no naming-convention dispatch leaked in:** grep the diff for
  any `template_name.startswith("judge.")`-style check in non-test code —
  `is_judge` (and the `TEMPLATE_INPUTS` dict key lookup) must be the only
  signals used
- [x] Success: full suite + static analysis clean; walkthrough commands 1–2
  print their `PASS:` lines; `sq review list` shows all 6 templates; no
  naming-convention dispatch found

**Commit:** `chore: validate design-phase judge templates slice`

---

## Coverage Check (against LLD)

| LLD change | Task(s) |
|------------|---------|
| `judge-tasks-vs-slice.yaml` — template + `judge:` block (78/55) | T1, T2 |
| `judge-slice-vs-arch.yaml` — template + `judge:` block (82/60) | T3, T4 |
| `TEMPLATE_INPUTS` entries for both judge template names | T5, T6 |
| Failure mode: rogue model-emitted verdict discarded | T7 |
| Failure mode: `TEMPLATE_INPUTS` resolution failure → `UNKNOWN` | T8 |
| Risk mitigation: live-provider verification per template | T9, T10 |
| Corrected walkthrough (no CLI subcommand claim) verified directly | T9, T10, T11 |
| Backward-compat + static-analysis gate | T2, T4, T6, T7, T8, T11 |
