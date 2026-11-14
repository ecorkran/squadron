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
reviewedSha: 7d41e55dffdccc54f40cece5968aa23ccf54f914
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
diffTruncated: false
effort: xhigh
turns: 33
promptTokens: 4244377
cachedTokens: 4022655
cacheWriteTokens: 221672
completionTokens: 86543
durationSeconds: 386.0
costUsd: 0.647497
costBasis: provider
runId: run-20261114-p6-1708bfe1
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Fix commit can read a reply from an earlier container step"
    location: "src/squadron/pipeline/models.py:67"
  - id: F002
    severity: concern
    category: correctness
    summary: "Issue-fetch refusals suggest input the fix command rejects"
    location: "src/squadron/pipeline/fix_issue.py:82"
  - id: F003
    severity: concern
    category: correctness
    summary: "Issue-file resolution ignores the `cwd` argument"
    location: "src/squadron/pipeline/fix_issue.py:100"
  - id: F004
    severity: concern
    category: correctness
    summary: "Agent-created paths reach git as glob pathspecs"
    location: "src/squadron/pipeline/actions/commit.py:167"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "Git state readers are imported and patched, not injected"
    location: "src/squadron/pipeline/fix_commit.py:86"
  - id: F006
    severity: note
    category: consistency-rot
    summary: "Three HEAD readers and four copies of the commit-to value list"
    location: "src/squadron/pipeline/fix_commit.py:75"
  - id: F007
    severity: note
    category: security-hygiene
    summary: "Fetched issue text decides what gets committed"
    location: "src/squadron/pipeline/fix_commit.py#fix_commit_plan"
  - id: F008
    severity: note
    category: test-debt
    summary: "Parity test depends on a private dispatch method"
    location: "tests/pipeline/test_fix_pipeline.py#_FakeAgent._execute"
  - id: F009
    severity: pass
    category: correctness
    summary: "The report contract agrees across the prompt, parser and run.md"
    location: "src/squadron/data/prompts/fix.md"
---

# Review: code — slice 423

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 31 successful tool call(s) of 32 made; 169218 of 169218 diff characters reached the model

## Findings

### [CONCERN] Fix commit can read a reply from an earlier container step

`results_in_current_step` keeps any key with no `:` whose suffix is decimal. Results inside a container body are keyed `"{inner_index}-{type}-{n}"` (executor.py:1890-1891, into `running_prior` seeded at 1819). Those keys pass the filter, so the docstring's claim that earlier steps are skipped holds only for top-level `step:` keys. The helper then sorts by action index alone, and `_request_from_results` takes the last `dispatch` result. If a fix step sits inside a loop or each body after an inner step whose dispatch is at action index 2 or later, the fix's own dispatch (index 1) sorts first and the commit parses the other reply. Top-level fix pipelines are not affected. Fix: order by execution position or exclude keys from other scopes, and add a test with a fix step inside a container.

### [CONCERN] Issue-fetch refusals suggest input the fix command rejects

`IssueTextLoader._fetch` builds a `PullRequestTarget` (the PR grammar in targets.py:34) and passes it to `select_remote`. For a bare `#301` with no served remote, or with several, the refusal carries hints from remotes.py:217 ("name the pull request by URL") and remotes.py:223 ("Name the repository explicitly, for example owner/repo#number"). `parse_issue_ref` accepts only `301` or `#301`, so the second hint leads to a second refusal and the first refers to the wrong kind of object. Fix: give issue lookups their own hints and add a test that asserts the fetch refusal text.

### [CONCERN] Issue-file resolution ignores the `cwd` argument

`load()` takes `cwd` and uses it for fetch, but `_read_file` drops it. When `io_dir` is None, `Path(issue_file)` resolves against the process working directory, while the git operations in `FixContextAction` use `context.cwd`. Production always passes `io_dir` (`io_dir()` in dispatch_io.py:112 defaults to cwd), so the branch is latent. The test `test_relative_path_resolves_under_cwd_without_io_dir` (tests/pipeline/test_fix_issue.py:68) cannot detect the difference: it calls `monkeypatch.chdir` to the same directory it passes as `cwd`. Fix: thread `cwd` through to `_read_file` and use different directories in the test.

### [CONCERN] Agent-created paths reach git as glob pathspecs

`_stage_and_commit` runs `git add -- <paths>` and `git commit -- <paths>` with no literal-pathspec handling. The fix commit is the first caller whose paths come from arbitrary files an agent created. Git treats `*`, `?` and `[` as pattern characters, so a file named like `report[1].md` either makes `git add` fail or matches a different path, and in the second case the literal file can be left out of the commit. Fix: use `git --literal-pathspecs` (or a `:(literal)` prefix) on the fix path, and add a test with bracket characters in a filename.

### [CONCERN] Git state readers are imported and patched, not injected

`fix_commit_plan` and `FixContextAction` call module-level helpers (`current_branch`, `read_head`, `changed_paths`) directly. The new tests patch those module attributes (tests/pipeline/test_fix_commit.py and tests/pipeline/actions/test_fix_context.py). The review rules treat that as a sign the dependency graph is inverted. The cf reader is injected correctly, so the git side is the gap. The existing commit action follows the same pattern, so this is also a consistency question. Fix: a small git-state protocol passed in as a parameter, with a fake in tests.

### [NOTE] Three HEAD readers and four copies of the commit-to value list

`_head_refusal` reads HEAD and words its failure as "unknown". `FixContextAction._run` and `fix_commit_args` in fix_prompt_args.py read HEAD again with different messages. The `CommitTo` values are listed again in steps/fix.py:55, commit_run_fix.py:80 and fix_context.py. One helper each would keep the wording and checks in step.

### [NOTE] Fetched issue text decides what gets committed

Issue bodies and comments can be written by anyone who can comment on the issue, and the prompt carries them to the agent. The fix commit then stages every changed path, with no allow-list like the glob check `guarded_commit` uses. The clean-tree check protects the start state only. The issue-text markers are also not escaped, so issue text containing `-----END ISSUE TEXT-----` can close the data block early. This may be an accepted risk under D3 and D5; the design should say so.

### [NOTE] Parity test depends on a private dispatch method

The fake agent calls `DispatchAction()._resolve_prompt`, a private method, behind a pyright ignore. A rename would break the tests without any product change. Test the prompt through a public path instead.

### [PASS] The report contract agrees across the prompt, parser and run.md

The prompt asks for `summary`, `failing_tests`, `failed_before_change` (true), `gates` (exit code 0) and `blocked`, and `parse_fix_report` checks the same fields in the same way. run.md has the `fix-context` section that tests/cli/test_run_md_actions.py checks for. The prompt holds exactly the two brace pairs the template test requires, and `render_fix_prompt` substitutes the issue text last, so braces inside the issue are not expanded. CI runs the whole `pytest` suite, so the new load test is not excluded.

### Run Digest

- Response length: 11194 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 33
- Tokens — prompt / cached / cache write / completion / reasoning: 4244377 / 4022655 / 221672 / 86543 / not computed
- Duration: 386.0 s
- Cost: $0.65 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
