---
docType: review
layer: project
reviewType: tasks
slice: small-fixes-batch
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/921-tasks.small-fixes-batch.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260917
dateUpdated: 20260917
responseStatus: addressed
reviewedSha: 63a5157d2f4dce725fe3f365465f3ec75f64c995
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
findings:
  - id: F001
    severity: concern
    category: task-accuracy
    summary: "Task 1.2's guard condition also fires when no model is supplied at all"
    location: "src/squadron/cli/commands/review.py:597-608"
  - id: F002
    severity: concern
    category: test-determinism
    summary: "New `--restore` tests are machine-dependent unless `--cwd` is passed; Task 2.5's \"empty set\" premise is false"
    location: "tests/cli/commands/test_summary_instructions.py:155-176"
  - id: F003
    severity: concern
    category: verification
    summary: "Fix 1 smoke-test invocation cannot reach the guard"
    location: "src/squadron/cli/commands/review.py:1062"
  - id: F004
    severity: concern
    category: traceability
    summary: "Design F003's \"record in acceptance criteria / consider --profile hint\" instruction was dropped"
    location: "project-documents/user/tasks/921-tasks.small-fixes-batch.md:84-103"
  - id: F005
    severity: note
    category: design-alignment
    summary: "Task 2.2 silently drops the design's \"prefix-continuation\" qualifier from the partition predicate"
    location: "project-documents/user/tasks/921-tasks.small-fixes-batch.md:210-248"
  - id: F006
    severity: note
    category: verification
    summary: "Smoke-test command name `sq summary` doesn't match the command the test suite exercises"
    location: "src/squadron/cli/app.py:64"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success-criteria coverage, sequencing, and commit strategy are sound"
    location: "project-documents/user/tasks/921-tasks.small-fixes-batch.md"
---

# Review: tasks — slice 921

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Task 1.2's guard condition also fires when no model is supplied at all

`alias_model`/`alias_profile` are initialized to `None` and only assigned inside `if raw_model is not None:` (line 604). Task 1.2 says to add `if alias_model == raw_model and alias_profile is None` "after line 605 ... before computing `resolved_profile` at line 608" — that span is ambiguous between inside the `if raw_model is not None:` block and after it. If placed after the block, `None == None` is `True` and every model-less invocation (no flag, no config, template without `model:`) raises `unknown model alias 'None'` — breaking the existing `test_run_review_command_defaults_to_sdk` (tests/cli/test_review_profile.py:144), which passes no model at all. The design's predicate ("when `resolve_model_alias` returns `(name, None)`") presupposes a name was given; the task's restatement lost the `raw_model is not None` precondition, and the same shape exists in `_resolve_judge_model` (review.py:1170-1176) for Task 1.3. Tasks 1.4–1.6 add no no-model regression test. The task should state the placement explicitly (inside the `if` block, or add `raw_model is not None` to the condition) and add one no-model test. The existing suite would catch a literal mis-placement, so this is not blocking — but the spec is a trap for a literal-minded implementer.

### [CONCERN] New `--restore` tests are machine-dependent unless `--cwd` is passed; Task 2.5's "empty set" premise is false

Every existing `TestRestoreFlag`/`TestRestoreKey` invocation (including the `_run` helper) omits `--cwd`, so under the fix `_sibling_projects` reads the *real* parent of the process CWD, not an empty set. Consequences: (a) a Task 2.4 test written per "the existing pattern" — patch `gather_cf_params`/`_SUMMARIES_DIR`, create `tmp_path/"squadron"` and `tmp_path/"squadron-pr"` but forget `--cwd` — passes on this dev machine (parent of the squadron checkout really contains `squadron-pr`, so the exclusion fires anyway) and fails on CI where no sibling exists (`squadron-pr-p5a.md` stays clean, `matches[0]` picks it, the assertion fails). That is false confidence of exactly the kind the project's parsing rules warn about. (b) Task 2.5's claim "they don't set up sibling directories, so `_sibling_projects` should return an empty set for all of them" is factually wrong — the set is whatever is really in the parent, minus the patched project name — and its "fix Task 2.2's implementation, not the test" instruction would send the implementer chasing a phantom bug on any environment collision. Tasks 2.4/2.5 should explicitly require passing `--cwd` into the `tmp_path` layout for all new cases, and ideally update the existing classes to pass `--cwd` too (a small edit contradicting "unchanged").

