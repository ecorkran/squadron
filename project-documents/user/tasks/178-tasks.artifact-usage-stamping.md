---
docType: tasks
slice: artifact-usage-stamping
project: squadron
lld: user/slices/178-slice.artifact-usage-stamping.md
dependencies: [175, 176]
projectState: >
  Slice design complete (20261016) and trimmed after review. No code written. Slices 175 and 176
  are complete; main is the integration target (`git.integration_branch` unset).
dateCreated: 20261016
dateUpdated: 20261016
status: in_progress
---

## Context Summary

- Working on **178 artifact-usage-stamping** (fixes #222). A new POST_ACTION built-in,
  `squadron.usage-stamp`, folds each successful phase dispatch's `UsageRecord` into the
  frontmatter of the artifact it wrote (slice design, task file, architecture doc), so cost by
  stage survives `sq runs prune`. `sq stats slice` gains an `artifact spend` line read from those
  stamps. Slice 179 consumes `artifacts_usage_report` and `ArtifactUsage`.
- Tasks reference the slice design by decision number (D1–D6) rather than restating it. The
  design's D-sections, API Contracts, Success Criteria and Verification Walkthrough are the contract.
- Order follows the design's Development Approach: no-behavior-change refactors (Part A), the
  usage model (Part B), the stamp action (Part C), the report and slice line (Part D), docs (Part E).
- Every task that changes code ends with `ruff format`, `ruff check`, `pyright` (zero errors), the
  tests for the touched area, and a commit on the slice branch with a semantic prefix. Locate
  existing tests with `grep` before adding new files. Tests that write artifacts use `tmp_path`,
  never the project checkout.
- Out of scope (design Technical Scope, Excluded): summary/compact, implement dispatch, failed
  dispatches, model/profile/effort/`costBasis` keys, back-filling, split task breakdowns,
  atomic writes (#233), a `sq stats artifacts` command.
- Effort: 3/5. Next planned slice: 179 (Staged Effort Estimates and Accuracy).

---

## Task 1 — Create the slice branch

- [x] Confirm `cf config get git.integration_branch` is empty (target = `main`) and `git status` is clean
- [x] `git checkout -b 178-slice.artifact-usage-stamping main`
  - [x] Success: `git branch --show-current` prints `178-slice.artifact-usage-stamping`

---

## Part A — Refactors without behavior change (D3, D4)

## Task 2 — `RunCost.frontmatter_fields` and `RunCost.from_record`

- [x] In `src/squadron/review/run_cost.py`, add `frontmatter_fields() -> dict[str, object]` returning the 931 D10 key→value mapping that `frontmatter_lines()` renders today
  - [x] A key is present only when its value is not `None`; `costUsd` rounded to 6 places; `durationSeconds` a float rounded to 1 place (D4)
  - [x] Key order matches the current `frontmatter_lines()` output order
  - [x] Extract the key names (today inline literals in `frontmatter_lines()`) into module-level constants in `run_cost.py`; `frontmatter_fields()` uses them
- [x] Rewrite `frontmatter_lines()` to render from `frontmatter_fields()`; no other change to its output
- [x] Add classmethod `from_record(record: UsageRecord) -> RunCost` mapping each `UsageRecord` field onto the matching `RunCost` field
  - [x] Read `UsageRecord` in `pipeline/usage_capture.py` / `core/usage.py` for exact field names; do not guess
  - [x] Success: pyright clean; no caller of `frontmatter_lines()` changed

## Task 3 — Tests: `RunCost` key table

- [x] Run the existing review persistence and rendering tests unchanged (`tests/review/test_run_cost_rendering.py`, `tests/review/test_persistence.py`)
  - [x] Success: all pass with no test edits (review artifacts byte-identical)
- [x] Add tests beside `test_run_cost_rendering.py`
  - [x] `frontmatter_fields()` omits `None` fields and rounds `costUsd` and `durationSeconds` as D4
  - [x] `from_record` round-trips every populated `UsageRecord` field
- [x] Commit: `refactor(review): expose RunCost frontmatter fields as one key table`

## Task 4 — Move the frontmatter reader to `review/frontmatter_usage.py`

- [x] Create `src/squadron/review/frontmatter_usage.py`
  - [x] Move `_record` (as public `record_from_frontmatter(path, front)`), `_INT_KEYS`, `_int`, `_float`, `_basis` verbatim from `src/squadron/stats/reviews_report.py`
- [x] In `stats/reviews_report.py`, import `record_from_frontmatter` and delete the moved definitions
  - [x] Success: `grep -n "_INT_KEYS\|def _record" src/squadron/stats/reviews_report.py` returns nothing; pyright clean; `tests/stats/test_reviews_report.py` passes unchanged
- [x] As a separate edit after the move passes, replace the key string literals in the moved code with the `run_cost.py` key constants from Task 2, so each key is defined once (D4); change no parsing logic
  - [x] Success: `tests/stats/test_reviews_report.py` still passes unchanged

## Task 5 — Tests: reader move

- [x] Run `tests/stats/test_reviews_report.py` and the `sq stats reviews` CLI tests unchanged
  - [x] Success: all pass with no test edits
- [x] Commit: `refactor(review): move frontmatter usage reader beside RunCost`

## Task 6 — `dispatch_artifact_paths` in `artifact_paths.py`

- [x] In `src/squadron/events/builtin/artifact_paths.py`, add `dispatch_artifact_paths(kind, slice_param, plan_param, cf_client, cwd) -> list[str]` per the design's API Contracts (D3)
  - [x] Slice index present → `expected_artifact_paths(...)`; plan index with no slice → `[resolve_arch_file(index, cwd)]`
  - [x] Lift the branching from `dispatch_artifact._dispatch_artifact_post_condition_error` as-is; resolver exceptions propagate to the caller
- [x] Change `_dispatch_artifact_post_condition_error` to call `dispatch_artifact_paths`
  - [x] Its error messages, mtime check and `dispatch post-condition` log prefix stay exactly as they are
  - [x] Success: pyright clean

## Task 7 — Tests: path resolution move

- [x] Run `tests/events/builtin/test_dispatch_artifact.py` and `tests/pipeline/test_existing_keep.py` unchanged
  - [x] Success: all pass with no test edits
- [x] Add tests for `dispatch_artifact_paths` beside the existing `artifact_paths` tests (find with `grep -rn expected_artifact_paths tests`)
  - [x] Slice-scoped design and tasks kinds return the `expected_artifact_paths` list
  - [x] Plan-scoped design kind with no slice returns the arch file path
  - [x] A resolver error propagates (not swallowed)
- [x] Commit: `refactor(events): extract dispatch artifact path resolution`

---

## Part B — Artifact usage model (D2, D4)

## Task 8 — `review/artifact_usage.py`

- [x] Create `src/squadron/review/artifact_usage.py` with `USAGE_ROUNDS_KEY`, `PRICED_ROUNDS_KEY`, frozen `ArtifactUsage(cost, rounds, priced_rounds)` (API Contracts)
- [x] `fold(prior, record) -> ArtifactUsage` per D2
  - [x] Tokens and turns sum with `core/usage.add_optional`; a field no round reported stays `None`
  - [x] Cost sums priced rounds only; `priced_rounds` increments only when the record has a cost; an unpriced round never adds $0
  - [x] Duration sums with `add_optional_float`; `rounds` increments by one
  - [x] `prior=None` starts from an empty total
- [x] `artifact_usage_fields(usage) -> dict[str, object]`: `cost.frontmatter_fields()` without `costBasis` (#231), plus `usageRounds` and `pricedRounds`
- [x] `read_artifact_usage(path, front) -> ArtifactUsage | None`
  - [x] Returns `None` when `usageRounds` is absent
  - [x] Uses `record_from_frontmatter` and `RunCost.from_record` for the review keys
  - [x] Malformed prior (any usage key non-numeric, or `usageRounds` not a positive int, or `pricedRounds` not a non-negative int): returns `None` and logs one WARNING naming the path and the key (D2)
  - [x] Success: module imports nothing from `pipeline` or `events`; pyright clean

## Task 9 — Tests: artifact usage model

- [x] Add `tests/review/test_artifact_usage.py`
  - [x] Fold from `None` with a priced record: totals equal the record, `rounds=1`, `priced_rounds=1`
  - [x] Fold sequence priced → unpriced → priced: cost is the sum of the two priced rounds, `rounds=3`, `priced_rounds=2`
  - [x] A token field reported by no round is absent from `artifact_usage_fields`; reported by one round equals that value
  - [x] `artifact_usage_fields` never contains `costBasis`
  - [x] `read_artifact_usage` round-trips `artifact_usage_fields` output
  - [x] Missing `usageRounds` returns `None` with no WARNING
  - [x] Each malformed case returns `None` and asserts the WARNING names path and key (`caplog`)
- [x] Commit: `feat(review): add cumulative artifact usage model`

---

## Part C — `squadron.usage-stamp` (D1, D2, D6)

## Task 10 — `UsageStampAction`

- [x] Create `src/squadron/events/builtin/usage_stamp.py` modeled on `revision_stamp.py` (same registration pattern and protocol)
- [x] Eligibility (D1): act only when `action_type` is dispatch, `result.success`, and `expected_artifact_kind` is not `None`; otherwise return success with no effect
  - [x] No usage record in `result.metadata[USAGE_KEY]` → DEBUG line naming the step, return success
  - [x] Never read `result.outputs`
- [x] File selection (D1): call `dispatch_artifact_paths` with `params` `slice`/`plan`, keep candidates that exist on disk
  - [x] Exactly one → stamp it; more than one → WARNING naming the files, no stamp; zero → no stamp
- [x] Stamp: `read_frontmatter` → `read_artifact_usage` → `fold` → `update_frontmatter` with `artifact_usage_fields`
  - [x] Revision round (`context.iteration >= 1`, the field `revision_stamp.py` checks) with no prior `usageRounds`: WARNING with the D2 text `usage stamp: no prior usage keys on revision round {n} of {path}; total restarts and undercounts`
- [x] Failure handling (D6): resolution errors (cf client error, missing arch doc, non-numeric slice/plan), `FrontmatterError`, `OSError` → WARNING naming kind/scope or path and the reason; always return success
  - [x] Catch only those specific exception types, each with a comment (CLAUDE.md exception rule)
  - [x] Success: the action never alters `result`; pyright clean

## Task 11 — Tests: usage stamp, eligibility and happy paths

- [x] Add `tests/events/builtin/test_usage_stamp.py`, calling the action directly, using a temp project with real `SLICES_DIR`/`TASKS_DIR`/`ARCHITECTURE_DIR` layout and a fake cf client; frontmatter fixtures copied from real slice, task and arch files in this repo
  - [x] Slice design dispatch: file gains the review keys, `usageRounds: 1`, `pricedRounds: 1`; values match the record
  - [x] Task file dispatch stamped the same way
  - [x] Plan-scoped design dispatch stamps the architecture doc
  - [x] Second fold on the same file (revision round with prior keys): totals summed, `usageRounds: 2`, no WARNING
  - [x] Unpriced record: `usageRounds` increments, `pricedRounds` and `costUsd` unchanged
  - [x] Body bytes unchanged after stamping; existing frontmatter keys keep their order
- [x] Eligibility (no file change asserted for each): non-dispatch action, failed dispatch, `expected_artifact_kind=None` (implement), empty `metadata` (`existing: keep` / prompt-only)
- [x] No `StateManager` writes during a stamp (patch or spy on its save method)
- [x] Commit: `feat(events): add usage stamp event action`

## Task 12 — Tests: usage stamp failure modes (D6)

- [x] One test per D6 row the stamp owns, each asserting the action returns success and the stated log signal (`caplog`)
  - [x] cf resolution error → WARNING naming kind, scope, reason
  - [x] Plan scope with no arch doc → WARNING
  - [x] Non-numeric slice param → WARNING
  - [x] Artifact with no frontmatter block, and with invalid YAML → WARNING naming path and `FrontmatterError`
  - [x] `OSError` on write → WARNING naming path
  - [x] Two candidates on disk (`nnn-tasks.name-1.md`, `-2.md`) → no stamp, WARNING naming both files
  - [x] Revision round with no prior keys → D2 WARNING text, file stamped with `usageRounds: 1`
  - [x] Malformed prior key → WARNING naming path and key, total restarts
  - [x] No usage record → DEBUG naming the step
- [x] Commit: `test(events): cover usage stamp failure modes`

## Task 13 — Register the binding, with tests

- [x] Register `squadron.usage-stamp` with the built-in event actions the same way `revision-stamp` is registered
- [x] In `src/squadron/events/manifest.py`, append the POST_ACTION binding to `DEFAULT_BINDINGS` directly after `squadron.revision-stamp`
- [x] Binding tests (extend `tests/events/test_manifest.py`)
  - [x] `squadron.usage-stamp` follows `squadron.revision-stamp` in `DEFAULT_BINDINGS`
  - [x] An `events.yaml` `disable:` entry for `squadron.usage-stamp` removes it, as for other built-ins
- [x] Commit: `feat(events): bind usage stamp after revision stamp`

---

## Part D — Artifacts report and `sq stats slice` line (D5)

## Task 14 — `stats/artifacts_report.py`

- [x] Create `src/squadron/stats/artifacts_report.py` with `ArtifactUsageRow` (API Contracts) and a report type holding the rows; name it `ArtifactsUsageReport`
- [x] `artifacts_usage_report(project_root, slice_filter)` per D5
  - [x] Reads top-level `*.md` in `SLICES_DIR` and `TASKS_DIR`, and `*-arch.*.md` in `ARCHITECTURE_DIR`, frontmatter only
  - [x] Kind from the directory: `TASKS_DIR` → `ArtifactKind.TASKS`; `SLICES_DIR` and `ARCHITECTURE_DIR` → `ArtifactKind.DESIGN`
  - [x] Slice from the file name's leading index, reusing the reviews report's rule (import it; do not reimplement; if the helper is underscore-private, make it public in place and update its callers)
  - [x] `slice_filter` keeps only rows whose slice matches
  - [x] Files without `usageRounds` skipped silently; unreadable file (`FrontmatterError`, `OSError`) skipped with a WARNING naming the path
- [x] Provide a per-kind aggregate (cost of priced rounds, `rounds`, `priced_rounds`) for the slice line; keep it in this module so 179 can reuse it
  - [x] Success: pyright clean

## Task 15 — Tests: artifacts report

- [x] Add `tests/stats/test_artifacts_report.py`; fixtures copied from real slice, task and arch frontmatter in this repo, with usage keys appended (CLAUDE.md parsing rule)
  - [x] One stamped design, one stamped task file, one stamped arch doc → three rows with correct kind and slice
  - [x] Unstamped files produce no row and no WARNING
  - [x] Unreadable file → skipped with WARNING naming the path
  - [x] `slice_filter` excludes other slices' files
  - [x] Nested subdirectories under `SLICES_DIR`/`TASKS_DIR` are not read
  - [x] Per-kind aggregate sums cost and round counts
  - [x] No run state exists in the temp project (179 integration requirement)
- [x] Commit: `feat(stats): add artifacts usage report`

## Task 16 — `artifact spend` line on `sq stats slice`

- [x] In `stats/effort_report.py`, attach the slice's `artifacts_usage_report(..., slice_filter=index)` result to the slice report
- [x] In `cli/stats_effort_views.py`, print one line directly after `recorded spend`: `artifact spend: design $x (k of m rounds) · tasks $y (k of m rounds) (floor)` (D5, UI Specifications)
  - [x] Only kinds with stamped rows appear; no stamped rows → line omitted
  - [x] Unpriced rounds show via `k of m`; never rendered as $0 when no round is priced (follow the existing `_spend` rendering for the no-cost case)
  - [x] Never added into `recorded spend`
  - [x] Success: pyright clean

## Task 17 — Tests: slice line

- [x] Extend `tests/cli/test_stats_effort.py` and `tests/stats/test_effort_report.py` (the report now carries the artifact usage attachment from Task 16)
  - [x] Stamped design and tasks → line shows both kinds after `recorded spend`, ending in the `(floor)` label
  - [x] The attachment on the slice report holds the per-kind aggregate
  - [x] Only a design stamped → line shows design only
  - [x] No stamps → no `artifact spend` line
  - [x] Recorded spend value is the same with and without stamped artifacts
  - [x] No run state at all (pruned) → artifact spend line still shown
- [x] Commit: `feat(stats): show artifact spend on sq stats slice`

---

## Part E — Docs and verification

## Task 18 — Architecture, slice plan and CHANGELOG

- [x] `project-documents/user/architecture/140-arch.pipeline-foundation.md`
  - [x] Add `usage_stamp.py  # POST_ACTION — 178 usage stamp` to the `events/builtin/` tree, after the `revision_stamp.py` entry
  - [x] In the sentence naming "the built-in dispatch-artifact-then-revision-stamp ordering", name the order as dispatch-artifact, then revision-stamp, then usage-stamp
  - [x] Amend the sentence ending "reusing only `ActionResult` and `ValidationError`" to say built-ins also import pipeline-layer helpers (`dispatch-artifact` the path helpers; `usage-stamp` `UsageRecord` and `review/artifact_usage`)
- [x] Confirm `140-slices.pipeline-foundation.md` entry 34 already states the dispatch-only scope (it does as of 20261016); edit only if not
- [x] Add a CHANGELOG `Unreleased` bullet: design, task and architecture docs written by a pipeline now record their production cost in frontmatter, and `sq stats slice` shows it as artifact spend
- [x] Commit: `docs: record usage stamp in pipeline architecture and changelog`

## Task 19 — Full validation and walkthrough

- [x] Run `ruff format`, `ruff check`, `pyright` (zero errors), and the full test suite
  - [x] Success: all pass; any failure fixed before continuing
- [ ] Before the walkthrough, ask the Project Manager to confirm running live P4 and P5 pipelines (they spend real LLM budget); if not confirmed, mark the walkthrough items not run in the slice design and continue
- [ ] Run the design's Verification Walkthrough steps 1–6 on a scratch slice, and record results (pass/fail per step, with the observed values) in the slice design's Verification Walkthrough section
  - [ ] Pruning in step 5 targets only the scratch runs created for this walkthrough; if `sq runs prune` cannot select only those runs, stop and ask the Project Manager before pruning
  - [ ] Delete the scratch slice's artifacts afterwards; they are not committed
- [ ] Commit: `docs: record artifact usage stamping walkthrough results`
