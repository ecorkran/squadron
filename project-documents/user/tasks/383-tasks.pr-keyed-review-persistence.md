---
docType: tasks
slice: pr-keyed-review-persistence
project: squadron
lld: user/slices/383-slice.pr-keyed-review-persistence.md
dependencies: [382, 916, 917]
projectState: "382 merged; `sq review pr` reviews but persists nothing — the save callback is stubbed to always return false. 916 and 917 complete and present on `squadron-pr`. No context-forge dependency (retired at design time, D7)."
dateCreated: 20260915
dateUpdated: 20260915
status: not_started
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

- [ ] **1.1 Add the `RulesSource` enum**
  - [ ] Define a `RulesSource` StrEnum in `src/squadron/review/rules.py` with members for project, user, template, and none
  - [ ] Values are lowercase strings (`project`, `user`, `template`, `none`) — these are written to frontmatter and read back
  - [ ] Success: enum defined; `pyright` clean; no other module changed yet
  - [ ] Effort: 1

- [ ] **1.2 Change `resolve_rules_dir` to return path and source**
  - [ ] Return the resolved path **and** its `RulesSource` together instead of a bare `Path | None`
  - [ ] Each of the five existing branches reports the source that produced it; the not-found branch reports `NONE`
  - [ ] Do not change which path any branch resolves — this task is behavior-preserving on the path value
  - [ ] Success: every existing caller updated to the new signature; `ruff check` and `pyright` clean
  - [ ] Effort: 2

- [ ] **1.3 Test the rules-source branches** *(test-with 1.1–1.2)*
  - [ ] Create `tests/review/test_rules_source.py`
  - [ ] Assert each `RulesSource` branch is reported for the directory layout that triggers it
  - [ ] **Pin the paths:** assert every existing caller's resolved *path* is unchanged from pre-change behavior
  - [ ] Success: all tests pass; the full existing review test suite passes unchanged
  - [ ] Effort: 2

- [ ] **1.4 Commit** — `refactor(review): resolve_rules_dir reports its source`
  - [ ] Success: `ruff format`, `ruff check`, `pyright` all clean before committing
  - [ ] Effort: 1

---

## Task 2 — Capture byte-identity fixtures (before any persistence change)

This task must complete **before** Task 3 touches `persistence.py`. Fixtures captured after the change prove nothing.

- [ ] **2.1 Capture pre-migration artifacts for all three existing paths**
  - [ ] Generate and store a reference artifact for a **slice** review, an **arch** review, and a **pipeline step** review
  - [ ] Store under `tests/review/fixtures/` as the exact bytes each path writes today
  - [ ] Record in the fixture directory (or a short README) which commit the fixtures were captured at
  - [ ] Success: three fixture files exist and are committed; each was produced by current unmodified code
  - [ ] Effort: 2

- [ ] **2.2 Add the byte-identity test harness** *(test-with 2.1)*
  - [ ] Create `tests/review/test_persistence_migration.py`
  - [ ] Assert each path's current output equals its fixture byte-for-byte
  - [ ] Success: all three comparisons pass **against unmodified code** — confirming the harness is wired correctly before it is relied upon
  - [ ] Effort: 2

- [ ] **2.3 Commit** — `test(review): capture pre-migration persistence fixtures`
  - [ ] Success: fixtures and harness committed together; this is the rollback point for the migration
  - [ ] Effort: 1

---

## Task 3 — The `SaveTarget` contract (D1, D2)

- [ ] **3.1 Define the `SaveTarget` protocol**
  - [ ] Create `src/squadron/review/save_target.py`
  - [ ] Three methods only: `filename_stem(review_type)`, `frontmatter_fields()`, `source_document()`
  - [ ] The reviews directory is **not** a protocol method — it is invocation-dependent and passed to `save_review_result` as it is today (D1)
  - [ ] Use `typing.Protocol` (structural), not a base class or union — `review/` must never name `PrTarget`
  - [ ] Success: module imports nothing from `squadron.codehost`; `pyright` clean
  - [ ] Effort: 2