### [CONCERN] Fix 1 smoke-test invocation cannot reach the guard

`sq review code --model definitely-not-a-real-alias` (Task 3.1) exits 1 at the scope check — "provide a slice number, --diff, or --files" — before `_run_review_command` is ever called, so the unknown-alias message is unreachable with that invocation. Because both failures exit 1, a junior could run it, see a non-zero exit, and half-verify the fix. The command needs a scope argument, e.g. `sq review code --files "**/*" --model definitely-not-a-real-alias` (or `--diff`/slice number). Task 3.1's success line does demand the alias message, so a careful implementer self-corrects, but the example is a trap; the project's own CLAUDE.md guidance on hallucination-prone examples applies.

### [CONCERN] Design F003's "record in acceptance criteria / consider --profile hint" instruction was dropped

The design (Fix 1, F003 paragraph) explicitly requires recording that a *valid* literal model ID with no `--profile` and no `default_review_profile` — which dispatches correctly today via the bare `"sdk"` default — starts failing after this fix, and asks the author to consider adding a `--profile` remedy hint to the error message. Task 1.2 records only the stale-`default_model` collateral; no task records the F003 shape, Task 1.1's message is the design's base message with no hint, and Task 3.2's DEVLOG bullets don't mention it. Either add the callout to a task's acceptance criteria (1.2 or 1.7) or add the `--profile` hint; as written, a design-mandated record of a real behavior change was lost between design and tasks.

### [NOTE] Task 2.2 silently drops the design's "prefix-continuation" qualifier from the partition predicate

The design defines `clean` as stems not starting with `{sibling}-` "where `project` is not itself a prefix-continuation of `sibling`"; Task 2.2 (line 216) states the plain predicate only. The simplified form matches the design's own "correct predicate" restatement and I could not construct a case where the (undefined) qualifier changes the outcome — current-project stems never start with `{sibling}-` when sibling ≠ project — but the simplification is unexplained and a later reader may mistake it for an oversight. A one-line note in the task would close the loop.

### [NOTE] Smoke-test command name `sq summary` doesn't match the command the test suite exercises

The registered hidden command is `_summary-instructions` (app.py:64; all tests invoke `["_summary-instructions", "--restore"]`), while Task 3.1 — like the design and issue prose — says `sq summary --restore`. I could not verify whether a `summary` alias command also exists (`summary_run.py` defines a command whose registration I did not confirm), so this may be a naming slip in a manual step only. If no alias exists the check fails with "No such command," which is self-evident; worth confirming before relying on the smoke step.

### [PASS] Success-criteria coverage, sequencing, and commit strategy are sound

Cross-referencing the design: Fix 1's guard (1.1–1.2), shared judge-path helper per F004 (1.1/1.3), error message with known aliases (1.1, asserted in 1.5), and all three profile channels tested (1.4–1.5) are all present; Fix 2's sibling derivation (2.1), unstripped-stem partition (2.2), disambiguation policy with unchanged `_summary_key`/`--key` (2.2, asserted end-to-end in 2.4), empty-`clean` error (2.2, 2.4), OSError → WARNING + empty set per F002 (2.1, with the required caplog assertion in 2.3, matching `.claude/rules/review-code.md:29`), and the limitation comment (2.1) are all present. No task traces outside the design's scope (no loader or `ModelResolver` changes), test tasks immediately follow their implementation tasks, dependencies flow one direction with no cycles, and the two parts are explicitly independent. Commits are distributed (1.7, 2.6, final verification) rather than batched, and 1.7's batching rationale — no commit in history has the guard active alongside the contradicting test — is correct, since after Task 1.2 alone the old `test_unknown_model_passes_through` would fail. No NFR is restated in the design, so the load-test/CI-gating criteria are not applicable.

### Run Digest

- Response length: 8940 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 77330
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response (20260917)

All 7 findings verified against source before acting. All 4 CONCERNs and both
NOTEs were real; F005's investigation turned up a bug the finding itself had
inverted.

