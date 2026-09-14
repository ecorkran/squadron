---
docType: tasks
slice: verification-that-verified-nothing
project: squadron
lldReference: project-documents/user/slices/919-slice.verification-that-verified-nothing.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [917, 918]
interfaces: []
status: not_started
dateCreated: 20260914
dateUpdated: 20260914
---

# Tasks: Verification That Verified Nothing (2 of 2)

## Context Summary

Part 2 of three; Part 1 is in `919-tasks.verification-that-verified-nothing-1.md`.

- **Part 2 (#97, this file)** — a verdict derived from findings after a
  failed summary parse is indistinguishable, in frontmatter, from one the
  model actually stated. `fallback_used` already reaches the artifact body;
  only `_review_frontmatter_lines` has no degradation parameter. Fixed by a
  `verdictSource: stated | derived` frontmatter key (D6, PM decision,
  verified non-blocking on Context Forge).
- **Part 3 (#98, this file)** — `frontmatter_gate.py` hands `cf` explicit
  staged paths and reads only the exit code; in a sibling git worktree `cf`
  silently checks none of them and exits 0. Fixed by reading `filesChecked`
  from `cf validate frontmatter --json` and failing closed on zero-against-
  nonempty, an unparseable count, or a hung subprocess (D14, added after
  slice review).

Full rationale and decisions D6-D14 are in the slice design — read it before
starting. Issues: [#97](https://github.com/ecorkran/squadron/issues/97),
[#98](https://github.com/ecorkran/squadron/issues/98).

Commit after each task per `CLAUDE.md`'s "at least once per task" rule — the
only checklist items explicitly named `Verify and commit` (T2.7, T3.11) are
each part's semantic closeout commit, not the only commits in the part.

Part 2 and Part 3 touch disjoint files and do not depend on each other or on
Part 1's completion in the same working session, but Part 1 must be merged
first per the design's execution order. Each part ends in its own
verify-and-commit task.

Branch: `919-slice.verification-that-verified-nothing` (same branch as file
1 — continue on it, do not create a new one).

### Verified code anchors (traced on `d1863815`, 20260914)

| Anchor | Location |
|---|---|
| `Verdict` `StrEnum` — pattern to mirror for the new enum | [models.py:10](src/squadron/review/models.py#L10) |
| `ReviewResult.fallback_used` | [models.py:99](src/squadron/review/models.py#L99) |
| `_extract_verdict` | [parsers.py:115](src/squadron/review/parsers.py#L115) |
| `_verdict_from_findings` (#28 recovery) | [parsers.py:124](src/squadron/review/parsers.py#L124) |
| `fallback_used` set on derivation | [parsers.py:802](src/squadron/review/parsers.py#L802) |
| `fallback_used` NOT set, nothing-parsed branch (D8) | [parsers.py:816](src/squadron/review/parsers.py#L816) |
| `fallback_used` in `to_dict()` | [models.py:201](src/squadron/review/models.py#L201) |
| `degraded` folds `fallback_used` into body rendering | [persistence.py:340](src/squadron/review/persistence.py#L340) |
| `_findings_not_parsed_section` render | [persistence.py:405](src/squadron/review/persistence.py#L405) |
| `_review_frontmatter_lines` — needs the new parameter | [persistence.py:242](src/squadron/review/persistence.py#L242) |
| First call site (normal review path) | [persistence.py:352](src/squadron/review/persistence.py#L352) |
| Second call site (provider-failure path) | [persistence.py:683](src/squadron/review/persistence.py#L683) |
| `frontmatter_gate.py` full file (small, read entirely) | [frontmatter_gate.py](src/squadron/events/builtin/frontmatter_gate.py) |
| Subprocess spawn, no timeout today | [frontmatter_gate.py:44-53](src/squadron/events/builtin/frontmatter_gate.py#L44-L53) |
| Reference timeout/kill pattern to mirror (D14) | [bash_tool.py:33-40](src/squadron/tools/builtin/bash_tool.py#L33-L40) (`_kill_process_group`), [:62-73](src/squadron/tools/builtin/bash_tool.py#L62-L73) (`asyncio.wait_for` + `start_new_session=True`) |
| `limits.py` — where the new timeout constant belongs | [tools/limits.py](src/squadron/tools/limits.py) (see `BASH_TIMEOUT_S`, `GREP_TIMEOUT_S`) |
| `review_verdict_gate.py` — confirm untouched, reads paths itself | [review_verdict_gate.py:97](src/squadron/events/builtin/review_verdict_gate.py#L97) |
| Existing gate test file to extend | `tests/events/builtin/test_frontmatter_gate.py` (136 lines; `_fake_process`, `_commit_context` helpers already present) |

Re-verify every cited line number before editing.

---

## Part 2 — Verdict provenance in frontmatter (#97)

### T2.1 — Define the `VerdictSource` enum

- [x] Add `VerdictSource(StrEnum)` to `review/models.py`, mirroring the
      `Verdict` enum's style ([models.py:10](src/squadron/review/models.py#L10)):
      exactly two members, `STATED = "stated"` and `DERIVED = "derived"`
      (D7's closed two-value vocabulary — no reason string, no third value).
- [x] Place it near `Verdict` and `Severity` so the three enums read as a
      family.

**Success:** `pyright` clean; the enum is importable from `review.models`
and defines exactly the two members. Effort: 1.

### T2.2 — Thread provenance through `parse_review_output`'s result

- [x] Add a field to `ReviewResult` carrying the resolved `VerdictSource` (or
      an equivalent that lets the caller compute it — decide based on
      whether `fallback_used` alone is sufficient, per D7's note that a
      normalized-but-then-stated parse, per D4, is still `stated`).
- [x] Set it in `parsers.py` at the same two sites that currently set
      `fallback_used`: the derivation branch
      ([parsers.py:802](src/squadron/review/parsers.py#L802)) sets `DERIVED`;
      every other branch that produces a real verdict sets `STATED`.
- [x] Resolve D8 explicitly for the nothing-parsed branch
      ([parsers.py:816](src/squadron/review/parsers.py#L816), verdict stays
      `UNKNOWN`): choose and document whether this emits `STATED` (if
      unambiguous) or omits the key entirely, following the established
      `_review_frontmatter_lines` convention that an absent optional key
      means "does not apply." Write the chosen behavior as a code comment at
      the branch, not only in the task file.
- [x] Add `verdictSource` to `to_dict()` ([models.py:201](src/squadron/review/models.py#L201),
      beside `fallback_used`) so the JSON contract and frontmatter can be
      compared for agreement (design success criterion 6) — see T2.5.

**Success:** every path through `parse_review_output` that returns a verdict
other than the nothing-parsed case sets an unambiguous `VerdictSource`; the
nothing-parsed case's behavior is decided and commented; `to_dict()` carries
the same field frontmatter will render. Effort: 2.

### T2.3 — Test provenance resolution in isolation

- [x] Test: the #96-shaped case (a parse that fails the summary but yields
      one benign finding, most-severe-wins deriving `PASS`) resolves to
      `VerdictSource.DERIVED` — this is the end-to-end regression for the
      defect #97 describes.
- [x] Test: a normal parse where `## Summary` is found directly resolves to
      `VerdictSource.STATED`.
- [x] Test: a normalized-newline-free parse (Part 1) whose `## Summary` is
      then found after normalization resolves to `STATED`, not `DERIVED` —
      confirms D7's orthogonality (`verdictSource` answers "did the model say
      this", not "how much work did squadron do to read it").
- [x] **Test the stated-vs-derived mismatch branch explicitly** — the
      `verdict in (CONCERNS, FAIL) and not findings` case
      ([parsers.py:826-828](src/squadron/review/parsers.py#L826-L828)).
      `fallback_used` is `True` here too, but the verdict came from
      `_extract_verdict` (the model genuinely stated it) — only the
      *findings* failed to parse. This is the one branch where
      `fallback_used` and the correct `VerdictSource` diverge, so it must
      resolve to `STATED`. **Do not compute `VerdictSource` as a function of
      `fallback_used` alone** — that would silently mislabel this branch as
      `derived`; T2.2's field must be set independently at each branch, per
      what actually happened to the verdict, not derived from the findings
      flag.
- [x] Test the nothing-parsed branch per whichever T2.2 decided.

**Success:** all five cases pass and are distinguishable from each other —
no two produce the same `VerdictSource` for different reasons without a
comment explaining why that is correct, and the mismatch-branch test fails
if `VerdictSource` is ever computed from `fallback_used` directly. Effort: 2.

### T2.4 — Emit `verdictSource` in frontmatter at both call sites

- [x] Add a `verdict_source: VerdictSource | None` parameter to
      `_review_frontmatter_lines` ([persistence.py:242](src/squadron/review/persistence.py#L242)),
      following the existing optional-key convention in that function
      (append the line only when the value is supplied, matching
      `reviewed_sha`/`revision_number`/`tools_suppressed_reason`'s pattern
      immediately below it).
- [x] Pass it at **both** call sites — the normal review path
      ([persistence.py:352](src/squadron/review/persistence.py#L352)) from
      the `ReviewResult` field T2.2 added, and the provider-failure path
      ([persistence.py:683](src/squadron/review/persistence.py#L683)) with
      whatever value is correct for a failure (likely omitted — a provider
      failure has no verdict to attribute provenance to; decide and comment).
- [x] Emit the key as `verdictSource: stated` / `verdictSource: derived` in
      frontmatter, placed adjacent to the existing `verdict:` line for
      readability.

**Success:** `grep -n "verdictSource" src/squadron/review/persistence.py`
shows it threaded through both call sites, not just one — a fix that only
covers the normal path leaves the provider-failure artifact silently
inconsistent. Effort: 2.

### T2.5 — Test frontmatter emission end to end

- [x] Test: a review artifact built from the #96-shaped derivation case
      (T2.3's first case) has frontmatter containing both `verdict: PASS`
      and `verdictSource: derived` — read the rendered markdown's frontmatter
      block directly, not the internal `ReviewResult`, since the whole
      defect was one surface (JSON `to_dict()`) knowing what another
      (frontmatter) did not.
- [x] Test: a real parsed `## Summary` case's artifact shows
      `verdictSource: stated`.
- [x] **`to_dict()` must also emit `verdictSource`**, not only frontmatter —
      design success criterion 6 ("no surface says `stated` while another
      says `derived`") is not executable otherwise, since JSON currently
      carries only `fallback_used`. Add the key to `to_dict()`
      ([models.py:201](src/squadron/review/models.py#L201), beside
      `fallback_used`) as part of T2.2, not here. Test: `to_dict()`'s
      `verdictSource` and the frontmatter's `verdictSource` line report the
      same value for the same `ReviewResult`, for both the derived and
      stated cases.
- [x] Test: an existing artifact snapshot (or a `ReviewResult` built the way
      one was before this slice) with no `verdictSource` field set renders
      frontmatter with the key **absent**, not a placeholder — confirms
      design success criterion 3 (additive, absence is meaningful).

**Success:** all four pass; criterion 4 (#96-shaped case produces a derived
marking, not a clean one) and criterion 6 (surfaces agree) both hold as
executable tests, not just documentation claims. Effort: 2.

### T2.6 — File the Context Forge coordination issue

- [x] File an issue against context-forge (or the appropriate tracker) asking
      its review gate to read `verdictSource` and decline to auto-clear on
      `derived` — reference this slice and #97. Not a blocking precondition
      (D6 verified `cf` tolerates the unknown key today), but design success
      criterion 7 requires it be filed once the key ships. Filed:
      [context-forge#89](https://github.com/ecorkran/context-forge/issues/89)
- [x] Link the filed issue number back into this task's checklist item and
      into the slice design's Part 2 section (a one-line addition noting the
      issue number, once known).

**Success:** issue filed, number recorded in both places. Effort: 1.

### T2.7 — Verify and commit Part 2

- [ ] `uv run pytest tests/review/ -q` green.
- [ ] `uv run ruff format --check . && uv run ruff check . && uv run pyright`
      clean.
- [ ] Run the design's Part 2 verification walkthrough: construct the #96
      shape, `grep -E '^(verdict|verdictSource):'` the resulting artifact,
      confirm both keys, then `uv run pytest tests/review/ -k "provenance or
      verdict_source" -v`.
- [ ] Commit: `feat(review): emit verdictSource provenance in frontmatter (#97)`
- [ ] Effort: 1

---

## Part 3 — Frontmatter gate fails closed (#98)

### T3.1 — Add the gate timeout constant

- [ ] Add a new constant to `tools/limits.py` (e.g.
      `FRONTMATTER_GATE_TIMEOUT_S`), placed alongside `BASH_TIMEOUT_S` and
      `GREP_TIMEOUT_S`, with a docstring comment following that module's
      existing style. Value should sit well below `BASH_TIMEOUT_S` (120.0)
      since `cf validate frontmatter` on a handful of staged files is fast
      — pick a concrete number (e.g. 15.0-30.0) and state the reasoning in
      the comment; this is an implementation call, not a design-mandated
      exact value.
- [ ] Do **not** hard-code the value at the `frontmatter_gate.py` call site
      (`CLAUDE.md`'s rule against scattering magic defaults) — reference
      `limits.FRONTMATTER_GATE_TIMEOUT_S` by module attribute, read at call
      time, matching `bash_tool.py`'s
      `timeout = limits.BASH_TIMEOUT_S` pattern exactly
      ([bash_tool.py:62-63](src/squadron/tools/builtin/bash_tool.py#L62-L63)).

**Success:** one new constant, referenced by module attribute (not imported
by value) from the gate. Effort: 1.

### T3.2 — Pass `--json` and read `filesChecked` (D10)

- [ ] In `FrontmatterGateAction.execute` ([frontmatter_gate.py:44](src/squadron/events/builtin/frontmatter_gate.py#L44)),
      add `--json` to the `cf validate frontmatter` invocation.
- [ ] Parse `filesChecked` from the JSON stdout. When
      `context.staged_paths` is non-empty and `filesChecked == 0`, treat this
      as a **failure**, distinct from cf's own findings-based failure
      (exit code 1) and from the missing-cf/could-not-run cases already
      handled.
- [ ] The failure message must name the likely cause per D10's wording: cf
      validated 0 of N staged files, which in a git worktree usually means cf
      resolved in-root against a different checkout, so the gate cannot
      confirm frontmatter and is failing closed. Do not just say "0 files
      checked" — the operator cannot infer the worktree cause from that
      alone.
- [ ] **Update the existing fake-process tests in
      `test_frontmatter_gate.py`'s `TestExitMapping`** so each includes a
      `filesChecked` key in its fake stdout —
      `test_exit_0_succeeds` currently returns `b'{"totalFindings":0}'` with
      no `filesChecked` key, which passes today only because nothing reads
      that field yet. Once this task and T3.3 land, D11's fail-closed rule
      makes an absent `filesChecked` a failure, so this and the sibling
      exit-1/exit-2 tests will go red unless updated to include a
      `filesChecked` count consistent with their fake `staged_paths`. Fix
      the tests as part of this task, not as an unplanned discovery at
      T3.11.

**Success:** a fake `cf` process returning exit 0 with
`{"filesChecked": 0, ...}` against non-empty staged paths now fails, with a
message containing the worktree explanation; the three pre-existing
`TestExitMapping` tests are updated to carry a `filesChecked` value and
still pass. Effort: 2.

### T3.3 — Fail closed on absent or unparseable `filesChecked` (D11)

- [ ] When the JSON cannot be parsed at all, or parses but has no
      `filesChecked` key, take the same fail-closed path as T3.2 — never a
      silent fallback to exit-code-only behavior (`CLAUDE.md`'s "never use
      silent fallback values").
- [ ] Give this case its own distinct message (per D11: "the count could not
      be read"), separate from T3.2's worktree-cause message, so the
      operator can tell a cf-version/output-shape problem from a worktree
      problem.

**Success:** malformed JSON stdout and JSON missing the key both fail with a
message distinguishable from T3.2's. Effort: 1.

### T3.4 — Confirm zero-staged-paths is a legitimate pass (D12)

- [ ] Confirm (or add if missing) that when `context.staged_paths` is empty,
      `filesChecked: 0` is **not** treated as a failure — this must be
      tested explicitly, since it is the case that would otherwise make
      T3.2's fix fail every code-only commit.
- [ ] The failure condition from T3.2 is specifically "zero-checked against
      non-empty staged input," never "zero-checked" alone — verify the
      implementation reads that way, not as two separate conditions that
      happen to coincide.

**Success:** a commit staging no markdown passes, unchanged from today.
Effort: 1.

### T3.5 — Bound the subprocess with a timeout and reap on kill (D14)

- [ ] Change the subprocess spawn
      ([frontmatter_gate.py:44-49](src/squadron/events/builtin/frontmatter_gate.py#L44-L49))
      to pass `start_new_session=True`, matching `bash_tool.py`'s reasoning
      (the timeout path must be able to kill the whole process group, not
      just the `cf` process itself).
- [ ] Wrap `proc.communicate()` in `asyncio.wait_for(..., timeout=limits.FRONTMATTER_GATE_TIMEOUT_S)`
      (T3.1's constant), catching the timeout.
- [ ] On timeout, kill and reap the process group — reuse or mirror
      `_kill_process_group` from `bash_tool.py`
      ([bash_tool.py:33-40](src/squadron/tools/builtin/bash_tool.py#L33-L40))
      rather than reimplementing it; if it cannot be imported directly
      without creating an unwanted dependency between `tools` and `events`,
      duplicate the function with a comment noting it mirrors
      `bash_tool.py`'s implementation and why it is not shared.
- [ ] Log at WARNING on timeout, naming the timeout value and that `cf` was
      killed — matching `bash_tool.py`'s WARNING wording style.
- [ ] The gate fails on timeout, with a message distinct from both T3.2's
      (worktree) and T3.3's (unparseable count) messages — the operator's
      next action differs for each of the three causes.

**Success:** a stub `cf` that sleeps past the timeout is killed, reaped (no
zombie process left — verify via `proc.returncode` being set after the kill,
not `None`), logged at WARNING, and the gate fails with its own distinct
message. This is design success criterion 5 and the Failure-Mode
Enumeration rule's required observable signal. Effort: 3.

### T3.6 — Test the timeout path in `test_frontmatter_gate.py`

- [ ] Extend `tests/events/builtin/test_frontmatter_gate.py` with a test
      class for the timeout case, following the file's existing
      `_fake_process`/`_commit_context` helper pattern
      (or add a new helper that simulates a hanging `communicate()` — e.g. a
      mock whose `communicate` awaits `asyncio.sleep` longer than the test's
      patched timeout).
- [ ] Assert: the gate's result is a failure; a WARNING was logged (use
      `caplog`, matching the existing project convention in
      `tests/tools/test_jail.py`'s WARNING assertions); the process's kill
      path was invoked (assert on the mock, since a real hung subprocess
      cannot be spawned safely in a unit test).
- [ ] Patch `limits.FRONTMATTER_GATE_TIMEOUT_S` down to a small value for the
      test rather than actually waiting close to its real value — keep the
      test fast.

**Success:** the new test passes, runs in well under a second, and fails
if T3.5's timeout wrapping is removed. Effort: 2.

### T3.7 — Test the zero-checked and unparseable-count paths

- [ ] Add tests to `test_frontmatter_gate.py` covering T3.2
      (zero-checked-against-nonempty fails, with the worktree message), T3.3
      (absent/unparseable `filesChecked` fails, with its own message), and
      T3.4 (empty staged list with `filesChecked: 0` passes).
- [ ] **Add the design's criterion 2 pair — the default-checkout case is
      otherwise untested.** A fake `cf` returning exit 0 with
      `filesChecked` equal to the staged-path count passes (valid
      frontmatter, default checkout, unchanged from today); a fake `cf`
      returning exit 1 with `filesChecked` equal to the staged-path count
      and findings in stdout fails, carrying cf's own finding text — not
      one of T3.2's or T3.3's fail-closed messages. This is what proves the
      fail-closed paths added by this part did not also start failing the
      ordinary, everything-worked case.
- [ ] Confirm all three failure messages (worktree, unparseable-count,
      timeout) are distinguishable from each other by asserting on
      message content, not just on `success is False` — design success
      criterion 5 requires the messages be genuinely distinct, and a test
      that doesn't check content would pass even if two collapsed to the
      same text.

**Success:** design success criteria 1-4 hold as executable tests; the
three failure messages are pairwise distinguishable. Effort: 2.

### T3.8 — Confirm `review_verdict_gate.py` is unaffected

- [ ] Read `review_verdict_gate.py` ([review_verdict_gate.py:97](src/squadron/events/builtin/review_verdict_gate.py#L97))
      and confirm it reads and parses each staged path itself, never
      shelling out to `cf` — this part must not have touched it.
- [ ] Run its existing test file unchanged:
      `uv run pytest tests/events/builtin/test_review_verdict_gate.py -q`.

**Success:** design success criterion 6 confirmed; no diff touches that
file. Effort: 1.

### T3.9 — Reproduce the original defect from a sibling worktree, then confirm the fix

- [ ] From a sibling git worktree (`git worktree list` to confirm which
      checkout is default), stage a throwaway markdown file with genuinely
      invalid frontmatter, and confirm `cf validate frontmatter --json <path>`
      reports `filesChecked: 0`, exit 0 — reproducing #98 as the design's
      walkthrough describes.
- [ ] Confirm that **before** this part's fix, committing that file would
      have reported `squadron.frontmatter-gate: ok` (this can be confirmed
      against the pre-fix code via `git stash` or by checking out the prior
      commit in a scratch clone — do not actually commit invalid frontmatter
      to any real branch).
- [ ] Confirm that **after** the fix, the same commit attempt fails with the
      T3.2 worktree-cause message.
- [ ] Record the outcome in the DEVLOG per the design's instruction to
      refine the verification walkthrough from what was actually run.

**Success:** the reproduction is genuine (invalid frontmatter, not just a
missing file) and the before/after contrast is confirmed directly, not
assumed from the unit tests alone. Effort: 2.

### T3.10 — Add the CHANGELOG line (D13)

- [ ] Add a CHANGELOG entry noting that commits from a git worktree with
      staged markdown may now fail frontmatter validation where they
      previously passed silently, and name the workaround (commit markdown
      from the default checkout, or register the worktree with `cf`) — this
      is a deliberate behavior change per D13 and needs to be visible to
      whoever hits it first.
- [ ] Keep it a short, user-facing bullet per this project's changelog
      convention — technical detail belongs in the DEVLOG entry from T3.9,
      not here.

**Success:** one CHANGELOG bullet, user-facing, naming the workaround.
Effort: 1.

### T3.11 — Verify and commit Part 3

- [ ] `uv run pytest tests/events/builtin/test_frontmatter_gate.py -v` green,
      and `uv run pytest -q` for the full suite.
- [ ] `uv run ruff format --check . && uv run ruff check . && uv run pyright`
      clean.
- [ ] Commit: `fix(events): fail closed when cf checks zero staged files (#98)`
- [ ] Effort: 1

---

## Final slice verification

### T4.1 — Full-suite gate and slice closeout

- [ ] `uv run ruff format --check . && uv run ruff check . && uv run pyright`
      clean across the whole tree — zero pyright errors is a merge blocker
      per `CLAUDE.md`.
- [ ] `uv run pytest -q` full suite green. Compare the pass count against the
      design's stated baseline (3698 passed, 4 skipped in the default
      checkout before this slice) and confirm the new count reflects only
      this slice's additions, with no unexplained change in skip count.
- [ ] Confirm all three parts' commits are present on the slice branch in
      order (T1.10, T2.7, T3.11).
- [ ] Update the slice design's frontmatter `status` field from
      `not_started` to `complete` (or the project's equivalent terminal
      status) once all tasks above are checked off — delegate the checklist
      update itself to the `task-checker` agent per `CLAUDE.md`.
- [ ] Write the DEVLOG entry for this slice's completion per
      `prompt.ai-project.system.md`'s Session State Summary guidance,
      covering all three parts and referencing #96, #97, #98.

**Success:** gates green, both task files fully checked, slice design status
updated, DEVLOG entry written. Effort: 1.
