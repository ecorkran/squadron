---
docType: tasks
slice: review-resolution-recording-that-findings-were-addressed
project: squadron
lld: user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md
dependencies: [305]
projectState: >
  File 1 of 2 for slice 306 (initiative 300, eval-actions / LLM-as-judge).
  Covers Part 0 (relocation), Part A (reviewedSha stamp), and Part D
  (overwrite guard) — T1–T14. Parts B–C and Closeout (T15–T40) continue in
  306-tasks.review-resolution-recording-that-findings-were-addressed-2.md.
  Slice 305 is merged and its code review resolved: the findings-addressed
  gate policy ships in pipeline/actions/findings_addressed/ (models,
  screens, parsing, judge, verification, evidence, policy), reachable only
  from inside a pipeline loop. This slice makes the same per-finding
  derivation invocable interactively via `sq review resolve`, persisting a
  versioned resolution artifact beside the review — never inside it. The
  slice design review (306-review.slice...) returned CONCERNS; all four
  concerns were resolved by design edits before this breakdown started,
  most significantly F002: the context-free core (models, parsing,
  verification, extracted judge transport) relocates into a new
  `review/addressed/` package rather than being imported across the
  pipeline→review boundary. Phase 6 has not started; no branch exists for
  306.
dateCreated: 20260803
dateUpdated: 20260803
status: complete
---

## Context Summary

- Working on the **review-resolution** slice (306) under initiative 300,
  directly following 305. Where 305 answers "were the prior round's findings
  addressed?" *inside a loop*, 306 answers the same question *interactively*,
  for a review run outside any pipeline — `sq review code 305` fails, you fix
  it by hand, then `sq review resolve 305` tells you, with evidence, whether
  you actually addressed it.
- **The governing constraint:** agents stay barred from editing `verdict:` on
  a review file. Resolution is a **second assertion in a second artifact**
  (`resolution: ADDRESSED|UNADDRESSED|UNKNOWN`, never named `verdict:`),
  derived — never declared — by the same discipline 305 established: screens
  first, judge only over what remains, claims verified against the diff
  before being trusted, `UNKNOWN` evaluated before failure.
- **This file (1 of 2) is infrastructure that Part B (file 2) depends on.**
  Part 0 relocates the context-free core to `review/addressed/` — every task
  in file 2 imports from there. Part D fixes a live data-loss bug
  independently of Part B and should land regardless of when file 2 starts.
- **F002 reshapes the file layout.** A new package `review/addressed/`
  (models, parsing, verification, and a context-free judge-transport core)
  is *relocated* out of `pipeline/actions/findings_addressed/`, not
  duplicated. `pipeline/actions/findings_addressed/` keeps only what is
  loop-specific — `screens.py`, `evidence.py`, `policy.py` — and its
  `judge.py` becomes a thin `ActionContext`-resolving wrapper over the moved
  core.
- **One failure-closed rule covered in this file (F003 from the design
  review) must not be treated as optional polish:** a failed archive copy
  aborts the overwrite rather than proceeding (T13/T14). The remaining two
  design-review rules (F001, F004) live in file 2's Part B.
- Read the slice design (all sections) before starting, especially Decisions
  1–7 and the Data Flow diagram — this breakdown implements that diagram
  node by node and does not restate its reasoning.
- **cf coordination checklist item (design review F005, binding):** T12
  below verifies whether Context Forge's artifact scanning recurses into
  `project-documents/user/reviews/archive/`, and is placed **before** the
  archive-guard implementation (T13/T14) so the gating is structural rather
  than a note asking the implementer to check back later.

### Test-with discipline for this breakdown

Every implementation task in this file is immediately followed by its test
task. Part 0 (relocation) is verified by re-running 305's existing suite
unchanged — no new tests are written for code that only moved.

---

## Part 0 — Relocate the context-free core to `review/addressed/`

