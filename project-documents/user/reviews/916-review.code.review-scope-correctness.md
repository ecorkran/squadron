---
docType: review
layer: project
reviewType: code
slice: review-scope-correctness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/916-slice.review-scope-correctness.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260911
dateUpdated: 20260911
reviewedSha: 0aae0c8c7228a3e5bb8bcc5fa404d4589c88947b
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 31
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "Parametrized failed-save test passes for the wrong reason on 2 of 4 subcommands"
    location: "tests/cli/test_review_save_outcome.py#TestFailedSaveExitsOne"
  - id: F002
    severity: concern
    category: design
    summary: "`NO_CHANGES` folds \"git could not compute the range\" into the same member as \"range is genuinely empty\""
    location: "src/squadron/review/git_utils.py#assert_reviewable_scope"
  - id: F003
    severity: concern
    category: typing
    summary: "Save closures pass `SliceInfo | None` into a non-optional parameter — likely strict-pyright failure (unverified)"
    location: "src/squadron/cli/commands/review.py#review_slice"
  - id: F004
    severity: note
    category: performance
    summary: "Scope guard issues the identical `git diff --name-only` twice when no exclusion patterns apply"
    location: "src/squadron/pipeline/actions/review.py#ReviewAction._review"
  - id: F005
    severity: note
    category: design
    summary: "Step-supplied `diff` is silently overwritten when `slice` is also present — parity gap with the CLI"
    location: "src/squadron/pipeline/actions/review.py#ReviewAction._resolve_slice_inputs"
  - id: F006
    severity: note
    category: documentation
    summary: "`EmptyScopeCase` docstring says \"two\" cases; enum has three; `excluded_count` semantics drift in one branch"
    location: "src/squadron/review/git_utils.py#EmptyScopeCase"
  - id: F007
    severity: note
    category: design
    summary: "Setting `tools` changes the meaning of `allowed_tools` for every SDK agent, not just reviews"
    location: "src/squadron/providers/sdk/provider.py#ClaudeSDKProvider.create_agent"
  - id: F008
    severity: note
    category: testing
    summary: "Conditional assertion silently skips when no rules directory resolves"
    location: "tests/cli/test_review_scope.py#TestDiffSpecNormalizationAtCLI.test_bare_ref_reaches_both_consumers_normalized"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Git invocations are now bounded, with the timeout observable at WARNING"
    location: "src/squadron/review/git_utils.py#run_git"
  - id: F010
    severity: pass
    category: security
    summary: "`tools` + `allowed_tools` both set — verified against the installed SDK"
    location: "tests/review/test_template_sdk_regression.py#TestDeclaredToolsAreTheWholeToolSet"
  - id: F011
    severity: pass
    category: correctness
    summary: "Diff-spec normalization check order is correct and pinned by a test"
    location: "src/squadron/review/git_utils.py#normalize_diff_spec"
  - id: F012
    severity: pass
    category: design
    summary: "`SaveOutcome` replaces the success-initialized boolean with a tested four-state model"
    location: "src/squadron/cli/commands/review.py#SaveOutcome"
  - id: F013
    severity: pass
    category: testing
    summary: "Autouse fixture restores logger state mutated by `-v` reviews"
    location: "tests/conftest.py#restore_agent_logger_state"
---

# Review: code — slice 916

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Parametrized failed-save test passes for the wrong reason on 2 of 4 subcommands

`test_oserror_on_save_exits_one` builds a `slice_info` fixture with `"design_file": None`, but `review_slice` exits 1 at its `if not slice_info["design_file"]` guard (cli/commands/review.py) before `_run_review_command` or the save ever runs — so the "slice" parametrization never exercises a failed write. `review_tasks` hits the same `design_file` guard (its `task_files` check passes; the design check does not), so "tasks" is also vacuous. The "code" case does not patch `assert_reviewable_scope`, so it runs a real `git diff --name-only HEAD~1...HEAD` against the host repository (CliRunner does not chdir, and `get_config` is unpatched in this test) — whether the exit 1 comes from the OSError-on-save path or from the scope guard depends on the host repo's last commit. Only "arch" reliably tests the documented intent ("an attempted write that failed exits 1 regardless of a PASS verdict"). Since all paths exit 1, the assertions pass regardless. Fix: give the fixture a real `design_file`, patch `assert_reviewable_scope` for the code case, and assert `mock_run_review` was called (or assert on the "Review not saved" rich output) so a wrong-reason exit fails the test.

