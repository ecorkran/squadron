---
docType: tasks
slice: small-fixes-batch-2
project: squadron
lldReference: project-documents/user/slices/922-slice.small-fixes-batch-2.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: "Design complete and reviewed (CONCERNS, all findings addressed — F001 citation correction, F002 declined with rationale, F003 addressed). Six independent fixes batched — #65 (findings 2-3), #117, #112, #108, #57, #100. No code changes yet."
status: not_started
dateCreated: 20260920
dateUpdated: 20260920
---

# Tasks: Small Fixes Batch 2

## Context Summary

Six independently small, root-caused items bundled into one slice per
[900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md)
entry 20. None shares code with another; they are batched to avoid a slice
per issue.

| Fix | Issue | Statement |
|---|---|---|
| 1 | [#65](https://github.com/ecorkran/squadron/issues/65) (findings 2–3) | Declared dependencies do not match what `src/` imports |
| 2 | [#117](https://github.com/ecorkran/squadron/issues/117) | Frontmatter gate fails closed when all staged markdown is outside cf's scope |
| 3 | [#112](https://github.com/ecorkran/squadron/issues/112) | `ProcessRunner` reports a nonexistent `cwd` as "executable not found" |
| 4 | [#108](https://github.com/ecorkran/squadron/issues/108) | `tool_use` / `tool_result` sdk_type literals are scattered |
| 5 | [#57](https://github.com/ecorkran/squadron/issues/57) | `sq setup` renders routine INSTALL steps as red errors |
| 6 | [#100](https://github.com/ecorkran/squadron/issues/100) | Jail-exclusion refusals flood `-v` review output |

Every fix is grounded in the finalized design
([922-slice.small-fixes-batch-2.md](project-documents/user/slices/922-slice.small-fixes-batch-2.md)),
which carries decisions **D1–D6** — one per fix. Read the relevant decision
before implementing its fix; each records a rejected alternative that looks
reasonable and explains why it was rejected.

**Two corrections recorded in the design, do not re-derive them:**

- Issue #65's text says `mcp` is unimported. That is **stale** — `mcp` is now
  imported by `tools/mcp_bridge.py` and `tools/cf_tools.py` and **stays**.
- Issue #100 attributes the exclusion-logging policy to slice 917. That is
  **wrong** — the policy is slice 918 **D3**
  ([918-slice.review-grounding.md:144](project-documents/user/slices/918-slice.review-grounding.md)).

**Ordering (design, Development Approach):** Fix 2 first — it unblocks
hook-clean commits for the rest of the slice — then 3, 4, 6, 5, and Fix 1
last, since it regenerates `uv.lock` and is most likely to conflict with
anything else in flight. **One commit per fix.**

**Current project state:** no code changes yet; design and design review only.

**Dependencies:** none. Each fix is independent of the others and of any open
slice.

**This file covers Parts A–E** (Fixes 2, 3, 4, 6, 5). **Part F** (Fix 1 —
dependencies) and **Part G** (verification and closeout) are in
[922-tasks.small-fixes-batch-2-2.md](project-documents/user/tasks/922-tasks.small-fixes-batch-2-2.md).
The slice is not complete until both files are.

**Non-goals** (design, Non-goals): the `[serve]` extra
([#118](https://github.com/ecorkran/squadron/issues/118)); consolidating the
scattered `project-documents/user/...` path constants; pruning excluded
subtrees at walk descent; rewording `doctor_checks.py` detail strings;
partial `filesChecked` mismatch comparison.

---

## Part A — Fix 2 (#117): frontmatter gate scope predicate

Design decision **D2**. Do this first: it unblocks committing the rest of the
slice without `--no-verify`.

### A1. File the upstream context-forge issue

Do this **first**: task A2's predicate comment cites the issue number, and
filing it up front means the comment is written once rather than revisited.

- [x] File an issue on context-forge asking `cf validate frontmatter --json`
      to report paths it skipped as out of scope, so the gate can distinguish
      "skipped" from "wrong checkout" without a squadron-side predicate.
- [x] Note the issue number — task **A2** links it from the predicate comment.
- **Effort:** 1
- **Success:** issue exists; its number is in hand before A2 starts.

### A2. Add the document-root scope predicate

- [x] Open `src/squadron/events/builtin/frontmatter_gate.py`.
- [x] Define the cf user-document root **once** as a module-level constant
      (the design requires a single definition; do not inline the path
      string at the use site).
- [x] Add a predicate that answers "is this staged path under the cf
      user-document root".
  - [x] Compare **normalized path parts**, not string prefixes, so that
        `./project-documents/user/x.md` and `project-documents/user/x.md`
        classify identically. A `startswith` comparison is explicitly
        insufficient.
  - [x] Staged paths arrive repository-root-relative (the hook in
        `setup_install.py` passes `git diff --cached --name-only` output).
- [x] Add a comment at the predicate recording its removal condition: it goes
      away when `cf validate frontmatter --json` reports skipped-as-out-of-scope
      paths. Cite the context-forge issue number from task **A1**.
- **Effort:** 2
- **Success:** the constant is defined once; the predicate classifies both
  path spellings above the same way.

### A3. Use the predicate only in the zero branch

- [x] Locate the D12 zero-of-N branch at
      [frontmatter_gate.py:137](src/squadron/events/builtin/frontmatter_gate.py#L137)
      (`staged_count > 0 and files_checked == 0`).
- [x] Keep passing **all** staged paths to cf. Do **not** pre-filter the
      paths sent to cf — D2 rejects that alternative explicitly, because it
      would make squadron's predicate the authority and let in-scope files go
      unvalidated if cf's scope is ever broader.
- [x] Inside the zero branch only, count how many staged paths are in scope:
  - [x] in-scope count `== 0` → **PASS** (nothing cf would have checked).
  - [x] in-scope count `> 0` → **FAIL CLOSED**, keeping the existing D10
        worktree message, now reporting the **in-scope** count rather than
        the total staged count. Update `_worktree_cause_message`
        ([frontmatter_gate.py:42](src/squadron/events/builtin/frontmatter_gate.py#L42))
        accordingly.
- [x] Leave every other posture untouched: `files_checked > 0`, unreadable
      count (D11), timeout, and missing `cf` behave exactly as today.
- **Effort:** 2
- **Success:** criteria 4–6 of the design's Functional Requirements hold.

### A4. Test Fix 2

- [x] Add tests to `tests/events/builtin/test_frontmatter_gate.py`, alongside
      the existing slice-919 D10–D12 class near
      [line 95](tests/events/builtin/test_frontmatter_gate.py#L95).
- [x] Use the **real cf JSON shape** shown in the design's Technical Scope
      table — not an invented shape. The design records probed values:
      `CHANGELOG.md`, `README.md`, `docs/QUICKSTART.md`, `.claude/rules/python.md`,
      `project-documents/DEVLOG.md`, and
      `project-documents/ai-project-guide/readme.md` each yield
      `filesChecked: 0`; `project-documents/user/slices/921-slice.small-fixes-batch.md`
      yields `filesChecked: 1`.
- [x] Test (criterion 4): release-shaped staging — `CHANGELOG.md`,
      `pyproject.toml`, `uv.lock` — with `filesChecked: 0` → **passes**.
- [x] Test (criterion 5): at least one staged path under
      `project-documents/user/` with `filesChecked: 0` → **fails closed**,
      and the error still carries the D10 worktree wording.
- [x] Test (criterion 6): `filesChecked > 0`, unreadable count, timeout, and
      missing `cf` are each unchanged. Confirm the existing tests at
      [lines 201](tests/events/builtin/test_frontmatter_gate.py#L201) and
      [267](tests/events/builtin/test_frontmatter_gate.py#L267) — which assert
      the worktree, unreadable-count, and timeout messages stay
      distinguishable — still pass.
- [x] Test: the mixed case — some staged paths in scope, some out, with
      `filesChecked: 0` → fails closed (in-scope count is non-zero).
- **Effort:** 2
- **Success:** all tests pass; no existing gate test is weakened to
  accommodate the change.

### A5. Verify Fix 2 against the real hook

- [x] On a scratch branch, run the design's Verification Walkthrough for Fix 2:

  ```bash
  echo "" >> CHANGELOG.md && git add CHANGELOG.md
  git commit -m "test: gate scope"        # expect: squadron.frontmatter-gate: ok
  git reset --hard HEAD~1
  ```

- [x] The fail-closed side needs a sibling worktree and is covered by the A3
      unit test for criterion 5; do **not** attempt to reproduce it live.
- [x] Commit Fix 2 on its own.
- **Effort:** 1
- **Success:** a release-shaped commit passes the installed pre-commit hook
  without `--no-verify`.

---

## Part B — Fix 3 (#112): `cwd` misreported as missing executable

Design decision **D3**.

### B1. Add `ProcessCwdNotFoundError` and classify in the handler

- [x] Open `src/squadron/core/process_runner.py`.
- [x] Add `ProcessCwdNotFoundError(cwd)` beside `ProcessNotFoundError`
      ([line 40](src/squadron/core/process_runner.py#L40)). It carries the
      offending directory. It does **not** join the `CodeHostError`
      hierarchy — a missing working directory is a configuration error, not a
      code-host condition.
- [x] In the **existing** `except FileNotFoundError` handler
      ([line 104](src/squadron/core/process_runner.py#L104)), raise
      `ProcessCwdNotFoundError` when `cwd` is not `None` and is not a
      directory; otherwise raise `ProcessNotFoundError` as today.
- [x] Do **not** pre-check `cwd` before `Popen`. D3 classifies inside the
      handler deliberately: it keeps the success path free of an extra stat
      and avoids a check-then-use gap.
- [x] Document the new exception in the `ProcessRunner` protocol docstring
      ([line 57](src/squadron/core/process_runner.py#L57)). Record that the
      protocol obliges no caller to handle it — it signals a configuration
      error and is meant to surface.
- **Effort:** 2
- **Success:** criterion 7 of the design's Functional Requirements holds.

### B2. Stop `github_cli` converting it to "gh is not on PATH"

- [x] Open `src/squadron/codehost/github_cli.py`, the `except
      ProcessNotFoundError` handler at
      [line 490](src/squadron/codehost/github_cli.py#L490).
- [x] Let `ProcessCwdNotFoundError` **propagate** rather than converting it
      to `GitHubCliMissingError`. Log the condition at WARNING first.
- [x] Confirm `ProcessCwdNotFoundError` does not subclass
      `ProcessNotFoundError`, or the existing handler will still swallow it.
- [x] No change needed at the git call sites in `codehost/remotes.py` and
      `codehost/refs.py` — they do not catch `ProcessNotFoundError`.
- **Effort:** 1
- **Success:** criterion 8 holds — no "gh is not on PATH" for a nonexistent
  `cwd`, and the condition is logged at WARNING.

### B3. Test Fix 3

- [x] Add tests to `tests/core/test_process_runner.py`:
  - [x] nonexistent `cwd` → `ProcessCwdNotFoundError` **naming the
        directory**.
  - [x] missing executable with a valid `cwd` → `ProcessNotFoundError`
        (unchanged).
  - [x] missing executable with `cwd=None` → `ProcessNotFoundError`
        (unchanged).
- [x] Add a test for the `github_cli` path: a scripted
      `ProcessCwdNotFoundError` propagates rather than becoming
      `GitHubCliMissingError`, and a WARNING record is emitted.
  - [x] Produce the condition by scripting the exception through
        `tests/codehost/fake_runner.py::FakeProcessRunner`, which raises
        whatever `Exception` a test gives it. **`FakeProcessRunner` needs no
        change.**
- [x] Confirm the exact `run` keyword arguments against the protocol
      signature ([line 60](src/squadron/core/process_runner.py#L60)) — the
      design flags these as to-be-confirmed.
- **Effort:** 2
- **Success:** all tests pass; no existing `process_runner` or `github_cli`
  test regresses.

### B4. Verify and commit Fix 3

- [x] Run the design's Verification Walkthrough for Fix 3:

  ```bash
  uv run python -c "
  from squadron.core.process_runner import SubprocessRunner
  SubprocessRunner().run(['git','status'], cwd='/nonexistent-922', timeout=5)"
  # expect: ProcessCwdNotFoundError naming /nonexistent-922
  ```

- [x] Commit Fix 3 on its own.
- **Effort:** 1
- **Success:** the error names the directory, not `executable not found: git`.

---

## Part C — Fix 4 (#108): centralize sdk_type literals

Design decision **D4**.

### C1. Define the two constants

- [x] Open `src/squadron/core/models.py`.
- [x] Add `TOOL_USE_TYPE = "tool_use"` and `TOOL_RESULT_TYPE = "tool_result"`
      beside the existing `SDK_RESULT_TYPE`
      ([line 112](src/squadron/core/models.py#L112)) and
      `RATE_LIMIT_EVENT_TYPE` ([line 123](src/squadron/core/models.py#L123)),
      following their comment style.
- **Effort:** 1
- **Success:** both constants exist next to the existing two.

### C2. Replace the literal at the producer

- [x] `src/squadron/providers/sdk/translation.py` lines **62** and **78** —
      this is the **producer**, the site that writes `metadata["sdk_type"]`.
      Replace both literals with the constants.
- **Effort:** 1
- **Success:** no `"tool_use"` or `"tool_result"` literal remains in
  `translation.py`.

### C3. Replace the literals at the four consumers

Separate sub-tasks per component, each independently verifiable:

- [x] `src/squadron/pipeline/sdk_session.py` lines **188–189**.
- [x] `src/squadron/pipeline/summary_oneshot.py` line **147** (already imports
      `SDK_RESULT_TYPE` and `RATE_LIMIT_EVENT_TYPE` in the same expression).
- [x] `src/squadron/review/review_client.py` line **271** (same shape as
      above).
- [x] `src/squadron/metrology/audit.py` lines **542** and **547**.
- [x] **Leave alone:** `cli/commands/task.py:47` compares
      `metadata["type"]` — a different key on the daemon message path, not
      `sdk_type` (D4).
- [x] **Leave alone:** `src/squadron/models/aliases.py` lines 67, 69, 207 —
      `"tool_use"` there is a TOML config key, not an sdk_type value.
- [x] `#108` also names `pipeline/actions/dispatch.py:174`; that line no
      longer contains either literal. Confirm and do not chase it.
- **Effort:** 2
- **Success:** criterion 9 holds.

### C4. Test Fix 4

- [x] This is a pure substitution with no behavior change; the guard is that
      the existing suites for these five modules still pass.
- [x] Run the design's literal check:

  ```bash
  grep -rnE '"tool_(use|result)"' src/squadron/providers/sdk/translation.py \
    src/squadron/pipeline/sdk_session.py src/squadron/pipeline/summary_oneshot.py \
    src/squadron/review/review_client.py src/squadron/metrology/audit.py
  # expect: no output
  ```

- [x] Run the tests covering these modules and confirm they pass unchanged.
- [x] Commit Fix 4 on its own.
- **Effort:** 1
- **Success:** the grep is silent; no test changed to accommodate the edit.

---

## Part D — Fix 6 (#100): exclusion refusals log at DEBUG

Design decision **D6**. This deliberately amends slice 918 **D3** for the
policy-exclusion case only; the silent-to-the-model half of D3 is untouched.

### D1. Demote exclusions at both sites

- [x] Open `src/squadron/tools/builtin/_shared.py`.
- [x] **Walk-filter site**, [line 93](src/squadron/tools/builtin/_shared.py#L93):
      the *policy exclusion* record (`refusing excluded path ...`) drops to
      **DEBUG**.
- [x] **`jail_violation` site**, [line 175](src/squadron/tools/builtin/_shared.py#L175):
      the same record drops to **DEBUG**.
- [x] **Jail escapes stay at WARNING** — [line 87](src/squadron/tools/builtin/_shared.py#L87)
      and [line 182](src/squadron/tools/builtin/_shared.py#L182)
      (`rejected path outside working directory`). An escape means something
      reached for the trust boundary; an exclusion is policy working as
      designed.
- [x] Preserve the "one refusal, one record" property of `jail_violation`
      and the distinguishable wording of the two kinds.
- **Effort:** 1
- **Success:** criterion 11 holds — a policy exclusion emits no record at
  INFO or above; a jail escape still emits exactly one WARNING.

### D2. Correct the docstrings

- [x] `_shared.py` [line 82](src/squadron/tools/builtin/_shared.py#L82) states
      "Both are logged at WARNING" — correct it to record the split and cite
      **918 D3** as the amended decision.
- [x] Check [line 53](src/squadron/tools/builtin/_shared.py#L53) ("a refusal
      produces exactly one WARNING") and
      [lines 193–194](src/squadron/tools/builtin/_shared.py#L193) for the same
      stale claim; correct any that no longer hold.
- **Effort:** 1
- **Success:** no docstring in `_shared.py` claims exclusions log at WARNING.

### D3. Update the slice-918 tests and add per-kind tests

- [x] `tests/tools/test_jail_exclusions.py` has **three** tests pinned to
      WARNING for exclusions, at lines **90–97**, **112–127**, and
      **140–148**. **Update them** to assert DEBUG — the design is explicit:
      update rather than adding parallel tests.
- [x] Add one test per refusal kind asserting **both level and count**, at
      **both** sites (walk filter and `jail_violation`) — four assertions
      total:
  - [x] walk filter, exclusion → exactly one DEBUG record, nothing at INFO+.
  - [x] walk filter, escape → exactly one WARNING record.
  - [x] `jail_violation`, exclusion → exactly one DEBUG record, nothing at
        INFO+.
  - [x] `jail_violation`, escape → exactly one WARNING record.
- [x] `tests/tools/test_jail.py` has **two** more tests that will fail once
      exclusions drop to DEBUG. Update both:
  - [x] `test_an_exclusion_refusal_emits_exactly_one_warning`
        ([line 201](tests/tools/test_jail.py#L201)) — filters
        `levelno == logging.WARNING` and asserts exactly one record for an
        exclusion through `jail_violation`. After D1 that filter finds zero.
  - [x] `test_an_exclusion_refusal_is_worded_distinguishably_from_a_jail_escape`
        ([line 246](tests/tools/test_jail.py#L246)) — asserts
        `len(messages) == 2` at WARNING for an exclusion plus an escape
        through `contained_in_jail`. After D1 only the escape remains at
        WARNING. Keep what this test exists to prove — that the two refusals
        are worded distinguishably — by capturing at DEBUG and asserting the
        wording across both levels, not by deleting the exclusion half.
- [x] Leave [line 194](tests/tools/test_jail.py#L194) alone — it asserts the
      walk predicate emits *nothing* at WARNING, which stays true.
- [x] Check `tests/tools/test_jail_symlinks.py` for further WARNING-pinned
      exclusion assertions and update any found.
- **Effort:** 2
- **Success:** the whole `tests/tools/` suite passes; no test asserts a
  WARNING for a policy exclusion.

### D4. Verify and commit Fix 6

- [ ] Run #100's own repro from the design:

  ```bash
  uv run sq review tasks 919 -v --model deepseek4-flash
  # expect: no "refusing excluded path" lines
  ```

  **Not run this session.** Attempted once in the interactive session used
  for implementation; `--model` is silently ignored there (the CLI's
  own model is used instead), and the run went against the wrong
  target — it re-reviewed slice 919's own task files rather than
  exercising #100's `-v` exclusion-noise repro. The accidental review
  output was reverted (`git checkout HEAD --`) before it could
  overwrite the real 919 review artifacts; no unintended change
  landed. Left unchecked rather than falsely marked done — run this
  from a plain CLI session (not this interactive one) before closing
  the slice.
- [ ] Run the same command with `-vv` and confirm the lines **do** appear
      (`-vv` maps to DEBUG). Same caveat as above — not run this session.
- [x] Commit Fix 6 on its own.
- **Effort:** 1
- **Success:** `-v` is clean; `-vv` still shows the exclusions. **Verified so
  far only by unit test** (`tests/tools/test_jail.py`'s four level+count
  tests, asserting DEBUG vs WARNING directly), not by the live `sq review`
  repro above.

---

## Part E — Fix 5 (#57): `sq setup` INSTALL iconography

Design decision **D5**.

### E1. Give INSTALL its own neutral icon

- [ ] Open `src/squadron/cli/commands/setup.py`, the `_ICON` map at
      [line 30](src/squadron/cli/commands/setup.py#L30). Today
      `StepKind.INSTALL` and `StepKind.CONFIGURE` both map to `("✗", "red")`.
- [ ] Map `StepKind.INSTALL` to a **non-error glyph and color**, distinct
      from all three other kinds (`ALREADY_DONE` is `("✓", "green")`,
      `CONFIGURE` is `("✗", "red")`, `OPTIONAL` is `("!", "yellow")`).
- [ ] `StepKind.CONFIGURE` keeps the red ✗.
- [ ] Do **not** change the `missing_count` logic at
      [line 51](src/squadron/cli/commands/setup.py#L51) — INSTALL still
      counts as a step needing action; only its rendering changes.
- [ ] Do **not** touch the `detail="not on PATH"` strings — they live in
      `doctor_checks.py`, are shared with `sq doctor`, and are accurate
      diagnostic output there (D5, and a Non-goal).
- **Effort:** 1
- **Success:** criterion 10 holds — `_ICON[StepKind.INSTALL]` differs from
  `_ICON[StepKind.CONFIGURE]` in **both** glyph and color, and is not red.

### E2. Test Fix 5

- [ ] Add a test to `tests/cli/test_setup.py` asserting `_ICON` gives INSTALL
      a glyph and color distinct from CONFIGURE, and that its color is not
      `"red"`.
- [ ] Assert the icon is also distinct from `ALREADY_DONE` and `OPTIONAL`.
- [ ] Confirm existing `tests/cli/test_setup.py` and
      `tests/cli/test_setup_steps.py` still pass — in particular any test
      asserting the missing-step count.
- **Effort:** 1
- **Success:** tests pass; the INSTALL row is visibly neutral.

### E3. Verify and commit Fix 5

- [ ] Confirm the flag name against `sq setup --help` (the design flags
      `--check` as to-be-confirmed), then run setup in check mode on a
      machine or PATH lacking one integration.
- [ ] Confirm the missing step shows the new neutral icon, not a red ✗.
- [ ] Commit Fix 5 on its own.
- **Effort:** 1
- **Success:** a routine first-run state no longer reads as an error.

---
