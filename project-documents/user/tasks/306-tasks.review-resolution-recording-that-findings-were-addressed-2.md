---
docType: tasks
slice: review-resolution-recording-that-findings-were-addressed
project: squadron
lld: user/slices/306-slice.review-resolution-recording-that-findings-were-addressed.md
dependencies: [305]
projectState: >
  File 2 of 2 for slice 306 (Parts B–C, T15–T40); Parts 0/A/D (T1–T14)
  are in 306-tasks.review-resolution-recording-that-findings-were-addressed-1.md
  and must be complete before starting here — T15 onward assumes
  `review/addressed/` exists (Part 0) and imports from it, and Part D's
  overwrite guard (T13/T14, gated by T12's cf-scanning check) is
  independent but should already be merged.
dateCreated: 20260803
dateUpdated: 20260803
status: complete
---

## Context Summary

- This file continues file 1's breakdown of slice 306. See file 1's Context
  Summary for the full governing constraints (derived-not-declared,
  `resolution:` never named `verdict:`, the review file is never touched).
- **Prerequisite: Part 0 must be complete.** Every task below imports from
  `review/addressed/` (models, parsing, verification, judge core) as
  relocated by file 1's T1–T8. If that package does not yet exist, stop and
  complete file 1 first.
- Part B builds `sq review resolve` end to end, task by task, following the
  slice design's Data Flow diagram node for node: locate → load →
  verdict-consistency screen → diff-base resolve → diff compute →
  empty/git-failure screen → judge leg → verify → derive → render → save →
  CLI → slash command. Part C documents the contract. Closeout verifies the
  whole slice against its own success criteria.
- **Three design-review-added rules land here, not in file 1:** the
  verdict-consistency screen (T23/T24, F001), the judge-leg failure modes
  and injection cap (T25/T26, F004), and the untouched-path claim
  verification (T27/T28, reused from 305 but newly exercised on this path).
  Each has its own dedicated test task — do not merge them into a general
  "error handling" task.

---

## Part B — `sq review resolve` command

- [x] **T15. `records_from_frontmatter` — read a review file's findings**
  - [x] In `review/addressed/models.py`, add
        `records_from_frontmatter(findings: list[dict]) -> list[FindingRecord]`
        that reads the *exact* shape `format_review_markdown` writes into
        frontmatter (`id`, `severity` — already lowercase in this shape,
        unlike the `ActionResult.findings` shape `read_findings` consumes —
        `category`, `summary`, `location`). Reuse `_as_severity` for
        normalization consistency even though this source is already
        lowercase, so both readers share one normalization path. Missing
        required fields → `malformed=True`, logged at WARNING, kept as
        residue — same rule as `read_findings`, not a new one.
  - [x] This is a **second reader**, not a change to `read_findings` (which
        reads `ActionResult.findings`, a different shape) — do not attempt
        to unify the two call signatures; document the shape difference in
        the docstring instead, citing 305 F002 (fixtures must match the
        real producer shape) as the reason two readers exist rather than one
        lenient one.
  - [x] File 1's T11 already pinned that `format_review_markdown` emits this
        shape unchanged after the `reviewedSha` addition — if that task's
        round-trip assertion needed adjusting to pass, re-read this shape
        assumption before writing this reader; do not silently reconcile a
        shape mismatch by loosening this function instead.
  - Effort: 2/5

- [x] **T16. Test — `records_from_frontmatter` against a real rendered review**
  - [x] Build a `ReviewResult` with mixed-severity `ReviewFinding`s, render it
        through the real `format_review_markdown`, parse the YAML
        frontmatter back out with `yaml.safe_load`, and pass its `findings`
        list to `records_from_frontmatter` — assert the CONCERN+ subset
        matches what went in. This is the round-trip test the F001/F002
        lesson demands: parse what the real writer produces, not a hand-built
        fixture.
  - [x] Test a finding dict missing `location` → `malformed=True`, kept, not
        dropped.
  - Commit: `feat: add records_from_frontmatter reader for review-file findings`
  - Effort: 1/5

- [x] **T17. `review/resolution.py` — locate review, resolve type, load findings**
  - [x] New module `review/resolution.py`. Function
        `locate_review(index: int, review_type: str | None, cwd: str) ->
        Path` — with `review_type` given, exact path match (error if
        missing); with `review_type=None`, glob
        `{index}-review.*.md` non-recursively in the reviews dir: exactly one
        match → use its type (parsed from the filename); zero matches →
        error naming the index; more than one → error listing every matched
        filename (never guess, per the design's stated rule).
  - [x] Function `load_review(path: Path) -> tuple[frontmatter dict, verdict,
        list[FindingRecord]]` parsing the target file's YAML frontmatter with
        `yaml.safe_load`, extracting `verdict`, `reviewedSha` (may be
        absent), and findings via T15's reader.
  - Effort: 2/5

- [x] **T18. Test — locate and load, including the ambiguous-type case**
  - [x] Test: single review file for an index → `review_type=None` resolves
        it correctly.
  - [x] Test: two review files for the same index (e.g. `code` and `tasks`,
        matching 305's real on-disk state) with `review_type=None` → raises
        an error whose message lists both filenames.
  - [x] Test: explicit `review_type` that does not exist on disk → error
        naming the expected path, not a silent empty result.
  - Commit: `feat: add review/resolution.py review-location and load logic`
  - Effort: 1/5

- [x] **T19. Diff-base resolution — `reviewedSha`, file-history fallback, `--since`**
  - [x] Function `resolve_diff_base(frontmatter: dict, review_path: Path, *,
        since: str | None, cwd: str) -> tuple[str | None, str]` returning
        `(sha_or_ref, source)` where `source` is one of `"frontmatter"`,
        `"file-history"`, `"since"`.
  - [x] `since` given → always wins, `source="since"`, no git calls to
        determine the base (the caller still needs `run_git` to validate the
        ref resolves, per the next bullet).
  - [x] Otherwise: `frontmatter["reviewedSha"]` present → use it,
        `source="frontmatter"`. Absent → fallback via
        `run_git(["log", "-1", "--format=%H", "--", str(review_path)],
        cwd=cwd)`, `source="file-history"`, with a WARNING naming that the
        fallback was used and why (no stamp present).
  - [x] If the resolved ref does not exist in the repo (bad `--since`, or a
        file-history query on an unmanaged path) — `run_git` returns
        non-zero or `None` — this is a git-failure state, handled by T21, not
        here; this function returns what it resolved and lets the caller
        classify success/failure when it actually runs the diff.
  - Effort: 2/5
  - Note: The function was named `resolve_review_diff_base`, not `resolve_diff_base`, to avoid collision with `squadron/review/git_utils.py`'s existing `resolve_diff_base` (which answers a different question: which branch slice work forks from). `tests/review/conftest.py` patches the git_utils name via autouse fixture, so a duplicate would be a patch-the-wrong-one hazard.

- [x] **T20. Test — diff-base resolution precedence and fallback**
  - [x] Test: `--since` overrides a present `reviewedSha` — `source="since"`.
  - [x] Test: `reviewedSha` present, no `--since` — `source="frontmatter"`,
        exact SHA returned.
  - [x] Test: `reviewedSha` absent, no `--since` — `source="file-history"`,
        WARNING logged, SHA resolved via `git log -1`.
  - [x] Test: `--since` given **and** `reviewedSha` absent — `source="since"`,
        the given ref is used directly, and **no** file-history fallback
        WARNING is logged (a distinct fixture from the first bullet above,
        which has `reviewedSha` present: this one confirms `--since`'s
        precedence holds even when there is nothing to fall back to, not
        just when it is overriding a real value).
  - Commit: `feat: add diff-base resolution with reviewedSha and file-history fallback`
  - Effort: 1/5

- [x] **T21. Round-diff computation and empty-diff / git-failure screens**
  - [x] Function `compute_diff_since(base_ref: str, *, cwd: str) -> RoundDiff`
        (reusing the `RoundDiff` shape from `pipeline/actions/findings_addressed/screens.py`
        — import it, do not redefine it) via `run_git(["diff", base_ref,
        "HEAD", "--name-only"], cwd=cwd)` plus `run_git(["status",
        "--porcelain"], cwd=cwd)` for the working tree, unioned — mirroring
        `compute_round_diff`'s existing pattern but parameterized on an
        arbitrary base ref instead of always `HEAD`. A git failure on either
        call sets `RoundDiff.failed_command` to the exact command that
        failed (existing field, reused).
  - [x] In `resolution.py`'s orchestration: `diff.failed_command is not None`
        → `resolution=UNKNOWN`, WARNING naming the exact failed command
        (reuse the existing screen_git_failure pattern's log message shape).
  - [x] `diff.is_empty` (base..HEAD and working tree both empty against the
        CONCERN+ findings' scope) → every CONCERN+ finding `unaddressed`,
        `resolution=UNADDRESSED`, **no judge call** — mirrors 305's Screen 1
        exactly; reuse `screen_byte_identical` from
        `pipeline/actions/findings_addressed/screens.py` rather than
        reimplementing the same logic under a new name.
  - Effort: 2/5
  - Note (RoundDiff/context-free split): The `RoundDiff` question was resolved by moving the context-free pieces into `squadron/review/addressed/screens.py` — `RoundDiff`, the git measurement, `ScreenResult`, `screen_byte_identical`, `screen_git_failure` — while screen 0 (needs an iteration number) and screen 2 (needs a fresh review) stayed in the pipeline package and now import from review. This follows the design's own stated criterion for what is loop-specific, and preserves F002's direction. `compute_round_diff` became a thin wrapper over `compute_diff_since("HEAD")`; `git diff <base>` with one commit argument spans base→working tree, so the gate's failed-command string is unchanged and no 305 assertion changed (only mock target paths moved).
  - Note (review file in diff): An unanticipated gap — a review file is written *after* the commit its own `reviewedSha` names, so it always appears in its own diff. The reviews directory is therefore excluded from the measurement, or the empty-diff screen would be unreachable and every stale review would reach the judge with the review itself as its only evidence.

- [x] **T22. Test — empty diff and git-failure paths never reach the judge**
  - [x] Test with a real git fixture (following the 305 e2e pattern —
        `tmp_path` repo, real commits): no changes since `reviewedSha` →
        `resolution=UNADDRESSED`, every finding `unaddressed`,
        `screen=byte_identical`, and assert the judge transport mock was
        never called.
  - [x] Test: `run_git` failure injected (mock `run_git` to return `None` for
        the diff command) → `resolution=UNKNOWN`, WARNING logs the exact
        failed command string, judge never called.
  - Commit: `feat: add round-diff computation with empty-diff and git-failure screens`
  - Effort: 1/5

- [x] **T23. Verdict-consistency screen (design review F001, binding)**
  - [x] Before any diff work: if the CONCERN+ subset from T17's loaded
        findings is empty, branch on the *review's own recorded verdict*
        (already loaded in T17's `load_review`, not re-derived): verdict
        `PASS` → `resolution=ADDRESSED`, annotated "no CONCERN+ findings",
        zero judge calls, zero diff computation (nothing to measure against).
        Verdict `FAIL` or `CONCERNS` with zero parsed CONCERN+ findings →
        `resolution=UNKNOWN`, WARNING explicitly naming the mismatch (e.g.
        "review verdict is {verdict} but 0 CONCERN+ findings were parsed —
        treating as inconsistent evidence, not a pass"), citing the
        parser-drop lineage in the log message or a code comment (issue #28)
        so a future reader understands why this is not simplified back to
        "empty means pass."
  - [x] This check runs **before** T19–T22's diff machinery — an
        inconsistent-evidence UNKNOWN needs no diff to justify it.
  - Effort: 1/5

- [x] **T24. Test — verdict-consistency screen catches the F001 scenario**
  - [x] Test: review frontmatter `verdict: PASS`, findings list empty →
        `resolution=ADDRESSED`, no git calls made (assert via mock call
        count), no judge call.
  - [x] Test: review frontmatter `verdict: FAIL`, findings list empty (the
        exact shape a parser-drop bug like #28 would produce) →
        `resolution=UNKNOWN`, WARNING text contains both "FAIL" and a
        mismatch phrase; no judge call.
  - [x] Test: same as above with `verdict: CONCERNS` — same outcome.
  - Commit: `fix: treat empty findings against a failing review verdict as inconsistent evidence, not a pass`
  - Effort: 1/5

- [x] **T25. Judge leg over full CONCERN+ residue, with cap and transport failure handling**
  - [x] When the diff is non-empty and CONCERN+ findings exist: call
        `judge_residue_core` (from file 1's T5, `review/addressed/judge.py`)
        with residue = the **entire CONCERN+ set** (no exact-match
        pre-filter — Decision 3: no fresh review exists on this path, so
        305's Screen 2 cannot run), `fresh_findings=[]` (there is no fresh
        review's finding set to compare against on this path — document
        this explicitly in a comment, since `verify_outcomes`'s
        `MOVED`-successor check will therefore always fail to find a
        successor, which is the intended, documented Decision 3 behavior,
        not a bug).
  - [x] `--no-judge` flag → skip the judge call entirely; all residue stays
        `disputed` → `resolution=UNKNOWN` via the normal derivation (no
        special-cased short-circuit needed — this falls out of the existing
        derivation rule for free once residue is left unsettled).
  - [x] Judge transport failure (the judge core's existing `failed=True`
        path) → `resolution=UNKNOWN`, WARNING (this is 305's existing
        fail-closed behavior in `judge_residue_core`; this task is to
        confirm and test it on the new call path, not to add new logic).
  - [x] Injection-cap check: before calling the judge, measure the diff
        content (changed paths, or diff byte size — reuse whatever
        threshold/measurement 305's architecture already defines for the
        injection cap; if 305 does not enforce a cap in code today, only in
        the architecture doc's stated constraint, add the same check here
        and flag to the Project Manager that 305 may be missing the
        equivalent enforcement — do not silently add scope beyond this
        slice's boundary to fix that in 305). Over cap → `resolution=UNKNOWN`,
        WARNING naming the cap value and the resolved diff base, no judge
        call made.
  - Effort: 3/5
  - Note: Verified against source — 305 enforces `review.max_total_injection_bytes` on *file injections* only (`review/review_client.py`), and does **not** apply it to the judge's change-set input. Per T25's instruction, the cap check was added on the resolve path only, and the gap in 305 is flagged to the Project Manager rather than fixed here. Logged as issue #53 (low priority).

- [x] **T26. Test — judge leg, `--no-judge`, transport failure, and injection cap**
  - [x] Test: non-empty diff, CONCERN+ findings present, judge transport
        mocked to return `addressed` for all → `resolution=ADDRESSED`.
  - [x] Test: `--no-judge` set → `resolution=UNKNOWN`, judge transport mock
        never called.
  - [x] Test: judge transport mocked to raise → `resolution=UNKNOWN`, WARNING
        logged, matching 305's existing transport-failure test pattern from
        `test_findings_addressed_judge.py`.
  - [x] Test: diff constructed to exceed the injection cap →
        `resolution=UNKNOWN`, WARNING names the cap and the diff base used,
        judge transport mock never called.
  - Commit: `feat: add judge leg for review-resolve with cap and transport-failure handling`
  - Effort: 2/5

- [x] **T27. Claim verification and derivation — wire `verify_outcomes` and `derive_addressed_verdict`**
  - [x] Call the existing (relocated, file 1's T3) `verify_outcomes` on the
        judge's raw outcomes against the computed diff — reused verbatim, no
        new logic. `MOVED` claims always downgrade to `disputed` here (no
        fresh findings to verify a successor against, per Decision 3 — this
        falls out of the existing function's behavior when
        `fresh_findings=[]`, so this task is wiring, not new derivation
        code).
  - [x] Call `derive_addressed_verdict` on the verified outcomes for the
        final `resolution` value — reused verbatim.
  - Effort: 1/5

- [x] **T28. Test — untouched-path claims downgrade; derivation order holds**
  - [x] Test: judge claims `addressed` for a finding whose location the diff
        never touched → outcome downgraded to `disputed`,
        `resolution=UNKNOWN` (exercises the real `verify_outcomes` on this
        new call path, per the design's explicit success criterion).
  - [x] Test: judge claims `moved` with a successor id → always downgraded to
        `disputed` on this path (since `fresh_findings=[]`), confirming
        Decision 3's stated consequence holds in practice.
  - [x] Test: mixed outcomes where one is `disputed` and another is
        `addressed` → overall `resolution=UNKNOWN` (UNKNOWN evaluated before
        a would-be pass — reuses `derive_addressed_verdict`'s existing
        ordering, confirmed on this path).
  - Commit: `feat: wire claim verification and verdict derivation into review-resolve`
  - Effort: 1/5

- [x] **T29. Resolution-artifact rendering and the shared YAML-frontmatter helper**
  - [x] Extract the frontmatter-dict-to-string serialization already built
        in `pipeline/actions/findings_addressed/evidence.py` (`_yaml_safe`
        and the `yaml.safe_dump` call pattern from
        `gate_evidence_frontmatter`/`render_gate_evidence`) into a small
        shared helper — either promote `_yaml_safe` to a public function in
        a neutral location (`review/addressed/` is the natural home, since
        `evidence.py` will now import it in the pipeline→review direction
        like everything else) or leave `evidence.py`'s copy in place and add
        an equivalent in the new module if the two enum sets genuinely
        differ enough to make sharing awkward — decide based on what the
        code actually looks like once file 1's T5–T7 have landed, but do not
        hand-roll a third unescaped-string frontmatter writer (305 F005's
        lesson applies identically: notes embed arbitrary model text).
        **If promoting `_yaml_safe`, update both call sites**:
        `pipeline/actions/findings_addressed/evidence.py`'s
        `gate_evidence_frontmatter` (existing caller) and this task's own
        new `render_resolution` (below) — both must import the promoted
        version, not one importing it and the other keeping a local copy.
  - [x] Build `render_resolution(index, review_type, slice_name, project,
        review_verdict, resolution, reviewed_sha, resolved_sha, sha_source,
        judge_model, finding_statuses) -> str` producing the frontmatter
        schema exactly as specified in the slice design's "Resolution
        artifact schema" section (`docType: review-resolution`, all fields
        listed there) followed by a short human-readable body section
        listing each finding's status, mirroring `render_gate_evidence`'s
        body-section shape.
  - Effort: 2/5
  - Note: `_yaml_safe` was promoted out of `evidence.py` to `squadron/documents/frontmatter.py` as public `yaml_safe`, together with `render_frontmatter_block`; both call sites updated. `evidence.py`'s duplicate reviews-dir constant now points at `persistence.REVIEWS_DIR`.

- [x] **T30. Test — resolution artifact renders valid, escaped YAML**
  - [x] Round-trip test: render a resolution with a note containing a
        colon-space, a leading `#`, and an embedded newline (same hostile
        fixture 305's F005 test used) — parse the rendered frontmatter back
        with `yaml.safe_load` and assert it succeeds and round-trips the
        hostile string exactly.
  - [x] Test the full schema is present: all fields from the design's schema
        block appear with correct types (`resolution` is one of the three
        literal strings, `findingStatuses` is a list of dicts with `id`,
        `status`, `screen`).
  - Commit: `feat: add resolution-artifact rendering with escaped YAML frontmatter`
  - Effort: 1/5
  - Note: These tasks landed inside T29/T30's commit (`feat: add resolution-artifact rendering with escaped YAML frontmatter`) rather than getting their own — the writer had to exist for the module it lives in to lint. No work was dropped.

- [x] **T31. Versioned-filename writer — never overwrite, `-r{n}` increments**
  - [x] Function `save_resolution(rendered: str, *, index: int, review_type:
        str, slice_name: str, cwd: str) -> Path` computing the next
        available `r{n}` by globbing existing
        `{index}-resolution.{review_type}.{slice_name}-r*.md` files
        non-recursively, taking the max `n` found + 1 (starting at 1 if
        none exist), and writing to that path. Never overwrites an existing
        `-r{n}` file — if a race or a bug would collide, raise rather than
        silently overwrite (this artifact's entire purpose is an immutable
        audit trail; a silent overwrite here is the same class of bug Part D
        fixes for reviews).
  - [x] `mkdir(parents=True, exist_ok=True)` on the reviews dir, matching
        existing persistence helpers' pattern.
  - Effort: 1/5

- [x] **T32. Test — versioned writes never collide, metrology glob excludes them**
  - [x] Test: first `save_resolution` call for an index writes `-r1`; a
        second call writes `-r2`, and the first file's content is
        untouched.
  - [x] Test: `discover_judge_results` (real function, real glob, per 305's
        own precedent test in `test_capture_discovery.py`) run against a
        directory containing a saved resolution artifact returns an empty
        list — the `-resolution.` filename never matches metrology's
        `*-review.*` pattern (verify this is true by construction: the
        filename format is `{index}-resolution.{type}.{name}-r{n}.md`, which
        contains no `-review.` substring).
  - [x] **Second, separate glob is a distinct function — test it too.**
        `metrology/capture.py` has its own index-scoped review-discovery
        function using `reviews_dir.glob(f"{index}-review.*")` (a different
        pattern shape than `discover_judge_results`'s `*-review.*`, though
        the same "no `-review.` substring" proof applies to both). Add a
        second assertion — call that function (find its current name by
        reading `metrology/capture.py`, since this task file predates it
        and should not guess at an API) against the same fixture directory
        and assert it also returns no resolution artifacts. Do not assume
        one glob's exclusion implies the other's — assert both explicitly,
        per SC11's own wording ("`discover_judge_results` **and** review
        discovery").
  - Commit: `feat: add versioned resolution-artifact writer with no-overwrite guarantee`
  - Effort: 1/5

- [x] **T33. Orchestration — `resolve_review()` end-to-end function**
  - [x] In `review/resolution.py`, a single `resolve_review(index: int,
        review_type: str | None, *, model: str | None, profile: str | None,
        no_judge: bool, since: str | None, cwd: str) -> ResolutionResult`
        (a small dataclass carrying `resolution`, `artifact_path`,
        `finding_statuses`, mirroring the shape a CLI command needs to print
        and set an exit code from) that sequences T17→T33 in the order the
        Data Flow diagram specifies: locate → load → verdict-consistency
        screen → diff-base resolve → diff compute → empty/git-failure screen
        → judge leg → verify → derive → render → save.
  - [x] Every WARNING/ERROR emitted by the steps above must actually surface
        (this function does not swallow or downgrade any log level a called
        function already chose).
  - Effort: 2/5
  - Note: `resolution.py` reached 613 lines and was split at the evidence/decision seam into `resolution_evidence.py` (locate, load, diff base, diff compute, screens) and `resolution.py` (decide, orchestrate); `resolution_artifact.py` holds render + the versioned writer.

- [x] **T34. Test — full end-to-end resolve against a real git fixture**
  - [x] Following the 305 e2e pattern (`tests/pipeline/test_findings_addressed_e2e.py`'s
        real-repo fixture): author a review via the real
        `format_review_markdown`/`save_review_result` path, commit a fix,
        run `resolve_review` with the judge transport mocked to claim
        `addressed` — assert the final `ResolutionResult.resolution ==
        "ADDRESSED"`, the artifact file exists at the expected `-r1` path,
        and the original review file is byte-identical before and after
        (this is the design's own primary success criterion — assert it
        directly, do not infer it).
  - [x] Test the full negative chain in one fixture: empty diff → UNADDRESSED
        → fix nothing, resolve again → still UNADDRESSED, `-r2` written.
  - [x] **Test T33's no-swallowed-log requirement directly, not by
        inference.** T33 states every WARNING/ERROR a called step emits
        must actually surface through `resolve_review`. Nothing else in
        this file asserts that — without it, the F001 mismatch WARNING
        (T23/T24), the injection-cap WARNING (T25/T26), or the
        file-history-fallback WARNING (T19/T20) could be silently dropped
        by the orchestration layer with no test catching it. Using
        `caplog`, drive `resolve_review` through one path that a called
        function is known to WARNING on (the file-history-fallback case
        from T19/T20 is a convenient one — no mocking beyond what T20
        already sets up) and assert the WARNING text appears in `caplog`
        at `WARNING` level, not `INFO` or below, not absent.
  - Commit: `feat: add end-to-end review-resolution orchestration`
  - Effort: 2/5

- [x] **T35. `sq review resolve` CLI command**
  - [x] In `src/squadron/cli/commands/review.py`, add
        `@review_app.command("resolve")` with signature
        `resolve(index: int = typer.Argument(...), review_type: str | None =
        typer.Argument(None), model: str | None = typer.Option(None,
        "--model", ...), profile: str | None = typer.Option(None,
        "--profile", ...), no_judge: bool = typer.Option(False,
        "--no-judge", ...), since: str | None = typer.Option(None,
        "--since", ...), cwd: str | None = typer.Option(None, "--cwd", ...),
        verbose: int = typer.Option(0, "--verbose", "-v", count=True, ...))`
        — flag help text and option ordering follow the existing `review
        code` command's conventions in the same file.
  - [x] Print a per-finding table (reuse whatever rich table/console pattern
        `review code` already uses for findings display) plus the artifact
        path and final `resolution:` value.
  - [x] `sys.exit(0)` on `ADDRESSED`, `sys.exit(1)` on
        `UNADDRESSED`/`UNKNOWN` — matching the design's stated shell-
        composability requirement.
  - Effort: 2/5

- [x] **T36. Test — CLI command end-to-end via Typer's test runner**
  - [x] Using the project's existing Typer CLI test pattern (check
        `tests/cli/commands/test_review.py` for the idiom already in use for
        `review code`), invoke `sq review resolve` against a fixture repo and
        assert stdout contains the resolution value and artifact path, and
        the process exit code matches the ADDRESSED/UNADDRESSED case tested.
  - [x] Test the ambiguous-type CLI error path: two review files present, no
        `TYPE` argument given → non-zero exit, error message lists both
        matched files (surfacing T18's underlying behavior through the CLI
        layer).
  - Commit: `feat: add sq review resolve CLI command`
  - Effort: 1/5

- [x] **T37. Slash-command parity — `/sq:review resolve`**
  - [x] Update `commands/sq/review.md`: add `resolve` to the valid-subcommand
        list, document its argument/flag passthrough following the same
        pattern the file already uses for `code`/`slice`/`tasks`/`arch`.
  - [x] No new logic — this file dispatches to the CLI command already
        built in T35; confirm by reading the existing dispatch pattern for
        another subcommand before writing this one.
  - Commit: `docs: add /sq:review resolve slash command`
  - Effort: 1/5

---

## Part C — Contract documentation and PM procedure

- [x] **T38. Document the resolution-artifact schema and `review resolve` in `docs/COMMANDS.md`**
  - [x] Add a `### review resolve` section to `docs/COMMANDS.md` following
        the existing `### review code` section's format (argument/option
        table, example invocations) — the design's Data Flow section and
        schema block are the source of truth for what to write, not a
        re-derivation.
  - [x] Document the artifact filename pattern, the `docType:
        review-resolution` schema fields, and explicitly state: *this
        artifact does not affect `verdict:` on the review file; it is
        evidence for a human (or a future tool) to act on.*
  - [x] Document the interim PM procedure from Decision 6: a verdict edit is
        justified by an `ADDRESSED` resolution artifact and should cite it
        in the commit message — the same practice already used for slice
        305's own verdict edit, now named as the standing procedure.
  - Effort: 1/5

- [x] **T39. DEVLOG entry and coordination note**
  - [x] Write the DEVLOG entry for Phase 6 completion once implementation is
        done (deferred until Phase 6 closes — noted here so it is not
        forgotten, per the process guide's Session State Summary
        requirement).
  - [x] Draft the Context Forge coordination note (referenced in the slice
        design's Decision 6 and Cross-Slice Dependencies) describing the
        resolution-artifact schema as an offered contract — this is
        communication, not a squadron code change; confirm with the Project
        Manager how this coordination should actually be delivered (issue,
        message, shared doc) before drafting it, since the design document
        does not specify the delivery mechanism.
  - Effort: 1/5
  - Note: The delivery mechanism was confirmed with the Project Manager — a GitHub issue. Filed as https://github.com/ecorkran/context-forge/issues/69.

---

## Closeout

- [x] **T40. Full-suite verification and success-criteria walkthrough**
  - [x] Run the slice design's full Verification Walkthrough (steps 1–8)
        against a real scratch repo, confirming each `# →` comment in the
        walkthrough matches actual output.
  - [x] `uv run pytest -q` — full suite passes.
  - [x] `uv run ruff check src tests` — clean. `uv run ruff format --check
        src tests` — clean.
  - [x] `uv run pyright` — zero errors.
  - [x] Walk every checkbox in the slice design's Success Criteria section
        and confirm each is demonstrably true (cite the test that proves
        it, matching the pattern 305's slice design used in its own
        Verification Walkthrough section).
  - [x] Mark the slice design's `status:` field `complete` and update
        `dateUpdated`.
  - [x] Update slice-plan entry 7 in
        `300-slices.eval-actions-llm-as-judge-scoring.md`: mark `[x]`,
        add an Implemented note in the same style as slice 305's entry
        (branch name, commit count, what shipped).
  - Commit: `docs: close out slice 306 review resolution`
  - Effort: 1/5
  - Note: Two defects were found by *running* the walkthrough rather than by the tests, and both were fixed with tests added: (a) a skipped or failed judge leg returned no outcomes at all, so the artifact was silent about the findings it was supposed to account for — every accountable finding with no outcome is now recorded as `disputed` with a note; (b) `dateCreated` was being emitted quoted (`'20260803'`), a different parsed type than every other squadron-written frontmatter — now unquoted.