### [CONCERN] `NO_CHANGES` folds "git could not compute the range" into the same member as "range is genuinely empty"

The `EmptyScopeCase` docstring establishes the contract: "callers branch on this field rather than on message text," and `EmptyScopeError` "carries the case … so consumers never parse the message." Yet the first branch of `assert_reviewable_scope` maps `_changed_paths(...) is None` — which covers both a non-zero git exit (bad ref, refused range) and git being unavailable — to `NO_CHANGES`, whose documented meaning is "the range itself contains no changed files — wrong base, an already-merged branch, or a typo." Two different diagnoses now share one enum value and are distinguishable only by message text, exactly what the taxonomy was built to prevent. A future consumer doing `if exc.case is NO_CHANGES: omit_review()` (the "already merged → skip" remedy the messages suggest) would also silently skip on a broken git invocation. Consider a distinct member (e.g. `UNCOMPUTABLE`) or narrowing what `_changed_paths` collapses into `None`.

### [CONCERN] Save closures pass `SliceInfo | None` into a non-optional parameter — likely strict-pyright failure (unverified)

`_save_and_report` is declared `def _save_and_report(result, review_type, slice_info: SliceInfo, *, ...)`, but the `save` lambdas capture the `slice_info: SliceInfo | None` variable and pass it through un-narrowed: `save=lambda: _save_and_report(result, "slice", slice_info, ...)` in `review_slice`, the equivalent lambda in `review_code`, and `_save_part` in `review_tasks`. The `persistable=slice_info is not None` argument gives a checker no narrowing it can apply inside the closure, so the captured type at the lambda's declaration point is `SliceInfo | None`. Under the project's strict pyright gate (`include = ["src"]`, `typeCheckingMode = "strict"`), this should produce an `reportArgumentType` error. Runtime is safe — `save` is only invoked when `persistable` is true — so this is a static-typing issue, not a behavior bug. I could not run pyright in this review to confirm; please verify with `uv run pyright`. If it errors, bind a non-optional local (e.g. `info = slice_info` under a guard) before constructing the closure.

### [NOTE] Scope guard issues the identical `git diff --name-only` twice when no exclusion patterns apply

In the pipeline path, `diff_exclude_patterns` comes only from step params, so `exclude_patterns` is frequently `None` — yet `assert_reviewable_scope` then runs `_changed_paths(diff, cwd, None)` twice with identical arguments (two full subprocess spawns), discards the returned list, and `extract_diff_paths` recomputes it a third time inside the rules branch. A one-line short-circuit (`filtered = unfiltered if not exclude_patterns else _changed_paths(...)`) removes the duplicate without touching the guard's placement rationale.

### [NOTE] Step-supplied `diff` is silently overwritten when `slice` is also present — parity gap with the CLI

The CLI gives an explicit `--diff` precedence over slice-derived ranges (`if not diff: diff = resolve_slice_diff_range(...)` in `review_code`), but the pipeline runs `_resolve_slice_inputs` whenever `slice` is present and `"input" not in inputs`, and the "code" entry in `TEMPLATE_INPUTS` unconditionally overwrites `inputs["diff"]` with the slice-derived range — discarding the step-supplied value the new code just normalized. The behavior is pre-existing, but the diff's own comment frames this work as "interface parity is the point" (issue #89), and this asymmetry (`sq review code 118 --diff main` keeps the explicit range; `template: code, slice: 194, diff: main` does not) remains in the very function the comment anchors.

### [NOTE] `EmptyScopeCase` docstring says "two" cases; enum has three; `excluded_count` semantics drift in one branch

The class docstring opens "Two different operator errors with two different fixes," but three members are defined — `INVALID_EXCLUDE_PATTERN` was added without updating the lead-in. Separately, in the `INVALID_EXCLUDE_PATTERN` branch of `assert_reviewable_scope`, `excluded_count=len(unfiltered)` records the count of files *in range*, none of which were excluded; the field's name is only accurate in the `ALL_EXCLUDED` branch.

### [NOTE] Setting `tools` changes the meaning of `allowed_tools` for every SDK agent, not just reviews