- [x] **T1. Create the `review/addressed/` package and move `models.py`**
  - [x] Create `src/squadron/review/addressed/__init__.py` (empty for now;
        populated by T7).
  - [x] Move `src/squadron/pipeline/actions/findings_addressed/models.py` to
        `src/squadron/review/addressed/models.py` verbatim — no logic
        changes, only the file's own internal imports if any reference
        sibling modules by full path.
  - [x] Update every importer found by
        `grep -rln "findings_addressed.models\|findings_addressed import" src tests`
        to import from `squadron.review.addressed.models` instead. Expected
        importers: `findings_addressed/__init__.py`, `evidence.py`,
        `judge.py`, `parsing.py`, `policy.py`, `screens.py`,
        `verification.py`, and the four `tests/pipeline/test_findings_addressed*.py`
        files.
  - Effort: 2/5

- [x] **T2. Verify T1 — full findings-addressed suite passes unchanged**
  - [x] Run `uv run pytest tests/pipeline/test_findings_addressed.py tests/pipeline/test_findings_addressed_e2e.py tests/pipeline/test_findings_addressed_evidence.py tests/pipeline/test_findings_addressed_judge.py tests/metrology/test_capture_discovery.py -q`
        — all pass, same count as before the move.
  - [x] `uv run pyright` — zero errors (import-path updates are the only
        change; strict mode must not regress).
  - **NOTE:** this is a *focused* subset, not the full-suite check — it
        confirms this move did not break the findings-addressed package's
        own tests, but a regression in an importer outside this subset
        (elsewhere in `src`/`tests`) will not surface until T8's
        `uv run pytest -q`. Commit here regardless; T8 is the full-suite
        gate for all of Part 0.
  - Commit: `refactor: relocate findings-addressed models to review/addressed/`
  - Effort: 1/5

- [x] **T3. Move `parsing.py` and `verification.py` to `review/addressed/`**
  - [x] Move `parsing.py` and `verification.py` verbatim into
        `review/addressed/`. `verification.py` already imports
        `squadron.review.parsers.location_path` and
        `squadron.review.models.Verdict` — both already in the target
        package, so this move *removes* a cross-package import rather than
        adding one.
  - [x] `verification.py`'s import of `RoundDiff` from
        `pipeline.actions.findings_addressed.screens` stays as a
        cross-package import in the pipeline→review direction (screens is
        loop-specific and stays put per the design) — update the import path
        accordingly, do not move `screens.py`.
  - [x] Update all importers (same grep pattern as T1, rerun after T1's
        edits).
  - Effort: 2/5

- [x] **T4. Verify T3 — full findings-addressed suite passes unchanged**
  - [x] Same command as T2. All pass, same count.
  - [x] `uv run pyright` — zero errors.
  - **NOTE:** same caveat as T2 — this is the focused subset, not the
        full-suite gate. T8 is what confirms this commit did not regress
        anything outside the findings-addressed package.
  - Commit: `refactor: relocate findings-addressed parsing and verification to review/addressed/`
  - Effort: 1/5

- [x] **T5. Extract the context-free judge-transport core into `review/addressed/judge.py`**
  - [x] In the new `review/addressed/judge.py`, define
        `judge_residue_core(residue, fresh_findings, diff, *, model_id,
        profile, cwd) -> JudgeLegResult` — the body of today's
        `judge_residue` from `_resolve_model` onward (template load,
        `run_review_with_profile` call, parse, `is_parse_failure` check),
        taking resolved `model_id`/`profile` as parameters instead of an
        `ActionContext`. `JudgeLegResult`, `JUDGE_TEMPLATE_NAME`,
        `_render_findings` move here too — they are used only by this logic.
  - [x] In `pipeline/actions/findings_addressed/judge.py`, keep
        `_resolve_model(context, template_model)` (it is genuinely
        `ActionContext`-coupled — reads `context.params`, `context.resolver`)
        and rewrite `judge_residue(context, ...)` as a thin wrapper: resolve
        model/profile via `_resolve_model`, then call
        `judge_residue_core(...)` and return its result.
  - [x] `JUDGE_BLOCK_PARAM` stays in the pipeline module — it names a
        `context.params` key, which is pipeline-specific.
  - Effort: 3/5

