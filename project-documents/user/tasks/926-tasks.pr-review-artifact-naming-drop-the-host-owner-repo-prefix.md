---
docType: tasks
slice: pr-review-artifact-naming-drop-the-host-owner-repo-prefix
project: squadron
lldReference: project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Design finalized, reviewed PASS (glm-5.3-flash) with two accepted notes folded in (F009 fixture-preservation list, F010 D7 ordering language). No code changes yet.
status: not_started
dateCreated: 20260925
dateUpdated: 20260925
---

# Tasks: PR Review Artifact Naming — Drop the Host/Owner/Repo Prefix

## Context Summary

Fixes [issue #124](https://github.com/ecorkran/squadron/issues/124). `sq review pr`
names its artifact from `PullRequestRecord.path_key`
([models.py:57](src/squadron/codehost/models.py#L57)), producing
`github.com-ecorkran-squadron-83-review.code.md`. The host/owner/repo prefix is
redundant whenever the artifact lands in a directory that already belongs to
one repository — the common case. This slice shortens the name to
`pr-{number}-review.{type}.md`, qualifying with `{owner}-{repo}` only when the
resolved reviews directory can hold reviews from more than one repository.

Full rationale is in the design
([926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md](project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md)) —
read D1–D7 before implementing. In particular:

- **D1**: qualification is decided by the existing `ReviewsDirRule` enum
  ([reviews_dir.py](src/squadron/review/reviews_dir.py)), not by comparing
  against the `origin` git remote. `PROJECT` and `DEFAULT` → unqualified;
  `CONFIG` and `FLAG` → qualified.
- **D3**: `PullRequestRecord.path_key` stays the scratch worktree's name only.
  `PrTarget` stops using it and builds its own stem.
- **D5**: the slice plan's claim that `pr/inputs.py`'s
  `*-review.*.md` glob misses the new name is **wrong** — verified it
  matches. Add a pinning test; do not touch the glob.
- **D6**: no migration. Three test fixture files build old-name
  (`github.com-…`) artifacts on purpose and must not be renamed — see Part C.

**Current project state:** design only, no code changes. Effort for the whole
slice: 2/5 per the design.

**Dependencies:** none. Initiative 380 (the `sq review pr` path) is complete.

**Next planned slice:** none specific — general maintenance backlog per
[900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md).

---

## Part A — `ReviewsDirRule.repository_scoped`

### Task A.1 — Add the `repository_scoped` property

- [ ] Effort: 1/5
- [ ] In [src/squadron/review/reviews_dir.py](src/squadron/review/reviews_dir.py),
      add a `repository_scoped` property (or equivalent classmethod-backed
      property) to `ReviewsDirRule` (defined ~line 36):
      - `PROJECT` → `True`
      - `DEFAULT` → `True`
      - `CONFIG` → `False`
      - `FLAG` → `False`
- [ ] Docstring states the property is the single place this mapping lives
      (per D1's table) — do not duplicate the True/False decision anywhere
      else in the codebase.

### Task A.2 — Exhaustiveness test

- [ ] Effort: 1/5
- [ ] In `tests/review/test_reviews_dir.py` (or create it if no such file
      exists — check first), add a test that iterates every
      `ReviewsDirRule` member and asserts `repository_scoped` does not raise
      for any of them (e.g. call it for each member pulled from
      `ReviewsDirRule.__members__` or equivalent iteration).
- [ ] The point: adding a new rule without deciding its `repository_scoped`
      value must fail this test, not silently default.
- [ ] Add a second, simple test asserting the exact True/False mapping from
      D1's table for all four current members.
- [ ] Run: `pytest tests/review/test_reviews_dir.py -x`.

---

## Part B — `PrTarget` stem and qualification

### Task B.1 — Add `qualify` to `PrTarget` and rebuild `filename_stem`

- [ ] Effort: 2/5
- [ ] In [src/squadron/cli/commands/review_pr.py](src/squadron/cli/commands/review_pr.py),
      change `PrTarget.__init__` (currently at line 131, signature
      `(self, record: PullRequestRecord, rules_source: RulesSource)`) to accept
      a third keyword-only parameter `qualify: bool`. Store it as
      `self._qualify`.
- [ ] Replace `filename_stem` (currently line 144:
      `return f"{self._record.path_key}-review.{review_type}"`) with logic
      implementing D2's two forms:
      - unqualified: `f"pr-{self._record.number}-review.{review_type}"`
      - qualified: `f"pr-{self._record.number}-review.{review_type}.{self._record.owner}-{self._record.repository}"`
      choosing based on `self._qualify`.
- [ ] Do not touch `PullRequestRecord.path_key` or `.key` in
      [src/squadron/codehost/models.py](src/squadron/codehost/models.py) in
      this task — that's Task D.1.
- [ ] Update every call site that constructs `PrTarget(...)` in
      `review_pr.py` to pass `qualify=`. At this point in the sequence there
      is exactly one call site (line 471,
      `PrTarget(resolved.record, rules_source)`, inside `_resolve_save_outcome`'s
      `target=` argument) — Task B.3 changes what value it passes; for this
      task it's acceptable to pass a literal placeholder if needed to keep
      the type checker green, but prefer doing Task B.1–B.3 together in one
      commit since they're tightly coupled.

### Task B.2 — Update `PrTarget` stem tests

- [ ] Effort: 2/5
- [ ] In `tests/cli/test_review_pr_persistence.py`, update every test that
      constructs a `PrTarget` and asserts on `filename_stem` to pass
      `qualify=` explicitly and to expect the new stem forms. Known
      locations to change (line numbers as of design time — verify against
      current file before editing):
      - `test_stem_is_pr_keyed_with_no_slice_segment` (~line 59): expect
        `"github.com-ecorkran-squadron-83-review.code"` → new value depends
        on the `qualify` you pass; add cases for both `qualify=True` and
        `qualify=False` if the existing test only covers one.
      - `test_stem_carries_no_character_a_path_cannot` (~line 62)
      - `test_stem_never_begins_with_a_digit` (~line 74) — still true under
        the new `pr-` prefix; keep the assertion, update the constructed
        stem's expected shape only if the test hardcodes it.
      - `test_stem_varies_only_by_review_type` (~line 175): update the
        expected f-string.
- [ ] Add new tests (do not replace, add) covering:
      - `qualify=False` → stem is exactly `pr-{number}-review.{type}` with
        no owner/repo segment.
      - `qualify=True` → stem is exactly
        `pr-{number}-review.{type}.{owner}-{repository}`.
- [ ] Run: `pytest tests/cli/test_review_pr_persistence.py -x`.

### Task B.3 — Reorder `review_pr` to resolve the directory first

- [ ] Effort: 2/5
- [ ] In [src/squadron/cli/commands/review_pr.py](src/squadron/cli/commands/review_pr.py),
      move the `resolve_reviews_dir(...)` call (currently inside `_save_pr`,
      lines 439–445) to run **before** `PrTarget(...)` is constructed
      (currently line 471). `resolve_reviews_dir` only reads config and
      checks `is_dir()` (per D-notes in `reviews_dir.py`'s own docstring), so
      this is side-effect free even on a `--no-save` run.
- [ ] Pass `qualify=not rule.repository_scoped` into the `PrTarget(...)`
      construction at (what is currently) line 471.
- [ ] Update `_save_pr` (lines 432–464) to take the pre-resolved
      `reviews_dir` and `rule` as parameters (closure capture or explicit
      args — match the existing style of nested functions in this file)
      instead of calling `resolve_reviews_dir` itself.
- [ ] Verify no behavior change to the printed "Saved review to … (<rule>)"
      line (line 463) or the `OSError` failure path (lines 457–462).

### Task B.4 — Persistence/CLI test for the reordering

- [ ] Effort: 2/5
- [ ] In `tests/cli/test_review_pr_persistence.py`, add or extend a
      CLI-level test (using the existing `CliRunner` + faked code host
      pattern already in this file) that runs `sq review pr` against:
      - a project-scoped reviews directory (`PROJECT` rule) → asserts the
        saved file is named `pr-{number}-review.code.md` with no
        owner/repo segment.
      - `--reviews-dir <tmp>` (`FLAG` rule) → asserts the saved file is
        named `pr-{number}-review.code.{owner}-{repository}.md`.
- [ ] Run: `pytest tests/cli/test_review_pr_persistence.py -x`.

---

## Part C — Preserve old-name fixtures (D6)

### Task C.1 — Confirm and widen `test_review_consumers_ignore_pr.py`

- [ ] Effort: 1/5
- [ ] Read `tests/review/test_review_consumers_ignore_pr.py`. Confirm it
      builds a `github.com-…` fixture artifact on purpose (per D6/Migration
      Plan). **Do not rename this fixture or the file.**
- [ ] Add a second case (parametrize or a sibling test) using a `pr-…`
      fixture artifact, asserting the same "consumers ignore this, it's not
      a slice review" behavior holds for the new name too.
- [ ] Widen the docstring: change any language describing the fixture stem
      as "beginning `github.com-`" to describe it generically as "any
      non-numeric stem."
- [ ] Run: `pytest tests/review/test_review_consumers_ignore_pr.py -x`.

### Task C.2 — Confirm untouched: remaining D6 fixture files

- [ ] Effort: 1/5
- [ ] Read `tests/documents/test_pr_review_frontmatter.py` and
      `tests/review/test_pr_artifact_is_target_agnostic.py`. Confirm both
      build `github.com-…` fixtures as deliberate old-name coverage per D6.
- [ ] Make no changes to either file. If either test fails after Parts A/B's
      changes, that is a signal something in Parts A/B broke old-name
      artifact compatibility — stop and re-check against D6 rather than
      editing these fixtures to make them pass.
- [ ] Run: `pytest tests/documents/test_pr_review_frontmatter.py tests/review/test_pr_artifact_is_target_agnostic.py -x`.

---

## Part D — `path_key` docstring and metrology message

### Task D.1 — Update `path_key`'s docstring

- [ ] Effort: 1/5
- [ ] In [src/squadron/codehost/models.py](src/squadron/codehost/models.py),
      update `path_key`'s docstring (currently lines 57–65). It currently
      claims two consumers (worktree directory and review artifact
      filename) sharing "one definition." Change it to name **one**
      consumer — the scratch worktree directory
      (`ScratchWorktree.__enter__`) — and state that the PR review artifact
      deliberately stopped using it as of slice 926, so a future reader does
      not "fix" the divergence back.
- [ ] Do not change `path_key`'s implementation (line 65,
      `self.key.replace("/", "-").replace("#", "-")`) — only the docstring.
- [ ] Confirm `ScratchWorktree.__enter__` is still the only remaining
      consumer of `path_key` (grep for `path_key` across `src/`) before
      writing the docstring's consumer claim.

### Task D.2 — Metrology `resolve_target` error message

- [ ] Effort: 1/5
- [ ] In [src/squadron/metrology/capture.py](src/squadron/metrology/capture.py),
      update the `MetrologyTargetError` message in `resolve_target` (lines
      89–93) from:
      `f"Target {target!r} is neither an existing review file nor a slice index. Pass a review-file path, or an index with --type."`
      to state that PR reviews are always addressed by path, per D4:
      `f"Target {target!r} is neither an existing review file nor a slice index. Pass a review-file path (PR reviews are always addressed by path), or a slice index with --type."`
- [ ] This is a message-only change — `resolve_target`'s behavior is
      unchanged (a digit-index lookup never matched a PR review artifact
      under the old name either, per D4).

### Task D.3 — Test the new metrology message

- [ ] Effort: 1/5
- [ ] Find or create the test covering `resolve_target`'s non-digit,
      non-path refusal (check `tests/metrology/` for an existing test
      exercising this branch before adding a new one).
- [ ] Assert the error message contains "PR reviews are always addressed by
      path".
- [ ] Run: `pytest tests/metrology/ -k resolve_target -x`.

---

## Part E — Discovery glob pinning test (D5)

### Task E.1 — Add the glob-pinning test

- [ ] Effort: 1/5
- [ ] In `tests/pr/` (check for an existing test file covering
      [src/squadron/pr/inputs.py](src/squadron/pr/inputs.py)'s discovery
      glob at line 147, `reviews_dir.glob("*-review.*.md")` — likely
      `tests/pr/test_inputs.py` or similar; create one if none exists),
      add a test that creates three files in a temp directory:
      - `pr-83-review.code.md` (new unqualified form)
      - `pr-83-review.code.ecorkran-squadron.md` (new qualified form)
      - `github.com-ecorkran-squadron-83-review.code.md` (old form)
      and asserts `Path(tmpdir).glob("*-review.*.md")` matches all three.
- [ ] This is a regression pin per D5: the slice plan wrongly assumed this
      glob needed a change. It doesn't. This test exists so a future glob
      tightening fails loudly instead of silently breaking PR review
      discovery.
- [ ] Run: `pytest tests/pr/ -k glob -x`.

---

## Part F — Documentation

### Task F.1 — Update `docs/COMMANDS.md`

- [ ] Effort: 1/5
- [ ] In `docs/COMMANDS.md`, find the `sq review pr` section and add or
      update text naming both artifact forms
      (`pr-{number}-review.{type}.md` and
      `pr-{number}-review.{type}.{owner}-{repo}.md`) and stating plainly
      when the qualifier appears: only when the reviews directory could
      hold more than one repository's reviews (`--reviews-dir` or
      `review.external_reviews_dir`), never for the project directory or
      the built-in default.

### Task F.2 — Upstream conventions edit (D7)

- [ ] Effort: 1/5
- [ ] This edit lands in a **different repository**:
      `/Users/manta/source/repos/manta/ai-project-guide/file-naming-conventions.md`.
      Do not hand-edit squadron's installed copy under
      `project-documents/ai-project-guide/`.
- [ ] In that repo's `file-naming-conventions.md`, find the "Pull-Request
      Reviews" section. Update it to describe both name forms, D1's rule
      table (one line per rule: PROJECT/DEFAULT unqualified,
      CONFIG/FLAG qualified), and replace the old host-prefix reference in
      the "non-numeric prefix is load-bearing" paragraph with the `pr-`
      prefix.
- [ ] Commit this change in the `ai-project-guide` repo, separately from
      squadron's commits for this slice. Per D7, squadron's installed copy
      lags until the next guide update pulls it in — that's expected, not a
      bug to fix here.

---

## Part G — Full verification

### Task G.1 — Full suite, lint, typecheck

- [ ] Effort: 1/5
- [ ] From the squadron repo root: `ruff format && ruff check && pyright`.
      Zero pyright errors — merge blocker per project rules.
- [ ] Run the full test suite: `pytest`. All green.

### Task G.2 — Manual verification walkthrough

- [ ] Effort: 2/5
- [ ] Follow the design's Verification Walkthrough section exactly (design
      doc, "Verification Walkthrough", using PR 116 or any real merged PR
      number):
      1. `sq review pr 116 --no-tools` from the squadron checkout → confirm
         stderr ends with
         `Saved review to .../project-documents/user/reviews/pr-116-review.code.md (project reviews directory)`,
         and `pr:` frontmatter still names `github.com`/`ecorkran`/`squadron`/`116`.
      2. `sq review pr 116 --no-tools --reviews-dir /tmp/sq-926` → confirm
         `/tmp/sq-926/pr-116-review.code.ecorkran-squadron.md` exists and
         stderr names `(--reviews-dir)`.
      3. Re-run step 1 without `--no-tools` → confirm the printed
         `worktree:` path still ends `github.com-ecorkran-squadron-116-<run_id>`
         (path_key unchanged).
      4. `sq metrology sample pr-116` → refuses with the D4 message.
         `sq metrology sample project-documents/user/reviews/pr-116-review.code.md` →
         resolves.
      5. `pytest tests/pr -k glob` passes for both forms.
      6. Clean up the step-1 artifact (`git checkout` or `rm`) unless
         intentionally kept.
- [ ] Note any deviation from the design's expected output as a finding,
      not a silent adjustment — if something doesn't match, stop and
      report before proceeding.

### Task G.3 — Commit

- [ ] Effort: 1/5
- [ ] `git add` and commit from the squadron project root, per project
      Source Control rules. Use a `fix:` prefix (this closes issue #124),
      e.g. `fix: shorten PR review artifact name, drop host/owner/repo prefix`.
- [ ] Confirm current working directory before running git commands.

---

## Completion

- [ ] Mark this task file's `status:` as `complete` in frontmatter once all
      parts are done (or delegate to `task-checker`).
- [ ] Mark the slice design's `status:` as `complete` in
      [926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md](project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md)
      frontmatter.
- [ ] Update the slice plan entry (900-slices.maintenance-and-refactoring.md,
      entry 24 / index 926) checkbox to `[x]`.
- [ ] Write a DEVLOG entry per `prompt.ai-project.system.md`, Session State
      Summary guidance, dated 20260925 (or the actual completion date),
      noting the slice closed issue #124 and the D5 glob correction.
