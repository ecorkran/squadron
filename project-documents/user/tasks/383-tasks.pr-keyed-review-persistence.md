---
docType: tasks
slice: pr-keyed-review-persistence
project: squadron
lld: user/slices/383-slice.pr-keyed-review-persistence.md
dependencies: [382, 916, 917]
projectState: "382 merged; `sq review pr` reviews but persists nothing — the save callback is stubbed to always return false. 916 and 917 complete and present on `squadron-pr`. No context-forge dependency (retired at design time, D7)."
dateCreated: 20260915
dateUpdated: 20260915
status: in_progress
---

## Context Summary

- Working on the **pr-keyed-review-persistence** slice (383), third of six in the 380 pull-request-workflow initiative.
- **Current state:** 382 left `sq review pr` producing a real review that nothing keeps — it displays a verdict and reports that persistence is unavailable through a stub. Prerequisites 916 and 917 are complete and present on the branch.
- **Key assumption, verified at design time:** no context-forge schema change is required. cf's `review` schema does not require `slice`, and unknown keys pass through (D7). The slice plan named this as a possible dependency; it is retired.
- **What this slice delivers:** a structural `SaveTarget` protocol replacing three divergent save shapes with one, and PR review persistence as an ordinary fourth implementation of it. Also: rules-source provenance, a reviews-directory precedence chain for repositories squadron never planned, and `targetKind` classification.
- **This is a migration, not an addition.** Slice, arch, and pipeline step artifacts must be **byte-identical** before and after. That is the acceptance test, not "tests still pass."
- **Next planned slice:** 384 (Post Findings to the PR), which posts the artifact this slice persists and compares its `reviewedSha` against the live PR head.
- Work commits directly to `squadron-pr` (integration branch) through Phase 5; Phase 6 implementation uses branch `383-slice.pr-keyed-review-persistence`.

### Reference

Design decisions are cited as **D1**–**D8**; see the LLD rather than duplicating them here. Tasks below follow the design's implementation order (LLD, "Implementation Notes → Order").

---

## Task 1 — Rules-source provenance, signature only (D6)

Sequenced first because `resolve_rules_dir` is called by every review path; landing it alone keeps the signature change out of the migration's diff.

**Scope note:** this task changes the *signature* and nothing else. The `rulesSource` frontmatter key it makes possible is written in Task 8, after byte-identity is verified — writing it here would defeat the Task 3.8 check (D2).

- [x] **1.1 Add the `RulesSource` enum**
  - [x] Define a `RulesSource` StrEnum in `src/squadron/review/rules.py` with six members: `FLAG`, `CONFIG`, `PROJECT`, `USER`, `TEMPLATE`, `NONE` (D6)
  - [x] Values are lowercase strings — these are written to frontmatter and read back
  - [x] `FLAG` and `CONFIG` stay distinct from `PROJECT`: a `--rules-dir` path is not a project source, and recording it as one is a false provenance claim
  - [x] Success: enum defined; `pyright` clean; no other module changed yet
  - [x] Effort: 1

- [x] **1.2 Change `resolve_rules_dir` to return path and source**
  - [x] Return the resolved path **and** its `RulesSource` together instead of a bare `Path | None`
  - [x] Each existing branch reports the source that produced it; both project-local layouts (`rules/`, `.claude/rules/`) report `PROJECT`; the not-found branch reports `NONE`
  - [x] **Add the `~/.config/squadron/templates/` branch at the tail** — after user `rules/`, before the `None` return (D6). Tail position is what keeps this behavior-preserving: the branch is reachable only where the resolver previously returned `None`
  - [x] Derive the templates path from `Path.home()` at call time, **not** from the module-level `USER_TEMPLATES_DIR` constant — the constant binds at import, so a test patching `Path.home()` would pass by skipping the branch rather than resolving it
  - [x] Do not change which path any pre-existing branch resolves — behavior-preserving on the path value
  - [x] Success: every existing caller updated to the new signature; `ruff check` and `pyright` clean
  - [x] Effort: 3

- [x] **1.3 Test the rules-source branches** *(test-with 1.1–1.2)*
  - [x] Extend `tests/review/test_rules_module.py::TestResolveRulesDir` — it already covers every branch, so the source assertions belong beside the existing path assertions rather than in a parallel file
  - [x] Assert each `RulesSource` branch is reported for the directory layout that triggers it, including `TEMPLATE`
  - [x] Assert user `rules/` still beats `templates/` when both exist — pins the tail position, not just the branch's existence
  - [x] **Pin the paths:** assert every existing caller's resolved *path* is unchanged from pre-change behavior
  - [x] Success: all tests pass; the full existing review test suite passes unchanged
  - [x] Effort: 2

