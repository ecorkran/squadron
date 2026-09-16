---
docType: review
layer: project
reviewType: code
slice: pr-keyed-review-persistence
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/383-slice.pr-keyed-review-persistence.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260916
dateUpdated: 20260916
responseStatus: addressed
reviewedSha: e5e9e2ad7f14a22b53590dc7f45c494a67e35072
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Arch reviews persist with `targetKind: slice`; `ArchTarget` is unreachable in production"
    location: "src/squadron/cli/commands/review.py#_save_arch"
  - id: F002
    severity: concern
    category: correctness
    summary: "`resolve_reviews_dir` reads the config key without the `cwd` it was given"
    location: "src/squadron/review/reviews_dir.py#resolve_reviews_dir"
  - id: F003
    severity: concern
    category: async-correctness
    summary: "Pipeline success-path save runs a 30s-bounded git subprocess and file I/O on the event loop"
    location: "src/squadron/pipeline/actions/review.py#ReviewAction._review"
  - id: F004
    severity: concern
    category: testing
    summary: "The PR-persistence regression test is vacuous, and `_save_pr`'s wiring has no CLI-level test"
    location: "tests/cli/test_review_pr.py#test_pr_review_no_longer_reports_persistence_unavailable"
  - id: F005
    severity: concern
    category: testing
    summary: "The cf frontmatter test writes fixtures into the live repository tree and hard-fails without `cf`"
    location: "tests/documents/test_pr_review_frontmatter.py"
  - id: F006
    severity: note
    category: documentation
    summary: "`SaveTarget` docstrings still say \"three questions\" while declaring four methods"
    location: "src/squadron/review/save_target.py#SaveTarget"
  - id: F007
    severity: note
    category: structure
    summary: "Fifth private cross-module import deepens the `pyright: ignore[reportPrivateUsage]` pattern"
    location: "src/squadron/cli/commands/review_pr.py"
  - id: F008
    severity: note
    category: correctness
    summary: "`rulesSource` under-reports when only a `--rules` file is injected"
    location: "src/squadron/cli/commands/review_pr.py#_resolve_pr_rules_content"
  - id: F009
    severity: pass
    category: testing
    summary: "Migration discipline and drift guards are exemplary"
    location: "tests/review/test_persistence_migration.py"
---

# Review: code — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [FAIL] Arch reviews persist with `targetKind: slice`; `ArchTarget` is unreachable in production

In `review_arch`, `arch_failure_target` is non-`None` exactly when `arch_index` is non-`None` (it is built as `_arch_slice_info(arch_index, input_file) if arch_index is not None else None`), and `_resolve_save_outcome(target=arch_index, save=_save_arch, ...)` only invokes `_save_arch` when `arch_index` is not `None`. Therefore the `else ArchTarget(...)` branch in `_save_arch` is dead code — every persisted arch review renders through `SliceTarget`, whose `frontmatter_fields()` (`src/squadron/review/save_target.py`) returns `targetKind: slice`.

Consequences:

- `sq review arch 380` (the documented index form) writes `targetKind: slice` into the durable artifact, while the slice's own regeneration fixture `tests/review/fixtures/383-postkeys-arch.md:6` records `targetKind: arch` for the same review shape. Production output contradicts the pinned artifact.
- D4's contract — "a `targetKind` frontmatter key (`slice | arch | step | pr`) written by every target through the contract" — is violated on the only path that persists arch reviews. 384/385, listed as required interfaces, classify by reading this key, so every index-keyed arch review will be misclassified as a slice review when those land. Artifacts already written stay wrong; they are archived, not regenerated.
- The design's D1 correction states "`_arch_slice_info` survives, narrowed. The save path no longer calls it" — but the save path's `SliceTarget` wraps exactly that fabrication. The in-code comment ("reuse it rather than rebuilding the identity a second way") rationalizes the reuse without accounting for the `targetKind` consequence.
- No test catches it: `tests/review/test_persistence_migration.py::test_arch_path` constructs `ArchTarget` directly, and there is no CLI-level test asserting `targetKind` on a saved arch artifact.

