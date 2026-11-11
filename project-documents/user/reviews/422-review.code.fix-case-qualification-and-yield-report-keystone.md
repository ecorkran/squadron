---
docType: review
layer: project
reviewType: code
slice: fix-case-qualification-and-yield-report-keystone
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261111
dateUpdated: 20261111
reviewedSha: ca3defa5e4df3d71f69a0425b5c6cea70f78947b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
diffTruncated: false
effort: xhigh
turns: 16
promptTokens: 2120368
cachedTokens: 1817579
cacheWriteTokens: 302775
completionTokens: 64190
durationSeconds: 321.1
costUsd: 0.669926
costBasis: provider
runId: run-20261111-p6-62b55a9e
squadronVersion: 0.24.26
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "Systemic harness failures continue the build, while a missing gh halts it"
    location: "src/squadron/benchmark/qualify_sandbox.py:102"
  - id: F002
    severity: concern
    category: correctness
    summary: "Bare and qualified references to one issue count as two issues"
    location: "src/squadron/benchmark/fix_discovery.py:151"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "Try/except without a log or a justifying comment"
    location: "src/squadron/benchmark/pytest_trace/squadron_fixcase_patches.py:142"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "github_cli.py is 697 lines"
    location: "src/squadron/codehost/github_cli.py"
  - id: F005
    severity: concern
    category: architectural-decay
    summary: "Squadron-specific exemption hardcoded in the shared fairness rule"
    location: "src/squadron/benchmark/trace_verdict.py:26"
  - id: F006
    severity: note
    category: performance-resource
    summary: "get_issue re-requests the last finished connection on each remaining iteration"
    location: "src/squadron/codehost/github_cli.py#GitHubCli.get_issue"
  - id: F007
    severity: note
    category: other
    summary: "Git timeout for the sandbox command halved; discovery now inherits 30 s"
    location: "src/squadron/cli/commands/benchmark_common.py#git_output"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "Two classes named EnvironmentIdentity"
    location: "src/squadron/metrology/benchmark_environment.py"
  - id: F009
    severity: note
    category: type-contract-debt
    summary: "Tests bypass strict typing with object, Any and ignores"
    location: "tests/benchmark/test_python_fairness.py:112"
  - id: F010
    severity: note
    category: type-contract-debt
    summary: "`_new_record` passes untyped keywords into model_validate"
    location: "src/squadron/benchmark/qualify_types.py:126"
  - id: F011
    severity: note
    category: correctness
    summary: "An added autouse fixture passes classification"
    location: "src/squadron/benchmark/diff_classify.py:113"
  - id: F012
    severity: note
    category: test-debt
    summary: "Load test asserts a loose bound on scripted responses"
    location: "tests/load/test_github_issue_paging.py#test_an_issue_filling_every_allowed_page_is_fetched_whole_within_budget"
  - id: F013
    severity: note
    category: other
    summary: "Coverage and what was not checked"
    location: "unverified"
---

# Review: code — slice 422

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 15 successful tool call(s) of 15 made; 500709 of 500709 diff characters reached the model

## Findings

### [CONCERN] Systemic harness failures continue the build, while a missing gh halts it

`qualify_in_sandbox` records `MissingHarnessHomeError`, `MissingHarnessToolError` (line 102), and the `INSTALLER_MISSING` and `INSTALL_TIMEOUT` resolution reasons (line 70, used at lines 85–95) as per-candidate `harness_error` records, and the build moves on. `run_pre_sandbox_stages` does the opposite for a missing `gh` (`src/squadron/benchmark/qualify_stages.py:177`): it raises `BuildHalted`, with the comment "every later candidate would fail the same way." A missing `uv`, a missing `HOME` (`scrubbed_env.py:47`), or a missing harness tool has the same systemic cause. Today, a run with no `uv` on PATH logs one ERROR per candidate, stores a `harness_error` for each, and `build_command` exits 0 with "no qualified cases: no case set written." The failure is visible in the log, but it reads like N ordinary candidate outcomes. Pick one policy: systemic harness-environment errors halt the build the way `gh` does, and per-candidate faults (a timeout, one bad overlay) stay as records.

### [CONCERN] Bare and qualified references to one issue count as two issues

`_closers_by_issue` (lines 151–156) and `_rejection_for` (line 191) key references by `(repository, number)`. A bare `#13` has repository `None` (`_references_in`, line 123). A commit with `Fixes #13` and another with `Fixes acme/widgets#13` for the same repository therefore count as closers of two different issues. Each count is 1, so neither gets `multiple_closing_commits`, and both become candidates, which duplicates the case for one issue. The D1 rule exists to stop exactly this. Normalize bare references to the checkout's own repository before counting. The existing test only covers repeated use of one spelling. The impact requires mixed spellings in the history, which is why this is a CONCERN and not a FAIL.

### [CONCERN] Try/except without a log or a justifying comment

`_record_dotted` catches `(ImportError, AttributeError, ValueError)`, records the patch as `unresolved`, and returns, with no `logger.exception` and no inline comment. The project rule requires one or the other. Mitigation: the wrapper calls the original `setattr`/`delattr` afterwards, and that call raises the real error, so nothing is hidden. The same file's `_resolve_dotted` has an `except ImportError: continue` with no comment either. Add the justifying comment.