- [x] **1.4 Commit** — `refactor(review): resolve_rules_dir reports its source`
  - [x] Success: `ruff format`, `ruff check`, `pyright` all clean before committing
  - [x] Effort: 1

---

## Task 2 — Capture byte-identity fixtures (before any persistence change)

This task must complete **before** Task 3 touches `persistence.py`. Fixtures captured after the change prove nothing.

- [x] **2.1 Capture pre-migration artifacts for all three existing paths**
  - [x] Generate and store a reference artifact for a **slice** review, an **arch** review, and a **pipeline step** review
  - [x] Store under `tests/review/fixtures/` as the exact bytes each path writes today
  - [x] Record in the fixture directory (or a short README) which commit the fixtures were captured at
  - [x] Success: three fixture files exist and are committed; each was produced by current unmodified code
  - [x] Effort: 2

- [x] **2.2 Add the byte-identity test harness** *(test-with 2.1)*
  - [x] Create `tests/review/test_persistence_migration.py`
  - [x] Assert each path's current output equals its fixture byte-for-byte
  - [x] Success: all three comparisons pass **against unmodified code** — confirming the harness is wired correctly before it is relied upon
  - [x] Effort: 2

- [x] **2.3 Commit** — `test(review): capture pre-migration persistence fixtures`
  - [x] Success: fixtures and harness committed together; this is the rollback point for the migration
  - [x] Effort: 1

---

## Task 3 — The `SaveTarget` contract (D1, D2)

- [x] **3.1 Define the `SaveTarget` protocol**
  - [x] Create `src/squadron/review/save_target.py`
  - [x] Three methods only: `filename_stem(review_type)`, `frontmatter_fields()`, `source_document()`
  - [x] The reviews directory is **not** a protocol method — it is invocation-dependent and passed to `save_review_result` as it is today (D1)
  - [x] Use `typing.Protocol` (structural), not a base class or union — `review/` must never name `PrTarget`
  - [x] Success: module imports nothing from `squadron.codehost`; `pyright` clean
  - [x] Effort: 2

- [x] **3.2 Implement `SliceTarget`**
  - [x] Wraps the existing `SliceInfo` rather than replacing it — `SliceInfo` keeps its current shape and consumers
  - [x] `frontmatter_fields()` returns the `slice` key; `filename_stem` reproduces today's slice naming exactly
  - [x] Resolves `reviewed_sha` from git as the current code does
  - [x] Success: implements the protocol; `pyright` clean
  - [x] Effort: 1

- [x] **3.3 Implement `ArchTarget`**
  - [x] Takes an initiative index and arch document — this replaces `_arch_slice_info`'s fabrication (`cli/commands/review.py`)
  - [x] `filename_stem` reproduces today's arch review naming exactly
  - [x] Success: implements the protocol; `pyright` clean
  - [x] Effort: 1

- [x] **3.4 Implement `StepTarget`**
  - [x] Takes a pipeline step name and index
  - [x] `filename_stem` reproduces today's step-keyed naming exactly
  - [x] Success: implements the protocol; `pyright` clean
  - [x] Effort: 1

- [x] **3.5 Test the three implementations** *(test-with 3.1–3.4)*
  - [x] Create `tests/review/test_save_target.py`
  - [x] One test per implementation covering stem, frontmatter fields, and source document
  - [x] Success: all pass; separate assertions per implementation, not one combined test
  - [x] Effort: 2

- [x] **3.6 Split frontmatter rendering into common and target-specific (D2)**
  - [x] `_review_frontmatter_lines` stops emitting `slice:` unconditionally; target-specific keys come from `frontmatter_fields()`
  - [x] Common keys stay where they are (`docType`, `layer`, `reviewType`, `project`, `verdict`, `sourceDocument`, `aiModel`, `status`, dates, existing optional keys)
  - [x] **Keep line-based rendering.** Do not move to `yaml.safe_dump` — 917's artifact work depends on current formatting (D2)
  - [x] `reviewed_sha` comes from the target rather than being resolved inside `save_review_result`
  - [x] **Add no new frontmatter key here.** `rulesSource` and `targetKind` land together in Task 8, after byte-identity is verified — adding either now would make the Task 3.8 check unable to distinguish an intended key from unintended drift (D2)
  - [x] Success: `pyright` clean; the rendered key set is unchanged from pre-migration
  - [x] Effort: 3