- [x] **T6. Verify T5 — judge-leg behavior is unchanged through the wrapper**
  - [x] Run `tests/pipeline/test_findings_addressed_judge.py` and
        `tests/pipeline/test_findings_addressed_e2e.py` — all pass unchanged;
        these are the tests that exercise `judge_residue` end to end through
        `ActionContext`, so an unchanged pass here is the proof the
        extraction preserved behavior.
  - [x] Confirm no test needed rewriting to pass (if one did, the extraction
        changed behavior — stop and reconcile with the design before
        continuing).
  - **NOTE:** same caveat as T2/T4 — these two files are the tests that
        specifically exercise `judge_residue`, not the full suite. Their
        unchanged pass is the proof this extraction preserved behavior for
        the judge leg specifically; T8 remains the gate for the whole
        project.
  - Commit: `refactor: extract context-free judge-transport core to review/addressed/judge.py`
  - Effort: 1/5

- [x] **T7. Update package `__all__` exports and docstrings**
  - [x] `review/addressed/__init__.py` exports the moved public names
        (mirroring the removed entries from
        `pipeline/actions/findings_addressed/__init__.py`'s `__all__`):
        `FindingRecord`, `FindingOutcome`, `FindingStatus`, `SettlingScreen`,
        `CONCERN_PLUS_SEVERITIES`, `concern_plus`, `read_findings`,
        `JudgeStatus`, `is_parse_failure`, `parse_status_lines`,
        `statuses_to_outcomes`, `derive_addressed_verdict`,
        `verify_outcomes`, `JudgeLegResult`, `JUDGE_TEMPLATE_NAME`,
        `judge_residue_core`.
  - [x] `pipeline/actions/findings_addressed/__init__.py`'s `__all__` drops
        the names that moved and re-exports nothing it no longer defines —
        importers outside the package that used the old path are updated,
        not shimmed (no backwards-compat re-export; this is a pre-release
        internal reorganization).
  - [x] Module docstring at the top of
        `pipeline/actions/findings_addressed/__init__.py` updated to
        describe the narrowed scope (screens, evidence, policy — the
        loop-specific layer) and points to `review.addressed` for the
        shared vocabulary.
  - Effort: 1/5

- [x] **T8. Verify T7 — full project suite and lint pass**
  - [x] `uv run pytest -q` — full suite passes, same pass count as slice 305's
        close-out baseline (2832 passed, 2 skipped) plus this slice's later
        additions.
  - [x] `uv run ruff check src tests` — clean.
  - [x] `uv run pyright` — zero errors.
  - Commit: `refactor: finalize review/addressed/ exports, narrow findings_addressed scope`
  - Effort: 1/5

---

## Part A — `reviewedSha` stamp at review-authoring time

- [x] **T9. Add `reviewed_sha` to `format_review_markdown`**
  - [x] In `src/squadron/review/persistence.py`, add an optional
        `reviewed_sha: str | None = None` parameter to
        `format_review_markdown`. When not `None`, emit
        `reviewedSha: {reviewed_sha}` in frontmatter, placed after
        `dateUpdated:` (matching the existing ordering convention of
        metadata-then-content fields).
  - [x] Absent (`None`) → key omitted entirely, not emitted as `null` — a
        review authored before this slice, or one authored where git was
        unavailable, must not carry a fabricated placeholder.
  - Effort: 1/5

- [x] **T10. Wire `reviewed_sha` through both persistence callers**
  - [x] `review/persistence.save_review_result` (the CLI path): resolve HEAD
        via `run_git(["rev-parse", "HEAD"], cwd=...)` from
        `review.git_utils`; on success pass the trimmed SHA as
        `reviewed_sha`; on `None`/non-zero return, omit the argument and log
        a WARNING naming that the stamp could not be written (never fall
        back to a placeholder like `"unknown"`).
  - [x] `pipeline/actions/review.py` (the pipeline-action path): same
        resolution and same fallback behavior — interface parity between CLI
        and pipeline-authored reviews is a standing project rule.
  - Effort: 2/5

- [x] **T11. Test — `reviewedSha` is stamped, or absent, correctly**
  - [x] Unit test on `format_review_markdown`: `reviewed_sha="abc123"`
        produces a frontmatter line `reviewedSha: abc123`; `reviewed_sha=None`
        produces no such line at all (assert the key is absent from parsed
        frontmatter, not merely falsy).
  - [x] Integration test on `save_review_result` (or the pipeline review
        action, whichever is more directly testable) against a real git repo
        fixture: the saved file's frontmatter `reviewedSha` equals
        `git rev-parse HEAD` at save time.
  - [x] Test the git-unavailable path (mock `run_git` returning `None`): the
        saved file has no `reviewedSha` key and a WARNING is logged — reuse
        the existing `caplog` idiom from the 305 test suite.
  - [x] **Findings round-trip test (binding — this is the only place in
        file 1 that verifies the shape file 2's `records_from_frontmatter`
        depends on):** build a `ReviewResult` with several
        `ReviewFinding`s covering multiple severities, render it through
        the real `format_review_markdown` (with the new `reviewed_sha`
        parameter set), parse the frontmatter back out with
        `yaml.safe_load`, and assert the `findings:` block's shape is
        exactly what it was before this task's changes — same keys
        (`id`, `severity`, `category`, `summary`, `location`), same
        lowercase severity values. This task changes
        `format_review_markdown`; if it inadvertently altered how findings
        serialize, file 2's frontmatter reader would silently break
        against real artifacts with no test anywhere catching it (per the
        305 F001/F002 lesson: a hand-rolled fixture would not have caught
        F001 either). Confirming here — at the point of the change — is
        cheaper than discovering it while implementing file 2.
  - Commit: `feat: stamp reviewedSha into review frontmatter at authoring time`
  - Effort: 2/5

---

## Part D — Overwrite guard

- [x] **T12. Verification checkpoint — cf archive-scanning (design review F005, blocking)**
  - [x] Determine how Context Forge's artifact/review scanning enumerates
        `project-documents/user/reviews/` — check whether it globs
        non-recursively (matching squadron's own
        `discover_judge_results`, `reviews_dir.glob("*-review.*")`,
        verified non-recursive) or walks recursively. Consult
        `ai-project-guide/tool-guides/context-forge/` first; if the guide
        does not answer this, ask the Project Manager directly rather than
        guessing — this is exactly the class of external-tool fact the
        project's "do not guess or assume" rule exists for.
  - [x] **If non-recursive (expected, matching squadron's own pattern):**
        no further action needed for the archived filename — record the
        finding in this task's checkbox notes and proceed to T13 as
        written below.
  - [x] **If recursive:** the archived filename must not match whatever
        pattern cf keys on. Apply the design's stated fallback — strip or
        alter the `-review.` segment in the archived copy's filename (e.g.
        `{original}.archived` suffix, or replace `-review.` with
        `-archived.`) — and incorporate that filename scheme into T13/T14
        below as written, before either is implemented.
  - [x] This task is placed **before** T13/T14 (rather than after, as an
        earlier draft of this file had it) precisely so the gating is
        structural: whoever picks up T13 already knows the answer this
        task produces, instead of discovering a rework requirement after
        implementing against the wrong assumption.
  - Effort: 1/5
  - **Finding:** Context Forge's review scanning is NON-RECURSIVE. Verified against context-forge v0.10.7 source (the installed `cf` binary is the same version): `ProjectModelBuilder.scanDirectory`, `parsers/documentDetector.detectDocuments`, and `ConsistencyChecker.discoverAllDocuments` all call `readdir(dir)` with no options and then skip any entry not ending in `.md`; `reviews/archive/` is a directory and is never descended into. The only `recursive: true` calls in cf are `mkdir`/`rmSync`. Conclusion: the archived copy keeps its ORIGINAL filename — no mangling needed.

- [x] **T13. Add archive-on-overwrite to `save_review_file`, fail-closed**
  - [x] In `review/persistence.py`, before `save_review_file` writes to an
        existing `path`: copy the existing file's current bytes to
        `project-documents/user/reviews/archive/{original filename}`
        (`mkdir(parents=True, exist_ok=True)` on the archive dir first).
  - [x] **Verify the copy before proceeding**: read back the archived file
        and compare its bytes (or size, at minimum) to the original. If the
        copy cannot be created, or verification fails, **abort the
        overwrite**: log an ERROR naming both the original path and the
        attempted archive path, return `None` (matching the function's
        existing failure-return contract), and do not call `write_text` on
        the original. This is the fail-closed requirement from design review
        F003 — a guard that proceeds after a failed copy destroys exactly
        the content it exists to protect.
  - [x] When no file exists at `path` yet (first-time save), skip archiving
        entirely and write directly — no behavior change for the common
        case.
  - [x] Log a WARNING (not ERROR) on the success path naming the file that
        was archived, so an overwrite is visible in normal operation even
        when nothing failed.
  - [x] Use the archived-filename scheme T12 settled — plain
        `{original filename}` if T12 found non-recursive scanning, or T12's
        mangled scheme if it found recursive scanning. T12 must be complete
        before this task starts.
  - Effort: 2/5
  - **Scope decision (approved by Project Manager):** `sq review code <N>` persists via `save_review_result`, not `save_review_file`, so the guard was implemented ONCE as a shared helper `archive_existing_review(path) -> bool` in `review/persistence.py` and called from BOTH `save_review_file` (returns None on failure, existing contract) and `save_review_result` (raises OSError on failure, since its signature returns Path). The CLI gained a `_save_and_report` helper in `cli/commands/review.py` so the refusal prints an error instead of a traceback. Without this, the slice's own success criterion ("re-running `sq review code <N>` over an edited review file archives the prior content and warns") would have gone unmet.

- [x] **T14. Test — overwrite guard preserves content and fails closed**
  - [x] Test: save a review, hand-edit the saved file (append a marker
        string), save again over the same path — assert the archived copy in
        `archive/` contains the marker string byte-for-byte, and the new
        content is what was just saved to the original path.
  - [x] Test: make the archive directory unwritable (existing project idiom
        — a file where the directory should be, as used in
        `test_findings_addressed_evidence.py`'s
        `test_unwritable_reviews_directory_warns_and_returns_none`) — assert
        `save_review_file` returns `None`, the original file's content is
        **unchanged** from before the attempted overwrite, and an ERROR is
        logged. This covers the copy-cannot-be-created failure mode.
  - [x] Test the **second** failure mode T12 enumerates — copy succeeds but
        read-back verification fails: mock or monkeypatch the verification
        step (e.g. the read-back comparison) to report a mismatch after a
        real, successful copy — assert the overwrite is still aborted,
        `save_review_file` returns `None`, the original file is unchanged,
        and an ERROR is logged. Do not treat the unwritable-directory test
        above as covering this case — a successful copy that fails
        verification is a distinct code path from a copy that never
        happened.
  - [x] Test: saving to a path with no pre-existing file writes directly,
        with no archive directory created as a side effect.
  - Commit: `fix: archive prior review content before overwrite, fail closed on archive failure`
  - Effort: 2/5

---

## Handoff to file 2

Parts 0/A/D complete and verified (T8's full-suite pass, T12's cf-scanning
answer known) is the entry condition for
`306-tasks.review-resolution-recording-that-findings-were-addressed-2.md`,
which builds `sq review resolve` (Part B) and its documentation (Part C) on
top of the relocated `review/addressed/` package.