The fix is small: construct `ArchTarget` in both branches of `_save_arch` (the failure path can keep its own fabricated `SliceInfo`, since `save_provider_failure` still takes one). Note also that the path-invocation form (`sq review arch <path>.md`) was already NOT_PERSISTABLE pre-slice (`target=arch_index` is `None`), which is why the else branch was added without a reachable caller.

### [CONCERN] `resolve_reviews_dir` reads the config key without the `cwd` it was given

The resolver accepts `cwd` and uses it for rule 2 (`Path(cwd) / REVIEWS_DIR`), but calls `get_config("review.external_reviews_dir")` with no `cwd`. `get_config(key, cwd=".")` resolves the project-level `.squadron.toml` from the *process* working directory (`config/manager.py:87`, `project_config_path`), not from the checkout. So `sq review pr 83 --cwd /path/to/repo` run from anywhere else silently ignores a `review.external_reviews_dir` set in that repo's `.squadron.toml` and falls through to the built-in default — a silent location change on the exact path D5 exists to make visible. This is inconsistent with `_resolve_pr_max_bytes(cwd)` in the same command (`src/squadron/cli/commands/review_pr.py`), which threads `cwd` into its config read. Pass `cwd=cwd` to the `get_config` call.

### [CONCERN] Pipeline success-path save runs a 30s-bounded git subprocess and file I/O on the event loop

The migrated step branch calls `save_review_result(...)` synchronously inside `async def _review`. Through `StepTarget.reviewed_sha()` this runs `run_git(["rev-parse", "HEAD"], cwd)` — the comment in `_save_failure_artifact` in the same file states that subprocess is "bounded at 30s" — plus `archive_existing_review`'s read/mkdir/write bytes. Thirty lines above, the provider-failure branch routes the identical work through `asyncio.to_thread(_save_failure_artifact, ...)` with an explicit comment that "no blocking call belongs on the event loop inside an async def (project async rule)". The pre-migration code had the same inline blocking shape, so this is inherited rather than newly introduced — but this slice rewrote the block and left the asymmetry in place. Wrap the success-path save in `asyncio.to_thread` the same way.

### [CONCERN] The PR-persistence regression test is vacuous, and `_save_pr`'s wiring has no CLI-level test

