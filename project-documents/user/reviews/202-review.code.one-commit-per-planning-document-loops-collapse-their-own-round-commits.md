---
docType: review
layer: project
reviewType: code
slice: one-commit-per-planning-document-loops-collapse-their-own-round-commits
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: 5de98bf11c1c5dcd37b61bc83787ebdcd2e29952
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 74083
cachedTokens: 3232
cacheWriteTokens: 70849
completionTokens: 3348
durationSeconds: 27.1
costUsd: 0.322442
costBasis: provider
squadronVersion: 0.24.12
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "A timed-out `update-ref` can crash a completed loop, contradicting the \"never changes status\" contract"
    location: "src/squadron/pipeline/executor.py#_execute_loop_body"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "Executor loop code keeps growing; the new split adds a 20-keyword pass-through"
    location: "src/squadron/pipeline/executor.py#_run_loop_rounds"
  - id: F003
    severity: concern
    category: architectural-decay
    summary: "Duplicated git-failure detail extraction"
    location: "src/squadron/pipeline/loop_collapse.py:70-76"
  - id: F004
    severity: note
    category: architectural-decay
    summary: "`loop_collapse.py` exceeds the ~300-line guideline"
    location: "src/squadron/pipeline/loop_collapse.py"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "Lazy import to break a state/ledger cycle"
    location: "src/squadron/pipeline/loop_ledger.py#_stored_ledger"
  - id: F006
    severity: note
    category: error-handling-observability
    summary: "Fallback to a fresh ledger when run state is missing"
    location: "src/squadron/pipeline/loop_ledger.py#_stored_ledger"
  - id: F007
    severity: pass
    category: test-debt
    summary: "Collapse safety design and test coverage"
    location: "tests/pipeline/test_loop_collapse.py"
---

# Review: code — slice 202

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] A timed-out `update-ref` can crash a completed loop, contradicting the "never changes status" contract

The docstring says the collapse never changes the loop's status. But `collapse_loop_commits` is documented to let `GitStateUnknownError` propagate, and `_execute_loop_body` calls `collapse_completed_loop` via `asyncio.to_thread` with no handler. A timeout on either `update-ref` therefore escapes after the loop has already COMPLETED, and the executor never records or returns that step.

Other uncaught paths exist as well:
- `int(run_checked(...))` in `_range_problem` raises `ValueError` if git prints something unexpected.
- `collapse_message` raises `ValueError` when the params name no subject.

The error is logged at ERROR in `_update_ref`, so it isn't silent. But the executor should deliberately decide what happens. Either catch it at this process-level boundary, log it, and keep COMPLETED, or document and test that a state-unknown ref aborts the run. No test covers the executor's behaviour in this case.

### [CONCERN] Executor loop code keeps growing; the new split adds a 20-keyword pass-through

`_execute_loop_body` now forwards about 19 keyword arguments one-for-one to `_run_loop_rounds`. That adds a second wrapper layer to an already very large module and function. Ledger setup, the rounds, and the collapse are three concerns. Consider a small context object for the shared arguments, or move the ledger lifecycle (start, attach, collapse) into `loop_ledger` or `loop_collapse` so the executor makes one call.

The condition `if ledger is not None and commit_params is not None and result.status == ExecutionStatus.COMPLETED:` also exceeds 88 characters and repeats a None-check. `ledger` is only non-None when `commit_params` is, so one check would do. Several lines in `loop_collapse.py` and its tests run over 88 characters too. Run `ruff format` and `ruff check` to confirm.

### [CONCERN] Duplicated git-failure detail extraction

The expression `(result.stderr.strip() if result is not None else "") or "timed out or could not run"` appears three times: in `run_checked`, in `_is_ancestor`, and in `_git_failed`. Extract one helper. The literal is also a scattered string that should be defined once.

### [NOTE] `loop_collapse.py` exceeds the ~300-line guideline

The file is about 330 lines and mixes proof checks, message composition, and the git writes. Splitting the proof checks into their own module would match the SRP guidance. This is not blocking.

### [NOTE] Lazy import to break a state/ledger cycle

The function-level import of `StateManager` avoids a cycle (`state` imports `loop_ledger`, which needs `state`). It is documented, so acceptable. It also instantiates `StateManager` directly instead of receiving it, which is a mild DIP smell. Passing in a ledger-lookup callable would remove both the cycle and the direct instantiation.

### [NOTE] Fallback to a fresh ledger when run state is missing

A missing state file on resume logs a warning and opens a fresh ledger. The fresh ledger only claims commits made from then on, so the collapse is conservative. This is observable and safe. A test asserting the warning would complete the failure-mode coverage.

### [PASS] Collapse safety design and test coverage

The collapse is conservative:
- It reuses the old tree and writes a backup ref.
- It swaps HEAD with compare-and-swap.
- It checks branch, ancestry, merges, count, and remote containment.
- Each refusal is logged once at WARNING.

The tests use real git repositories and cover:
- each refusal reason;
- operator edits surviving the collapse;
- the compare-and-swap race;
- pause and resume;
- the pre-ledger state record;
- agent commits;
- the `update-ref` timeout.

The HEAD-stamp chaining in `head_stamp.py` and `loop_ledger.py` is clearly reasoned and tested.

### Run Digest

- Response length: 4488 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 74083 / 3232 / 70849 / 3348 / not computed
- Duration: 27.1 s
- Cost: $0.32 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response

- **F001 — fixed.** `GitStateUnknownError` propagating is deliberate: a timed-out ref write leaves HEAD unknown, so the run stops. The executor call site now says so, and `test_a_state_unknown_ref_write_stops_the_run_instead_of_continuing` pins it. The `rev-list --count` parse failure is now a git-failed outcome, and a loop with no commit subject is a refusal (`CommitTargetError`), so neither raises.
- **F002 — deferred.** The keyword pass-through is the existing loop signature; reworking the executor's loop code is its own slice.
- **F003 — fixed.** One `_failure_detail` helper and one `_NO_GIT_OUTPUT` constant replace the three copies in `loop_collapse.py`.
- **F004 — accepted.** Already recorded as a deviation in the task file; splitting the file is churn.
- **F005 — accepted.** The lazy import breaks a real cycle and is documented.
- **F006 — fixed.** `test_a_resume_with_no_run_state_warns_and_opens_a_fresh_ledger` asserts the warning and the fresh ledger.
