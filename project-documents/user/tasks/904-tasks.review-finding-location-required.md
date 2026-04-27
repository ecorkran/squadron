---
docType: tasks
slice: review-finding-location-required
project: squadron
lld: user/slices/904-slice.review-finding-location-required.md
dependencies: []
projectState: 902 (verbosity passthrough + bootstrap_step_types) complete on main. Branch 904-review-finding-location-required.
dateCreated: 20260427
dateUpdated: 20260427
status: in_progress
---

## Context Summary

- Fixes [issue #10](https://github.com/ecorkran/squadron/issues/10): `location:` field on review findings is inconsistent and often missing on PASS findings.
- Three coordinated changes: (1) prompt updates in all four review templates; (2) soft-fail parser validator that auto-fills `-` and logs WARNING; (3) diff-membership WARNING for code reviews.
- Open questions resolved: soft-fail (not hard); WARNING-only path validation; standalone slice (don't wait on finding-schema).
- `task_ref:` field deferred to future slice (likely under 189 ensemble review).
- Files touched: 4 template YAMLs, `src/squadron/review/parsers.py`, possibly `src/squadron/review/models.py` (add `tags` or similar field), tests under `tests/review/`.
- Effort: 2/5. Risk: Low–Medium (changes prompt behavior; existing reviews stay parseable).

---

## Tasks

- [ ] **T1. Survey current template prompts**
  - Files: `src/squadron/data/templates/{code,slice,arch,tasks}.yaml`
  - For each template, locate the section that describes the finding format (severity, title, body).
  - Note the existing instructions about citing files/lines (if any).
  - Success: a one-paragraph note in the task file describing the current state of each template's location guidance.

- [ ] **T2. Update `code.yaml` finding-format prompt**
  - Add an explicit `location:` requirement to the finding format spec.
  - Spell out the precedence ladder: `path:line` → `path:start-end` → `path#symbol` → `path` → `-`/`global` (justify).
  - State that PASS findings get the same treatment.
  - Add multi-file guidance: cite primary location in `location:`, mention others in prose.
  - Success: a synthetic test review against the updated prompt produces `location:` on every finding (manual eyeball — full integration in T8).

- [ ] **T3. Update `slice.yaml` finding-format prompt**
  - Same structure as T2 but the preferred form is slice-doc `path:line` or code `path:line`.

- [ ] **T4. Update `arch.yaml` finding-format prompt**
  - Same structure as T2 but the preferred form is `path` (whole-doc) or `path#section-heading`.
  - Explicitly note that `-`/`global` with justification is more common for arch reviews (e.g. "missing coverage" findings).

- [ ] **T5. Update `tasks.yaml` finding-format prompt**
  - Same structure as T2 but the preferred form is code `path:line` (location of the issue, not the task ID).
  - Note that `task_ref:` is **not** currently part of the finding schema (future enhancement).

- [ ] **T6. Add soft-fail location validator to parser**
  - File: `src/squadron/review/parsers.py`
  - In `_extract_findings`, after the existing location extraction (`_LOCATION_RE` match + `file_ref` fallback), if the finding still has no location, set `location = "-"` and log WARNING via the module logger naming the finding's `id` (or title) and the verdict.
  - The existing `file_ref` fallback at line 128-130 already handles part of this; the change is to explicitly tag and warn when **both** sources are missing rather than leaving `location` as `None`.
  - Success: `pytest tests/review/test_parsers.py` — existing tests pass; new soft-fail test (T7) passes.

- [ ] **T7. Add parser tests for soft-fail and missing-location warning**
  - File: `tests/review/test_parsers.py` (or create if absent)
  - Test 1: a review body with one finding lacking `location:` produces `ReviewFinding.location == "-"`.
  - Test 2: caplog captures a WARNING-level message naming the finding and verdict.
  - Test 3 (regression): a review body with all findings cited continues to produce no warnings.

- [ ] **T8. Add diff-membership check (code reviews only)**
  - File: `src/squadron/review/parsers.py` (or a new helper module if it's sizable)
  - After parsing, when a `ParsedReview` was produced from a `code`-template run AND a diff is available in the parser context, for each finding whose `location` matches `^([^:#-][^:#]*):` (i.e. cites a path with a line spec), verify the path is one of the files in the diff.
  - On miss, log WARNING naming the finding and the cited path. Do not modify the finding.
  - This may require threading the diff (or the set of diff filenames) into the parser entry point. Survey the call sites in T1.5 if not already done.
  - Success: synthetic test in T9 passes.

- [ ] **T9. Add tests for diff-membership warning**
  - Test 1: code review with one finding citing `src/nonexistent.py:42` and a diff touching only `src/squadron/foo.py` — assert WARNING logged, finding still parsed unchanged.
  - Test 2: arch/slice/tasks review with same configuration — assert no WARNING (check skipped).
  - Test 3: code review with all locations matching diff files — assert no WARNING.

- [ ] **T10. Manual end-to-end verification (code template)**
  - Branch off main; pick a small, recent slice with a known diff.
  - Run `uv run sq review code <slice> -v --model <fast-model>`.
  - Inspect the resulting review file in `project-documents/user/reviews/`. Every finding (PASS included) should have a `location:` field.
  - Note: this depends on model behavior; if the model still drops locations on PASS findings, log the prompt-engineering gap and consider a stronger prompt or a parser-side post-hoc location-inference step (out of scope for this slice).

- [ ] **T11. Manual end-to-end verification (arch template)**
  - Run `uv run sq review arch <slice> -v --model <fast-model>`.
  - Inspect the resulting review file. Every finding should have a `location:` field; cross-cutting findings should use `-` with prose justification.

- [ ] **T12. Documentation and final commits**
  - Update CHANGELOG.md under `### Fixed` (or `### Changed` if behavior shift is more apt).
  - Update DEVLOG.md with slice 904 entry summarizing the three coordinated changes and any model-behavior caveats observed in T10/T11.
  - Fill in the verification walkthrough section in the slice doc with actual outputs.
  - Mark the slice complete in 900-slices.maintenance-and-refactoring.md (entry to be added in this slice's first commit).
  - Commits with semantic prefixes; suggested split:
    - `feat(review): require location: field on every finding (template prompts)`
    - `fix(review): soft-fail location parsing with WARNING and dedup tag`
    - `feat(review): diff-membership warning for code-review locations`
    - `docs: add slice 904 (review-finding-location-required)`

- [ ] **T13. Final validation**
  - Run full gate: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run pyright`.
  - All must pass before marking complete.
  - Update task file `status: complete`, bump `dateUpdated`.