- [ ] **3.2 Implement `SliceTarget`**
  - [ ] Wraps the existing `SliceInfo` rather than replacing it — `SliceInfo` keeps its current shape and consumers
  - [ ] `frontmatter_fields()` returns the `slice` key; `filename_stem` reproduces today's slice naming exactly
  - [ ] Resolves `reviewed_sha` from git as the current code does
  - [ ] Success: implements the protocol; `pyright` clean
  - [ ] Effort: 1

- [ ] **3.3 Implement `ArchTarget`**
  - [ ] Takes an initiative index and arch document — this replaces `_arch_slice_info`'s fabrication (`cli/commands/review.py`)
  - [ ] `filename_stem` reproduces today's arch review naming exactly
  - [ ] Success: implements the protocol; `pyright` clean
  - [ ] Effort: 1

- [ ] **3.4 Implement `StepTarget`**
  - [ ] Takes a pipeline step name and index
  - [ ] `filename_stem` reproduces today's step-keyed naming exactly
  - [ ] Success: implements the protocol; `pyright` clean
  - [ ] Effort: 1

- [ ] **3.5 Test the three implementations** *(test-with 3.1–3.4)*
  - [ ] Create `tests/review/test_save_target.py`
  - [ ] One test per implementation covering stem, frontmatter fields, and source document
  - [ ] Success: all pass; separate assertions per implementation, not one combined test
  - [ ] Effort: 2

- [ ] **3.6 Split frontmatter rendering into common and target-specific (D2)**
  - [ ] `_review_frontmatter_lines` stops emitting `slice:` unconditionally; target-specific keys come from `frontmatter_fields()`
  - [ ] Common keys stay where they are (`docType`, `layer`, `reviewType`, `project`, `verdict`, `sourceDocument`, `aiModel`, `status`, dates, existing optional keys)
  - [ ] **Keep line-based rendering.** Do not move to `yaml.safe_dump` — 917's artifact work depends on current formatting (D2)
  - [ ] `reviewed_sha` comes from the target rather than being resolved inside `save_review_result`
  - [ ] **Add no new frontmatter key here.** `rulesSource` and `targetKind` land together in Task 8, after byte-identity is verified — adding either now would make the Task 3.8 check unable to distinguish an intended key from unintended drift (D2)
  - [ ] Success: `pyright` clean; the rendered key set is unchanged from pre-migration
  - [ ] Effort: 3

- [ ] **3.7 Migrate `save_review_result` and `format_review_markdown` to take a target**
  - [ ] Both take a `SaveTarget` rather than a `SliceInfo`
  - [ ] Slice and arch call sites in `cli/commands/review.py` pass targets; `_arch_slice_info` is deleted
  - [ ] Success: `ruff check` and `pyright` clean
  - [ ] Effort: 3

- [ ] **3.8 Verify byte-identity for slice and arch** *(test-with 3.6–3.7)*
  - [ ] Run `tests/review/test_persistence_migration.py` — slice and arch artifacts must match their Task 2 fixtures byte-for-byte
  - [ ] **Any diff is a regression, not an improvement.** Do not update a fixture to match new output
  - [ ] Success: slice and arch comparisons pass; full existing test suite passes
  - [ ] Effort: 2

- [ ] **3.9 Commit** — `refactor(review): persistence takes a save target`
  - [ ] Success: `ruff format`, `ruff check`, `pyright` clean; byte-identity passing for slice and arch
  - [ ] Effort: 1

---

## Task 4 — Migrate the pipeline step path (D2)

This is a **behavior change on an existing path**, not pure refactoring — it is the only save path that never runs the refuse-on-failed-archive guard.

- [ ] **4.1 Route the step path through the contract**
  - [ ] `src/squadron/pipeline/actions/review.py` stops calling `format_review_markdown` + `save_review_file` directly
  - [ ] It calls `save_review_result` with a `StepTarget`, gaining `archive_existing_review`'s guard
  - [ ] **Preserve the action's existing boundary:** its `try/except` around the save keeps persistence failure non-fatal to the action
  - [ ] Success: `pyright` clean
  - [ ] Effort: 2

