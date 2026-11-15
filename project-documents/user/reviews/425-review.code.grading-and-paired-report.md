---
docType: review
layer: project
reviewType: code
slice: grading-and-paired-report
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/425-slice.grading-and-paired-report.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 3efff6d06307993923525813c2680e71d5f4be42
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
diffTruncated: false
effort: xhigh
turns: 17
promptTokens: 3730987
cachedTokens: 3372638
cacheWriteTokens: 358327
completionTokens: 54670
durationSeconds: 243.9
costUsd: 0.797237
costBasis: provider
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "Grading review never checks whether the diff reached the model"
    location: "src/squadron/benchmark/grade_review.py:202-223"
  - id: F002
    severity: concern
    category: correctness
    summary: "Suppression count falls back to `HEAD` instead of failing"
    location: "src/squadron/benchmark/grade_checks.py:171"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "Tree-read process failures escape as crashes instead of absences"
    location: "src/squadron/benchmark/tree_reader.py:74"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "Dropped off-scale findings are invisible in the report"
    location: "src/squadron/benchmark/bench_report.py#_findings_rows"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "Code-template prompt still tells the no-tools model to run git"
    location: "src/squadron/review/builders/code.py:91-98"
  - id: F006
    severity: note
    category: error-handling-observability
    summary: "Parse errors always blame the reference tree"
    location: "src/squadron/benchmark/python_injection.py#_parse"
  - id: F007
    severity: note
    category: dependency-config-debt
    summary: "Pyright excludes tests, which this slice relies on"
    location: "pyproject.toml:107"
---

# Review: code — slice 425

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 16 successful tool call(s) of 16 made; 595980 of 595980 diff characters reached the model

## Findings

### [CONCERN] Grading review never checks whether the diff reached the model

`review_tree_diff` never reads `result.diff_injection`. That field is always set when a diff input is given (`src/squadron/review/models.py:273`), and `DiffInjection.truncated` reports partial delivery (`models.py:150`). Two failure cases pass silently into a grade:

- If `git diff` fails inside the review call, `_run_git_diff` returns `None` after a WARNING (`src/squadron/review/review_client.py:765-770`). The injection code treats that as "nothing changed" and records `DiffInjection(total_chars=0, injected_chars=0)` (`review_client.py:649-652`). The model reviews an empty diff, and the outcome is stored as a valid graded result.
- A diff cut by `review.max_file_size_bytes` or the total injection cap (`review_client.py:654-667`) is recorded as a full review. `ReviewOutcome` has no field for the cut, so findings on a partial diff are compared with findings on full ones.

The failure is logged, but the record says the grade succeeded. Fix: raise `ReviewFailed` when the subject diff is non-empty and `total_chars` is 0. Carry `truncated` and the cut-file list into `ReviewOutcome` and `ReviewSummary`, so the report shows them or the grade refuses them.

### [CONCERN] Suppression count falls back to `HEAD` instead of failing

`count_added_suppressions` uses `run.head_sha or "HEAD"`. The same file's `take_snapshot` refuses the identical unset state with `ValueError` (`grade_checks.py:122-123`). The call order (`apply_subject` sets `head_sha` first) keeps the fallback unused today. If the order changes, suppressions would be counted against whatever HEAD the sandbox has, with no error. The project rule is no silent fallback values. Fix: apply the same guard as `take_snapshot`.

### [CONCERN] Tree-read process failures escape as crashes instead of absences

`GitTreeReader._git` catches only `ProcessTimedOutError`. `SubprocessRunner` also raises `ProcessNotFoundError` and `ProcessCwdNotFoundError` (`src/squadron/core/process_runner.py:42, 50, 151-153`). `grade_run.run_git` maps all three to `GitFailure` (`src/squadron/benchmark/grade_run.py:27`).

In `grade_one`, the inner handler catches only `(GradeAbsent, TreeReadError)` (`src/squadron/benchmark/grade_one.py:146`), and the outer handler catches only `(EnvironmentResolutionError, SandboxError)` (`grade_one.py:169`). If the user's checkout disappears or git cannot start during a read, the exception escapes and aborts the whole grade invocation. `_as_absence` in `grade_one.py` says a tree-read failure is a harness absence, `reference_unreadable`, so that record should be written and the run should continue. Fix: catch `_PROCESS_FAILURES` in `_git` and raise `TreeReadError`.

### [CONCERN] Dropped off-scale findings are invisible in the report

`_findings` in `grade_review.py` drops off-scale severities with a WARNING and counts them in `unnormalized_count`. That count is stored on each `ReviewSummary` (`src/squadron/metrology/grade_models.py:220`). Nothing in the report reads it. `FindingsRow` has no field for it, and neither `_findings_rows` nor `bench_report_render.py#_findings` mentions it. So `mean_total` and the per-severity means silently exclude those findings, and a reader of `sq benchmark report` cannot see that. Fix: add an `unnormalized` field to `FindingsRow` and print it beside the totals.

### [NOTE] Code-template prompt still tells the no-tools model to run git

With `no_tools`, the system prompt gets `NO_TOOLS_NOTICE` (`review_client.py:118-123`), which forbids tool calls. The code builder's user prompt still says "Run `git diff …` to identify changed files" in the diff branch. The notice likely wins in practice, and the `review_client.py` comment cites a walkthrough. The two instructions still contradict each other. Consider a no-tools flag in the builder.

### [NOTE] Parse errors always blame the reference tree

`_parse` always builds its message as `parse {path} at the reference`. `_added_imports` also parses the start commit's conftest through it, so a start-side parse failure is reported as a reference failure. This is a diagnostic issue only.

### [NOTE] Pyright excludes tests, which this slice relies on

`[tool.pyright] include = ["src"]` differs from the required `["src", "tests"]`. The comment ties this to issue #50. Most of this slice's new code is test code, so type errors in tests are not gated. The deviation is documented, so this is a NOTE and not a finding against the diff.

### Run Digest

- Response length: 8941 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 3730987 / 3372638 / 358327 / 54670 / not computed
- Duration: 243.9 s
- Cost: $0.80 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response

Round 4 of slice 425's code review. Dispositions:

- **F001 fixed.** `review_tree_diff` raises `ReviewFailed` (ERROR log, cost carried) when `diff_injection.truncated`. The empty-diff case is not treated as a failure: an empty injection cannot be told apart from a subject that changed nothing, which is a valid zero-finding review.
- **F002 fixed.** `count_added_suppressions` uses the same committed-head guard as `take_snapshot` (`_committed_head`).
- **F003 fixed.** `GitTreeReader._git` catches `PROCESS_FAILURES` (not found, cwd not found, timeout) and raises `TreeReadError`; `grade_run` now imports the same tuple.
- **F004 fixed.** `FindingsRow.unnormalized` carries the dropped off-scale count and the report line prints it.
- **F005 not changed.** The no-tools notice wins in practice (slice 425 walkthrough). The builder prompt wording is left for the review-prompt work.
- **F006 fixed.** `_parse` names the tree (`REFERENCE_TREE`, `START_TREE`) the source came from.
- **F007 not changed.** The pyright `include` deviation is documented and tracked by #50.