### [CONCERN] github_cli.py is 697 lines

The project convention is about 300 lines per file. This diff adds `get_issue`, `_issue_node` and `_next_page`. The module already splits parsing and queries into `github_parse.py` and `github_queries.py`, so issue fetching could follow the same split, for example into a `github_issue.py` that receives `_graphql` as a dependency. I did not measure the size before this diff; 697 is the current count.

### [CONCERN] Squadron-specific exemption hardcoded in the shared fairness rule

`ENVIRONMENT_ISOLATION_PATCH_TARGETS = frozenset({"squadron.cli.app._load_env_file"})` sits inside `judge_trace`, and the benchmark applies `judge_trace` to any repository it qualifies. For another project the entry is dead. For a project that happens to have a patch target with that name, it silently removes a `patches_project_code` rejection. The docstring at line 25 calls it squadron's own conftest behavior, which is the sign it belongs in per-project configuration rather than in the shared rule.

### [NOTE] get_issue re-requests the last finished connection on each remaining iteration

When a connection is exhausted, `_next_page` returns the cursor that fetched its last page. Later iterations send that same `after` cursor again, so a long rename history re-downloads the last comments page (up to 100 nodes) on each remaining iteration, and each request counts toward `MAX_DISCUSSION_PAGES`. The result stays correct, because `comments_done` gates the extend. It is wasted work. Send no cursor, or skip the field, once a connection is done.

### [NOTE] Git timeout for the sandbox command halved; discovery now inherits 30 s

The removed `GIT_TIMEOUT_S = 60` in `benchmark_sandbox.py` is replaced by `GIT_QUERY_TIMEOUT_SECONDS = 30` (`codehost/git_refs.py:24`) through `git_output`. Nothing records the change. The same 30 s bound now applies to `git log HEAD` in discovery, and a timeout there halts the build (`fix_discovery.py`, `_run_git_log`). A large history on a slow disk could hit it. Keep 60 for the sandbox command, or document the change, and decide whether the full-history log needs its own bound.

### [NOTE] Two classes named EnvironmentIdentity

`metrology/snapshot_models` and this module both define `EnvironmentIdentity`. The module docstring says they differ. `benchmark/adapter.py` re-exports this one, and `tests/metrology/test_benchmark_models.py` imports it through `squadron.benchmark.adapter`, so metrology tests depend on the package the docstring says metrology must not import. Rename this one before slice 424 consumes it.

### [NOTE] Tests bypass strict typing with object, Any and ignores

`scripted_context(..., handler: object)` and `run_collect(..., on_pytest: object)` call through `# type: ignore[operator]` (line 136). `test_python_trace.py:87` does the same with `trace_step: object`. `test_qualify_sandbox.py:234,247` passes `_unused_host() -> Any` as a `CodeHost`. `tests/benchmark/support.py:264` and `test_file_states.py:249` pass `env=None  # type: ignore[arg-type]` into `SandboxContext`. `test_real_commit_verdicts.py:162` passes `host=None`. The project requires strict pyright over tests, and these hide what the tests actually call. Typed fakes, a null host object, and a real `ScrubbedEnvironment` would remove the ignores.

### [NOTE] `_new_record` passes untyped keywords into model_validate

`_new_record(..., **fields: Any)` builds the dict for `FixQualification.model_validate`. The model uses pydantic's default `extra="ignore"`, so a misspelled keyword is dropped silently instead of rejected. The current callers pass correct names, so there is no live bug. The risk is the next edit. Give `_new_record` typed parameters.

### [NOTE] An added autouse fixture passes classification

`_is_fixture_function` accepts any `@fixture`, including `autouse=True`. An autouse fixture added with the fix runs in every test, so it changes the setup of every unchanged test at the reference, and the classification never checks that. Both the reference state and parent-plus-overlay include the fixture, so the verdicts stay internally consistent, but "unchanged" no longer means the same code at parent and reference. Consider rejecting an added autouse fixture as `modifies_test_support`, or document the choice.

### [NOTE] Load test asserts a loose bound on scripted responses

The test runs entirely on scripted in-process responses. It asserts a call count and `< 5.0 s` for parsing 1000 comments. The docstring says the calls are scripted, so it is honest about that. The bound would not catch a regression in round-trip cost, which is the path that matters for network latency. It also imports helpers from another test module (`tests.codehost.test_github_issue`). Consider stating a per-issue call-count and byte bound instead of a latency budget.

### [NOTE] Coverage and what was not checked

I read the GraphQL path (`_graphql`, `_issue_node`, `_classify_failure`, `dig_list`, `require`), the sandbox and stage error handling, the discovery keying, the patch recorder, and the separability constants. I did not read most of the roughly 60 other new files line by line, so findings on those rest on the diff text. I did not run pytest, ruff, or pyright, and the network-marked tests are unverified. Two things are worth confirming by running. First, pyright resolution of sibling imports inside `pytest_trace/` (for example `import squadron_fixcase_closure` in `squadron_fixcase_trace.py`, which has no ignore, while the test that imports it does). Second, that CI fetches full history for `test_real_commit_verdicts.py`, since `require_commit` fails rather than skips when a pinned commit is missing.

### Run Digest

- Response length: 10886 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 2120368 / 1817579 / 302775 / 64190 / not computed
- Duration: 321.1 s
- Cost: $0.67 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