- [ ] **4.2 Test the step path's byte-identity and its new refusal** *(test-with 4.1)*
  - [ ] Step artifact matches its Task 2 fixture byte-for-byte
  - [ ] **New test for the deliberate change:** a step review whose target file cannot be archived is refused and logged, and the action still returns its review result rather than failing
  - [ ] Success: both pass; the refusal is observable in logs at WARNING or above, not silent
  - [ ] Effort: 2

- [ ] **4.3 Commit** — `refactor(pipeline): migrate step-keyed save onto the contract`
  - [ ] Success: all three byte-identity comparisons now pass; `ruff format`, `ruff check`, `pyright` clean
  - [ ] Effort: 1

---

## Task 5 — `PullRequestRecord.path_key` (D3)

- [ ] **5.1 Promote `_flatten_key` to a record property**
  - [ ] Add a `path_key` property to `PullRequestRecord` returning the flattened, filesystem-safe form
  - [ ] Collapse `codehost/worktree.py::_flatten_key` onto it — one definition, not two copies that can drift
  - [ ] **Correct the misleading docstring:** `key` is `host/owner/repo#number` and is *not* filesystem-safe; say which property is
  - [ ] Success: worktree directory naming behavior unchanged; `pyright` clean
  - [ ] Effort: 2

- [ ] **5.2 Test `path_key` and worktree naming** *(test-with 5.1)*
  - [ ] Assert `path_key` contains no `/` or `#`
  - [ ] Assert existing worktree directory names are unchanged by the collapse
  - [ ] Success: both pass
  - [ ] Effort: 1

- [ ] **5.3 Commit** — `refactor(codehost): promote flattened key to PullRequestRecord.path_key`
  - [ ] Effort: 1

---

## Task 6 — Reviews-directory precedence and failure modes (D5)

- [ ] **6.1 Add the `review.external_reviews_dir` config key**
  - [ ] In `src/squadron/config/keys.py`, following the existing `metrology.store_dir` shape (`type_=str`, `default=None`)
  - [ ] Success: key registered and readable; `pyright` clean
  - [ ] Effort: 1

- [ ] **6.2 Implement the precedence resolver**
  - [ ] Order: `--reviews-dir` → existing project reviews dir → `review.external_reviews_dir` → `~/.config/squadron/reviews/<host>/<owner>/<repo>/`
  - [ ] Built-in default is under `~/.config/squadron/` — **not** `data_dir()`, which resolves to the installed package's read-only directory
  - [ ] Rule 2 **requires** the project reviews directory to already exist; it is never created, so squadron does not put `project-documents/` in a repository that did not ask for one
  - [ ] **Precedence selects once and never falls through on failure** — a failure of the selected directory is an error, not an advance to the next rule (the silent fallback the project rules forbid)
  - [ ] Print the chosen directory **and which rule chose it**
  - [ ] Success: `pyright` clean
  - [ ] Effort: 3

- [ ] **6.3 Add the `--reviews-dir` flag**
  - [ ] Add to `sq review pr`; help text distinguishes it from the existing `--output-path` (a JSON dump destination, unchanged in meaning)
  - [ ] Success: flag parses; help text names both
  - [ ] Effort: 1

- [ ] **6.4 Test precedence and every enumerated failure mode** *(test-with 6.1–6.3)*
  - [ ] Table-test the full chain: flag beats existing project dir, beats config key, beats built-in default
  - [ ] `--reviews-dir` at a non-existent path is **created** (`parents=True`) and written
  - [ ] An uncreatable directory reports `UNSAVED` with non-zero exit and a message naming the path and the selecting rule
  - [ ] A failed write reports `UNSAVED` with non-zero exit
  - [ ] **No fall-through on failure:** assert the next-rule location is empty afterwards
  - [ ] Success: all four failure modes produce an observable signal, each asserted
  - [ ] Effort: 3

- [ ] **6.5 Commit** — `feat(review): add reviews-directory precedence and --reviews-dir`
  - [ ] Effort: 1

---

## Task 7 — `PrTarget` and the real save (D3, D8)