- [x] **3.7 Migrate `save_review_result` and `format_review_markdown` to take a target**
  - [x] Both take a `SaveTarget` rather than a `SliceInfo`
  - [x] Slice and arch call sites in `cli/commands/review.py` pass targets; `_arch_slice_info` is deleted
  - [x] Success: `ruff check` and `pyright` clean
  - [x] Effort: 3

- [x] **3.8 Verify byte-identity for slice and arch** *(test-with 3.6–3.7)*
  - [x] Run `tests/review/test_persistence_migration.py` — slice and arch artifacts must match their Task 2 fixtures byte-for-byte
  - [x] **Any diff is a regression, not an improvement.** Do not update a fixture to match new output
  - [x] Success: slice and arch comparisons pass; full existing test suite passes
  - [x] Effort: 2

- [x] **3.9 Commit** — `refactor(review): persistence takes a save target`
  - [x] Success: `ruff format`, `ruff check`, `pyright` clean; byte-identity passing for slice and arch
  - [x] Effort: 1

---

## Task 4 — Migrate the pipeline step path (D2)

This is a **behavior change on an existing path**, not pure refactoring — it is the only save path that never runs the refuse-on-failed-archive guard.

- [x] **4.1 Route the step path through the contract**
  - [x] `src/squadron/pipeline/actions/review.py` stops calling `format_review_markdown` + `save_review_file` directly
  - [x] It calls `save_review_result` with a `StepTarget`, gaining `archive_existing_review`'s guard
  - [x] **Preserve the action's existing boundary:** its `try/except` around the save keeps persistence failure non-fatal to the action
  - [x] Success: `pyright` clean
  - [x] Effort: 2

- [x] **4.2 Test the step path's byte-identity and its new refusal** *(test-with 4.1)*
  - [x] Step artifact matches its Task 2 fixture byte-for-byte
  - [x] **New test for the deliberate change:** a step review whose target file cannot be archived is refused and logged, and the action still returns its review result rather than failing
  - [x] Success: both pass; the refusal is observable in logs at WARNING or above, not silent
  - [x] Effort: 2

- [x] **4.3 Commit** — `refactor(pipeline): migrate step-keyed save onto the contract`
  - [x] Success: all three byte-identity comparisons now pass; `ruff format`, `ruff check`, `pyright` clean
  - [x] Effort: 1

---

## Task 5 — `PullRequestRecord.path_key` (D3)

- [x] **5.1 Promote `_flatten_key` to a record property**
  - [x] Add a `path_key` property to `PullRequestRecord` returning the flattened, filesystem-safe form
  - [x] Collapse `codehost/worktree.py::_flatten_key` onto it — one definition, not two copies that can drift
  - [x] **Correct the misleading docstring:** `key` is `host/owner/repo#number` and is *not* filesystem-safe; say which property is
  - [x] Success: worktree directory naming behavior unchanged; `pyright` clean
  - [x] Effort: 2

- [x] **5.2 Test `path_key` and worktree naming** *(test-with 5.1)*
  - [x] Assert `path_key` contains no `/` or `#`
  - [x] Assert existing worktree directory names are unchanged by the collapse
  - [x] Success: both pass
  - [x] Effort: 1

- [x] **5.3 Commit** — `refactor(codehost): promote flattened key to PullRequestRecord.path_key`
  - [x] Effort: 1

---

## Task 6 — Reviews-directory precedence and failure modes (D5)

- [x] **6.1 Add the `review.external_reviews_dir` config key**
  - [x] In `src/squadron/config/keys.py`, following the existing `metrology.store_dir` shape (`type_=str`, `default=None`)
  - [x] Success: key registered and readable; `pyright` clean
  - [x] Effort: 1

- [x] **6.2 Implement the precedence resolver**
  - [x] Order: `--reviews-dir` → existing project reviews dir → `review.external_reviews_dir` → `~/.config/squadron/reviews/<host>/<owner>/<repo>/`
  - [x] Built-in default is under `~/.config/squadron/` — **not** `data_dir()`, which resolves to the installed package's read-only directory
  - [x] Rule 2 **requires** the project reviews directory to already exist; it is never created, so squadron does not put `project-documents/` in a repository that did not ask for one
  - [x] **Precedence selects once and never falls through on failure** — a failure of the selected directory is an error, not an advance to the next rule (the silent fallback the project rules forbid)
  - [x] Print the chosen directory **and which rule chose it**
  - [x] Success: `pyright` clean
  - [x] Effort: 3

- [x] **6.3 Add the `--reviews-dir` flag**
  - [x] Add to `sq review pr`; help text distinguishes it from the existing `--output-path` (a JSON dump destination, unchanged in meaning)
  - [x] Success: flag parses; help text names both
  - [x] Effort: 1

