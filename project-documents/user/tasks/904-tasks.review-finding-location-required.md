---
docType: tasks
slice: review-finding-location-required
project: squadron
lld: user/slices/904-slice.review-finding-location-required.md
dependencies: []
projectState: 902 (verbosity passthrough + bootstrap_step_types) complete on main. Branch 904-review-finding-location-required.
dateCreated: 20260427
dateUpdated: 20260427
status: complete
---

## Context Summary

- Fixes [issue #10](https://github.com/ecorkran/squadron/issues/10): `location:` field on review findings is inconsistent and often missing on PASS findings.
- Coordinated changes:
  1. Prompt updates in all four review templates — require `location:` on every finding, with `unverified` as the explicit "I don't know" token.
  2. Soft-fail parser validator: missing `location:` becomes `unverified` with WARNING.
  3. Diff-membership WARNING for code-review findings whose location cites a path.
  4. Path-existence WARNING for all template types (catches hallucinated filenames in arch/slice/tasks reviews where there is no diff to check against).
- Open questions resolved: soft-fail (not hard); WARNING-only path validation; standalone slice.
- Hallucination mitigation: `unverified` is a self-documenting token (humans see it in the review file) AND the parser logs a count; path-existence check catches made-up filenames cheaply.
- `task_ref:` field deferred to future slice (likely under 189 ensemble review).
- Files touched: 4 template YAMLs, `src/squadron/review/parsers.py`, possibly `src/squadron/review/models.py`, tests under `tests/review/`.
- Effort: 2.5/5. Risk: Low–Medium.

---

## Tasks

- [x] **T1. Survey current template prompts**
  - Files: `src/squadron/data/templates/{code,slice,arch,tasks}.yaml`
  - For each template, locate the section that describes the finding format (severity, title, body).
  - Note the existing instructions about citing files/lines (if any).
  - Success: a one-paragraph note in the task file describing the current state of each template's location guidance.

- [x] **T2. Update `code.yaml` finding-format prompt**
  - Add an explicit `location:` requirement to the finding format spec.
  - Spell out the precedence ladder: `path:line` → `path:start-end` → `path#symbol` → `path` → `unverified`.
  - **`unverified` is the explicit "I don't know" token.** Instruct the model to use `unverified` rather than guess a path it isn't certain of. State that hallucinated locations are worse than `unverified`.
  - State that PASS findings get the same treatment.
  - Add multi-file guidance: cite primary location in `location:`, mention others in prose.
  - Success: a synthetic test review against the updated prompt produces `location:` on every finding (manual eyeball — full integration in T11).

- [x] **T3. Update `slice.yaml` finding-format prompt**
  - Same structure as T2 but the preferred form is slice-doc `path:line` → `path#section-heading` → `path` → `unverified`.
  - Slice reviews target the slice *design document*, not the implementation; do not instruct the model to cite code paths.
  - Same `unverified` guidance: do not guess a slice-doc path you are not certain of.

- [x] **T4. Update `arch.yaml` finding-format prompt**
  - Same structure as T2 but the preferred form is `path` (whole-doc) or `path#section-heading` → `unverified`.
  - Explicitly note that `unverified` with prose justification is acceptable for arch reviews on cross-cutting findings (e.g. "missing coverage").

- [x] **T5. Update `tasks.yaml` finding-format prompt**
  - Same structure as T2 but the preferred form is code `path:line` (location of the issue, not the task ID) → `unverified`.
  - Note that `task_ref:` is **not** currently part of the finding schema (future enhancement).

- [x] **T6. Add soft-fail location validator to parser**
  - File: `src/squadron/review/parsers.py`
  - In `_extract_findings`, after the existing location extraction (`_LOCATION_RE` match + `file_ref` fallback), if the finding still has no location, set `location = "unverified"` and log WARNING via the module logger naming the finding's `id` (or title) and the verdict.
  - Also normalize the case where the model wrote `location: -` or `location: global` or empty — treat all of these as `unverified` for downstream uniformity.
  - The existing `file_ref` fallback at line 128-130 already handles part of this; the change is to explicitly normalize, tag, and warn when **all** location sources are absent rather than leaving `location` as `None`.
  - Success: `pytest tests/review/test_parsers.py` — existing tests pass; new soft-fail test (T7) passes.

- [x] **T7. Add parser tests for soft-fail and missing-location warning**
  - File: `tests/review/test_parsers.py` (or create if absent)
  - Test 1: a review body with one finding lacking `location:` produces `ReviewFinding.location == "unverified"`.
  - Test 2: caplog captures a WARNING-level message naming the finding and verdict.
  - Test 3 (regression): a review body with all findings cited continues to produce no warnings.
  - Test 4 (non-code safety): an arch-style review with `location: docs/foo.md#bar` parses with `location` set unchanged and no warning. Confirms the soft-fail path is template-agnostic and existing arch/slice/tasks reviews continue to parse identically.
  - Test 5 (normalization): findings with `location: -`, `location: global`, or `location: ` (empty) all normalize to `unverified` with a WARNING.

- [x] **T8. Add diff-membership check (code reviews only)**
  - File: `src/squadron/review/parsers.py` (or a new helper module if sizable)
  - After parsing, when a `ParsedReview` was produced from a `code`-template run AND a diff is available in the parser context, for each finding whose `location` cites a path (matches `^([^:#]+)(:|#|$)`), verify the path is one of the files in the diff.
  - On miss, log WARNING naming the finding ID and the cited path. Do not modify the finding.
  - This may require threading the diff (or the set of diff filenames) into the parser entry point. Survey call sites first.
  - Skip if `location == "unverified"`.
  - Success: synthetic test in T10 passes.

- [x] **T9. Add path-existence check (all template types)**
  - File: same as T8.
  - For every finding whose `location` cites a `path:` (line/range), `path#section`, or bare `path` form — and `location != "unverified"` — verify the path exists relative to the project root via `Path.exists()`.
  - On miss, log WARNING naming the finding ID and the cited path. Do not modify the finding.
  - This is the primary defense against hallucinated filenames in arch/slice/tasks reviews (where there is no diff). For code reviews, T8 catches the stricter case (path exists but isn't in the diff); T9 catches the looser case (path doesn't exist at all).
  - Cheap: one `Path.exists()` per finding.
  - Success: synthetic test in T10 passes.

- [x] **T10. Add tests for diff-membership and path-existence warnings**
  - Test 1 (T8): code review with one finding citing `src/nonexistent.py:42` and a diff touching only `src/squadron/foo.py` — assert WARNING logged (covers both T8 diff-miss AND T9 nonexistent), finding still parsed unchanged.
  - Test 2 (T8): code review with finding citing `src/squadron/bar.py:10` (file exists in repo but not in diff) — assert T8 WARNING logged but T9 does NOT warn.
  - Test 3 (T8): code review with all locations matching diff files — assert no WARNING.
  - Test 4 (T9): arch review citing `project-documents/nonexistent.md` — assert T9 WARNING logged.
  - Test 5 (T9): arch review citing an existing arch document — assert no WARNING.
  - Test 6 (T9): finding with `location: unverified` — assert no WARNING for either check.

- [x] **T11. Manual end-to-end verification (code template)**
  - Branch off main; pick a small, recent slice with a known diff.
  - Run `uv run sq review code <slice> -v --model <fast-model>`.
  - Inspect the resulting review file in `project-documents/user/reviews/`. Every finding (PASS included) should have a `location:` field.
  - Specifically check the `unverified` count: if the model emits many `unverified` locations, the prompt may need strengthening. If the model emits hallucinated paths instead of `unverified`, T8/T9 WARNINGS should fire — count and report.
  - Note: this depends on model behavior; if results are poor, log the prompt-engineering gap and consider a stronger prompt or a parser-side post-hoc location-inference step (out of scope for this slice).

- [x] **T12. Manual end-to-end verification (arch template)**
  - Run `uv run sq review arch <slice> -v --model <fast-model>`.
  - Inspect the resulting review file. Every finding should have a `location:` field; cross-cutting findings should use `unverified` with prose justification.
  - Verify T9 path-existence WARNING fires if model hallucinates an arch document path.

- [x] **T13. Documentation and final commits**
  - Update CHANGELOG.md under `### Fixed` (or `### Changed` if behavior shift is more apt).
  - Update DEVLOG.md with slice 904 entry summarizing the four coordinated changes (templates, soft-fail, diff-membership, path-existence) and any model-behavior caveats observed in T11/T12.
  - Fill in the verification walkthrough section in the slice doc with actual outputs.
  - Mark the slice complete in 900-slices.maintenance-and-refactoring.md.
  - Commits with semantic prefixes; suggested split:
    - `feat(review): require location: field on every finding (template prompts)`
    - `fix(review): soft-fail location parsing with WARNING and unverified normalization`
    - `feat(review): diff-membership and path-existence warnings for finding locations`
    - `docs: add slice 904 (review-finding-location-required)`

- [x] **T14. Final validation**
  - Run full gate: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run pyright`.
  - All must pass before marking complete.
  - Update task file `status: complete`, bump `dateUpdated`.