- [ ] **7.1 Implement `PrTarget` in the CLI layer**
  - [ ] Construct in `src/squadron/cli/commands/review_pr.py` — **not** in `review/`, which must never import `codehost`
  - [ ] Takes the `PullRequestRecord` and the `RulesSource` from Task 1
  - [ ] Stem is `{path_key}-review.{review_type}` — no slice-name segment, and never derived from the PR title
  - [ ] `frontmatter_fields()` returns a `pr` mapping (host, owner, repository, number, url) and no slice key; nested mapping renders as indented lines the way `criteria:` already does
  - [ ] `source_document()` is the PR URL
  - [ ] **`reviewed_sha` is `record.head_sha`** — never `resolve_reviewed_sha(".")`, which on this path is the operator's tree
  - [ ] Success: `pyright` clean; import-graph test still passes
  - [ ] Effort: 2

- [ ] **7.2 Replace 382's stub with the real save (D8)**
  - [ ] Delete `_NOT_PERSISTABLE_REASON` and the `save=lambda _target: False` stub
  - [ ] `NOT_PERSISTABLE` survives only for its real case: a review with no target to name an artifact under (slice-less `sq review code`)
  - [ ] A PR review always has a target — it saves, or reports `UNSAVED` with non-zero exit
  - [ ] Success: `ruff check` and `pyright` clean
  - [ ] Effort: 2

- [ ] **7.3 Test PR persistence** *(test-with 7.1–7.2)*
  - [ ] Create `tests/cli/test_review_pr_persistence.py`
  - [ ] **`reviewedSha` is the PR's, not yours** — set up operator HEAD deliberately different from PR head so the two cannot pass by coincidence
  - [ ] Unplanned-repository case: review saves externally and `git status --porcelain` is empty afterwards
  - [ ] A PR review of a slice-less `sq review code` still takes `NOT_PERSISTABLE`
  - [ ] Success: all pass; no test requires `gh`, network, or auth
  - [ ] Effort: 3

- [ ] **7.4 Commit** — `feat(review): persist PR reviews under a PR-keyed name`
  - [ ] Effort: 1

---

## Task 8 — The two additive frontmatter keys, and consumer regression tests (D2, D4, D6)

Both new keys land here, **after** Task 3.8 and Task 4.2 have proven byte-identity green against untouched fixtures. This is the one deliberate artifact change in the slice; it is not part of the migration's diff (D2).

- [ ] **8.1 Write `rulesSource` and `targetKind` through the contract**
  - [ ] Thread the `RulesSource` from Task 1.2 through to `frontmatter_fields()` so `rulesSource` is written on **every** review, not only PR reviews (D6)
  - [ ] Every target writes `targetKind` (`slice` | `arch` | `step` | `pr`) (D4)
  - [ ] **Absence means `slice`** for `targetKind`, and absence of `rulesSource` is never inferred as any particular source — artifacts written before this task keep parsing
  - [ ] `*-review.*` consumers (`metrology/discovery`, archive, digest) classify by reading `targetKind` — **never by parsing the filename**
  - [ ] Success: `pyright` clean
  - [ ] Effort: 2

- [ ] **8.2 Regenerate the fixtures and pin the diff** *(test-with 8.1)*
  - [ ] Regenerate the three Task 2 fixtures **once**, now that both keys exist
  - [ ] Assert the regenerated fixtures differ from the pre-migration ones by **exactly these two keys and nothing else**, on all three paths
  - [ ] A third difference is unintended drift the migration check would otherwise have hidden — investigate it, do not absorb it into the fixture
  - [ ] Success: the two-key diff is asserted, not eyeballed; `tests/review/test_persistence_migration.py` passes against the regenerated fixtures
  - [ ] Effort: 2

- [ ] **8.3 Test `rulesSource` end-to-end** *(test-with 8.1)*
  - [ ] Write a review artifact, read `rulesSource` back **from the written file**, and assert it matches the directory the loader actually used — for each of the `project`, `user`, and `template` branches
  - [ ] This closes the gap between Task 1.3 (the resolver returns the right source) and 8.1 (the field is written): neither alone catches a hardcoded value or a source that never reaches `frontmatter_fields()`
  - [ ] Assert an artifact written without the key still parses
  - [ ] Success: all branches pass; a deliberately hardcoded `rulesSource` fails this test
  - [ ] Effort: 2