`create_agent` serves all SDK agents (spawn, pipelines), not only reviews. Configs that previously used `allowed_tools` as "pre-approve these, keep the rest permission-gated" now have the rest removed from the tool universe entirely. The direction is the security-correct one for #69 and the shipped templates are pinned by tests, but this semantic change to a shared config field deserves a callout in release/config documentation.

### [NOTE] Conditional assertion silently skips when no rules directory resolves

The test's second assertion is wrapped in `if mock_extract.call_args is not None:`. `resolve_rules_dir` returns None on a clean machine for the tmp repo fixture (no `.claude/rules` there; `~/.config/squadron/rules` is machine-specific), so the "both consumers see the same normalized range" assertion only runs on machines that happen to have a user rules directory. Consider patching `resolve_rules_dir` to a real tmp dir so the extraction-side normalization is always asserted.

### [PASS] Git invocations are now bounded, with the timeout observable at WARNING

`timeout=GIT_COMMAND_TIMEOUT_SECONDS` bounds every call routed through `run_git`; `TimeoutExpired` is logged at WARNING (satisfying the failure-mode-observability rule) and returned as the same "git could not answer" `None` signal every caller already handles. The `OSError` branch carries a justification comment consistent with the project's exception-handling rule. Rerouting `extract_diff_paths` (review/rules.py) through `run_git` closes the one always-run path that previously called `subprocess.run` directly. Tests pin both the timeout pass-through (`kwargs["timeout"] == GIT_COMMAND_TIMEOUT_SECONDS`) and the WARNING, and the stderr-vs-stdout discipline for the timeout log is correct.

### [PASS] `tools` + `allowed_tools` both set — verified against the installed SDK

I confirmed against the vendored `claude_agent_sdk` 0.1.38 that `ClaudeAgentOptions` has both `tools` and `allowed_tools`, and that the subprocess transport maps `options.tools` → `--tools` (a list of zero/one/more names) while `allowed_tools` only maps to `--allowedTools` — i.e., the fix genuinely constrains the CLI's tool universe rather than only pre-approving. The new tests assert `"Bash" not in options.tools` for the code template, constrain `tools` across every shipped template, verify `allowed_tools` is still set, and pin that an unmapped canonical name raises `ProviderError` rather than silently widening — the loud-failure property `translate_tool_names` already promised.

### [PASS] Diff-spec normalization check order is correct and pinned by a test

Testing `THREE_DOT in spec or TWO_DOT in spec` in that order is correct (every three-dot spec contains a two-dot substring), and `tests/review/test_git_utils.py::TestNormalizeDiffSpec` pins the order with the `origin/main...HEAD` case. The bare-ref rewrite to `<ref>...HEAD` gives merge-base semantics, explicit ranges pass through untouched, and the `NotAGitRepositoryError`/`RefNotFoundError` split distinguishes "git couldn't run" from "no such ref" before any model spend — with the two cases asserted both by `ref` field and by `isinstance` disjunction.

### [PASS] `SaveOutcome` replaces the success-initialized boolean with a tested four-state model

The enum closes the "reported success for a write that was never attempted" hole (issue #70) with an explicit space (SAVED/SUPPRESSED/NOT_PERSISTABLE/UNSAVED), a single severity map (`_OUTCOME_SEVERITY`) rather than scattered comparisons, and `_exit_on` precedence documented in its docstring: FAIL=2, UNSAVED=1, NOT_PERSISTABLE exits on verdict. The multi-part tasks fold (`_worst_outcome`) keeps "the worst thing that happened to any part" semantics, and the `_save_part` default-arg binding correctly captures per-iteration values. `TestSaveOutcomeResolution` covers all four outcomes plus worst-case folding, and `TestDocumentedInvocations` pins the exit-0 behavior of the documented `--diff`-only forms, including the stderr discipline that keeps `--output json` parseable (asserted via `json.loads(result.stdout)`).

### [PASS] Autouse fixture restores logger state mutated by `-v` reviews

`_configure_agent_logging` mutates three module loggers process-wide (level + stderr handler) with no teardown; the fixture snapshots level and handlers before each test and restores them in place (`logger.handlers[:] = handlers`) after — removing a real class of cross-test failure where a caplog assertion sees a level an earlier CLI invocation set. Correctly scoped as `autouse` since the mutation can come from any test that invokes a review command.