- **F001** (guard also fires when no model is supplied) — confirmed by reading
  review.py:601-608: `alias_model`/`alias_profile` are initialized to `None`
  and assigned only inside `if raw_model is not None:`, so a guard placed
  after that block evaluates `None == None and None is None` → `True` on every
  model-less invocation. Task 1.2 now specifies placement **inside** the block
  explicitly, with a callout naming the failure mode and the
  `raw_model is not None` alternative; Task 1.3 carries the same warning for
  `_resolve_judge_model`, which has the identical shape. Task 1.5 gains a
  direct no-model regression test rather than relying on
  `test_run_review_command_defaults_to_sdk` to catch a misplacement
  incidentally.

- **F002** (machine-dependent `--restore` tests; Task 2.5's "empty set"
  premise false) — confirmed: `grep -- --cwd tests/cli/commands/test_summary_instructions.py`
  returns nothing, so every existing invocation takes the `--cwd` default of
  `"."` and `_sibling_projects` would enumerate the real parent of the process
  CWD. Task 2.4 now requires `--cwd` on every new invocation, with the reason
  stated (passes on this dev machine, fails on CI). Task 2.5 is rewritten:
  its false "they don't set up sibling directories, so the set is empty" claim
  is replaced with the instruction to add `--cwd` to the existing
  `TestRestoreFlag`/`TestRestoreKey` invocations including the `_run` helper,
  and its "fix the implementation, not the test" directive is now gated behind
  that edit so it cannot send an implementer chasing an environment collision.
  Effort raised 1/5 → 2/5 to reflect the added edit.

- **F003** (smoke-test invocation cannot reach the guard) — confirmed: the
  scope check at review.py:1062 precedes the `_run_review_command` call at
  review.py:1116, so the invocation exits 1 before the guard is reachable.
  Task 3.1 now uses `sq review code --files "**/*" --model
  definitely-not-a-real-alias` and states that both failures exit 1, so the
  message — not the exit code — is the verification.

- **F004** (design F003's acceptance-criteria instruction dropped) —
  confirmed: the design's Fix 1 section requires recording the valid-literal-ID
  collateral and asks for a `--profile` remedy hint; neither appeared in any
  task. Task 1.2 now records both collateral effects as an explicit numbered
  list, and the `--profile` remedy clause is folded into Task 1.1 where the
  message is actually defined (not only as a downstream amendment), with
  Task 1.5 asserting the clause is present.

- **F005** (Task 2.2 drops the design's prefix-continuation qualifier) —
  the omission was real, but the finding's assessment that it is outcome-neutral
  is wrong, and this was the most valuable finding in the review. The qualifier
  guards the **shorter-sibling** direction: run from the `squadron-pr`
  worktree, `project` is `squadron-pr` and the sibling set contains `squadron`;
  every stem in `matches` starts with `squadron-` by construction of the
  `{project}-*.md` glob, so the unqualified predicate marks *every*
  `squadron-pr` summary excluded, leaving `clean` empty and making bare
  `--restore` raise "no summary files found" in a worktree holding eight of its
  own summaries. Verified by direct computation. That is the inverse of #103
  and strictly worse than today's behavior. Task 2.2 now states the qualifier
  as load-bearing with that worked example, and Task 2.4 gains a
  reversed-roles regression case that fails without it. The design was already
  correct here and needed no change.

- **F006** (`sq summary` is not the registered command) — confirmed: app.py:64-65
  register `_summary-instructions` and `_summary-run`, both hidden and
  `_`-prefixed; no `summary` alias exists, so the smoke step would have failed
  with "No such command." Task 3.1 now uses `sq _summary-instructions
  --restore`. The Fix 2 smoke check was also strengthened while there: it had
  been framed as a no-setup sanity check, but running it from the `squadron`
  checkout with a `squadron-pr` sibling present *is* #103's motivating case, so
  it now asserts the corrected selection, the excluded-entry marking, and the
  `--key` escape hatch.

- **F007** (PASS) — no action.

Task file updated: `project-documents/user/tasks/921-tasks.small-fixes-batch.md`
(dateUpdated 20260917). No design changes were required.
