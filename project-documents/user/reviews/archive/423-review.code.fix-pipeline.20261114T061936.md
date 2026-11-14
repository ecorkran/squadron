---
docType: review
layer: project
reviewType: code
slice: fix-pipeline
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/423-slice.fix-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261113
dateUpdated: 20261113
reviewedSha: b33973508e4f7f7e56ed4612227b157298816ab4
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 39
diffTruncated: false
effort: xhigh
turns: 40
promptTokens: 2701742
cachedTokens: 2517837
cacheWriteTokens: 183871
completionTokens: 59210
durationSeconds: 262.0
costUsd: 0.465663
costBasis: provider
runId: run-20261114-p6-1708bfe1
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`sq _commit --subject fix` silently discards most of its other flags"
    location: "src/squadron/cli/commands/commit_run.py:75-88"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "Fix-branch checks are duplicated, with the same messages in three places"
    location: "src/squadron/pipeline/actions/fix_context.py#FixContextAction._branch_problem"
  - id: F003
    severity: concern
    category: test-debt
    summary: "Unreadable-git failure branches have no test"
    location: "src/squadron/pipeline/actions/fix_context.py#FixContextAction._dirty_tree"
  - id: F004
    severity: note
    category: documentation-drift
    summary: "The fix report parser reads the first JSON object, but the design says the last"
    location: "src/squadron/pipeline/fix_report.py#parse_fix_report"
  - id: F005
    severity: note
    category: correctness
    summary: "`--commit-to`, `--start-head` and `--start-branch` are not validated at the CLI boundary"
    location: "src/squadron/cli/commands/commit_run_fix.py:86-87"
  - id: F006
    severity: note
    category: documentation-drift
    summary: "The executor comment says the fix pipeline makes no cf call"
    location: "src/squadron/pipeline/executor.py:582-586"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "The `build_context` operation name is defined three times"
    location: "src/squadron/pipeline/actions/fix_context.py:48"
  - id: F008
    severity: note
    category: architectural-decay
    summary: "The pipeline imports the benchmark package to render issues"
    location: "src/squadron/pipeline/fix_issue.py"
  - id: F009
    severity: note
    category: type-contract-debt
    summary: "Test helpers drop type information and fixtures are suppressed"
    location: "tests/pipeline/test_fix_commit.py#_plan"
---

# Review: code — slice 423

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 39 successful tool call(s) of 39 made; 158738 of 158738 diff characters reached the model

## Findings

### [CONCERN] `sq _commit --subject fix` silently discards most of its other flags

`--message`, `--path`, `--slice`, `--plan`, `--template` and `--round` are copied into `params` for any subject. A fix commit never reads them. `CommitAction._commit` sends `CommitSubject.FIX` to `_fix_commit` (src/squadron/pipeline/actions/commit.py:99-100), which uses only the prior outputs and the report. So `sq _commit --subject fix --message "x" ...` commits the report's summary and drops the message. `--slice` is checked only when malformed: `commit_target_from_params` (commit.py:96) rejects `--slice abc`, but `--slice 5` is accepted and then ignored. `check_fix_flags` (commit_run_fix.py:52-62) rejects fix-only flags on other subjects but does not reject these on the fix subject. The rendered prompt-only commands never pass them, so this is reachable only by hand. It is still the silent-discard pattern the project rules forbid. Reject these flags for `CommitSubject.FIX` in `check_fix_flags`.

### [CONCERN] Fix-branch checks are duplicated, with the same messages in three places

The detached-HEAD and integration-target checks are written three times. `_branch_problem` (fix_context.py:134 and :139) and `_branch_refusal` (fix_commit.py:80 and :86) both check for detached HEAD and for a branch that is not the target, with the same wording. A third detached-HEAD check with the same wording is in `fix_commit_args` (src/squadron/pipeline/fix_prompt_args.py:54). The copies have already diverged: `_branch_refusal` also checks the branch against `start_branch`, and the prompt-only copy raises where the others return a string. A change to the rule or its wording has to land in all three. Move the check into one function that takes the branch, the destination and the cf reader, and call it from all three places.

### [CONCERN] Unreadable-git failure branches have no test