- [ ] **8.4 Test that `{index}-review.*` consumers cannot match** *(test-with 8.1)*
  - [ ] Create `tests/review/test_review_consumers_ignore_pr.py`
  - [ ] Place a PR review of PR 42 beside a slice review of slice 42 in one directory
  - [ ] Assert `sq review resolve 42` selects the slice review
  - [ ] Assert metrology capture for index 42 selects the slice review
  - [ ] Success: both pass — these consumers build their glob from an `int`, so a non-numeric prefix cannot match by construction; this test pins that
  - [ ] Effort: 2

- [ ] **8.5 Test that archiving, digest, and 917 integrity run on a PR artifact**
  - [ ] Assert each runs unchanged against a PR review artifact
  - [ ] Success: all pass without changes to those paths — they are target-agnostic already
  - [ ] Effort: 2

- [ ] **8.6 Commit** — `feat(review): add rules-source and target-kind frontmatter keys`
  - [ ] Effort: 1

---

## Task 9 — Documentation, validation, and closeout

- [ ] **9.1 Update the naming-conventions guide**
  - [ ] Add the PR review filename form to `project-documents/ai-project-guide/file-naming-conventions.md`
  - [ ] Success: the form is documented alongside the existing review naming sections
  - [ ] Effort: 1

- [ ] **9.2 Add the cf frontmatter validation test**
  - [ ] Add a PR-shaped fixture test under `tests/documents/`
  - [ ] **Assert `filesChecked` increased by one**, never merely that findings were zero — a *skipped* file also reports zero findings (D7)
  - [ ] Note for the implementer: `cf validate frontmatter` resolves by **registered project**, not cwd; `-p` is the only override. The valid probe is the no-argument walk against the registered root, comparing counts
  - [ ] Success: `filesChecked` increases by one and findings are zero
  - [ ] Effort: 2

- [ ] **9.3 Confirm the pre-existing schema-drift failures are unchanged**
  - [ ] The three `tests/documents/test_schema_drift.py` failures in this worktree are context-forge #88 (registered-root mismatch), **not this slice's to fix**
  - [ ] Success: the same three fail, no more and no fewer, and no new failure is introduced
  - [ ] Effort: 1

- [ ] **9.4 Full verification pass**
  - [ ] `ruff format`, `ruff check`, `pyright` — zero pyright errors is a merge blocker
  - [ ] Confirm no module under `review/` imports `squadron.codehost` (existing import-graph test, with `save_target.py` now present)
  - [ ] Confirm all three byte-identity fixtures still match
  - [ ] Success: full suite green except the three known #88 failures
  - [ ] Effort: 2

- [ ] **9.5 Live verification run**
  - [ ] Execute the LLD's "Verification Walkthrough" (steps 1–6) in a clone with `gh` authenticated, against an open PR
  - [ ] Record the evidence from steps 2, 4, and 6 for the DEVLOG
  - [ ] Success: each step's stated expectation observed; evidence captured, not summarized from memory
  - [ ] Effort: 2

- [ ] **9.6 DEVLOG entry**
  - [ ] Follow `prompt.ai-project.system.md`, section "Session State Summary"
  - [ ] Include the live evidence from 9.5
  - [ ] Effort: 1

- [ ] **9.7 CHANGELOG line**
  - [ ] Short user-facing bullet — technical detail belongs in the DEVLOG
  - [ ] Effort: 1

- [ ] **9.8 Mark the slice complete**
  - [ ] Set `status: complete` in the slice design and check the 383 entry in `380-slices.pull-request-workflow.md`
  - [ ] **Mark any dropped or skipped task item `[x]` before closing** — the visualizer reads checkbox state
  - [ ] Effort: 1

- [ ] **9.9 Final commit** — `docs: record slice 383 completion`
  - [ ] Effort: 1