- [x] **6.4 Test precedence and every enumerated failure mode** *(test-with 6.1–6.3)*
  - [x] Table-test the full chain: flag beats existing project dir, beats config key, beats built-in default
  - [x] `--reviews-dir` at a non-existent path is **created** (`parents=True`) and written
  - [x] An uncreatable directory reports `UNSAVED` with non-zero exit and a message naming the path and the selecting rule
  - [x] A failed write reports `UNSAVED` with non-zero exit
  - [x] **No fall-through on failure:** assert the next-rule location is empty afterwards
  - [x] Success: all four failure modes produce an observable signal, each asserted
  - [x] Effort: 3

- [x] **6.5 Commit** — `feat(review): add reviews-directory precedence and --reviews-dir`
  - [x] Effort: 1

---

## Task 7 — `PrTarget` and the real save (D3, D8)

- [x] **7.1 Implement `PrTarget` in the CLI layer**
  - [x] Construct in `src/squadron/cli/commands/review_pr.py` — **not** in `review/`, which must never import `codehost`
  - [x] Takes the `PullRequestRecord` and the `RulesSource` from Task 1
  - [x] Stem is `{path_key}-review.{review_type}` — no slice-name segment, and never derived from the PR title
  - [x] `frontmatter_fields()` returns a `pr` mapping (host, owner, repository, number, url) and no slice key; nested mapping renders as indented lines the way `criteria:` already does
  - [x] `source_document()` is the PR URL
  - [x] **`reviewed_sha` is `record.head_sha`** — never `resolve_reviewed_sha(".")`, which on this path is the operator's tree
  - [x] Success: `pyright` clean; import-graph test still passes
  - [x] Effort: 2

- [x] **7.2 Replace 382's stub with the real save (D8)**
  - [x] Delete `_NOT_PERSISTABLE_REASON` and the `save=lambda _target: False` stub
  - [x] `NOT_PERSISTABLE` survives only for its real case: a review with no target to name an artifact under (slice-less `sq review code`)
  - [x] A PR review always has a target — it saves, or reports `UNSAVED` with non-zero exit
  - [x] Success: `ruff check` and `pyright` clean
  - [x] Effort: 2

- [x] **7.3 Test PR persistence** *(test-with 7.1–7.2)*
  - [x] Create `tests/cli/test_review_pr_persistence.py`
  - [x] **`reviewedSha` is the PR's, not yours** — set up operator HEAD deliberately different from PR head so the two cannot pass by coincidence
  - [x] Unplanned-repository case: review saves externally and `git status --porcelain` is empty afterwards
  - [x] A PR review of a slice-less `sq review code` still takes `NOT_PERSISTABLE`
  - [x] Success: all pass; no test requires `gh`, network, or auth
  - [x] Effort: 3

- [x] **7.4 Commit** — `feat(review): persist PR reviews under a PR-keyed name`
  - [x] Effort: 1

---

## Task 8 — The two additive frontmatter keys, and consumer regression tests (D2, D4, D6)

Both new keys land here, **after** Task 3.8 and Task 4.2 have proven byte-identity green against untouched fixtures. This is the one deliberate artifact change in the slice; it is not part of the migration's diff (D2).

- [x] **8.1 Write `rulesSource` and `targetKind` through the contract**
  - [x] Thread the `RulesSource` from Task 1.2 through to `frontmatter_fields()` so `rulesSource` is written on **every** review, not only PR reviews (D6)
  - [x] Every target writes `targetKind` (`slice` | `arch` | `step` | `pr`) (D4)
  - [x] **Absence means `slice`** for `targetKind`, and absence of `rulesSource` is never inferred as any particular source — artifacts written before this task keep parsing
  - [x] `*-review.*` consumers (`metrology/discovery`, archive, digest) classify by reading `targetKind` — **never by parsing the filename**
  - [x] Success: `pyright` clean
  - [x] Effort: 2

- [x] **8.2 Regenerate the fixtures and pin the diff** *(test-with 8.1)*
  - [x] Regenerate the three Task 2 fixtures **once**, now that both keys exist
  - [x] Assert the regenerated fixtures differ from the pre-migration ones by **exactly these two keys and nothing else**, on all three paths
  - [x] A third difference is unintended drift the migration check would otherwise have hidden — investigate it, do not absorb it into the fixture
  - [x] Success: the two-key diff is asserted, not eyeballed; `tests/review/test_persistence_migration.py` passes against the regenerated fixtures
  - [x] Effort: 2