`_dirty_tree` returns "cannot read the working tree state" (fix_context.py:125). The commit plan returns "cannot list the changed paths" (src/squadron/pipeline/fix_commit.py:121) when `git status` fails. Neither branch is tested. `test_fix_context.py` covers a dirty tree and an unreadable HEAD, and `test_fix_commit.py` covers an unreadable HEAD, branch and target, but nothing makes `changed_paths` fail. The failure-mode rule requires a test that asserts each I/O failure produces its observable signal. Add one for each site: monkeypatch `changed_paths` to return an error string, then assert the refusal text and the WARNING record.

### [NOTE] The fix report parser reads the first JSON object, but the design says the last

`parse_fix_report` calls `extract_json_object`, which returns the first decodable object (src/squadron/pipeline/actions/dispatch_io.py:56-72). The `fix_report.py` docstring and slice 423 D4 both say the report is "the JSON object an agent ends its reply with". The prompt does not say that. `fix.md` tells the agent "the first one found is read as the report" and to write no other object. So the code and prompt agree, and the design and docstring are the outliers. The risk is an agent that quotes a JSON object before its report. The refusal then names a field of the wrong object, and the real report is never read. Decide which contract holds. If first-object stands, correct the docstring and the design. If last-object is intended, change the parser and add a test with an earlier object.

### [NOTE] `--commit-to`, `--start-head` and `--start-branch` are not validated at the CLI boundary

`fix_prior_outputs` copies `--commit-to` into the fix-context result without checking it against `CommitTo`. `check_fix_flags` rejects only `None`, so `--start-head ""` or `--start-branch ""` passes. A bad destination then fails later in `_request_from_results` (src/squadron/pipeline/fix_commit.py:160) with "the fix-context result has an unusable value". That message describes a result the user never produced. Validate the three values in `fix_prior_outputs`, using the same `CommitTo` and non-empty checks the step uses, and raise `FixFlagsError` there.

### [NOTE] The executor comment says the fix pipeline makes no cf call

The comment says a cf-free pipeline, "(#288, the fix pipeline)", "makes no cf call". Under `commit-to: target` the fix pipeline does call cf, because `_branch_problem` and `_branch_refusal` call `read_integration_target`. The gate itself is correct: `FixStepType.needs_context_forge` returns False (src/squadron/pipeline/steps/fix.py:77), and the fix pipeline never uses `_project`. Only the comment is wrong. Say that `commit-to: current` makes no cf call, or drop the fix pipeline from the example.

### [NOTE] The `build_context` operation name is defined three times

`fix_context.py` adds `BUILD_CONTEXT_OPERATION = "build_context"`. `cf_op.py:37` already defines the same value as a class constant, and `dispatch.py:845` compares against the bare string. The project rule is one value, one source. Reuse the existing definition in `fix_context.py` and `dispatch.py`.

### [NOTE] The pipeline imports the benchmark package to render issues

`fix_issue.py` imports `render_issue` from `squadron.benchmark.issue_freeze`. The production fix path therefore depends on the benchmark package. There is no cycle today: `issue_freeze` imports only `squadron.codehost` and `squadron.metrology`. The dependency still points the wrong way for a product path. Move `render_issue` into a shared module that both the benchmark and the fix pipeline import.

### [NOTE] Test helpers drop type information and fixtures are suppressed

`_plan` returns `object`, and `_expect_plan` and `_expect_refusal` take `object`, so each test narrows by hand. Two fixtures have no annotations and are silenced with `# type: ignore[no-untyped-def]`: `in_repo` in `tests/cli/test_fix_commands.py` and `_fake_cf` in `tests/pipeline/test_fix_prompt_parity.py`. Those suppressions hide the gaps from pyright strict. Annotate the fixtures as `Iterator[Path]` and `Iterator[None]`, and type `_plan` as `FixCommitPlan | FixCommitRefusal`.

### Run Digest

- Response length: 10363 chars
- Response is newline-free: no
- Tool calls made: 39
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 40
- Tokens — prompt / cached / cache write / completion / reasoning: 2701742 / 2517837 / 183871 / 59210 / not computed
- Duration: 262.0 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
