---
docType: tasks
slice: review-scope-correctness
project: squadron
lldReference: project-documents/user/slices/916-slice.review-scope-correctness.md
parent: project-documents/user/slices/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: [917]
status: not_started
dateCreated: 20260911
dateUpdated: 20260911
---

# Tasks: Review Scope Correctness

## Context Summary

Five defects on the `sq review` entry path, all answering one question: **did the
review examine the change set the operator meant, and was it equipped to read
it?** Fixes issues [#86](https://github.com/ecorkran/squadron/issues/86),
[#89](https://github.com/ecorkran/squadron/issues/89),
[#70](https://github.com/ecorkran/squadron/issues/70),
[#62](https://github.com/ecorkran/squadron/issues/62),
[#69](https://github.com/ecorkran/squadron/issues/69); verifies
[#71](https://github.com/ecorkran/squadron/issues/71).

Sequenced **D → A → C → B → E** per the design's Implementation Notes. The order
is load-bearing:

- **D** first — smallest change; its helper extraction consolidates the function
  bodies A/B/C then edit.
- **A** next — contained, independently verifiable against `git diff --name-only`.
- **C** before **B** — B's new failure path builds on C's corrected save-outcome
  model rather than being retrofitted into `saved = True` optimism.
- **B** after both — widest behavior change, depends on C's outcome enum.
- **E** last — the only part that alters a working reviewer's capability, and the
  only one whose verification needs a live model call.

Each part is independently committable and leaves the CLI working. Commit at each
part boundary.

### Verified code anchors (traced on `08df0c5`, 20260911)

| Anchor | Location |
|---|---|
| `review_slice` cwd/rules resolution (no git-root) | [review.py:597-598](src/squadron/cli/commands/review.py#L597-L598) |
| `review_arch` cwd/rules resolution (no git-root) | [review.py:655-656](src/squadron/cli/commands/review.py#L655-L656) |
| `review_tasks` cwd/rules resolution (no git-root) | [review.py:756-757](src/squadron/cli/commands/review.py#L756-L757) |
| `review_code` — correct pattern to extract | [review.py:871-890](src/squadron/cli/commands/review.py#L871-L890) |
| `review_resolve` — correct pattern | [review.py:1032-1035](src/squadron/cli/commands/review.py#L1032-L1035) |
| `resolve_slice_diff_range` called only when `--diff` absent | [review.py:850-852](src/squadron/cli/commands/review.py#L850-L852) |
| `saved = True` initializers (four) | [:616](src/squadron/cli/commands/review.py#L616), [:673](src/squadron/cli/commands/review.py#L673), [:760](src/squadron/cli/commands/review.py#L760), [:930](src/squadron/cli/commands/review.py#L930) |
| `_save_and_report` — returns `False` on `OSError` | [review.py:238](src/squadron/cli/commands/review.py#L238) |
| `_exit_on(verdict, saved)` | [review.py:273](src/squadron/cli/commands/review.py#L273) |
| `run_git` — **no `timeout` argument** | [git_utils.py:21](src/squadron/review/git_utils.py#L21) |
| `extract_diff_paths` — CLI call site, under `if rules_dir is not None:` | [review.py:891-893](src/squadron/cli/commands/review.py#L891-L893) |
| `extract_diff_paths` — pipeline call site, same guard | [actions/review.py:188-195](src/squadron/pipeline/actions/review.py#L188-L195) |
| SDK kwargs build — sets `allowed_tools` only | [provider.py:64-66](src/squadron/providers/sdk/provider.py#L64-L66) |
| `translate_tool_names` — raises on unmapped names | [tool_names.py:26](src/squadron/providers/sdk/tool_names.py#L26) |

### Standing constraints

- No new `Verdict` member. The five verdict consumers enumerated in the design's
  Part B table must not change.
- Every new failure path exits non-zero **and** logs at WARNING or above
  (Failure-Mode Enumeration rule). No silent path may be replaced by another
  silent path.
- No test may assert on user-facing message *text* as logical structure. Assert
  on exit codes and the outcome enum.

---

## Part D — Tool Jail Root (#86)

### Task D.1 — Extract the shared cwd/rules-dir resolution helper

- [ ] Read [review.py:871-890](src/squadron/cli/commands/review.py#L871-L890) to
      capture the correct pattern: `_resolve_cwd(cwd)` → `find_git_root(...) or
      resolved_cwd` → `resolve_rules_dir(review_cwd, None, rules_dir_flag)`.
- [ ] Add one private helper in `src/squadron/cli/commands/review.py` that takes
      the raw `cwd` and `rules_dir_flag` and returns the pair
      `(review_cwd, resolved_rules_dir)`.
- [ ] The helper is the only place the git-root resolution appears. Do not leave a
      second copy anywhere in the module.
- [ ] Effort: 2

### Task D.2 — Route all five subcommands through the helper

- [ ] Replace the resolution block in `review_slice`
      ([:597-598](src/squadron/cli/commands/review.py#L597-L598)) with a call to
      the D.1 helper; pass the returned `review_cwd` as the `cwd` in the config
      dict at [:602](src/squadron/cli/commands/review.py#L602).
- [ ] Same for `review_arch` ([:655-659](src/squadron/cli/commands/review.py#L655-L659)).
- [ ] Same for `review_tasks` ([:756-770](src/squadron/cli/commands/review.py#L756-L770)).
- [ ] Same for `review_code` ([:871-890](src/squadron/cli/commands/review.py#L871-L890)) —
      this one already has the correct behavior; the edit removes the duplicate,
      it must not change behavior.
- [ ] Same for `review_resolve` ([:1032-1035](src/squadron/cli/commands/review.py#L1032-L1035)).
- [ ] Success: `grep -c "find_git_root" src/squadron/cli/commands/review.py`
      returns 1 (the import) plus 1 (the helper) — no per-subcommand copies.
- [ ] Effort: 2

### Task D.3 — Test: jail root is the git root under a subdirectory `cwd`

- [ ] Add a test in `tests/review/test_config_cwd.py` (existing home for cwd
      behavior) that configures `cwd` as a subdirectory of a git repo fixture and
      asserts the `AgentConfig.cwd` the review client receives is the **git root**,
      not the configured subdirectory.
- [ ] Cover `slice`, `arch`, and `tasks` — the three subcommands that were wrong.
- [ ] Add one case where `cwd` is **not** inside a git work tree: the helper must
      fall back to `resolved_cwd` (the `or resolved_cwd` branch), not raise.
- [ ] This is the test [#86](https://github.com/ecorkran/squadron/issues/86) asks
      for.
- [ ] Effort: 2

### Task D.4 — Verify and commit Part D

- [ ] Run `uv run pytest tests/review tests/cli -q`. All green.
- [ ] Run `uv run ruff format` then `uv run ruff check`.
- [ ] Manual walkthrough: with `cwd = "./project-documents/user"` configured, run
      `uv run sq review slice 267 -v` and confirm there are no
      `read_file: file not found` lines carrying a doubled
      `project-documents/user/project-documents/user/` prefix.
- [ ] Commit: `refactor(review): extract shared jail-root and rules-dir resolution`
- [ ] Effort: 1

---

## Part A — `--diff` Merge-Base Normalization (#89)

### Task A.1 — Add a bounded timeout to `run_git`

- [ ] `run_git` ([git_utils.py:21](src/squadron/review/git_utils.py#L21)) passes no
      `timeout`, so `subprocess.run` blocks indefinitely against an unreachable
      remote-tracking ref.
- [ ] Add a module-level timeout constant and pass it to `subprocess.run`. Define
      the value once; do not inline a literal at the call site.
- [ ] Catch `subprocess.TimeoutExpired` alongside the existing `OSError` and
      return `None` — every caller already treats `None` as "git could not be
      invoked", so no call-site changes are needed.
- [ ] Log at WARNING on timeout, naming the git args. A timeout that returns
      `None` silently is the failure mode this task exists to remove.
- [ ] This hardens all seven existing `run_git` callers, not only Part A's new one.
- [ ] Effort: 2

### Task A.2 — Test: `run_git` timeout path

- [ ] In `tests/review/test_git_utils.py`, assert that a `subprocess.TimeoutExpired`
      raised by the underlying call yields `None` and emits a WARNING-level record.
- [ ] Assert the existing `OSError` path is unchanged.
- [ ] Effort: 1

### Task A.3 — Implement `normalize_diff_spec`

- [ ] Add `normalize_diff_spec(spec, cwd)` to `src/squadron/review/git_utils.py`.
- [ ] Shape table — this is the whole rule, and only the third row changes behavior:

  | Input shape | Treatment |
  |---|---|
  | contains `...` | pass through unchanged |
  | contains `..` | pass through unchanged |
  | bare ref (no range operator) | rewrite to `<ref>...HEAD` |

- [ ] Check for `...` **before** `..` — a three-dot spec contains a two-dot
      substring, so testing `..` first misclassifies every three-dot range.
- [ ] Hand the three-dot string to git; do **not** pre-resolve the merge-base
      ourselves (design A3). The string stays legible in the prompt and in
      `reviewedSha` provenance.
- [ ] Do not call `resolve_slice_diff_range` — it is slice-number-shaped. A needs
      the same semantics applied to a user-supplied ref.
- [ ] Effort: 2

### Task A.4 — Guard the bare-ref case with a resolution check

- [ ] Before rewriting a bare ref, resolve it via the existing `_resolve_rev`-style
      helper in `git_utils` (through `run_git`).
- [ ] Unresolvable bare ref → raise a typed error carrying the offending ref value.
- [ ] The error must distinguish **"not a git repository"** from **"ref not
      found"** — different operator errors with different fixes. `run_git`
      returning `None` is the former; a non-zero `returncode` is the latter.
- [ ] Explicit `a..b` / `a...b` endpoints are deliberately **not** validated
      (design A5). Do not add endpoint validation; B2's guard catches the outcome.
- [ ] Effort: 2

### Task A.5 — Wire normalization in at the CLI edge

- [ ] In `review_code`, call `normalize_diff_spec` immediately after the `--diff`
      value is read, **before** either consumer sees it — the normalized string is
      what flows onward (design A1).
- [ ] Confirm both consumers receive the same normalized string: `extract_diff_paths`
      ([review.py:893](src/squadron/cli/commands/review.py#L893)) and the prompt
      builder input `inputs["diff"]`.
- [ ] The slice-number path ([:850-852](src/squadron/cli/commands/review.py#L850-L852))
      already produces merge-base semantics via `resolve_slice_diff_range` — leave
      it alone; do not double-normalize.
- [ ] A typed error from A.4 exits non-zero **before any model call**, logging at
      ERROR with the offending ref.
- [ ] Effort: 2

### Task A.6 — Test: normalization shape table and failure paths

- [ ] In `tests/review/test_git_utils.py`, table-test `normalize_diff_spec` across
      all three shapes, **including both pass-through cases** — the pass-throughs
      are what protect `--diff a..b` from A6's rewrite.
- [ ] Cover a three-dot spec explicitly, to pin the check-order requirement in A.3.
- [ ] Assert an unresolvable bare ref raises, and that not-a-git-repo and
      ref-not-found are distinguishable **by error type or a structured field**,
      not by message text.
- [ ] Add a CLI-level test asserting `--diff <nonexistent>` exits non-zero with no
      provider invocation (assert the review client was never called).
- [ ] Effort: 3

### Task A.7 — Verify and commit Part A

- [ ] Run `uv run pytest tests/review tests/cli -q`. All green.
- [ ] Run `uv run ruff format` then `uv run ruff check`.
- [ ] Manual walkthrough, in any repo with a branch behind its base:
      ```bash
      git checkout -b probe origin/main~3
      echo x >> README.md && git commit -am "probe change"
      uv run sq review code --diff origin/main -v
      git diff --name-only origin/main...HEAD
      ```
      The two file lists must agree — only the branch's own changes.
- [ ] Commit: `fix(review): normalize bare --diff refs to merge-base range`
- [ ] Effort: 1

---

## Part C — Save Gating (#70)

### Task C.1 — Define the save-outcome enum

- [ ] Add a small enum to `src/squadron/cli/commands/review.py` (or the nearest
      shared review module) with four members covering the design's outcome table:
      **saved**, **suppressed** (`--no-save`), **not-persistable** (no slice
      identifier), **unsaved** (attempted and failed).
- [ ] Per the project rule against scattered comparison values, every branch that
      decides exit behavior references this enum — no boolean history, no string
      labels.
- [ ] Effort: 2

### Task C.2 — Invert the initializer and thread the outcome through

- [ ] Replace each `saved = True` initializer
      ([:616](src/squadron/cli/commands/review.py#L616),
      [:673](src/squadron/cli/commands/review.py#L673),
      [:760](src/squadron/cli/commands/review.py#L760),
      [:930](src/squadron/cli/commands/review.py#L930)) with the enum, defaulting
      to the not-persistable / unsaved side. Optimism about an unperformed write is
      the whole defect (design C1).
- [ ] `_save_and_report` already returns `False` on `OSError`
      ([:266-268](src/squadron/cli/commands/review.py#L266-L268)) — map its return
      onto **saved** vs **unsaved**. No new failure machinery is needed.
- [ ] `--no-save` maps to **suppressed**.
- [ ] Update `_exit_on` ([:273](src/squadron/cli/commands/review.py#L273)) to take
      the outcome rather than a bare bool, preserving its existing precedence.
- [ ] Effort: 3

### Task C.3 — Exit behavior per the outcome table

- [ ] Implement exactly this mapping — note that a slice-less `--diff` run
      **exits on verdict, not 1** (design C3, reversed after slice review F003):

  | Outcome | Exit |
  |---|---|
  | saved | on verdict |
  | suppressed (`--no-save`) | on verdict, no warning |
  | not-persistable (no slice identifier) | on verdict, **plus a WARNING** |
  | unsaved (attempted and failed) | **1**, per `_exit_on` precedence |

- [ ] The not-persistable WARNING must name **both** the fact (no artifact was
      written) and the remedy (supply a slice number, or `--output file` with
      `--output-path`). A warning that only reports absence leaves the operator
      where they started (design C4).
- [ ] Do **not** invent an artifact naming scheme for slice-less reviews — that gap
      is [issue #90](https://github.com/ecorkran/squadron/issues/90), deliberately
      out of scope.
- [ ] Effort: 2

### Task C.4 — Apply to all four subcommands

- [ ] `review_slice`, `review_arch`, `review_tasks`, and `review_code` all carry
      the defect; all four get the same mechanism (design C5, interface parity).
- [ ] Effort: 2

### Task C.5 — Test: save-outcome enum across all four subcommands

- [ ] In `tests/cli/test_review_save.py` (existing home for save behavior), assert
      each of the four outcomes for each of the four subcommands.
- [ ] Assert on **exit codes and the enum**, never on warning text.
- [ ] The attempted-and-failed case: force `save_review_result` to raise `OSError`
      and assert exit 1 regardless of a PASS verdict.
- [ ] The not-persistable case: assert exit 0 on PASS **and** that a WARNING-level
      record was emitted. Both halves — exit 0 alone was the bug's symptom.
- [ ] Assert `--no-save` emits **no** warning.
- [ ] Effort: 3

### Task C.6 — Regression-guard the documented invocations

- [ ] The design's Risk Assessment names this as the part touching the tool's
      most-documented invocation. Add CLI tests pinning the forms that appear in
      shipped docs:
      - `sq review code --diff main --output json` (README:344) — exits on verdict,
        emits parseable JSON on stdout.
      - `sq review code --diff main --files "src/**/*.py"` (README:292).
      - The bare `--diff` form for `slice`, `arch`, and `tasks`.
- [ ] Confirm by reading [README.md](README.md) lines 154, 176, 286, 292, 322, 341,
      344, 347 and [docs/COMMANDS.md](docs/COMMANDS.md) lines 90, 96 that each
      still describes working behavior. **No documentation updates are expected** —
      that is the point of the C3 revision. If implementation finds a case where
      exiting 0 is untenable, stop and raise it with the Project Manager rather
      than absorbing doc rewrites into this slice.
- [ ] Effort: 2

### Task C.7 — Verify and commit Part C

- [ ] Run `uv run pytest tests/review tests/cli -q`. All green.
- [ ] Run `uv run ruff format` then `uv run ruff check`.
- [ ] Manual walkthrough against a range that does contain code:
      ```bash
      uv run sq review code --diff origin/main -v; echo "exit=$?"
      git status --short project-documents/user/reviews/
      ```
      Expect exit 0 on a PASS, findings on the terminal, a WARNING naming the
      absent artifact and the remedy, and no new file under `reviews/`.
- [ ] Confirm `--no-save` exits on verdict with no warning.
- [ ] Confirm a genuinely failing save (reviews directory pointed at a read-only
      path) exits 1.
- [ ] Commit: `fix(review): report unsaved reviews instead of assuming success`
- [ ] Effort: 1

---

## Part B — Empty Filtered Scope (#62)

### Task B.1 — Implement `assert_reviewable_scope` in `git_utils`

- [ ] Add `assert_reviewable_scope(diff, cwd, exclude_patterns)` to
      `src/squadron/review/git_utils.py`.
- [ ] It computes the **unfiltered** and **filtered** path lists itself. Do not
      hang it off either existing `extract_diff_paths` call site
      ([review.py:893](src/squadron/cli/commands/review.py#L893),
      [actions/review.py:195](src/squadron/pipeline/actions/review.py#L195)) —
      both are nested under `if rules_dir is not None:` and feed language
      detection, discarding `file_paths` afterward. A guard hung off them would
      silently not run whenever no rules directory resolves (design B1, from slice
      review F001).
- [ ] Raise a typed error carrying **which of B.2's two cases occurred** plus the
      matched exclusion patterns and the excluded file count, as structured fields.
- [ ] Leave the existing rules-loading calls untouched — they do a different job.
- [ ] Effort: 3

### Task B.2 — Distinguish the two empty cases

- [ ] **All excluded**: the range resolved and had changed files, but every one
      matched an exclusion pattern. The error carries the matched patterns and the
      excluded count. The operator likely wants the review omitted, or a different
      range.
- [ ] **No changed files at all**: the range itself is the problem — wrong base,
      already-merged branch, or typo.
- [ ] Both exit non-zero; both must be distinguishable **by structured field**, not
      by message text. Conflating them is how
      [#71](https://github.com/ecorkran/squadron/issues/71) stayed unexplained.
- [ ] Effort: 2

### Task B.3 — Call the guard from both entry points, unconditionally

- [ ] Call `assert_reviewable_scope` in `review_code` before any provider work and
      **outside** any `if rules_dir is not None:` guard.
- [ ] Call it identically in the pipeline review action
      ([actions/review.py](src/squadron/pipeline/actions/review.py)) — `sq run` is
      the path that clears review gates, and is the harm B exists to fix.
- [ ] Both call sites refuse to persist and exit non-zero. No artifact is written;
      no `Verdict` member is added.
- [ ] Pre-flight placement means no model call is spent to be told what git already
      knew.
- [ ] Effort: 3

### Task B.4 — Test: empty scope, both cases, both entry points, rules-absent

- [ ] In `tests/review/test_git_utils.py`, unit-test `assert_reviewable_scope`
      across: all-excluded, no-changes-at-all, and the healthy pass-through case.
- [ ] CLI test: an all-excluded range exits non-zero and writes **no** artifact
      (assert the reviews directory is unchanged).
- [ ] CLI test: a no-changed-files range exits non-zero with a **different**
      structured case than all-excluded.
- [ ] Pipeline test: both cases hold identically via the review action, not only
      via the CLI (design criterion 6).
- [ ] **Rules-absent test**: with `resolve_rules_dir` returning `None`, the
      empty-scope refusal must still fire. This is the exact regression the
      original B1 would have shipped — it is the most important test in this part.
- [ ] Effort: 3

### Task B.5 — Verify the pipeline escape hatch (no code change)

- [ ] Confirm that omitting a phase's `review:` key suppresses both the review and
      its checkpoint — [phase.py:76](src/squadron/pipeline/steps/phase.py#L76)
      (`if review is not None`) and [:163](src/squadron/pipeline/steps/phase.py#L163).
- [ ] Verify with `uv run sq run <pipeline> <slice> --dry-run` on a phase with no
      `review:` key: neither a review action nor a checkpoint appears.
- [ ] **No pipeline-surface work is required by this part.** This task exists so
      implementation does not go looking for a feature that does not need building.
- [ ] Effort: 1

### Task B.6 — Pre-landing behavior-change check

- [ ] Per the design's Risk Assessment: B turns a passing outcome into a failing
      one. Before landing, check whether any repo's active pipeline has a
      docs-shaped phase carrying a `review:` key.
- [ ] Where found, remove the `review:` key per B3 rather than weakening the guard.
- [ ] If a case is found that cannot be resolved by removing the key, stop and
      raise it with the Project Manager.
- [ ] Effort: 1

### Task B.7 — Verify and commit Part B

- [ ] Run `uv run pytest tests/review tests/cli tests/pipeline -q`. All green.
- [ ] Run `uv run ruff format` then `uv run ruff check`.
- [ ] Manual walkthrough on a branch whose only changes are markdown:
      ```bash
      uv run sq review code --diff origin/main -v; echo "exit=$?"
      git status --short project-documents/user/reviews/
      ```
      Expect non-zero, a message naming the `*.md` exclusion, and no new file.
- [ ] Re-run with `--rules-dir` pointing somewhere with no rules, so
      `resolve_rules_dir` returns `None`. The refusal must still fire.
- [ ] Run the same range through the pipeline; it must fail identically, not pass.
- [ ] Commit: `fix(review): refuse to persist a review with empty scope`
- [ ] Effort: 1

### Task B.8 — #71 follow-up (not a deliverable)

- [ ] After B lands, re-run [#71](https://github.com/ecorkran/squadron/issues/71)'s
      reproduction script in the reporting repo.
- [ ] If B's new message explains the observed behavior, close #71 citing this
      slice. If not, re-file with the new evidence.
- [ ] No code in this slice is written *for* #71 (design B4).
- [ ] Effort: 1

---

## Part E — SDK Tool Availability (#69)

### Task E.1 — Scope check on `allowed_tools` producers

- [ ] Before implementing, enumerate every producer of `AgentConfig.allowed_tools`
      in the codebase — it feeds non-review dispatch too (design E5).
- [ ] For each producer, determine whether it relied on receiving the CLI's
      **default** tool set while declaring a narrower `allowed_tools` list.
- [ ] If no non-review producer depends on the current behavior, proceed with E.2
      at the provider edge.
- [ ] If one does, narrow the change to the review client's config construction
      instead of the provider edge, and record which producer forced the narrowing.
- [ ] This task gates E.2. Do not implement before it resolves.
- [ ] Effort: 2

### Task E.2 — Set `tools` from the declared list

- [ ] In the SDK provider kwargs build
      ([provider.py:64-66](src/squadron/providers/sdk/provider.py#L64-L66)), set
      `tools` alongside the existing `allowed_tools` translation, from the same
      declared list:
      ```python
      kwargs["tools"] = translate_tool_names(config.allowed_tools)
      ```
- [ ] Both `tools` and `allowed_tools` are set deliberately (design E2) — they
      answer different questions (what exists vs. what is pre-approved).
- [ ] Do **not** use `disallowed_tools`. A denylist must be re-audited each time
      the CLI's default tool set grows; an allowlist cannot drift that way
      (design E1).
- [ ] `translate_tool_names` ([tool_names.py:26](src/squadron/providers/sdk/tool_names.py#L26))
      already raises `ProviderError` on unmapped names — a template typo fails
      loudly rather than silently widening the set. Do not add a fallback.
- [ ] Leave `permission_mode: bypassPermissions` in the four templates unchanged
      (design E3): a review is unattended and a prompt would hang it; the tool set
      was the actual exposure. **Re-examine only if a future template declares a
      mutating tool.**
- [ ] Effort: 2

### Task E.3 — Test: emitted SDK kwargs

- [ ] In `tests/review/test_template_sdk_regression.py` or
      `tests/test_providers.py`, assert the constructed `ClaudeAgentOptions`
      carries `tools` equal to the translated declared list.
- [ ] Assert `Bash` is **not** present for a review config declaring
      `[read_file, list_files, grep]`.
- [ ] Assert `allowed_tools` is still set (E2 — both, deliberately).
- [ ] Assert an unmapped tool name in a config raises `ProviderError`.
- [ ] Effort: 2

### Task E.4 — Live SDK review verification

- [ ] A kwargs assertion is necessary but **not sufficient** (design E4). Run a live
      SDK-profile code review at `-vv`.
- [ ] From the per-tool-call DEBUG records, confirm only `read_file`, `list_files`,
      and `grep` are used.
- [ ] Confirm the review is still **usable** — a reviewer restricted to three tools
      must still produce a review with grounded findings, not a degraded artifact.
- [ ] Confirm `--tools` reaches the CLI as declared.
- [ ] If the review is materially degraded, stop and raise it with the Project
      Manager rather than widening the tool set unilaterally.
- [ ] Effort: 2

### Task E.5 — Verify and commit Part E

- [ ] Run `uv run pytest -q`. Full suite green.
- [ ] Run `uv run ruff format` then `uv run ruff check`.
- [ ] Commit: `fix(providers): restrict SDK review agents to declared tools`
- [ ] Effort: 1

---

## Slice Completion

### Task Z.1 — Success criteria sweep

- [ ] Walk the design's eleven Functional criteria and confirm each is demonstrated
      by a test or a recorded manual walkthrough:
  - [ ] 1, 2, 3 — A: merge-base file list matches `git diff --name-only
        <base>...HEAD`; both range forms pass through; nonexistent ref exits
        non-zero with no model call.
  - [ ] 4, 5, 6 — B: all-excluded and no-changes exit non-zero with distinct
        cases; both hold via `sq run` and with no rules directory.
  - [ ] 7, 8, 9 — C: `--diff`-only exits on verdict with a WARNING and the 10
        documented examples still work; failed save exits 1; `--no-save` is quiet.
  - [ ] 10 — D: subdirectory `cwd` yields a git-root jail; inputs open.
  - [ ] 11 — E: `tools` set to the declared list; `Bash` unavailable.
- [ ] Confirm the Technical criteria: no new `Verdict` member; one shared helper
      for D, not five copies; every new failure path exits non-zero **and** logs at
      WARNING or above; no test asserts on message text as logical structure.
- [ ] Effort: 2

### Task Z.2 — DEVLOG and status

- [ ] Write a DEVLOG entry per `prompt.ai-project.system.md`, section "Session
      State Summary".
- [ ] Mark this task file `status: complete` and set `dateUpdated`.
- [ ] Mark the slice complete in
      [916-slice.review-scope-correctness.md](project-documents/user/slices/916-slice.review-scope-correctness.md)
      and in the parent slice plan.
- [ ] Close issues #86, #89, #70, #62, #69 citing this slice. Handle #71 per B.8.
- [ ] Confirm [#90](https://github.com/ecorkran/squadron/issues/90) remains open —
      slice-less review artifact naming is deliberately not addressed here.
- [ ] Effort: 1