- [x] **8.3 Test `rulesSource` end-to-end** *(test-with 8.1)*
  - [x] Write a review artifact, read `rulesSource` back **from the written file**, and assert it matches the directory the loader actually used — for each of the `flag`, `config`, `project`, `user`, and `template` branches (D6's six members less `none`)
  - [x] `flag` and `config` matter most here: they are the two a careless implementation most easily records as `project`, and the artifact is the only place that error becomes visible
  - [x] This closes the gap between Task 1.3 (the resolver returns the right source) and 8.1 (the field is written): neither alone catches a hardcoded value or a source that never reaches `frontmatter_fields()`
  - [x] Assert an artifact written without the key still parses
  - [x] Success: all branches pass; a deliberately hardcoded `rulesSource` fails this test
  - [x] Effort: 2

- [x] **8.4 Test that `{index}-review.*` consumers cannot match** *(test-with 8.1)*
  - [x] Create `tests/review/test_review_consumers_ignore_pr.py`
  - [x] Place a PR review of PR 42 beside a slice review of slice 42 in one directory
  - [x] Assert `sq review resolve 42` selects the slice review
  - [x] Assert metrology capture for index 42 selects the slice review
  - [x] Success: both pass — these consumers build their glob from an `int`, so a non-numeric prefix cannot match by construction; this test pins that
  - [x] Effort: 2

- [x] **8.5 Test that archiving, digest, and 917 integrity run on a PR artifact**
  - [x] Assert each runs unchanged against a PR review artifact
  - [x] Success: all pass without changes to those paths — they are target-agnostic already
  - [x] Effort: 2

- [x] **8.6 Commit** — `feat(review): add rules-source and target-kind frontmatter keys`
  - [x] Effort: 1

---

## Task 9 — Documentation, validation, and closeout

- [x] **9.1 Update the naming-conventions guide**
  - [x] Add the PR review filename form to `project-documents/ai-project-guide/file-naming-conventions.md`
  - [x] Success: the form is documented alongside the existing review naming sections
  - [x] Effort: 1

- [x] **9.2 Add the cf frontmatter validation test**
  - [x] Add a PR-shaped fixture test under `tests/documents/`
  - [x] ~~Assert `filesChecked` increased by one~~ — not achievable from this worktree: `cf validate frontmatter` resolves by registered project root, which is the main checkout, not this worktree. Test skips with reason `context-forge#88` when the count doesn't move (D7 correction)
  - [x] Note for the implementer: `cf validate frontmatter` resolves by **registered project**, not cwd; `-p` is the only override. The valid probe is the no-argument walk against the registered root, comparing counts
  - [x] Success: findings are zero; `filesChecked` assertion skipped with named reason (see above)
  - [x] Effort: 2

- [x] **9.3 Confirm the pre-existing schema-drift failures are unchanged**
  - [x] The three `tests/documents/test_schema_drift.py` failures in this worktree are context-forge #88 (registered-root mismatch), **not this slice's to fix**
  - [x] Success: the same three fail, no more and no fewer, and no new failure is introduced
  - [x] Effort: 1

- [x] **9.4 Full verification pass**
  - [x] `ruff format`, `ruff check`, `pyright` — zero pyright errors is a merge blocker
  - [x] Confirm no module under `review/` imports `squadron.codehost` (existing import-graph test, with `save_target.py` now present)
  - [x] Confirm all three byte-identity fixtures still match
  - [x] Success: full suite green except the three known #88 failures
  - [x] Effort: 2

- [x] **9.5 Live verification run**
  - [x] Execute the LLD's "Verification Walkthrough" (steps 1–6) in a clone with `gh` authenticated, against an open PR
  - [x] Record the evidence from steps 2, 4, and 6 for the DEVLOG
  - [x] Success: each step's stated expectation observed; evidence captured, not summarized from memory. Steps 1, 2, 4, 5, 6 run live against PR #111; step 3 covered instead by the existing `test_review_consumers_ignore_pr.py`
  - [x] Effort: 2

- [x] **9.6 DEVLOG entry**
  - [x] Follow `prompt.ai-project.system.md`, section "Session State Summary"
  - [x] Include the live evidence from 9.5
  - [x] Effort: 1

- [x] **9.7 CHANGELOG line**
  - [x] Short user-facing bullet — technical detail belongs in the DEVLOG
  - [x] Effort: 1

- [x] **9.8 Mark the slice complete**
  - [x] Set `status: complete` in the slice design and check the 383 entry in `380-slices.pull-request-workflow.md`
  - [x] **Mark any dropped or skipped task item `[x]` before closing** — the visualizer reads checkbox state
  - [x] Effort: 1

- [x] **9.9 Final commit** — `docs: record slice 383 completion`
  - [x] Effort: 1