The test invokes `[*_PARITY_BASE, "--no-save"]`. `_resolve_save_outcome` returns `SUPPRESSED` on `no_save` *before* reaching the `target is None` branch, so 382's stub (`target=None` + `_NOT_PERSISTABLE_REASON`) also printed nothing under `--no-save` — the assertions pass against the pre-change code and guard nothing. The docstring's justification (the fake `_Result` can't render an artifact) explains the `--no-save` choice but not why the assertion was kept in a form that cannot fail.

Relatedly, nothing tests the composition the slice actually built: `tests/cli/test_review_pr_persistence.py` unit-tests `PrTarget` and the sha, `tests/review/test_reviews_dir.py` unit-tests the resolver, and `tests/review/test_pr_artifact_is_target_agnostic.py` calls `save_review_result` directly — but no test drives `sq review pr` and asserts the artifact lands where `resolve_reviews_dir` says, or that a failed save reports `UNSAVED` with exit 1. The slice's own success criteria promise exactly those CLI-level assertions ("an uncreatable directory and a failed write each report UNSAVED with a non-zero exit and a message naming the path"; the unplanned-repo no-write end-to-end check), and they are not present. Mocking `save_review_result` in the CLI test would let the regression test run without `--no-save` and actually exercise the changed path.

### [CONCERN] The cf frontmatter test writes fixtures into the live repository tree and hard-fails without `cf`

`_skip_unless_this_checkout_is_the_registered_root` and both tests write `zz-*.md` fixtures into the repository's real `project-documents/user/reviews/` directory (not `tmp_path`). A killed or interrupted run leaves stray files in the working tree that `cf validate` then walks and that can be accidentally committed; concurrent runs can also observe each other's fixtures through the shared `filesChecked` count. The in-root requirement is a genuine cf limitation and is documented, but the *hard failure* when `cf` is absent (`raise AssertionError`) makes the entire suite red on any machine without the external binary — at odds with the slice's own testing norm ("No test here needs gh, network, or auth") and with the suite's otherwise self-contained fixtures. At minimum, the fixture writes belong behind a guard that cannot leave debris (write-then-always-unlink including on `mkdir` failure), and the missing-`cf` case deserves reconsideration given the suite is otherwise runnable offline.

### [NOTE] `SaveTarget` docstrings still say "three questions" while declaring four methods

The module docstring ("three questions persistence actually asks") and the `SaveTarget` class docstring ("The three target-specific questions") were not updated when `reviewed_sha()` was added as the fourth method. The persistence-side copy (`SaveTargetProtocol` in `persistence.py`) documents the fourth method explicitly; the canonical protocol should too, since it is the one implementers read. Similarly, `save_review_result`'s docstring (`src/squadron/review/persistence.py#save_review_result`) documents only `OSError` under Raises but now also raises `ValueError` when neither `target` nor `slice_info` is supplied.

### [NOTE] Fifth private cross-module import deepens the `pyright: ignore[reportPrivateUsage]` pattern

`_cf_project_name` is imported from `squadron.cli.commands.review` with a `reportPrivateUsage` suppression, alongside the four existing private imports. The design (D5) explicitly declined a fifth private import of `REVIEWS_DIR` on the grounds the pattern was "already flagged four times" — then added one anyway for `_cf_project_name`, which is a Context-Forge integration concern living in the review CLI module rather than beside `ContextForgeClient` or in a shared helper. Not blocking, but the next private import will be the sixth.

### [NOTE] `rulesSource` under-reports when only a `--rules` file is injected

The key records which source produced the rules *directory*. When `--rules <file>` supplies manual content and no rules directory resolves, the artifact writes `rulesSource: none` even though rules demonstrably reached the reviewer — the mirror image of the `--no-rules` reasoning the same code block states ("naming a directory in the artifact would claim a provenance this run does not have"). This is the directory-scoped definition D6 chose, so it is design-sanctioned, but it is a known false-negative worth recording before consumers treat `none` as "no rules were given".

### [PASS] Migration discipline and drift guards are exemplary

The two-fixture-set approach (pre-migration captures vs. postkeys regenerations, with `TestTheTwoNewKeysAreTheOnlyChange` asserting the diff is exactly the two sanctioned keys), the explicit repair of the harness hole ("a green byte-identity check is what the migration wanted to see"), the `__protocol_attrs__` equality test that keeps the deliberately duplicated protocol declarations honest, the mechanism-level sha test (`resolver.assert_not_called()` rather than value-only), and the resolver-level no-fall-through tests each encode a real failure mode rather than a happy path. The design document's honest recording of its own corrections (the fourth protocol method, the surviving `_arch_slice_info`, the cf registered-root limitation) is exactly the documentation quality this project should keep.

## Response

All nine findings accepted. Every actionable one (F001–F008) is fixed; F009 records
no defect. Verified after the changes: `ruff format` clean, `ruff check` clean,
`pyright` 0 errors, full suite **3 failed / 4055 passed / 6 skipped**. The three
failures are `tests/documents/test_schema_drift.py`, the known context-forge #88
out-of-root symptom (`filesChecked: 0`) this worktree already carried — an untouched
file, failing identically before these changes.

### [FAIL] F001 — arch reviews persisted as `targetKind: slice`

Confirmed and fixed. `_save_arch` ran only when `arch_index is not None`, which is
exactly when `arch_failure_target` was non-`None`, so the `SliceTarget` branch always
won and the `ArchTarget` branch was unreachable. Every persisted arch review carried
`targetKind: slice`, contradicting the slice's own pinned fixture.

`_save_arch` now constructs `ArchTarget` unconditionally
(`src/squadron/cli/commands/review.py`). `_arch_slice_info` survives for
`save_provider_failure`, its one remaining consumer, as D1 intended.

The finding's last observation — that no test caught this because the migration test
constructs `ArchTarget` directly — was the more useful half. Added
`TestArchReviewsPersistAsArchReviews` in `tests/cli/test_review_save_outcome.py`: it
drives `sq review arch 380` through the CLI and asserts on the frontmatter actually
written, not on the target type, since the artifact is what 384/385 will classify by.

### [CONCERN] F002 — `resolve_reviews_dir` ignored its own `cwd`

Confirmed and fixed. `get_config` defaults `cwd="."`, resolving `.squadron.toml` from
the process working directory, so `--cwd` silently lost a repository's
`review.external_reviews_dir`. Now passes `cwd=cwd`, matching
`_resolve_pr_max_bytes`. The same latent bug existed in `_resolve_pr_rules_content`'s
`default_rules` read; fixed there too.

### [CONCERN] F003 — blocking save on the event loop

Confirmed and fixed. Both success-path saves in `ReviewAction._review` now run through
`asyncio.to_thread`, matching the provider-failure branch thirty lines above. Correctly
characterized as inherited rather than introduced — but this slice rewrote the block,
which is where it became ours.

### [CONCERN] F004 — vacuous regression test, untested `_save_pr` wiring

Confirmed and fixed. `--no-save` returned `SUPPRESSED` before the `target is None`
branch, so the test passed against 382's stub and guarded nothing.

The test now runs without `--no-save`, mocks `save_review_result`, and asserts the save
was actually reached — so the absence of the refusal wording means something. Added
`test_a_failed_pr_save_reports_unsaved_and_exits_one` for the CLI-level failure path
the slice's success criteria promised: exit 1, with the path named.

### [CONCERN] F005 — fixture debris in the live tree

Confirmed and fixed. Replaced the hand-rolled write/`finally` pairs with a
`_fixture_in_reviews` context manager that always unlinks, with `mkdir` inside the
guarded region — previously a failure between `mkdir` and the caller's `try` escaped
cleanup entirely. Worth noting this is not hypothetical: a stray review artifact from a
verification run had to be cleaned out of this directory before the slice's own closing
commit.

The hard-fail on missing `cf` is kept deliberately. The finding is right that it
diverges from the suite's offline norm, but a schema test that skips when the schema
tool is absent is the silent fallback the project rules forbid — it would report green
while proving nothing. The in-root skip stays because context-forge #88 is a real
external limitation with an issue against it; the missing-binary case is not.

### [NOTE] F006 — stale docstrings

Fixed. `SaveTarget`'s module and class docstrings now say four questions and name
`reviewed_sha` as the fourth. `save_review_result` now documents `ValueError` alongside
`OSError`.

### [NOTE] F007 — fifth private cross-module import

Fixed by removing the import rather than suppressing it again. `_cf_project_name` moved
to `squadron.integrations.context_forge` as `cf_project_name`, beside
`ContextForgeClient` — it was a Context-Forge concern that happened to live in the
review CLI, and both review commands are its callers rather than its owner. Four private
imports remain, not six.

### [NOTE] F008 — `rulesSource` under-reporting

Fixed. Added `RulesSource.FILE`. When `--rules` (or the `default_rules` config key)
supplies content and no rules directory resolves, the artifact records `file` instead of
`none`. The finding called this design-sanctioned and merely worth recording; recording
it as `none` would have let consumers read "no rules were given" about a run that
demonstrably got some, so it is fixed rather than noted.

### [PASS] F009

No action. Noted for the fixture discipline it describes.

### Run Digest

- Response length: 10952 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 77688
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
